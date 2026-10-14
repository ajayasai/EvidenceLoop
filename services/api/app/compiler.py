"""Two-stage orchestration. Model output is a candidate, never displayable prose."""
from __future__ import annotations

import os
from dataclasses import replace
from urllib.parse import urlsplit

from . import domain
from .contracts import CompactExtractionCandidate, AlignmentCandidate
from .provider import AttemptBudget, ProviderConfig, ProviderError, StructuredProvider, LocalTokenCounter
from .gemini import GeminiTokenCounter, OFFICIAL_BASE
from .slot_extraction import SlotExtractionCandidate, expand_slot_claim
from .review import is_verified_clinical_pack


class ClaimCompiler:
    def __init__(self, provider=None, *, alignment_enabled=None):
        config = ProviderConfig.from_env()
        self._configuration_error = None
        self.alignment_enabled = (os.getenv("EVIDENCELOOP_ALIGNMENT_ENABLED") == "true"
                                  if alignment_enabled is None else alignment_enabled)
        if provider is not None:
            self.provider = provider
        elif config.base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            self.provider = StructuredProvider(config, token_counter=LocalTokenCounter(config.base_url))
        elif config.base_url.rstrip("/") == OFFICIAL_BASE:
            # Misconfiguration keeps capture disabled rather than breaking the
            # local replay/review interface at startup.
            try:
                counter = GeminiTokenCounter(config)
            except ProviderError as exc:
                self._configuration_error = exc.code
                self.provider = StructuredProvider(replace(config, enabled=False))
            else:
                self.provider = StructuredProvider(config, token_counter=counter)
        else:
            self.provider = StructuredProvider(config)

    @property
    def available(self):
        if self._configuration_error:
            return False
        try:
            self.provider.config.require_enabled()
            return True
        except ProviderError:
            return False

    @property
    def alignment_available(self):
        # A configuration flag is not semantic qualification. Generic live
        # claims lack a signed predicate; authored replay cannot qualify them.
        return False

    @property
    def extraction_scope(self):
        if not self.available:
            return None
        host = urlsplit(getattr(self.provider.config, "base_url", "")).hostname
        return "local" if host in {"localhost", "127.0.0.1", "::1"} else "remote"

    async def extract(self, text, intent, ledger):
        safety = domain.screen_safety(text, intent)
        if safety["urgent"]:
            return domain.interpret(text, intent, mode="manual")
        data = {"original_text": text}
        # Named nullable slots force explicit consideration of each field and
        # enforce classifier enums in the Gemini wire schema. Keep the compact
        # contract for existing local/fake adapters.
        use_slots = getattr(getattr(self.provider, "config", None), "base_url", "").rstrip("/") == OFFICIAL_BASE
        contract = SlotExtractionCandidate if use_slots else CompactExtractionCandidate
        expand = expand_slot_claim if use_slots else domain.expand_compact_claim
        try:
            if self._configuration_error:
                raise ProviderError(self._configuration_error)
            with ledger.meter():
                candidate = await self.provider.call("extraction", data, contract.model_json_schema(), ledger,
                    validator=lambda value: expand(text, value, intent))
                result = expand(text, candidate.payload, intent)
            result["model_metadata"] = {**ledger.metadata(), "model_revision": candidate.model_revision,
                "prompt_version": candidate.prompt_version, "repair_count": getattr(candidate, "repair_count", 0),
                "transient_retry_count": getattr(candidate, "transient_retry_count", 0),
                "truncation_retry_count": getattr(candidate, "truncation_retry_count", 0)}
            return result
        except (ProviderError, domain.DomainError) as exc:
            result = domain.interpret(text, intent, mode="manual")
            result["system_status"] = "model_error"
            result["reason_codes"].append(exc.code)
            result["mode_description"] = "Live extraction failed its checks. Complete and confirm the manual fields; no model interpretation is being presented."
            result["model_metadata"] = ledger.metadata()
            return result

    async def assess(self, snapshot, intent, pack, ledger):
        if not self.alignment_enabled or not domain.has_authored_comparison(snapshot):
            # Claim reading and evidence alignment are independently qualified.
            # The extraction fields do not retain the claimed effect direction:
            # "increases X" and "decreases X" can have the same confirmed nouns
            # and affirmed polarity. Library matching is useful context, but it
            # cannot warrant either exact claim. Keep safety/trust/unknown
            # failures intact and never promote a match into a scientific verdict.
            result = domain.assess(snapshot, intent, pack, mode="manual")
            domain.context_only_comparison(result, snapshot, intent)
            result["alignment_mode"] = "extraction_only"
            result["model_metadata"] = ledger.metadata()
            return result
        safety = domain.screen_safety(intent=intent, claim=snapshot)
        excluded_scope = {"pregnancy_scope", "pediatric_scope"}.intersection(safety["safety_flags"])
        if safety["urgent"] or excluded_scope or safety["health_context"] and not is_verified_clinical_pack(pack):
            result = domain.assess(snapshot, intent, pack, mode="live")
            result["alignment_mode"] = "not_permitted"
            return result
        try:
            if self._configuration_error:
                raise ProviderError(self._configuration_error)
            with ledger.meter():
                context = domain.alignment_context(snapshot, pack)
                if not context["eligible_conclusions"]:
                    result = domain.assess(snapshot,intent,pack,mode="live",alignment={"schema_version":"1.0","alignments":[]})
                    result["alignment_mode"] = "not_required"
                else:
                    context["intent"] = {k: {"state":v["state"],"value":v["value"]} for k,v in intent.items() if isinstance(v,dict) and "state" in v}
                    candidate = await self.provider.call("alignment",context,AlignmentCandidate.model_json_schema(),ledger,
                        validator=lambda value: domain.admit_alignment(snapshot,value,pack))
                    result = domain.assess(snapshot,intent,pack,mode="live",alignment=candidate.payload)
                    result["reproduction"]["model_revision"] = candidate.model_revision
                    result["alignment_mode"] = "live"
            result["model_metadata"] = ledger.metadata()
            return result
        except (ProviderError, domain.DomainError) as exc:
            result = domain.assess(snapshot,intent,pack,mode="live",alignment=None)
            result.update(case_state="cannot_assess",coverage="blocked",evidence_status="not_assessable",system_status="model_error",
                          evidence=[],supported_conclusion_ids=[],not_established_conclusion_ids=[],operator_findings=[],
                          effect_direction="undetermined",effect_direction_by_outcome=[],save_eligible=False,next_step=None,
                          summary="The model could not complete a valid evidence comparison. This is a system limitation, not a finding about the claim.")
            result["reason_codes"].append(exc.code)
            result["model_metadata"] = ledger.metadata()
            result["alignment_mode"] = "failed"
            return result
