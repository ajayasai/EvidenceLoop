import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Capture from './Capture';
import App from './App';
import type { Draft, Session } from './api';

const noop = () => {};
const field = (value: unknown) => ({state: 'stated', value, provenance: []});
const session: Session = {csrf_token: 'test-csrf', mode: 'replay', preferred_mode: 'live', reviewer: false, live_available: true, extraction_available: true, alignment_available: false, extraction_scope: 'local', retention_days: 30, synthetic: true, clinical_review: 'not_performed'};
const draft: Draft = {draft_id: 'test-draft', revision: 1, claim: {propositions: [{proposition_id: 'p-1', intervention: field({surface: 'glow water'}), population: field({surface: 'fictional ferns'}), measured_outcome: field({surface: 'fern growth'}), polarity: field('negated'), relation: field('causal'), speaker: 'quoted_source', speech_act: 'reported_assertion', attribution_text: field('a fictional article')}]}, intent: {}, route: 'education', reason_codes: [], system_status: 'ok', mode: 'live'};
function view(value: Draft, onAssessment = noop) {
  return <Capture session={session} mode="live" setMode={noop} draft={value} setDraft={noop} example={null} onAssessment={onAssessment} onError={noop} onNotice={noop} inputText="A fictional article denies that glow water causes fern growth." onInputText={noop} intent={{action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'rejects'}} setIntent={noop} />;
}
afterEach(() => {vi.unstubAllGlobals(); vi.restoreAllMocks();});

describe('Readable interpretation and honest manual fallback', () => {
  it.each([
    {scope: 'remote' as const, mode: 'live' as const, alignmentAvailable: false, button: 'Read with Google AI', permitted: true},
    {scope: 'remote' as const, mode: 'replay' as const, alignmentAvailable: false, button: 'Review the interpretation', permitted: false},
    {scope: 'local' as const, mode: 'live' as const, alignmentAvailable: false, button: 'Read with local AI', permitted: false},
    {scope: 'local' as const, mode: 'live' as const, alignmentAvailable: true, button: 'Read with local AI', permitted: false},
  ])('discloses $scope $mode destination with alignment $alignmentAvailable and sends remote permission only after an explicit live remote action', async ({scope, mode, alignmentAvailable, button, permitted}) => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(draft), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    render(<Capture session={{...session, extraction_scope: scope, alignment_available: alignmentAvailable}} mode={mode} setMode={noop} draft={null} setDraft={noop} example={null} onAssessment={noop} onError={noop} onNotice={noop} inputText="A public fictional fern claim." onInputText={noop} intent={{action_kind: 'learn', current_care_relationship: 'unrelated', endorsement: 'uncertain'}} setIntent={noop} />);
    expect(fetcher).not.toHaveBeenCalled();
    const contextNote = screen.queryByText(/Library information is shown as context; this reader does not verify the claimed effect/);
    if (mode === 'live' && !alignmentAvailable) expect(contextNote).toBeVisible();
    else expect(contextNote).not.toBeInTheDocument();
    if (mode === 'live' && alignmentAvailable) expect(screen.getByText(/Evidence comes from the available library/)).toBeVisible();
    const send = screen.getByRole('button', {name: button});
    if (permitted) {
      expect(screen.getByText(/Your claim text will be sent to Google AI/)).toBeVisible();
      expect(send).toHaveAccessibleDescription(/without personal or confidential details/);
      expect(send).toHaveAccessibleDescription(/free service may use content to improve its products/);
      expect(screen.getByRole('link', {name: 'Google AI terms'})).toHaveAttribute('href', 'https://ai.google.dev/gemini-api/terms');
    } else expect(screen.queryByText(/Your claim text will be sent to Google AI/)).not.toBeInTheDocument();
    await user.click(send);
    expect(fetcher).toHaveBeenCalledOnce();
    const submitted = JSON.parse((fetcher.mock.calls[0][1] as RequestInit).body as string);
    expect(submitted.mode).toBe(mode);
    if (permitted) expect(submitted.allow_remote_processing).toBe(true);
    else expect(submitted).not.toHaveProperty('allow_remote_processing');
  });

  it('shows a complete AI interpretation without technical inputs, preserves source and negation, and still requires confirmation', async () => {
    const user = userEvent.setup(), fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    render(view(draft));
    expect(screen.getByText('Here is what I understood.')).toBeVisible();
    expect(screen.getByText('The wording denies this relationship.')).toBeVisible();
    expect(screen.getByText('A quoted source: a fictional article')).toBeVisible();
    expect(screen.getByText('Reporting what someone else claims')).toBeVisible();
    expect(screen.getByText(/You disagree with the claim/)).toBeVisible();
    for (const input of screen.queryAllByRole('textbox')) expect(input).not.toBeVisible();
    expect(screen.getByText('Original wording and technical details').closest('details')).not.toHaveAttribute('open');
    const assess = screen.getByRole('button', {name: 'Explore the evidence'});
    expect(assess).toBeDisabled();
    await user.click(screen.getByRole('checkbox'));
    expect(assess).toBeEnabled();
    await user.click(screen.getByRole('button', {name: 'Correct the interpretation'}));
    await user.selectOptions(screen.getByLabelText('Does the wording say this happens?'), 'affirmed');
    expect(screen.getByText(/The wording states this relationship/)).toBeVisible();
    expect(assess).toBeDisabled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('explains an extraction failure and asks only essential questions without inventing unknown details', async () => {
    const user = userEvent.setup();
    const manual: Draft = {...draft, mode: 'manual', system_status: 'model_error', route: 'clarify', claim: {propositions: [{proposition_id: 'p-1'}]}};
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({...manual, revision: 2, confirmed: true}), {status: 200})).mockResolvedValueOnce(new Response(JSON.stringify({receipt_id: 'test-receipt'}), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    render(view(manual));
    expect(screen.getByRole('status')).toHaveTextContent('AI could not produce a reliable interpretation');
    expect(screen.getByRole('status')).toHaveTextContent('It has not been used');
    for (const label of ['What is being discussed?', 'Who or what is the claim about?', 'What result does it describe?', 'How does it describe the connection?', 'Does the wording say this happens?']) expect(screen.getByLabelText(label)).toBeVisible();
    expect(screen.getByLabelText('How certain is the wording?')).not.toBeVisible();
    expect(screen.getByLabelText('A further outcome it claims')).not.toBeVisible();
    const population = screen.getByLabelText('Who or what is the claim about?');
    expect(population).not.toBeRequired();
    expect(population).toHaveValue('');
    fireEvent.change(screen.getByLabelText('What is being discussed?'), {target: {value: 'glow water'}});
    fireEvent.change(screen.getByLabelText('What result does it describe?'), {target: {value: 'fern growth'}});
    await user.selectOptions(screen.getByLabelText('How does it describe the connection?'), 'causal');
    await user.selectOptions(screen.getByLabelText('Does the wording say this happens?'), 'negated');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', {name: 'Explore the evidence'}));
    const submitted = JSON.parse((fetcher.mock.calls[0][1] as RequestInit).body as string);
    expect(submitted.edits).toEqual({intervention: 'glow water', measured_outcome: 'fern growth', relation: 'causal', polarity: 'negated'});
    expect(submitted.edits).not.toHaveProperty('population');
    expect(fetcher.mock.calls[0][0]).toBe('/api/claims/test-draft/confirm');
  });

  it('starts with available AI reading and keeps an explicit replay choice across navigation', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'scrollTo').mockImplementation(noop);
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/session' ? session : []), {status: 200})));
    render(<App />);
    await user.click(await screen.findByText('Reading mode'));
    expect(screen.getByLabelText('How to read this claim')).toHaveValue('live');
    expect(screen.getByText(/Library information is shown as context; this reader does not verify the claimed effect/)).toBeVisible();
    await user.selectOptions(screen.getByLabelText('How to read this claim'), 'replay');
    await user.click(screen.getByRole('button', {name: 'How it works'}));
    await user.click(screen.getByRole('button', {name: 'Check a claim'}));
    await user.click(screen.getByText('Reading mode'));
    expect(screen.getByLabelText('How to read this claim')).toHaveValue('replay');
  });

  it.each([
    ['provider_temporarily_unavailable', 'The AI service is temporarily unavailable.'],
    ['provider_timeout', 'The AI reader took too long.'],
    ['provider_quota_exhausted', 'The AI reading limit has been reached.'],
    ['local_rate_limit_reached', 'The AI reading limit has been reached.'],
  ])('distinguishes %s from a rejected interpretation without making another request', (reason, title) => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    render(view({...draft, mode: 'manual', system_status: 'model_error', reason_codes: [reason],
      claim: {propositions: [{proposition_id: 'p-1'}]}}));
    expect(screen.getByRole('status')).toHaveTextContent(title);
    expect(screen.getByRole('status')).toHaveTextContent('try again later');
    expect(screen.getByRole('status')).not.toHaveTextContent('did not pass the reading checks');
    expect(screen.getByLabelText('What is being discussed?')).toHaveValue('');
    expect(screen.getByRole('button', {name: 'Explore the evidence'})).toBeDisabled();
    expect(fetcher).not.toHaveBeenCalled();
  });
});
