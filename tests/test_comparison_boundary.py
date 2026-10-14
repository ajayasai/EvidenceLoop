"""Missing directional semantics must never become a claim-support judgment."""
from copy import deepcopy

import pytest

from services.api.app import domain


def replay(edits=None):
    fixture=domain.fixture_catalog()[0]
    draft=domain.interpret(fixture["text"],fixture["intent"])
    return domain.confirm(draft["claim"],draft["intent"],edits=edits)


def assert_context_only(result):
    assert result["evidence_status"]=="not_assessable"
    assert result["effect_direction"]=="undetermined"
    assert result["effect_direction_by_outcome"]==[]
    assert result["supported_conclusion_ids"]==result["not_established_conclusion_ids"]==[]
    assert result["operator_findings"]==[] and result["argument_graph"]=={"nodes":[],"edges":[]}
    assert result["save_eligible"] is False and result["next_step"] is None
    assert result["comparison_basis"]=="context_only"
    assert "exact_claim_comparison_unqualified" in result["reason_codes"]


@pytest.mark.parametrize("effect",["increases","decreases","does not increase","does not decrease"])
@pytest.mark.parametrize("runtime_mode",["replay","manual","live"])
def test_direct_domain_mode_cannot_qualify_a_manual_signed_claim(effect,runtime_mode):
    text=f"In the fictional Fern Lab, glow water {effect} fern height compared with plain water."
    draft=domain.interpret(text,{"action_kind":"learn"},mode="manual")
    confirmed=domain.confirm(draft["claim"],draft["intent"],edits={
        "population":"fictional Fern Lab","intervention":"glow water","measured_outcome":"fern height",
        "comparator":"plain water","relation":"causal","polarity":"negated" if effect.startswith("does not") else "affirmed"})
    candidate={"alignments":[{"proposition_id":confirmed["snapshot"]["selected_proposition_id"],
        "conclusion_id":"C-FERN-1","relation_candidate":"supports_within_scope","field_matches":[],"operator_candidates":[]}]}
    result=domain.assess(confirmed["snapshot"],confirmed["intent"],mode=runtime_mode,alignment=candidate)
    assert_context_only(result)
    assert result["system_status"]=="ok" and result["coverage"]=="matched"
    assert result["evidence"] and result["dependencies"]
    with pytest.raises(domain.DomainError,match="exact claim comparison unqualified"):
        domain.admit_alignment(confirmed["snapshot"],candidate)


@pytest.mark.parametrize("edits",[
    {"polarity":"negated"},{"relation":"associative"},{"speech_act":"question"},
    {"measured_outcome":"next-day recall"},{"intervention":"moon cards"},
    {"comparator":"unreviewed comparator"},{"timeframe":{"value":365,"unit":"days"}},
    {"population":"different fictional group"},{"certainty":"guaranteed"},
])
def test_editing_authored_replay_does_not_reuse_its_missing_predicate(edits):
    confirmed=replay(edits)
    assert not domain.has_authored_comparison(confirmed["snapshot"])
    assert_context_only(domain.assess(confirmed["snapshot"],confirmed["intent"]))


@pytest.mark.parametrize("mutation",["missing","foreign","mixed","manual_mode"])
def test_authored_signature_alone_cannot_replace_original_input_provenance(mutation):
    confirmed=replay()
    snapshot=deepcopy(confirmed["snapshot"])
    if mutation=="missing":
        for ref in snapshot["provenance_refs"]:
            ref["input_hash"]=None
    elif mutation=="foreign":
        for ref in snapshot["provenance_refs"]:
            ref["input_hash"]="0"*64
    elif mutation=="mixed":
        snapshot["provenance_refs"][0]["input_hash"]="0"*64
    else:
        snapshot["mode"]="manual"
    assert not domain.has_authored_comparison(snapshot)
    assert_context_only(domain.assess(snapshot,confirmed["intent"]))


def test_identical_user_reconfirmation_preserves_authored_frame_and_discarded_raw_text():
    confirmed=replay({"population":"fictional Fern Lab"})
    assert domain.has_authored_comparison(confirmed["snapshot"])
    result=domain.assess(confirmed["snapshot"],confirmed["intent"])
    assert result["comparison_basis"]=="authored_replay"
    assert result["evidence_status"]=="supports_within_scope"
    assert result["save_eligible"] is True
    assert "original_text" not in confirmed["snapshot"]
    assert all("quote" not in ref for ref in confirmed["snapshot"]["provenance_refs"])
