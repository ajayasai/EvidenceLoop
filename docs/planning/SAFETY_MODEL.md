# EvidenceLoop safety model

Status: **PROPOSED**, planning only. No control below is implemented, tested, independently reviewed, or clinically validated. [DECISIONS.md](DECISIONS.md) owns the enums. [CLAIM_COMPILER.md](CLAIM_COMPILER.md) owns extraction and L01–L18 operators. This model defines release conditions for an English, adult type 2 diabetes educational demonstration using synthetic users and a bounded reviewed library.

## Intended use and authority

EvidenceLoop explains the gap between an evidence proposition and an intended action. It does not determine personal suitability, diagnose, prescribe, optimize a dose, assess emergency severity, or authorize starting, stopping, replacing, or continuing treatment. Even `supports_within_scope` with `scenario_aligned` means personal suitability is `not_individually_assessed`. The next-step template is a question for a qualified professional, never a medication instruction. Avoid blanket “continue your treatment” language: the system cannot establish whether ongoing care is appropriate, particularly when a user raises an adverse reaction.

The model proposes extracted fields and evidence alignments. Application code decides policy, authorization, trust state, and admissible output. Human review approves evidence mappings and safety wording; user confirmation approves what the user meant, not a medical conclusion. Reviewed sources remain untrusted as instructions. A citation or matching hash establishes identity, not scientific entailment.

## Blueprint principles and implementation gates

The blueprint's **P001–P012** retain their original meaning. Gate IDs **G01–G12** below are implementation controls; leap operators use **L01–L18**, and blueprint acceptance fixtures use **T01–T18**.

| Blueprint principle | Enforcement / evidence |
|---|---|
| P001 Approved current briefs only | G09 eligibility and transaction checks |
| P002 Missing evidence is not evidence of absence | G08 wording; separate coverage and evidence states |
| P003 Quoted claim is not confirmed intent | G07 confirmation and explicit attribution |
| P004 An existing citation does not prove support | G10 admission plus independent sentence-support audit |
| P005 General support is not personal suitability | Fixed `not_individually_assessed`; G03–G05 scope |
| P006 No autonomous medication, dose, or treatment change | G02–G03 and bounded next-step templates |
| P007 Urgency can supersede educational flow | G01 takes route precedence |
| P008 No personal write/share without consent | G11 transactional consent; sharing deferred |
| P009 Review materiality before notices | G09 recall review and explicit notice eligibility |
| P010 System failure is not a scientific verdict | G09–G10 operational states |
| P011 Source review is not review of every AI answer | Receipt shows exactly what was reviewed; never label an AI response clinically approved merely because its sources were reviewed |
| P012 New evidence can amend or withdraw conclusions | G09 and G12 source/receipt rechecks and historical version preservation |

## Deterministic policy contract

The decision contains `case_state`, `route`, `coverage`, `evidence_status`, `effect_direction`, `applicability`, `system_status`, all triggered policy IDs, reason codes, required confirmation fields, input/claim/policy versions, and permitted next-step kind. Do not overload one field with another field's meaning. A template may display several reasons but may not lower the highest required route.

All safety-relevant facts carry `present`, `absent`, or `unknown`, with an input span and provenance. Absence of a keyword is not evidence of absence. Explicit structured user answers take precedence over an extraction proposal only after contradictions are resolved; a later answer cannot silently erase earlier serious-concern content. Quoted third-party claims are distinct from a user's present symptoms or intended action. Ambiguous negation, sarcasm, conflicting statements, or obscured intent become `unknown`.

| Policy | Trigger and deterministic consequence |
|---|---|
| G01 | An explicit current emergency concern or serious adverse-reaction concern triggers `urgent_escalation`; interrupt ordinary assessment and next-step saving. Render a fixed, reviewer-approved message to seek urgent professional help using local emergency services where appropriate. Do not score severity, name a diagnosis, promise safety, request more symptom details, or delay the message behind model inference. If the time/context of a serious concern is unclear, show the precautionary help message plus a minimal context clarification; never claim an emergency has been ruled out. |
| G02 | A stated plan to stop prescribed medication or prescribed care triggers `professional_review_recommended`. No endorsement or schedule for stopping or continuing. Ask the user to discuss the proposed change with the prescribing professional; G01 overrides when an acute concern is present. |
| G03 | A stated replacement of prescribed care, dose adjustment, personalized prescribing request, or asserted cure as a reason for replacement triggers `professional_review_recommended`. A source studying an adjunct cannot authorize replacement. Educational comparison may remain available only if the other gates pass. |
| G04 | A pregnancy-related scenario is outside the approved MVP population: `cannot_assess`, `professional_review_recommended`, and `not_assessable`. Do not infer absence of pregnancy from missing text or ask for unrelated sensitive history. |
| G05 | A pediatric scenario is outside the adult scope: the same response as G04. Unknown age needs confirmation only where age determines the scenario's eligibility; do not collect date of birth. |
| G06 | Product, ingredient, formulation, route, or relevant identity is uncertain: `needs_confirmation` / `clarify`, with no evidence equivalence inferred. If unresolved, `cannot_assess`; a proposed health action also warrants professional review. Brand resemblance, a shared ingredient word, or a user-supplied URL cannot prove product equivalence. |
| G07 | Missing or contradictory intended action, unresolved stopping/replacement intent, or ambiguous negation blocks assessment: `needs_confirmation` / `clarify`. Preserve `unknown`; never default to add-on use. If explicit stopping/replacement is already present, retain its professional route while clarifying. |
| G08 | Out-of-scope condition, language, or unmatched approved evidence yields `cannot_assess`, `coverage=no_matching_approved_evidence`, `evidence_status=not_assessable`, and `effect_direction=undetermined`. Explain library limits without claiming no scientific evidence exists. Use `clarify` only if a specific missing fact could establish coverage; otherwise general educational signposting or professional review for an intended health action. |
| G09 | Unapproved, withdrawn, superseded-but-unreviewed evidence, changed trust state, broken anchors, or a dependency/version mismatch blocks a current scientific result: `coverage=blocked`, `not_assessable`. Set `system_status=evidence_under_review` for review holds or `evidence_integrity_error` for integrity failures. Historical receipts may show their old assessment clearly marked unavailable as current guidance. |
| G10 | Invalid model schema, invented source/anchor, unapproved conclusion, unsupported generated fact, or injected instruction fails output admission. Use one budget-bounded schema repair when permitted. After Stage A extraction failure, use `needs_confirmation`, `route=clarify`, and `system_status=model_error`; allow the same manual confirmation form if feasible. After Stage B alignment failure, use `cannot_assess`, `evidence_status=not_assessable`, and `system_status=model_error`. A higher independently detected safety route remains visible. No raw model answer is rendered as fallback. |
| G11 | Missing ownership, authentication where required, purpose-specific consent, or current save eligibility rejects the read/write. Return a generic authorization error without confirming another user's record exists. Reading does not create consent; agreeing with a claim does not authorize storage. |
| G12 | Recompute policy and trust at capture, confirmation, assessment admission, receipt retrieval, save, and check-in. Stale confirmation or versions require reassessment. An active global/family/provider kill switch blocks affected assessment and save paths; fixed safety/help messaging and authorized deletion remain available. |

Routes compose as `urgent_escalation > professional_review_recommended > clarify > education`. This ordering never bypasses authorization or evidence blocks: an urgent message can accompany `cannot_assess` and `coverage=blocked`. Scientific assessment needs a confirmed frozen frame, resolved material ambiguity, scope eligibility, approved evidence, valid mappings, and valid output. ClaimIR may extract 1–3 propositions, but the user selects **one principal proposition per assessment**; other distinct claims are visibly not assessed. The global safety route screens all supplied content, so selecting an assessable proposition cannot conceal a dangerous action in another.

Raw-input screening runs before any model request. Structured output is screened again afterward because linguistic extraction may reveal an intent the first check missed. Model flags may add a constraint; they cannot remove deterministic flags. Exact triggers and help wording require qualified review before public use; a keyword list alone is insufficient. This architecture does not claim comprehensive emergency detection.

## Evidence and interaction boundaries

Benefit, no effect, harm, mixed findings, insufficiency, and conflicting evidence remain separate from support for the precise user proposition. A nonsignificant result alone is insufficient to establish no effect: a threshold on a p-value cannot alone settle a scientific conclusion. [ASA statement](https://www.amstat.org/docs/default-source/amstat-documents/p-valuestatement.pdf) Source trust changes invalidate current eligibility, including cached and saved views. G09 is checked in the final transaction to prevent an approval/withdrawal race. The recall workflow shows reviewed changes in the explanation; it never automatically instructs a treatment change.

An urgent route suppresses persuasive visual scoring, routine check-ins, and “save this plan” prompts. Professional routes offer only the approved professional-question next step. Check-in may accept optional `new_concern_text` and `request_reassessment`: new concern text remains ephemeral, undergoes safety screening, and is never persisted with the check-in. Changed circumstances reopen confirmation before reassessment; an urgent concern supersedes routine completion. Completing a step is `done_self_reported`, not verified adherence or improved health. A reasoning exercise cannot supply personal treatment advice or reward a user for agreeing with the system.

## Trust, security, and access design

Prompt instructions are insufficient protection against prompt injection; OWASP explicitly includes attacks embedded in retrieved external material and recommends constrained outputs, privilege controls, and adversarial testing. These are design inputs, not a security certification. [OWASP LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

The runtime model has no browser, shell, filesystem, database, notification, publication, or reviewer tool authority. It sees only the minimum structured case and selected approved passages. Runtime input URLs remain text; the server does not fetch user/model URLs. Reviewer imports use uploaded, size-limited files or a separately reviewed ingestion process; no arbitrary URL fetcher ships. Render escaped text and application-generated citations only; reject executable HTML, Markdown images, and model-generated links. The server constructs links from reviewed source metadata. Bound request length, model tokens, retries, and processing time. The 40-second limit measures cumulative automated work across extraction/alignment, excluding human confirmation dwell. Each endpoint receives only the remaining reserved time/token budget; aggregate limits are 11,000 input and 4,000 output tokens including repairs.

Role boundaries are explicit: an owner reads/deletes only their own saved objects; an evidence reviewer imports, reviews, approves, or withdraws evidence; an operator manages deployment, incidents, and kill switches. A reviewer has no default access to saved personal cases, and an operator cannot fabricate a clinical approval. Server-side checks cover every object, nested receipt dependency, and export. Use least-privilege database credentials, secret storage outside prompts/client bundles, TLS, secure session cookies, CSRF protection for cookie-authenticated mutations, restricted origins, rate limits, and audit events. Verify these in implementation; they are not assurances that a deployment is secure. Reviewer authentication and publication checks are mandatory even in a minimal UI.

## Data ownership, consent, and retention

Before Save, an opaque session handle resolves only to server memory. Proposed expiry is **30 minutes of inactivity**, with a two-hour absolute cap; restarting the single MVP process loses unsaved drafts. Do not use local storage, analytics events, access-log query strings, or model traces as accidental persistence. Expiry clears raw text, frames, receipts, and model buffers. Explain this behavior at capture.

Save requires an authenticated owner or appropriately secured demo identity and explicit consent to the named purpose: retaining this receipt and professional-question next step for retrieval/check-in. Promote all necessary versions and the consent record in one transaction. Keep an expiry preview; proposed saved retention is **30 days of inactivity**, reset only by explicit owner interaction, with delete available immediately. Recall notifications are separately opt-in; MVP in-app status does not require email/phone collection. Do not make product use contingent on research consent.

Public submission uses synthetic data. Accidental real data is removed, not silently adopted as a research sample. Saved raw input is excluded by default; retain only the confirmed minimum representation, evidence dependencies, and user-approved step. Provider retention, regions, subprocessors, training use, and deletion controls are **NEEDS VERIFICATION** before sending real health content. An “ephemeral” application session does not imply zero provider retention.

Operational logs retain request IDs, timestamps, policy IDs, model/prompt versions, token counts, latency, error categories, and dependency hashes; no raw claim, symptom text, full prompts, private reasoning, or identifiers unnecessary for troubleshooting. Proposed log retention is seven days. Evidence review/version audit records may persist for provenance; never attach personal case content to them. Deletion removes owned cases, receipt/step/check-in links, caches, and diagnostic artifacts, leaving only a non-content deletion event. If backups are enabled, specify their separately disclosed expiry, prohibit recovery into active service without reapplying deletion tombstones, and test the process before real-data use.

## Hazard review and release safety case

| Hazard | Prevention / detectable failure | Required evidence |
|---|---|---|
| H01 Unsafe action endorsement | G01–G07, bounded next-step templates, output rejection | All relevant sentinels pass; reviewer signs wording and failure examples |
| H02 Incorrect scientific certainty | Enabled Lxx operators, reviewed conclusion mapping, independent sentence support check | Status/operator metrics and source-level provenance audit |
| H03 Stale or wrong evidence displayed | G08–G09, version checks at admission and retrieval | Withdrawal, anchor corruption, cache and transaction-race tests |
| H04 Injection or data disclosure | G10–G11, no model tools, escaped output, ownership checks | Adversarial and cross-owner negative tests |
| H05 Follow-through creates clinical authority | G02–G03 and G12 at check-in | End-to-end edits, new adverse concern, and consent-revocation tests |
| H06 Safe-looking failures hide a broken system | Explicit `system_status`, separate abstention/completion metrics | Timeout/provider outage drills and monitored error counts |

The release safety case is a small reviewed packet: intended use, hazard table, approved evidence manifest, policy/template versions, test report, known failures, reviewer identity/date, and rollback owner. The developer demonstrates enforcement; a qualified reviewer approves evidence and clinical-facing wording. Neither substitutes for the other. With no qualified reviewer, health-related synthetic engineering work stays internal. Any public fallback is limited to architecture or a nonclinical abstract demonstration, with no health advice, health assessment output, or clinical-performance claim.

Any unsafe action endorsement, fabricated citation reaching the UI, ownership breach, or withdrawn source served as current triggers stop-release and the appropriate kill switch. Preserve content-minimized incident metadata, reproduce with a synthetic case, identify affected versions/dependencies, fix, rerun the failing case plus all sentinels, and obtain reviewer reapproval for clinical changes. Resume only after documented sign-off. Remaining risk includes missed language, incomplete library coverage, reviewer error, and limited benchmark diversity; no passing score establishes clinical safety.
