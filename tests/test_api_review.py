"""Clinical publication boundaries with fictional engineering data in isolated PG.

The qualification records and source packets in this suite are NOT clinical
reviews. They are never installed in the runtime database and are dropped after
each test. Both evidence staff and user flows go through the HTTP API.
"""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import domain
from app.compiler import ClaimCompiler
from app.provider import AttemptBudget, ProviderError
from app.storage import digest
from test_review import reviews, source_payload, brief_payload, engineering_claim_fixture


@pytest.fixture
def api_review(reviews,monkeypatch):
    review,qualification=reviews
    monkeypatch.setenv("EDITOR_TOKEN","engineering-editor-token")
    from app.main import create_app
    config={"clinical_enabled":True,"qualified_reviewers":{"engineering-reviewer":qualification},
            "token_hashes":{"engineering-reviewer":digest("engineering-reviewer-token")}}
    app=create_app(review.store.url,review_config=config)
    with TestClient(app) as reader:
        session=reader.get("/api/session").json()
        reader.headers["X-CSRF-Token"]=session["csrf_token"]
        staff=TestClient(app)
        staff_session=staff.get("/api/session").json()
        staff.headers["X-CSRF-Token"]=staff_session["csrf_token"]
        assert staff.post("/api/review/editor-login",json={"token":"engineering-editor-token"}).status_code==200
        yield app,reader,staff,qualification
        staff.close()


def _ok(response):
    assert response.status_code==200,response.text
    return response.json()


def publish_scenario(api_review,with_context=True):
    app,reader,staff,qualification=api_review
    source=_ok(staff.post("/api/review/sources",json=source_payload()))
    body=brief_payload(source["source_version_id"])
    context=None
    if with_context:
        context_body=source_payload()
        context_body["source_id"]="ENGINEERING-CONTEXT"
        context_body["title"]="Context packet without a displayed conclusion anchor"
        context_body["anchors"][0]["anchor_id"]="ENGINEERING-CONTEXT-A1"
        context_body["origin_group_ids"]=["engineering-context-origin"]
        context=_ok(staff.post("/api/review/sources",json=context_body))
        body["source_dependencies"].append({"source_version_id":context["source_version_id"],"role":"context"})
    brief=_ok(staff.post("/api/review/briefs",json=body))
    _ok(staff.post("/api/review/clinical-login",json={"identity":"engineering-reviewer","token":"engineering-reviewer-token"}))
    _ok(staff.post(f"/api/review/briefs/{brief['brief_version_id']}/decisions",json={"decision":"approved",
        "rationale":"Fictional engineering test approval only. No medical review is asserted.","expected_hash":brief["target_hash"]}))
    publication=_ok(staff.post("/api/review/publications",json={"brief_version_ids":[brief["brief_version_id"]],"expected_revision":0}))
    return {"source":source,"context":context,"brief":brief,"publication":publication}


def make_clinical_receipt(reader):
    fixture=engineering_claim_fixture()
    captured=_ok(reader.post("/api/claims",json={"text":fixture["text"],
        "mode":"replay","intent":fixture["intent"]}))
    confirmed=_ok(reader.post(f"/api/claims/{captured['draft_id']}/confirm",json={"expected_revision":captured["revision"],"edits":{}}))
    envelope=_ok(reader.post("/api/assessments",json={"draft_id":captured["draft_id"],"expected_revision":confirmed["revision"]}))
    assert envelope["receipt"]["evidence_status"]=="supports_within_scope"
    assert envelope["receipt"]["clinical_review"] is True
    assert envelope["receipt"]["synthetic"] is False
    return envelope


def preview_receipt(reader,receipt):
    return _ok(reader.post("/api/next-steps/preview",json={"receipt_id":receipt["receipt_id"]}))


def save_preview(reader,preview):
    return reader.post("/api/next-steps",json={"preview_id":preview["preview_id"],"preview_hash":preview["preview_hash"],"consent":True},
        headers={"Idempotency-Key":uuid4().hex})


def assert_saved_step_unchanged(app,step):
    with app.state.store.connect() as con:
        row=con.execute("SELECT version,check_ins FROM next_steps WHERE id=%s",(step["id"],)).fetchone()
    assert row["version"]==step["version"]
    assert row["check_ins"]==step["check_ins"]


def snapshot_user_rows(app):
    """Read complete user rows without renewing retention; review/audit rows are separate."""
    with app.state.store.connect() as con:
        def rows(sql):
            return [dict(row) for row in con.execute(sql).fetchall()]

        return {
            "owners": rows("SELECT * FROM owners ORDER BY id"),
            "next_steps": rows("SELECT * FROM next_steps ORDER BY id"),
            "idempotency": rows("SELECT * FROM idempotency ORDER BY owner_id, key"),
        }


def test_context_source_is_persisted_even_without_displayed_anchor(api_review):
    app,reader,staff,qualification=api_review
    scenario=publish_scenario(api_review)
    receipt=make_clinical_receipt(reader)
    assert {e["source_id"] for e in receipt["receipt"]["evidence"]}=={"ENGINEERING-SOURCE"}
    assert set(receipt["receipt"]["source_ids"])=={"ENGINEERING-SOURCE","ENGINEERING-CONTEXT"}
    assert receipt["receipt"]["reproduction"]["publication_id"]==scenario["publication"]["publication_id"]
    step=_ok(save_preview(reader,preview_receipt(reader,receipt)))
    state=app.state.store.trust(["ENGINEERING-CONTEXT"])["ENGINEERING-CONTEXT"]
    _ok(staff.post("/api/review/sources/ENGINEERING-CONTEXT/withdrawal",json={
        "expected_revision":state["revision"],"reason":"Engineering context withdrawal exercise."}))
    reopened=_ok(reader.get(f"/api/receipts/{receipt['receipt_id']}"))
    assert reopened["current_trust"]["state"]=="withdrawn"
    assert "ENGINEERING-CONTEXT" in reopened["current_trust"]["affected_dependency_ids"]
    response=reader.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":step["version"],"state":"done_self_reported","consent":True})
    assert response.status_code==409,response.text
    assert_saved_step_unchanged(app,step)


def test_context_withdrawal_between_preview_and_save_creates_no_rows(api_review):
    app,reader,staff,qualification=api_review
    publish_scenario(api_review)
    preview=preview_receipt(reader,make_clinical_receipt(reader))
    state=app.state.store.trust(["ENGINEERING-CONTEXT"])["ENGINEERING-CONTEXT"]
    _ok(staff.post("/api/review/sources/ENGINEERING-CONTEXT/withdrawal",json={
        "expected_revision":state["revision"],"reason":"Engineering context withdrawal exercise."}))
    response=save_preview(reader,preview)
    assert response.status_code==409,response.text
    with app.state.store.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM next_steps").fetchone()["n"]==0
        assert con.execute("SELECT count(*) AS n FROM owners").fetchone()["n"]==0


@pytest.mark.parametrize("kind", ["save", "checkin"])
def test_post_precheck_source_withdrawal_blocks_user_write(api_review, monkeypatch, kind):
    app, reader, staff, qualification = api_review
    publish_scenario(api_review)
    receipt = make_clinical_receipt(reader)
    preview = preview_receipt(reader, receipt)
    if kind == "checkin":
        step = _ok(save_preview(reader, preview))

    source_id = "ENGINEERING-CONTEXT"
    state_before = app.state.store.trust([source_id])[source_id]
    assert state_before["state"] == "current"
    method_name = "save" if kind == "save" else "check_in"
    original = getattr(app.state.store, method_name)
    entered = 0

    def withdraw_then_write(*args, **kwargs):
        nonlocal entered
        entered += 1
        # Commit a real withdrawal after the route precheck, then call the real
        # storage method. This ordered window test does not prove lock isolation
        # or general concurrent scheduling behavior.
        revision = app.state.store.trust([source_id])[source_id]["revision"]
        app.state.reviews.withdraw_source(
            "local-evidence-editor", source_id, revision,
            "Engineering post-precheck withdrawal exercise.",
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(app.state.store, method_name, withdraw_then_write)
    before = snapshot_user_rows(app)
    expected_count = 0 if kind == "save" else 1
    assert {name: len(rows) for name, rows in before.items()} == {
        "owners": expected_count, "next_steps": expected_count, "idempotency": expected_count,
    }
    if kind == "save":
        response = save_preview(reader, preview)
    else:
        response = reader.post(f"/api/next-steps/{step['id']}/check-ins", json={
            "expected_version": step["version"], "state": "done_self_reported", "consent": True,
        })
    after = snapshot_user_rows(app)

    assert entered == 1
    assert app.state.store.trust([source_id])[source_id] == {
        "source_id": source_id, "state": "withdrawn", "revision": state_before["revision"] + 1,
    }
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "version_conflict"
    assert after == before, "Rejected post-precheck withdrawal must leave all user rows unchanged."


def test_operational_withdrawal_requires_editor_and_preserves_cas_and_audit(api_review):
    app,reader,staff,qualification=api_review
    packet=source_payload()
    _ok(staff.post("/api/review/sources",json=packet))
    source_id=packet["source_id"]
    path=f"/api/review/sources/{source_id}/withdrawal"
    state=app.state.store.trust([source_id])[source_id]
    reason="Fictional engineering withdrawal; source packet needs correction."
    body={"expected_revision":state["revision"],"reason":reason}
    assert reader.post(path,json=body).status_code==403
    # A configured clinical reviewer still needs the separate editor role.
    _ok(reader.post("/api/review/clinical-login",json={"identity":"engineering-reviewer","token":"engineering-reviewer-token"}))
    assert reader.post(path,json=body).status_code==403
    assert staff.post(path,json=body,headers={"X-CSRF-Token":"incorrect"}).status_code==403
    withdrawn=_ok(staff.post(path,json=body))
    assert withdrawn=={"source_id":source_id,"state":"withdrawn","revision":state["revision"]+1}
    assert staff.post(path,json=body).status_code==409
    assert staff.post("/api/review/sources/UNKNOWN-ENGINEERING-SOURCE/withdrawal",json=body).status_code==404
    synthetic_id=app.state.pack["sources"][0]["source_id"]
    assert staff.post(f"/api/review/sources/{synthetic_id}/withdrawal",json=body).status_code==404
    queue=_ok(staff.get("/api/review/queue"))
    queued=next(s for s in queue["sources"] if s["source_id"]==source_id)
    assert (queued["state"],queued["revision"])==("withdrawn",withdrawn["revision"])
    with app.state.store.connect() as con:
        events=con.execute("SELECT actor_identity,reason FROM review_audit WHERE event_kind='source_withdrawn' AND entity_id=%s",(source_id,)).fetchall()
    assert events==[{"actor_identity":"local-evidence-editor","reason":reason}]


def test_expired_qualification_blocks_checkin_without_source_revision_change(api_review):
    app,reader,staff,qualification=api_review
    publish_scenario(api_review)
    receipt=make_clinical_receipt(reader)
    step=_ok(save_preview(reader,preview_receipt(reader,receipt)))
    states_before=app.state.store.trust(receipt["receipt"]["source_ids"])
    app.state.reviews.qualified_reviewers["engineering-reviewer"]={**qualification,"expires_at":"2000-01-01T00:00:00+00:00"}
    assert app.state.store.trust(receipt["receipt"]["source_ids"])==states_before
    reopened=_ok(reader.get(f"/api/receipts/{receipt['receipt_id']}"))
    assert reopened["current_trust"]["state"]=="under_review"
    response=reader.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":step["version"],"state":"done_self_reported","consent":True})
    assert response.status_code==409,response.text
    assert_saved_step_unchanged(app,step)


def test_qualification_invalidation_after_precheck_is_caught_inside_save_transaction(api_review,monkeypatch):
    app,reader,staff,qualification=api_review
    publish_scenario(api_review)
    preview=preview_receipt(reader,make_clinical_receipt(reader))
    original=app.state.store.save
    def invalidate_then_save(*args,**kwargs):
        app.state.reviews.qualified_reviewers["engineering-reviewer"]={**qualification,"expires_at":"2000-01-01T00:00:00+00:00"}
        return original(*args,**kwargs)
    monkeypatch.setattr(app.state.store,"save",invalidate_then_save)
    response=save_preview(reader,preview)
    assert response.status_code==409,response.text
    with app.state.store.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM next_steps").fetchone()["n"]==0
        assert con.execute("SELECT count(*) AS n FROM owners").fetchone()["n"]==0


def test_qualification_invalidation_after_precheck_is_caught_inside_checkin_transaction(api_review,monkeypatch):
    app,reader,staff,qualification=api_review
    publish_scenario(api_review)
    receipt=make_clinical_receipt(reader)
    step=_ok(save_preview(reader,preview_receipt(reader,receipt)))
    original=app.state.store.check_in
    def invalidate_then_checkin(*args,**kwargs):
        app.state.reviews.qualified_reviewers["engineering-reviewer"]={**qualification,"expires_at":"2000-01-01T00:00:00+00:00"}
        return original(*args,**kwargs)
    monkeypatch.setattr(app.state.store,"check_in",invalidate_then_checkin)
    response=reader.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":step["version"],"state":"done_self_reported","consent":True})
    assert response.status_code==409,response.text
    assert_saved_step_unchanged(app,step)


def test_new_publication_invalidates_old_saved_receipt(api_review):
    app,reader,staff,qualification=api_review
    scenario=publish_scenario(api_review)
    receipt=make_clinical_receipt(reader)
    step=_ok(save_preview(reader,preview_receipt(reader,receipt)))
    replacement=_ok(staff.post("/api/review/publications",json={"brief_version_ids":[scenario["brief"]["brief_version_id"]],"expected_revision":1}))
    assert replacement["publication_id"]!=receipt["receipt"]["reproduction"]["publication_id"]
    assert _ok(reader.get(f"/api/receipts/{receipt['receipt_id']}"))["current_trust"]["state"]=="under_review"
    response=reader.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":step["version"],"state":"done_self_reported","consent":True})
    assert response.status_code==409,response.text
    assert_saved_step_unchanged(app,step)


@pytest.mark.parametrize("text",["I am pregnant and asking about medication.","This medication question is for my child."])
def test_excluded_health_scope_never_calls_alignment_and_has_accurate_boundary(api_review,text):
    app,reader,staff,qualification=api_review
    publish_scenario(api_review)
    pack=app.state.reviews.load_current_pack()
    captured=domain.interpret(text,{"action_kind":"learn"},mode="manual")
    confirmed=domain.confirm(captured["claim"],captured["intent"],edits={"population":"fictional adults with type 2 diabetes",
        "intervention":"symbolic teaching token","measured_outcome":"fictional score","relation":"causal","polarity":"affirmed"})
    class NeverCall:
        config=SimpleNamespace(require_enabled=lambda:None)
        def __init__(self):
            self.seen=[]
        async def call(self,*args,**kwargs):
            self.seen.append(args[0])
            raise ProviderError("must_not_call_provider_for_excluded_scope")
    provider=NeverCall()
    result=asyncio.run(ClaimCompiler(provider, alignment_enabled=True).assess(confirmed["snapshot"],confirmed["intent"],pack,AttemptBudget()))
    assert provider.seen==[]
    assert result["route"]=="professional_review_recommended"
    assert result["evidence_status"]=="not_assessable"
    assert "outside the reviewed" in result["summary"]
    assert "No clinically reviewed library is installed" not in result["summary"]
