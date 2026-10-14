# Entry copy — EvidenceLoop

Draft prepared 14 October 2026. Use the current factual baseline in [README](README.md). The user completed the form's first page, including captain/contact details, and the second-page project requirements have now been inspected. Contact details are intentionally excluded from these public drafts. Local deck, cover, sponsor PDF and video assets exist; engineering checks passed. Live AI remains unqualified and disabled. No final submission has been made.

## Title and blurb

**Title:** EvidenceLoop

**Blurb:** Turn confusing health claims into questions worth following up.

Blurb word count: **9**.

**Track:** Healthcare — Case Study 2: long-term self-care.

**Entry/team identifier:** AJ_001. **Team size:** 1. **Institution:** NTU. The user confirmed being an international student studying for a Master's in AI and completed the captain/contact form fields themselves. Do not copy their contact information into public project materials or substitute the team identifier for their legal name.

## Short description

EvidenceLoop is a prototype for people managing a long-term condition and caregivers preparing a professional discussion. It connects a confirmed claim, an inspectable source, a question the user chooses to save, and a later self-reported check-in. Source status is checked again when a receipt is reopened or used. The current local demonstration uses fictional nonclinical evidence; live AI remains disabled because no candidate passed qualification.

## Form-ready description: users, pain point, design, prompting and proposed value

EvidenceLoop is designed for adults managing a long-term condition and caregivers preparing a healthcare discussion. They may encounter a confident claim without knowing which outcome was measured, whether it applies to their situation, or what action follows. The product hypothesis is that making those distinctions visible can help people prepare better questions and retain context for a later discussion. That benefit has not yet been established in a user or clinical study.

The working prototype links claim confirmation to a scoped evidence receipt and a consented follow-up. The user checks the claim's meaning and their intended action separately, inspects the source passage and limitations, then previews the exact question before deciding whether to save it. A later check-in records the user's own report. A withdrawn source changes the current trust status of affected receipts and blocks relevant new writes; a saved receipt does not freeze old authority in place.

This fits Healthcare Challenge 2 through question preparation, continuity and user control. It does not recommend a medicine, change treatment or verify adherence. The current demonstration uses fictional nonclinical examples. Real clinical source packets remain quarantined pending qualified review, and live AI remains disabled after failed qualification. The interface labels replay and manual interpretation explicitly.

The optional reader is prompted to return bounded structured fields anchored to exact input quotations, preserve unknown information, and keep claim meaning separate from user intent. The server checks schema, provenance and policy; the model cannot approve evidence, authorize storage or invent a clinical next step. Tested free candidates still made semantic errors, so the public workflow uses guided fictional example replay with no free-text or manual claim entry. The full local implementation also contains manual interpretation, with context-only restrictions when exact comparison cannot be established. An unqualified reader is not presented as working AI.

The implementation uses React/TypeScript, FastAPI and PostgreSQL. Consent, ownership, versioning and source checks are enforced on the server. The public mode disables live AI and reviewer controls, accepts supplied fictional examples, and warns that saved demonstration records may reset on free-host restart. Source is published on GitHub. The public FERN journey through confirmation, consented saving and a self-reported check-in, plus hosted video playback, were verified in Chrome on 14 October. Genuine WorkBuddy development review contributed negative-test proposals for consent and source withdrawal. Codex corrected and implemented those proposals and ran 44 related passing tests. The evidence package includes four inspected captures and a sanitized log. These are engineering results, not clinical validation.

Proposed business value is a reusable, auditable question-preparation workflow for patient-education or care-navigation teams, with explicit consent and source-status checks when people return. It could reduce repeated work reconstructing why a question was saved and make content-review responsibilities clearer. This is a hypothesis, not measured savings, demand or willingness to pay. An initial evaluation would compare time to prepare a source-linked question, unassisted task completion and staff rework against an existing workflow; adoption, cost and any health benefit would require separate evidence. No customers, revenue or clinical outcomes are claimed.

## Verified project-page fields and local mapping

The official form deadline is **16 October 2026, 23:59 GMT+8**. The observed second page requires the following; no final submission has occurred.

| Form field | Prepared content or remaining action |
| --- | --- |
| Project Title | EvidenceLoop |
| Blurb, fewer than 10 words | The nine-word blurb above |
| Project Description | Form-ready description above covers target users, pain point, design/prompting and proposed business value |
| Cover upload, maximum 1 MB | [Prepared cover](../../artifacts/submission-20261014/cover.png), 51,994 bytes, 16:9; uploaded to the form |
| Project Web Link, required browser experience | [Live Render demo](https://evidenceloop-aj-001.onrender.com/), public FERN journey through consented save/check-in verified in Chrome. Guided fictional-only mode, no live AI/reviewer controls, records reset on restart; URL filled. |
| Demo Video Link, required 5-8 minutes | [Hosted video](https://evidenceloop-aj-001.onrender.com/demo-video.html), 6:03.78; public muted playback advanced to 11.25 seconds with readyState 4 and no error; URL filled. |
| WorkBuddy/CodeBuddy Conversation History, one file, maximum 10 MB | [Sponsor evidence PDF](../../artifacts/submission-20261014/sponsor-evidence.pdf): conversation-history summary, four actual captures and sanitized local test result; 346,975 bytes; uploaded. It is not a complete account transcript. |
| Architecture Diagram PPT, one file, maximum 10 MB | [Editable deck revision 2](../../artifacts/submission-20261014/deck/EvidenceLoop-judging-deck-v2.pptx), 455,581 bytes; architecture/trust-boundary content on slide 8; uploaded and accepted chip visible |
| GitHub source URL, required | [Published source](https://github.com/ajayasai/EvidenceLoop), initial commit `6f1b125`; URL filled in the form after user authorization |
| Social bonus | Optional; no post or benefit claimed |

## What to highlight to judges

- **A return journey:** understanding a claim leads to a saved question and a later self-report, with an option to revise or abandon it.
- **Evidence that can lose authority:** the original receipt remains historical, while current source status controls new use.
- **Separate decisions:** what a source says, what the user intends, and permission to store information are represented independently.
- **Inspectable limits:** source passages and version records are available; a model failure, missing evidence and a scientific contradiction are not interchangeable outcomes.

These describe the demonstrated design. Superiority over a conventional retrieval assistant and improved health outcomes have not been measured.

## Sponsor-use answer

On 13 October 2026, WorkBuddy's Hy3 model was used in an authenticated Free-plan conversation to review source excerpts for consent and source-withdrawal behavior. Its proposals identified missing negative-test coverage. Codex corrected fixture and comparison mistakes, extended the coverage, implemented five new parameter cases and executed the local checks. The combined related suite passed 44 tests. WorkBuddy reviewed the reported result; it did not execute the tests or clinically validate the application. Four contemporaneous inspected captures and the validation record are included in [the sponsor package](../sponsor-evidence/2026-10-13/README.md).

## Cover copy

**EvidenceLoop**

Turn confusing health claims into questions worth following up.

**Confirm → Inspect → Save by choice → Return**

Small footer: **Healthcare Challenge 2 · Fictional engineering demonstration**

The prepared [cover](../../artifacts/submission-20261014/cover.png) uses a 16:9, 1280×720 layout with original typography/shapes and a fictional-prototype label. Its 51,994 bytes fit the observed 1 MB form limit. Do not add clinician portraits, approval badges, health outcomes or live-AI claims.

## Concise judge Q&A

**What does AI do today?** The bounded extraction and alignment adapters are implemented and tested, but live application AI is disabled because no candidate qualified. WorkBuddy was genuinely used for development review. The recorded workflow uses labeled replay/manual interpretation.

**Why use a fictional example in a healthcare challenge?** It makes the implemented confirmation, consent, persistence and withdrawal behavior inspectable without passing unreviewed medical content off as advice. The intended healthcare application still needs qualified source and wording review.

**How is this different from displaying a citation?** The demo links exact confirmed meaning and intention to a versioned receipt, then rechecks source status on later use. A citation alone does not show that a conclusion supports an action or remains eligible after withdrawal. Comparative superiority is unmeasured.

**Does a check-in prove that someone followed advice or improved?** No. It is explicitly a self-report, and no clinical outcome or adherence improvement has been measured.

**What is the next validation step?** Qualify a bounded reader on fresh fictional inputs, address the directional comparison gap, obtain independent review of a narrow clinical example, and observe whether people can use the workflow without coaching. These are separate pieces of evidence.

## Optional social-bonus post — draft, not posted

Ready to copy if the user chooses to post. The hashtags below are those shown by the form. Actual sponsor development use was WorkBuddy review; no CodeBuddy or Miora use is claimed, and no social bonus has been earned or verified.

```text
I built EvidenceLoop for Healthcare Challenge 2: a guided fictional prototype that connects a claim, its source, a question saved by choice and a later self-reported check-in.

WorkBuddy contributed consent and source-withdrawal code review. Codex corrected and implemented the proposed regressions; 44 related tests passed. The public demo uses labeled example replay. Live AI remains disabled, and this is not clinically validated.

Try it: https://evidenceloop-aj-001.onrender.com/
Watch the 6-minute walkthrough: https://evidenceloop-aj-001.onrender.com/demo-video.html
Source: https://github.com/ajayasai/EvidenceLoop

#WorkBuddy #CodeBuddy #Miora #TencentCloudHackathon
```

