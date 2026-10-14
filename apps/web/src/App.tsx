import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, ArrowRight, BookOpen, Check, ChevronRight, CircleDot, FileCheck2, FlaskConical, GitCompareArrows, Leaf, LockKeyhole, RotateCcw, ShieldCheck, Sparkles, X } from 'lucide-react';
import { loadSession, request } from './api';
import type { Draft, Envelope, Example, Intent, Mode, Session } from './api';
import Capture from './Capture';
import Assessment from './Assessment';
import Saved from './Saved';
import Reviewer from './Reviewer';

type Page = 'check' | 'saved' | 'how' | 'reviewer';

function LoopLogo() {
  return <span className="brand-symbol" aria-hidden="true"><RotateCcw size={24} strokeWidth={1.6} /></span>;
}

export default function App() {
  const [page, setPage] = useState<Page>('check');
  const [session, setSession] = useState<Session | null>(null);
  const [examples, setExamples] = useState<Example[]>([]);
  const [mode, setMode] = useState<Mode>('replay');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [receipt, setReceipt] = useState<Envelope | null>(null);
  const [selectedExample, setSelectedExample] = useState<Example | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [inputText, setInputText] = useState('');
  const [captureIntent, setCaptureIntent] = useState<Intent>({action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain', actor: 'hypothetical'});
  const [previousReceipt, setPreviousReceipt] = useState<Envelope | null>(null);

  const refreshSession = useCallback(async () => {
    const next = await loadSession();
    setSession(next);
    return next;
  }, []);

  useEffect(() => {
    async function start() {
      try {
        const next = await refreshSession();
        setMode(next.preferred_mode || next.mode || 'replay');
        const data = await request<Example[] | {items: Example[]}>('/examples');
        setExamples(Array.isArray(data) ? data : data.items);
      } catch (e) { setError(e instanceof Error ? e.message : 'The workspace could not be opened.'); }
    }
    void start();
  }, [refreshSession]);

  function navigate(next: Page) {
    setPage(next);
    setError('');
    window.scrollTo({top: 0, behavior: 'instant'});
  }
  function restart() {
    setReceipt(null);
    setDraft(null);
    setSelectedExample(null);
    setNotice('');
    setInputText('');
    setPreviousReceipt(null);
    navigate('check');
  }
  function assessed(value: Envelope) {
    setReceipt(value);
    setError('');
    window.scrollTo({top: 0, behavior: 'instant'});
  }

  const isCapture = page === 'check' && !receipt;
  const displayMode = receipt?.receipt.mode || draft?.mode || mode;
  const canEditLocal = Boolean(receipt?.persistence === 'ephemeral' && draft?.snapshot?.version_id && draft.snapshot.version_id === receipt.receipt.snapshot?.version_id);
  const libraryLabel = receipt ? receipt.receipt.synthetic === false && receipt.receipt.clinical_review === true ? 'Reviewed evidence · Personal suitability not assessed' : receipt.receipt.synthetic === false ? 'Evidence review status unavailable' : 'Synthetic demonstration · No clinical review' : session?.library_status === 'under_review' || session?.clinical_review === 'unavailable' ? 'Evidence library under review · Availability is limited' : session?.synthetic === false && session?.clinical_review === 'verified_publication' ? 'Reviewed evidence library · Educational use' : session?.synthetic === true || session?.clinical_review === 'not_performed' ? 'Synthetic demonstration · No clinical review' : 'Checking evidence library status';

  return <>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="shell">
      <header className="header">
        <button className="brand" onClick={() => navigate('check')} aria-label="EvidenceLoop home"><LoopLogo /><span className="brand-name">Evidence<span>Loop</span></span></button>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={`nav-button ${page === 'check' ? 'active' : ''}`} aria-current={page === 'check' ? 'page' : undefined} onClick={() => navigate('check')}>Check a claim</button>
          <button className={`nav-button ${page === 'saved' ? 'active' : ''}`} aria-current={page === 'saved' ? 'page' : undefined} onClick={() => navigate('saved')}>My next steps</button>
          <button className={`nav-button nav-how ${page === 'how' ? 'active' : ''}`} aria-current={page === 'how' ? 'page' : undefined} onClick={() => navigate('how')}>How it works</button>
        </nav>
        <span className="header-tag"><span className="status-dot" /> An evidence-to-action workspace</span>
      </header>
      <div className="demo-strip">
        <span><FlaskConical size={12} /> {libraryLabel}</span>
        <span><CircleDot size={11} /> {displayMode === 'replay' ? 'Example replay' : displayMode === 'manual' ? 'Manual interpretation' : 'AI claim reader'} · Educational use</span>
      </div>

      <main id="main-content">
        {session?.public_demo && <div className="wide-note" role="note"><FlaskConical size={22} /><div><h3>Guided fictional demo · No live AI</h3><p>Choose an included example. Use only fictional details when editing. Saved steps belong to this browser and disappear whenever the free demo sleeps, restarts, or is redeployed. Do not enter personal or health information.</p></div></div>}
        {isCapture && <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <span className="eyebrow"><span className="status-dot" /> Check the claim. Keep the context.</span>
            <h1 id="hero-title">A convincing claim.<br />A <em>clearer</em> next step.</h1>
            <p>Look beyond the headline. Explore what a claim says, what the evidence supports, and the leap in between.</p>
          </div>
          <div className="journey-sketch" aria-label="The evidence-to-action journey: claim, evidence, next step">
            <div className="sketch-title">A little more clarity, one step at a time</div>
            <div className="sketch-nodes">
              <div className="sketch-node"><span className="node-icon"><BookOpen size={21} strokeWidth={1.4} /></span><span>The claim</span></div>
              <ArrowRight className="sketch-arrow" size={22} strokeWidth={1} />
              <div className="sketch-node"><span className="node-icon"><GitCompareArrows size={21} strokeWidth={1.4} /></span><span>The evidence</span></div>
              <ArrowRight className="sketch-arrow" size={22} strokeWidth={1} />
              <div className="sketch-node"><span className="node-icon"><Check size={22} strokeWidth={1.5} /></span><span>Your next step</span></div>
            </div>
            <div className="sketch-caption"><Leaf size={13} /> Understanding first. Decisions with the right support.</div>
          </div>
        </section>}

        {error && <div className="error-banner" role="alert"><AlertCircle size={18} /><div>{error}{!session && <><br /><button className="text-button" onClick={() => window.location.reload()}>Reconnect to the workspace <RotateCcw size={12} /></button></>}</div><button aria-label="Dismiss error" onClick={() => setError('')}><X size={15} /></button></div>}
        <div className="visually-hidden" role="status" aria-live="polite">{notice}</div>

        {isCapture && <section className="workspace" aria-label="Claim workspace">
          <div className="workflow-label"><div className="step-trail" aria-label="Your progress">
            <span className={draft ? 'complete' : 'current'}><span className="step-number">01</span> Capture</span><ChevronRight size={12} />
            <span className={draft ? 'current' : ''}><span className="step-number">02</span> Confirm</span><ChevronRight size={12} />
            <span><span className="step-number">03</span> Understand</span>
          </div><span className="section-kicker">One claim. Thoughtfully examined.</span></div>
          <div className="workspace-grid">
            <Capture session={session} mode={mode} setMode={setMode} draft={draft} setDraft={setDraft} example={selectedExample} onAssessment={assessed} onError={setError} onNotice={setNotice} inputText={inputText} onInputText={setInputText} intent={captureIntent} setIntent={setCaptureIntent} />
            <aside className="aside" aria-label="Examples and scope">
              <div className="aside-card">
                <span className="aside-eyebrow"><Sparkles size={12} /> A place to start</span>
                <h3>Try a fictional example</h3>
                <p>Explore how a small change in a claim can change the questions worth asking.</p>
                <div className="example-list">{examples.slice(0, 4).map((example, index) => <button className="example-button" key={example.id} onClick={() => {setSelectedExample(example); setDraft(null); setError('');}} disabled={!session}>
                  {index % 2 ? <GitCompareArrows size={16} strokeWidth={1.5} /> : <Leaf size={16} strokeWidth={1.5} />}<span>{example.title}</span><ArrowRight size={13} />
                </button>)}</div>
                {examples.length > 4 && <details style={{marginTop: 12}}><summary className="text-button">Explore all examples <ChevronRight size={12} /></summary><div className="example-list" style={{marginTop: 9}}>{examples.slice(4).map(example => <button className="example-button" key={example.id} onClick={() => {setSelectedExample(example); setDraft(null); setError('');}}><BookOpen size={14} /><span>{example.title}</span><ArrowRight size={12} /></button>)}</div></details>}
                {!examples.length && <p className="aside-note">Examples appear when the local workspace is connected.</p>}
                <p className="aside-note">{session?.synthetic === false ? 'These practice examples remain fictional. A reviewed library does not establish personal suitability.' : 'Every example and evidence record in this demonstration is synthetic.'}</p>
              </div>
              <div className="boundary-note"><ShieldCheck size={19} strokeWidth={1.4} /><div><h4>Understanding, with boundaries</h4><p>For educational exploration. This workspace does not diagnose, determine personal suitability, or recommend treatment changes.</p></div></div>
            </aside>
          </div>
          <div className="principles">
            <div className="principle"><FileCheck2 size={19} strokeWidth={1.3} /><div><h4>Evidence you can inspect</h4><p>See the passage, its scope, and the limits behind every assessment.</p></div></div>
            <div className="principle"><GitCompareArrows size={19} strokeWidth={1.3} /><div><h4>Room for uncertainty</h4><p>A missing piece of evidence is a reason to ask, not a reason to guess.</p></div></div>
            <div className="principle"><LockKeyhole size={18} strokeWidth={1.3} /><div><h4>You decide what stays</h4><p>Your input is temporary. Saving a next step is always your choice.</p></div></div>
          </div>
        </section>}

        {page === 'check' && receipt && <Assessment envelope={receipt} previousEnvelope={previousReceipt} canEditLocal={canEditLocal} onChange={setReceipt} onRestart={restart} onEdit={() => {setPreviousReceipt(receipt); setReceipt(null); setSelectedExample(null); if (!canEditLocal) {setDraft(null); setInputText(''); setNotice('The saved receipt does not retain the original input. Enter a new claim to begin a fresh assessment.');}}} onSaved={() => {setNotice('Your next step was saved.'); navigate('saved');}} onError={setError} retentionDays={session?.retention_days ?? 30} />}
        {page === 'saved' && <Saved onStart={restart} onReceipt={(value) => {setReceipt(value); navigate('check');}} onError={setError} onSessionReset={async () => {await refreshSession(); setReceipt(null); setPreviousReceipt(null); setDraft(null); setInputText(''); setSelectedExample(null); setCaptureIntent({action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain', actor: 'hypothetical'}); setNotice('Your saved data was deleted.');}} />}
        {page === 'how' && <HowItWorks onStart={restart} session={session} />}
        {page === 'reviewer' && <Reviewer session={session} onSession={refreshSession} onError={setError} />}
      </main>

      <footer className="footer"><span className="footer-brand"><RotateCcw size={12} /> EvidenceLoop <span>·</span> Clarity before action.</span>{!session?.public_demo && <button className="text-button" onClick={() => navigate('reviewer')}>Reviewer workspace <ArrowRight size={11} /></button>}<span>Built for careful questions,<br className="print-only" /> not clinical decisions.</span></footer>
    </div>
  </>;
}

function HowItWorks({onStart, session}: {onStart: () => void; session: Session | null}) {
  return <section className="workspace">
    <div className="page-intro"><span className="eyebrow">The space between evidence and action</span><h1>Make the reasoning visible.</h1><p>A plausible mechanism, a measured change, and a personal decision are different things. EvidenceLoop helps you inspect the connections.</p></div>
    <div className="how-grid">
      <div className="card how-card"><span className="how-number">01</span><h3>Clarify the claim</h3><p>Enter a fictional claim. Check the interpretation and tell us whether you are simply curious or considering an action. You confirm the meaning before assessment.</p></div>
      <div className="card how-card"><span className="how-number">02</span><h3>Inspect the evidence</h3><p>Compare the precise claim with a bounded evidence record. Spot the leap between what was measured and what is being suggested. See limits and uncertainty alongside support.</p></div>
      <div className="card how-card"><span className="how-number">03</span><h3>Prepare a question</h3><p>Preview a question to discuss with a qualified professional. Choose whether to save it, return for a self-reported check-in, and try a small reasoning exercise.</p></div>
    </div>
    <div className="wide-note"><FlaskConical size={22} /><div><h3>Understand the current evidence mode</h3><p>{session?.synthetic === false && session.clinical_review === 'verified_publication' ? 'The active library contains a verified evidence publication. Evidence review applies to the source brief and its scoped mappings; an individual assessment is not independently reviewed. Practice examples remain fictional.' : session?.clinical_review === 'unavailable' ? 'The current evidence publication cannot be verified. Assessments stay limited until source status is resolved.' : 'The included scenarios, evidence passages and trust rehearsals are synthetic and have no clinical review.'} Replay mode uses deterministic fixtures, not a live AI response. Live mode, when configured, uses the currently eligible bounded library.</p></div></div>
    <div className="wide-note"><LockKeyhole size={22} /><div><h3>Only keep what you choose</h3><p>Unsaved claims are temporary. Saving requires explicit consent and stores a minimized receipt and question, not your original pasted text. You can delete your saved data. This demonstration uses the same browser session to recognize your saved items.</p></div></div>
    <button className="primary-button" onClick={onStart}>Explore a claim <ArrowRight size={15} /></button>
  </section>;
}
