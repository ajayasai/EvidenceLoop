# EvidenceLoop demo plan

Status: PROPOSED, 30 September 2026; unimplemented and unvalidated. DECISIONS.md governs scope and states. Public demos use synthetic adult type 2 diabetes/caregiver scenarios and English educational content.

## Demonstration promise

Show a complete journey: confirm a health claim, separate evidence from intended action, inspect a receipt, save a professional question, and return to it. The intended benefit is better preparation for care conversations. Do not promise improved glucose control, adherence, clinical safety, or patient outcomes.

The proposed four-minute walkthrough is a rehearsal constraint. The official optional video is 5–8 minutes; add architecture, genuine sponsor-tool usage and limitations. Verify finalist presentation/Q&A time separately. SPONSOR_VERIFICATION.md records provenance and unresolved requirements.

## Case preparation and review

Prepare a clearly marked fictional social post: “Some cinnamon studies reported lower fasting blood sugar, so cinnamon can replace my metformin.” The first clause is deliberately narrower than the action inferred from it. The presenter must identify it as a synthetic claim to examine, never as advice or a genuine quotation from a patient.

[NCCIH's diabetes and supplements overview](https://www.nccih.nih.gov/health/diabetes-and-dietary-supplements-what-you-need-to-know) describes suggestive findings alongside limitations and variation across studies. Its [cinnamon fact sheet](https://www.nccih.nih.gov/health/cinnamon), content updated November 2024 and inspected 30 September 2026, says benefit for diabetes remains uncertain and notes differences between cinnamon products. These are candidate source documents, not an approved EvidenceLoop evidence pack. Their summaries motivate this example; they do not establish medication substitution, individual suitability, or a causal result for this fictional person.

Before recording, a qualified reviewer must approve source snapshots, exact passages, conclusion mappings, scenario boundaries and the displayed language. Preserve publication/update dates separately from retrieval and review dates. Do not assign `conflicting` simply because studies differ, or `no_effect` because a result is nonsignificant. The reviewer must decide the proposition-level evidence status; unresolved review means the case stays unavailable for an evidentiary demonstration.

Have a second short example ready: a reviewer-approved, limited statement about cinnamon in ordinary food amounts, with a personal-treatment question explicitly left unassessed. This can demonstrate support within scope without endorsing supplement use. An invented product called “Glucora-47” provides the separate no-coverage case; label the product fictional. Its absence from the approved library must produce `no_matching_approved_evidence`, not a claim that no scientific evidence exists anywhere.

## Four-minute run of show

| Time | Presenter action | Observable acceptance criterion |
|---|---|---|
| 0:00–0:20 | Identify Healthcare Challenge 2, educational scope, synthetic data and current live/replay mode. State the patient problem in one sentence. | Mode and scope are visible before input. No diagnosis or treatment promise. |
| 0:20–0:55 | Paste the synthetic post. Show the compiler's proposed frame: population, intervention/product, comparator, outcome, timeframe, qualifiers and intended action. Confirm or correct it. | Missing species, formulation or timeframe stays unknown. Assessment uses the exact confirmed frame version. |
| 0:55–1:30 | Open result, reasoning-leap panel and receipt. Point to the narrow observation and unsupported replacement inference. | Scientific relation, action route, coverage and system status are separate. A citation opens the reviewed passage and source version. |
| 1:30–2:05 | Edit the intent live from “instead of” to “alongside” prescribed treatment; confirm again. Make a punctuation-only edit as a control. | Material intent edit invalidates the old assessment. Safety reasoning changes where warranted; both versions may still recommend professional review. Punctuation alone does not invent a new clinical distinction. |
| 2:05–2:30 | Show the limited supported example, then the fictional unknown product. | Support remains scoped. Unknown coverage produces an honest boundary and no invented source or confidence score. |
| 2:30–3:15 | Select the professional-question template, explicitly save, reopen, and advance the demonstration clock to a later check-in. | Consent precedes persistence; the saved receipt is retrievable. “Simulated later check-in” is visible. Self-report is labeled and stored with the correct state. |
| 3:15–3:40 | Complete one reviewed transfer exercise using a new sentence with the same observation-to-action gap. | Feedback explains the distinction; it does not prescribe a health action. Correctness comes from an approved answer key. |
| 3:40–4:00 | Show architecture boundary, actual evaluation status and one limitation. | Report only completed counts and measured results, with commit, corpus and run identifiers. |

If preloading the second example, distinguish its saved result from fresh inference. Do not splice outputs or accelerate indicators to imply lower latency.

## Receipt and longitudinal interaction

The receipt exposes confirmed proposition/intent, source versions, approved conclusion mapping, assessment/model/prompt versions, policy decision and timestamp. It records provenance, not medical certification. Show concise admissible reasons and passages, without internal chain of thought.

The only core next step is a question such as “What should I ask my pharmacist about this cinnamon claim and my current medicines?” Review the template before inclusion. Save only after purpose-specific consent; do not persist raw draft input merely to make the demo convenient. Returning to the saved record must recheck source trust and ownership. A check-in may record `done_self_reported` or `deferred`; neither proves a consultation occurred. Show a reviewed transfer exercise, not a claim that one successful answer demonstrates lasting learning.

## Replay and optional recall

If inference fails, display `model_error` or `unavailable`, then offer an explicitly labeled recorded fixture replay. Fixtures replace only extraction/alignment responses for enumerated inputs. They must continue through the same claim confirmation, policy checks, evidence-version validation, ownership checks, deterministic renderer and persistence rules. An unmatched novel input cannot receive a fabricated fixture answer. A network outage must not silently activate replay or bypass a withdrawal. Present latency as replay latency and make no novel-language AI claims.

Keep the recall demonstration in an optional appendix. In a separate synthetic evidence namespace, a reviewer withdraws a demo source version with a fictional reason; reopening the saved case then exposes the current trust state and blocks reuse where required. Explicitly say this is simulated withdrawal, not a real NCCIH correction. Preserve the historical receipt without showing it as current. Cut this appendix before cutting confirmation, honest uncertainty or the longitudinal loop.

## Rehearsal checklist

- [ ] Developer: complete the core journey three consecutive times after clean synthetic resets; retain a run log and screen recording. Acceptance: no hidden manual database fixes; fallback is a labeled recording of the last verified build.
- [ ] Clinical reviewer: approve every visible medical sentence and exercise key. Evidence: dated approval and source-version mapping. Fallback: remove the case or show architecture only.
- [ ] Evaluation owner: reconcile every displayed denominator with exported run artifacts. The 60 scenarios and 30 sentinels in DECISIONS.md remain targets until completed. Fallback: state “evaluation incomplete” and disclose actual reviewed/run counts.
- [ ] Presenter: rehearse four minutes plus questions, and record a separate 5–8-minute submission cut. Evidence: timed recording; fallback: omit recall and presentation extras.
- [ ] Submission owner: scrub footage, browser tabs, logs, receipts and sponsor screenshots for credentials or real health data. Acceptance: synthetic-only public bundle with permissions checked; fallback: rerecord affected portions.
