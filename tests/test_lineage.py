"""A revised receipt links history without mutating its old assessment."""
from test_api import app, client, make_receipt
from copy import deepcopy


def test_changed_claim_creates_linked_immutable_receipt(client,app):
    first = make_receipt(client)
    draft = next(iter(next(iter(app.state.sessions.values()))['drafts'].values()))
    response = client.post(f"/api/claims/{draft['draft_id']}/confirm",json={
        'expected_revision':draft['revision'],'edits':{'measured_outcome':'leaf width'}})
    assert response.status_code == 200,response.text
    second = client.post('/api/assessments',json={
        'draft_id':draft['draft_id'],'expected_revision':response.json()['revision']}).json()
    assert second['receipt']['supersedes_receipt_version_id'] == first['receipt']['receipt_version_id']
    assert second['receipt']['parent_attempt_id'] == first['receipt']['attempt_id']
    assert second['receipt']['evidence_status'] == 'not_assessable'
    assert second['receipt']['comparison_basis'] == 'context_only'
    assert second['receipt']['supported_conclusion_ids'] == []
    assert second['receipt']['operator_findings'] == []
    assert second['receipt']['argument_graph'] == {'nodes': [], 'edges': []}
    assert second['receipt']['save_eligible'] is False
    assert second['receipt']['next_step'] is None
    assert client.post('/api/next-steps/preview',json={'receipt_id':second['receipt_id']}).status_code == 409
    original = client.get(f"/api/receipts/{first['receipt_id']}").json()
    assert original['receipt'] == first['receipt']


def test_switching_propositions_shows_all_prior_confirmed_fields(client,app):
    example = client.get('/api/examples').json()[0]
    captured = client.post('/api/claims',json={'text':example['text'],'intent':example['intent']}).json()
    draft = next(iter(app.state.sessions.values()))['drafts'][captured['draft_id']]
    second = deepcopy(draft['claim']['propositions'][0])
    second['proposition_id'] = 'proposition-2'
    draft['claim']['propositions'].append(second)
    path = f"/api/claims/{captured['draft_id']}/confirm"
    first = client.post(path,json={'expected_revision':1,'selected_proposition_id':'proposition-1','edits':{'intervention':'blue water'}}).json()
    next_frame = client.post(path,json={'expected_revision':first['revision'],'selected_proposition_id':'proposition-2','edits':{'measured_outcome':'leaf width'}}).json()
    propositions = next_frame['claim']['propositions']
    assert propositions[0]['intervention']['value']['surface'] == 'blue water'
    assert propositions[1]['measured_outcome']['value']['surface'] == 'leaf width'
    returned = client.post(path,json={'expected_revision':next_frame['revision'],'selected_proposition_id':'proposition-1','edits':{}}).json()
    assert returned['snapshot']['confirmed_proposition']['intervention']['value']['surface'] == 'blue water'
    assert 'confirmed_frames' not in returned


def test_new_confirmation_prevents_saving_previous_preview(client,app):
    first = make_receipt(client)
    preview = client.post('/api/next-steps/preview',json={'receipt_id':first['receipt_id']}).json()
    draft = next(iter(next(iter(app.state.sessions.values()))['drafts'].values()))
    changed = client.post(f"/api/claims/{draft['draft_id']}/confirm",json={
        'expected_revision':draft['revision'],'edits':{'measured_outcome':'leaf width'}})
    assert changed.status_code == 200
    body = {'preview_id':preview['preview_id'],'preview_hash':preview['preview_hash'],'consent':True}
    assert client.post('/api/next-steps',json=body,headers={'Idempotency-Key':'superseded-preview'}).status_code == 409
    assert client.post('/api/next-steps/preview',json={'receipt_id':first['receipt_id']}).status_code == 409
    historical = client.get(f"/api/receipts/{first['receipt_id']}").json()
    assert historical['current_claim']['state'] == 'superseded'
    assert historical['receipt'] == first['receipt']
    assert client.get('/api/next-steps').json()['items'] == []


def test_rejected_incomplete_edit_requires_confirmation_before_any_write(client,app):
    first = make_receipt(client)
    preview = client.post('/api/next-steps/preview',json={'receipt_id':first['receipt_id']}).json()
    draft = next(iter(next(iter(app.state.sessions.values()))['drafts'].values()))
    path = f"/api/claims/{draft['draft_id']}/confirm"
    ledger = draft['ledger']
    rejected = client.post(path,json={'expected_revision':draft['revision'],'intent':{'action_kind':None}})
    assert rejected.status_code == 422
    assert not draft['confirmed']
    assert draft['ledger'] is ledger
    body = {'preview_id':preview['preview_id'],'preview_hash':preview['preview_hash'],'consent':True}
    assert client.post('/api/next-steps',json=body,headers={'Idempotency-Key':'incomplete-edit'}).status_code == 409
    assert client.get(f"/api/receipts/{first['receipt_id']}").json()['current_claim']['state'] == 'needs_confirmation'
    corrected = client.post(path,json={'expected_revision':draft['revision'],'intent':{'action_kind':'learn'}})
    assert corrected.status_code == 200
    assert draft['confirmed']
    assert draft['ledger'] is ledger
