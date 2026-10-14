import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { Draft, Envelope, Proposition, Session } from './api';

const field = (surface: string) => ({state: 'stated', value: {surface, concept_id: null}, provenance: []});
const initial: Proposition = {proposition_id: 'p-1', intervention: field('glow water'), population: field('fictional Fern Lab'), measured_outcome: field('fern height'), relation: {value: 'causal'}, polarity: {value: 'affirmed'}};
const session: Session = {csrf_token: 'csrf', mode: 'replay', reviewer: false, live_available: false, retention_days: 30, synthetic: true, clinical_review: 'not_performed', library_status: 'current'};
afterEach(() => vi.unstubAllGlobals());

describe('Editing a confirmed local interpretation', () => {
  it('preserves edit A across a receipt remount and submits edit B against the existing draft', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    let draft: Draft = {draft_id: 'draft-1', revision: 1, claim: {propositions: [initial]}, intent: {}, route: 'education', reason_codes: [], system_status: 'ok', mode: 'replay'};
    let confirmed = {...initial};
    let currentReceipt: Envelope;
    const confirmations: Record<string, unknown>[] = [];
    let extractions = 0;
    vi.stubGlobal('fetch', vi.fn(async (url: string, options: RequestInit = {}) => {
      let result: unknown;
      if (url === '/api/session') result = session;
      else if (url === '/api/examples') result = [];
      else if (url === '/api/claims') {extractions++; result = draft;}
      else if (url === '/api/claims/draft-1/confirm') {
        const body = JSON.parse(options.body as string);
        confirmations.push(body);
        for (const [key, value] of Object.entries(body.edits)) confirmed = {...confirmed, [key]: field(String(value))};
        draft = {...draft, revision: draft.revision + 1, confirmed: true, snapshot: {version_id: `v${draft.revision + 1}`, selected_proposition_id: 'p-1', confirmed_proposition: confirmed}};
        result = draft;
      } else if (url === '/api/assessments') {
        currentReceipt = {receipt_id: `receipt-${draft.revision}`, persistence: 'ephemeral', current_trust: {state: 'current', checked_at: '2026-09-30T00:00:00Z', affected_dependency_ids: []}, receipt: {receipt_id: `receipt-${draft.revision}`, case_state: 'assessed', route: 'education', coverage: 'matched', evidence_status: 'supports_within_scope', applicability: 'scenario_aligned', system_status: 'ok', reason_codes: [], evidence: [], operator_findings: [], limitations: [], action_boundary: 'Test-only boundary.', mode: 'replay', snapshot: draft.snapshot!, intent: {action_kind: {value: 'learn'}}, assessed_at: '2026-09-30T00:00:00Z', synthetic: true, clinical_review: false}};
        result = currentReceipt;
      } else if (url.startsWith('/api/receipts/')) result = currentReceipt!;
      else throw new Error(`Unexpected test request ${url}`);
      return new Response(JSON.stringify(result), {status: 200});
    }));
    render(<App />);
    await screen.findByText('Synthetic demonstration · No clinical review');
    fireEvent.change(screen.getByLabelText('The claim or advice'), {target: {value: 'A fictional claim.'}});
    await user.click(screen.getByRole('button', {name: 'Review the interpretation'}));
    await user.click(await screen.findByRole('button', {name: 'Correct the interpretation'}));
    const population = await screen.findByLabelText('Who or what is the claim about?');
    fireEvent.change(population, {target: {value: 'edited population A'}});
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', {name: 'Explore the evidence'}));
    await screen.findByRole('heading', {name: 'What the evidence allows.'});
    await user.click(screen.getByRole('button', {name: 'Edit the claim'}));
    await user.click(screen.getByRole('button', {name: 'Correct the interpretation'}));
    expect(await screen.findByLabelText('Who or what is the claim about?')).toHaveValue('edited population A');
    fireEvent.change(screen.getByLabelText('What result does it describe?'), {target: {value: 'edited outcome B'}});
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', {name: 'Explore the evidence'}));
    await screen.findByRole('heading', {name: 'What the evidence allows.'});
    expect(extractions).toBe(1);
    expect(confirmations[0].edits).toEqual({population: 'edited population A'});
    expect(confirmations[1].edits).toEqual({measured_outcome: 'edited outcome B'});
    expect(confirmations[1].expected_revision).toBe(2);
    expect(confirmations[1].intent).toMatchObject({target: null, timing: null});
    await user.click(screen.getByRole('button', {name: 'Edit the claim'}));
    await user.click(screen.getByRole('button', {name: 'Correct the interpretation'}));
    expect(screen.getByLabelText('Who or what is the claim about?')).toHaveValue('edited population A');
    expect(screen.getByLabelText('What result does it describe?')).toHaveValue('edited outcome B');
  });

  it('identifies an enabled reviewed publication without labelling it clinically unreviewed', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/session' ? {...session, synthetic: false, clinical_review: 'verified_publication', publication_id: 'publication-test'} : []), {status: 200})));
    render(<App />);
    expect(await screen.findByText('Reviewed evidence library · Educational use')).toBeVisible();
    await waitFor(() => expect(screen.queryByText('Synthetic demonstration · No clinical review')).not.toBeInTheDocument());
    expect(screen.getByText(/These practice examples remain fictional/)).toBeVisible();
  });
});
