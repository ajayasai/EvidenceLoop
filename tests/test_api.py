"""Integration tests use a portable, isolated PostgreSQL schema and non-owner role."""
from __future__ import annotations

import json
import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def app(monkeypatch,isolated_database):
    monkeypatch.setenv("REVIEWER_TOKEN", "test-reviewer-token")
    from services.api.app.main import create_app
    application = create_app(isolated_database.url)
    yield application


@pytest.fixture()
def client(app):
    with TestClient(app) as client:
        session = client.get("/api/session").json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        yield client


def make_receipt(client, example_id=None):
    catalog = client.get("/api/examples").json()
    example = next((x for x in catalog if x["id"] == example_id), catalog[0])
    response = client.post("/api/claims", json={"text": example["text"], "intent": example["intent"], "mode": "replay"})
    assert response.status_code == 200, response.text
    draft = response.json()
    response = client.post(f"/api/claims/{draft['draft_id']}/confirm", json={"expected_revision":draft["revision"],"selected_proposition_id":draft["claim"]["propositions"][0]["proposition_id"],"edits":{}})
    assert response.status_code == 200, response.text
    confirmed = response.json()
    response = client.post("/api/assessments", json={"draft_id":draft["draft_id"],"expected_revision":confirmed["revision"]})
    assert response.status_code == 200, response.text
    return response.json()


def save_receipt(client, receipt=None, key=None):
    receipt = receipt or make_receipt(client)
    preview = client.post("/api/next-steps/preview", json={"receipt_id":receipt["receipt_id"]})
    assert preview.status_code == 200, preview.text
    value = preview.json()
    body = {"preview_id":value["preview_id"],"preview_hash":value["preview_hash"],"consent":True}
    headers = {"Idempotency-Key": key or uuid.uuid4().hex}
    response = client.post("/api/next-steps", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json(), body, headers


def snapshot_rows(app):
    """Read full persistent rows on a fresh connection without renewing retention."""
    with app.state.store.connect() as con:
        def rows(sql):
            return [dict(row) for row in con.execute(sql).fetchall()]

        return {
            "owners": rows("SELECT * FROM owners ORDER BY id"),
            "next_steps": rows("SELECT * FROM next_steps ORDER BY id"),
            "idempotency": rows("SELECT * FROM idempotency ORDER BY owner_id, key"),
        }


def test_capture_confirm_assess_do_not_persist(client, app):
    receipt = make_receipt(client)
    assert receipt["persistence"] == "ephemeral"
    with app.state.store.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM next_steps").fetchone()["n"] == 0
        assert con.execute("SELECT count(*) AS n FROM owners").fetchone()["n"] == 0
    assert receipt["receipt"]["synthetic"] is True
    snapshot = json.dumps(receipt["receipt"]["snapshot"])
    assert '"original_text"' not in snapshot
    for value in receipt["receipt"]["snapshot"]["confirmed_proposition"].values():
        if isinstance(value, dict) and "provenance" in value:
            assert all(p.get("quote") is None and p["kind"] == "saved_ref" for p in value["provenance"])


def test_confirmation_required_and_stale_revision_rejected(client):
    e = client.get("/api/examples").json()[0]
    draft = client.post("/api/claims",json={"text":e["text"],"intent":e["intent"]}).json()
    assert client.post("/api/assessments",json={"draft_id":draft["draft_id"],"expected_revision":1}).status_code == 409
    assert client.post(f"/api/claims/{draft['draft_id']}/confirm",json={"expected_revision":9}).status_code == 409


def test_save_requires_consent_and_is_idempotent(client, app):
    receipt = make_receipt(client)
    p = client.post("/api/next-steps/preview",json={"receipt_id":receipt["receipt_id"]}).json()
    body = {"preview_id":p["preview_id"],"preview_hash":p["preview_hash"],"consent":False}
    assert client.post("/api/next-steps",json=body,headers={"Idempotency-Key":"one"}).status_code == 422
    step, body, headers = save_receipt(client, receipt)
    again = client.post("/api/next-steps",json=body,headers=headers)
    assert again.json()["id"] == step["id"]
    assert len(client.get("/api/next-steps").json()["items"]) == 1
    assert client.get(f"/api/receipts/{receipt['receipt_id']}").json()["persistence"] == "saved"


@pytest.mark.parametrize("preexisting_saved_row", [False, True], ids=["fresh-owner", "existing-owner"])
def test_denied_save_consent_leaves_all_persistent_rows_unchanged(client, app, preexisting_saved_row):
    if preexisting_saved_row:
        save_receipt(client)
    receipt = make_receipt(client)
    preview = client.post("/api/next-steps/preview", json={"receipt_id": receipt["receipt_id"]})
    assert preview.status_code == 200, preview.text
    value = preview.json()
    before = snapshot_rows(app)
    expected_count = 1 if preexisting_saved_row else 0
    assert {name: len(rows) for name, rows in before.items()} == {
        "owners": expected_count, "next_steps": expected_count, "idempotency": expected_count,
    }

    response = client.post("/api/next-steps", json={
        "preview_id": value["preview_id"], "preview_hash": value["preview_hash"], "consent": False,
    }, headers={"Idempotency-Key": "denied-consent"})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Explicit permission to save this receipt and question is required."
    assert snapshot_rows(app) == before, "Denied save must not insert or alter any persistent row."


def test_denied_checkin_consent_leaves_all_persistent_rows_unchanged(client, app):
    step, _, _ = save_receipt(client)
    before = snapshot_rows(app)
    assert {name: len(rows) for name, rows in before.items()} == {
        "owners": 1, "next_steps": 1, "idempotency": 1,
    }
    assert before["next_steps"][0]["version"] == step["version"] == 1
    assert before["next_steps"][0]["state"] == "planned"
    assert before["next_steps"][0]["check_ins"] == []

    response = client.post(f"/api/next-steps/{step['id']}/check-ins", json={
        "expected_version": step["version"], "state": "done_self_reported", "consent": False,
    })
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Consent to save this self-report is required."
    assert snapshot_rows(app) == before, "Denied check-in must not alter any persistent row, including its version."


def test_csrf_origin_body_and_schema_boundaries(client):
    assert client.post("/api/claims",json={"text":"hello"},headers={"X-CSRF-Token":"wrong"}).status_code == 403
    assert client.post("/api/claims",json={"text":"hello"},headers={"Origin":"https://evil.example"}).status_code == 403
    assert client.post("/api/claims",json={"text":"hello","admin":True}).status_code == 422
    response = client.post("/api/claims",content=b'x'*32769,headers={"Content-Type":"application/json"})
    assert response.status_code == 413
    secret_like = "private-input-marker-"*400
    response = client.post("/api/claims",json={"text":secret_like})
    assert response.status_code == 422
    assert "private-input-marker" not in response.text


def test_cross_owner_isolation(client, app):
    receipt = make_receipt(client)
    step, _, _ = save_receipt(client, receipt)
    with TestClient(app) as other:
        other.headers["X-CSRF-Token"] = other.get("/api/session").json()["csrf_token"]
        assert other.get(f"/api/receipts/{receipt['receipt_id']}").status_code == 404
        assert other.get("/api/next-steps").json()["items"] == []
        assert other.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":1,"state":"done_self_reported","consent":True}).status_code == 404
        assert other.get("/api/review/sources").status_code == 403


def test_checkin_version_and_context_changes(client):
    step, _, _ = save_receipt(client)
    body = {"expected_version":step["version"],"state":"done_self_reported","consent":True,"new_concern_text":"My question has changed."}
    response = client.post(f"/api/next-steps/{step['id']}/check-ins",json=body)
    assert response.json()["saved"] is False
    body.pop("new_concern_text")
    body["exercise_choice"] = "different"
    response = client.post(f"/api/next-steps/{step['id']}/check-ins",json=body)
    assert response.json()["step"]["state"] == "done_self_reported"
    assert response.json()["step"]["version"] == 2
    assert client.post(f"/api/next-steps/{step['id']}/check-ins",json=body).status_code == 409


def test_withdrawal_blocks_old_receipt_writes_and_restore_does_not_revalidate_history(client):
    receipt = make_receipt(client)
    step, _, _ = save_receipt(client, receipt)
    assert client.post("/api/review/login",json={"token":"test-reviewer-token"}).status_code == 200
    source_id = receipt["receipt"]["source_ids"][0]
    row = next(x for x in client.get("/api/review/sources").json()["items"] if x["source_id"] == source_id)
    change = client.post(f"/api/review/sources/{source_id}/decision",json={"expected_revision":row["revision"],"decision":"withdraw","reason":"Synthetic integrity exercise"})
    assert change.status_code == 200
    assert client.get(f"/api/receipts/{receipt['receipt_id']}").json()["current_trust"]["state"] == "withdrawn"
    assert client.post("/api/next-steps/preview",json={"receipt_id":receipt["receipt_id"]}).status_code == 409
    assert client.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":1,"state":"done_self_reported","consent":True}).status_code == 409
    restore = client.post(f"/api/review/sources/{source_id}/decision",json={"expected_revision":change.json()["revision"],"decision":"restore","reason":"Synthetic restore"})
    assert restore.status_code == 200
    assert client.get(f"/api/receipts/{receipt['receipt_id']}").json()["current_trust"]["state"] == "under_review"


def test_reopen_saved_session_and_delete(client, app):
    step, _, _ = save_receipt(client)
    owner_cookie = client.cookies.get("el_owner")
    with TestClient(app) as reopened:
        reopened.cookies.set("el_owner", owner_cookie)
        reopened.headers["X-CSRF-Token"] = reopened.get("/api/session").json()["csrf_token"]
        assert reopened.get("/api/next-steps").json()["items"][0]["id"] == step["id"]
        assert reopened.delete("/api/account/data").json()["deleted"] is True
        assert reopened.get("/api/session").status_code == 200
        assert reopened.get("/api/next-steps").json()["items"] == []


def test_partial_reconfirmation_preserves_edits_and_only_semantic_changes_reset_attempt(client, app):
    example = client.get("/api/examples").json()[0]
    draft = client.post("/api/claims",json={"text":example["text"],"intent":example["intent"]}).json()
    path = f"/api/claims/{draft['draft_id']}/confirm"
    first = client.post(path,json={"expected_revision":1,"edits":{"intervention":"blue water"}}).json()
    internal = next(iter(app.state.sessions.values()))["drafts"][draft["draft_id"]]
    ledger = internal["ledger"]
    ledger.terminal_stages.add("alignment")
    same = client.post(path,json={"expected_revision":first["revision"],"edits":{}}).json()
    assert same["revision"] == first["revision"]
    assert same["attempt_id"] == first["attempt_id"]
    assert internal["ledger"] is ledger
    response = client.post(path,json={"expected_revision":same["revision"],"edits":{"measured_outcome":"leaf width"}})
    assert response.status_code == 200, response.text
    second = response.json()
    frame = second["snapshot"]["confirmed_proposition"]
    assert frame["intervention"]["value"]["surface"] == "blue water"
    assert frame["measured_outcome"]["value"]["surface"] == "leaf width"
    assert second["parent_attempt_id"] == first["attempt_id"]
    assert second["attempt_id"] != first["attempt_id"]
    assert second["snapshot"]["parent_version_id"] == first["snapshot"]["version_id"]
    assert internal["ledger"] is not ledger
    assert internal["ledger"].terminal_stages == set()
    assert "confirmed_edits" not in second


def test_explicit_null_intent_is_not_silently_ignored(client):
    e = client.get("/api/examples").json()[0]
    draft = client.post("/api/claims",json={"text":e["text"],"intent":{**e["intent"],"target":"garden"}}).json()
    path = f"/api/claims/{draft['draft_id']}/confirm"
    first = client.post(path,json={"expected_revision":1,"edits":{}}).json()
    cleared = client.post(path,json={"expected_revision":first["revision"],"intent":{"target":None}}).json()
    assert cleared["intent"]["target"]["state"] == "unknown"
    assert cleared["intent"]["target"]["value"] is None
    missing = client.post(path,json={"expected_revision":cleared["revision"],"intent":{"action_kind":None}})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "confirmation_incomplete"
