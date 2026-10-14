# EvidenceLoop

EvidenceLoop separates a claim, its supporting evidence and the action someone is considering. The local application takes a claim through explicit confirmation, a bounded evidence receipt, a saved question and a later self-reported check-in.

**The local engineering build is runnable; live AI is disabled and no candidate is qualified.** The working library consists of clearly fictional, nonclinical mechanism examples. Clinical evidence and live-model release gates remain pending; no clinical validation is claimed. The strict additional-spending budget is zero.

## Run on this Windows computer

From the project directory, run `scripts/start.ps1`, then open http://127.0.0.1:8765. It uses the project Python environment, local PostgreSQL on loopback port 15432 and the built React interface. PostgreSQL is a private project process, not a system service. Stop the API with Ctrl+C; `scripts/stop_database.ps1` stops the project database.

If setting up a new checkout:

1. Create `.venv` using Python 3.12 or newer and install `requirements.lock.txt`.
2. Run `.venv/Scripts/python.exe scripts/bootstrap_db.py`. The Windows helper downloads the official EDB PostgreSQL archive, initializes a loopback-only database, creates a non-owner application role and writes private configuration to ignored `.env` and `.runtime` files.
3. In `apps/web`, run `npm ci` and `npm run build` using a compatible Node runtime.
4. Run `scripts/start.ps1`.

On other operating systems, use an existing PostgreSQL instance and set separate `DATABASE_ADMIN_URL` and unprivileged `DATABASE_URL`. Run `python scripts/migrate_db.py` to apply both operational and review schemas. Use `--create-role` only if the runtime role does not exist, and `--schema NAME --create-schema` only for a new named schema. A custom schema also needs a matching `search_path` in the runtime connection URL. Start `python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8765 --no-access-log`. The Windows bootstrap binary cannot run on Linux/macOS.

## What the current application does

- Keeps raw claims and extraction spans in expiring server memory; confirmation does not save a case.
- Presents a plain-language interpretation with attribution, negation and separate intent. Corrections are available on demand; optional fields and technical details stay collapsed. Unknown details remain unknown, and insufficient context can still prevent assessment.
- Renders bounded, versioned evidence and reasoning distinctions from the installed synthetic library.
- Saves only the selected normalized claim, minimized provenance, receipt, approved question and explicit consent.
- Uses PostgreSQL transactions, owner-bound cookies, CSRF checks, idempotency keys and optimistic versions.
- Rechecks evidence trust on display, save and check-in. Withdrawing a source prevents old receipts from authorizing new actions.
- Provides a clearly separate synthetic reviewer workspace, self-report check-ins, transfer exercise and deletion.
- Provides source quarantine, independent reviewer authorization, immutable review decisions, publication and operational withdrawal for a future qualified clinical library.

Replay and manual modes are explicitly identified. A bounded Gemini integration, native token counter and local ONNX inference server are implemented. A separate unpaid Google project and private local key were verified on 13 October 2026, but the tested models did not qualify. Gemini 3.1 and 3.5 Flash-Lite failed semantic checks; stronger Flash and Gemma probes encountered service errors, timeouts or unresolved semantic errors. The adapter now includes one bounded transient recovery and an optional rolling request cap. See the [dated AI verification report](docs/AI_EXTRACTION_VERIFICATION_20261013.md) for individual results. Neither extraction nor alignment is enabled.

The comparison guard permits a support/contradiction assessment and saved question only for an unchanged authored fictional replay. It checks the original input hash and confirmed semantic fields; changing only the separate intention remains allowed. Generic manual/live claims and semantically edited replays can show trusted library context, but receive no effect judgment, claim-support graph, save permission or next step. Enabling AI alignment cannot bypass this restriction: the current claim schema does not represent an exact signed effect. Current eligibility is rechecked when older saved receipts are reopened or used, without rewriting their historical contents.

On 14 October, free-project billing was rechecked as disabled. Prompt and bounded recovery improvements were implemented, including an opt-in thirty-second extraction deadline and an explicit-length regeneration within the existing token/dispatch caps. The final low-reasoning trial completed all twelve known cases in at most 2.468 seconds, but made material attribution and field-assignment errors. No candidate qualified and the fresh evaluation sets remain unrun. See the [14 October report](docs/AI_EXTRACTION_VERIFICATION_20261014.md); working transport is not reliable interpretation.

Historical local lean-format diagnostics from 30 September recorded **28 attempts and 4 exact matches** across repeated tuning cases. The tested local model is unsuitable for release. Those diagnostics and earlier failures remain in [evals/development](evals/development/lean-runtime-summary.json). The [original extraction benchmark](evals/extraction/README.md) supplies 12 development and 12 regression cases. The subsequently tested [October partition](evals/extraction-next-20261013/manifest.json) is also regression-only because its failures were inspected. A new [final 12-case partition](evals/extraction-final-20261013/manifest.json) is frozen and **has not been run against a model**. These are developer-authored fictional engineering checks, not independently reviewed clinical validation.

## Free Google AI status

The existing unpaid project and private local key are already set up; another key or a paid plan is not required to explain or address these results. The blockers are failed model qualification and observed service failures. Keep live mode disabled. [Setup observations](docs/FREE_AI_SETUP_20261013.md) and [free inference notes](docs/FREE_INFERENCE.md) record the account checks and requirements for any future bounded pilot. The key stays in ignored `.env.ai`; do not paste it into chat or commit it.

When remote reading is qualified and enabled, the capture screen discloses that the text is sent to Google AI before the **Read with Google AI** action. Use fictional or public claims without personal or confidential details; the unpaid service may use submitted content to improve products. See [Google's terms](https://ai.google.dev/gemini-api/terms).

## Local reviewer access

The setup helper generates a random `REVIEWER_TOKEN` in ignored `.env`. The account holder can copy that local value into the application's Reviewer sign-in. Do not commit or share the file. This credential controls **synthetic evidence trust exercises only**; it does not establish clinical qualifications or approve a clinical pack.

The separate `EDITOR_TOKEN` opens the quarantine workspace. Six partial public-domain NCCIH source packets are prepared in `evidence/quarantine`; import them with `python scripts/import_quarantine.py`. They require independent review and are not exposed as clinical evidence. [Review workflow](docs/REVIEW_WORKFLOW.md) describes the private qualification registry and publication boundary.

## Verification

The [local verification record](docs/VERIFICATION.md) preserves executed tests, build checks and engineering replay results at their recorded checkpoints. These passed checks do not establish clinical safety or live-model quality.

Run `.venv/Scripts/python.exe -m pytest`. API integration tests create a unique temporary schema in the project PostgreSQL database and remove that exact schema afterward. No user application records are deleted by tests. For portable tests, set both `TEST_DATABASE_ADMIN_URL` and `TEST_DATABASE_URL`; CI fails rather than silently skipping these tests. Domain tests cover semantic states and safety boundaries; provider tests cover budgets, schema errors, quotas and failure behavior. Run `npm test` and `npm run build` in `apps/web` for interface verification. The prepared GitHub Actions workflow skips private repositories to protect the $0 constraint; it has not run remotely.

See [build status](docs/BUILD_STATUS.md), [architecture](docs/ARCHITECTURE.md), [demo runbook](docs/DEMO_RUNBOOK.md), [evaluation runbook](docs/EVALUATION_RUNBOOK.md), [free inference notes](docs/FREE_INFERENCE.md) and the [original implementation plan](docs/planning/IMPLEMENTATION_PLAN.md). Actual results and remaining release gates are recorded separately from planned thresholds.

## Data and limits

Use synthetic data while the project is under development. Unsaved drafts expire after 30 minutes of inactivity or two hours total, with a scheduled cleanup check every minute. Saved cases expire after 30 days of inactivity; seven-day operational audit records contain event IDs, not raw prompts. Immutable evidence-review records have a separate lifecycle and contain no end-user claims. This is a single-process local application. Anonymous browser ownership does not provide cross-device account recovery. Clearing the ownership cookie loses access to saved cases until expiry; no public deployment or backup policy is implied.

Genuine WorkBuddy development review and four inspected evidence captures are complete. The [submission materials](docs/submission/README.md) include an editable deck, recorded screenshot walkthrough, captions, cover and entry copy for AJ_001. Entry eligibility, final contact details, judge-accessible publication and submission remain separate from the local assets. Clinical use and live AI still require their own outstanding review and evaluation.
