"""Disposable PostgreSQL engineering fixtures, NEVER real medical approvals.

The deliberately fictional qualification registry exists only in these tests.
No reviewer identity, evidence conclusion or publication is seeded in runtime.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import psycopg
from psycopg import sql
import pytest

from app.domain import DomainError, assess, confirm, interpret, validate_pack
from app.review import EvidenceReviewStore, VerifiedClinicalPack
from app.storage import Store


def engineering_claim_fixture():
    """Authored nonclinical semantics, installed only in the isolated test process."""
    def concept(surface):
        return {"surface":surface,"concept_id":None}
    return {"id":"engineering-authored-predicate","title":"Fictional authored comparison fixture",
        "text":"ENGINEERING TEST ONLY: symbolic teaching token changes fictional score in fictional adults with type 2 diabetes.",
        "fields":{
            "population":("fictional adults with type 2 diabetes",concept("fictional adults with type 2 diabetes")),
            "intervention":("symbolic teaching token",concept("symbolic teaching token")),
            "measured_outcome":("fictional score",concept("fictional score")),
            "relation":("changes","causal"),"polarity":("changes","affirmed")},
        "intent":{"action_kind":"learn","actor":"hypothetical"},
        "expected":"supports_within_scope","label":"Engineering-only authored replay; not medical evidence",
        "visibility":"internal_only"}


def qualification():
    return {"qualification_id":"ENGINEERING-TEST-NOT-A-CREDENTIAL","credential_reference":"Fictional test declaration, not a professional credential",
        "verified_by":"automated engineering test only","verified_at":(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),
        "expires_at":(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),"scope":"adult_type_2_diabetes_evidence",
        "conflict_disclosure":"This is a fictional software test; no medical review took place."}


def source_payload():
    text="ENGINEERING FIXTURE ONLY. A symbolic teaching token changes a fictional score in a fictional adult type 2 diabetes exercise. This is not research and establishes no medical fact."
    return {"source_id":"ENGINEERING-SOURCE","title":"Fictional engineering packet, not medical evidence","publisher":"Automated test only",
        "canonical_url":"https://example.invalid/engineering-only","source_type":"official_information","text":text,
        "licensing_note":"Original engineering fixture authored solely for this test.","storage_permission":"permission_granted",
        "permission_reference":"Test fixture author declaration","permission_attested":True,"snapshot_complete":True,
        "origin_group_ids":["engineering-only-origin"],"anchors":[{"anchor_id":"ENGINEERING-A1","start":0,"end":len(text),"quote":text,"section":"Entire test fixture","original_locator":"tests/test_review.py"}]}


def brief_payload(source_version_id):
    return {"family_id":"ENGINEERING-FAMILY","name":"Fictional test only","intended_population":"adults_with_type_2_diabetes",
        "intervention_aliases":["symbolic teaching token"],"source_dependencies":[{"source_version_id":source_version_id,"role":"supports"}],
        "conclusions":[{"conclusion_id":"ENGINEERING-C1","statement":"A fictional symbolic teaching token changes a fictional score; this establishes no medical fact.",
            "outcome_id":"fictional-score","effect_direction":"benefit","anchor_ids":["ENGINEERING-A1"],
            "limitations":["No medical research or clinical review exists in this engineering fixture."],
            "admissions":[{"rule_id":"engineering-rule-1","relation":"supports_within_scope","predicates":[
                {"field_path":"population","allowed_values":["fictional adults with type 2 diabetes"]},
                {"field_path":"intervention","allowed_values":["symbolic teaching token"]},
                {"field_path":"measured_outcome","allowed_values":["fictional score"]},
                {"field_path":"relation","allowed_values":["causal"]},
                {"field_path":"polarity","allowed_values":["affirmed"]}]}]}],
        "review_due_at":(datetime.now(timezone.utc)+timedelta(days=5)).isoformat(),
        "quality_appraisal_label":"Engineering fixture, not medical evidence","quality_appraisal_method":"No scientific appraisal: this packet tests software integrity only.",
        "professional_question":"What evidence would be required to assess this educational question with a professional?",
        "scope_note":"This artificial packet is confined to automated engineering tests and carries no actual clinical approval."}


@pytest.fixture
def reviews(isolated_database, monkeypatch):
    from app import domain
    original_fixtures=domain._fixtures
    monkeypatch.setattr(domain,"_fixtures",lambda:original_fixtures()+[engineering_claim_fixture()])
    q=qualification()
    review=EvidenceReviewStore(Store(isolated_database.url),{"engineering-reviewer":q},clinical_enabled=True)
    yield review,q


def ready(reviews):
    review,q=reviews
    source=review.import_source("engineering-editor",source_payload())
    brief=review.draft_brief("engineering-editor",brief_payload(source["source_version_id"]))
    return review,q,source,brief


def approved(reviews):
    review,q,source,brief=ready(reviews)
    decision=review.review_decision("engineering-reviewer",q["qualification_id"],brief["brief_version_id"],"approved",
        "This is an engineering fixture. No real clinical review has occurred.",brief["target_hash"])
    return review,q,source,brief,decision


def test_default_and_synthetic_reviewers_cannot_approve(reviews):
    review,q,source,brief=ready(reviews)
    for blocked in (EvidenceReviewStore(review.store),EvidenceReviewStore(review.store,{"local-demo":q},True)):
        with pytest.raises(DomainError) as error:
            blocked.review_decision("local-demo",q["qualification_id"],brief["brief_version_id"],"approved","This should never create an approval.",brief["target_hash"])
        assert error.value.status_code==403
    assert review.load_current_pack() is None


def test_import_is_quarantined_deduplicated_and_not_published(reviews):
    review,q=reviews
    first=review.import_source("engineering-editor",source_payload())
    second=review.import_source("engineering-editor",source_payload())
    assert first["source_version_id"]==second["source_version_id"]
    assert second["duplicate"] is True
    assert review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]["state"]=="under_review"
    assert review.load_current_pack() is None
    assert review.list_queue()["publication"]["revision"]==0


def test_broken_anchor_and_missing_storage_attestation_rejected(reviews):
    review,_=reviews
    for field in ("anchor","permission"):
        payload=source_payload()
        if field=="anchor":
            payload["anchors"][0]["start"]=1
        else:
            payload["permission_attested"]=False
        with pytest.raises(DomainError):
            review.import_source("engineering-editor",payload)
    assert review.list_queue()["sources"]==[]


def test_unknown_anchor_and_nonsignificance_no_effect_are_rejected(reviews):
    review,q,source,brief=ready(reviews)
    for field in ("anchor","no_effect"):
        payload=brief_payload(source["source_version_id"])
        if field=="anchor":
            payload["conclusions"][0]["anchor_ids"]=["invented-anchor"]
        else:
            payload["conclusions"][0]["effect_direction"]="no_effect"
        with pytest.raises(DomainError):
            review.draft_brief("engineering-editor",payload)


def test_editor_cannot_approve_own_packet(reviews):
    review,q,source,brief=ready(reviews)
    review.qualified_reviewers["engineering-editor"]=q
    with pytest.raises(DomainError) as error:
        review.review_decision("engineering-editor",q["qualification_id"],brief["brief_version_id"],"approved","Engineering test for independent review enforcement.",brief["target_hash"])
    assert error.value.code=="independent_reviewer_required"


def test_wrong_target_hash_cannot_be_approved(reviews):
    review,q,source,brief=ready(reviews)
    with pytest.raises(DomainError) as error:
        review.review_decision("engineering-reviewer",q["qualification_id"],brief["brief_version_id"],"approved","Engineering test for exact target hash enforcement.","0"*64)
    assert error.value.code=="review_target_changed"


def test_unapproved_brief_cannot_publish(reviews):
    review,q,source,brief=ready(reviews)
    with pytest.raises(DomainError) as error:
        review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    assert error.value.code=="brief_not_approved"
    assert review.list_queue()["publication"]["revision"]==0


def test_atomic_publication_and_compare_and_swap(reviews):
    review,q,source,brief,decision=approved(reviews)
    published=review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    assert published["revision"]==1
    assert review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]["state"]=="current"
    pack=review.load_current_pack()
    assert pack.publication_verified
    validate_pack(pack)
    validate_pack(deepcopy(pack))
    with pytest.raises(DomainError) as error:
        review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    assert error.value.code=="publication_revision_changed"
    assert review.list_queue()["publication"]["revision"]==1


def test_plain_json_cannot_manufacture_publication_authority(reviews):
    review,q,source,brief,decision=approved(reviews)
    review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    pack=review.load_current_pack()
    with pytest.raises(DomainError):
        validate_pack(json.loads(json.dumps(pack)))
    with pytest.raises(DomainError):
        VerifiedClinicalPack(dict(pack))
    changed=deepcopy(pack)
    changed["conclusions"][0]["statement"]="Changed outside the approved publication."
    with pytest.raises(DomainError):
        validate_pack(changed)


def test_versions_and_review_decisions_are_database_immutable(reviews):
    review,q,source,brief,decision=approved(reviews)
    for table,key,id in (("review_sources","source_version_id",source["source_version_id"]),("review_briefs","brief_version_id",brief["brief_version_id"]),("review_decisions","review_id",decision["review_id"])):
        with pytest.raises(psycopg.Error), review.store.connect() as con:
            con.execute(sql.SQL("DELETE FROM {} WHERE {}=%s").format(sql.Identifier(table),sql.Identifier(key)),(id,))


def test_withdrawal_blocks_publication_without_partial_write(reviews):
    review,q,source,brief,decision=approved(reviews)
    state=review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]
    review.store.change_trust("ENGINEERING-SOURCE",state["revision"],"withdrawn")
    with pytest.raises(DomainError) as error:
        review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    assert error.value.code=="source_withdrawn"
    assert review.list_queue()["publication"]["revision"]==0
    with review.store.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM review_publications").fetchone()["n"]==0


def test_editor_withdrawal_is_audited_cas_and_blocks_published_pack(reviews):
    review,q,source,brief,decision=approved(reviews)
    review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    state=review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]
    # Withdrawal needs editor authentication, not authority to approve medicine.
    operator=EvidenceReviewStore(review.store)
    result=operator.withdraw_source("engineering-editor","ENGINEERING-SOURCE",state["revision"],"Engineering test: packet integrity is being investigated.")
    assert result["state"]=="withdrawn"
    assert result["revision"]==state["revision"]+1
    queue=operator.list_queue()
    assert queue["sources"][0]["state"]=="withdrawn"
    assert queue["sources"][0]["revision"]==result["revision"]
    with pytest.raises(DomainError) as error:
        operator.withdraw_source("engineering-editor","ENGINEERING-SOURCE",state["revision"],"A stale retry must not duplicate this event.")
    assert error.value.code=="source_revision_changed"
    with review.store.connect() as con:
        rows=con.execute("SELECT actor_identity,reason FROM review_audit WHERE event_kind='source_withdrawn'").fetchall()
    assert len(rows)==1
    assert rows[0]["actor_identity"]=="engineering-editor"
    assert "packet integrity" in rows[0]["reason"]
    pack=review.load_current_pack()
    from app.domain import current_trust
    assert current_trust([{"id":source["source_version_id"],"kind":"source_version"}],pack)["state"]=="withdrawn"
    with pytest.raises(DomainError) as error:
        review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],1)
    assert error.value.code=="source_withdrawn"


def test_withdrawal_rejects_unknown_source_and_does_not_operate_on_synthetic_registry(reviews):
    review,q=reviews
    review.store.seed_states(["SYN-FERN"])
    for source_id in ("missing-source","SYN-FERN"):
        with pytest.raises(DomainError) as error:
            review.withdraw_source("engineering-editor",source_id,1,"Engineering test reason.")
        assert error.value.code=="unknown_review_source"
    payload=source_payload()
    payload["source_id"]="SYN-FERN"
    with pytest.raises(DomainError):
        review.import_source("engineering-editor",payload)
    assert review.store.trust(["SYN-FERN"])["SYN-FERN"]["state"]=="current"


def test_new_corrected_version_and_independent_review_required_after_withdrawal(reviews):
    review,q,source,brief,decision=approved(reviews)
    publication=review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    state=review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]
    review.withdraw_source("engineering-editor","ENGINEERING-SOURCE",state["revision"],"Engineering correction requires new review.")
    corrected=source_payload()
    corrected["previous_version_id"]=source["source_version_id"]
    corrected["title"]="Corrected fictional engineering packet"
    replacement=review.import_source("engineering-editor",corrected)
    assert review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]["state"]=="under_review"
    new_brief=review.draft_brief("engineering-editor",brief_payload(replacement["source_version_id"]))
    with pytest.raises(DomainError) as error:
        review.publish("engineering-reviewer",q["qualification_id"],[new_brief["brief_version_id"]],1)
    assert error.value.code=="brief_not_approved"
    review.review_decision("engineering-reviewer",q["qualification_id"],new_brief["brief_version_id"],"approved",
        "Engineering correction reviewed only for software tests.",new_brief["target_hash"])
    newer=review.publish("engineering-reviewer",q["qualification_id"],[new_brief["brief_version_id"]],1)
    assert newer["publication_id"]!=publication["publication_id"]
    assert review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]["state"]=="current"


def test_newer_source_cannot_be_bypassed_by_publishing_old_review(reviews):
    review,q,source,brief,decision=approved(reviews)
    payload=source_payload()
    payload["previous_version_id"]=source["source_version_id"]
    payload["title"]="A later fictional engineering version"
    review.import_source("engineering-editor",payload)
    with pytest.raises(DomainError) as error:
        review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    assert error.value.code=="newer_source_requires_review"


def test_qualification_change_invalidates_active_pack(reviews):
    review,q,source,brief,decision=approved(reviews)
    review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    review.qualified_reviewers["engineering-reviewer"]={**q,"credential_reference":"changed configuration requires a new review"}
    with pytest.raises(DomainError) as error:
        review.load_current_pack()
    assert error.value.code=="reviewer_qualification_changed"


def test_publication_guard_rejects_superseded_and_later_rejected_reviews(reviews):
    review,q,source,brief,decision=approved(reviews)
    first=review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    with review.store.connect() as con:
        assert review.require_current_publication(con,first["publication_id"])["revision"]==1
    second=review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],1)
    with pytest.raises(DomainError) as error,review.store.connect() as con:
        review.require_current_publication(con,first["publication_id"])
    assert error.value.code=="publication_revision_changed"
    review.review_decision("engineering-reviewer",q["qualification_id"],brief["brief_version_id"],"rejected",
        "Engineering test: reject this packet after publication.",brief["target_hash"])
    with pytest.raises(DomainError) as error,review.store.connect() as con:
        review.require_current_publication(con,second["publication_id"])
    assert error.value.code=="brief_not_approved"


def test_active_publication_guard_locks_out_concurrent_review_invalidation(reviews):
    review,q,source,brief,decision=approved(reviews)
    published=review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    class BoundedLockStore(Store):
        def connect(self):
            con=super().connect()
            con.execute("SET lock_timeout='150ms'")
            return con
    competitor=EvidenceReviewStore(BoundedLockStore(review.store.url),review.qualified_reviewers,True)
    with review.store.connect() as con:
        review.require_current_publication(con,published["publication_id"])
        with pytest.raises(psycopg.errors.LockNotAvailable):
            competitor.review_decision("engineering-reviewer",q["qualification_id"],brief["brief_version_id"],"rejected",
                "Engineering test: concurrent invalidation must wait.",brief["target_hash"])
        assert con.execute("SELECT count(*) AS n FROM review_decisions").fetchone()["n"]==1
    # The same decision can commit after the simulated save transaction finishes.
    competitor.review_decision("engineering-reviewer",q["qualification_id"],brief["brief_version_id"],"rejected",
        "Engineering test: invalidation after transaction commit.",brief["target_hash"])
    with pytest.raises(DomainError):
        review.load_current_pack()


def test_qualified_pack_uses_reviewed_mappings_and_templates_only(reviews):
    review,q,source,brief,decision=approved(reviews)
    review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    pack=review.load_current_pack()
    fixture=engineering_claim_fixture()
    i=interpret(fixture["text"],fixture["intent"],mode="replay")
    c=confirm(i["claim"],i["intent"])
    blocked=assess(c["snapshot"],c["intent"])
    assert blocked["evidence_status"]=="not_assessable"
    r=assess(c["snapshot"],c["intent"],pack,mode="replay")
    assert r["evidence_status"]=="supports_within_scope"
    assert r["personal_suitability"]=="not_individually_assessed"
    assert r["evidence"][0]["statement"]==pack["conclusions"][0]["statement"]
    assert r["next_step"]["text"]==pack["families"][0]["professional_question"]
    assert r["synthetic_label"] is None
    state=review.store.trust(["ENGINEERING-SOURCE"])["ENGINEERING-SOURCE"]
    review.store.change_trust("ENGINEERING-SOURCE",state["revision"],"withdrawn")
    unavailable=assess(c["snapshot"],c["intent"],review.load_current_pack(),mode="manual")
    assert unavailable["coverage"]=="blocked"
    assert unavailable["evidence_status"]=="not_assessable"


def test_reviewed_noun_mappings_do_not_qualify_manual_claim_effect(reviews):
    review,q,source,brief,decision=approved(reviews)
    review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    pack=review.load_current_pack()
    i=interpret("Fictional teaching token decreases fictional score.",{"action_kind":"learn"},mode="manual")
    c=confirm(i["claim"],i["intent"],edits={"population":"fictional adults with type 2 diabetes",
        "intervention":"symbolic teaching token","measured_outcome":"fictional score","relation":"causal","polarity":"affirmed"})
    r=assess(c["snapshot"],c["intent"],pack,mode="manual")
    assert r["coverage"]=="matched" and r["evidence"]
    assert r["evidence_status"]=="not_assessable" and r["effect_direction"]=="undetermined"
    assert r["comparison_basis"]=="context_only"
    assert r["supported_conclusion_ids"]==[] and r["argument_graph"]["edges"]==[]
    assert r["next_step"] is None and r["save_eligible"] is False
    assert r["review_scope"]=="library_publication_only"


def test_unmatched_clinical_claim_has_library_boundary_without_fictional_or_action_claim(reviews):
    review,q,source,brief,decision=approved(reviews)
    published=review.publish("engineering-reviewer",q["qualification_id"],[brief["brief_version_id"]],0)
    pack=review.load_current_pack()
    captured=interpret("An unmatched medication evidence question.",{"action_kind":"learn"},mode="manual")
    confirmed=confirm(captured["claim"],captured["intent"],edits={"population":"fictional adults with type 2 diabetes",
        "intervention":"unlisted teaching medication","measured_outcome":"fictional score","relation":"causal","polarity":"affirmed"})
    result=assess(confirmed["snapshot"],confirmed["intent"],pack,mode="manual")
    assert result["coverage"]=="no_matching_approved_evidence"
    assert result["evidence_status"]=="not_assessable"
    assert result["effect_direction"]=="undetermined"
    assert "fictional" not in result["summary"].lower()
    assert "No efficacy conclusion is issued" in result["summary"]
    assert result["synthetic"] is False
    assert result["synthetic_label"] is None
    assert result["clinical_review"] is True
    assert result["review_scope"]=="library_publication_only"
    assert result["reproduction"]["publication_id"]==published["publication_id"]
    assert result["personal_suitability"]=="not_individually_assessed"
    assert result["evidence"]==[]
    assert result["next_step"] is None and result["save_eligible"] is False
    assert result["comparison_basis"]=="context_only"
