import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCheck, ChevronDown, Info, LoaderCircle, LockKeyhole, PencilLine } from 'lucide-react';
import { fieldText, post } from './api';
import type { Draft, Envelope, Example, Intent, Mode, Proposition, Session } from './api';
import Interpretation from './Interpretation';

const defaultIntent: Intent = {action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain', actor: 'hypothetical'};
const actionLabels: Record<string, string> = {learn: 'You are just learning about this claim.', discuss: 'You are considering discussing this with a professional.', start: 'You are considering starting something.', add: 'You are considering adding something to the current approach.', replace: 'You are considering replacing part of the current approach.', stop: 'You are considering stopping the current approach.', delay: 'You are considering delaying a planned step.', change_dose: 'You are considering a dose change.', prevent: 'You are considering prevention.', seek_cure: 'You are looking for a cure.', other: 'Your intended action is not specified.'};
const endorsementLabels: Record<string, string> = {supports: 'You agree with the claim.', rejects: 'You disagree with the claim.', uncertain: 'You are not sure whether you agree.', not_stated: 'You have not stated whether you agree.'};

function IntentFields({intent, onChange}: {intent: Intent; onChange: (value: Intent) => void}) {
  return <div className="field-row">
    <div className="field"><label htmlFor="action-kind">What are you considering?</label><select id="action-kind" value={intent.action_kind} onChange={e => onChange({...intent, action_kind: e.target.value})}>
      <option value="learn">Just learning about the claim</option><option value="discuss">Discussing it with a professional</option><option value="start">Starting something</option><option value="add">Adding something to the current approach</option><option value="replace">Replacing part of the current approach</option><option value="stop">Stopping the current approach</option><option value="delay">Delaying a planned step</option><option value="change_dose">Changing a dose</option><option value="prevent">Considering prevention</option><option value="seek_cure">Looking for a cure</option><option value="other">Something else / prefer not to say</option>
    </select></div>
    <div className="field"><label htmlFor="care-relationship">Relationship to the current approach</label><select id="care-relationship" value={intent.current_care_relationship} onChange={e => onChange({...intent, current_care_relationship: e.target.value})}>
      <option value="unrelated">Not related to a change</option><option value="alongside">Alongside the current approach</option><option value="instead_of">Instead of the current approach</option><option value="">Unknown / prefer not to say</option>
    </select></div>
    {intent.target !== undefined && <div className="field full"><label htmlFor="intent-target">What this action concerns</label><input id="intent-target" value={intent.target} onChange={event => onChange({...intent, target: event.target.value})} maxLength={160} /></div>}
    <div className="field full"><label htmlFor="endorsement">Your view of the claim</label><select id="endorsement" value={intent.endorsement} onChange={e => onChange({...intent, endorsement: e.target.value})}>
      <option value="uncertain">I am not sure</option><option value="supports">I agree with it</option><option value="rejects">I disagree with it</option><option value="not_stated">Prefer not to say</option>
    </select></div>
  </div>;
}

function propositionLabel(proposition: Proposition) {
  const intervention = fieldText(proposition.intervention) || 'Unspecified subject';
  const outcome = fieldText(proposition.claimed_clinical_outcome) || fieldText(proposition.measured_outcome);
  return outcome ? `${intervention} · ${outcome}` : intervention;
}

function readingFailure(reasonCodes: string[]) {
  if (reasonCodes.some(code => ['provider_quota_exhausted', 'free_request_quota_exhausted', 'local_rate_limit_reached', 'gemini_counter_quota_exhausted'].includes(code))) {
    return {title: 'The AI reading limit has been reached.', detail: 'No AI interpretation is available for this attempt. You can return to your wording and try again later, or clarify the essential details below.'};
  }
  if (reasonCodes.some(code => ['provider_temporarily_unavailable', 'provider_network_error', 'token_counter_unavailable'].includes(code))) {
    return {title: 'The AI service is temporarily unavailable.', detail: 'No AI interpretation is available for this attempt. You can return to your wording and try again later, or clarify the essential details below.'};
  }
  if (reasonCodes.some(code => ['provider_timeout', 'token_counter_timeout', 'stage_time_budget_exhausted'].includes(code))) {
    return {title: 'The AI reader took too long.', detail: 'This attempt stopped without an AI interpretation. You can return to your wording and try again later, or clarify the essential details below.'};
  }
  return {title: 'AI could not produce a reliable interpretation.', detail: 'The AI response did not pass the reading checks. It has not been used. You can clarify the essential details below, or return to your wording.'};
}

interface Props {
  session: Session | null;
  mode: Mode;
  setMode: (value: Mode) => void;
  draft: Draft | null;
  setDraft: (value: Draft | null) => void;
  example: Example | null;
  onAssessment: (value: Envelope) => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  inputText: string;
  onInputText: (value: string) => void;
  intent: Intent;
  setIntent: (value: Intent) => void;
}

export default function Capture({session, mode, setMode, draft, setDraft, example, onAssessment, onError, onNotice, inputText: text, onInputText: setText, intent, setIntent}: Props) {
  const [busy, setBusy] = useState('');
  const [selected, setSelected] = useState('');
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState(false);
  const remoteProcessing = mode === 'live' && session?.extraction_scope === 'remote';
  const selectedId = draft?.claim.propositions.some(proposition => proposition.proposition_id === selected) ? selected : draft?.snapshot?.selected_proposition_id || draft?.claim.propositions[0]?.proposition_id || '';
  useEffect(() => {
    if (example) {setText(example.text); setIntent({...defaultIntent, ...example.intent}); setConfirmed(false);}
  }, [example]);
  useEffect(() => {
    if (draft?.claim.propositions.length) {
      setSelected(draft.snapshot?.selected_proposition_id || draft.claim.propositions[0].proposition_id);
      setEdits({});
      setConfirmed(false);
    }
  }, [draft?.draft_id, draft?.revision]);

  async function extract(event: React.FormEvent) {
    event.preventDefault();
    onError('');
    setBusy('Reading the claim');
    try {
      const cleanIntent = {action_kind: intent.action_kind || null, current_care_relationship: intent.current_care_relationship || null, endorsement: intent.endorsement || null, actor: intent.actor || 'hypothetical', target: intent.target || null, timing: intent.timing || null};
      const result = await post<Draft>('/claims', {text, intent: cleanIntent, mode, ...(remoteProcessing ? {allow_remote_processing: true} : {})});
      setDraft(result);
      onNotice(result.route === 'urgent_escalation' ? 'Assessment stopped. This workspace cannot assess an urgent concern; seek appropriate urgent professional help.' : result.route === 'professional_review_recommended' ? 'The proposed action needs professional review. This workspace cannot authorize a treatment change.' : result.mode === 'manual' ? 'Manual confirmation is needed. No model interpretation is being presented.' : 'Interpretation ready. Review the claim and your intended action.');
    } catch (error) {onError(error instanceof Error ? error.message : 'The claim could not be read.');}
    finally {setBusy('');}
  }
  async function assess(event: React.FormEvent) {
    event.preventDefault();
    if (!draft || !confirmed || draft.route === 'urgent_escalation') return;
    onError('');
    setBusy('Confirming your interpretation');
    try {
      const cleanIntent = {action_kind: intent.action_kind || null, current_care_relationship: intent.current_care_relationship || null, endorsement: intent.endorsement || null, actor: intent.actor || 'hypothetical', target: intent.target || null, timing: intent.timing || null};
      const confirmedDraft = await post<Draft>(`/claims/${encodeURIComponent(draft.draft_id)}/confirm`, {expected_revision: draft.revision, selected_proposition_id: selectedId, edits, intent: cleanIntent});
      setDraft(confirmedDraft);
      setBusy('Comparing the evidence and checking its limits');
      const result = await post<Envelope>('/assessments', {draft_id: confirmedDraft.draft_id, expected_revision: confirmedDraft.revision});
      onNotice('Assessment ready. Evidence, uncertainty and action boundaries are shown separately.');
      onAssessment(result);
    } catch (error) {onError(error instanceof Error ? error.message : 'The assessment could not be completed.');}
    finally {setBusy('');}
  }
  const selectedProposition = draft?.snapshot?.selected_proposition_id === selectedId ? draft.snapshot.confirmed_proposition : draft?.claim.propositions.find(p => p.proposition_id === selectedId);
  const editValue = (key: string) => edits[key] ?? fieldText(selectedProposition?.[key]);
  const editField = (key: string, value: string) => {setEdits(current => ({...current, [key]: value})); setConfirmed(false);};
  const readingError = readingFailure(draft?.reason_codes || []);

  if (!draft) return <form className="card main-card" onSubmit={extract}>
    <div className="card-title-row"><div><h3>What would you like to understand?</h3><p>Start with one claim and the action you are considering.</p></div><span className="card-icon"><PencilLine size={18} strokeWidth={1.5} /></span></div>
    <label className="input-label" htmlFor="claim-text">The claim or advice</label>
    <textarea id="claim-text" className="claim-input" placeholder={session?.public_demo ? 'Choose a fictional example from “A place to start”. You can inspect and edit its interpretation in the next step.' : '“A fictional study found taller ferns. Does that mean the same approach helps every plant?”\n\nPaste a fictional claim, or try an example on the right.'} value={text} maxLength={6000} onChange={event => setText(event.target.value)} required disabled={Boolean(busy)} readOnly={session?.public_demo} />
    <div className="input-meta"><span><LockKeyhole size={10} /> Please use fictional details, not personal health information.</span><span>{text.length.toLocaleString()} / 6,000</span></div>
    <div className="input-label">A little context <span className="optional">· your intent is separate from the claim</span></div>
    <IntentFields intent={intent} onChange={setIntent} />
    {(session?.extraction_available ?? session?.live_available) && <details className="mode-details"><summary className="text-button">Reading mode <ChevronDown size={12} /></summary><div className="field"><label htmlFor="mode">How to read this claim</label><select id="mode" value={mode} onChange={e => setMode(e.target.value as Mode)}><option value="live">AI claim reader{session?.extraction_scope === 'local' ? ' · runs on this computer' : ''}</option><option value="replay">Example replay · no AI extraction</option></select></div></details>}
    {mode === 'live' && <p className="reader-note">AI will draft an interpretation for you to check. {session?.alignment_available === false ? 'Library information is shown as context; this reader does not verify the claimed effect.' : 'Evidence comes from the available library.'}</p>}
    {remoteProcessing && <p className="remote-disclosure" id="remote-disclosure">Your claim text will be sent to Google AI. Use fictional or public claims without personal or confidential details. The free service may use content to improve its products. <a href="https://ai.google.dev/gemini-api/terms" target="_blank" rel="noreferrer">Google AI terms <ArrowRight size={11} /></a></p>}
    <div className="form-footer"><span><LockKeyhole size={12} /> Temporary in EvidenceLoop until you save</span><button className="primary-button" type="submit" aria-describedby={remoteProcessing ? 'remote-disclosure' : undefined} disabled={!text.trim() || !session || Boolean(busy)}>{busy ? <><LoaderCircle size={15} className="spinner" /> Reading the claim…</> : <>{remoteProcessing ? 'Read with Google AI' : mode === 'live' && session?.extraction_scope === 'local' ? 'Read with local AI' : 'Review the interpretation'} <ArrowRight size={15} /></>}</button></div>
    {busy && <p className="status-message" role="status">{busy}. No assessment is shown until checks finish.</p>}
  </form>;

  if (draft.route === 'urgent_escalation') return <article className="card main-card">
    <div className="route-banner urgent" role="alert"><AlertTriangle size={22} /><div><h3>This concern needs professional attention.</h3><p>This workspace cannot assess an urgent concern. Seek appropriate urgent professional help using local emergency services where appropriate. It cannot assess severity.</p></div></div>
    <p className="confirmation-intro" style={{marginTop: 22}}>This route stops the claim assessment. No evidence verdict or next step will be generated from this input.</p>
    <button className="secondary-button" onClick={() => {setText(''); setDraft(null);}}><ArrowLeft size={14} /> Clear and return to the start</button>
  </article>;

  return <form className="card main-card" onSubmit={assess}>
    <div className="card-title-row"><div><h3>{draft.mode === 'manual' ? 'Let’s clarify the claim.' : 'Here is what I understood.'}</h3><p>Check the meaning. Correct anything that does not match.</p></div><span className="card-icon"><CheckCheck size={18} strokeWidth={1.5} /></span></div>
    {draft.mode === 'manual' && <div className="manual-notice" role="status"><Info size={18} /><div><h4>{draft.system_status === 'model_error' ? readingError.title : 'This wording does not have an automatic interpretation.'}</h4><p>{draft.system_status === 'model_error' ? readingError.detail : 'Manual interpretation — no model interpretation is being presented. Example replay only recognizes the included examples. You can clarify the essential details below.'} Unknown details can stay unknown.</p></div></div>}
    {draft.route === 'professional_review_recommended' && <div className="route-banner" style={{marginBottom: 20}}><Info size={18} /><div><h3>Discuss the proposed action with a qualified professional.</h3><p>This workspace cannot authorize a personal treatment change. The claim and its intended action need professional review.</p></div></div>}
    {draft.claim.propositions.length > 1 && <fieldset className="proposition-selector"><legend className="input-label">Choose one proposition to assess</legend>{draft.claim.propositions.map(proposition => <label className="proposition-choice" key={proposition.proposition_id}><input type="radio" name="proposition" value={proposition.proposition_id} checked={selected === proposition.proposition_id} onChange={() => {setSelected(proposition.proposition_id); setEdits({}); setConfirmed(false);}} />{propositionLabel(proposition)}</label>)}<p className="aside-note">Other propositions remain unassessed. Safety checks still consider the whole input.</p></fieldset>}
    <Interpretation key={`${draft.draft_id}-${selectedId}`} proposition={selectedProposition} value={editValue} onEdit={editField} mode={draft.mode} originalText={text || fieldText(draft.claim.original_text)} busy={Boolean(busy)} />
    <div className="intent-confirmation"><h4>Your intention, separately</h4><p>{actionLabels[intent.action_kind] || 'Your intended action is not specified.'} {intent.current_care_relationship === 'instead_of' ? 'This would be instead of the current approach. ' : intent.current_care_relationship === 'alongside' ? 'This would be alongside the current approach. ' : ''}{endorsementLabels[intent.endorsement] || 'You have not stated whether you agree.'}</p>{intent.target && <p>What this concerns: {intent.target}</p>}<details className="confirmation-options"><summary>Change my intention or view <ChevronDown size={13} /></summary><fieldset disabled={Boolean(busy)}><IntentFields intent={intent} onChange={value => {setIntent(value); setConfirmed(false);}} /></fieldset></details></div>
    <div className="review-note"><Info size={15} /><span>{draft.mode === 'replay' ? 'This is a deterministic interpretation of the demonstration library. ' : ''}Confirmation records your intended meaning. It does not establish that the claim is true or appropriate for you.</span></div>
    <label className="checkbox-row"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} required />I have checked the selected claim and my intended action. Assess this interpretation.</label>
    <div className="form-footer"><button className="text-button" type="button" onClick={() => setDraft(null)} disabled={Boolean(busy)}><ArrowLeft size={13} /> Back to my wording</button><button className="primary-button" type="submit" disabled={!confirmed || Boolean(busy)}>{busy ? <><LoaderCircle className="spinner" size={15} /> Checking…</> : <>Explore the evidence <ArrowRight size={15} /></>}</button></div>
    {busy && <p className="status-message" role="status">{busy}.</p>}
  </form>;
}
