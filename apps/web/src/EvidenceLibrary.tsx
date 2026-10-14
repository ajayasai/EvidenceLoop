import { useEffect, useState } from 'react';
import { ArrowRight, BookOpen, Check, ChevronDown, FilePlus2, Info, LoaderCircle, LockKeyhole, RefreshCw, ShieldCheck, Upload } from 'lucide-react';
import { fieldText, formatDate, humanize, post, request, safeLink } from './api';
import type { LibraryBrief, LibrarySource, ReviewQueue, Session } from './api';

type Props = {session: Session | null; onSession: () => Promise<Session>; onError: (message: string) => void};
const records = (value: unknown) => Array.isArray(value) ? value.filter(item => item && typeof item === 'object') as Record<string, unknown>[] : [];
const strings = (value: unknown) => Array.isArray(value) ? value.filter(item => typeof item === 'string') as string[] : [];

export default function EvidenceLibrary({session, onSession, onError}: Props) {
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [selectedBriefs, setSelectedBriefs] = useState<string[]>([]);
  const [publicationConsent, setPublicationConsent] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const accessible = Boolean(session?.editor || session?.clinical_reviewer);
  const clinical = Boolean(session?.clinical_reviewer && queue?.clinical_enabled && queue.qualified_reviewer_count > 0);
  async function refresh() {
    setLoading(true);
    try {
      const result = await request<ReviewQueue>('/review/queue');
      setQueue(result);
      setSelectedBriefs(current => current.filter(id => result.briefs.some(brief => brief.brief_version_id === id && brief.latest_decision === 'approved')));
      setPublicationConsent(false);
    } finally {setLoading(false);}
  }
  useEffect(() => {
    if (accessible) void refresh().catch(error => onError(error instanceof Error ? error.message : 'The evidence queue could not be loaded.'));
  }, [accessible]);
  async function publish() {
    if (!clinical || !queue || !publicationConsent) return;
    setPublishing(true);
    try {
      await post('/review/publications', {brief_version_ids: selectedBriefs, expected_revision: queue.publication.revision});
      await refresh();
      setNotice('The selected approved brief versions were published. The publication pointer and exact source dependencies were checked by the server.');
    } catch (error) {onError(error instanceof Error ? error.message : 'Publication was not completed.');}
    finally {setPublishing(false);}
  }
  return <section className="workspace" aria-labelledby="library-title">
    <div className="page-intro"><span className="eyebrow"><BookOpen size={13} /> Evidence library</span><h1 id="library-title">Review before release.</h1><p>Import source packets into quarantine, draft anchored conclusions, and keep independent review separate from authoring.</p></div>
    <div className="wide-note"><ShieldCheck size={22} /><div><h3>Import is not approval.</h3><p>An editor can prepare evidence. Clinical decisions and publication require a separately verified, qualified human reviewer. Synthetic trust access grants neither role.</p>{queue && <p>{queue.clinical_enabled && queue.qualified_reviewer_count > 0 ? `${queue.qualified_reviewer_count} qualified reviewer record(s) configured. Access still requires the matching identity.` : 'Clinical approval is unavailable: no enabled qualified reviewer is configured.'}</p>}</div></div>
    <div className="library-access">
      {session?.editor ? <span className="badge neutral"><Check size={12} /> Editor access · quarantine only</span> : <LibraryLogin role="editor" onSession={onSession} onError={onError} />}
      {session?.clinical_reviewer ? <span className="badge"><ShieldCheck size={12} /> Qualified reviewer session</span> : <details className="accordion"><summary><LockKeyhole size={14} /> Qualified reviewer access <ChevronDown size={14} /></summary><div className="accordion-body"><p className="confirmation-intro">Only an independently configured reviewer identity can sign in here. The local demo operator cannot create a qualification by using this form.</p><LibraryLogin role="clinical" onSession={onSession} onError={onError} disabled={Boolean(queue && (!queue.clinical_enabled || !queue.qualified_reviewer_count))} /></div></details>}
    </div>
    {accessible && <>
      <div className="workflow-label" style={{marginTop: 28}}><h3>Quarantine and review queue</h3><button className="text-button" onClick={() => refresh().catch(error => onError(error instanceof Error ? error.message : 'Refresh failed.'))} disabled={loading}><RefreshCw size={13} className={loading ? 'spinner' : ''} /> Refresh queue</button></div>
      {session?.editor && <PacketImporter onImported={async message => {await refresh(); setNotice(message);}} />}
      {loading && !queue && <p className="loading-inline" role="status"><LoaderCircle size={16} className="spinner" /> Loading source versions and review decisions…</p>}
      {queue && <>
        <div className="library-columns">
          <div className="stack"><h3 className="library-column-title">Source packets <span>{queue.sources.length}</span></h3>{queue.sources.length ? queue.sources.map(source => <LibrarySourceCard key={source.source_version_id} source={source} editor={Boolean(session?.editor)} onWithdrawn={async () => {await refresh(); setNotice('Source withdrawn from use. A corrected source version and independent review are required before future release.');}} onError={onError} />) : <div className="card section-card"><p className="confirmation-intro">No source packets have been imported. The editor can add a rights-attested, precisely anchored packet above.</p></div>}</div>
          <div className="stack"><h3 className="library-column-title">Evidence briefs <span>{queue.briefs.length}</span></h3>{queue.briefs.length ? queue.briefs.map(brief => <BriefCard key={brief.brief_version_id} brief={brief} sources={queue.sources} clinical={clinical} onReviewed={async () => {await refresh(); setNotice('The review decision was recorded for the exact brief and source versions.');}} onError={onError} />) : <div className="card section-card"><p className="confirmation-intro">No briefs are awaiting review. Drafts must reference imported source version IDs and exact anchors.</p></div>}</div>
        </div>
        <article className="card section-card" style={{marginTop: 26}}><div className="section-header"><span><ShieldCheck size={17} /></span><div><h3>Publish an approved evidence set</h3><p>Current publication revision {queue.publication.revision}{queue.publication.publication_id ? ' · a publication is active' : ' · nothing has been published'}</p></div></div>
          {!clinical && <p className="review-note"><Info size={15} />Publication requires enabled qualified reviewer access. Imported or editor-authored content cannot publish itself.</p>}
          <div className="publication-choices">{queue.briefs.filter(brief => brief.latest_decision === 'approved').map(brief => <label className="checkbox-row" key={brief.brief_version_id}><input type="checkbox" checked={selectedBriefs.includes(brief.brief_version_id)} disabled={!clinical || publishing} onChange={event => {setSelectedBriefs(current => event.target.checked ? [...current, brief.brief_version_id] : current.filter(id => id !== brief.brief_version_id)); setPublicationConsent(false);}} />{fieldText(brief.payload.name)} <span className="source-meta">· {brief.brief_version_id}</span></label>)}</div>
          {!queue.briefs.some(brief => brief.latest_decision === 'approved') && <p className="confirmation-intro">There are no approved brief versions to select.</p>}
          <label className="checkbox-row"><input type="checkbox" checked={publicationConsent} onChange={event => setPublicationConsent(event.target.checked)} disabled={!clinical || selectedBriefs.length === 0 || selectedBriefs.length > 6 || publishing} />I have inspected these exact approved versions and their dependencies. Publish this set.</label>
          <button className="primary-button" style={{marginTop: 18}} onClick={publish} disabled={!clinical || !publicationConsent || !selectedBriefs.length || selectedBriefs.length > 6 || publishing}>{publishing ? <LoaderCircle size={14} className="spinner" /> : <Upload size={14} />} Publish selected versions</button>
          <p className="checkin-note">Select one to six briefs. Publication rechecks review hashes, independence, validity and current source state in a single transaction.</p>
        </article>
      </>}
    </>}
    {notice && <p className="status-message" role="status">{notice}</p>}
  </section>;
}

function LibraryLogin({role, onSession, onError, disabled = false}: {role: 'editor' | 'clinical'; onSession: Props['onSession']; onError: Props['onError']; disabled?: boolean}) {
  const [token, setToken] = useState('');
  const [identity, setIdentity] = useState('');
  const [busy, setBusy] = useState(false);
  async function login(event: React.FormEvent) {
    event.preventDefault(); setBusy(true);
    try {await post(role === 'editor' ? '/review/editor-login' : '/review/clinical-login', role === 'editor' ? {token} : {token, identity}); setToken(''); await onSession();}
    catch (error) {onError(error instanceof Error ? error.message : 'Access was not granted.');}
    finally {setBusy(false);}
  }
  return <form className={role === 'editor' ? 'card section-card' : ''} onSubmit={login}><h3 style={{fontSize: 15, marginBottom: 17}}>{role === 'editor' ? 'Evidence editor access' : 'Qualified reviewer sign-in'}</h3>{role === 'clinical' && <div className="field" style={{marginBottom: 14}}><label htmlFor="clinical-identity">Registered reviewer identity</label><input id="clinical-identity" value={identity} onChange={event => setIdentity(event.target.value)} disabled={disabled || busy} required autoComplete="username" /></div>}<div className="field"><label htmlFor={`${role}-token`}>{role === 'editor' ? 'Editor token' : 'Qualified reviewer token'}</label><input id={`${role}-token`} value={token} onChange={event => setToken(event.target.value)} type="password" disabled={disabled || busy} required autoComplete="off" /></div><button className="secondary-button" style={{marginTop: 15}} type="submit" disabled={disabled || busy || !token || (role === 'clinical' && !identity)}>{busy ? <LoaderCircle className="spinner" size={13} /> : <LockKeyhole size={13} />} {role === 'editor' ? 'Open quarantine workspace' : 'Authenticate qualified reviewer'}</button>{disabled && <p className="checkin-note">The server has no enabled qualified reviewer configuration.</p>}</form>;
}

export function PacketImporter({onImported}: {onImported: (message: string) => Promise<void>}) {
  const [kind, setKind] = useState<'source' | 'brief'>('source');
  const [text, setText] = useState('');
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function importPacket(event: React.FormEvent) {
    event.preventDefault(); setError('');
    let packet: unknown;
    try {packet = JSON.parse(text); if (!packet || typeof packet !== 'object' || Array.isArray(packet)) throw new Error();}
    catch {setError('Enter one valid JSON object. Nothing was imported.'); return;}
    if (new TextEncoder().encode(JSON.stringify(packet)).length > 32000) {setError('The packet exceeds the 32 KB request limit. Use a bounded, rights-permitted excerpt with exact anchors.'); return;}
    setBusy(true);
    try {await post(kind === 'source' ? '/review/sources' : '/review/briefs', packet); setText(''); setChecked(false); await onImported(kind === 'source' ? 'Source packet imported into quarantine. It is not clinically approved or published.' : 'Evidence brief drafted. Independent review is required before publication.');}
    catch (error) {setError(error instanceof Error ? error.message : 'The packet was not imported.');}
    finally {setBusy(false);}
  }
  async function readFile(file?: File) {
    if (!file) return;
    if (file.size > 32000) {setError('Select a JSON file smaller than 32 KB.'); return;}
    setText(await file.text()); setChecked(false); setError('');
  }
  return <details className="accordion" style={{marginBottom: 24}}><summary><FilePlus2 size={17} /> Import a source packet or draft brief <ChevronDown size={15} /></summary><div className="accordion-body"><form onSubmit={importPacket}>
    <div className="field-row"><div className="field"><label htmlFor="packet-kind">Packet type</label><select id="packet-kind" value={kind} onChange={event => {setKind(event.target.value as 'source' | 'brief'); setChecked(false);}} disabled={busy}><option value="source">Source packet → quarantine</option><option value="brief">Evidence brief → draft review queue</option></select></div><div className="field"><label htmlFor="packet-file">Load a local JSON file <span className="optional">optional</span></label><input id="packet-file" type="file" accept=".json,application/json" disabled={busy} onChange={event => void readFile(event.target.files?.[0])} /></div></div>
    <p className="confirmation-intro">{kind === 'source' ? 'Include source identity, HTTPS citation, storage permission and reference, origin groups, normalized passage text, and exact quote anchors. The citation URL is a reference; the server does not fetch it.' : 'Reference imported source version IDs, supporting and limiting anchors, bounded conclusions and admissions, review due date, quality appraisal and a professional-question template.'} The server validates the full schema and rejects invalid references.</p>
    <div className="field"><label htmlFor="packet-json">{kind === 'source' ? 'Source packet JSON' : 'Evidence brief JSON'}</label><textarea className="packet-input" id="packet-json" value={text} onChange={event => {setText(event.target.value); setChecked(false);}} placeholder="Paste the complete structured packet here." spellCheck={false} disabled={busy} required /></div>
    <details style={{marginTop: 10}}><summary className="text-button">Required structure <ChevronDown size={12} /></summary><pre className="technical-record">{kind === 'source' ? 'source_id, title, publisher, canonical_url, source_type, text,\nlicensing_note, storage_permission, permission_reference,\npermission_attested, snapshot_complete, origin_group_ids,\nanchors: [{anchor_id, start, end, quote, section, original_locator}]' : 'family_id, name, intended_population, intervention_aliases,\nsource_dependencies: [{source_version_id, role}],\nconclusions: [{conclusion_id, statement, outcome_id, effect_direction,\n  anchor_ids, limitations, admissions, operator_mappings}],\nconflicts, review_due_at, quality_appraisal_label,\nquality_appraisal_method, professional_question, scope_note'}</pre><p className="source-meta">Use the exported SourceImport and BriefDraft JSON schemas or the API reference for all enums and nested constraints. Offsets count Unicode code points in NFC text with LF line endings.</p></details>
    <label className="checkbox-row"><input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} disabled={busy} />I have inspected this exact packet and its references. Import it into the unpublished review workspace.</label>
    {error && <p className="preview-error" role="alert">{error}</p>}<button className="primary-button" type="submit" style={{marginTop: 17}} disabled={!text.trim() || !checked || busy}>{busy ? <LoaderCircle size={14} className="spinner" /> : <FilePlus2 size={14} />} {kind === 'source' ? 'Import into quarantine' : 'Create draft brief'} <ArrowRight size={13} /></button>
  </form></div></details>;
}

function LibrarySourceCard({source, editor, onWithdrawn, onError}: {source: LibrarySource; editor: boolean; onWithdrawn: () => Promise<void>; onError: Props['onError']}) {
  const value = source.payload;
  const link = safeLink(value.canonical_url);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  async function withdraw() {
    if (!editor || !Number.isInteger(source.revision)) return;
    setBusy(true);
    try {await post(`/review/sources/${encodeURIComponent(source.source_id)}/withdrawal`, {expected_revision: source.revision, reason}); await onWithdrawn(); setReason('');}
    catch (error) {onError(error instanceof Error ? error.message : 'Source withdrawal was not completed.');}
    finally {setBusy(false);}
  }
  return <details className="accordion"><summary><BookOpen size={16} /><span>{fieldText(value.title) || source.source_id}</span><ChevronDown size={15} /></summary><div className="accordion-body"><span className="badge neutral">Imported source packet · {source.state ? humanize(source.state) : 'not an approval'}</span><p className="source-meta" style={{marginTop: 12}}>{fieldText(value.publisher)} · {fieldText(value.source_date) || 'Date not supplied'}<br />Imported {formatDate(source.imported_at)} by {source.editor_identity}</p>{link && <a className="text-button" href={link} target="_blank" rel="noreferrer">Open citation reference <ArrowRight size={12} /></a>}<h4 style={{marginTop: 16}}>Rights and preserved context</h4><p className="confirmation-intro">{fieldText(value.licensing_note)}</p><p className="source-meta">Storage basis: {humanize(fieldText(value.storage_permission))}<br />Permission reference: {fieldText(value.permission_reference)}<br />Complete snapshot: {value.snapshot_complete === true ? 'Yes' : 'No · excerpt only'}</p>{records(value.anchors).map((anchor, index) => <div className="source-entry" key={fieldText(anchor.anchor_id) || index}><h4>{fieldText(anchor.section)}</h4><blockquote>{fieldText(anchor.quote)}</blockquote><p className="source-meta">{fieldText(anchor.anchor_id)} · {fieldText(anchor.original_locator)} · offsets {fieldText(anchor.start)}–{fieldText(anchor.end)}</p></div>)}<details><summary className="text-button">Packet, context and version hashes <ChevronDown size={12} /></summary><pre className="technical-record">{JSON.stringify(source, null, 2)}</pre></details>{editor && <div className="changed-panel"><h4>Block a source from use</h4><p>Withdrawal only blocks use. It cannot approve or restore evidence. A corrected source version and independent review are required before future release.</p><div className="field"><label htmlFor={`withdrawal-${source.source_version_id}`}>Reason for source withdrawal</label><textarea id={`withdrawal-${source.source_version_id}`} value={reason} onChange={event => setReason(event.target.value)} minLength={10} maxLength={500} disabled={busy || source.state === 'withdrawn'} /></div><button className="secondary-button danger-button" onClick={withdraw} disabled={busy || reason.trim().length < 10 || source.state === 'withdrawn' || !Number.isInteger(source.revision)}>{busy ? <LoaderCircle size={13} className="spinner" /> : <Info size={13} />}Withdraw source from use</button></div>}</div></details>;
}

function BriefCard({brief, sources, clinical, onReviewed, onError}: {brief: LibraryBrief; sources: LibrarySource[]; clinical: boolean; onReviewed: () => Promise<void>; onError: Props['onError']}) {
  const [rationale, setRationale] = useState('');
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const value = brief.payload;
  async function decide(decision: 'approved' | 'changes_requested' | 'rejected') {
    if (!clinical || !checked) return;
    setBusy(true);
    try {await post(`/review/briefs/${encodeURIComponent(brief.brief_version_id)}/decisions`, {decision, rationale, expected_hash: brief.target_hash}); await onReviewed(); setRationale(''); setChecked(false);}
    catch (error) {onError(error instanceof Error ? error.message : 'The review decision was not saved.');}
    finally {setBusy(false);}
  }
  return <article className="card section-card"><span className={`badge ${brief.latest_decision === 'approved' ? '' : 'neutral'}`}>{brief.latest_decision ? humanize(brief.latest_decision) : 'Awaiting independent review'}</span><h3 style={{marginTop: 14, fontSize: 17}}>{fieldText(value.name) || brief.family_id}</h3><p className="confirmation-intro">{fieldText(value.scope_note)}</p><p className="source-meta">Review due: {formatDate(fieldText(value.review_due_at))}<br />Appraisal: {fieldText(value.quality_appraisal_label)}</p><details style={{margin: '13px 0'}}><summary className="text-button">Inspect source dependencies, conclusions and limitations <ChevronDown size={12} /></summary><p className="confirmation-intro">{fieldText(value.quality_appraisal_method)}</p>{records(value.source_dependencies).map((dependency, index) => <div className="finding" key={index} style={{marginBottom: 9}}><h4>{humanize(fieldText(dependency.role))}</h4><p>{fieldText(sources.find(source => source.source_version_id === dependency.source_version_id)?.payload.title) || fieldText(dependency.source_version_id)}</p></div>)}{records(value.conclusions).map((conclusion, index) => <div className="source-entry" key={index}><h4>{fieldText(conclusion.statement)}</h4><p className="source-meta">Outcome: {fieldText(conclusion.outcome_id)} · Effect direction: {humanize(fieldText(conclusion.effect_direction))}</p><ul className="limitations" style={{marginTop: 12}}>{strings(conclusion.limitations).map((limitation, item) => <li key={item}><Info size={12} /><span>{limitation}</span></li>)}</ul><p className="source-meta">Anchors: {strings(conclusion.anchor_ids).join(', ')}</p></div>)}<p className="confirmation-intro">Professional question: {fieldText(value.professional_question)}</p><pre className="technical-record">{JSON.stringify({brief_version_id: brief.brief_version_id, target_hash: brief.target_hash, editor_identity: brief.editor_identity, payload: value}, null, 2)}</pre></details>
    <div className="field"><label htmlFor={`rationale-${brief.brief_version_id}`}>Review rationale</label><textarea id={`rationale-${brief.brief_version_id}`} value={rationale} onChange={event => setRationale(event.target.value)} disabled={!clinical || busy} minLength={20} maxLength={2000} placeholder="Record your independent assessment, caveats and requested changes." /></div><label className="checkbox-row"><input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} disabled={!clinical || busy} />I reviewed this exact brief, its anchored source passages, limitations, rights and scope.</label><div className="reviewer-actions"><button className="primary-button" disabled={!clinical || !checked || rationale.trim().length < 20 || busy} onClick={() => decide('approved')}>Approve exact version</button><button className="secondary-button" disabled={!clinical || !checked || rationale.trim().length < 20 || busy} onClick={() => decide('changes_requested')}>Request changes</button><button className="secondary-button danger-button" disabled={!clinical || !checked || rationale.trim().length < 20 || busy} onClick={() => decide('rejected')}>Reject</button></div>{!clinical && <p className="checkin-note">Read-only: a qualified reviewer session is required for decisions. Editor access does not grant approval authority.</p>}</article>;
}
