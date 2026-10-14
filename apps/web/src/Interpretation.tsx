import { useState } from 'react';
import { BookOpen, Check, ChevronDown, PencilLine } from 'lucide-react';
import { fieldText } from './api';
import type { Mode, Proposition } from './api';

const essentialFields = [
  ['intervention', 'What is being discussed?', 'For example, an approach, product or activity'],
  ['population', 'Who or what is the claim about?', 'The group named in the wording'],
  ['measured_outcome', 'What result does it describe?', 'The change or outcome named in the wording'],
] as const;
const optionalFields = [
  ['claimed_clinical_outcome', 'A further outcome it claims'],
  ['comparator', 'What it is compared with'],
  ['condition_context', 'Additional condition or context'],
] as const;
const relationLabels: Record<string, string> = {causal: 'a cause-and-effect relationship', associative: 'an association', descriptive: 'a description'};
const certaintyLabels: Record<string, string> = {possible: 'a possibility', probable: 'probable', asserted: 'a definite assertion', guaranteed: 'a guarantee'};

type Props = {proposition?: Proposition; value: (key: string) => string; onEdit: (key: string, value: string) => void; mode: Mode; originalText: string; busy: boolean};

export default function Interpretation({proposition, value, onEdit, mode, originalText, busy}: Props) {
  const [editing, setEditing] = useState(false);
  // Keep initially missing questions on screen while the user answers them.
  const missing = ['intervention', 'population', 'measured_outcome', 'relation', 'polarity'].filter(key => !fieldText(proposition?.[key]));
  const showField = (key: string) => editing || missing.includes(key);
  const input = (key: string, label: string, placeholder = 'Not stated is okay') => <div className="field" key={key}><label htmlFor={`confirm-${key}`}>{label}</label><input id={`confirm-${key}`} value={value(key)} onChange={event => onEdit(key, event.target.value)} maxLength={160} placeholder={placeholder} disabled={busy} /></div>;
  const polarity = value('polarity'), relation = value('relation');
  const source = value('speaker'), speech = value('speech_act');
  const attribution = value('attribution_text');
  const scope = value('population');

  return <>
    <div className="interpretation-card">
      <div className="interpretation-heading"><span className="small-label">{mode === 'live' ? 'AI interpretation · please check' : mode === 'replay' ? 'Example interpretation · please check' : 'Your interpretation'}</span><button className="text-button" type="button" onClick={() => setEditing(current => !current)} disabled={busy} aria-expanded={editing} aria-controls="claim-corrections">{editing ? <Check size={13} /> : <PencilLine size={13} />}{editing ? 'Done correcting' : 'Correct the interpretation'}</button></div>
      <p className="interpretation-sentence">{value('intervention') || value('measured_outcome') ? <>The claim is about <strong>{value('intervention') || 'a subject not yet identified'}</strong> and <strong>{value('measured_outcome') || 'an outcome not yet identified'}</strong>{scope ? <> in <strong>{scope}</strong></> : ' for a group that has not been specified'}.</> : 'The meaning has not been identified yet. Use the questions below to clarify it.'}</p>
      <p className="interpretation-meaning">{relation ? <>It presents {relationLabels[relation] || relation}. </> : 'The kind of connection is not yet clear. '}{polarity === 'negated' ? <strong>The wording denies this relationship.</strong> : polarity === 'affirmed' ? 'The wording states this relationship.' : <strong>Whether the wording states or denies it is not yet clear.</strong>}{value('certainty') && <> It is expressed as {certaintyLabels[value('certainty')] || value('certainty')}.</>}</p>
      <dl className="interpretation-context"><div><dt>Whose words?</dt><dd>{source === 'quoted_source' ? attribution ? `A quoted source: ${attribution}` : 'A quoted source, not automatically your own view' : source === 'user' ? 'Your own statement or question' : 'The speaker has not been identified'}</dd></div><div><dt>How it is presented</dt><dd>{speech === 'question' ? 'A question, not an endorsement' : speech === 'reported_assertion' ? 'Reporting what someone else claims' : speech === 'assertion' ? 'An assertion' : 'Not yet specified'}</dd></div></dl>
      {optionalFields.some(([key]) => value(key)) && <dl className="interpretation-details">{optionalFields.filter(([key]) => value(key)).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{value(key)}</dd></div>)}</dl>}
    </div>

    {(editing || missing.length > 0) && <div className="claim-corrections" id="claim-corrections"><h4>{editing ? 'Correct the meaning' : 'A little more detail is needed'}</h4><p className="confirmation-intro">Use only what the wording says. If a detail is not stated, leave it unknown. We will keep that limit in the assessment.</p><div className="confirmation-grid">
      {essentialFields.filter(([key]) => showField(key)).map(([key, label, placeholder]) => input(key, label, placeholder))}
      {showField('relation') && <div className="field"><label htmlFor="relation">How does it describe the connection?</label><select id="relation" value={value('relation')} onChange={event => onEdit('relation', event.target.value)} disabled={busy}><option value="">Not stated / I cannot tell</option><option value="causal">One thing causes a result</option><option value="associative">Two things are associated</option><option value="descriptive">It describes something</option></select></div>}
      {showField('polarity') && <div className="field"><label htmlFor="polarity">Does the wording say this happens?</label><select id="polarity" value={polarity} onChange={event => onEdit('polarity', event.target.value)} disabled={busy}><option value="">Not stated / I cannot tell</option><option value="affirmed">Yes, it says the relationship happens</option><option value="negated">No, it denies the relationship</option></select></div>}
      {editing && <><div className="field"><label htmlFor="speaker">Whose claim is this?</label><select id="speaker" value={source || 'unknown'} onChange={event => onEdit('speaker', event.target.value)} disabled={busy}><option value="unknown">Not clear</option><option value="quoted_source">A quoted source</option><option value="user">My own statement or question</option></select></div><div className="field"><label htmlFor="speech-act">How is it presented?</label><select id="speech-act" value={speech} onChange={event => onEdit('speech_act', event.target.value)} disabled={busy}><option value="" disabled>Not specified</option><option value="assertion">An assertion</option><option value="question">A question</option><option value="reported_assertion">Reporting someone else's claim</option></select></div></>}
    </div></div>}

    <details className="confirmation-options"><summary>More details <span className="optional">optional</span><ChevronDown size={13} /></summary><p className="confirmation-intro">These can stay unknown. Add or correct them only if they appear in the wording.</p><div className="confirmation-grid">{optionalFields.map(([key, label]) => input(key, label))}<div className="field"><label htmlFor="certainty">How certain is the wording?</label><select id="certainty" value={value('certainty')} onChange={event => onEdit('certainty', event.target.value)} disabled={busy}><option value="">Not stated / I cannot tell</option><option value="possible">It suggests a possibility</option><option value="probable">It says this is probable</option><option value="asserted">It makes a definite assertion</option><option value="guaranteed">It makes a guarantee</option></select></div></div></details>
    <details className="confirmation-options"><summary><BookOpen size={13} /> Original wording and technical details <ChevronDown size={13} /></summary><blockquote className="original-wording">{originalText}</blockquote><p className="source-meta">The structured record below preserves the interpretation and its source references. It is not a scientific conclusion.</p><pre className="technical-record">{JSON.stringify(proposition, null, 2)}</pre></details>
  </>;
}
