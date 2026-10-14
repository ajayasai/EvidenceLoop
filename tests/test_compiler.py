import asyncio
from types import SimpleNamespace

import pytest

from services.api.app import domain
from services.api.app.compiler import ClaimCompiler
from services.api.app.gemini import OFFICIAL_BASE
from services.api.app.provider import AttemptBudget, ProviderError
from services.api.app.slot_extraction import SLOT_FIELDS


class ScriptedProvider:
    def __init__(self, outputs):
        self.outputs = outputs
        self.seen = []
        self.config = SimpleNamespace(require_enabled=lambda: None)

    async def call(self, kind, data, schema, ledger, validator=None):
        self.seen.append(kind)
        ledger.reserve(kind, 100, 100)
        payload = self.outputs[kind]
        if isinstance(payload, Exception):
            raise payload
        if validator:
            validator(payload)
        return SimpleNamespace(payload=payload,model_revision="test-scripted-no-live-model",prompt_version="test-1")


def extraction_for_first_fixture():
    fixture = domain.fixture_catalog()[0]
    replay = domain.interpret(fixture["text"],fixture["intent"])
    p = replay["claim"]["propositions"][0]
    fields = []
    for name,field in p.items():
        if not isinstance(field,dict) or field.get("state") != "stated":
            continue
        value = field["value"]
        value = value.get("surface") if isinstance(value,dict) else value
        if not isinstance(value,str) or name in {"timeframe","magnitude","negation_scope"}:
            continue
        fields.append({"name":name,"value":value,"quote":field["provenance"][0]["quote"]})
    return fixture,{"propositions":[{"proposition_id":"p1","speaker":"user","speech_act":"assertion","fields":fields}],"unresolved_fields":[]}


def test_alignment_flag_cannot_qualify_a_live_claim_without_a_signed_predicate():
    fixture, extraction = extraction_for_first_fixture()
    provider = ScriptedProvider({"extraction":extraction})
    compiler, ledger = ClaimCompiler(provider, alignment_enabled=True), AttemptBudget()
    captured = asyncio.run(compiler.extract(fixture["text"],fixture["intent"],ledger))
    assert captured["mode"] == "live"
    confirmed = domain.confirm(captured["claim"],captured["intent"],"p1")
    pack = domain.load_pack()
    context = domain.alignment_context(confirmed["snapshot"],pack)
    provider.outputs["alignment"] = {"schema_version":"1.0","alignments":[{
        "proposition_id":"p1","conclusion_id":c["conclusion_id"],"relation_candidate":"supports_within_scope","field_matches":[],"operator_candidates":[]
    } for c in context["eligible_conclusions"]]}
    result = asyncio.run(compiler.assess(confirmed["snapshot"],confirmed["intent"],pack,ledger))
    assert provider.seen == ["extraction"]
    assert result["system_status"] == "ok"
    assert result["evidence_status"] == "not_assessable"
    assert result["comparison_basis"] == "context_only"
    assert result["save_eligible"] is False and result["next_step"] is None
    assert result["model_metadata"]["input_tokens"] == 100
    assert compiler.alignment_available is False


def test_invalid_extraction_becomes_explicit_manual_fallback():
    fixture, extraction = extraction_for_first_fixture()
    extraction["propositions"][0]["fields"][0]["quote"] = "invented phrase not in the input"
    compiler = ClaimCompiler(ScriptedProvider({"extraction":extraction}))
    result = asyncio.run(compiler.extract(fixture["text"],fixture["intent"],AttemptBudget()))
    assert result["mode"] == "manual"
    assert result["system_status"] == "model_error"
    assert result["claim"]["propositions"][0]["intervention"]["value"] is None


def test_alignment_failure_does_not_become_a_scientific_verdict():
    fixture = domain.fixture_catalog()[0]
    capture = domain.interpret(fixture["text"],fixture["intent"])
    confirmed = domain.confirm(capture["claim"],capture["intent"])
    provider = ScriptedProvider({"alignment":ProviderError("provider_timeout")})
    result = asyncio.run(ClaimCompiler(provider, alignment_enabled=True).assess(confirmed["snapshot"],confirmed["intent"],domain.load_pack(),AttemptBudget()))
    assert result["system_status"] == "model_error"
    assert result["evidence_status"] == "not_assessable"
    assert result["evidence"] == []
    assert result["operator_findings"] == []
    assert not result["save_eligible"]


def test_urgent_concern_never_calls_the_model():
    provider = ScriptedProvider({})
    result = asyncio.run(ClaimCompiler(provider).extract("I have chest pain and cannot breathe right now.",{"action_kind":"learn"},AttemptBudget()))
    assert result["route"] == "urgent_escalation"
    assert provider.seen == []


@pytest.mark.parametrize("effect,polarity", [
    ("increases", "affirmed"), ("decreases", "affirmed"),
    ("does not increase", "negated"), ("does not decrease", "negated"),
])
@pytest.mark.parametrize("alignment_enabled", [False, True])
def test_extraction_only_never_warrants_opposite_directional_claims(effect, polarity, alignment_enabled):
    fixture, compact = extraction_for_first_fixture()
    literals = {field["name"]: field["value"] for field in compact["propositions"][0]["fields"]}
    text = (f'For {literals["population"]}, {literals["intervention"]} '
            f'{effect} {literals["measured_outcome"]} compared with {literals["comparator"]}.')
    quote = lambda value: {"quote": value, "occurrence": None}
    proposition = {**dict.fromkeys(SLOT_FIELDS), "speaker": "user", "speech_act": "assertion"}
    for name in ("population", "intervention", "measured_outcome", "comparator"):
        proposition[name] = quote(literals[name])
    for name, value in (("relation", "causal"), ("polarity", polarity), ("certainty", "asserted")):
        proposition[name] = {**quote(text), "value": value}
    provider = ScriptedProvider({"extraction": {"propositions": [proposition]}})
    provider.config.base_url = OFFICIAL_BASE
    compiler, ledger = ClaimCompiler(provider, alignment_enabled=alignment_enabled), AttemptBudget()
    captured = asyncio.run(compiler.extract(text, fixture["intent"], ledger))
    assert captured["mode"] == "live"
    confirmed = domain.confirm(captured["claim"], captured["intent"], "p1")
    pack = domain.load_pack()
    # Direct domain access cannot bypass the same missing-predicate boundary.
    baseline = domain.assess(confirmed["snapshot"], confirmed["intent"], pack, mode="manual")
    assert baseline["evidence_status"] == "not_assessable"
    result = asyncio.run(compiler.assess(confirmed["snapshot"], confirmed["intent"], pack, ledger))
    assert result["case_state"] == "cannot_assess"
    assert result["evidence_status"] == "not_assessable" and result["system_status"] == "ok"
    assert result["coverage"] == "matched" and result["applicability"] == "unknown"
    assert result["evidence"] == baseline["evidence"] and result["evidence"]
    assert result["dependencies"] == baseline["dependencies"]
    assert result["supported_conclusion_ids"] == result["not_established_conclusion_ids"] == []
    assert result["operator_findings"] == []
    assert result["argument_graph"] == {"nodes": [], "edges": []}
    assert result["effect_direction"] == "undetermined" and result["effect_direction_by_outcome"] == []
    assert result["save_eligible"] is False and result["next_step"] is None
    assert "exact_claim_comparison_unqualified" in result["reason_codes"]
    assert "cannot establish whether the evidence supports the exact effect" in result["summary"]
    assert result["alignment_mode"] == "extraction_only" and provider.seen == ["extraction"]


@pytest.mark.parametrize("boundary", ["unknown", "unmatched", "health", "urgent", "integrity", "withdrawn"])
def test_extraction_only_preserves_existing_boundary_failures(boundary):
    fixture = domain.fixture_catalog()[0]
    intent = fixture["intent"]
    if boundary == "health":
        intent = {"action_kind": "stop", "target": "prescribed medication", "actor": "self"}
    captured = domain.interpret(fixture["text"], intent)
    if boundary == "urgent":
        captured["claim"]["safety_flags"].extend(["current_serious_concern", "health_context"])
    edits = {"population": None} if boundary == "unknown" else (
        {"intervention": "unlisted fictional material"} if boundary == "unmatched" else None)
    confirmed = domain.confirm(captured["claim"], captured["intent"], edits=edits)
    pack = domain.load_pack()
    if boundary == "integrity":
        pack["sources"][0]["content_hash"] = "0" * 64
    elif boundary == "withdrawn":
        pack["trust_states"] = {source["source_id"]: {"state": "withdrawn", "revision": 2}
                                for source in pack["sources"]}
    baseline = domain.assess(confirmed["snapshot"], confirmed["intent"], pack, mode="manual")
    assert baseline["case_state"] == "cannot_assess"
    if boundary in {"health", "urgent"}:
        assert baseline["route"] == ("urgent_escalation" if boundary == "urgent"
                                      else "professional_review_recommended")
    provider = ScriptedProvider({})
    result = asyncio.run(ClaimCompiler(provider, alignment_enabled=False).assess(
        confirmed["snapshot"], confirmed["intent"], pack, AttemptBudget()))
    for key in ("case_state", "system_status", "evidence_status", "route", "coverage", "summary", "action_boundary"):
        assert result[key] == baseline[key]
    assert result["current_trust"]["state"] == baseline["current_trust"]["state"]
    assert set(baseline["reason_codes"]).issubset(result["reason_codes"])
    assert result["save_eligible"] is False and result["next_step"] is None
    assert provider.seen == []


def test_extraction_only_removes_operator_warrants_and_their_reason_codes():
    fixture = next(row for row in domain.fixture_catalog() if row["id"] == "quiz-replacement")
    captured = domain.interpret(fixture["text"], fixture["intent"])
    confirmed = domain.confirm(captured["claim"], captured["intent"])
    pack = domain.load_pack()
    baseline = domain.assess(confirmed["snapshot"], confirmed["intent"], pack, mode="manual")
    assert "adjunct_does_not_authorize_replacement" in baseline["reason_codes"]
    result = asyncio.run(ClaimCompiler(ScriptedProvider({}), alignment_enabled=False).assess(
        confirmed["snapshot"], confirmed["intent"], pack, AttemptBudget()))
    assert result["operator_findings"] == [] and result["argument_graph"]["edges"] == []
    assert "adjunct_does_not_authorize_replacement" not in result["reason_codes"]
    assert result["evidence"] == baseline["evidence"]
    assert "does not establish the claimed effect" in result["action_boundary"]
