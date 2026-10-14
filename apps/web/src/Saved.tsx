import { useEffect, useState } from 'react';
import { ArrowRight, BookOpen, Check, ChevronDown, Clock3, FileCheck2, Info, LoaderCircle, MessageCircle, RefreshCw, Trash2 } from 'lucide-react';
import { formatDate, humanize, post, request } from './api';
import type { CheckInResponse, Envelope, SavedStep, StepState } from './api';

const stateLabels: Record<StepState, string> = {planned: 'Planned', done_self_reported: 'Done · self-reported', deferred: 'For another time', abandoned: 'No longer planned', needs_revision: 'Needs a fresh look'};
const choices = [{value: 'same', text: 'Yes, support for one outcome automatically carries over.'}, {value: 'different', text: 'No, a different outcome needs its own evidence.'}, {value: 'unknown', text: 'I am not sure.'}] as const;

interface Props {
  onStart: () => void;
  onReceipt: (value: Envelope) => void;
  onError: (message: string) => void;
  onSessionReset: () => Promise<void>;
}

export default function Saved({onStart, onReceipt, onError, onSessionReset}: Props) {
  const [items, setItems] = useState<SavedStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConsent, setDeleteConsent] = useState(false);
  useEffect(() => {
    request<{items: SavedStep[]}>('/next-steps').then(data => setItems(data.items)).catch(error => onError(error instanceof Error ? error.message : 'Saved steps could not be loaded.')).finally(() => setLoading(false));
  }, []);
  async function openReceipt(step: SavedStep) {
    try {onReceipt(await request<Envelope>(`/receipts/${encodeURIComponent(step.receipt_id)}`));}
    catch (error) {onError(error instanceof Error ? error.message : 'The receipt could not be opened.');}
  }
  async function deleteAll() {
    setDeleting(true);
    try {await request('/account/data', {method: 'DELETE'}); await onSessionReset(); setItems([]); setDeleteOpen(false); setDeleteConsent(false);}
    catch (error) {onError(error instanceof Error ? error.message : 'Your data could not be deleted.');}
    finally {setDeleting(false);}
  }
  return <section className="workspace" aria-labelledby="saved-title">
    <div className="page-intro"><span className="eyebrow"><MessageCircle size={13} /> A small step toward clarity</span><h1 id="saved-title">Keep the question in view.</h1><p>Return to a question you chose to save. Record your own follow-through, change your mind, or start again with fresh context.</p></div>
    {loading ? <div className="loading-inline" role="status"><LoaderCircle className="spinner" size={18} />Retrieving your saved questions…</div> : items.length === 0 ? <div className="card empty-state"><div className="empty-icon"><BookmarkIcon /></div><h2>Your next step starts<br />with a good question.</h2><p>You have no saved questions in this browser. Explore a claim, preview a question, and decide whether you want to keep it.</p><button className="primary-button" onClick={onStart}>Check a claim <ArrowRight size={15} /></button></div> : <div className="saved-list">{items.map(item => <StepCard key={item.id} step={item} onChange={updated => setItems(current => current.map(step => step.id === updated.id ? updated : step))} onReceipt={() => openReceipt(item)} onError={onError} onStart={onStart} />)}</div>}
    {!loading && items.length > 0 && <details className="accordion" style={{maxWidth: 850, marginTop: 30}} open={deleteOpen} onToggle={event => setDeleteOpen(event.currentTarget.open)}><summary><Trash2 size={15} /> Manage my saved data <ChevronDown size={15} /></summary><div className="accordion-body"><p className="confirmation-intro">Delete all saved questions, receipts, check-ins and unsaved drafts belonging to this browser identity. This cannot be undone in the workspace.</p><label className="checkbox-row"><input type="checkbox" checked={deleteConsent} onChange={event => setDeleteConsent(event.target.checked)} />I want to delete my EvidenceLoop data.</label><button className="secondary-button danger-button" style={{marginTop: 15}} disabled={!deleteConsent || deleting} onClick={deleteAll}>{deleting ? <LoaderCircle className="spinner" size={13} /> : <Trash2 size={13} />} Delete my data</button></div></details>}
    <p className="checkin-note" style={{marginTop: 23}}>Saved items are recognized by a private browser cookie. Clearing cookies can remove your access to them. Use fictional scenarios; inspect evidence review status on each receipt.</p>
  </section>;
}

function BookmarkIcon() {return <MessageCircle size={25} strokeWidth={1.3} />;}

function StepCard({step, onChange, onReceipt, onError, onStart}: {step: SavedStep; onChange: (step: SavedStep) => void; onReceipt: () => void; onError: (message: string) => void; onStart: () => void}) {
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState(false);
  const [concern, setConcern] = useState('');
  const [result, setResult] = useState<CheckInResponse | null>(null);
  const [choice, setChoice] = useState<'same' | 'different' | 'unknown' | null>(null);
  const claimCurrent = !step.current_claim || step.current_claim.state === 'current';
  const comparisonCurrent = step.current_comparison?.state !== 'unqualified';
  const canCheckIn = consent && !busy && claimCurrent && comparisonCurrent && (!step.current_trust || step.current_trust.state === 'current');
  async function checkIn(state: Exclude<StepState, 'planned'>, reassess = false, exerciseChoice?: string) {
    setBusy(true);
    try {
      const data = await post<CheckInResponse>(`/next-steps/${encodeURIComponent(step.id)}/check-ins`, {expected_version: step.version, state, consent, ...(reassess ? {request_reassessment: true, new_concern_text: concern} : {}), ...(exerciseChoice ? {exercise_choice: exerciseChoice} : {})});
      setResult(data); onChange(data.step); if (reassess) setConcern('');
    } catch (error) {onError(error instanceof Error ? error.message : 'The check-in was not saved.');}
    finally {setBusy(false);}
  }
  return <article className="card saved-card">
    <div className="saved-top"><span className="badge neutral"><Clock3 size={11} />{stateLabels[step.state] || humanize(step.state)}</span><button className="text-button" onClick={onReceipt}><FileCheck2 size={13} /> View receipt</button></div>
    <h2 className="saved-question">{step.question}</h2><p className="saved-date">Saved {formatDate(step.created_at)} · {step.receipt?.synthetic === false ? 'See receipt for evidence review and scope' : 'Synthetic scenario'}</p>
    {step.current_trust && step.current_trust.state !== 'current' && <div className="review-note"><Info size={15} />The supporting record is {humanize(step.current_trust.state).toLowerCase()}. Open the receipt to inspect its current status before proceeding.</div>}
    {!claimCurrent && <div className="review-note"><Info size={15} />The claim has been edited. Confirm and assess the current claim before recording another check-in.</div>}
    {!comparisonCurrent && <div className="review-note"><Info size={15} />{step.current_comparison?.message}</div>}
    <label className="checkbox-row"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />Save my check-in as a self-report, without treating it as a verified outcome.</label>
    <div className="saved-actions"><button className="secondary-button" disabled={!canCheckIn} onClick={() => checkIn('done_self_reported')}><Check size={13} />I discussed it</button><button className="secondary-button" disabled={!canCheckIn} onClick={() => checkIn('deferred')}><Clock3 size={13} />For another time</button><button className="secondary-button" disabled={!canCheckIn} onClick={() => checkIn('abandoned')}>No longer planned</button><button className="text-button" onClick={() => setChanged(!changed)}><RefreshCw size={12} />Something changed</button></div>
    {busy && <p className="loading-inline" role="status"><LoaderCircle className="spinner" size={13} />Checking the current record…</p>}
    {changed && <div className="changed-panel"><h4>A fresh context needs a fresh assessment.</h4><p>Optionally describe a fictional change. This text is temporary and is not saved as a health or symptom record.</p><textarea aria-label="New fictional concern" value={concern} maxLength={2000} onChange={e => setConcern(e.target.value)} placeholder="What changed in the fictional scenario?" /><button className="secondary-button" disabled={!canCheckIn} onClick={() => checkIn('needs_revision', true)}>Review this change <ArrowRight size={13} /></button></div>}
    {result && <>{!choice && <p className="status-message" role="status">{result.feedback}</p>}{result.route !== 'education' && <button className="primary-button" onClick={onStart}>Start a fresh assessment <ArrowRight size={13} /></button>}{result.exercise && <div className="transfer-panel"><span className="eyebrow"><BookOpen size={12} /> Take the reasoning with you</span><h3>One optional thought experiment</h3><p>{result.exercise.question}</p><div className="transfer-options">{choices.map(option => <button className={`transfer-option ${choice === option.value ? 'selected' : ''}`} key={option.value} disabled={!canCheckIn} onClick={() => {setChoice(option.value); void checkIn(step.state === 'planned' ? 'done_self_reported' : step.state, false, option.value);}}>{choice === option.value && <Check size={13} />}{option.text}</button>)}</div>{choice && <p className="transfer-feedback">{result.feedback}</p>}<p className="checkin-note">This exercise explores reasoning. It does not score your trustworthiness or clinical understanding.</p></div>}</>}
  </article>;
}

