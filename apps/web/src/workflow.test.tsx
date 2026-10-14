import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Assessment, { SaveModal } from './Assessment';
import Capture from './Capture';
import Saved from './Saved';
import { setCsrfToken } from './api';
import type { Draft, Envelope } from './api';

const noop = () => {};
const field = (value: unknown) => ({value, state: 'stated', provenance: []});
const envelope: Envelope = {
  receipt_id: 'receipt-1', persistence: 'ephemeral', current_trust: {state: 'current', checked_at: '2026-09-30T10:00:00Z', affected_dependency_ids: []},
  receipt: {receipt_id: 'receipt-1', case_state: 'assessed', route: 'education', coverage: 'matched', evidence_status: 'supports_within_scope', applicability: 'scenario_aligned', system_status: 'ok', reason_codes: [], evidence: [{title: 'Fictional Fern Lab', statement: 'A preserved synthetic finding.'}], operator_findings: [], limitations: [], action_boundary: 'No personal suitability is established.', mode: 'replay', snapshot: {confirmed_proposition: {intervention: field({surface: 'glow water'}), measured_outcome: field({surface: 'fern height'})}}, intent: {action_kind: field('learn')}, assessed_at: '2026-09-30T10:00:00Z'},
};

afterEach(() => vi.unstubAllGlobals());

describe('Explicit save consent and current evidence boundaries', () => {
  it('does not write before consent, keeps preview on rejection, and retries with the same idempotency key', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({error: {message: 'Evidence changed. Reassess before saving.'}}), {status: 409})).mockResolvedValueOnce(new Response(JSON.stringify({id: 'step-1'}), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    setCsrfToken('session-csrf');
    render(<SaveModal preview={{preview_id: 'preview-1', preview_hash: 'a'.repeat(64), text: 'What evidence would justify the action?', expires_at: '2026-09-30T10:10:00Z'}} retentionDays={30} onClose={noop} onSaved={onSaved} />);
    const save = screen.getByRole('button', {name: 'Save my next step'});
    expect(save).toBeDisabled();
    await user.click(save);
    expect(fetcher).not.toHaveBeenCalled();
    await user.click(screen.getByRole('checkbox'));
    await user.click(save);
    expect(await screen.findByRole('alert')).toHaveTextContent('Evidence changed');
    expect(onSaved).not.toHaveBeenCalled();
    expect(screen.getByText('What evidence would justify the action?')).toBeVisible();
    await user.click(save);
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    const first = fetcher.mock.calls[0][1] as RequestInit;
    const second = fetcher.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(first.body as string)).toEqual({preview_id: 'preview-1', preview_hash: 'a'.repeat(64), consent: true});
    expect(new Headers(first.headers).get('X-CSRF-Token')).toBe('session-csrf');
    expect(new Headers(first.headers).get('Idempotency-Key')).toEqual(new Headers(second.headers).get('Idempotency-Key'));
  });

  it('rechecks trust and hides old conclusions when the supporting source was withdrawn', async () => {
    const withdrawn: Envelope = {...envelope, current_trust: {...envelope.current_trust, state: 'withdrawn'}};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(withdrawn), {status: 200})));
    render(<Assessment envelope={withdrawn} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('historical: Withdrawn');
    expect(screen.queryByText('A preserved synthetic finding.')).not.toBeInTheDocument();
    expect(screen.queryByText('Supported within the studied scope')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Preview my next step/})).toBeDisabled();
  });

  it('cannot display a previously current finding when the current-status request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    render(<Assessment envelope={envelope} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    expect(await screen.findByText(/Current receipt status could not be verified/)).toBeVisible();
    expect(screen.queryByText('A preserved synthetic finding.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Preview my next step/})).toBeDisabled();
  });

  it('hides a legacy verdict when comparison eligibility changes without calling its source withdrawn', async () => {
    const restricted: Envelope = {...envelope, current_comparison: {state: 'unqualified', reason_codes: ['exact_claim_comparison_unqualified'], message: 'The saved claim comparison is unavailable. Start a new assessment.'}};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(restricted), {status: 200})));
    render(<Assessment envelope={restricted} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    expect(await screen.findByText('This comparison is unavailable under current checks.')).toBeVisible();
    expect(screen.queryByText('Supported within the studied scope')).not.toBeInTheDocument();
    expect(screen.queryByText('A preserved synthetic finding.')).not.toBeInTheDocument();
    expect(screen.queryByText(/A source dependency is no longer current/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Preview my next step/})).toBeDisabled();
  });

  it('retains explicitly unassessed library context while comparison is unavailable', async () => {
    const context: Envelope = {...envelope, current_comparison: {state: 'unqualified', reason_codes: ['exact_claim_comparison_unqualified'], message: 'An exact comparison is unavailable.'}, receipt: {...envelope.receipt, evidence_status: 'not_assessable', save_eligible: false, summary: 'Library information is context only.'}};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(context), {status: 200})));
    render(<Assessment envelope={context} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    expect(await screen.findByText('Unable to assess this claim')).toBeVisible();
    expect(screen.getByText('Library information is context only.')).toBeVisible();
    expect(screen.getAllByText('A preserved synthetic finding.')[0]).toBeVisible();
    expect(screen.getByRole('button', {name: /Preview my next step/})).toBeDisabled();
  });

  it('disables saved check-ins even with consent when the old comparison no longer qualifies', async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({items: [{id: 'step-legacy', receipt_id: 'receipt-1', question: 'A saved fictional question.', state: 'planned', version: 1, created_at: '2026-10-13T10:00:00Z', current_trust: envelope.current_trust, current_claim: {state: 'current'}, current_comparison: {state: 'unqualified', reason_codes: ['exact_claim_comparison_unqualified'], message: 'The saved claim comparison is unavailable. Start a new assessment.'}}]}), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    render(<Saved onStart={noop} onReceipt={noop} onError={noop} onSessionReset={async () => {}} />);
    expect(await screen.findByText('The saved claim comparison is unavailable. Start a new assessment.')).toBeVisible();
    await user.click(screen.getByLabelText(/Save my check-in as a self-report/));
    const checkIn = screen.getByRole('button', {name: 'I discussed it'});
    expect(checkIn).toBeDisabled();
    await user.click(checkIn);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(screen.queryByText(/The supporting record is/)).not.toBeInTheDocument();
  });

  it.each(['superseded', 'needs_confirmation'] as const)('keeps a %s claim receipt inspectable but cannot preview or save from it', async (state) => {
    const user = userEvent.setup();
    const superseded: Envelope = {...envelope, current_claim: {state}};
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(superseded), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    render(<Assessment envelope={superseded} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    expect(await screen.findByText(state === 'superseded' ? 'This receipt describes an earlier claim version.' : 'Your edited claim needs confirmation.')).toBeVisible();
    expect(screen.getAllByText('A preserved synthetic finding.')[0]).toBeVisible();
    expect(screen.getByText('Supported within the studied scope')).toBeVisible();
    const preview = screen.getByRole('button', {name: /Preview my next step/});
    expect(preview).toBeDisabled();
    await user.click(preview);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe('/api/receipts/receipt-1');
  });

  it('keeps support for a proposition separate from the recorded effect direction', async () => {
    const noEffect: Envelope = {...envelope, receipt: {...envelope.receipt, effect_direction_by_outcome: [{outcome_id: 'next-day-recall', effect_direction: 'no_effect', conclusion_ids: ['synthetic-conclusion']}]}};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(noEffect), {status: 200})));
    render(<Assessment envelope={noEffect} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    expect(await screen.findByText('Supported within the studied scope')).toBeVisible();
    expect(screen.getByText('No effect')).toBeVisible();
    expect(screen.getByText('Not individually assessed')).toBeVisible();
  });

  it('labels an extraction-only receipt without claiming an evidence comparison', async () => {
    const user = userEvent.setup();
    const extractionOnly: Envelope = {...envelope, receipt: {...envelope.receipt,
      mode: 'live', extraction_mode: 'live', alignment_mode: 'extraction_only',
      case_state: 'cannot_assess', coverage: 'blocked', evidence_status: 'not_assessable',
      applicability: 'unknown', evidence: [], save_eligible: false,
    }};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(extractionOnly), {status: 200})));
    render(<Assessment envelope={extractionOnly} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    await user.click(await screen.findByText('Inspect the evidence receipt'));
    expect(screen.getByText('Claim reading only · Exact evidence comparison unavailable')).toBeVisible();
    expect(screen.getByText('AI-assisted claim reading', {exact: false})).toBeVisible();
    expect(screen.queryByText('AI-assisted evidence alignment', {exact: false})).not.toBeInTheDocument();
    expect(screen.queryByText('Library-rule evidence comparison', {exact: false})).not.toBeInTheDocument();
    expect(screen.getByText('Unable to assess this claim')).toBeVisible();
    expect(screen.getByRole('button', {name: /Preview my next step/})).toBeDisabled();
  });

  it.each([
    {mode: 'live', alignment_mode: 'live', reading: 'AI-assisted claim reading', comparison: 'AI-assisted evidence alignment'},
    {mode: 'live', alignment_mode: 'deterministic_library_rules', reading: 'AI-assisted claim reading', comparison: 'Library-rule evidence comparison'},
    {mode: 'replay', alignment_mode: undefined, reading: 'Example replay', comparison: undefined},
    {mode: 'manual', alignment_mode: undefined, reading: 'User-confirmed manual interpretation', comparison: undefined},
  ] as const)('preserves the $mode receipt label with $alignment_mode alignment', async ({mode, alignment_mode, reading, comparison}) => {
    const user = userEvent.setup();
    const labeled: Envelope = {...envelope, receipt: {...envelope.receipt, mode, alignment_mode}};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(labeled), {status: 200})));
    render(<Assessment envelope={labeled} onChange={noop} onRestart={noop} onEdit={noop} onSaved={noop} onError={noop} retentionDays={30} />);
    await user.click(await screen.findByText('Inspect the evidence receipt'));
    expect(screen.getByText(reading, {exact: false})).toBeVisible();
    if (comparison) expect(screen.getByText(comparison, {exact: false})).toBeVisible();
    for (const otherLabel of ['AI-assisted claim reading', 'AI-assisted evidence alignment', 'Library-rule evidence comparison', 'Example replay', 'User-confirmed manual interpretation', 'Claim reading only · Exact evidence comparison unavailable']) {
      if (otherLabel !== reading && otherLabel !== comparison) {
        expect(screen.queryByText(otherLabel, {exact: false})).not.toBeInTheDocument();
      }
    }
  });

  it('requires a fresh confirmation after the user changes the polarity', async () => {
    const user = userEvent.setup();
    const draft: Draft = {draft_id: 'draft-1', revision: 1, claim: {propositions: [{proposition_id: 'p-1', intervention: field({surface: 'glow water'}), population: field({surface: 'fictional Fern Lab'}), measured_outcome: field({surface: 'fern height'}), polarity: field('affirmed'), relation: field('causal')}]}, intent: {}, route: 'education', reason_codes: [], system_status: 'ok', mode: 'replay'};
    render(<Capture session={{csrf_token: 'csrf', mode: 'replay', reviewer: false, live_available: false, retention_days: 30}} mode="replay" setMode={noop} draft={draft} setDraft={noop} example={null} onAssessment={noop} onError={noop} onNotice={noop} inputText="A fictional claim" onInputText={noop} intent={{action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain'}} setIntent={noop} />);
    const assess = screen.getByRole('button', {name: 'Explore the evidence'});
    expect(assess).toBeDisabled();
    await user.click(screen.getByRole('checkbox'));
    expect(assess).toBeEnabled();
    await user.click(screen.getByRole('button', {name: 'Correct the interpretation'}));
    fireEvent.change(screen.getByLabelText('Does the wording say this happens?'), {target: {value: 'negated'}});
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(assess).toBeDisabled();
  });

  it('shows an urgent route immediately and offers no path to assessment', async () => {
    const user = userEvent.setup();
    const clear = vi.fn(), setDraft = vi.fn();
    const draft: Draft = {draft_id: 'urgent-1', revision: 1, claim: {propositions: [{proposition_id: 'p-1'}]}, intent: {}, route: 'urgent_escalation', reason_codes: ['serious_concern'], system_status: 'ok', mode: 'manual'};
    render(<Capture session={null} mode="replay" setMode={noop} draft={draft} setDraft={setDraft} example={null} onAssessment={noop} onError={noop} onNotice={noop} inputText="A serious concern" onInputText={clear} intent={{action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain'}} setIntent={noop} />);
    expect(screen.getByRole('alert')).toHaveTextContent('This workspace cannot assess an urgent concern');
    expect(screen.queryByRole('button', {name: 'Explore the evidence'})).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: 'Clear and return to the start'}));
    expect(clear).toHaveBeenCalledWith('');
    expect(setDraft).toHaveBeenCalledWith(null);
  });

  it('labels an unmatched manual draft without claiming that a model interpreted it', () => {
    const draft: Draft = {draft_id: 'manual-1', revision: 1, claim: {propositions: [{proposition_id: 'p-1'}]}, intent: {}, route: 'clarify', reason_codes: [], system_status: 'ok', mode: 'manual'};
    render(<Capture session={null} mode="replay" setMode={noop} draft={draft} setDraft={noop} example={null} onAssessment={noop} onError={noop} onNotice={noop} inputText="An unfamiliar fictional claim" onInputText={noop} intent={{action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain'}} setIntent={noop} />);
    expect(screen.getByRole('status')).toHaveTextContent('Manual interpretation — no model interpretation is being presented');
    expect(screen.queryByText(/deterministic interpretation/)).not.toBeInTheDocument();
  });
});
