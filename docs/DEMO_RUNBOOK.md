# Current local demonstration

The [submission draft package](submission/README.md) contains paste-ready entry copy, a timed six-minute narration and shot list, an architecture/results companion, the source/sponsor evidence index, and three fictional usability tasks with a blank observations template. These prepared assets are not a completed recording, user study or submission.

## Competition focus — 14 October 2026

The user confirmed Healthcare Challenge 2. The official [submission form](https://docs.google.com/forms/d/e/1FAIpQLScr54QzuASZyUPhYYGwZ3tQ1DpU4_FEAIPsVATDrMv4I4fYbw/viewform), linked from the [event listing](https://luma.com/26fqf3hy) and inspected in signed-in Chrome on 14 October, confirms the cutoff: **Friday, 16 October 2026 at 23:59 GMT+8**. Aim to have the package ready on **15 October**. This is an internal target, not a scheduled automation or a promise that remaining release dependencies are satisfied.

Proposed product pitch: **“Turn confusing health claims into sourced questions and follow-up.”** The intended user is an adult managing a long-term condition or a caregiver preparing a professional discussion. The present implementation demonstrates the workflow with fictional nonclinical evidence; clinical usefulness, clinical evidence approval and reliable live extraction remain unproven.

Priorities, in order:

1. **14 October: complete the remaining entry checks.** Normal Google sign-in, genuine WorkBuddy development review, combined local tests and the four-capture sponsor evidence package are complete. The first submission page shows team/captain/contact and member fields, plus Healthcare track and Case Study 2 options. No answers were entered; later pages require personal inputs and were not inspected. Confirm Singapore-based eligibility, the later required fields and the edit/late-submission policies. The private event code must stay outside the repository, prompts and public footage. No public submission has occurred.
2. **14 October: finish one complete journey.** Keep claim confirmation, a source passage, an explicitly saved professional question, a self-reported follow-up and the source-withdrawal check. Timebox remaining AI work around quotation fidelity, ambiguity and real end-to-end tests; avoid unbounded provider shopping. Do not enable unqualified AI or relabel replay. If a no-cost qualified reviewer is available, seek review of one narrow health example. Otherwise retain fictional examples and state the clinical limitation. Ask three volunteers to perform the fictional task without coaching; record actual completion, time, confusion and corrections, not a claim of health benefit.
3. **15 October: freeze and package.** Rehearse the exact build three times, record a 5–8-minute submission video, prepare the required cover/description/source access and sponsor proof, and check every intended submission link. A public live link is optional and must not introduce spend or delay the core package. Final submission still requires the actual form requirements and authorized publication/submission.

Cut from the remaining scope: voice, extra dashboards, new infrastructure, six-family clinical expansion, decorative design work before the core video, and performance/health claims unsupported by measured results. Miora credits are optional for a cover after the core package is ready.

### Genuine sponsor development review — verified and documented

On 13 October 2026, the user approved the legal terms and normal Google sign-in succeeded in Chrome. The event redemption added **1,000 credits**. The WorkBuddy web UI at `codebuddy.ai/agents` showed the **Free** plan and **1,350 credits** after redemption and again at the ending check at **22:23 Singapore time**. No paid setup was used.

**Hy3**, listed at **0.00×**, was used in an authenticated account conversation to review source excerpts for consent and source-withdrawal behavior. The interaction produced findings and a corrected test proposal. Codex applied the test changes and ran local validation; WorkBuddy did not run local tests. Production logic was unchanged. Five parameter cases were added: denied save with fresh and existing data, denied check-in, and source withdrawal after the API precheck but before the storage transaction for both save and check-in. These ordered checks do not establish general concurrency correctness.

The initial consent selection passed **5 tests, with 8 deselected**. Combined validation of `tests/test_api.py`, `tests/test_api_review.py` and `tests/test_review.py` then passed **44 tests in 51.89 seconds**, with one existing Starlette/httpx deprecation warning. The exact command is recorded in [sponsor verification](planning/SPONSOR_VERIFICATION.md).

The [completed sponsor evidence package](sponsor-evidence/2026-10-13/README.md) contains **four inspected public-safe PNGs** showing the source-withdrawal request, review, transaction-test proposal and corrected closing review of the locally reported validation. They were captured directly with the account sidebar collapsed and contain no visible account email or voucher. The package includes a sanitized test log and hash manifest confirming that the three inspected production source files remained unchanged. The closing review distinguishes consent denial (422) from source-withdrawal conflict (409) and attributes the corrections and local tests to Codex. This records genuine development use, not organizer acceptance, clinical review or runtime AI qualification.

### Six-minute submission story

| Time | Show | Evidence boundary |
| --- | --- | --- |
| 0:00–0:30 | The long-term self-care problem and intended user | State the current prototype and evidence scope. |
| 0:30–2:15 | One claim, confirmation, source passage and scoped receipt | Visibly label live, manual or replay; do not mix their results. |
| 2:15–3:00 | Consent to save a professional question, then a simulated later check-in | Distinguish self-report from verified health improvement. |
| 3:00–3:45 | Withdraw a fictional source and reopen its saved receipt | Show that old information cannot silently remain trusted. |
| 3:45–4:30 | An ambiguous claim or unavailable AI service | Show clear failure and user control, not a fabricated answer. |
| 4:30–5:15 | Architecture, data boundaries and genuine sponsor contribution | Attribute tools and work accurately. |
| 5:15–6:00 | Measured checks, user observations and next validation step | Include failures and actual denominators; no invented testimonials. |

The existing runbook below remains the implemented fictional demonstration. The competition-focused sequence is a rehearsal plan, not evidence it has been recorded or submitted.

## Implemented demonstration steps

Start `scripts/start.ps1` and open `http://127.0.0.1:8765`. The current public-safe route uses fictional, nonclinical examples and clearly labeled replay. This demonstrates the implemented workflow, not clinical accuracy or a completed AI benchmark.

1. Choose **A finding within its scope**. Review the extracted fields and separate intention; explicitly confirm. Explain the scoped result and inspect its exact fictional passage.
2. Use the edit control to change the measured outcome. Confirm the new meaning. Compare the old and new receipts: support for one measured outcome does not automatically establish another. The prior receipt is retained as history.
3. Try **From a narrow finding to a guarantee** and **Incomplete evidence**. Show the limits and the separate action route. Unknown coverage must not be described as falsehood.
4. Preview the proposed question, explicitly consent to save it, then open **My next steps**. Record a self-reported discussion and answer the optional transfer exercise. No real consultation or learning outcome is verified.
5. In the separate synthetic reviewer workspace, use the private local reviewer token to withdraw a fictional source. Reopen an affected saved receipt; current trust blocks new use. Do not represent this as a real publisher correction.
6. Show `docs/BUILD_STATUS.md` and the exact evaluation run. Report observed test counts and failed live-model probes as they are; do not substitute planned targets.

The current health-data route deliberately declines assessment because there is no approved clinical library. An internal urgent routing example demonstrates an engineering branch only; do not call it validated triage. Keep real health details and local credentials out of recordings.

## Historical CLI access attempt

An earlier international CodeBuddy CLI sign-in attempt failed with `getaddrinfo ENOENT www.codebuddy.ai`. Read-only DNS inspection returned `0.0.0.1`; no network or security protection was changed. This historical failure does not describe the successful Chrome sign-in and WorkBuddy review above.

The genuine Tencent CodeBuddy CLI remains installed locally. Its installation is separate from the verified browser-based development use. No paid trial, card entry or automatic renewal is needed for the recorded work.

## Submission boundary

No repository has been published and no hackathon entry has been submitted. Confirm team eligibility, genuine sponsor evidence, clinical review and the agreed evaluation gates before a healthcare submission. The original official-rule references and unresolved details are in `docs/planning/SPONSOR_VERIFICATION.md`. A local engineering demonstration is a useful artifact, but it does not waive the competition's entry requirements or constitute approval for healthcare use.
