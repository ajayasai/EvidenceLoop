import { useEffect, useState } from 'react';
import { ArrowRight, ChevronDown, FlaskConical, LoaderCircle, LockKeyhole, ShieldCheck } from 'lucide-react';
import { fieldText, humanize, post, request } from './api';
import type { ReviewSource, Session } from './api';
import EvidenceLibrary from './EvidenceLibrary';

export default function Reviewer({session, onSession, onError}: {session: Session | null; onSession: () => Promise<Session>; onError: (message: string) => void}) {
  const [section, setSection] = useState<'synthetic' | 'library'>('synthetic');
  return <><div className="review-tabs" aria-label="Reviewer sections"><button className={`secondary-button ${section === 'synthetic' ? 'selected' : ''}`} aria-pressed={section === 'synthetic'} onClick={() => setSection('synthetic')}>Synthetic trust rehearsal</button><button className={`secondary-button ${section === 'library' ? 'selected' : ''}`} aria-pressed={section === 'library'} onClick={() => setSection('library')}>Evidence library</button></div>{section === 'synthetic' ? <SyntheticReviewer session={session} onSession={onSession} onError={onError} /> : <EvidenceLibrary session={session} onSession={onSession} onError={onError} />}</>;
}

function SyntheticReviewer({session, onSession, onError}: {session: Session | null; onSession: () => Promise<Session>; onError: (message: string) => void}) {
  const [token, setToken] = useState('');
  const [sources, setSources] = useState<ReviewSource[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  async function refresh() {
    const data = await request<{items: ReviewSource[]}>('/review/sources');
    setSources(data.items);
    setSelectedId(current => current || data.items[0]?.source_id || '');
  }
  useEffect(() => {if (session?.reviewer) void refresh().catch(error => onError(error instanceof Error ? error.message : 'The review queue could not be loaded.'));}, [session?.reviewer]);
  async function login(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); onError('');
    try {await post('/review/login', {token}); setToken(''); await onSession();}
    catch (error) {onError(error instanceof Error ? error.message : 'Reviewer sign-in failed.');}
    finally {setBusy(false);}
  }
  const selected = sources.find(source => source.source_id === selectedId);
  async function decide(decision: 'withdraw' | 'restore') {
    if (!selected) return;
    setBusy(true); onError('');
    try {await post(`/review/sources/${encodeURIComponent(selected.source_id)}/decision`, {expected_revision: selected.revision, decision, reason}); await refresh(); setReason(''); setNotice(`Synthetic source ${decision === 'withdraw' ? 'withdrawn' : 'restored'}. Receipts will recheck its current status.`);}
    catch (error) {onError(error instanceof Error ? error.message : 'The source decision could not be saved.');}
    finally {setBusy(false);}
  }
  return <section className="workspace"><div className="page-intro"><span className="eyebrow"><ShieldCheck size={13} /> Govern the evidence, preserve the record</span><h1>Reviewer workspace.</h1><p>Inspect synthetic source passages and rehearse a change in evidence status. These controls never confer clinical approval.</p></div>
    {!session?.reviewer ? <form className="card main-card" style={{maxWidth: 530}} onSubmit={login}><div className="section-header"><span><LockKeyhole size={17} /></span><div><h3>Operator access</h3><p>Use the local reviewer credential supplied by the operator.</p></div></div><div className="field"><label htmlFor="reviewer-token">Reviewer token</label><input id="reviewer-token" type="password" value={token} onChange={e => setToken(e.target.value)} autoComplete="off" required /></div><p className="checkin-note">The token is sent only to this application and is not kept in browser storage.</p><button className="primary-button" style={{marginTop: 20}} disabled={!token || busy}>{busy ? <LoaderCircle className="spinner" size={14} /> : <LockKeyhole size={14} />} Open the workspace <ArrowRight size={13} /></button></form> : <><div className="wide-note"><FlaskConical size={21} /><div><h3>Synthetic trust-state rehearsal</h3><p>Withdrawals block affected receipts from being presented as current. Restoring a source makes its synthetic record available again; it does not count as qualified evidence review.</p></div></div><div className="reviewer-grid"><div className="reviewer-list">{sources.map(source => <button className={`reviewer-item ${selectedId === source.source_id ? 'selected' : ''}`} key={source.source_id} onClick={() => {setSelectedId(source.source_id); setReason('');}}><strong>{source.title}</strong><span className={`badge ${source.state === 'current' ? 'neutral' : 'amber'}`}>{humanize(source.state || source.trust_state || 'unknown')}</span></button>)}</div>{selected && <article className="card main-card"><span className="badge neutral">Synthetic fixture · revision {selected.revision}</span><h3 style={{marginTop: 17}}>{selected.title}</h3><p className="source-meta" style={{marginTop: 10}}>{fieldText(selected.publisher)} · {fieldText(selected.source_date)}</p><blockquote style={{margin: '23px 0', padding: '15px 18px', borderLeft: '2px solid #98ae8b', background: '#f3f5ec', fontSize: 13, lineHeight: 1.8}}>{fieldText(selected.text)}</blockquote><details><summary className="text-button">Inspect anchors and source version <ChevronDown size={13} /></summary><pre className="technical-record">{JSON.stringify(selected, null, 2)}</pre></details><div className="field" style={{marginTop: 23}}><label htmlFor="decision-reason">Reason for this status decision</label><textarea id="decision-reason" value={reason} onChange={e => setReason(e.target.value)} maxLength={500} placeholder="Describe the synthetic review event and its reason." /></div><div className="reviewer-actions"><button className="secondary-button danger-button" disabled={reason.trim().length < 3 || busy || selected.state === 'withdrawn'} onClick={() => decide('withdraw')}>Withdraw synthetic source</button><button className="primary-button" disabled={reason.trim().length < 3 || busy || selected.state === 'current'} onClick={() => decide('restore')}>Restore synthetic source</button></div>{notice && <p className="status-message" role="status">{notice}</p>}</article>}</div></>}
  </section>;
}

