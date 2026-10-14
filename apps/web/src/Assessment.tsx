import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowDownRight, ArrowRight, BookOpen, BookmarkPlus, Check, ChevronDown, FileCheck2, GitCompareArrows, Info, Link2, LoaderCircle, LockKeyhole, MessageCircle, RefreshCw, ShieldCheck, X } from 'lucide-react';
import { fieldText, formatDate, humanize, post, request, safeLink } from './api';
import type { Envelope, EvidenceItem, Preview } from './api';

const evidenceLabels: Record<string, string> = {
  supports_within_scope: 'Supported within the studied scope', contradicts_within_scope: 'Contradicted within the studied scope',
  insufficient: 'Not enough evidence to resolve this', conflicting: 'The evidence is in conflict', not_assessable: 'Unable to assess this claim',
};
const applicabilityLabels: Record<string, string> = {scenario_aligned: 'The stated scenario aligns', scope_mismatch: 'The scope differs', unknown: 'Scenario match is unknown'};
const routeLabels: Record<string, string> = {clarify: 'A little more clarity is needed', professional_review_recommended: 'Bring the action question to a professional', urgent_escalation: 'This needs immediate professional attention'};
const operatorNames: Record<string, string> = {L03: 'A measured result → a different outcome', L04: 'An association → a cause', L05: 'One population → another', L07: 'A studied form → a different formulation', L08: 'A limited finding → a guarantee', L09: 'An add-on → a replacement', L11: 'A benefit → a safety claim', L15: 'A mechanism → a benefit'};
function objectText(value: unknown, keys: string[]) {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object') for (const key of keys) {
    const text = fieldText((value as Record<string, unknown>)[key]);
    if (text) return text;
  }
  return '';
}
function conclusionText(item: EvidenceItem) {
  return objectText(item, ['conclusion_text', 'conclusion', 'text', 'statement']);
}

interface Props {
  envelope: Envelope;
  previousEnvelope?: Envelope | null;
  canEditLocal?: boolean;
  onChange: (value: Envelope) => void;
  onRestart: () => void;
  onEdit: () => void;
  onSaved: () => void;
  onError: (message: string) => void;
  retentionDays: number;
}

export default function Assessment({envelope, previousEnvelope, canEditLocal = true, onChange, onRestart, onEdit, onSaved, onError, retentionDays}: Props) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [verified, setVerified] = useState(false);
  const [verificationFailed, setVerificationFailed] = useState(false);
  const receipt = envelope.receipt;
  const synthetic = receipt.synthetic !== false;
  const reviewLabel = synthetic ? 'Synthetic record, no clinical review' : receipt.clinical_review === true ? 'Reviewed evidence; individual output not independently reviewed' : 'Evidence review status unavailable';
  const readingMode = receipt.extraction_mode ?? receipt.mode;
  const readingLabel = readingMode === 'live' ? 'AI-assisted claim reading' : readingMode === 'manual' ? 'User-confirmed manual interpretation' : 'Example replay';
  const alignmentLabel = receipt.alignment_mode === 'extraction_only' ? 'Claim reading only · Exact evidence comparison unavailable' : receipt.alignment_mode === 'live' ? 'AI-assisted evidence alignment' : receipt.alignment_mode === 'deterministic_library_rules' ? 'Library-rule evidence comparison' : '';
  const sourceCurrent = verified && envelope.current_trust.state === 'current';
  const comparisonUnqualified = envelope.current_comparison?.state === 'unqualified';
  const historicalComparison = comparisonUnqualified && receipt.evidence_status !== 'not_assessable';
  const current = sourceCurrent && !historicalComparison;
  const claimSuperseded = envelope.current_claim?.state === 'superseded';
  const claimNeedsConfirmation = envelope.current_claim?.state === 'needs_confirmation';
  const canSave = current && !comparisonUnqualified && !claimSuperseded && !claimNeedsConfirmation && receipt.save_eligible !== false && receipt.system_status === 'ok' && !['clarify', 'urgent_escalation'].includes(receipt.route) && envelope.persistence !== 'saved';
  const proposition = (receipt.snapshot?.confirmed_proposition || receipt.snapshot || {}) as Record<string, unknown>;
  const actionText = objectText(receipt.action_boundary, ['text', 'message', 'explanation', 'route_text', 'instruction']);
  const intervention = fieldText(proposition.intervention) || 'The confirmed proposition';
  const outcome = fieldText(proposition.claimed_clinical_outcome) || fieldText(proposition.measured_outcome);
  const established = receipt.operator_findings?.filter(finding => finding.operator_state === 'established') || [];
  const otherFindings = receipt.operator_findings?.filter(finding => finding.operator_state !== 'established') || [];
  useEffect(() => {
    let active = true;
    setVerified(false);
    setVerificationFailed(false);
    request<Envelope>(`/receipts/${encodeURIComponent(envelope.receipt_id)}`).then(value => {
      if (active) {onChange(value); setVerified(true);}
    }).catch(error => {
      if (active) {setVerificationFailed(true); onError(error instanceof Error ? error.message : 'Current receipt status could not be verified.');}
    });
    return () => {active = false;};
  }, [envelope.receipt_id]);

  async function createPreview() {
    if (!canSave) return;
    setBusy(true); onError('');
    try {setPreview(await post<Preview>('/next-steps/preview', {receipt_id: envelope.receipt_id}));}
    catch (error) {onError(error instanceof Error ? error.message : 'The next-step preview could not be prepared.');}
    finally {setBusy(false);}
  }
  async function refresh() {
    setRefreshing(true);
    setVerified(false);
    try {onChange(await request<Envelope>(`/receipts/${encodeURIComponent(envelope.receipt_id)}`)); setVerified(true); setVerificationFailed(false);}
    catch (error) {setVerificationFailed(true); onError(error instanceof Error ? error.message : 'Current evidence status could not be checked.');}
    finally {setRefreshing(false);}
  }

  return <section className="workspace" aria-labelledby="assessment-title">
    <div className="result-heading"><div><span className="eyebrow"><FileCheck2 size={13} /> Your evidence receipt</span><h1 id="assessment-title">What the evidence allows.</h1><p>A scoped finding, a visible uncertainty, and a question worth asking.</p></div><button className="secondary-button" onClick={onEdit}><GitCompareArrows size={14} /> {canEditLocal ? 'Edit the claim' : 'Start a new assessment'}</button></div>
    {!verified && <div className="review-note" role="status" style={{marginBottom: 20}}><Info size={16} />{verificationFailed ? 'Current receipt status could not be verified. Evidence conclusions stay hidden until the check succeeds.' : 'Checking current source status before displaying the receipt…'}</div>}
    {verified && !sourceCurrent && <div className="route-banner urgent" role="alert" style={{marginBottom: 20}}><AlertTriangle size={20} /><div><h3>This receipt is historical: {humanize(envelope.current_trust.state)}</h3><p>A source dependency is no longer current. Its previous assessment is hidden below until it can be reassessed. This is an evidence-status notice, not a treatment instruction.</p></div></div>}
    {verified && comparisonUnqualified && <div className="route-banner" role="status" style={{marginBottom: 20}}><Info size={20} /><div><h3>This comparison is unavailable under current checks.</h3><p>{envelope.current_comparison?.message}</p></div></div>}
    {verified && claimSuperseded && <div className="route-banner" role="status" style={{marginBottom: 20}}><Info size={20} /><div><h3>This receipt describes an earlier claim version.</h3><p>The confirmed claim has changed since this assessment. This historical receipt remains available for inspection, but it cannot create or save a next step. Assess the latest confirmed claim to continue.</p></div></div>}
    {verified && claimNeedsConfirmation && <div className="route-banner" role="status" style={{marginBottom: 20}}><Info size={20} /><div><h3>Your edited claim needs confirmation.</h3><p>This receipt remains available for inspection. Complete and confirm the edited claim before creating or saving a next step.</p></div></div>}
    {receipt.route !== 'education' && <div className={`route-banner ${receipt.route === 'urgent_escalation' ? 'urgent' : ''}`} style={{marginBottom: 20}}><Info size={20} /><div><h3>{routeLabels[receipt.route] || humanize(receipt.route)}</h3><p>{actionText || 'This workspace cannot resolve the intended action. The limitation needs attention before continuing.'}</p></div></div>}
    <div className="result-grid">
      <div className="stack">
        <article className="card result-summary">
          <span className="small-label">Your confirmed interpretation</span>
          <p className="claim-quote">{intervention}{outcome && <> <ArrowDownRight size={21} strokeWidth={1} /> {outcome}</>}</p>
          <div className="intent-pill"><MessageCircle size={14} /><span>Your intention: {humanize(fieldText(receipt.intent?.action_kind) || 'unknown')}{fieldText(receipt.intent?.current_care_relationship) && ` · ${humanize(fieldText(receipt.intent.current_care_relationship))}`}</span></div>
          {current ? <div className="status-grid">
            <div className="status-item"><span>Evidence relationship</span><strong>{evidenceLabels[receipt.evidence_status] || humanize(receipt.evidence_status)}</strong></div>
            <div className="status-item"><span>Scenario applicability</span><strong>{applicabilityLabels[receipt.applicability] || humanize(receipt.applicability)}</strong></div>
            <div className="status-item"><span>Library coverage</span><strong>{receipt.coverage === 'matched' ? synthetic ? 'A relevant synthetic record was found' : 'A relevant reviewed record was found' : receipt.coverage === 'blocked' ? 'Evidence access is blocked' : 'No eligible record in this library'}</strong></div>
            <div className="status-item"><span>Personal suitability</span><strong>Not individually assessed</strong></div>
            {receipt.effect_direction_by_outcome?.map(effect => <div className="status-item" key={effect.outcome_id}><span>Effect in the {synthetic ? 'synthetic' : 'reviewed'} record · {effect.outcome_id.replaceAll('-', ' ')}</span><strong>{humanize(effect.effect_direction)}</strong></div>)}
          </div> : <p className="review-note">{historicalComparison ? 'The previous finding is historical; the current comparison checks do not qualify it.' : 'Current evidence status prevents displaying the historical finding as current guidance.'}</p>}
          {current && Boolean(receipt.summary) && <p className="confirmation-intro" style={{marginBottom: 0}}>{fieldText(receipt.summary)}</p>}
          {current && receipt.route === 'education' && actionText && <div className="review-note"><Info size={15} /><span>{actionText}</span></div>}
          {receipt.system_status !== 'ok' && <div className="review-note"><Info size={15} />Operational status: {humanize(receipt.system_status)}. This is not a scientific verdict.</div>}
        </article>

        {current && <>
          <article className="card section-card"><div className="section-header"><span><GitCompareArrows size={17} /></span><div><h3>Spot the leap</h3><p>Which connection needs more support?</p></div></div>
            {established.length ? <div className="findings-list">{established.map((finding, index) => <div className="finding" key={finding.operator_id || index}><div className="finding-title"><h4>{finding.title || operatorNames[finding.operator_id || ''] || 'Scope mismatch'}</h4><span className="badge amber">Unsupported transition</span></div><p>{finding.explanation || objectText(finding, ['description', 'text', 'reason'])}</p>{(finding.claim_facet || finding.source_facet) && <div className="finding-pair"><span>Evidence facet<b>{fieldText(finding.source_facet) || 'Not specified'}</b></span><ArrowRight size={17} /><span>Claim facet<b>{fieldText(finding.claim_facet) || 'Not specified'}</b></span></div>}</div>)}</div> : <p className="confirmation-intro">No mismatch was established by the available checks. That does not establish personal suitability or permission to act.</p>}
            {otherFindings.length > 0 && <details style={{marginTop: 17}}><summary className="text-button">Other checks and unknowns <ChevronDown size={12} /></summary><div className="findings-list" style={{marginTop: 12}}>{otherFindings.map((finding, index) => <div className="finding" key={finding.operator_id || index}><div className="finding-title"><h4>{finding.title || operatorNames[finding.operator_id || ""] || finding.operator_id}</h4><span className="badge neutral">{humanize(finding.operator_state)}</span></div><p>{finding.explanation || objectText(finding, ['description', 'text', 'reason'])}</p></div>)}</div></details>}
          </article>

          {receipt.evidence?.length > 0 && <article className="card section-card"><div className="section-header"><span><BookOpen size={17} /></span><div><h3>What the record says</h3><p>Source statements retain their original limits.</p></div></div>{receipt.evidence.map((item, index) => <div className="evidence-assertion" key={item.conclusion_id || index}><p>{conclusionText(item) || 'Inspect the preserved passage and its scope below.'}</p><span className="citation-label"><Link2 size={11} /> {item.title || item.source_id || 'Synthetic evidence record'}</span></div>)}</article>}
          {receipt.limitations?.length > 0 && <article className="card section-card"><div className="section-header"><span><Info size={17} /></span><div><h3>Keep these limits in view</h3><p>Uncertainty belongs beside the finding.</p></div></div><ul className="limitations">{receipt.limitations.map((item, index) => <li key={index}><ArrowRight size={12} /><span>{fieldText(item) || objectText(item, ['message', 'limitation'])}</span></li>)}</ul></article>}

          <details className="accordion"><summary><FileCheck2 size={17} /> Inspect the evidence receipt <ChevronDown size={16} /></summary><div className="accordion-body"><p className="source-meta">Assessment: {formatDate(receipt.assessed_at)} · {readingLabel}{alignmentLabel && <> · <span>{alignmentLabel}</span></>} · {reviewLabel}</p>{receipt.evidence?.length ? receipt.evidence.map((item, index) => <SourceEntry key={item.source_id || index} item={item} />) : <p className="confirmation-intro">No eligible source passage supports an assessment of this claim in the current library.</p>}</div></details>
        </>}

        {previousEnvelope && <ChangeRecord before={previousEnvelope} after={envelope} />}
        <details className="accordion"><summary><GitCompareArrows size={17} /> Technical record <ChevronDown size={16} /></summary><div className="accordion-body"><p className="source-meta">Version IDs preserve traceability. They are not a quality score.</p><pre className="technical-record">{JSON.stringify({receipt_id: envelope.receipt_id, assessed_at: receipt.assessed_at, mode: receipt.mode, current_trust: envelope.current_trust, reason_codes: receipt.reason_codes, reproduction: receipt.reproduction, argument_graph: receipt.argument_graph}, null, 2)}</pre></div></details>
        <button className="text-button" style={{alignSelf: 'flex-start'}} onClick={onRestart}>Start a different claim <ArrowRight size={13} /></button>
      </div>
      <aside className="aside">
        <div className="nextstep-card"><span className="aside-eyebrow"><BookmarkPlus size={13} /> Close the loop</span><h3>Turn uncertainty<br />into a better question.</h3><p>Prepare one question for a thoughtful discussion. Read the exact wording before deciding to save it.</p><button className="primary-button" onClick={createPreview} disabled={!canSave || busy}>{busy ? <LoaderCircle className="spinner" size={14} /> : <MessageCircle size={14} />}{envelope.persistence === 'saved' ? 'This receipt has been saved' : 'Preview my next step'}<ArrowRight size={13} /></button><small>{canSave ? 'Nothing is saved until you give permission.' : envelope.persistence === 'saved' ? 'Find your question in My next steps.' : 'Resolve the current limitation before saving a next step.'}</small></div>
        <div className="trust-note"><h4><ShieldCheck size={14} /> Evidence status, checked again</h4><p>Current state: {humanize(envelope.current_trust.state)}. This refers to the record availability. Evidence review does not establish personal suitability.</p><button className="text-button" onClick={refresh} disabled={refreshing}><RefreshCw size={11} className={refreshing ? 'spinner' : ''} /> Recheck source status</button><p>Last checked {new Date(envelope.current_trust.checked_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}.</p></div>
      </aside>
    </div>
    {preview && canSave && <SaveModal preview={preview} retentionDays={retentionDays} onClose={() => setPreview(null)} onSaved={onSaved} />}
  </section>;
}

function SourceEntry({item}: {item: EvidenceItem}) {
  const link = safeLink(item.canonical_url);
  const anchors = Array.isArray(item.anchors) ? item.anchors as Record<string, unknown>[] : [];
  const passage = item.passage || item.excerpt || objectText(item, ['quote', 'anchor_quote']);
  const synthetic = item.synthetic !== false;
  const review = item.review_record && typeof item.review_record === 'object' ? item.review_record as Record<string, unknown> : {};
  const reviewedAt = item.review_date || fieldText(review.reviewed_at);
  return <article className="source-entry"><span className="badge neutral">{synthetic ? 'Synthetic · no clinical review' : 'Evidence record · review details below'}</span><h4>{item.title || item.source_id || 'Evidence record'}</h4><p className="source-meta">{item.publisher || (synthetic ? 'Synthetic fixture authors' : 'Publisher not supplied')}{item.source_date ? ` · ${fieldText(item.source_date)}` : ''}</p>{passage && <blockquote>{passage}</blockquote>}{anchors.map((anchor, index) => <div key={index}><blockquote>{fieldText(anchor.quote)}</blockquote><p className="source-meta">{fieldText(anchor.section)} · {fieldText(anchor.anchor_id)}</p></div>)}<p>{conclusionText(item)}</p><p className="source-meta">Source version: {item.source_version_id || 'See technical record'}<br />Review: {fieldText(item.review_label) || (synthetic ? 'Synthetic fixture; no qualified clinical review' : 'Inspect the recorded review metadata')}{reviewedAt ? ` · ${formatDate(reviewedAt)}` : ''}</p>{!synthetic && <details style={{marginTop: 10}}><summary className="text-button">Review and quality appraisal <ChevronDown size={12} /></summary><p className="source-meta">{fieldText(item.quality_appraisal)}<br />{fieldText(item.quality_appraisal_method)}</p><pre className="technical-record">{JSON.stringify(review, null, 2)}</pre></details>}{link && <a className="text-button" href={link} target="_blank" rel="noreferrer">Open original source <ArrowRight size={12} /></a>}</article>;
}

export function SaveModal({preview, retentionDays, onClose, onSaved}: {preview: Preview; retentionDays: number; onClose: () => void; onSaved: () => void}) {
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const modalRef = useRef<HTMLDivElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement;
    const dialog = modalRef.current;
    dialog?.querySelector<HTMLElement>('button')?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onClose();
      if (event.key === 'Tab' && dialog) {
        const targets = [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), a[href], [tabindex="0"]')];
        const first = targets[0], last = targets[targets.length - 1];
        if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
      }
    };
    document.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {document.removeEventListener('keydown', onKey); document.body.style.overflow = previousOverflow; previouslyFocused?.focus();};
  }, [onClose, busy]);
  async function save() {
    setBusy(true); setError('');
    try {await post('/next-steps', {preview_id: preview.preview_id, preview_hash: preview.preview_hash, consent}, {'Idempotency-Key': idempotencyKey.current}); onSaved();}
    catch (error) {setError(error instanceof Error ? error.message : 'Saving failed. Your question has not been confirmed as saved.');}
    finally {setBusy(false);}
  }
  return <div className="modal-backdrop"><div className="modal" ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="preview-title"><button className="modal-close" onClick={onClose} disabled={busy} aria-label="Close preview"><X size={18} /></button><span className="eyebrow"><MessageCircle size={13} /> Your next step, in your control</span><h2 id="preview-title">A question to take forward.</h2><p className="modal-intro">Here is the exact question that will be saved with your minimized evidence receipt.</p><div className="question-preview">{preview.text}</div><ul className="save-details"><li><Check size={13} /> Saves this question, the confirmed fields and the receipt.</li><li><LockKeyhole size={13} /> Does not save your original pasted text.</li><li><Info size={13} /> Available in this browser; retained for up to {retentionDays} days of inactivity. You can delete it.</li></ul><label className="checkbox-row"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} disabled={busy} />I agree to save this question and minimized receipt so I can return for a check-in. This does not consent to notifications or analytics.</label>{error && <p className="preview-error" role="alert">{error}</p>}<div className="modal-actions"><button className="secondary-button" onClick={onClose} disabled={busy}>Leave without saving</button><button className="primary-button" onClick={save} disabled={!consent || busy}>{busy ? <LoaderCircle className="spinner" size={14} /> : <BookmarkPlus size={14} />}Save my next step</button></div></div></div>;
}

function ChangeRecord({before, after}: {before: Envelope; after: Envelope}) {
  const oldProposition = (before.receipt.snapshot?.confirmed_proposition || {}) as Record<string, unknown>;
  const newProposition = (after.receipt.snapshot?.confirmed_proposition || {}) as Record<string, unknown>;
  const fields = ['intervention', 'population', 'measured_outcome', 'claimed_clinical_outcome', 'comparator', 'relation', 'polarity', 'certainty', 'generalization', 'formulation'];
  const changes = fields.map(key => ({name: humanize(key), old: fieldText(oldProposition[key]) || 'Unknown', next: fieldText(newProposition[key]) || 'Unknown'})).filter(value => value.old !== value.next);
  for (const key of ['action_kind', 'current_care_relationship', 'endorsement']) {
    const old = fieldText(before.receipt.intent[key]) || 'Unknown', next = fieldText(after.receipt.intent[key]) || 'Unknown';
    if (old !== next) changes.push({name: `Intention: ${humanize(key)}`, old: humanize(old), next: humanize(next)});
  }
  return <article className="card section-card"><div className="section-header"><span><GitCompareArrows size={17} /></span><div><h3>What changed in this revision?</h3><p>Compared with the previous receipt in this session.</p></div></div>{changes.length ? <div className="findings-list">{changes.map(change => <div className="finding" key={change.name}><h4>{change.name}</h4><div className="finding-pair"><span>Before<b>{change.old}</b></span><ArrowRight size={15} /><span>After<b>{change.next}</b></span></div></div>)}</div> : <p className="confirmation-intro">No changes were detected in the compared semantic fields. Formatting-only changes can correctly leave the result unchanged.</p>}<p className="checkin-note">Evidence relationship: {humanize(before.receipt.evidence_status)} → {humanize(after.receipt.evidence_status)}. These are server assessment results; the comparison does not infer that an edit caused a result.</p></article>;
}




