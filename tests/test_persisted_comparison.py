"""Legacy saved verdicts cannot bypass current comparison eligibility."""
from copy import deepcopy

from psycopg.types.json import Jsonb
import pytest

from services.api.app.main import canonical_hash
from test_api import app, client, make_receipt, save_receipt


@pytest.mark.parametrize("legacy_kind",["manual","live","edited_replay"])
def test_legacy_saved_verdict_is_immutable_but_no_longer_authorizes_writes(client,app,legacy_kind):
    original=make_receipt(client)
    step,body,headers=save_receipt(client,original)
    legacy=deepcopy(step["receipt"])
    if legacy_kind=="edited_replay":
        legacy["snapshot"]["confirmed_proposition"]["polarity"]["value"]="negated"
    else:
        legacy["snapshot"]["mode"]=legacy_kind
    # Model the previous compiler's persisted approval without bypassing any
    # production check in the new HTTP routes. All data is fictional and local
    # to the isolated test database.
    legacy["save_eligible"]=True
    legacy["comparison_basis"]="authored_replay"  # Stored flags are not authority.
    legacy["reproduction"]["compiler_version"]="synthetic-compiler-1.0"
    legacy["confirmed_claim"]=deepcopy(legacy["snapshot"])
    legacy.pop("content_hash",None)
    legacy["content_hash"]=canonical_hash(legacy)
    with app.state.store.connect() as con:
        con.execute("UPDATE next_steps SET receipt=%s WHERE id=%s",(Jsonb(legacy),step["id"]))
    session=next(iter(app.state.sessions.values()))
    session["drafts"].clear()
    session["receipts"].clear()

    reopened=client.get(f"/api/receipts/{original['receipt_id']}").json()
    assert reopened["receipt"]==legacy
    assert reopened["current_claim"]["state"]=="current"
    assert reopened["current_trust"]["state"]=="current"
    assert reopened["current_comparison"]["state"]=="unqualified"
    assert reopened["current_comparison"]["reason_codes"]==["exact_claim_comparison_unqualified"]
    listed=client.get("/api/next-steps").json()["items"][0]
    assert listed["receipt"]==legacy
    assert listed["current_comparison"]["state"]=="unqualified"

    before=app.state.store.get_step(session["owner_id"],step["id"])
    responses=[
        client.post("/api/next-steps/preview",json={"receipt_id":original["receipt_id"]}),
        client.post("/api/next-steps",json=body,headers={"Idempotency-Key":"legacy-new-save"}),
        client.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":step["version"],"state":"done_self_reported","consent":True}),
    ]
    for response in responses:
        assert response.status_code==409,response.text
        assert "claim comparison is not qualified" in response.json()["error"]["message"]
    after=app.state.store.get_step(session["owner_id"],step["id"])
    assert after["receipt"]==before["receipt"]==legacy
    assert after["version"]==before["version"]==step["version"]
    assert after["check_ins"]==before["check_ins"]==[]
    with app.state.store.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM next_steps").fetchone()["n"]==1
        assert con.execute("SELECT count(*) AS n FROM idempotency").fetchone()["n"]==1


def test_unchanged_authored_saved_receipt_survives_loss_of_ephemeral_drafts(client,app):
    original=make_receipt(client)
    step,_,_=save_receipt(client,original)
    session=next(iter(app.state.sessions.values()))
    session["drafts"].clear()
    session["receipts"].clear()
    reopened=client.get(f"/api/receipts/{original['receipt_id']}").json()
    assert reopened["receipt"]==step["receipt"]
    assert reopened["current_comparison"]["state"]=="current"
    response=client.post(f"/api/next-steps/{step['id']}/check-ins",json={"expected_version":step["version"],"state":"done_self_reported","consent":True})
    assert response.status_code==200,response.text
    assert response.json()["saved"] is True
    assert response.json()["step"]["receipt"]==step["receipt"]
