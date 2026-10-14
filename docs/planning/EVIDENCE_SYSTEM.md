# Approved evidence, receipts and recalls

Status: PROPOSED; no evidence library has been clinically reviewed or published. [DECISIONS.md](DECISIONS.md) governs all state names. The submission uses a bounded library and synthetic users. Internet search is a reviewer acquisition aid, never an unrestricted runtime knowledge source.

## 1. Library boundary and ownership

Plan six evidence-family slots `F01–F06` and 6–10 distinct source documents, subject to qualified reviewer availability. A family is a retrieval/evaluation grouping, not a guaranteed clinical conclusion. Initial candidates can cover mechanism versus benefit, biomarker versus clinical outcome, association versus causation, studied formulation versus commercial product, certainty language, and adjunct versus replacement. Several families can share source documents; count independent underlying evidence, not URLs. Allocate entire connected source-overlap components to one evaluation split, even if this reduces the number of independent test families.

The [NCCIH overview on diabetes and dietary supplements](https://www.nccih.nih.gov/health/diabetes-and-dietary-supplements-what-you-need-to-know) is a verified public candidate for a limited supplement illustration. Its existence does not establish approval for any particular EvidenceLoop conclusion. A qualified reviewer must select exact passages, check scope and permissions, and approve mappings. No synthetic example in this package is a medical finding or a completed review.

Roles: an editor imports source material and drafts briefs; a qualified evidence reviewer approves scientific scope/mappings; an administrator manages access and operational withdrawals. The developer may seed synthetic fixtures but cannot label their own medical interpretation independently reviewed. Without a qualified reviewer, health fixtures are limited to internal synthetic rehearsal; a public fallback shows architecture or a nonclinical abstract demonstration without health content. Do not manufacture an approved clinical library.

## 2. Immutable entities and relational contracts

| Entity | Required fields and relationships |
|---|---|
| Source | `source_id`, canonical URL/DOI, title, publisher, source type, licensing note, `origin_group_ids[]`; mutable registry metadata is separately audited |
| SourceVersion | `source_version_id`, source FK, previous-version FK, retrieved timestamp, publication/update dates if stated, content hash, extraction version, snapshot location, language; immutable content |
| Anchor | `anchor_id`, source-version FK, exact quote, quote hash, normalized-text half-open code-point offsets, PDF page and bounding box when available, section label, original-file locator; extraction mapping retained |
| ClaimFamily | ID, name, reviewed aliases, enabled operators, scope restrictions, evaluation split group |
| EvidenceBriefVersion | ID, prior-version FK, family FK, reviewed population/intervention/comparator/outcome/timeframe, study design, limitations, review-due date, versioned quality appraisal and appraisal method |
| Conclusion | ID, brief-version FK, bounded statement, outcome ID, `effect_direction`, certainty wording, scope, anchor IDs, allowed claim relations, operator warrant/mismatch mappings, exclusion notes |
| Review | ID, reviewed entity/version IDs, reviewer identity/qualification declaration, decision, rationale, timestamp, conflict-of-interest disclosure, materiality decision when relevant |
| Publication | ID, exact approved brief/source/conclusion IDs, policy-compatible schema version, approver, committed timestamp; immutable snapshot |
| TrustEvent | ID, entity/version ID, event type, reason, actor, timestamp, superseding version; append-only lifecycle history |
| Dependency | Child type/version ID, parent type/version ID, role (`supports`, `limits`, `conflicts`, `rendered`, `context`); unique directed edge |

Every scientific conclusion has at least one precise anchor and a reviewed entailment mapping. An anchor verifies identity/integrity, not that the passage supports the claim. Human review and sentence-support evaluation address that separate question. A citation to a whole web page is insufficient for receipt-level traceability. Keep source snapshots in private storage only where licensing permits; otherwise retain a lawful short quotation, metadata and extraction/hash evidence. If the necessary traceability cannot be retained, omit that source from the core library.

These are logical entities, not a demand for additional database tables. In [ARCHITECTURE.md](ARCHITECTURE.md), `ClaimFamily` lives in the versioned pack manifest; `Conclusion` is an ID-bearing typed object within `evidence_briefs.conclusions_json`; `TrustEvent` is an append-only `audit_events` record whose current projection is `evidence_state`; and `Dependency` is represented by `brief_anchors` plus `assessment_evidence` and their source-version foreign keys. Publication validates global conclusion-ID uniqueness and every embedded reference. These joins must include limiting, conflicting and considered context dependencies even when a passage is not displayed.

Evidence packets are separate from ephemeral user input. Retain the permitted source quote and sufficient normalized surrounding context, source-version hash, original document locator, normalized offset base and normalization/extraction version for as long as a published or retained historical receipt depends on them. Packet-local offsets map explicitly to source-document offsets. Raw-user-text expiry never deletes or reinterprets source anchors; if source rights prevent this minimum packet, that source is ineligible.

`origin_group_ids` join systematic reviews, summaries, trials and republished pages that share underlying evidence. A summary and its cited trial are not independent replications. Reviewers record partial overlap and uncertainty; uncertain independence cannot inflate support. Multiple outcomes and subgroups have separate conclusions, preventing an adverse event statement from being flattened into overall efficacy.

Database foreign keys use immutable version IDs. Index source/version hashes, family plus eligibility, anchor source-version IDs, dependency parent IDs, receipt owner plus assessment date, and recall event plus affected receipt. Unique content hashes detect duplicate imports; source identity is still checked because identical pages may have different provenance. See [ARCHITECTURE.md](ARCHITECTURE.md) for owner, consent and application-table relationships.

## 3. Review and atomic publication

Content lifecycle: `draft → in_review → approved`; review may instead return `changes_requested` or `rejected`. A published version can become `under_review`, `superseded` or `withdrawn` through an append-only trust event. These editorial labels are distinct from runtime `system_status` and `evidence_status`. Only approved, current, not-overdue versions are eligible. Review intervals are source-specific reviewer decisions; passage of time alone is not proof that a scientific claim became false.

Publication is one transaction:

1. Lock the candidate publication and included trust-state rows; check reviewer authorization and fresh approval for exact hashes.
2. Validate required fields, anchor hashes/locators, reference integrity, licensing, overlap IDs, contradictory-conclusion links and allowed operator mappings.
3. Insert immutable publication and dependency edges; switch the current publication pointer using a compare-and-swap revision.
4. Append audit/outbox events in the same transaction; commit. The dispatcher later invalidates caches and creates review work idempotently.

A concurrent withdrawal must win before admission: assessment finalization and receipt reads recheck current trust state, not only the publication captured at retrieval. Failure rolls back the whole publication. No partial source/brief mixture becomes visible. An overdue review, changed source hash pending review, broken anchor or administrative withdrawal removes affected conclusions from eligibility until reviewed.

## 4. Retrieval and evidence semantics

Deterministic retrieval first filters eligibility, English/adult type 2 scope, approved family aliases and intervention/outcome IDs. Rank remaining briefs by exact concepts and reviewed aliases; return at most six briefs/eight conclusions within the alignment budget. Include linked conflicting and limiting conclusions even when their lexical rank is lower. If these do not fit, ask to narrow or abstain. The model cannot select only favorable sources. No vector database is needed for this bounded corpus.

| Situation | Required structured result |
|---|---|
| No eligible family matches | `coverage=no_matching_approved_evidence`, `evidence_status=not_assessable`; explain library coverage only |
| Match exists but findings do not resolve proposition | `coverage=matched`, `evidence_status=insufficient`, outcome direction usually `undetermined` unless separately reviewed |
| Relevant approved findings materially disagree | `coverage=matched`, `evidence_status=conflicting`; show disagreement and overlap, not a vote count |
| Reviewed finding of no meaningful effect | `effect_direction=no_effect`; relation still depends on exact proposition and scope |
| Reviewed adverse outcome | `effect_direction=harm` for that outcome; do not generalize to every outcome/product |
| Reviewed beneficial outcome | `effect_direction=benefit`; does not establish individual suitability or permission to act |
| Required source is broken/withdrawn/awaiting review | `coverage=blocked`, `evidence_status=not_assessable`; `system_status=evidence_integrity_error` or `evidence_under_review` as appropriate |

Nonsignificance alone cannot justify `no_effect`. Conflicting means unresolved relevant disagreement after scope and evidence overlap are considered, not merely different findings in different populations. `supports_within_scope` can apply to a proposition reporting no effect or harm; it does not mean a positive health benefit. `contradicts_within_scope` requires an approved conflicting proposition, not merely missing support. `applicability=unknown` or `scope_mismatch` remains separate; personal suitability is always `not_individually_assessed`.

Runtime admission permits only reviewer-authored conclusion text, approved paraphrase templates and exact mappings. A model may align a field to a conclusion; it cannot write a new scientific sentence into the receipt. Any unknown conclusion/anchor ID, unsupported relation or unauthorized operator fails the candidate, followed by bounded retry or abstention. Integrity failures never become evidence of falsehood.

## 5. Receipt contract and presentation

`EvidenceReceipt/1.0` is an immutable assessment snapshot. `ReceiptEnvelope/1.0` supplies separately checked ownership, persistence and current trust, avoiding mutation of the snapshot when it is saved. The full schema is:

| Object | Required fields |
|---|---|
| Identity | `schema_version`, `receipt_id`, `receipt_version_id`, nullable `supersedes_receipt_version_id`, `assessment_id`, `assessed_at` |
| Confirmed input | `claim_version_id`, `selected_proposition_id`, one `ConfirmedClaimSnapshot/1.0` and its provenance hashes/offsets; `intent_version_id`, confirmed action; confirmation timestamp; raw original excluded from saved snapshot |
| Outcome | `case_state`, `route`, `coverage`, `evidence_status`, `effect_direction_by_outcome[]`, `applicability`, `personal_suitability=not_individually_assessed`, `system_status`, `reason_codes[]` |
| Interpretation | `supported_conclusion_ids[]`, `not_established_conclusion_ids[]`, `limitations[]`, `operator_findings[]`, argument-graph edges, bounded uncertainty codes |
| Evidence | For each conclusion: brief/source/version IDs, title, publisher, canonical URL, source date if known, anchor IDs and permitted passage excerpts, review ID/date, quality appraisal label/method, overlap IDs |
| Action boundary | Policy rule IDs/version, route template ID, next-step template ID, rendered bounded professional question; no treatment instruction |
| Reproduction | Publication ID, IR/compiler/operator/schema/template versions, prompt/model revision, model-run IDs, claim/intent hashes, dependency-set hash |
| Envelope ownership/consent | `persistence=ephemeral \| saved`; owner ID, consent-record ID and retention-expiry timestamp only after save; server authorizes every fetch |

Envelope `current_trust = {checked_at, state: current | under_review | superseded | withdrawn | integrity_error, affected_dependency_ids[], notice_id}` never rewrites historic content. Limitations and not-established statements reference reviewed conclusion/template IDs, never new model prose. Historical evidence is labeled before display; the ordinary result view cannot present it as current guidance. Failure to check trust yields unavailable status, not a reassuring cached “current” badge.

Default UI shows confirmed claim/action, scoped evidence status, two leap cards, the action boundary, source title/date and safe next step. Expand “Inspect evidence” for exact passages, what each supports/does not establish, limitations, reviewer status and source versions. Expand “Technical record” for hashes/run versions. Do not expose opaque IDs as the main explanation. A synthetic fixture uses a persistent “Synthetic demonstration—no clinical review” label and cannot carry a clinical-approval badge.

Before consent, case, assessment and receipt use opaque ephemeral handles in server memory. Explicit save atomically creates owner-bound versions, receipt dependencies, consent and next step; failed save creates none. Saving a receipt does not grant notification or analytics consent. Saved retrieval, check-in and export repeat authorization, policy and trust checks. Minimal receipt dependencies survive only for the defined consent/retention lifecycle; deletion removes owner-linked recall eligibility.

## 6. Recalls: honest MVP and stretch path

MVP includes manual import, approve, withdraw and current-trust checks. FUTURE WORK includes autonomous source watching, semantic update classifiers, external notification channels and population-wide recall operations. One **synthetic** source-update/recall demonstration is optional only after core release gates pass.

Recall path: a source-version update or trust event creates an event keyed by `(source_id, old_version_id, new_version_id, event_type)`. Reverse dependency traversal identifies affected briefs, assessments and saved receipts. Include limiting/conflicting/context dependencies, not just displayed citations; removing counterevidence can materially change an assessment. Enqueue review items using unique `(event_id, receipt_version_id)` keys. Replayed events, outbox retries and repeated imports cannot duplicate work or notices.

Show content/anchor diffs and the changed outcome/scope fields to the reviewer. A hash detects change, not materiality. The qualified reviewer chooses `no_material_change`, `reassessment_required` or `withdrawal_required`, records rationale, and approves notice wording. While necessary evidence is under review, conservative eligibility blocking prevents new assessments depending on it. Administrative emergency withdrawal may immediately block eligibility; it cannot issue new medical advice.

A new assessment creates a new receipt version; the old one stays an auditable historical record. The current-trust overlay is mandatory on every authorized retrieval and never depends on notification consent: withdrawal of optional notice consent cannot hide stale or withdrawn evidence. An optional **proactive in-app recall notice** requires a saved affected receipt, current ownership, separate opt-in, unexpired retention and a reviewed material decision. External delivery is deferred. Recheck consent/deletion immediately before displaying that optional notice. Store its decision, template version, eligibility outcome and displayed/read state; no repeated notice after an identical event/receipt/template display.

Synthetic stretch fixture: reviewer-controlled source `SYNTH-01` v1 supports a narrowly defined demonstration outcome. v2 removes that synthetic conclusion. Dependency lookup finds one saved synthetic receipt, puts it under review, and the reviewer approves: “The evidence record used for this assessment changed. This receipt needs review. Do not change treatment based on this notice; discuss treatment questions with a qualified professional.” Show a second unaffected receipt to prove selection, replay the update to prove idempotence, and revoke optional notice consent to prove suppression while the mandatory current-trust overlay remains. Every screen and narration labels the source, user, timeline and update synthetic.

Acceptance: broken anchor blocks publication; withdrawal blocks fresh use and changes historical trust display; conflicting findings survive retrieval limits; overlap cannot increase independent-source counts; every rendered scientific sentence has approved dependencies; publication/save races cannot yield mixed versions; recall replay creates one item; deletion/consent revocation prevents delivery. These are planned tests, not test results.
