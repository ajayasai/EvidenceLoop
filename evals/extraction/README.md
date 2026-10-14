# Fictional novel-input extraction benchmark

Status: **frozen, unexecuted** at corpus creation. This is a small engineering benchmark for extraction drafts, not clinical validation. Inputs and expected labels were authored by the developer agent. No independent human adjudication is claimed.

`development.inputs.jsonl` and `development.labels.jsonl` contain 12 tuning cases. `validation.inputs.jsonl` and `validation.labels.jsonl` contain 12 additional cases. Keep the validation files out of tuning prompts and manual prompt development. Freeze the model revision, wire schema, prompts, decoding, budget and hardware before the first validation run. Revisions based on validation results convert that partition into regression data; a later unseen-performance claim requires new cases. The splits share behavioral templates, so they are not independent language distributions.

The corpus tests literal interventions/outcomes, explicit versus absent populations, source versus population, negation, attributed disagreement, questions, association, uncertainty, ambiguous pronouns, missing outcomes, injection attempts and original Unicode spans. Every input concerns fictional nonclinical objects. There is one principal proposition per case; multiple substantive propositions, deep nesting, clinical language and broad multilingual coverage are outside this benchmark.

All four data files have exact SHA-256 hashes in `manifest.json`. Inputs include only `case_id`, `text` and explicit user `intent`; do not send labels or tag metadata to the model. The validation author necessarily saw the validation material. It is withheld from the integration owner's tuning, not independently sealed or medically reviewed.

## Prediction format and scoring

Write one JSONL row per attempted case:

```json
{"case_id":"D01","result":{"claim":{"propositions":[]},"intent":{},"mode":"live","system_status":"ok"},"wall_seconds":1.25}
```

`result` must be the normalized extraction result containing typed `Field` wrappers and original `input_span` provenance, as returned by the extraction compiler. A raw model-specific candidate must pass the production converter first. Record failed attempts too, with `error` and measured `wall_seconds`; absent predictions are failures, never excluded denominators. Repetitions use separate prediction files. Do not combine retries into extra independent cases.

Run scoring without a model or network call:

```text
python -m evals.extraction.score --partition development --predictions PATH --output NEW_PATH
```

The scorer separately reports:

- Accuracy on explicitly stated fields; unknown guesses do not count as correct extraction of known facts.
- Preservation of genuinely unknown fields; omitted population must not become the reporting organization.
- Critical errors for population, intervention, outcome, polarity, attribution, speaker, speech act and explicit intent.
- Exact case success, useful intervention/outcome/polarity extraction, every stated field's original-span integrity, and operational failures.
- All-attempt latency and missing timing measurements, with the current extraction stage's 10-second limit.

An affirmative question has `speech_act=question` and an affirmative embedded proposition; it is not user endorsement. Attributed disagreement does not negate the quoted proposition. Causal wording records the relation asserted by the input, never establishes that causation is true. `measured_outcome` identifies the outcome named in the user's proposition; the label does not assert that a real study measured it.

Expected literal alternatives are frozen narrow noun-phrase variants present in the same text. Enum labels require an original quote containing the relevant predicate or explicit uncertainty wording. Grounding does not prove the semantic role is correct; that is why surface assignment is scored separately. Every unscored stated field is listed for inspection, not silently certified.

The frozen engineering gate requires at least 95% stated-field accuracy, no critical errors, no invented unknowns, no invalid spans, at least 90% useful essential extraction, no operational failures, and all recorded attempts within 10 seconds. This is demanding for only 12 cases and provides no population-level reliability estimate. A failure is a measured failure; do not edit the label or discard the case merely to obtain a pass. No gate results exist until a real model run is scored.

## Contract findings and proposed simplification

The existing dynamic `fields[{name,value,quote}]` contract lets a model omit every essential field while returning valid JSON, duplicates literal text, and offers many competing labels. `unresolved_fields:[]` does not establish completeness. A quoted source organization is easily misassigned as the population. The discovered compiler/prompt input-key mismatch was corrected to canonical `original_text` in prompt version `structured-1.2` before any remote benchmark run.

Prefer required nullable literal slots for population, intervention, comparator, outcome and attribution, plus a copied predicate phrase and explicit speech form/source ownership. Each literal is an exact substring or null, with an occurrence index only when needed. The server computes IDs, hashes and offsets. Conservative predicate rules may derive relation/polarity/certainty with copied predicate provenance; unresolved semantics must remain unknown. Keep population distinct from whoever reports the claim. A claim's named outcome does not need to be proven measured before it can be extracted. Never ask the model to invent an absent population merely to satisfy confirmation.

Unit-test data integrity and the scorer separately from model performance. A gold-shaped synthetic prediction used to test the scorer is not an AI result and must never be included in a model-results file.
