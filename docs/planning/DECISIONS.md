# EvidenceLoop decision register

Planning date: 30 September 2026. Status: PROPOSED architecture; implementation has not started. The user authorized a detailed planning package and no application code. The 42-page blueprint and pasted brief are specification inputs, not evidence that any capability exists. This directory contains planning documents only.

## State and vocabulary contract

All documents use these orthogonal fields. No frontend may infer them from explanation text.

| Field | Allowed values | Meaning |
|---|---|---|
| case_state | captured, needs_confirmation, ready, assessing, assessed, cannot_assess | Processing lifecycle; a completed assessment can still recommend professional review. |
| route | education, clarify, professional_review_recommended, urgent_escalation | Permitted interaction, never authority to change treatment. |
| coverage | matched, no_matching_approved_evidence, blocked | Approved-library coverage, not the state of all scientific knowledge. |
| evidence_status | supports_within_scope, contradicts_within_scope, insufficient, conflicting, not_assessable | Relation between the precise proposition and reviewed evidence. |
| effect_direction | benefit, no_effect, harm, mixed, undetermined | Outcome-specific reviewer-authored finding; independent of claim support. |
| applicability | scenario_aligned, scope_mismatch, unknown | Match to stated scenario; personal suitability is always not_individually_assessed. |
| system_status | ok, model_error, evidence_integrity_error, evidence_under_review, unavailable | Operational condition, never a scientific verdict. |
| operator_state | established, not_detected, unknown, not_applicable | Whether a reviewed mismatch operator is justified; unknown is not falsehood. |
| next_step_state | planned, done_self_reported, deferred, abandoned, needs_revision | Self-report, not verified clinical adherence. |

`evidence_under_review` is a system status, not a sixth scientific state. `professional_review_recommended` and `urgent_escalation` are routes, not truth labels. A source's no-effect finding must be explicitly reviewed; a nonsignificant result alone cannot establish equivalence or absence of effect. Evidence quality uses published assessments or a labeled local appraisal; there is no invented confidence or GRADE score.

## Proposed decisions and explicit tradeoffs

| ID | Decision | Reason / rejected alternative | Revisit trigger |
|---|---|---|---|
| D01 | Educational, English, adult type 2 diabetes/caregiver scenarios; synthetic public demo | Preserves blueprint scope without pretending to provide individualized care | Qualified review and intended-use assessment authorize expansion |
| D02 | React + TypeScript + Vite; Python FastAPI/Pydantic; PostgreSQL; one optional worker from the same codebase | Familiar modular monolith; no microservices, graph DB, vector DB, Redis or separate agent framework at MVP | Measured bottleneck or an existing team stack changes effort |
| D03 | Two sequential model stages: extraction and bounded alignment; deterministic template rendering | AI handles language ambiguity; application owns authorization, source state and output admission | A third simplification call shows measured benefit without semantic loss |
| D04 | Six proposed evidence families, 6-10 distinct source documents as a planning target | Reduces blueprint's 8-12 families/20-30 sources to solo capacity; final selection depends on review | Review capacity confirmed and all core gates pass |
| D05 | 60 reviewed scenarios (30 development, 10 validation, 20 sealed), plus 30 repeatedly used safety sentinels | Small original evaluation; all variants and overlapping evidence clusters stay in one split | Reviewer can independently label a larger corpus |
| D06 | Three user screens plus one minimal reviewer page | Confirmation is part of capture; receipt/leap are panels within result | Usability observations show a need for separation |
| D07 | One professional-question next-step template, explicit save, retrieval, one check-in and one reviewed transfer exercise | Keeps the long-term self-care loop real; external reminders and clinical goal design are deferred | Core metrics and retention controls pass |
| D08 | Ephemeral server-memory session before save; persistent transaction only on purpose-specific consent | Reconciles case/receipt IDs with no automatic persistence | Multi-instance deployment or authorized real-data pilot requires a reviewed session store |
| D09 | Immutable evidence/claim/assessment/receipt versions; current trust state is checked again on read and write | Preserves auditability without serving withdrawn evidence as current | Never relax version integrity for caching |
| D10 | Minimal reviewer import/approve/withdraw path; synthetic recall only if core gates pass | Human approval is required; polished CMS and autonomous watchers are not | Additional reviewer capacity and measured update workload |
| D11 | CodeBuddy development use with contemporaneous proof; optional WorkBuddy de-identified review coordination; Miora optional design assets | Handbook page 37 requires CodeBuddy or WorkBuddy and usage evidence; Miora alone is insufficient under that stricter rule | Registered-track clarification changes requirements |
| D12 | Provider-neutral runtime model selected on validation and actual account access | Product marketing and tool credits do not establish inference API availability | Provider/access change requires new regression and budget checks |
| D13 | Proposed 96 focused developer-hours (16 days x 6 h), of which 76 committed and 20 reserved | Blueprint's 255 hours/three builders do not fit one builder | Actual availability differs; reduce breadth, not safety controls |
| D14 | Internal package target 15 October; public deadline 16 October 2026 | One-day submission buffer; exact cutoff/time zone remains unresolved | Organizer's written rules change |
| D15 | Planning only in this directory; any next build requires explicit user approval | Current user instruction | User approves a concrete implementation phase |
| D16 | Treat eligibility as an external entry gate: 1-3 team members, every participant based in Singapore | CONFIRMED in official handbook page 39; user/team eligibility remains unconfirmed | User establishes eligibility or organizer supplies a written exception |
| D17 | Use published ten-dimension, 10-points-each rubric as a coverage map; obtain registered-track criteria | Handbook page 40 resolves blueprint's unverified weighting, but says detailed track criteria follow registration | Track-specific rubric supplied |
| D18 | Require 100% audited sentence support and safety/state stability on the release sample; retain separate false-rejection and useful-coverage gates | Deliberately strengthens blueprint's 95% support/stability targets because the renderer uses reviewed text; stricter gates do not prove clinical safety | Reviewer workload pilot or a recorded scope change; never silently lower a gate after test results |
| D19 | Assess one selected principal proposition at a time; extract up to three for selection, screen all for safety | Avoids falsely reducing support for one claim and contradiction of another to conflicting evidence | A future per-proposition result schema is explicitly approved |
| D20 | Never persist raw original input in submission build; save a separate ConfirmedClaimSnapshot only | Ephemeral ClaimIR requires text/spans; saved schema must remain valid without them | Future reviewed retention policy, not an implementation shortcut |
| D21 | 40-second cumulative automated processing budget excludes human confirmation; 11k/4k tokens include repairs | Extraction and alignment occur on separate endpoints; human dwell is governed by session TTL | Measured provider capabilities require a documented revised budget |

Official handbook: [Tencent Singapore 2026 handbook](https://heikesong-global-1256915710.cos.ap-hongkong.myqcloud.com/online_video/3af2d08d-d3f0-4998-98a5-a820bd245910.pdf), retrieved 30 September 2026. The narrower healthcare preparation approach is permitted by the guidance on pages 33-35. Handbook pages 37 and 39 differ on Miora; follow page 37's explicit scoring requirement. See SPONSOR_VERIFICATION.md for provenance and remaining conflicts.

## Blueprint issues resolved openly

1. The sample response mixes action insufficiency with scientific status. Replace it with the orthogonal vocabulary above; preserve finer reasons in reason_codes.
2. The pseudocode re-extracts an already confirmed frame. Freeze the confirmed claim and intent version; assess that exact version. A later edit invalidates confirmation and assessment.
3. Always changing the route for "alongside" versus "instead of" would be incorrect. Require material field and warrant changes; both routes may still recommend professional discussion.
4. A valid anchor proves identity/integrity, not entailment. Require reviewed conclusion mappings plus a blinded sentence-support audit; do not market the admission gate as medical proof.
5. Persistent cases conflict with no persistence before consent. Use opaque ephemeral draft handles and transactional promotion to saved records.
6. A version hash cannot tell whether a source change matters. Show diffs, invalidate runtime eligibility conservatively when required, and let a qualified reviewer decide materiality and notice wording.
7. An early safety check alone misses intent revealed later. Run policy checks on capture, confirmation, output, save and check-in.
8. A six-family benchmark has weak generalization and leakage risk. Split connected evidence families together, disclose tiny independent test size, and shrink claims if the split becomes too small.
9. An offline fixture adapter cannot demonstrate novel-language AI. Label it deterministic replay and retain the same comparison, policy, renderer, version and ownership checks. Never label replay as live inference.
10. A four-minute demo is overloaded if every extension is shown. Core sequence includes support/uncertainty and live edits; recall is an optional appendix.

## Status discipline

Budget update, 30 September 2026: the user explicitly set an active goal to complete EvidenceLoop with **zero additional monetary spending** and authorized their Kaggle account if required. [ZERO_COST_PLAN.md](ZERO_COST_PLAN.md) governs free quotas, billing restrictions and conditional Kaggle use. The prior planning-only restriction is being clarified separately; setting this budget does not establish completed work or working account access.

CONFIRMED means directly observed in a cited source or user instruction. PROPOSED means a design choice awaiting implementation. NEEDS VERIFICATION means an external dependency is unresolved. FUTURE WORK is excluded from submission commitments. "Implemented", "tested", "independently reviewed", "deployed" and "clinically validated" are separate evidence-bearing claims; none is established by this plan.
