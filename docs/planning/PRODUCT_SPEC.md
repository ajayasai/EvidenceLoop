# Product specification

Status: PROPOSED, 30 September 2026. Primary input: EvidenceLoop Implementation Blueprint, all 42 PDF pages, especially printed pages 1-8 and 16-19. All software behavior described here is planned. No application, approved evidence pack, clinical review or user-study result is claimed.

## The product we are building

EvidenceLoop is a bounded educational web application for adults managing type 2 diabetes and their caregivers. It takes one selected principal health claim, confirms the proposition and the person's intended action, compares that exact combination with a reviewed evidence brief, makes any unsupported inference visible, produces an inspectable receipt, and lets the person save a professional question and return for one check-in and a reasoning-transfer exercise. Up to three propositions may be extracted for selection, but distinct unselected claims are labeled unassessed; safety screening considers the full input.

The submission demonstrates this with fictional scenarios and synthetic accounts. It does not establish personal treatment suitability. The product hypothesis is improved understanding of the evidence-to-action gap; the competition can establish engineering behavior and possibly formative usability, not better long-term health.

## The core distinction

A message can accurately report a measured effect but overstate the clinical outcome or justify an untested action. Model the chain as mechanism -> measured effect -> clinical outcome -> scenario applicability -> action justification. Each transition needs a warrant. Not every claim traverses every node; the graph must allow missing, irrelevant and uncertain edges.

The quoted message's recommendation, the user's endorsement of that recommendation, and permission to save information are three separate objects. Someone asking about a forwarded replacement claim may intend only to learn. A supported narrow claim may still lack evidence for individual use. These distinctions drive the interface and tests.

Related scientific claim verification already exists: [SciFact](https://aclanthology.org/2020.emnlp-main.609/) provides claim/evidence verification research. The defensible contribution to test is action-aware structure, named warrant checks, governed receipts, semantic-edit testing and a consented follow-through loop. Superiority to retrieval alone must be measured with a same-model baseline.

## Scope and ruthless cut line

| Tier | Included work | Completion condition |
|---|---|---|
| MUST HAVE | Text capture, one principal proposition plus necessary linked subclaims, confirmation and separate intent | Novel wording within approved scope completes the flow; ambiguity cannot silently become a confirmed fact |
| MUST HAVE | Six target claim families, versioned approved briefs and passage anchors | Only families actually reviewed may appear as approved; minimum fallback scope is three, with explicitly smaller evaluation claims |
| MUST HAVE | Compiler, active mismatch operators, bounded renderer, separate evidence/applicability/action/system states | No truth score; no display before admission checks |
| MUST HAVE | Receipt with visible uncertainty and source inspection | Every substantive assertion maps to an approved conclusion/anchor or policy template |
| MUST HAVE | Professional-question preview, consented save, later retrieval, check-in and one reviewed transfer exercise | Decline creates no persistent personal record; completion is labeled self-reported |
| MUST HAVE | Meaningful-edit and harmless-edit comparison, supported and uncertain cases | Diff reflects semantics; unchanged route can be correct |
| MUST HAVE | Minimal reviewer publish/withdraw, ownership checks, deletion, safety gates and failure states | Negative-path tests pass before public demonstration |
| MUST HAVE | Reproducible evaluation, version manifest, error ledger and honest demo labels | Report actual denominators, limitations and remaining failures |
| SHOULD HAVE | Synthetic recall through dependency lookup, reviewer decision and revised receipt | Attempt only after core gates; never pretend a real paper was retracted |
| SHOULD HAVE | Small formative usability check with fictional tasks | Appropriate oversight/consent available; otherwise internal reviewer walkthrough |
| SHOULD HAVE | Counterfactual explanation of why a phrase changed the result | Derived from structural diff and existing evidence, no extra unrestricted generation |
| COULD HAVE | Second reviewed question template; print-friendly receipt; one manually reviewed source challenge | No regression in core gates or schedule |
| DO NOT BUILD BEFORE SUBMISSION | OCR/screenshots, voice, multilingual support, multiple conditions, wearables, glucose analytics, diet/dose planning, diagnosis, autonomous triage, medication reminders, product recommendations | Explicitly excluded |
| DO NOT BUILD BEFORE SUBMISSION | Live web retrieval, vector database, graph database, autonomous agent debate, fine-tuning, automatic source watcher, automatic notification channels, external sharing, EHR/care-plan import, experimental routine lab | No need for the central demonstration |

One question-preparation template is enough to demonstrate a useful saved step. An existing-goal coach would expand the safety surface; it is deferred despite appearing in the blueprint's broader scope. A reviewer dashboard is a basic queue/detail/action page, not a full content-management product.

## Acceptance journey

1. Paste a clearly fictional message. The capture screen labels the session ephemeral and explains the approved topic boundary.
2. The extractor returns the principal proposition, original highlighted span and attributed message action. The user confirms or edits it and chooses curiosity, add-on, replace, stop, delay, other or unknown intent. An edit creates a new version.
3. If meaning or action is still ambiguous, ask one question whose answer changes interpretation or routing. Offer "prefer not to say"; unresolved material ambiguity leads to a limitation, not an invented answer.
4. Retrieve a complete approved brief with supporting and limiting anchors. Compare population, intervention, comparator, outcomes, duration, causality and certainty.
5. Display what is supported, what remains unestablished, and why the user's intended action matters. Distinguish library coverage from evidence insufficiency and contradiction.
6. Expand Spot the Leap: show the exact source facet and claim facet connected by a named unsupported transition. Unknown checks are labeled unknown. Source authenticity is separate from support.
7. Open the receipt: preserved passage/context, limitations, review date, current review status, AI-assisted assessment label and version IDs.
8. Optionally choose a concern such as cost or burden; this selects a professional-question template without inferring motives. Preview the exact question. Saving requires an explicit action and purpose-specific consent.
9. Reopen My next step, retrieve the saved item, and record done_self_reported, deferred, abandoned or needs_revision. A "Something changed" control opens reassessment; optional new concern text is ephemeral, reruns safety gates and is never saved as a symptom record. No outcome or adherence claim follows.
10. Offer one optional new reviewed reasoning item. Explain its answer; do not assign a gullibility or trustworthiness score.
11. Edit "alongside" to "instead of" and separately edit punctuation. Re-run extraction/confirmation/comparison and display substantive field changes. Punctuation controls do not waive validation.

## Minimum interface

| Screen | Hierarchy and interactions | Loading, uncertainty and failure |
|---|---|---|
| Check this advice | Scope line -> text input -> optional citation identifier (not auto-fetched) -> check button -> highlighted interpretation -> explicit intended action -> confirm | Name the stage without streaming medical text. Preserve user input on recoverable failure. Expired draft offers restart. Ambiguity shows alternative interpretations, not confidence percentages. |
| What the evidence allows | Separate action banner if needed -> supported scope -> missing warrant -> visible uncertainty -> Spot the Leap diagram with text equivalent -> receipt panel -> next-step choice | Cannot-assess explains library/model/integrity reason distinctly. Under-review badge overrides stale receipt display. Never show a green safety badge because a narrow claim is supported. |
| My next step | Preview/consent before initial save; then saved question -> due preference if used in-app -> self-report controls -> optional reasoning exercise -> delete | Persisted state only after server acknowledgment. Failed save retains preview, not a success toast. Deferred/abandoned are normal choices. Simulated timeline label stays attached to every synthetic event. |
| Reviewer | Queue by integrity/materiality/freshness -> source diff and anchored context -> brief conclusions and caveats -> approve/return/withdraw -> audit history | Approval requires role and expected version. No batch blind approval. Conflicts block publication and show changed revision. Review of a brief is never described as review of every AI answer. |

Use one-column mobile layouts, keyboard-accessible expansion controls, visible focus, meaningful headings, text alongside all color states and roughly 44 px targets. Announce completion/status through accessible live regions without reading speculative output. Keep citations adjacent to claims and expose preserved context before external navigation. Target [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/) and record actual audits; do not claim conformance from a component library.

No medical-dashboard charts, streaks, urgency badges for ordinary uncertainty, or engagement leaderboards. Users can leave without saving. Display generic prompts on any later reminder surface; external reminders are out of MVP scope.

## Additional useful innovations, ranked

These are proposed design improvements, not claims of first invention. Several extend ideas already present in the blueprint.

| Priority | Idea | Tier | Implementation / test |
|---|---|---|---|
| 1 | Field provenance ledger | MUST BUILD | Every critical field records exact span, user confirmation or reviewer source. Test that normalization never changes negation or attribution without a visible revision. |
| 2 | Reason-for-change receipt | MUST BUILD | Live edit links changed fields to changed operator result and caveat. Test alongside/instead and negation independently of route equality. |
| 3 | Minimal missing-evidence question | OPTIONAL DIFFERENTIATOR | Render reviewer-authored "what evidence would change this" beside a leap; verify it names the relevant comparator/outcome without inventing a study requirement. |
| 4 | Reasoning invariants on simplified copy | OPTIONAL DIFFERENTIATOR | Readability mode changes wording only from two reviewed variants with identical mandatory fields. Compare comprehension and qualifier preservation. No extra LLM call required. |
| 5 | Source-overlap cue | OPTIONAL DIFFERENTIATOR | Surface manually tagged shared study families so multiple reports do not appear to be independent support. Audit provenance on a tiny example. |
| 6 | Symmetric self-audit | OPTIONAL DIFFERENTIATOR | Apply the compiler to the project's own usability-versus-health-outcome claims using a separate nonclinical evaluation brief. Show only actual results. |
| 7 | Recall rehearsal ledger | OPTIONAL DIFFERENTIATOR | Store a synthetic event, impact set and reviewer decision with repeat-run idempotence; demonstrate that affected and unaffected receipts separate correctly. |
| 8 | Transfer-error feedback for reviewers | POST-COMPETITION | Aggregate consented exercise error categories to improve wording; suppress tiny groups and never label individuals' susceptibility. Test whether reviewer effort and comprehension improve. |

Do not add all optional ideas to the deadline. The first two are implementation details of the core workflow; the rest compete for the same reserved time.

## What judges may challenge

Reviewer-unavailable fallback is explicitly limited: keep synthetic health-workflow rehearsals internal, and use only architecture/nonclinical abstract examples publicly. It does not meet the planned reviewed-health-example release gates.

"This is rules plus RAG": show the same-model basic-retrieval comparison, exact action distinction and a failure case. "A curated library is cherry-picked": publish scope, selection/exclusion log, conflicts and no-coverage behavior. "A citation is still not proof": agree and show human support audit and source limitations. "One check-in is not long-term benefit": show functioning persistence while explicitly limiting the claim to demonstrated workflow. "Clinical reviewer unavailable": remove approval claims and present a synthetic engineering demonstrator. "Novelty is unproven": describe the combination and measured behavior, with prior work acknowledged.
