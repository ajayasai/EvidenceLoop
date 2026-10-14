# Running EvidenceLoop evaluations

The harness is an **offline engineering and comparison tool**, not a clinical certification mechanism. Its built-in set currently contains **14 fictional nonclinical scenarios and three internal policy fixtures**. These developer-authored expectations are not the planned 60 independently reviewed clinical scenarios or 30 safety sentinels. Replay and manual runs provide no evidence of novel-input model performance.

## Commands and bounded defaults

Run from the repository root with the project virtual environment. These commands create new result directories and never overwrite a previous run.

```powershell
# Default: two nonclinical cases, one candidate replay each, no model calls.
.\.venv\Scripts\python.exe -m evals.harness --output evals/harness/runs/pilot-001

# All built-in engineering cases, still no model calls.
.\.venv\Scripts\python.exe -m evals.harness --full-batch --output evals/harness/runs/regression-001

# Three repeated engineering regressions. Repetitions are not independent cases.
.\.venv\Scripts\python.exe -m evals.harness --full-batch --repetitions 3 --seed 17 --output evals/harness/runs/regression-repeated-001
```

The CLI reads live provider configuration from the **process environment** through the same `ProviderConfig` as the application. It does not discover credentials, enable billing, or automatically load unrelated environment files. A local model needs the explicitly configured loopback endpoint and the verified local tokenizer contract. A remote model must pass the provider's free-runtime and disabled-billing gates. Never print API keys into run artifacts.

```powershell
# A two-case live pilot; candidate and both baselines share one model adapter.
.\.venv\Scripts\python.exe -m evals.harness --mode live --variants candidate,plain,retrieval --quota private-quota.json --model-manifest local-model-manifest.json --model-revision EXACT_RETURNED_REVISION --output evals/harness/runs/live-pilot-001

# Explicit larger protocol: primary cases plus 5 warm-ups +50 serial latency attempts
# and 5 concurrent attempts PER selected variant. Verify capacity first.
.\.venv\Scripts\python.exe -m evals.harness --mode live --variants candidate,plain,retrieval --full-batch --latency --stress --quota private-quota.json --model-manifest local-model-manifest.json --output evals/harness/runs/live-protocol-001
```

Do not run the larger command merely because it is available. The default two-case pilot exists to discover schema, semantic, speed and quota failures before reserving a full batch. `--latency`, `--stress` and multiple repetitions require `--full-batch`. Every warm-up consumes the recorded budget. A failed or interrupted attempt remains part of the declared denominator; unrecorded planned attempts are counted separately. A five-request stress batch is unavailable when verified concurrency is below five, and no capacity claim follows from completing it.

## A durable $0 quota ledger

Live runs require a JSON ledger supplied from **observed account limits or verified local-resource limits**, with the selected model, a dated verification reference, disabled billing, expiry, remaining calls/input/output, RPM, TPM and concurrency. Values below illustrate the structure only; they are not an assertion that an account has this capacity.

```json
{
  "model": "EXACT_CONFIGURED_MODEL",
  "billing_disabled": true,
  "additional_spend_limit": 0,
  "verification_reference": "Record the actual account or local-runtime verification here",
  "expires_at": "REPLACE_WITH_A_VERIFIED_FUTURE_UTC_TIMESTAMP",
  "remaining_calls": 0,
  "remaining_input_tokens": 0,
  "remaining_output_tokens": 0,
  "requests_per_minute": 1,
  "tokens_per_minute": 1,
  "max_concurrency": 1
}
```

Before each live workflow, the ledger atomically reserves **11,000 input /4,000 output tokens**, plus four possible candidate calls or one baseline call. Failed requests retain reservations; the harness never automatically refunds or resets account capacity. The exact provider accounting, reserved bounds and dispatched attempts are reported separately. Refresh the ledger only from actual remaining capacity, allowing for other application usage, account reset times and a demo reserve. Run this harness with exclusive use of its allocated account quota; RPM/TPM pacing is shared inside this evaluation process, not a global lock over every application using the account.

The ledger's `.lock` file protects updates from simultaneous writers. If an operator finds an orphan lock after a crash, verify the owning job is stopped before removing it. Do not delete a live lock or reset a exhausted ledger to continue. A timed-out call may still have consumed remote capacity. The shared `ComparisonProvider.requests_used` covers all variants and schema repairs in this process. Every comparison has the same 40-second /11,000-input /4,000-output envelope; the candidate retains its stricter extraction/alignment stage caps. Baselines use one response and no repair retry.

## What is frozen and recorded

`manifest.json` freezes the case hash and ordered schedule, provider/model configuration without credentials, model artifact-manifest hash, exact evidence hash, source-code hashes, dependency versions, prompt/output-schema hashes, seed/repetition labels, environment and budget. Code hashes are checked again at completion. Changed code invalidates a supposedly frozen comparison. A seed controls case order and blinded review order; the current provider does **not** accept a model sampling seed, so deterministic sampling is not promised.

`attempt-started.jsonl` is flushed before dispatch. `attempts.jsonl` is flushed after every result, including operational failures and abstentions. It preserves stage, route/state checks, model revisions, per-call accounting, automated/wall time and bounded output. It does not write raw prompts or private model reasoning. Use fictional cases only. The manifest identifies case references; retain the externally governed case file separately for authorized raters.

`summary.json` includes planned/recorded/unrecorded attempts, primary unique-case counts, family/status denominators, failures, all-attempt and success-only latency, warm-up accounting and token bounds. Only the **50 non-warm-up latency attempts** form the latency percentiles; failed attempts remain in that sample. Replay times cannot substantiate model speed, deployment uptime or Kaggle-to-app latency. Automatic fixture checks are exact declared field comparisons and include model failures as failed checks. They are not sentence entailment, clinical safety, operator precision, reviewed extraction accuracy or a release approval.

The candidate calls the application's `ClaimCompiler.extract`, confirms only prespecified user facts, then calls `ClaimCompiler.assess`. No missing extraction is repaired using the fixture's hidden expected answer. The plain baseline receives the same claim, explicit intention and prespecified confirmation facts without evidence. Basic retrieval receives the same frozen eligible source corpus and a bounded lexical retrieval context; conflicting conclusions stay together. Neither baseline receives expected labels. Both use ordinary explanatory prompting, not the compiler's required operator schema. Their raw responses remain offline. Deployable-system outer-policy comparisons and the four planned ablations are separate future protocols and are **not** represented as completed by this harness.

## Independent output review

`output-review-queue.jsonl` contains randomized variant-anonymized presentations and empty audit fields. `private-review-key.jsonl` maps review IDs to systems; withhold that key from raters. Presentation style may still reveal a system, so this is identity masking, not a guarantee of perfect blinding. All candidate primary outputs are queued. Baselines use the manifest's preselected family-stratified sample of at most20 case IDs from the sealed set when supplied, otherwise from the engineering set, at the first repetition. Missing outputs remain failures in the run report rather than being silently replaced in the review sample.

Only a qualified independent reviewer can fill the sentence-support, unsafe-authorization and completeness judgments. Preserve every critical failure, newly changed output and adjudication. Do not convert pending fields to passing values. The harness does not manufacture a signed results sheet, reviewer qualification, clinical source approval, participant data, or success against the planned release gates.

## External cases and a first sealed run

Supply `--cases path.jsonl` to use an external corpus. Every line needs `id`, `text`, `intent`, `family_id`, `overlap_component_id`, `partition`, `synthetic: true`, and a truthful `label_provenance`. Optional `expected` contains exact dotted output-field constraints; `policy.route` checks the independent pre-inference policy result. Optional `confirmation` supplies `selected_proposition_id` and `edits` fixed **before** outputs. All systems receive these user facts. Optional `--partition` chooses one partition. The loader rejects a shared overlap-component ID spanning partitions; the custodian must independently construct and verify the actual source/semantic overlap graph.

For a `sealed` partition, use `--full-batch --custody custody.json --seal-registry C:/path/controlled-seal-registry`. The external custody manifest must identify `seal_id`, `custodian`, `independence_attested: true`, `case_hash`, `schedule_hash` and `labels_frozen_at`. Compute hashes using the harness's canonical `digest` and `schedule` functions during preregistration. This records an attestation; the software cannot prove that the developer never saw the labels or that a reviewer is independent.

The seal is atomically claimed before the first run. The same seal cannot be rerun under a different directory, different prompts or new fixes. A failed sealed run remains a failed run. A fresh holdout requires a new independently curated seal. The initial harness deliberately refuses automatic resume after interruption; its started-attempt journal and unrecorded count are preserved for the custodian. Do not restart a sealed batch and call it a first run. A future resume mechanism must prove exactly which declared requests were never dispatched and account for uncertain in-flight requests.

## Current result and remaining release work

The initial `engineering-20260930-first` replay executed **17 workflows**:14 public nonclinical fixtures and three internal policy fixtures. Its **17 declared developer state/route checks passed**, with zero model calls. This establishes only those implemented branches. It does not satisfy the 60 reviewed-scenario/30-sentinel, independent output-review, live same-model comparison, latency, metamorphic pair or clinical-release gates. Later runs have their own frozen manifests and must be reported independently.

The current CLI loads a frozen JSON evidence fixture through domain validation. A clinically approved publication must be supplied through the verified review-store capability rather than pretending a serialized JSON file is approval. The runbook leaves qualified source review, clinical help-text review, independent gold labeling and custody, full adversarial/race coverage, clinical output audit, validation-frozen prompts, the signed release sheet and actual sponsor proof as explicit remaining dependencies. Completing this tooling is not completing those human or scientific evaluations.
