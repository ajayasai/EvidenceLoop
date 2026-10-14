import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';

afterEach(() => vi.unstubAllGlobals());

it('labels the public replay and reset policy, hides reviewer access, and accepts catalog selection', async () => {
  const example = {id:'fictional-fern', title:'Fictional fern study', text:'Glow water made fictional ferns taller.',
    intent:{action_kind:'learn',current_care_relationship:'unrelated',endorsement:'uncertain',actor:'hypothetical'}};
  vi.stubGlobal('fetch', vi.fn(async (path: string) => new Response(JSON.stringify(path.endsWith('/session')
    ? {csrf_token:'fictional-csrf', mode:'replay',preferred_mode:'replay',public_demo:true,storage_resets_on_restart:true,
        synthetic:true,clinical_review:'not_performed',retention_days:30,reviewer:false,live_available:false,extraction_available:false}
    : [example]), {status:200})));
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByText('Guided fictional demo · No live AI')).toBeVisible();
  expect(screen.getByText(/disappear whenever the free demo sleeps, restarts, or is redeployed/)).toBeVisible();
  expect(screen.queryByRole('button', {name:/Reviewer workspace/})).not.toBeInTheDocument();
  const input = screen.getByRole('textbox', {name:'The claim or advice'});
  expect(input).toHaveAttribute('readonly');
  await user.click(await screen.findByRole('button', {name:example.title}));
  expect(input).toHaveValue(example.text);
  expect(screen.getByRole('button', {name:'Review the interpretation'})).toBeEnabled();
  expect(screen.queryByText('Reading mode')).not.toBeInTheDocument();
});
