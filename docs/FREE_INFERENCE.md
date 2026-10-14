# Free inference and compute

The additional monetary budget is zero. **Live application inference remains disabled; no tested candidate is qualified.** Replay is a labeled test mode, not evidence of live model performance. No paid plan, chargeable overage or automatic top-up has been enabled. A separate Google project with billing unlinked and a private local key were verified on 13 October 2026; see [setup observations](FREE_AI_SETUP_20261013.md) and the [dated extraction results](AI_EXTRACTION_VERIFICATION_20261013.md). Another key or payment is not a prerequisite: model quality and the observed service failures are the current blockers.

## Outcome on 13 October 2026

Gemini 3.5 Flash-Lite with low and medium reasoning failed semantic checks on fresh and regression cases. Gemini 3.8 Flash failed its first bounded pilot generation, and a diagnostic request returned HTTP 503 with a high-demand response. Gemini 3.6 Flash also returned HTTP 503 on its first generation. Gemma 4 31B counted the diagnostic request successfully at 923 tokens, but its compatibility generation returned HTTP 500 and its native generation reached the configured eight-second read timeout. No production Gemma adapter was added. Successful token counting and schema-shaped output are not extraction qualification. The dated report preserves failures and distinguishes semantic results from service availability failures.

## Implemented adapter

`StructuredProvider.call(task_kind, data, schema, ledger, validator=...)` implements bounded structured JSON over an OpenAI-compatible HTTP endpoint, including a compatible local server or [Gemini's documented compatibility endpoint](https://ai.google.dev/gemini-api/docs/openai). No OpenAI SDK or credential is required. All candidate output still passes the domain's independent provenance, reference, policy and renderer gates. No tools or private reasoning are requested.

The Gemini path includes `GeminiTokenCounter` in `services/api/app/gemini.py`. It uses Google's official native count endpoint for the bounded text/schema request, adds a compatibility reservation and retains the returned-usage checks. Counting has a two-second bound within the stage deadline, separate request accounting and no automatic retry. The account's earlier 2.5 Flash-Lite request returned model-unavailable; later candidates and settings were tested as recorded above. There is no qualified model or reasoning setting. Actual latency and model results are recorded separately from mocked transport checks.

Gemini extraction uses `SlotExtractionCandidate`: every named slot is required and nullable, literal fields contain exact source quotes, and classification slots use constrained enum values with supporting quotes. The server computes proposition IDs, original-text offsets and hashes, and unresolved field names; null slots become unknown fields. The Gemini request schema expands bounded local references and omits selected unsupported constraints, while response validation retains the complete original schema. Existing local adapters retain their compact extraction contract.

After validating the original quote and its occurrence, a conservative admission check marks a whole unresolved pronoun in population, intervention or measured outcome as ambiguous with no value. It never guesses an antecedent, and it does not search for pronouns inside named noun phrases. This guard limits what is admitted; it does not establish that the model extracted the field correctly. Evaluation must keep raw candidates distinguishable from admitted results.

Extraction and alignment have independent enablement flags, both currently disabled. `EVIDENCELOOP_LIVE_ENABLED` governs a qualified reader; `EVIDENCELOOP_ALIGNMENT_ENABLED` defaults to false. The extraction format does not retain the claimed effect direction: an increase and a decrease can have identical named fields and affirmed polarity. Therefore, with alignment disabled, live-extracted claims may show trusted matching library information only as context. The compiler returns `alignment_mode: extraction_only` and reason `exact_claim_comparison_unqualified`, with no support/contradiction verdict, supported conclusion IDs, operator claims, claim-support graph, save permission or next step. Its explanation states that AI read the claim but cannot establish whether evidence supports the exact effect claimed. Existing safety, unknown-field and trust failures are preserved. Replay/manual comparison paths outside the compiler are unchanged.

The capture interface shows a plain summary with corrections on demand. A failed reader response is explicitly identified and falls back to essential manual questions, with optional and technical details collapsed. When `extraction_scope` is remote, Google processing and data-use terms are visible before **Read with Google AI**. Only that explicit live remote submission sends `allow_remote_processing: true`; local/replay requests omit it. Use fictional or public claims without personal or confidential content. Google's [unpaid-service terms](https://ai.google.dev/gemini-api/terms) permit content use for product improvement.

The same server-owned `AttemptBudget` must survive both extraction and alignment HTTP endpoints. Wrap each automated endpoint in `with ledger.meter():` to include infrastructure time; human confirmation wait stays outside this context. Nested adapter metering does not double count. Total limits are 40 cumulative automated seconds, 11,000 input tokens and 4,000 output tokens. The entire extraction stage has one 10-second deadline; alignment has one 14-second deadline. Counting, generation, any permitted repair and candidate admission all consume that stage's remaining time. Per-call output caps are 1,800/2,200. One repair per stage is allowed only for invalid JSON/schema and only when the full request/output allowance fits both the remaining token budget and the original stage deadline. Official Gemini extraction can instead use the second dispatch for one 502/503/504 recovery attempt after a one-second wait; repair and recovery share a maximum of two dispatches. Failed requests retain their full token reservations, including in estimated usage metadata. Timeouts, other network failures, refusals, truncation, policy/reference rejection and quota failures remain terminal. Repeating a completed/failed stage on the same ledger cannot refresh its allowance.

The default input reservation counts serialized UTF-8 bytes plus framing. This intentionally conservative estimate can reject contexts that a verified tokenizer would accept. A provider-specific token counter may be supplied after checking its accounting against reported usage. Usage absence reserves full bounds; a returned bound violation aborts instead of silently admitting an overrun. Reasoning tokens must be included in provider completion usage and output limits. Such capabilities need a real provider pilot; mocked tests do not establish them.

Before any future bounded qualification pilot, recheck the actual account/model's unpaid allowance, disabled billing, permitted synthetic-data processing, expiry/reset information and absence of a paid fallback. The existing private key belongs only in ignored `.env.ai` as `EVIDENCELOOP_MODEL_API_KEY`; the application reads it without enabling live mode. The [README](../README.md#free-google-ai-status) records the current disabled status. Complete real schema/usage, quality and latency qualification before enabling the application reader; do not treat configuration flags as evidence that a check passed.

The bounded pilot entry point is `scripts/run_extraction_probe.py`, which requires a non-secret dated free-account verification reference, reads only the selected input partition, defaults to a two-case development pilot, records failed attempts and uses the shared extraction compiler with alignment disabled. Do not run validation during prompt development. The original [extraction benchmark](../evals/extraction/README.md) contains 12 development cases and 12 former validation cases. Its validation failures have now been inspected for changes, so those 12 cases are regression-only and cannot support a later unseen-performance claim.

The [next October partition](../evals/extraction-next-20261013/manifest.json) was subsequently run, failed, and inspected during development; it is now **regression-only**, not an unseen validation set. A separate [final 12-case validation partition](../evals/extraction-final-20261013/manifest.json) is frozen and **has not been run against a model**. Offline integrity and fabricated gold-shaped scorer checks verify data and scoring mechanics only. All cases and labels are developer-authored fictional nonclinical material, with no independent human adjudication. No held-out qualification pass is claimed.

The configuration contract, once its corresponding checks are satisfied, is:

| Variable | Required meaning |
|---|---|
| `EVIDENCELOOP_LIVE_ENABLED=true` | Explicit opt-in; absent means disabled |
| `EVIDENCELOOP_ALIGNMENT_ENABLED=true` | Separate opt-in only after alignment qualification; defaults false |
| `EVIDENCELOOP_MODEL_BASE_URL` | Trusted server base ending in its compatible API prefix; HTTPS remotely, loopback HTTP permitted |
| `EVIDENCELOOP_MODEL` | Verified model/revision; no default model |
| `EVIDENCELOOP_MODEL_API_KEY` | If required; process secret, never commit or print |
| `EVIDENCELOOP_FREE_BUDGET_VERIFIED=true` | Actual account allowance verified |
| `EVIDENCELOOP_BILLING_DISABLED=true` | Account cannot incur paid overages |
| `EVIDENCELOOP_SCHEMA_VERIFIED=true` | Model/endpoint schema and token capability pilot passed |
| `EVIDENCELOOP_FREE_VERIFICATION` | Reference to the non-secret verification record |
| `EVIDENCELOOP_MAX_MODEL_REQUESTS` | Positive bound for this server process; includes errors/repairs |
| `EVIDENCELOOP_MAX_MODEL_REQUESTS_PER_MINUTE` | Optional generation limit over a rolling 60-second window; every dispatch including repair/recovery counts. Set from the verified account/model allowance. Zero means no additional local pacing guard. |
| `EVIDENCELOOP_REASONING_EFFORT` | Explicit model-specific setting recorded with qualification; no setting is currently qualified |
| `EVIDENCELOOP_TEMPERATURE` | Explicit sampling setting recorded with qualification; `none` omits temperature from the request |

Flags are operator attestations, not proof of account settings. The in-memory request cap does not replace the provider's hard unpaid limit or a durable account quota ledger; restarting a process must not be used to evade a quota. Remote usage is not enabled by merely setting an API key. Secrets in URLs, redirects, external schema references and ambient proxy configuration are rejected/disabled. Provider exceptions contain codes, not response bodies or user text.

## Historical account and tool checks — 30 September 2026

Authenticated read-only inspection on 30 September 2026 used the official Kaggle CLI in `.tools/kaggle`. It used an existing standard `~/.kaggle/access_token` through Kaggle's own authentication implementation. The token was not displayed or copied into the repository. `kaggle quota` returned:

| Resource | Used | Remaining | Total | CLI refreshAt |
|---|---:|---:|---:|---|
| GPU | 0.00 h | 30.00 h | 30.00 h | 2026-10-03T00:00:00 |
| TPU | 0.00 h | 20.00 h | 20.00 h | 2026-10-03T00:00:00 |

The CLI did not show a timezone. Quota is a point-in-time observation, not guaranteed accelerator availability. This authenticated check superseded the earlier browser-only unknown. No jobs were created during that initial account check; separately authorized private experiments were subsequently executed as recorded below. A Kaggle batch cannot establish a separate live API's latency. Official references: [API authentication](https://www.kaggle.com/docs/api), [CLI authentication sources](https://github.com/Kaggle/kaggle-cli/blob/main/skills/references/auth.md), [notebook documentation](https://www.kaggle.com/docs/notebooks).

At the targeted check, Kaggle, Tencent CodeBuddy, WorkBuddy, Ollama and llama-server were not on PATH. The standard Kaggle token file existed; standard `kaggle.json` did not. Kaggle/Gemini/Google/OpenAI API environment variables inspected for presence were absent. This is not an exhaustive account inventory. The official Kaggle CLI was subsequently installed only in the ignored project tools directory.

## Sponsor development use

[Tencent's CLI quickstart](https://www.codebuddy.ai/docs/cli/quickstart) identifies the genuine package as `@tencent-ai/codebuddy-code`, supporting Windows and requiring login. It is distinct from unrelated projects with similar names. [Current pricing](https://www.codebuddy.ai/pricing/) offers a free plan; the separate Pro trial requires a payment card and automatically renews, so it is excluded from the zero-cost path. Installation and a saved prompt alone are not sponsor-use evidence. Retain real authenticated development interactions/screenshots only after free access is verified. Coding credits do not establish app inference API credit.

On 13 October the user supplied screenshots of a hackathon registration confirmation with a CodeBuddy/WorkBuddy redemption entitlement and an offer of 1,000 Miora credits. The private redemption code is not copied into this repository or submitted anywhere. CodeBuddy's [Preview Agent SDK](https://www.codebuddy.ai/docs/cli/sdk) and [Beta HTTP agent API](https://www.codebuddy.ai/docs/cli/http-api) provide supported agent integration routes, so it would be inaccurate to describe the product as UI-only. However, the reviewed public documentation does not establish that these specific event credits cover SDK/server calls or provide transferable Gemini inference credit. WorkBuddy and Miora may help development and design; actual redemption, entitlement, expiry, runtime eligibility and genuine sponsor-use evidence remain separate checks. These screenshots are user-supplied evidence, not authorization to redeem a code or accept account terms.

## Verification status

Current slot admission preserves exact original matches first. A missing literal quote may be resolved through canonical NFC equivalence only, with conservative boundary checks and original input slices/offsets/hashes retained. No case, whitespace, line-ending or compatibility folding is allowed. Inconsistent source-attribution combinations are rejected rather than relabeled. These representation/consistency controls cannot establish the truth of a semantic assignment or replace model qualification.

The earlier checkpoint recorded 34 adapter tests passing with mocked HTTP, including timeout/no retry, quotas, schema repair limits, shared time/token accounting, cancellation, truncation, semantic rejection, concurrent-attempt rejection, unsafe endpoint configuration, external-schema rejection, annotation-only schema compaction and an asynchronous token counter. Additional Gemini, stage-separation and interface checks are recorded in [VERIFICATION.md](VERIFICATION.md). These establish exercised software paths, not model accuracy, real endpoint performance or clinical suitability.

## Historical local and Kaggle experiments — 30 September 2026

On 30 September 2026, official llama.cpp b11272 CPU binaries and Qwen's pinned 0.5B GGUF were downloaded and SHA-256 verified. Windows Smart App Control rejected `llama.dll` (Code Integrity event 3077, exit 0xC0E90002). An independently installed official CPU PyTorch distribution was also rejected (`torch_python.dll`, WinError 4551). Security policy was not changed. A safetensors download was cancelled once the second runtime block was known. These are environment failures, not model-quality results.

Microsoft `onnxruntime==1.30.0` and `onnxruntime-genai==0.17.1` import successfully. `scripts/local_inference_server.py` runs actual local models on fixed loopback; it uses schema-constrained decoding and exposes exact prompt token counting. There are no tools, paid APIs, public listener, tunnels or prompt logging. The initial model was a [community ONNX conversion](https://huggingface.co/xiaoyao9184/Qwen2.5-0.5B-Instruct-onnx-genai) of [Qwen's Apache-2.0 base](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct), pinned to conversion revision `455ccdae478e4149475923256cc27bfa6f775b02`, tested on port 8090. No downloaded Python or Jinja template is executed. That conversion does not include a separate license declaration; upstream origin/license are recorded and it is not redistributed in the repository.

Verified artifact hashes:

| Artifact | SHA-256 |
|---|---|
| llama.cpp b11272 Windows CPU zip | `f6d6c2d547b8f87ac1cecf1614207ee300aae1e0cf9b1966bd01129ef58855f7` |
| Official Qwen 0.5B Q4_K_M GGUF | `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db` |
| Community ONNX graph | `ce313fa11d3d5b12a752f27531d745514fab253f5ff8690889717d73d9599382` |
| Community ONNX weights | `19a2860d7b120cf2d5c5d91c516ecbbbb9d2f7ce2ddbee75bf4c4c6d1ad26e02` |

A real local constrained-JSON smoke request returned `{"ok":true}` in 2.89 seconds. This establishes basic inference and grammar capability only. The first three-case compact extraction probe admitted **0/3** candidates: invented/missing quotes or attribution problems prevented semantic admission. Results are preserved in `evals/development/local-onnx-0.5b-probe.json`. They are development failures, not evidence of release readiness. `scripts/probe_local_inference.py` records subsequent versions separately. A `LocalTokenCounter` callback uses this server's identical prompt builder with an eight-token reserve; no remote counting API is used.

The private Kaggle notebook `ajayasaithambi/evidenceloop-private-synthetic-model-pilot` was created with a 600-second job cap, T4 GPU, internet enabled for public model/package downloads, no attached datasets and `is_private:true`; server metadata was pulled to verify privacy. It uses three fictional nonclinical texts and pinned official Qwen checkpoints. Version 1 rejected oversized inputs before generation and exposed a test-harness schema duplication bug for the second model. Version 2 fixed duplication and compacted cosmetic schema annotations, but all six attempts failed in the LM Format Enforcer integration. Version 3 identified its unsupported combination of string pattern and length constraints. These are integration failures, not model accuracy scores. Version 4 ran only Qwen 1.5B and omitted redundant length constraints from its decoding grammar where a pattern exists; the original complete schema was still validated after generation.

A separate private CPU notebook, `ajayasaithambi/evidenceloop-private-onnx-export`, successfully converted official `Qwen/Qwen2.5-1.5B-Instruct` revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` using Microsoft's ONNX Runtime GenAI 0.17.1 builder. Version 3 completed conversion in 95.265 seconds after correcting missing exporter dependencies in earlier versions. The job had a 900-second cap and no GPU, user data, server or tunnel. The source has Apache-2.0 licensing; safetensors were loaded without remote model code. The seven downloaded artifacts, including LICENSE, all matched their SHA-256 manifest. See `evals/development/qwen15-conversion-manifest.json`; weights are 986,284,032 bytes with SHA-256 `8bb770c9160800857013a8d03a83aef4c54a6bf9298a052dbb6536b47e752567`. Artifacts remain local under ignored `.runtime/qwen15-export/qwen-1.5b-onnx`.

### Measured outcome: experimental model, release disabled

The 1.5B loopback model produced a small real constrained JSON response in 0.98 seconds. Novel compact extraction on this CPU failed the 10-second stage limit; four threads and grammar fast-forward did not make it qualify. The three-case record `qwen2.5-1.5b-onnx-int4-pilot-probe-structured-1.1-4threads-ff.json` contains a 10.16-second generation timeout followed by two 2.03-second counter timeouts in the earlier runtime architecture. Those failures were retained rather than replaced by successful-looking mocks.

The runtime was then corrected to isolate native inference in a spawned process. HTTP stays responsive; busy count requests return 429 immediately. Deadline, disconnect and truncated-generation paths dispose of the worker and can prepare a new worker, but never retry the failed input. The automated stage limits remain unchanged. An actual bounded load check in `evals/development/local-runtime-cancellation.json` passed: health responded while generation was busy, the simultaneous count request returned 429, truncated generation ended in 9.516 seconds, the old worker process was confirmed terminated, and the replacement was ready with exactly one generation started. No queued or hidden second generation ran. This verifies responsiveness and cancellation for that exercised case, not semantic accuracy.

Kaggle version 4 completed three real 1.5B GPU generations with the following results. All were outside the 10-second stage budget; these timings include prompt/grammar preparation and are offline batch observations, not live API measurements.

| Case | Wall time | JSON/schema | Observed semantic failure |
|---|---:|---|---|
| Fictional lab / glow water / fern growth |14.458s|Valid|Used the lab as population; omitted intervention and measured outcome; mismatched context value/quote |
| Study Club / quiet cards / no recall improvement |14.208s|Valid|Used the source as population; omitted negation; mismatched context value/quote |
| Advertisement / every plant / user disagreement |14.319s|Valid|Misrepresented disagreement as a claimed clinical outcome; omitted key attribution distinctions |

The deterministic domain parser initially admitted all three candidates; that observation did **not** establish extraction accuracy. Inspection found the errors above. A subsequent guard requires a concept value to match its quoted surface after Unicode NFC normalization and trimming. Rechecking the same recorded outputs rejected all three with `extracted_surface_quote_mismatch`; both the initial and corrected admission records are preserved. This closes an observed grounding gap, but cannot establish semantic role accuracy or recover omitted negation. None is an accepted model-quality pass, and no sealed benchmark or clinical review was performed. Raw synthetic results, model/runtime versions and admission diagnostics are preserved under `evals/development/kaggle-v4/`. No further model download or training/evaluation job is needed to state this result accurately.

The final authenticated quota snapshot at 2026-09-30T08:12:33Z showed GPU 0.15 hours used / 29.85 remaining of 30 and TPU 0 used / 20 remaining of 20; refreshAt remained 2026-10-03T00:00:00 without a reported timezone. See `evals/development/kaggle-quota-final.json`. All jobs were complete. No paid resources were enabled.

### Later local lean-format diagnostics

The later [runtime summary](../evals/development/lean-runtime-summary.json), recorded at 2026-09-30T14:34:53Z, preserves **28 attempts and 4 exact matches** over repeated fictional cases and several prompt/runtime variants. Generic grammar preparation moved to startup; flat slots reduced output length, and some warm calls completed within ten seconds. Attribution, missing fields, literal spans and negation remained unreliable, including truncated attempts. These are tuning diagnostics, not 28 independent benchmark cases or a qualification pass. The tested local model is unsuitable for the application reader. The diagnostic service was stopped after the probes; the earlier Kaggle and runtime evidence above remains historical evidence.

### Resume the optional runtime

The experimental inference servers were stopped after verification. The model data and isolated environment remain available. From the project directory, run:

```powershell
.\scripts\start_local_inference.ps1 -FastForward
```

This starts `http://127.0.0.1:8091/v1` with model ID `qwen2.5-1.5b-onnx-int4-pilot`, four CPU threads, and `/health` plus `/v1/token-count`. Use `LocalTokenCounter(base_url)` for the adapter's verified identical prompt accounting. The app's live `.env` flag remains false: starting this experimental service does not qualify the model or enable it in the application. `scripts/requirements-local-inference.txt` records the isolated runtime dependencies. It does not install or change Windows security policy.

Tencent CodeBuddy CLI 2.160.0 was installed in `.tools/codebuddy` and executed. Startup showed login-method selection. The subsequent actual international-login attempt failed while generating its login URL with `getaddrinfo ENOENT www.codebuddy.ai`; read-only DNS inspection returned A record `0.0.0.1`, and Node DNS lookup also failed. No DNS or security setting was changed. This routing limitation prevented authentication, so no authenticated allowance, development model interaction or sponsor-use evidence is claimed.
