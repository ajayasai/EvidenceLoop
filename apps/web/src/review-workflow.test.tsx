import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import EvidenceLibrary, { PacketImporter } from './EvidenceLibrary';
import type { ReviewQueue, Session } from './api';

const session: Session = {csrf_token: 'csrf', mode: 'replay', reviewer: true, editor: true, clinical_reviewer: false, live_available: false, retention_days: 30};
const queue: ReviewQueue = {sources: [], briefs: [{brief_version_id: 'brief-test-1', family_id: 'family-test', editor_identity: 'local-evidence-editor', target_hash: 'a'.repeat(64), latest_decision: null, payload: {name: 'Test-only unreviewed brief', scope_note: 'A test fixture for interface authorization.', conclusions: [], source_dependencies: []}}], publication: {publication_id: null, revision: 0}, clinical_enabled: false, qualified_reviewer_count: 0};
afterEach(() => vi.unstubAllGlobals());

describe('Evidence quarantine and independent review', () => {
  it('rejects malformed JSON before a write and preserves a packet when server validation fails', async () => {
    const user = userEvent.setup(), imported = vi.fn();
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({error: {message: 'Anchor offsets must identify the exact quote.'}}), {status: 422}));
    vi.stubGlobal('fetch', fetcher);
    render(<PacketImporter onImported={imported} />);
    await user.click(screen.getByText('Import a source packet or draft brief'));
    const json = screen.getByLabelText('Source packet JSON');
    fireEvent.change(json, {target: {value: '{not json'}});
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', {name: 'Import into quarantine'}));
    expect(screen.getByRole('alert')).toHaveTextContent('Enter one valid JSON object. Nothing was imported.');
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.change(json, {target: {value: '{"source_id":"TEST"}'}});
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', {name: 'Import into quarantine'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Anchor offsets must identify the exact quote.');
    expect(json).toHaveValue('{"source_id":"TEST"}');
    expect(imported).not.toHaveBeenCalled();
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it('never grants an editor clinical decision or publication controls', async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(queue), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    render(<EvidenceLibrary session={session} onSession={async () => session} onError={vi.fn()} />);
    expect(await screen.findByText('Test-only unreviewed brief')).toBeVisible();
    expect(screen.getByText(/Clinical approval is unavailable/)).toBeVisible();
    expect(screen.getByRole('button', {name: 'Approve exact version'})).toBeDisabled();
    expect(screen.getByRole('button', {name: 'Request changes'})).toBeDisabled();
    expect(screen.getByRole('button', {name: 'Reject'})).toBeDisabled();
    expect(screen.getByRole('button', {name: 'Publish selected versions'})).toBeDisabled();
    await user.click(screen.getByRole('button', {name: 'Approve exact version'}));
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe('/api/review/queue');
  });

  it('submits the reviewed exact hash only after a qualified session attests and supplies a rationale', async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    const clinicalQueue = {...queue, clinical_enabled: true, qualified_reviewer_count: 1};
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(clinicalQueue), {status: 200})).mockResolvedValueOnce(new Response(JSON.stringify({error: {message: 'The exact review target changed.'}}), {status: 409}));
    vi.stubGlobal('fetch', fetcher);
    render(<EvidenceLibrary session={{...session, clinical_reviewer: true}} onSession={async () => session} onError={onError} />);
    const approve = await screen.findByRole('button', {name: 'Approve exact version'});
    expect(approve).toBeDisabled();
    const rationale = screen.getByLabelText('Review rationale');
    fireEvent.change(rationale, {target: {value: 'Test-only independent rationale for this exact packet.'}});
    expect(approve).toBeDisabled();
    await user.click(screen.getByRole('checkbox', {name: /I reviewed this exact brief/}));
    expect(approve).toBeEnabled();
    await user.click(approve);
    await waitFor(() => expect(onError).toHaveBeenCalledWith('The exact review target changed.'));
    const options = fetcher.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(options.body as string)).toEqual({decision: 'approved', rationale: 'Test-only independent rationale for this exact packet.', expected_hash: 'a'.repeat(64)});
    expect(rationale).toHaveValue('Test-only independent rationale for this exact packet.');
    expect(screen.queryByText('The review decision was recorded')).not.toBeInTheDocument();
  });

  it('withdraws only the inspected source revision and blocks another withdrawal after refresh', async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    const source = {source_version_id: 'source-test-version', source_id: 'source-test', editor_identity: 'local-evidence-editor', content_hash: 'b'.repeat(64), packet_hash: 'c'.repeat(64), imported_at: '2026-09-30T00:00:00Z', state: 'quarantined', revision: 3, payload: {title: 'Test-only source packet', publisher: 'Interface test'}};
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({...queue, sources: [source]}), {status: 200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({error: {message: 'The source revision changed. Refresh before withdrawing.'}}), {status: 409}))
      .mockResolvedValueOnce(new Response(JSON.stringify({state: 'withdrawn'}), {status: 200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({...queue, sources: [{...source, state: 'withdrawn', revision: 4}]}), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    render(<EvidenceLibrary session={session} onSession={async () => session} onError={onError} />);
    await user.click(await screen.findByText('Test-only source packet'));
    const withdraw = screen.getByRole('button', {name: 'Withdraw source from use'});
    expect(withdraw).toBeDisabled();
    const reason = screen.getByLabelText('Reason for source withdrawal');
    fireEvent.change(reason, {target: {value: 'Test-only source context requires correction.'}});
    await user.click(withdraw);
    await waitFor(() => expect(onError).toHaveBeenCalledWith('The source revision changed. Refresh before withdrawing.'));
    expect(reason).toHaveValue('Test-only source context requires correction.');
    expect(screen.queryByText(/Source withdrawn from use\./)).not.toBeInTheDocument();
    expect(fetcher.mock.calls[1][0]).toBe('/api/review/sources/source-test/withdrawal');
    expect(JSON.parse((fetcher.mock.calls[1][1] as RequestInit).body as string)).toEqual({expected_revision: 3, reason: 'Test-only source context requires correction.'});
    await user.click(withdraw);
    expect(await screen.findByText(/Source withdrawn from use\./)).toBeVisible();
    expect(withdraw).toBeDisabled();
    expect(reason).toHaveValue('');
    expect(screen.queryByRole('button', {name: /Restore/})).not.toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(4);
  });
});
