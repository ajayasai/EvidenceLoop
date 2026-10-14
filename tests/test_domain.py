"""Engineering invariants for synthetic cases; these are not clinical validation."""
from copy import deepcopy
import hashlib
import json
import unittest

from pydantic import ValidationError

from app.contracts import ConfirmedClaimSnapshot, SemanticField
from app.domain import (
    DomainError, admit_alignment, assess, confirm, current_trust, expand_compact_claim, fixture_catalog,
    internal_safety_fixtures, interpret, load_pack, screen_safety,
    validate_live_claim, validate_pack,
)


def fixture(id="fern-supported"):
    return next(f for f in fixture_catalog() if f["id"] == id)


def compiled(id="fern-supported", edits=None, intent=None):
    f = fixture(id)
    interpreted = interpret(f["text"], intent or f["intent"])
    confirmed = confirm(interpreted["claim"], interpreted["intent"], edits=edits)
    return interpreted, confirmed, assess(confirmed["snapshot"], confirmed["intent"])


class FieldContractTests(unittest.TestCase):
    def test_unknown_is_null_and_does_not_default_to_stated(self):
        self.assertIsNone(SemanticField[str]().value)
        with self.assertRaises(ValidationError):
            SemanticField[str](state="unknown", value="guessed")

    def test_stated_needs_value_and_provenance(self):
        for kwargs in ({"state":"stated"},{"state":"stated","value":""},{"state":"stated","value":"x"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                SemanticField[str](**kwargs)

    def test_unknown_keys_fail(self):
        with self.assertRaises(ValidationError):
            SemanticField[str](confidence=0.99)

    def test_not_applicable_needs_rule(self):
        with self.assertRaises(ValidationError):
            SemanticField[str](state="not_applicable")


class ExtractionTests(unittest.TestCase):
    def test_explicitly_confirmed_unknown_population_remains_unknown_and_blocks_assessment(self):
        captured=interpret("Saffron tabs increased maze completion speed.",{"action_kind":"learn"},mode="manual")
        confirmed=confirm(captured["claim"],captured["intent"],edits={"intervention":"Saffron tabs",
            "measured_outcome":"maze completion speed","polarity":"affirmed","relation":"causal"})
        population=confirmed["snapshot"]["confirmed_proposition"]["population"]
        self.assertEqual(population["state"],"unknown")
        self.assertIsNone(population["value"])
        self.assertEqual(confirmed["route"],"clarify")
        self.assertEqual(confirmed["case_state"],"needs_confirmation")
        self.assertIn("confirmation_incomplete",confirmed["reason_codes"])
        result=assess(confirmed["snapshot"],confirmed["intent"])
        self.assertEqual(result["evidence_status"],"not_assessable")
        self.assertEqual(result["route"],"clarify")
        self.assertEqual(result["evidence"],[])
        self.assertFalse(result["save_eligible"])
        self.assertIsNone(result["next_step"])

    def test_all_unknown_claim_fields_can_be_explicitly_confirmed_without_invention(self):
        captured=interpret("It made things better for them.",{"action_kind":"learn"},mode="manual")
        confirmed=confirm(captured["claim"],captured["intent"])
        for name in ("population","intervention","measured_outcome","relation","polarity"):
            with self.subTest(field=name):
                field=confirmed["snapshot"]["confirmed_proposition"][name]
                self.assertEqual(field["state"],"unknown")
                self.assertIsNone(field["value"])
                self.assertEqual(field["provenance"],[])
        self.assertEqual(confirmed["route"],"clarify")
        self.assertTrue(confirmed["snapshot"]["confirmation_event_id"])
        self.assertTrue(confirmed["intent"]["confirmed_at"])
        result=assess(confirmed["snapshot"],confirmed["intent"])
        self.assertEqual(result["summary"],"The claim is missing details needed for an evidence comparison.")
        self.assertEqual(result["evidence_status"],"not_assessable")
        self.assertEqual(result["evidence"],[])
        self.assertEqual(result["supported_conclusion_ids"],[])
        self.assertFalse(result["save_eligible"])
        self.assertIsNone(result["next_step"])

    def test_unknown_claim_confirmation_still_requires_explicit_valid_intent(self):
        for text in ("It made things better for them.","A medication claim with unclear meaning."):
            with self.subTest(text=text):
                captured=interpret(text,mode="manual")
                with self.assertRaises(DomainError) as missing:
                    confirm(captured["claim"],captured["intent"])
                self.assertEqual(missing.exception.code,"confirmation_incomplete")
                invalid=deepcopy(captured["intent"])
                invalid["action_kind"]={"state":"stated","value":"invented_action","provenance":[]}
                with self.assertRaises(DomainError):
                    confirm(captured["claim"],invalid)

    def test_compact_concept_value_must_be_grounded_in_its_own_quote(self):
        text="In a fictional club, quiet cards do not improve next-day recall."
        candidate={"propositions":[{"proposition_id":"p1","speaker":"user","speech_act":"assertion",
            "fields":[{"name":"intervention","value":"quiet cards","quote":"do not improve next-day recall"}]}]}
        with self.assertRaises(DomainError) as error:
            expand_compact_claim(text,candidate)
        self.assertEqual(error.exception.code,"extracted_surface_quote_mismatch")
        candidate["propositions"][0]["fields"][0]["quote"]="quiet cards"
        result=expand_compact_claim(text,candidate,{"action_kind":"learn"})
        frame=result["claim"]["propositions"][0]
        self.assertEqual(frame["intervention"]["value"]["surface"],"quiet cards")
        self.assertEqual(frame["polarity"]["state"],"unknown")
        self.assertEqual(frame["population"]["state"],"unknown")
        # An admitted partial extraction still cannot establish missing negation.
        confirmed=confirm(result["claim"],result["intent"])
        self.assertEqual(confirmed["route"],"clarify")
        self.assertEqual(assess(confirmed["snapshot"],confirmed["intent"])["evidence_status"],"not_assessable")

    def test_compact_surface_normalization_preserves_original_quote_span(self):
        text="🧪 Cafe\u0301 water was used in this fictional example."
        candidate={"propositions":[{"proposition_id":"p1","speaker":"user","speech_act":"assertion",
            "fields":[{"name":"intervention","value":"Café water","quote":"Cafe\u0301 water"}]}]}
        frame=expand_compact_claim(text,candidate)["claim"]["propositions"][0]
        origin=frame["intervention"]["provenance"][0]
        self.assertEqual(frame["intervention"]["value"]["surface"],"Café water")
        self.assertEqual(text[origin["start"]:origin["end"]],"Cafe\u0301 water")
        candidate["propositions"][0]["fields"][0]["value"]="café water"
        with self.assertRaises(DomainError) as error:
            expand_compact_claim(text,candidate)
        self.assertEqual(error.exception.code,"extracted_surface_quote_mismatch")

    def test_replay_exact_only(self):
        f=fixture()
        self.assertEqual(interpret(f["text"],f["intent"])["mode"],"replay")
        changed=interpret(f["text"]+" ",f["intent"])
        self.assertEqual(changed["mode"],"manual")
        self.assertEqual(changed["claim"]["propositions"][0]["intervention"]["state"],"unknown")
        self.assertIn("manual",changed["mode_description"].lower())

    def test_no_intent_or_endorsement_from_quoted_claim(self):
        result=interpret(fixture()["text"])
        self.assertEqual(result["intent"]["action_kind"]["state"],"unknown")
        self.assertEqual(result["intent"]["endorsement"]["state"],"unknown")
        self.assertEqual(result["route"],"clarify")

    def test_input_bounds_before_inference(self):
        for text in (" ","a"*6001,"\x00bad"):
            with self.subTest(text=text[:12]), self.assertRaises(DomainError):
                interpret(text)

    def test_original_unicode_codepoint_spans(self):
        f=fixture()
        old=interpret(f["text"],f["intent"])["claim"]
        prefix="🧪 Cafe\u0301\r\n"
        original=prefix+f["text"]
        propositions=deepcopy(old["propositions"])
        for p in propositions:
            for field in p.values():
                if isinstance(field,dict) and "provenance" in field:
                    for origin in field["provenance"]:
                        origin["start"]+=len(prefix)
                        origin["end"]+=len(prefix)
                        origin["input_hash"]=hashlib.sha256(original.encode()).hexdigest()
        candidate={"propositions":propositions}
        result=validate_live_claim(original,candidate,f["intent"])
        self.assertEqual(result["claim"]["original_text"],original)
        self.assertIn("Café\n",result["claim"]["normalized_text"])
        for field in result["claim"]["propositions"][0].values():
            if isinstance(field,dict) and "provenance" in field:
                for origin in field["provenance"]:
                    self.assertEqual(original[origin["start"]:origin["end"]],origin["quote"])
        candidate["propositions"][0]["intervention"]["provenance"][0]["start"]+=1
        with self.assertRaises(DomainError) as error:
            validate_live_claim(original,candidate,f["intent"])
        self.assertEqual(error.exception.code,"invalid_original_span")

    def test_invented_hash_and_user_edit_provenance_rejected_from_model(self):
        f=fixture()
        extracted=interpret(f["text"],f["intent"])["claim"]
        for bad in ({"kind":"input_span","start":0,"end":1,"quote":"I","input_hash":"0"*64},
                    {"kind":"user_confirmation","confirmation_event_id":"invented"}):
            candidate={"propositions":deepcopy(extracted["propositions"])}
            candidate["propositions"][0]["intervention"]["provenance"]=[bad]
            with self.subTest(bad=bad), self.assertRaises(DomainError):
                validate_live_claim(f["text"],candidate,f["intent"])

    def test_model_intent_cannot_replace_user_answer(self):
        f=fixture()
        p=interpret(f["text"],f["intent"])["claim"]["propositions"]
        result=validate_live_claim(f["text"],{"propositions":p,"intent_candidate":{"action_kind":"replace"}}, {"action_kind":"learn"})
        self.assertEqual(result["intent"]["action_kind"]["value"],"learn")

    def test_public_fixtures_have_no_internal_health_sentinels(self):
        self.assertTrue(internal_safety_fixtures())
        self.assertTrue(all(f["visibility"]=="public_nonclinical" for f in fixture_catalog()))
        self.assertTrue(all(not screen_safety(f["text"],f["intent"])["health_context"] for f in fixture_catalog()))


class ConfirmationTests(unittest.TestCase):
    def test_snapshot_excludes_raw_text_and_quotes(self):
        interpreted,confirmed,_=compiled()
        snapshot=confirmed["snapshot"]
        self.assertNotIn("original_text",snapshot)
        self.assertNotIn("normalization_map",snapshot)
        self.assertNotIn(interpreted["claim"]["original_text"],json.dumps(snapshot))
        for value in snapshot["confirmed_proposition"].values():
            if isinstance(value,dict) and "provenance" in value:
                self.assertTrue(all(p["kind"]=="saved_ref" and p.get("quote") is None for p in value["provenance"]))
        self.assertTrue(snapshot["provenance_refs"])

    def test_raw_fields_cannot_be_injected_into_snapshot(self):
        _,c,_=compiled()
        c["snapshot"]["original_text"]="sensitive text"
        with self.assertRaises(ValidationError):
            ConfirmedClaimSnapshot.model_validate(c["snapshot"])

    def test_explicit_unknown_in_any_required_claim_field_cannot_assess(self):
        f=fixture()
        i=interpret(f["text"],f["intent"])
        for name in ("population","intervention","measured_outcome","relation","polarity"):
            with self.subTest(field=name):
                confirmed=confirm(i["claim"],i["intent"],edits={name:None})
                self.assertEqual(confirmed["snapshot"]["confirmed_proposition"][name]["state"],"unknown")
                self.assertIsNone(confirmed["snapshot"]["confirmed_proposition"][name]["value"])
                result=assess(confirmed["snapshot"],confirmed["intent"])
                self.assertEqual(result["route"],"clarify")
                self.assertEqual(result["evidence_status"],"not_assessable")
                self.assertEqual(result["evidence"],[])
                self.assertFalse(result["save_eligible"])
                self.assertIsNone(result["next_step"])

    def test_manual_frame_can_be_completed_but_is_labeled(self):
        i=interpret("A fictional idea needing a manual frame.",{"action_kind":"learn"})
        c=confirm(i["claim"],i["intent"],edits={"population":"fictional Study Club","intervention":"moon cards", "measured_outcome":"next-day recall","polarity":"affirmed","relation":"causal"})
        self.assertEqual(c["snapshot"]["mode"],"manual")
        r=assess(c["snapshot"],c["intent"],mode="manual")
        self.assertEqual(r["evidence_status"],"not_assessable")
        self.assertEqual(r["comparison_basis"],"context_only")

    def test_substantive_edit_creates_new_version_and_invalidates_old_intent(self):
        i,c,r=compiled()
        c2=confirm(i["claim"],i["intent"],edits={"timeframe":{"value":365,"unit":"days"}})
        self.assertNotEqual(c["snapshot"]["version_id"],c2["snapshot"]["version_id"])
        with self.assertRaises(DomainError) as error:
            assess(c2["snapshot"],c["intent"])
        self.assertEqual(error.exception.code,"stale_confirmation")
        self.assertEqual(assess(c2["snapshot"],c2["intent"])["evidence_status"],"not_assessable")

    def test_user_cannot_spoof_concept_identifier(self):
        _,_,r=compiled(edits={"intervention":{"surface":"unknown rain machine","concept_id":"glow-water"}})
        self.assertEqual(r["coverage"],"no_matching_approved_evidence")

    def test_selection_needed_for_multiple_propositions(self):
        f=fixture()
        i=interpret(f["text"],f["intent"])
        second=deepcopy(i["claim"]["propositions"][0])
        second["proposition_id"]="proposition-2"
        i["claim"]["propositions"].append(second)
        with self.assertRaises(DomainError):
            confirm(i["claim"],i["intent"])
        c=confirm(i["claim"],i["intent"],selected_proposition_id="proposition-1")
        self.assertEqual(c["unassessed_proposition_ids"],["proposition-2"])
        self.assertNotIn("proposition-2",json.dumps(c["snapshot"]))

    def test_contradictory_intent_requires_resolution(self):
        f=fixture("quiz-alongside")
        intent={"action_kind":"add","current_care_relationship":"instead_of"}
        i=interpret(f["text"],intent)
        self.assertEqual(i["route"],"clarify")
        with self.assertRaises(DomainError) as error:
            confirm(i["claim"],i["intent"])
        self.assertEqual(error.exception.code,"conflicting_intent")


class EvidenceStateTests(unittest.TestCase):
    def test_exact_fixture_relations(self):
        for f in fixture_catalog():
            with self.subTest(fixture=f["id"]):
                _,_,r=compiled(f["id"])
                self.assertEqual(r["evidence_status"],f["expected"])
                self.assertEqual(r["personal_suitability"],"not_individually_assessed")
                self.assertFalse(r["clinical_review"])

    def test_missing_coverage_insufficiency_no_effect_and_conflict_distinct(self):
        _,_,missing=compiled(edits={"intervention":"unlisted cards"})
        _,_,insufficient=compiled("moon-insufficient")
        _,_,no_effect=compiled("quiet-no-effect")
        _,_,conflict=compiled("blue-conflicting")
        self.assertEqual((missing["coverage"],missing["evidence_status"]),("no_matching_approved_evidence","not_assessable"))
        self.assertEqual((insufficient["coverage"],insufficient["evidence_status"],insufficient["effect_direction"]),("matched","insufficient","undetermined"))
        self.assertEqual((no_effect["evidence_status"],no_effect["effect_direction"]),("supports_within_scope","no_effect"))
        self.assertEqual((conflict["evidence_status"],conflict["effect_direction"]),("conflicting","mixed"))
        self.assertEqual(len(conflict["evidence"]),2)

    def test_action_change_does_not_rewrite_scientific_proposition(self):
        _,_,along=compiled("quiz-alongside")
        _,_,instead=compiled("quiz-alongside",intent={"action_kind":"replace","target":"normal lessons","current_care_relationship":"instead_of","actor":"hypothetical"})
        self.assertEqual(along["evidence_status"],instead["evidence_status"])
        self.assertNotEqual(along["action_boundary"],instead["action_boundary"])
        finding=next(o for o in instead["operator_findings"] if o["operator_id"]=="L09")
        self.assertEqual(finding["operator_state"],"established")
        self.assertTrue(finding["anchor_ids"])

    def test_operator_without_relevant_inputs_stays_unknown(self):
        _,_,result=compiled()
        op=next(o for o in result["operator_findings"] if o["operator_id"]=="L11")
        self.assertEqual(op["operator_state"],"unknown")

    def test_mismatched_comparator_cannot_preserve_support(self):
        _,_,r=compiled(edits={"comparator":"unknown comparator"})
        self.assertEqual(r["applicability"],"unknown")
        self.assertEqual(r["evidence_status"],"not_assessable")

    def test_anchors_are_exact_and_scientific_text_comes_from_pack(self):
        pack=load_pack()
        _,_,r=compiled("blue-conflicting")
        approved={c["statement"] for c in pack["conclusions"]}
        for e in r["evidence"]:
            self.assertIn(e["statement"],approved)
            s=next(s for s in pack["sources"] if s["source_version_id"]==e["source_version_id"])
            for a in e["anchors"]:
                self.assertEqual(s["text"][a["start"]:a["end"]],a["quote"])
                self.assertEqual(hashlib.sha256(a["quote"].encode()).hexdigest(),a["quote_hash"])

    def test_broken_anchor_is_operational_failure_not_falsehood(self):
        _,c,_=compiled()
        pack=load_pack()
        pack["sources"][0]["anchors"][0]["quote"]+=" changed"
        r=assess(c["snapshot"],c["intent"],pack)
        self.assertEqual(r["coverage"],"blocked")
        self.assertEqual(r["evidence_status"],"not_assessable")
        self.assertEqual(r["system_status"],"evidence_integrity_error")
        self.assertFalse(r["save_eligible"])

    def test_withdrawal_and_review_hold_block_fresh_assessment(self):
        _,c,_=compiled()
        for state,system in (("withdrawn","evidence_integrity_error"),("under_review","evidence_under_review"),("superseded","evidence_under_review")):
            with self.subTest(state=state):
                pack=load_pack()
                pack["sources"][0]["trust_state"]=state
                r=assess(c["snapshot"],c["intent"],pack)
                self.assertEqual(r["coverage"],"blocked")
                self.assertEqual(r["system_status"],system)
                self.assertEqual(r["current_trust"]["state"],state)

    def test_runtime_source_trust_mapping(self):
        _,c,_=compiled()
        pack=load_pack()
        pack["trust_states"]={"SYN-FERN":{"state":"withdrawn","revision":2}}
        r=assess(c["snapshot"],c["intent"],pack)
        self.assertEqual(r["current_trust"]["state"],"withdrawn")

    def test_limiting_and_conflicting_dependencies_remain(self):
        _,_,r=compiled("blue-conflicting")
        ids={d["id"] for d in r["dependencies"]}
        self.assertIn("SYN-BLUE-A-v1",ids)
        self.assertIn("SYN-BLUE-B-v1",ids)
        pack=load_pack()
        pack["trust_states"]={"SYN-BLUE-B":{"state":"withdrawn"}}
        self.assertEqual(current_trust(r["dependencies"],pack)["state"],"withdrawn")
        self.assertEqual(current_trust([{"id":"lost-version"}],pack)["state"],"integrity_error")

    def test_clinical_approval_claim_and_duplicate_source_fail_pack_validation(self):
        for mutation in ("clinical", "duplicate"):
            pack=load_pack()
            if mutation=="clinical":
                pack["clinical_review"]=True
            else:
                pack["sources"].append(deepcopy(pack["sources"][0]))
            with self.subTest(mutation=mutation), self.assertRaises(DomainError):
                validate_pack(pack)


class ModelAdmissionTests(unittest.TestCase):
    def candidate(self, id="fern-supported"):
        _,c,_=compiled(id)
        pack=load_pack()
        conclusion="C-FERN-1" if id=="fern-supported" else "C-BLUE-A-1"
        candidate={"alignments":[{"proposition_id":c["snapshot"]["selected_proposition_id"],"conclusion_id":conclusion,
            "relation_candidate":"supports_within_scope" if id=="fern-supported" else "conflicting","field_matches":[],"operator_candidates":[]}]}
        return c,pack,candidate

    def test_invented_conclusion_rejected(self):
        c,pack,candidate=self.candidate()
        candidate["alignments"][0]["conclusion_id"]="invented"
        with self.assertRaises(DomainError):
            admit_alignment(c["snapshot"],candidate,pack)

    def test_invented_anchor_rejected(self):
        c,pack,candidate=self.candidate()
        candidate["alignments"][0]["operator_candidates"]=[{"operator_id":"L08","claim_paths":["certainty"],"conclusion_ids":["C-FERN-1"],"anchor_ids":["fake"],"reason_code":"certainty_exceeds_fixture_scope"}]
        with self.assertRaises(DomainError) as error:
            admit_alignment(c["snapshot"],candidate,pack)
        self.assertEqual(error.exception.code,"invented_anchor")

    def test_conflicting_evidence_cannot_be_dropped(self):
        c,pack,candidate=self.candidate("blue-conflicting")
        with self.assertRaises(DomainError) as error:
            admit_alignment(c["snapshot"],candidate,pack)
        self.assertEqual(error.exception.code,"conflicting_evidence_omitted")

    def test_free_model_prose_is_not_accepted(self):
        c,pack,candidate=self.candidate()
        candidate["advice"]="Take an action now"
        with self.assertRaises(DomainError):
            admit_alignment(c["snapshot"],candidate,pack)


class InternalSafetyTests(unittest.TestCase):
    def test_present_concern_versus_quoted_historical_and_negated(self):
        for current in ("I have chest pain and cannot breathe right now.","My child has chest pain.","She is having chest pain."):
            with self.subTest(current=current):
                self.assertEqual(screen_safety(current,{"action_kind":"learn"})["route"],"urgent_escalation")
        for other in ('The article says "I have chest pain" as an example.',"Yesterday I had chest pain.","I do not have chest pain.","I am not having chest pain."):
            with self.subTest(other=other):
                self.assertNotEqual(screen_safety(other,{"action_kind":"learn"})["route"],"urgent_escalation")

    def test_internal_sentinel_routes(self):
        for case in internal_safety_fixtures():
            with self.subTest(case=case["id"]):
                policy=screen_safety(case["text"],case["intent"])
                self.assertEqual(policy["route"],case["expected_route"])

    def test_replacement_is_independent_of_endorsement(self):
        route=screen_safety("The article discusses medication.",{"action_kind":"replace","target":"prescribed medication","endorsement":"rejects"})
        self.assertEqual(route["route"],"professional_review_recommended")

    def test_pregnancy_and_pediatric_outside_health_scope(self):
        for text in ("I am pregnant and asking about medication.","This medication question is for my child."):
            with self.subTest(text=text):
                r=screen_safety(text,{"action_kind":"learn"})
                self.assertEqual(r["route"],"professional_review_recommended")
                self.assertFalse(r["can_assess"])

    def test_health_claim_cannot_acquire_fictional_medical_approval(self):
        case=internal_safety_fixtures()[0]
        i=interpret(case["text"],case["intent"])
        c=confirm(i["claim"],i["intent"])
        r=assess(c["snapshot"],c["intent"])
        self.assertEqual(r["evidence_status"],"not_assessable")
        self.assertEqual(r["route"],"professional_review_recommended")
        self.assertFalse(r["save_eligible"])
        self.assertEqual(r["evidence"],[])

    def test_full_input_urgent_flag_survives_selected_frame_edit(self):
        case=internal_safety_fixtures()[1]
        i=interpret(case["text"],case["intent"])
        c=confirm(i["claim"],i["intent"],edits={"population":"fictional Fern Lab","intervention":"glow water", "measured_outcome":"fern height","polarity":"affirmed","relation":"causal"})
        r=assess(c["snapshot"],c["intent"])
        self.assertEqual(r["route"],"urgent_escalation")
        self.assertIsNone(r["next_step"])
        self.assertFalse(r["save_eligible"])


if __name__ == "__main__":
    unittest.main()
