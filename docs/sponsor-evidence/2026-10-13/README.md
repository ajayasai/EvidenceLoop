# Genuine WorkBuddy development use — 13 October 2026

Authenticated Chrome session: [Review EvidenceLoop consent boundary](https://www.codebuddy.ai/agents/task/2110009682776473600). This account conversation is not a public share link.

The event voucher redeemed successfully for **1,000 credits**. WorkBuddy showed the **Free** plan and **1,350 credits** after redemption and again after the development review. The selected **Hy3** model was listed at **0.00×**. No payment method, paid upgrade, subscription or billing setup was used. The voucher and account screenshots remain in ignored local evidence storage, outside this package.

## Actual contribution

WorkBuddy reviewed source excerpts for consent and source-withdrawal behavior, identified missing negative-test coverage, and proposed regression tests. Codex reviewed those proposals, corrected an invented fixture attribute and dictionary-key comparison, extended the save test to fresh/existing owners, and implemented the final tests. An ambiguous status-code statement in the closing response was corrected in the actual conversation.

Five new parameter cases now check:

- Save with consent denied, for both a fresh owner and an owner with an existing saved record: HTTP 422 with the consent-specific error; complete user rows unchanged.
- Check-in with consent denied: HTTP 422; complete user rows, version, consent data and check-in events unchanged.
- Source withdrawal after the API precheck but before save or check-in: real withdrawal committed once, HTTP 409 `version_conflict`, source revision advanced once, and complete user rows unchanged.

The final changes are in [test_api.py](../../../tests/test_api.py) and [test_api_review.py](../../../tests/test_api_review.py). Application logic and AI release gates did not change. These tests exercise fictional engineering fixtures and a deterministic invalidation window; they do not establish clinical validity or general concurrency correctness.

## Verification

Codex executed this local command; WorkBuddy reviewed the reported result and did not execute the tests:

```powershell
.venv\Scripts\python.exe -m pytest -o addopts='' tests/test_api.py tests/test_api_review.py tests/test_review.py -q -rs --tb=short
```

**44 passed, 1 existing dependency deprecation warning, 51.89 seconds.** See [the sanitized test log](validation.txt) and [artifact/source hashes](manifest.json). The two initial source-only prompt hashes and production-source consistency checks are recorded in the manifest. Original prompts and complete captured response text remain in ignored local storage.

## Contemporaneous captures

These four screenshots were captured directly from the real WorkBuddy conversation with the account sidebar collapsed. They contain no visible email address, voucher, API key or actual health data. They have not been reconstructed or altered, and have not been published or submitted.

1. [Source-withdrawal review request](01-source-withdrawal-request.png).
2. [Substantive source-withdrawal review](02-source-withdrawal-review.png).
3. [Proposed transaction-boundary regression](03-transaction-test-proposal.png).
4. [Corrected closing review and locally reported validation](04-local-validation-review.png).

This package records genuine sponsor development use. Organizer acceptance and the remaining competition entry requirements are separate.
