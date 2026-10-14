"""Bounded claim compiler and deterministic, synthetic-only evidence renderer.

No rule in this module is a clinical detector or a substitute for evidence review.
Health inputs receive a coverage boundary, never a scientific health assessment.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from pydantic import ValidationError

from .contracts import (
    AlignmentCandidate, ClaimIR, CompactExtractionCandidate, Concept, ConfirmedClaimSnapshot,
    ExtractionCandidate, IntentIR, Proposition, SemanticField,
)

VERSION = "synthetic-compiler-1.1"
POLICY_VERSION = "synthetic-boundaries-1.0"
LABEL = "Fictional nonclinical demonstration — no real research or clinical review"
PACK_PATH = Path(__file__).resolve().parents[3] / "evidence" / "synthetic_nonclinical.json"
CONCEPT_FIELDS = {
    "population", "condition_context", "intervention", "comparator", "measured_outcome",
    "claimed_clinical_outcome", "mechanism", "safety_outcome",
}
INTENT_FIELDS = {"action_kind", "target", "current_care_relationship", "timing", "actor", "endorsement"}
REQUIRED_FIELDS = ("population", "intervention", "measured_outcome", "polarity", "relation")
ROUTE_ORDER = {"education": 0, "clarify": 1, "professional_review_recommended": 2, "urgent_escalation": 3}
HEALTH = re.compile(r"\b(medic(?:al|ine|ines|ation|ations)|prescri(?:bed|ption)|diabet(?:es|ic)|insulin|metformin|pregnan\w*|breastfeed\w*|cancer|patient|treatment|supplement|dose|dosage|symptom|blood\s+(?:sugar|glucose)|chest\s+pain|breath(?:e|ing|less)|seizure|unconscious|bleeding|cure|doctor|clinician)\b", re.I)
# These limited engineering sentinels are deliberately not marketed as emergency triage.
URGENT_CURRENT = re.compile(r"\b(?:I|my\s+(?:child|partner|parent)|he|she)\s+(?:am\s+|is\s+)?(?:(?:have|has|having)\s+(?:severe\s+)?chest\s+pain|cannot\s+breathe|can['’]t\s+breathe|struggling\s+to\s+breathe|unconscious|bleeding\s+heavily)\b", re.I)
PREGNANCY = re.compile(r"\b(?:I\s+am|I'm|she\s+is|my\s+partner\s+is)\s+pregnant\b", re.I)
PEDIATRIC = re.compile(r"\b(?:my\s+(?:child|baby)|for\s+(?:a\s+)?(?:child|baby)|[1-9][ -]year[ -]old)\b", re.I)


class DomainError(ValueError):
    def __init__(self, code: str, message: str | None = None, status_code: int = 422):
        self.code = code
        self.status_code = status_code
        super().__init__(message or code.replace("_", " "))


def _id() -> str:
    return str(uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str | dict | list) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _value(obj: dict, name: str):
    v = obj.get(name)
    if isinstance(v, dict) and "state" in v:
        return v.get("value") if v.get("state") == "stated" else None
    return v


def _concept(obj: dict, name: str) -> dict:
    value = _value(obj, name)
    return value if isinstance(value, dict) else {}


def _route(*routes: str) -> str:
    return max(routes, key=lambda r: ROUTE_ORDER[r])


def _unknown() -> dict:
    return {"state": "unknown", "value": None, "provenance": []}


def _bounded_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise DomainError("empty_input")
    if len(text) > 6000 or len(text.encode("utf-8")) > 24576:
        raise DomainError("input_too_large", "Use at most 6,000 characters and 24 KiB of text.", 413)
    if "\x00" in text:
        raise DomainError("invalid_character")


def _normalize_with_map(text: str) -> tuple[str, list[list[int]]]:
    """NFC/CRLF normalization maps each output code point to original range."""
    clusters: list[tuple[str, int, int]] = []
    i = 0
    while i < len(text):
        start = i
        if text[i:i+2] == "\r\n":
            clusters.append(("\n", i, i+2))
            i += 2
            continue
        cluster = text[i]
        i += 1
        while i < len(text) and text[i] not in "\r\n" and (
            unicodedata.combining(text[i]) or
            len(unicodedata.normalize("NFC", cluster + text[i])) < len(unicodedata.normalize("NFC", cluster)) + 1
        ):
            cluster += text[i]
            i += 1
        normalized = unicodedata.normalize("NFC", cluster).replace("\r", "\n")
        clusters.append((normalized, start, i))
    return "".join(c[0] for c in clusters), [[s, e] for chunk, s, e in clusters for _ in chunk]


def _strip_quoted(text: str) -> str:
    # Quoted claims remain health-context evidence but do not alone imply current symptoms.
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”', " ", text)
    return text


def screen_safety(text: str = "", intent: dict | None = None, claim: dict | None = None) -> dict:
    """Conservative fixed routing for internal sentinels, not comprehensive triage."""
    intent = intent or {}
    claim = claim or {}
    flags = set(claim.get("safety_flags", []))
    plain = _strip_quoted(text)
    if HEALTH.search(text):
        flags.add("health_context")
    if URGENT_CURRENT.search(plain):
        flags.add("current_serious_concern")
    if PREGNANCY.search(plain):
        flags.add("pregnancy_scope")
    if PEDIATRIC.search(plain) and "health_context" in flags:
        flags.add("pediatric_scope")
    target = _value(intent, "target") or ""
    if isinstance(target, str) and HEALTH.search(target):
        flags.add("health_context")
    if claim.get("confirmed_proposition"):
        for key, val in claim["confirmed_proposition"].items():
            if key in CONCEPT_FIELDS and isinstance(val, dict):
                surface = (val.get("value") or {}).get("surface", "")
                if HEALTH.search(surface):
                    flags.add("health_context")
    action = _value(intent, "action_kind")
    relationship = _value(intent, "current_care_relationship")
    conflicting_intent = (action == "add" and relationship == "instead_of") or (action in {"replace", "stop"} and relationship == "alongside")
    if conflicting_intent:
        flags.add("conflicting_intent")
    if "health_context" in flags and action in {"replace", "stop", "delay", "change_dose", "seek_cure", "start", "add"}:
        flags.add("proposed_health_action")
    if "health_context" in flags and relationship == "instead_of":
        flags.add("care_replacement")
    route, rules = "education", []
    if not action or conflicting_intent:
        route, rules = "clarify", ["G07"]
    if "health_context" in flags:
        rules.append("G08")
    if "proposed_health_action" in flags or "care_replacement" in flags:
        route = _route(route, "professional_review_recommended")
        rules.append("G02" if action == "stop" else "G03")
    for flag, rule in (("pregnancy_scope", "G04"), ("pediatric_scope", "G05")):
        if flag in flags:
            route = _route(route, "professional_review_recommended")
            rules.append(rule)
    if "current_serious_concern" in flags:
        route = "urgent_escalation"
        rules.append("G01")
    return {"route": route, "reason_codes": sorted(flags), "policy_rule_ids": sorted(set(rules)),
            "safety_flags": sorted(flags), "health_context": "health_context" in flags,
            "urgent": "current_serious_concern" in flags,
            "can_assess": "health_context" not in flags and action is not None and not conflicting_intent}


def _intent(data: dict | None, claim_version: str, confirmation: str | None = None) -> dict:
    data = data or {}
    allowed = INTENT_FIELDS | {"schema_version", "intent_id", "version_id", "claim_version_id", "confirmed_at", "confirmation_event_id"}
    if set(data) - allowed:
        raise DomainError("invalid_intent_field")
    event = confirmation or _id()
    result = {"intent_id": data.get("intent_id") or _id(), "version_id": _id(), "claim_version_id": claim_version}
    for field in INTENT_FIELDS:
        raw = data.get(field)
        if isinstance(raw, dict) and "state" in raw:
            raw = raw.get("value") if raw.get("state") == "stated" else None
        result[field] = _unknown() if raw is None else {
            "state": "stated", "value": raw,
            "provenance": [{"kind": "user_confirmation", "confirmation_event_id": event}],
        }
    if confirmation:
        result.update(confirmed_at=_now(), confirmation_event_id=confirmation)
    try:
        return IntentIR.model_validate(result).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_intent") from exc


def _span(text: str, quote: str) -> dict:
    start = text.index(quote)
    return {"kind": "input_span", "input_hash": _hash(text), "start": start, "end": start + len(quote), "quote": quote}


def _stated(text: str, quote: str, value) -> dict:
    return {"state": "stated", "value": value, "provenance": [_span(text, quote)]}


def _fixture_proposition(fixture: dict) -> dict:
    text = fixture["text"]
    p = {"proposition_id": "proposition-1", "speaker": fixture.get("speaker", "quoted_source"),
         "speech_act": fixture.get("speech_act", "reported_assertion")}
    for key, definition in fixture["fields"].items():
        quote, value = definition
        p[key] = _stated(text, quote, value)
    return Proposition.model_validate(p).model_dump(mode="json")


def _fixtures() -> list[dict]:
    """Exact strings only; fixture extraction is never described as live AI."""
    def c(surface, id):
        return {"surface": surface, "concept_id": id}
    def fields(pop, inter, outcome="next-day recall", outcome_id="next-day-recall", polarity="affirmed", relation="causal"):
        return {"population": (pop, c(pop, "fern-lab" if "Fern" in pop else "study-club")),
                "intervention": (inter, c(inter, {"glow water":"glow-water","glow spray":"glow-water","moon cards":"moon-cards","quiet cards":"quiet-cards","blue cards":"blue-cards","short quizzes":"short-quizzes","spark cards":"spark-cards"}[inter])),
                "measured_outcome": (outcome, c(outcome, outcome_id)),
                "polarity": ("not" if polarity == "negated" else inter, polarity),
                "relation": (inter, relation), "certainty": (inter, "asserted"),
                "generalization": (pop, "scoped_population")}
    learn = {"action_kind":"learn", "actor":"hypothetical", "current_care_relationship":"unrelated", "endorsement":"uncertain"}
    records = []
    def add(id, title, text, p, expected, intent=None):
        records.append({"id":id,"title":title,"text":text,"fields":p,"intent":intent or deepcopy(learn),"expected":expected,"label":LABEL,"visibility":"public_nonclinical"})
    p = fields("fictional Fern Lab", "glow water", "fern height", "fern-height")
    p.update(formulation=("glow water","water"),comparator=("plain water",c("plain water","plain-water")),timeframe=("seven days",{"value":7,"unit":"days"}))
    add("fern-supported","A finding within its scope","In the fictional Fern Lab, glow water increased fern height over seven days compared with plain water.",p,"supports_within_scope")
    p = fields("fictional Fern Lab", "glow water", "fern height", "fern-height")
    p.update(generalization=("every plant","universal"),certainty=("guaranteed","guaranteed"),formulation=("glow water","water"))
    add("fern-certainty","From a narrow finding to a guarantee","The fictional Fern Lab says glow water is guaranteed to increase fern height in every plant.",p,"insufficient")
    p=fields("fictional Fern Lab", "glow spray", "fern height", "fern-height")
    p.update(formulation=("glow spray","spray"))
    add("fern-formulation","A similar name is not equivalence","In the fictional Fern Lab, glow spray increases fern height.",p,"insufficient")
    p=fields("fictional Study Club", "moon cards")
    add("moon-insufficient","Incomplete evidence","In the fictional Study Club, moon cards improve next-day recall.",p,"insufficient")
    p=fields("fictional Study Club", "quiet cards",polarity="negated")
    p["negation_scope"]=("not",["measured_outcome"])
    add("quiet-no-effect","An explicit finding of no effect","In the fictional Study Club, quiet cards do not change next-day recall.",p,"supports_within_scope")
    p=fields("fictional Study Club", "quiet cards")
    add("quiet-contradicted","Evidence can contradict a proposition","In the fictional Study Club, quiet cards improve next-day recall.",p,"contradicts_within_scope")
    p=fields("fictional Study Club", "blue cards")
    add("blue-conflicting","Keep conflicting findings visible","In the fictional Study Club, blue cards improve next-day recall.",p,"conflicting")
    p=fields("fictional Study Club", "short quizzes")
    p["co_intervention"]=("normal lessons","normal lessons")
    text="In the fictional Study Club, short quizzes alongside normal lessons improved next-day recall."
    add("quiz-alongside","Evidence for an add-on",text,p,"supports_within_scope",{"action_kind":"add","target":"short quizzes","actor":"hypothetical","current_care_relationship":"alongside","endorsement":"uncertain"})
    p=fields("fictional Study Club", "short quizzes")
    p["co_intervention"]=("normal lessons","normal lessons")
    add("quiz-replacement","Change the action, keep the claim","In the fictional Study Club, short quizzes with normal lessons improved next-day recall.",p,"supports_within_scope",{"action_kind":"replace","target":"normal lessons","actor":"hypothetical","current_care_relationship":"instead_of","endorsement":"uncertain"})
    p=fields("fictional Study Club", "short quizzes")
    p["claimed_clinical_outcome"]=("graduation",c("graduation","graduation"))
    add("quiz-outcome-leap","A short measurement is not a later outcome","In the fictional Study Club, short quizzes improve next-day recall, so they improve graduation.",p,"insufficient")
    p=fields("fictional Study Club", "spark cards")
    add("spark-causation","Association is not a causal warrant","In the fictional Study Club, spark cards cause better next-day recall.",p,"insufficient")
    p=fields("fictional Study Club", "spark cards",relation="associative")
    add("spark-association","An association within its scope","In the fictional Study Club, spark cards are associated with better next-day recall.",p,"supports_within_scope")
    p=fields("fictional Study Club", "spark cards")
    p["mechanism"]=("attention",c("attention","attention"))
    add("spark-mechanism","A mechanism does not establish benefit","In the fictional Study Club, spark cards improve attention, so they improve next-day recall.",p,"insufficient")
    p=fields("fictional Fern Lab", "glow water", "fern height", "fern-height")
    p["safety_outcome"]=("safe",c("safe","plant-safety"))
    add("fern-safety","Benefit does not establish safety","In the fictional Fern Lab, glow water increased fern height, so it is safe.",p,"insufficient")
    return records


def fixture_catalog(include_internal: bool = False) -> list[dict]:
    result = [{k:deepcopy(v) for k,v in r.items() if k != "fields"} for r in _fixtures()]
    if include_internal:
        result.extend(internal_safety_fixtures())
    return result


def _comparison_signature(proposition: dict) -> dict:
    """Compare confirmed meaning, not transient IDs or discarded quotations."""
    return {
        name: {"state": value["state"], "value": value["value"]}
        if isinstance(value, dict) and "state" in value else value
        for name, value in proposition.items()
        if name not in {"proposition_id", "attribution_text"}
    }


def has_authored_comparison(snapshot: dict) -> bool:
    """Only an unchanged, explicitly authored replay preserves a known predicate.

    Generic noun slots cannot distinguish increasing from decreasing an outcome.
    Polarity is negation, not effect direction. Neither an alignment model nor a
    user's confirmation can restore meaning which the schema never represented.
    Replay retains its narrowly authored meaning through content-free input
    hashes plus an exact semantic frame match. An edited frame must abstain.
    """
    if snapshot.get("mode") != "replay":
        return False
    origins = {ref["input_hash"] for ref in snapshot.get("provenance_refs", [])
               if ref.get("input_hash")}
    if len(origins) != 1:
        return False
    signature = _comparison_signature(snapshot.get("confirmed_proposition", {}))
    for fixture in _fixtures():
        if origins == {_hash(fixture["text"])}:
            return signature == _comparison_signature(_fixture_proposition(fixture))
    return False


def context_only_comparison(result: dict, snapshot: dict, intent: dict) -> dict:
    """Retain source context and prior boundaries, removing claim-level warrants."""
    if result["case_state"] == "assessed" and result["system_status"] == "ok":
        operator_codes = {finding["reason_code"] for finding in result["operator_findings"]
                          if finding["operator_state"] == "established"}
        safety_codes = screen_safety(intent=intent, claim=snapshot)["reason_codes"]
        result["reason_codes"] = [code for code in result["reason_codes"]
                                  if code not in operator_codes or code in safety_codes]
        result.update(
            case_state="cannot_assess", evidence_status="not_assessable", applicability="unknown",
            supported_conclusion_ids=[], not_established_conclusion_ids=[], operator_findings=[],
            argument_graph={"nodes": [], "edges": []}, effect_direction="undetermined",
            effect_direction_by_outcome=[],
            summary="This comparison cannot establish whether the evidence supports the exact effect being claimed. Library information is shown as context only.",
        )
        if result["route"] == "education":
            result["action_boundary"] = "Matched library information does not establish the claimed effect or justify the proposed action."
    result.pop("admitted_alignment", None)
    result["save_eligible"] = False
    result["next_step"] = None
    result["comparison_basis"] = "context_only"
    if "exact_claim_comparison_unqualified" not in result["reason_codes"]:
        result["reason_codes"].append("exact_claim_comparison_unqualified")
    return result


def internal_safety_fixtures() -> list[dict]:
    return [
        {"id":"INTERNAL-HEALTH-STOP","title":"Internal stop-care sentinel","text":"I plan to stop prescribed medication.","intent":{"action_kind":"stop","target":"prescribed medication","actor":"self"},"expected_route":"professional_review_recommended","visibility":"internal_only"},
        {"id":"INTERNAL-HEALTH-URGENT","title":"Internal serious-concern sentinel","text":"I cannot breathe and I have a question about medication.","intent":{"action_kind":"learn"},"expected_route":"urgent_escalation","visibility":"internal_only"},
        {"id":"INTERNAL-QUOTED-CONCERN","title":"Quoted concern is not current symptom","text":"The article says \"I cannot breathe\" as an example of a symptom.","intent":{"action_kind":"learn","actor":"hypothetical"},"expected_route":"education","visibility":"internal_only"},
    ]


def _validate_spans(text: str, propositions: list[dict]) -> None:
    for p in propositions:
        for field in p.values():
            if not isinstance(field, dict) or "state" not in field:
                continue
            for origin in field.get("provenance", []):
                if origin["kind"] != "input_span":
                    raise DomainError("invalid_extraction_provenance")
                start, end = origin["start"], origin["end"]
                if origin["input_hash"] != _hash(text) or end > len(text) or text[start:end] != origin["quote"]:
                    raise DomainError("invalid_original_span")


def _claim(text: str, propositions: list[dict], mode: str, safety: dict, unresolved=None) -> dict:
    normalized, mapping = _normalize_with_map(text)
    _validate_spans(text, propositions)
    try:
        return ClaimIR.model_validate({"claim_id":_id(),"version_id":_id(),"input_hash":_hash(text),"original_text":text,
            "normalized_text":normalized,"normalization_map":mapping,"propositions":propositions,
            "unresolved_fields":unresolved or [],"extraction_run_id":_id(),"mode":mode,
            "prompt_version":"extraction-1.0" if mode=="live" else "fixture-1.0", "safety_flags":safety["safety_flags"]}).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_claim_schema") from exc


def interpret(text: str, intent: dict | None = None, mode: str = "replay") -> dict:
    _bounded_text(text)
    if mode not in {"replay", "manual"}:
        raise DomainError("live_provider_required", "Live extraction requires the configured provider adapter.")
    safety = screen_safety(text, intent)
    fixture = next((r for r in _fixtures() if r["text"] == text), None) if mode=="replay" else None
    if fixture:
        propositions = [_fixture_proposition(fixture)]
        unresolved = []
        actual_mode, status = "replay", "ok"
    else:
        propositions = [Proposition(proposition_id="proposition-1").model_dump(mode="json")]
        unresolved = list(REQUIRED_FIELDS)
        actual_mode, status = "manual", "ok"
    claim = _claim(text, propositions, actual_mode, safety, unresolved)
    intention = _intent(intent, claim["version_id"])
    return {"claim":claim,"intent":intention,"case_state":"needs_confirmation",
            "route":_route(safety["route"], "clarify" if not fixture else "education"),
            "reason_codes":safety["reason_codes"] + ([] if fixture else ["exact_replay_not_found", "manual_confirmation_required"]),
            "policy_rule_ids":safety["policy_rule_ids"],"system_status":status,"mode":actual_mode,
            "fixture_id":fixture["id"] if fixture else None,"synthetic_label":LABEL,
            "mode_description":"Exact recorded fixture extraction; no model was called." if fixture else "Manual frame required; this text was not interpreted by a model."}


def validate_live_claim(text: str, payload: dict, intent: dict | None = None) -> dict:
    _bounded_text(text)
    safety = screen_safety(text, intent)
    try:
        candidate = ExtractionCandidate.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_claim_schema") from exc
    claim = _claim(text, candidate["propositions"], "live", safety, candidate["unresolved_fields"])
    # An extracted intent proposal cannot silently replace the separate user answer.
    intention = _intent(intent, claim["version_id"])
    return {"claim":claim,"intent":intention,"case_state":"needs_confirmation","route":safety["route"],
            "reason_codes":safety["reason_codes"],"policy_rule_ids":safety["policy_rule_ids"],
            "system_status":"ok","mode":"live","fixture_id":None,"synthetic_label":LABEL}


def expand_compact_claim(text: str, payload: dict, intent: dict | None = None) -> dict:
    """Expand exact quote references; the model does not calculate hashes or offsets."""
    _bounded_text(text)
    try:
        candidate=CompactExtractionCandidate.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_compact_extraction") from exc
    propositions=[]
    for compact in candidate["propositions"]:
        p={k:compact[k] for k in ("proposition_id","speaker","speech_act")}
        for field in compact["fields"]:
            name=field["name"]
            if name in p:
                raise DomainError("duplicate_extracted_field")
            quote=field["quote"]
            if name in CONCEPT_FIELDS:
                # Exact span existence alone does not ground an unrelated surface.
                # Normalization preserves Unicode spelling, not semantic paraphrases.
                literal=lambda value: unicodedata.normalize("NFC",value.strip())
                if literal(field["value"])!=literal(quote):
                    raise DomainError("extracted_surface_quote_mismatch")
            starts=[match.start() for match in re.finditer(re.escape(quote),text)]
            if not starts or (len(starts)>1 and field["occurrence"] is None):
                raise DomainError("quote_missing_or_ambiguous")
            occurrence=field["occurrence"] or 0
            if occurrence>=len(starts):
                raise DomainError("invalid_quote_occurrence")
            start=starts[occurrence]
            value=_edited_value(name,field["value"])
            p[name]={"state":"stated","value":value,"provenance":[{"kind":"input_span","input_hash":_hash(text),"start":start,"end":start+len(quote),"quote":quote}]}
        propositions.append(p)
    return validate_live_claim(text,{"propositions":propositions,"unresolved_fields":candidate["unresolved_fields"]},intent)


def _concept_id(surface: str) -> str | None:
    aliases = {"fictional fern lab":"fern-lab", "fictional study club":"study-club", "plain water":"plain-water",
        "plain cards":"plain-cards", "normal lessons":"normal-lessons", "graduation":"graduation", "attention":"attention", "safe":"plant-safety"}
    for family in load_pack()["families"]:
        for alias in family["intervention_aliases"]:
            aliases[alias.casefold()] = family["intervention_id"]
        for alias in family["outcome_aliases"]:
            aliases[alias.casefold()] = family["outcome_id"]
    return aliases.get(surface.casefold().strip())


def _edited_value(name: str, value):
    if name in CONCEPT_FIELDS:
        surface = value.get("surface") if isinstance(value, dict) else value
        if not isinstance(surface, str) or not surface.strip():
            raise DomainError("invalid_concept")
        surface = unicodedata.normalize("NFC", surface.strip())
        return {"surface":surface, "concept_id":_concept_id(surface)}
    return unicodedata.normalize("NFC", value.strip()) if isinstance(value, str) else value


def confirm(claim: dict, intent: dict, selected_proposition_id: str | None = None, edits: dict | None = None) -> dict:
    try:
        original = ClaimIR.model_validate(claim).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_claim_schema") from exc
    if original["input_hash"] != _hash(original["original_text"]):
        raise DomainError("input_hash_mismatch")
    _validate_spans(original["original_text"], original["propositions"])
    selected = selected_proposition_id or original.get("selected_proposition_id")
    if not selected:
        if len(original["propositions"]) != 1:
            raise DomainError("select_one_proposition")
        selected = original["propositions"][0]["proposition_id"]
    proposition = next((deepcopy(p) for p in original["propositions"] if p["proposition_id"]==selected), None)
    if not proposition:
        raise DomainError("invalid_proposition_selection")
    event, version = _id(), _id()
    edits = edits or {}
    allowed = set(Proposition.model_fields) - {"proposition_id", "missing_assumptions"}
    if set(edits) - allowed:
        raise DomainError("invalid_edit_field")
    for name, raw in edits.items():
        if name in {"speaker", "speech_act"}:
            proposition[name] = raw
            continue
        if isinstance(raw, dict) and "state" in raw:
            state, val = raw["state"], raw.get("value")
        else:
            state, val = ("unknown", None) if raw is None or raw == "" else ("stated", raw)
        proposition[name] = {"state":state,"value":_edited_value(name,val) if state=="stated" else None,
            "provenance":[{"kind":"user_confirmation","confirmation_event_id":event}] if state=="stated" else []}
    try:
        proposition = Proposition.model_validate(proposition).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_confirmed_field") from exc
    intention = _intent(intent, version, event)
    safety = screen_safety(original["original_text"], intention, original)
    # Preserve full-input safety constraints even when another proposition is selected.
    provisional = {"confirmed_proposition":proposition,"safety_flags":safety["safety_flags"]}
    safety = screen_safety("", intention, provisional)
    if "conflicting_intent" in safety["reason_codes"]:
        raise DomainError("conflicting_intent", "The action and its relationship to the current activity disagree; confirm the intended action.")
    missing = [name for name in REQUIRED_FIELDS if proposition[name]["state"] != "stated"]
    if _value(intention, "action_kind") is None:
        raise DomainError("confirmation_incomplete", "Confirm your intended action before continuing.")
    references = []
    for name, field in proposition.items():
        if not isinstance(field, dict) or "state" not in field:
            continue
        minimized = []
        for origin in field["provenance"]:
            ref_id = _id()
            references.append({"ref_id":ref_id,"field_path":name,"input_hash":origin.get("input_hash"),
                "start":origin.get("start"),"end":origin.get("end"),"confirmation_event_id":origin.get("confirmation_event_id")})
            minimized.append({"kind":"saved_ref","ref_id":ref_id})
        field["provenance"] = minimized
    # Attribution is ephemeral: it is neither needed for assessment nor retained as raw quotation.
    proposition["attribution_text"] = _unknown()
    references = [r for r in references if r["field_path"] != "attribution_text"]
    snapshot = ConfirmedClaimSnapshot.model_validate({"claim_id":original["claim_id"],"version_id":version,
        "parent_version_id":original["parent_version_id"],"selected_proposition_id":selected,
        "confirmed_proposition":proposition,"confirmed_at":_now(),"confirmation_event_id":event,
        "origin_claim_ir_version":original["version_id"],"provenance_refs":references,
        "safety_flags":safety["safety_flags"],"mode":original["mode"]}).model_dump(mode="json")
    return {"snapshot":snapshot,"intent":intention,"route":_route(safety["route"],"clarify") if missing else safety["route"],
            "reason_codes":safety["reason_codes"] + (["confirmation_incomplete"] if missing else []),
            "policy_rule_ids":safety["policy_rule_ids"],"system_status":"ok","case_state":"needs_confirmation" if missing else "ready",
            "unassessed_proposition_ids":[p["proposition_id"] for p in original["propositions"] if p["proposition_id"]!=selected]}


def load_pack(path: str | Path | None = None) -> dict:
    try:
        pack = json.loads(Path(path or PACK_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DomainError("evidence_pack_unavailable", status_code=503) from exc
    validate_pack(pack)
    return pack


def validate_pack(pack: dict) -> None:
    """Hash/reference integrity, not proof of scientific entailment or review."""
    try:
        if pack.get("domain")=="clinical_reviewed":
            from .review import is_verified_clinical_pack
            if not is_verified_clinical_pack(pack):
                raise DomainError("publication_verification_required")
            return
        if pack["schema_version"] != "EvidencePack/1.0" or pack["domain"] != "synthetic_nonclinical" or pack["clinical_review"] is not False:
            raise DomainError("clinical_publication_not_enabled")
        if not (1 <= len(pack["sources"]) <= 20 and 1 <= len(pack["conclusions"]) <= 40 and 1 <= len(pack["families"]) <= 12):
            raise DomainError("evidence_pack_bounds")
        source_ids, anchor_ids, conclusion_ids, family_ids = set(), set(), set(), set()
        anchors = {}
        for source in pack["sources"]:
            sid = source["source_version_id"]
            if sid in source_ids or source["synthetic"] is not True or source["canonical_url"] is not None:
                raise DomainError("invalid_synthetic_source")
            source_ids.add(sid)
            if source["content_hash"] != _hash(source["text"]):
                raise DomainError("source_hash_mismatch")
            for a in source["anchors"]:
                if a["anchor_id"] in anchor_ids or a["source_version_id"] != sid:
                    raise DomainError("invalid_anchor_reference")
                if not (0 <= a["start"] < a["end"] <= len(source["text"])) or source["text"][a["start"]:a["end"]] != a["quote"] or _hash(a["quote"]) != a["quote_hash"]:
                    raise DomainError("broken_anchor")
                anchor_ids.add(a["anchor_id"])
                anchors[a["anchor_id"]] = a
        for conclusion in pack["conclusions"]:
            cid = conclusion["conclusion_id"]
            if cid in conclusion_ids or conclusion["source_version_id"] not in source_ids or not conclusion["anchor_ids"]:
                raise DomainError("invalid_conclusion_reference")
            conclusion_ids.add(cid)
            if conclusion["review_status"] != "synthetic_author_check_only":
                raise DomainError("unverified_review_claim")
            if any(a not in anchors or anchors[a]["source_version_id"] != conclusion["source_version_id"] for a in conclusion["anchor_ids"]):
                raise DomainError("invalid_conclusion_anchor")
        for family in pack["families"]:
            if family["family_id"] in family_ids or not family["conclusion_ids"] or len(family["conclusion_ids"]) > 8:
                raise DomainError("invalid_family")
            family_ids.add(family["family_id"])
            if any(cid not in conclusion_ids for cid in family["conclusion_ids"]):
                raise DomainError("invalid_family_conclusion")
        for conclusion in pack["conclusions"]:
            if conclusion["family_id"] not in family_ids:
                raise DomainError("invalid_conclusion_family")
            owner = next(f for f in pack["families"] if f["family_id"]==conclusion["family_id"])
            if conclusion["conclusion_id"] not in owner["conclusion_ids"]:
                raise DomainError("conclusion_family_mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, DomainError):
            raise
        raise DomainError("invalid_evidence_pack") from exc


def _match_family(proposition: dict, pack: dict) -> dict | None:
    intervention = _concept(proposition, "intervention")
    surface = intervention.get("surface", "").casefold().strip()
    # A fabricated concept ID cannot route an unrelated surface into a trusted family.
    matches = [f for f in pack["families"] if surface in [a.casefold() for a in f["intervention_aliases"]]]
    return matches[0] if len(matches)==1 else None


def _dependencies(family: dict, pack: dict) -> list[dict]:
    conclusions = [c for c in pack["conclusions"] if c["conclusion_id"] in family["conclusion_ids"]]
    deps = [{"id":family["family_id"],"kind":"family","role":"context"}]
    for dependency in family.get("source_dependencies",[]):
        deps.append({"id":dependency["source_version_id"],"kind":"source_version","role":dependency["role"]})
    for c in conclusions:
        deps.extend([{"id":c["conclusion_id"],"kind":"conclusion","role":"conflicts" if family.get("warrant_mode")=="conflicting" or family.get("conflicts") else "supports"},
                     {"id":c["source_version_id"],"kind":"source_version","role":"context"},
                     {"id":c["brief_version_id"],"kind":"brief_version","role":"limits"}])
    return [dict(t) for t in {tuple(sorted(x.items())) for x in deps}]


def current_trust(dependencies: list[dict] | list[str], pack: dict | None = None) -> dict:
    try:
        pack = pack or load_pack()
        validate_pack(pack)
    except DomainError:
        return {"checked_at":_now(),"state":"integrity_error","affected_dependency_ids":[],"notice_id":None}
    ids = {x if isinstance(x,str) else x["id"] for x in dependencies}
    affected = []
    states = [pack.get("trust_state", "current")]
    known = {x["source_version_id"] for x in pack["sources"]} | {x["source_id"] for x in pack["sources"]} | {x["family_id"] for x in pack["families"]}
    known |= {x["conclusion_id"] for x in pack["conclusions"]} | {x["brief_version_id"] for x in pack["conclusions"]}
    if ids - known:
        return {"checked_at":_now(),"state":"integrity_error","affected_dependency_ids":sorted(ids-known),"notice_id":None}
    for obj in pack["sources"] + pack["families"]:
        oid = obj.get("source_version_id") or obj.get("family_id")
        state = obj.get("trust_state", "current")
        runtime = pack.get("trust_states", {}).get(obj.get("source_id", ""))
        if runtime:
            state = runtime.get("state", "integrity_error")
        if (oid in ids or obj.get("source_id") in ids) and state != "current":
            affected.append(oid)
            states.append(state)
    order = {"current":0,"superseded":1,"under_review":2,"withdrawn":3,"integrity_error":4}
    state = max(states, key=lambda s:order.get(s,4))
    if state not in order:
        state = "integrity_error"
    return {"checked_at":_now(),"state":state,"affected_dependency_ids":affected,"notice_id":None}


def _operators(p: dict, intent: dict, family: dict, conclusions: list[dict]) -> list[dict]:
    result = []
    candidates = {
        "L03": (_concept(p,"claimed_clinical_outcome").get("concept_id") not in {None, family["outcome_id"]}, ["measured_outcome","claimed_clinical_outcome"], "measured_outcome_to_distinct_outcome", "The measured outcome does not establish the different outcome in this fictional claim."),
        "L04": (family["relation"]=="associative" and _value(p,"relation")=="causal", ["relation"], "association_without_causal_warrant", "The fictional observation establishes an association, not the proposed causal explanation."),
        "L05": (_concept(p,"population").get("concept_id") not in {None,family["population_id"]}, ["population"], "population_outside_fixture_scope", "The proposed population is outside this fictional evidence scope."),
        "L07": (_value(p,"formulation") is not None and _value(p,"formulation") != family["formulation"], ["formulation"], "formulation_without_equivalence", "A different formulation has no equivalence warrant in this fictional evidence."),
        "L08": (_value(p,"certainty")=="guaranteed" or _value(p,"generalization")=="universal", ["certainty","generalization"], "certainty_exceeds_fixture_scope", "This fictional result does not establish a guarantee or a result for every population."),
        "L09": (_value(intent,"action_kind")=="replace" or _value(intent,"current_care_relationship")=="instead_of", ["intent.action_kind","intent.current_care_relationship"], "adjunct_does_not_authorize_replacement", "The fictional exercise tested quizzes alongside lessons; it did not establish replacement of lessons."),
        "L11": (_value(p,"safety_outcome") is not None, ["safety_outcome"], "benefit_without_safety_warrant", "The fictional benefit finding does not establish safety."),
        "L15": (_value(p,"mechanism") is not None and _value(p,"relation")=="causal", ["mechanism","relation"], "mechanism_without_benefit_warrant", "The proposed mechanism does not establish benefit in this fictional evidence."),
    }
    for op in family["enabled_operators"]:
        yes, paths, code, text = candidates[op]
        known = any(_value(intent if name.startswith("intent.") else p, name.split(".")[-1]) is not None for name in paths)
        state = "established" if yes else "not_detected" if known else "unknown"
        result.append({"operator_id":op,"operator_version":"1.0","operator_state":state,
            "claim_field_paths":paths,"evidence_conclusion_ids":[c["conclusion_id"] for c in conclusions],
            "anchor_ids":[a for c in conclusions for a in c["anchor_ids"]],"graph_edge_id":"edge-action" if op=="L09" else "edge-evidence",
            "reason_code":code if yes else "no_defined_mismatch_detected" if known else "required_field_unknown",
            "explanation":text if yes else None})
    return result


def admit_alignment(snapshot: dict, payload: dict, pack: dict | None = None) -> dict:
    pack = pack or load_pack()
    validate_pack(pack)
    snap = ConfirmedClaimSnapshot.model_validate(snapshot).model_dump(mode="json")
    if not has_authored_comparison(snap):
        raise DomainError("exact_claim_comparison_unqualified")
    family = _match_family(snap["confirmed_proposition"],pack)
    try:
        candidate = AlignmentCandidate.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("invalid_alignment_schema") from exc
    if not family and candidate["alignments"]:
        raise DomainError("alignment_outside_library")
    allowed = {c["conclusion_id"]:c for c in pack["conclusions"] if family and c["conclusion_id"] in family["conclusion_ids"]}
    seen = set()
    for item in candidate["alignments"]:
        cid = item["conclusion_id"]
        if cid not in allowed or cid in seen or item["proposition_id"] != snap["selected_proposition_id"]:
            raise DomainError("invalid_alignment_reference")
        seen.add(cid)
        if item["relation_candidate"] not in allowed[cid]["allowed_relations"]:
            raise DomainError("unapproved_relation")
        for op in item["operator_candidates"]:
            if op["operator_id"] not in family["enabled_operators"] or any(c not in allowed for c in op["conclusion_ids"]):
                raise DomainError("unapproved_operator")
            anchors = {a for c in op["conclusion_ids"] for a in allowed[c]["anchor_ids"]}
            if any(a not in anchors for a in op["anchor_ids"]):
                raise DomainError("invented_anchor")
            if any(path.split(".")[-1] not in Proposition.model_fields and path not in {"intent.action_kind","intent.current_care_relationship"} for path in op["claim_paths"]):
                raise DomainError("invalid_alignment_path")
    # All linked conflict/limiting conclusions must remain in the comparison.
    if family and (family.get("warrant_mode")=="conflicting" or family.get("conflicts")) and seen != set(allowed):
        raise DomainError("conflicting_evidence_omitted")
    return candidate


def alignment_context(snapshot: dict, pack: dict | None = None) -> dict:
    pack=pack or load_pack()
    validate_pack(pack)
    snap=ConfirmedClaimSnapshot.model_validate(snapshot).model_dump(mode="json")
    family=_match_family(snap["confirmed_proposition"],pack)
    conclusions=[c for c in pack["conclusions"] if family and c["conclusion_id"] in family["conclusion_ids"]]
    anchor_ids={a for c in conclusions for a in c["anchor_ids"]}
    anchors=[{"anchor_id":a["anchor_id"],"quote":a["quote"]} for s in pack["sources"] for a in s["anchors"] if a["anchor_id"] in anchor_ids]
    claim={name:{"state":value["state"],"value":value["value"]} if isinstance(value,dict) and "state" in value else value
           for name,value in snap["confirmed_proposition"].items() if name not in {"attribution_text","missing_assumptions"}}
    enabled=family.get("enabled_operators",[]) if family else []
    return {"publication_id":pack["publication_id"],"proposition_id":snap["selected_proposition_id"],"claim":claim,
            "eligible_conclusions":[{"conclusion_id":c["conclusion_id"],"statement":c["statement"],"allowed_relations":c["allowed_relations"],
              "anchor_ids":c["anchor_ids"],"limitations":c["limitations"]} for c in conclusions],
            "anchors":anchors,"allowed_operator_ids":enabled,
            "instructions":"Compare every included conclusion. Do not omit limiting or conflicting evidence. Return only the requested schema; an alignment does not authorize an action."}


def _enforce_live_alignment(result: dict, snapshot: dict, alignment: dict | None, pack: dict) -> dict:
    """Model proposals must agree with deterministic, published warrants or abstain."""
    try:
        if alignment is None:
            raise DomainError("alignment_required")
        candidate=admit_alignment(snapshot,alignment,pack)
        expected_ids={c["conclusion_id"] for c in result["evidence"]}
        proposed_ids={a["conclusion_id"] for a in candidate["alignments"]}
        if expected_ids!=proposed_ids:
            raise DomainError("required_alignment_omitted")
        if any(a["relation_candidate"]!=result["evidence_status"] for a in candidate["alignments"]):
            raise DomainError("alignment_warrant_mismatch")
        expected_ops={o["operator_id"]:o for o in result["operator_findings"] if o["operator_state"]=="established"}
        proposed_ops={o["operator_id"]:o for a in candidate["alignments"] for o in a["operator_candidates"]}
        semantic_ops=set(expected_ops)-{"L09"}
        if not semantic_ops.issubset(proposed_ops) or set(proposed_ops)-set(expected_ops):
            raise DomainError("operator_warrant_mismatch")
        for opid,op in proposed_ops.items():
            expected=expected_ops[opid]
            if op["reason_code"]!=expected["reason_code"] or not set(op["claim_paths"]).issubset(expected["claim_field_paths"]):
                raise DomainError("operator_warrant_mismatch")
        result["admitted_alignment"]={"conclusion_ids":sorted(proposed_ids),"operator_ids":sorted(proposed_ops)}
        return result
    except DomainError as exc:
        result.update(case_state="cannot_assess",evidence_status="not_assessable",system_status="model_error",save_eligible=False,
                      summary="The model alignment did not pass the evidence admission checks. No scientific conclusion is issued.",
                      supported_conclusion_ids=[],not_established_conclusion_ids=[],operator_findings=[],evidence=[],effect_direction="undetermined",effect_direction_by_outcome=[])
        result["argument_graph"]={"nodes":[],"edges":[]}
        result["reason_codes"].append(exc.code)
        result["policy_rule_ids"].append("G10")
        return result


def _base_result(snapshot: dict, intent: dict, mode: str, safety: dict) -> dict:
    return {"schema_version":"EvidenceReceipt/1.0","receipt_id":_id(),"receipt_version_id":_id(),"assessment_id":_id(),
        "supersedes_receipt_version_id":None,"assessed_at":_now(),"claim_version_id":snapshot["version_id"],
        "selected_proposition_id":snapshot["selected_proposition_id"],"confirmed_claim":snapshot,
        "intent_version_id":intent["version_id"],"confirmed_intent":intent,
        "case_state":"cannot_assess","route":safety["route"],"coverage":"no_matching_approved_evidence",
        "evidence_status":"not_assessable","effect_direction":"undetermined","effect_direction_by_outcome":[],
        "applicability":"unknown","personal_suitability":"not_individually_assessed","system_status":"ok",
        "reason_codes":list(safety["reason_codes"]),"policy_rule_ids":list(safety["policy_rule_ids"]),
        "supported_conclusion_ids":[],"not_established_conclusion_ids":[],"limitations":[],
        "operator_findings":[],"argument_graph":{"nodes":[],"edges":[]},"evidence":[],"dependencies":[],
        "synthetic_label":LABEL,"clinical_review":False,"mode":mode,
        "summary":"This bounded fictional library has no matching evidence for the confirmed proposition. This does not establish that evidence is absent elsewhere.",
        "action_boundary":"This demonstration explains fictional evidence and does not establish personal suitability.",
        "next_step":{"template_id":"educator-question-v1","kind":"question","text":"What does this evidence establish, and what additional evidence would justify the proposed action?"},
        "save_eligible":True,"reproduction":{"compiler_version":VERSION,"policy_version":POLICY_VERSION,"schema_version":"1.0",
            "template_version":"synthetic-templates-1.0","claim_hash":_hash(snapshot["confirmed_proposition"]),"intent_hash":_hash(intent)},
        "current_trust":{"checked_at":_now(),"state":"current","affected_dependency_ids":[],"notice_id":None}}


def _reviewed_predicate_matches(predicate: dict, proposition: dict, intent: dict) -> bool:
    path=predicate["field_path"]
    raw=_value(intent if path.startswith("intent.") else proposition,path.split(".")[-1])
    if isinstance(raw,dict):
        raw=raw.get("surface")
    if not isinstance(raw,str):
        return False
    value=unicodedata.normalize("NFC",raw).strip().casefold()
    return value in {unicodedata.normalize("NFC",v).strip().casefold() for v in predicate["allowed_values"]}


def _assess_clinical(snapshot: dict, intent: dict, pack: dict, result: dict, family: dict, alignment: dict | None, mode: str) -> dict:
    """Only human-authored scoped mappings and prose can reach a clinical receipt."""
    p=snapshot["confirmed_proposition"]
    conclusions=[c for c in pack["conclusions"] if c["conclusion_id"] in family["conclusion_ids"]]
    matches={}
    findings=[]
    for conclusion in conclusions:
        admitted=[a["relation"] for a in conclusion["admissions"] if all(_reviewed_predicate_matches(predicate,p,intent) for predicate in a["predicates"])]
        if len(set(admitted))==1:
            matches[conclusion["conclusion_id"]]=admitted[0]
        elif len(set(admitted))>1:
            result["reason_codes"].append("ambiguous_reviewed_mapping")
        for mapping in conclusion["operator_mappings"]:
            applicable=p["speech_act"]!="question" and all(_reviewed_predicate_matches(pred,p,intent) for pred in mapping["predicates"])
            complete=all(_value(intent if pred["field_path"].startswith("intent.") else p,pred["field_path"].split(".")[-1]) is not None for pred in mapping["predicates"])
            state="not_applicable" if p["speech_act"]=="question" else "established" if applicable else "not_detected" if complete else "unknown"
            findings.append({"operator_id":mapping["operator_id"],"operator_version":"reviewed-1.0","operator_state":state,
                "claim_field_paths":[pred["field_path"] for pred in mapping["predicates"]],"evidence_conclusion_ids":[conclusion["conclusion_id"]],
                "anchor_ids":mapping["anchor_ids"],"graph_edge_id":"edge-action" if mapping["operator_id"]=="L09" else "edge-evidence",
                "reason_code":mapping["reason_code"] if applicable else "required_field_unknown" if not complete else "no_defined_mismatch_detected",
                "explanation":mapping["explanation"] if applicable else None})
    conflict=any(set(group["conclusion_ids"]).issubset(matches) for group in family["conflicts"])
    statuses=set(matches.values())
    status="conflicting" if conflict else next(iter(statuses)) if len(statuses)==1 and len(matches)==len(conclusions) else "insufficient"
    result.update(case_state="assessed",coverage="matched",evidence_status=status,applicability="scenario_aligned" if matches else "unknown",
        synthetic_label=None,clinical_review=True,operator_findings=findings,
        summary={"supports_within_scope":"The reviewed evidence supports the confirmed proposition within its reviewed scope.",
                 "contradicts_within_scope":"The reviewed evidence contradicts the confirmed proposition within its reviewed scope.",
                 "insufficient":"The reviewed mappings do not establish the complete confirmed proposition. This is not evidence of no effect.",
                 "conflicting":"The included reviewed findings disagree within the same reviewed scope."}[status],
        action_boundary="Evidence about an outcome does not establish personal suitability or authorize starting, stopping, replacing, continuing or changing treatment.",
        next_step={"template_id":"reviewed-professional-question-v1","kind":"professional_question","text":family["professional_question"]})
    effects={c["effect_direction"] for c in conclusions}
    result["effect_direction"]=next(iter(effects)) if len(effects)==1 else "mixed"
    for outcome_id in sorted({c["outcome_id"] for c in conclusions}):
        subset=[c for c in conclusions if c["outcome_id"]==outcome_id]
        directions={c["effect_direction"] for c in subset}
        result["effect_direction_by_outcome"].append({"outcome_id":outcome_id,"effect_direction":next(iter(directions)) if len(directions)==1 else "mixed","conclusion_ids":[c["conclusion_id"] for c in subset]})
    for conclusion in conclusions:
        for source in pack["sources"]:
            anchors=[a for a in source["anchors"] if a["anchor_id"] in conclusion["anchor_ids"]]
            if not anchors:
                continue
            review=next(r for r in pack["review_records"] if r["review_id"]==conclusion["review_id"])
            result["evidence"].append({**deepcopy(conclusion),"source_id":source["source_id"],"source_version_id":source["source_version_id"],
                "title":source["title"],"publisher":source["publisher"],"source_date":source["source_date"],"canonical_url":source["canonical_url"],
                "source_hash":source["content_hash"],"synthetic":False,"origin_group_ids":source["origin_group_ids"],"anchors":deepcopy(anchors),
                "quality_appraisal":family["quality_appraisal_label"],"quality_appraisal_method":family["quality_appraisal_method"],
                "review_label":"Evidence and scoped mappings reviewed; this individual response is not independently reviewed.","review_record":review})
        result["limitations"].extend(conclusion["limitations"])
    result["limitations"]=list(dict.fromkeys(result["limitations"]+[family["scope_note"],"Personal suitability is not assessed."]))
    result["supported_conclusion_ids"]=[cid for cid,relation in matches.items() if relation=="supports_within_scope"]
    result["not_established_conclusion_ids"]=[c["conclusion_id"] for c in conclusions if matches.get(c["conclusion_id"]) in {None,"insufficient"}]
    result["argument_graph"]={"nodes":[{"id":"measured-effect","type":"measured_effect","label":_concept(p,"measured_outcome").get("surface","Reviewed outcome")},
        {"id":"scenario","type":"scenario","label":_concept(p,"population").get("surface","Confirmed scope")},
        {"id":"intended-action","type":"intended_action","label":_value(intent,"action_kind")}],
        "edges":[{"edge_id":"edge-evidence","from":"measured-effect","to":"scenario","warrant_ids":sorted(matches),"state":"bounded" if matches else "unwarranted"},
                 {"edge_id":"edge-action","from":"scenario","to":"intended-action","warrant_ids":[],"state":"not_individually_assessed"}]}
    return _enforce_live_alignment(result,snapshot,alignment,pack) if mode=="live" else result


def _assess_with_library(snapshot: dict, intent: dict, pack: dict | None = None, mode: str = "replay", alignment: dict | None = None) -> dict:
    try:
        snapshot = ConfirmedClaimSnapshot.model_validate(snapshot).model_dump(mode="json")
        intent = IntentIR.model_validate(intent).model_dump(mode="json")
    except ValidationError as exc:
        raise DomainError("confirmation_required") from exc
    if not intent["confirmed_at"] or intent["claim_version_id"] != snapshot["version_id"] or intent["confirmation_event_id"] != snapshot["confirmation_event_id"]:
        raise DomainError("stale_confirmation")
    safety = screen_safety("", intent, snapshot)
    result = _base_result(snapshot,intent,mode,safety)
    from .review import is_verified_clinical_pack
    clinical_pack=is_verified_clinical_pack(pack)
    if clinical_pack:
        # This flag records the queried publication, never approval of this user
        # proposition or independent clinical review of an individual response.
        result.update(synthetic=False,synthetic_label=None,clinical_review=True,review_scope="library_publication_only",
            summary="The reviewed library has no matching evidence mapping for this confirmed proposition. No efficacy conclusion is issued; this does not establish that evidence is absent elsewhere.",
            action_boundary="This system does not assess personal suitability or authorize starting, stopping, replacing, continuing or changing treatment.",
            next_step={"template_id":"professional-evidence-question-v1","kind":"professional_question",
                "text":"What evidence applies to this claim, and what remains uncertain to discuss with a qualified healthcare professional?"})
        result["reproduction"]["publication_id"]=pack["publication_id"]
    excluded_health_scope=bool({"pregnancy_scope","pediatric_scope","current_serious_concern"}&set(safety["safety_flags"]))
    if safety["health_context"] and (not clinical_pack or excluded_health_scope):
        summary="This scenario is outside the reviewed adult type 2 diabetes scope. No scientific assessment is issued." if clinical_pack else "No clinically reviewed library is installed. Health claims cannot be assessed by this nonclinical demonstration."
        result.update(save_eligible=False, summary=summary)
        result["limitations"] = ["Health routing is an internal engineering sentinel, not a clinically validated triage service."]
        if safety["route"]=="urgent_escalation":
            result["action_boundary"] = "If this describes a current serious concern, seek urgent professional help using local emergency services where appropriate. This system cannot assess severity."
            result["next_step"] = None
        elif safety["route"]=="professional_review_recommended":
            result["action_boundary"] = "This system cannot advise a treatment change. Discuss the proposed change or concern with a qualified healthcare professional."
            result["next_step"] = None
        return result
    p = snapshot["confirmed_proposition"]
    if any(p[name]["state"] != "stated" for name in REQUIRED_FIELDS) or not _value(intent,"action_kind"):
        result.update(route=_route(result["route"],"clarify"),summary="The claim is missing details needed for an evidence comparison.",save_eligible=False,next_step=None)
        result["reason_codes"].append("confirmation_incomplete")
        return result
    try:
        pack = pack or load_pack()
        validate_pack(pack)
    except DomainError as exc:
        result.update(coverage="blocked",system_status="evidence_integrity_error",save_eligible=False,
                      summary="The evidence record failed integrity checks. No scientific conclusion is issued.")
        result["reason_codes"].append(exc.code)
        result["current_trust"]["state"] = "integrity_error"
        return result
    result["reproduction"]["publication_id"] = pack["publication_id"]
    family = _match_family(p,pack)
    if family is None:
        result["reason_codes"].append("no_matching_library_family")
        return result
    result["dependencies"] = _dependencies(family,pack)
    result["reproduction"]["dependency_set_hash"] = _hash(sorted(result["dependencies"],key=lambda x:x["id"]))
    trust = current_trust(result["dependencies"],pack)
    result["current_trust"] = trust
    if trust["state"] != "current":
        result.update(coverage="blocked",system_status="evidence_under_review" if trust["state"] in {"under_review","superseded"} else "evidence_integrity_error",save_eligible=False,
                      summary="A required evidence record is unavailable for current use. This is an operational boundary, not a finding that the claim is false.")
        result["reason_codes"].append("evidence_"+trust["state"])
        result["policy_rule_ids"].append("G09")
        return result
    if clinical_pack:
        return _assess_clinical(snapshot,intent,pack,result,family,alignment,mode)
    conclusions = [c for c in pack["conclusions"] if c["conclusion_id"] in family["conclusion_ids"]]
    operators = _operators(p,intent,family,conclusions)
    result["operator_findings"] = operators
    leaps = [op for op in operators if op["operator_state"]=="established"]
    scientific_leaps = [op for op in leaps if op["operator_id"] != "L09"]
    population_matches = _concept(p,"population").get("concept_id") == family["population_id"]
    outcome_matches = _concept(p,"measured_outcome").get("concept_id") == family["outcome_id"]
    comparator = _concept(p,"comparator")
    comparator_matches = not comparator or comparator.get("concept_id") == family["comparator_id"]
    timeframe = _value(p,"timeframe")
    expected_days = 7 if family["family_id"]=="F01" else 1
    timeframe_matches = not timeframe or (timeframe.get("unit") in {"day", "days"} and timeframe.get("value")==expected_days)
    scope_matches = population_matches and outcome_matches and comparator_matches and timeframe_matches and _value(p,"generalization") != "universal"
    result["applicability"] = "scenario_aligned" if scope_matches else "scope_mismatch"
    result.update(case_state="assessed",coverage="matched")
    warrant = family["warrant_mode"]
    if scientific_leaps or not scope_matches:
        status = "insufficient"
    elif warrant=="conflicting":
        status = "conflicting"
    elif warrant=="insufficient":
        status = "insufficient"
    elif warrant=="no_effect":
        status = "supports_within_scope" if _value(p,"polarity")=="negated" else "contradicts_within_scope"
    elif _value(p,"polarity")=="negated":
        status = "contradicts_within_scope" if "contradicts_within_scope" in conclusions[0]["allowed_relations"] else "insufficient"
    else:
        status = "supports_within_scope"
    result["evidence_status"] = status
    effects = {c["effect_direction"] for c in conclusions}
    result["effect_direction"] = next(iter(effects)) if len(effects)==1 else "mixed"
    result["effect_direction_by_outcome"] = [{"outcome_id":family["outcome_id"],"effect_direction":result["effect_direction"],"conclusion_ids":[c["conclusion_id"] for c in conclusions]}]
    for c in conclusions:
        source = next(s for s in pack["sources"] if s["source_version_id"]==c["source_version_id"])
        result["evidence"].append({**deepcopy(c),"source_id":source["source_id"],"title":source["title"],"publisher":source["publisher"],
            "source_date":source["source_date"],"canonical_url":None,"source_hash":source["content_hash"],"synthetic":True,
            "origin_group_ids":source["origin_group_ids"],"anchors":[deepcopy(a) for a in source["anchors"] if a["anchor_id"] in c["anchor_ids"]],
            "quality_appraisal":"Not applicable: fictional software fixture","review_label":"Synthetic author check only; no clinical review"})
        result["limitations"].extend(c["limitations"])
    result["limitations"] = list(dict.fromkeys(result["limitations"] + ["Personal suitability is not assessed."]))
    result["supported_conclusion_ids"] = [c["conclusion_id"] for c in conclusions] if status=="supports_within_scope" else []
    result["not_established_conclusion_ids"] = [c["conclusion_id"] for c in conclusions] if status=="insufficient" else []
    summaries = {
        "supports_within_scope":"The fictional evidence supports this confirmed proposition within the stated scope.",
        "contradicts_within_scope":"The fictional evidence contradicts this confirmed proposition within the stated scope.",
        "insufficient":"The fictional evidence does not establish this complete proposition. Missing support is not a finding of no effect.",
        "conflicting":"Relevant fictional findings disagree within the same defined scope. Both findings remain visible.",
    }
    result["summary"] = summaries[status]
    if any(op["operator_id"]=="L09" for op in leaps):
        result["action_boundary"] = "Support for quizzes alongside lessons does not establish that quizzes can replace lessons."
        result["next_step"]["text"] = "What evidence would show whether replacing lessons is justified, rather than adding quizzes alongside them?"
    result["reason_codes"].extend(op["reason_code"] for op in leaps)
    result["argument_graph"] = {"nodes":[{"id":"measured-effect","type":"measured_effect","label":_concept(p,"measured_outcome").get("surface","Measured outcome")},
        {"id":"scenario","type":"scenario","label":_concept(p,"population").get("surface","Scenario")},
        {"id":"intended-action","type":"intended_action","label":_value(intent,"action_kind")}],
        "edges":[{"edge_id":"edge-evidence","from":"measured-effect","to":"scenario","warrant_ids":[c["conclusion_id"] for c in conclusions],
                  "operator_findings":[op["operator_id"] for op in scientific_leaps],"state":"bounded" if not scientific_leaps else "unwarranted"},
                 {"edge_id":"edge-action","from":"scenario","to":"intended-action","warrant_ids":[],
                  "operator_findings":[op["operator_id"] for op in leaps if op["operator_id"]=="L09"],"state":"not_individually_assessed"}]}
    # A final dependency check is repeated by the caller within its save transaction.
    return _enforce_live_alignment(result,snapshot,alignment,pack) if mode=="live" else result


def assess(snapshot: dict, intent: dict, pack: dict | None = None, mode: str = "replay", alignment: dict | None = None) -> dict:
    """The domain boundary cannot be bypassed by selecting another runtime mode."""
    qualified = has_authored_comparison(snapshot)
    result = _assess_with_library(snapshot, intent, pack,
                                 mode=mode if qualified else "manual",
                                 alignment=alignment if qualified else None)
    result["mode"] = mode
    if not qualified:
        return context_only_comparison(result, snapshot, intent)
    result["comparison_basis"] = "authored_replay"
    return result
