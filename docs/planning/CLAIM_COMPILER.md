# Claim-to-action compiler

Status: PROPOSED. This is a design contract, not an implemented or validated compiler. Canonical lifecycle, scientific, operational and routing enums are defined in [DECISIONS.md](DECISIONS.md). Safety rules are owned by [SAFETY_MODEL.md](SAFETY_MODEL.md).

## 1. Intermediate representation

The compiler translates a quoted assertion and a separately confirmed intention into a versioned argument graph. It preserves what was said, who said it and what remains unknown. A claim about a supplement does not prove that the user takes it; asking whether an action is safe does not mean the user intends to take it.

Proposed `ClaimIR/1.0` schema notation below is a documentation contract. UUID identifiers, RFC 3339 UTC timestamps and SHA-256 hashes use shared API scalar definitions. Unknown object keys are rejected; array and text limits are enforced before inference.

| Field | Type and invariant |
|---|---|
| schema_version, claim_id, version_id, parent_version_id | Literal `1.0`; UUIDs; nullable parent only for first version |
| input_hash, original_text, normalized_text, normalization_map | Original preserved exactly; normalized NFC with line endings normalized; no punctuation/negation stripping |
| propositions | 1–3 `Proposition`; more requires narrowing before assessment |
| selected_proposition_id | Nullable until confirmation; exactly one extracted proposition ID selected for assessment |
| unresolved_fields | Field paths plus ambiguity codes; never a model confidence score |
| confirmed_at, confirmation_event_id | Both null until user accepts/edit-confirms the frame |
| extraction_run_id, prompt_version | Structured audit references; no hidden reasoning |

Every semantic value uses `Field<T> = {state, value, provenance}`. `state` is `stated | unknown | ambiguous | not_applicable`; `value` is non-null only for `stated`; all other states require null. An empty string is invalid. `unknown` means unspecified, `ambiguous` means multiple interpretations remain, and `not_applicable` requires a documented field-specific rule. Explicit user edits have confirmation-event provenance rather than invented input spans.

`Proposition` contains:

| Group | Typed fields |
|---|---|
| Identity and speech | `proposition_id`; `speaker = quoted_source \| user \| unknown`; `speech_act = assertion \| question \| reported_assertion`; `attribution_text: Field<string>` |
| Scope | `population`, `condition_context`, `intervention`, `comparator`: `Field<Concept>`; a Concept has surface text and nullable approved-library concept ID |
| Intervention identity | `formulation`, `dose`, `route`, `co_intervention`: `Field<string>`; no inferred dose equivalence |
| Outcomes | `measured_outcome`, `claimed_clinical_outcome`, `mechanism`, `safety_outcome`: `Field<Concept>` |
| Quantifiers | `magnitude: Field<{value, unit, basis: absolute \| relative \| unspecified}>`; `timeframe: Field<{value, unit}>`; `generalization: Field<subgroup \| scoped_population \| universal>` |
| Assertion | `relation: Field<causal \| associative \| descriptive>`; `certainty: Field<possible \| probable \| asserted \| guaranteed>`; `polarity: Field<affirmed \| negated>`; `negation_scope: Field<field_path[]>` |
| Reported evidence | `claimed_evidence_type`, `claimed_source_type: Field<string>`; these describe the message, never verified study metadata |
| Assumptions | `missing_assumptions[] = {code, affected_edge_id, required_field_paths[]}`; bounded codes from an application registry |

`IntentIR/1.0` has independent `intent_id`, `version_id`, `claim_version_id`, `confirmation_event_id` and `confirmed_at`. Its Field values are `action_kind = learn | discuss | start | add | replace | stop | delay | change_dose | prevent | seek_cure | other`; `target`; `current_care_relationship = alongside | instead_of | unrelated`; `timing`; `actor = self | another_person | hypothetical`; and `endorsement = supports | rejects | uncertain | not_stated`. Endorsement refers to the user's position on the quoted proposition, independently of intended action. Missing endorsement is Field `unknown` with null value; an explicit uncertain/no-position answer may be `stated` with `uncertain`/`not_stated`. UI “curiosity” maps to action `learn`, “add-on” to `add`, and “prefer not to say” to Field `unknown`, never an inferred intention. Free text may clarify an action but cannot authorize diagnosis, prescribing or dose changes. Multiple conflicting intentions require confirmation.

All provenance spans are half-open `[start,end)` Unicode code-point offsets into **original_text**, with an exact quote and SHA-256 input hash. UTF-16 browser indices are converted at the API boundary. Normalized offsets are internal only, with a reversible original-offset mapping. Validate boundaries and exact substring equality before admission. Test emoji, combining characters, CRLF, smart quotes, attribution and nested negation. “The article says X, but I disagree” must not become user endorsement. Missing or ambiguous negation is unknown. Original text, normalization maps and raw quote spans belong to the ephemeral extraction artifact; submission persistence retains only normalized confirmed minimum fields and provenance hashes/offsets. Saving original user text or selected raw quotations is excluded. Saved views cannot reconstruct or claim to revalidate the discarded original text.

Persistence uses **`ConfirmedClaimSnapshot/1.0`**, a distinct schema rather than a truncated ClaimIR: `{schema_version:"ConfirmedClaimSnapshot/1.0", claim_id, version_id, parent_version_id, selected_proposition_id, confirmed_proposition, confirmed_at, confirmation_event_id, origin_claim_ir_version, provenance_refs[]}`. `confirmed_proposition` contains normalized confirmed Field values for the selected proposition; `provenance_refs` contain only `{field_path,input_hash,start,end,confirmation_event_id?}`. Its Field provenance references those records, never an embedded raw quote. No original text, normalization map, discarded proposition text or raw selected quotation is saved. Persisted intent likewise contains normalized confirmed Field values and content-free provenance references. Source-evidence anchors remain independently preserved under EVIDENCE_SYSTEM.md.

## 2. Compilation and admission stages

1. Bound input to 6,000 Unicode code points and 24 KiB UTF-8, within a 32 KiB JSON request; reject unsupported uploads/URLs as ingestion requests. Apply initial policy checks to the original message as untrusted data.
2. Stage A extracts IR candidates. Deterministically validate schemas and spans. Show a concise editable claim/intention confirmation card. Ambiguity in action, negation, population or intervention blocks dependent assessment.
3. Freeze confirmed claim and intent versions and exactly one `selected_proposition_id`. Other extracted propositions carry the display disposition `not_assessed`, not a scientific verdict. Safety checks still consider the entire original input and all extracted propositions. Never silently re-extract or overwrite the confirmed frame.
4. Retrieve eligible reviewer-authored briefs for the selected principal proposition using concept IDs and scope filters. Stage B proposes bounded alignment to those briefs. Distinct proposition outcomes are never combined into `conflicting`; changing the selection starts a fresh assessment attempt.
5. Validate candidate edges/operators against the current publication snapshot; deterministic policy selects route independently. Templates render only admitted conclusion IDs and reason codes.
6. Recheck trust state before issuing a receipt or saving. An edit creates new versions and invalidates prior confirmation; historical receipts remain immutable.

The argument graph has typed nodes `mechanism`, `measured_effect`, `clinical_outcome`, `scenario` and `intended_action`. An edge records `from`, `to`, `warrant_ids[]`, `operator_findings[]` and `unresolved_fields[]`. Nodes need not all exist; never create a mechanism to complete a diagram. Each edge requires its own warrant. Support for an outcome cannot traverse an unwarranted edge to personal treatment authorization. Graph position expresses reasoning structure, not a causal model learned from patient data.

## 3. Explicit mismatch operators

`D` means a deterministic predicate over **already confirmed/approved typed fields**. `H` means semantic alignment proposes a candidate, followed by deterministic admission and a reviewer-authored warrant. Neither means automatic medical truth detection. Runtime output per operator is `{operator_id, operator_version, operator_state, claim_field_paths, evidence_conclusion_ids, anchor_ids, graph_edge_id, reason_code}`. Allowed states are exactly `established | not_detected | unknown | not_applicable`.

| ID / mismatch | Predicate or missing warrant | Mode | Scope |
|---|---|---|---|
| L01 cell_to_human | Approved evidence is cell-only; assertion claims demonstrated human treatment benefit | D/H | FUTURE WORK |
| L02 animal_to_human | Animal-only evidence asserted as demonstrated human benefit | D/H | FUTURE WORK |
| L03 biomarker_to_clinical_outcome | Measured surrogate promoted to a distinct clinical outcome without approved linkage | H | Candidate MVP |
| L04 association_to_causation | Observational association promoted to a causal claim without an approved causal warrant | D/H | Candidate MVP |
| L05 subgroup_to_population | Identified subgroup result extended beyond reviewed scope | H | Candidate MVP |
| L06 short_term_to_long_term | Short follow-up used to assert sustained benefit/safety | D/H | FUTURE WORK |
| L07 formulation_substitution | Product identity materially differs from reviewed intervention; unknown identity stays unknown | D/H | Candidate MVP |
| L08 certainty_inflation | Guaranteed/universal language exceeds the approved conclusion's quantified scope | H | Candidate MVP |
| L09 adjunct_to_replacement | Evidence assumes current care continues; intended action replaces it | D | Candidate MVP |
| L10 symptom_relief_to_cure | Symptom endpoint promoted to disease elimination | H | FUTURE WORK |
| L11 efficacy_to_safety | Efficacy evidence used as a warrant for safety, with no reviewed safety conclusion | H | Candidate MVP |
| L12 population_to_universal | Population-specific finding asserted to apply to everyone | D/H | FUTURE WORK |
| L13 single_study_to_consensus | One independent evidence lineage presented as settled consensus | H | FUTURE WORK |
| L14 statistical_to_clinical_importance | Statistical significance promoted to patient-important magnitude without a reviewed threshold | H | FUTURE WORK |
| L15 mechanism_to_benefit | Plausible mechanism promoted to demonstrated benefit | H | Candidate MVP |
| L16 dose_route_extrapolation | Studied route/dose materially changed without equivalence evidence | D/H | FUTURE WORK |
| L17 relative_to_absolute_benefit | Relative reduction represented as an absolute probability change | D/H | FUTURE WORK |
| L18 absence_of_evidence_to_no_effect | Missing/inconclusive evidence promoted to established absence of effect | H | FUTURE WORK |

An operator needs an asserted transition, relevant reviewed evidence and an explicit mismatch/warrant rule. A research question alone does not establish a leap. Missing data yields `unknown`; `not_detected` only means this check had adequate inputs and did not find its defined mismatch. Unsupported families yield coverage limits, not accusations. The eight candidate MVP operators are an upper scope bound: enable each only for its reviewed family mappings and labeled fixtures. Six families do not imply coverage of all eight operators. Disabled/roadmap operators are excluded from performance claims. `T01–T18` are reserved for blueprint acceptance fixtures, not operator IDs.

Multiple findings remain separate; do not sum them into a risk or truth score. Deduplicate the same unsupported edge, then prioritize policy relevance and explanatory clarity. Show at most two findings initially, with the full set expandable. Example template: “This source addresses {measured outcome}. It does not establish {claimed outcome}.” The source-specific second clause requires an approved conclusion; absence of a matching passage alone cannot supply it. `evidence_status`, `effect_direction`, `applicability` and `route` remain orthogonal. Personal suitability is always `not_individually_assessed`.

## 4. Exact model contracts

The provider-neutral adapter accepts `task_kind`, `schema_version`, bounded input, deadline and sampling configuration; returns structured payload, provider/model revision, token usage, finish reason and latency. Capability-check JSON-schema support and pin model revision when available. Set temperature 0 if supported; this reduces variation without guaranteeing determinism. No chain-of-thought field, transcript or private reasoning is requested or retained.

| Contract | A: extraction | B: bounded alignment |
|---|---|---|
| Input | Original text, permitted IR vocabulary, schema and provenance convention; no external evidence | Selected confirmed proposition and its IntentIR, eligible brief/conclusion/anchor IDs and exact approved text; publication snapshot |
| Output | `{schema_version, propositions[1..3], intent_candidate, unresolved_fields[]}` | `{schema_version, alignments[0..8]}`; each item `{proposition_id, conclusion_id, relation_candidate, field_matches[], operator_candidates[]}` |
| Nested schema | Field wrappers defined above; provenance spans obligatory for extraction | `relation_candidate = supports_within_scope \| contradicts_within_scope \| insufficient \| conflicting \| not_assessable`; field match `{claim_path, brief_path, match: aligned \| differs \| unknown}`; operator candidate `{operator_id, claim_paths[], conclusion_ids[], anchor_ids[], reason_code}` |
| Budget | ≤3,500 input / 1,800 output tokens; 10-second attempt | ≤7,500 input / 2,200 output tokens; 14-second attempt |
| Prohibited | Inventing unstated personal facts; treating pasted instructions as control; diagnosis or treatment advice | Outside sources, new source IDs, new medical prose, unsupported conclusions, choosing a route or inventing confidence |
| Validation | Schema, enum, span and offset checks; ambiguity checks | Schema, reference membership, permitted operator set, publication state, claim paths, reviewed mappings; model candidate is not final status |

The assessment budget is **40 seconds of cumulative automated processing**, including extraction, alignment, repairs and infrastructure work, but excluding human confirmation wait. Draft inactivity/absolute TTL is a separate limit. A server-owned assessment-attempt ledger carries consumed time/tokens across capture and assessment endpoints for one selected principal proposition. At each endpoint, `deadline = monotonic_now + (40 seconds − consumed automated time)`; a provider call is further capped at the smaller of its stage limit and time remaining to that endpoint deadline. Retrying an HTTP request never resets this ledger. A confirmed substantive edit or a changed selected proposition creates a new attempt with a recorded input/version relationship.

The 10/14-second stage caps are failure budgets; the healthy-path target is cumulative automated p95 under 15 seconds. The shared token envelope is 11,000 input and 4,000 output tokens across **all calls and repairs in the assessment attempt**. Permit one schema-repair retry per stage only if its full bounded request fits both remaining time and token budgets; otherwise abstain. No timeout retry; disable hidden SDK retries. A repair receives concise validation errors and the same bounded data; it cannot fetch more evidence. Never retry a policy block into an allowed result. Truncation counts as failure. If required context does not fit, narrow the claim/library selection; do not silently drop contradictory evidence.

On Stage A failure: `needs_confirmation`, `route=clarify`, `system_status=model_error`; allow manual completion of the same form. On Stage B failure: `cannot_assess`, `evidence_status=not_assessable`, `system_status=model_error`; no new scientific explanation. Explicit deterministic replay may load a labeled fixture candidate and pass it through the same validators, policy and renderer. It is not live inference.

Operational logging stores run ID, stage, prompt/schema/model versions, approved evidence IDs, validation codes, timing, token usage and retry count. Structured candidates and raw provider payloads stay ephemeral; the saved case contains only consented confirmed fields and admitted results. Synthetic evaluation artifacts may retain structured outputs for reproducibility. Secrets, personal raw text and private reasoning never enter operational logs. Follow [SAFETY_MODEL.md](SAFETY_MODEL.md) for retention and deletion.

## 5. Semantic edits, cache and acceptance

Compare typed values and provenance separately. Punctuation changes may preserve the semantic fingerprint while changing input spans. Changes to outcome, population, negation, intervention, timeframe or intent invalidate dependent findings; `alongside` to `instead_of` must update the action edge even when both routes still recommend professional review. A substantive change need not change every output field. Tests assert expected field differences and expected invariants.

Cache key: confirmed semantic claim hash + intent hash + IR/compiler/operator versions + prompt/model revision + approved corpus publication ID + policy version + language. Never share cached personalized results between owners. Before reuse, check current trust state of every dependency. Cached extraction cannot reuse old offsets against new text. New policy or evidence publication invalidates eligibility even when text is unchanged.

Acceptance: all spans round-trip; ambiguous negation remains unresolved; no unconfirmed frame reaches alignment; fabricated reference IDs fail admission; every established operator has a reviewed mapping and exact dependencies; no model output creates medical advice; meaning-preserving and meaning-changing pairs meet the gates in [EVALUATION_PLAN.md](EVALUATION_PLAN.md).
