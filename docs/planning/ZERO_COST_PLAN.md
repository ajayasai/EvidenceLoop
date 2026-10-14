# Zero-cost completion plan

Status: user-confirmed budget constraint, 30 September 2026. The user requested an active goal to complete EvidenceLoop for free and authorized use of their Kaggle account if required. This does not establish account access, available compute, reviewer availability or tested integrations. The earlier planning-only boundary remains until the user confirms implementation may begin.

## Hard budget

Additional monetary spending: **0**. Use existing hardware/internet, free software, available free service quotas and eligible sponsor credits. Do not purchase hardware, software, credits, subscriptions, domains or hosting; enable automatic billing; or allow chargeable overages. Stop, defer, optimize or choose another free resource when a quota runs out. A paid trial that renews automatically is not the default free path. Existing account access is not permission to incur charges.

Record the source of every allowance, current balance, expiry, replenishment date, billing mode and expected consumption before depending on it. Credits do not mean unlimited use. Human time, donated review and existing equipment are real resources even when no new cash changes hands.

## Resource plan

| Requirement | Proposed free route | Gate / fallback |
|---|---|---|
| Development | Existing local editor/runtime, open-source stack, GitHub Free | No new paid developer subscription; use local tools if hosted quotas expire |
| Mandatory sponsor use | CodeBuddy/WorkBuddy free allowance and redeemed hackathon credits | Verify eligibility/redemption; retain genuine development evidence; do not assume these credits cover application API inference |
| Application and database | Run on the existing computer using the proposed React/Python/PostgreSQL stack | A live local demo does not require a paid cloud host or custom domain; any public host must have confirmed free limits and no paid fallback |
| Runtime AI | Evaluate an eligible free hosted API using synthetic data; alternatively a suitable model on existing hardware | Must meet structured-output, evidence-support and latency gates; free status alone does not establish suitability |
| Evaluation compute | Local runner first; Kaggle notebook if compute helps and the account has free capacity | Inspect current quotas/settings before starting; checkpoint batch work and avoid unnecessary reruns |
| Evidence | Accessible official sources, lawful excerpts and reviewer-authored summaries | No purchases of journals/datasets; missing access narrows approved scope |
| Clinical/evidence review | Qualified volunteer collaborator, mentor or institutional support | Do not replace independent review with a model or claim it occurred; lack of review remains a release dependency |
| Assets and presentation | Original diagrams, screenshots, free recording tools; optional already-available Miora credits | No stock asset or design subscription required |

Current verified examples: [GitHub Free](https://docs.github.com/en/get-started/learning-about-github/githubs-plans), [CodeBuddy free plan](https://www.codebuddy.ai/pricing/), [WorkBuddy pricing](https://www.workbuddy.ai/docs/workbuddy/pricing), and the [handbook's participant benefits](https://heikesong-global-1256915710.cos.ap-hongkong.myqcloud.com/online_video/3af2d08d-d3f0-4998-98a5-a820bd245910.pdf) (page 41). Account entitlements and remaining allowances have not been inspected. [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) lists free model options; [unpaid-service terms](https://ai.google.dev/gemini-api/terms) constrain data use, so only synthetic inputs belong in this candidate path.

## Observed local readiness

Read-only checks on 30 September 2026 found the following. These are environment observations, not a working application or model benchmark.

| Resource | Observed state | Consequence |
|---|---|---|
| Memory and CPU | 31.6 GiB RAM; Intel Core Ultra 7 155U, 12 cores / 14 logical processors | Suitable starting point for local application development; model speed remains unmeasured |
| Graphics | Intel integrated graphics; no NVIDIA accelerator established | Do not assume CUDA or adequate local inference speed; consider Kaggle only for a measured compute need |
| Disk | Approximately 19.8 GiB free on C: at inspection | Keep dependency/model downloads bounded; check expected download plus extracted size before installation |
| Available runtimes | Bundled Python 3.12.14, Node 24.19.0 and Git 2.53.0.windows.3 executed successfully; a separate Python 3.14 executable is on PATH | Use a project-specific environment after implementation approval; do not modify the user's global Python |
| Development dependencies | Pydantic discoverable in bundled Python; FastAPI, Uvicorn, pytest, psycopg, torch, transformers and Kaggle package not discoverable there | Installation is future work; this does not describe every Python environment on the computer |
| Database/container commands | docker, psql and nvidia-smi were not found on PATH | Availability elsewhere is unknown; choose and verify a free local PostgreSQL setup before claiming the environment is ready |

No application dependency or model was installed by these checks. The initial implementation route is the local application and database, followed by a small synthetic inference pilot; large model downloads and remote hosting are not prerequisites.

## Kaggle authorization and intended role

The user has authorized use of their Kaggle account when useful for this project. No Kaggle connector is currently available in the tool inventory. A read-only check of Kaggle in the accessible Codex in-app browser on 30 September 2026 showed the public page with Sign In/Register controls. An authenticated account was therefore not available in that browser; this says nothing about other browsers. Account-specific accelerator entitlement and remaining quota are unknown. No notebook, dataset, job or account setting was created or changed. If Kaggle becomes necessary, establish an authorized account session or supported API access first. Never request that credentials be pasted into chat or embed them in a notebook/repository.

Prefer Kaggle for bounded, resumable synthetic evaluation or candidate-model experiments if local compute is insufficient. It is not assumed to be a persistent application server or an unlimited GPU endpoint. Before any job, verify account-specific accelerator availability, remaining quota, session limits, network/download settings, output persistence, model license, notebook visibility and absence of chargeable resources. Keep project notebooks private by default where supported. Do not upload real health content, confidential source material or credentials. A notebook model experiment is not a live runtime integration or clinical validation.

Verified platform documentation: Kaggle offers free but capacity-limited GPU notebooks with bounded sessions ([notebook documentation](https://www.kaggle.com/docs/notebooks), [GPU usage guidance](https://www.kaggle.com/docs/efficient-gpu-usage)). The account's remaining allowance is not known. Notebook and dataset privacy must each be checked; one does not establish the other. Check model-specific access and license conditions in the [model documentation](https://www.kaggle.com/docs/models). Using Kaggle for batch work rather than always-on serving is an engineering choice based on those limits.

No fine-tuning is added merely because GPU access exists. First measure whether the existing extraction/alignment calls fail in a way that additional compute can fix. Use small pilot batches, then the frozen evaluation configuration, with checkpointed outputs and cost/usage metadata. A Kaggle interruption must not cause fabricated or selectively omitted test results.

## Quota preflight

Before selecting a runtime provider, fill in the account's actual free requests/minute, requests/day, tokens/minute, remaining token or credit balance, reset time, expiry and billing mode. Record model/version and whether failed requests and schema repairs consume quota. Compare these limits with the workload worksheet in [EVALUATION_PLAN.md](EVALUATION_PLAN.md), including warm-ups and concurrent requests. Public pricing documentation alone does not prove the account can complete that workload.

Reserve capacity for the required release checks and demo before optional ablations or tuning. A small synthetic pilot measures real token use and latency, then informs a bounded batch schedule. Pause at the verified free limit; do not enable billing to continue. If five concurrent requests cannot be tested within free limits, report that gate as untested or use a suitable free/local runtime and rerun the comparison. A Kaggle batch can support offline model evaluation but cannot establish the latency or reliability of a different live API deployment.

## Completion gates under the free constraint

1. The functional, evidence, consent, safety and evaluation gates in the implementation plan still apply.
2. All active dependencies have a verified free allowance or run on existing hardware; actual additional spend remains zero.
3. Quota exhaustion causes a clear limitation or postponed job, never automatic payment or a weaker medical answer.
4. A lack of qualified volunteer review cannot be hidden as a cost saving. Internal synthetic engineering work may proceed; public health-assessment examples remain dependent on review.
5. Clearly labeled replay is a demo recovery path, not proof that live inference or the full benchmark succeeded.
6. Zero-cost completion is the active goal, not a promise that unavailable account access, team eligibility or human review has already been resolved.

Next authorized planning work: confirm available free entitlements and compute routes. Once implementation is approved, start EL-001 locally and use Kaggle only when a measured compute need justifies it.
