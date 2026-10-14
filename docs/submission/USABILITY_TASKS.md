# Three fictional usability tasks

Ready-to-run facilitator script, prepared 14 October 2026. Invite three adults only if actually available and willing; this document does not claim recruitment or participation. This is a small formative interface check with fictional material, not a clinical study or evidence of improved self-care.

Use [observations-template.csv](observations-template.csv). It contains nine empty rows for up to three people completing three tasks. Assign P01–P03 only when sessions actually occur. Leave unrun rows blank. Use anonymous IDs; do not collect names, diagnoses, medications or contact details in this file.

## Preparation

Start the existing local demo and use a fresh, separate demo browser identity for each participant. Choose fictional examples only; live AI is disabled at this preparation checkpoint. Confirm the relevant synthetic source is current. A facilitator operates the synthetic reviewer workspace in a separate authenticated tab for Task C; no participant needs the private reviewer credential. After a withdrawal rehearsal, restore through the supported workflow and create a fresh receipt for the next session; old receipts do not regain eligibility merely because a source is restored.

Use the same build for all three participants and record its revision/date. Do not change the interface between participants without marking the changed build and reporting sessions separately. The facilitator keeps the task's expected outcome private while the participant works.

## Opening script — read aloud

“We are testing an unfinished interface, not you. Everything in this session is fictional. Please do not enter personal health details. You can stop at any time or skip a task. I will note whether the task is completed, how long it takes and where the interface is confusing. I will use an anonymous participant ID. May I take those notes? I will not record you or quote you by name. Any recording or quotation would need separate permission. Please say what you are looking for as you work; I will avoid showing you the steps unless you ask.”

Begin only after the person agrees to notes. Note permission as yes/no without storing an identity. If permission is declined, leave the row unused and do not retain observations. Allow up to three minutes per task. Time from the end of the instruction to completion, stopping or the time limit. If help is requested, first ask “What would you expect to happen?”; then provide the minimum necessary hint and mark the task **assisted**, even if it later finishes.

## Task A — understand the claim and its limits

**Read aloud:** “Open the fictional example called ‘A finding within its scope’. Work through it as someone who wants to understand the claim. Find the source passage and tell me what it measured, one limit on what it shows, and whether this is live AI or an example replay.”

**Facilitator only:** The example concerns glow water, fern height over seven days and plain water as comparator. The participant should locate the passage, distinguish the limited measurement from a guarantee for all plants, and identify the replay/synthetic label. Do not supply these answers or judge a participant's scientific ability. Record the actual answer and where it was found. Success requires completing confirmation and identifying the source plus at least one displayed scope limit without coaching; record mode identification separately if wrong.

**Afterward:** “What did you think the confirmation step meant?” Note if they interpreted confirmation as proof of truth. Ask “What, if anything, was unclear?” without suggesting the desired criticism.

## Task B — choose what to retain and return to it

**Read aloud, part 1:** “You are curious about this fictional finding but do not want to keep a record yet. Find the proposed question, then leave without saving it.”

**Read aloud, part 2 after part 1:** “Now imagine you decide to keep that question for a later conversation. Save it, find it again, and simulate recording that you discussed it. Tell me what that check-in proves and what it does not prove.”

**Facilitator only:** Observe whether the participant discovers the exact preview, leaves without saving, then explicitly consents to a save and to the self-report. The intended return path is **My next steps** → saved item → consent → **I discussed it**. Do not call the simulated action a real consultation. Record whether the person understands that original pasted text is excluded from the saved receipt and the check-in is unverified self-report. Any unexpected persistence after declining is a defect to investigate; do not conceal it or count it as successful.

**Afterward:** “What information do you think is stored, and how would you remove it?” Ask them to point to the deletion control; do not delete the fictional saved item yet because Task C uses it. Task success requires both choices and the later self-report; report partial completion explicitly.

## Task C — respond to withdrawn evidence

**Facilitator action:** After Task B, use the real synthetic-reviewer control to withdraw the source used by that saved receipt, with reason **Fictional usability exercise**. Do not edit a database directly. The evidence/audit change is part of the exercise; user-record writes are a separate boundary. If Task B did not create a record, prepare a clearly labeled facilitator-created fictional record and mark `facilitator_setup` in notes; do not count the setup as participant success.

**Read aloud:** “Imagine the source behind your saved question has been withdrawn. Return to the saved item, inspect its receipt, and work out whether you can record another discussion using that same receipt. Tell me what you would do next.”

**Facilitator only:** Observe whether the participant notices the changed trust status and understands that relevant new use is blocked. They should not interpret withdrawal as proof that the opposite scientific claim is true. Record the action they attempt and any misleading wording. Success means finding the restriction and explaining the need for a fresh, eligible assessment, without coaching. This is an ordered synthetic scenario, not a test of every concurrent operation.

**Afterward:** “What changed: the old record, its current authority, or both?” Record the answer without correcting it until notes are complete. Finish by letting the participant delete the fictional records if desired; log deletion as a separate observation, not a health outcome.

## Recording and reporting

For each task, use `completed_unassisted`, `completed_assisted`, `partial`, `not_completed` or `not_run`. Record seconds, the exact hint if any, concise observed behavior and a fix candidate. Leave unknowns empty. Do not infer satisfaction, trust, learning, clinical safety or future behavior from task completion.

Report small counts directly: “[actual n] of [actual N] completed Task A without assistance; [actual confusion] was observed.” Report each task separately and include incomplete sessions. Times from three people are descriptive observations, not population estimates. Use anonymous paraphrases by default; publish a verbatim quotation only with explicit permission. No results sentence belongs in the entry or video until actual sessions exist.

## Blank findings summary

| Field | Result |
| --- | --- |
| Session date(s) and build revision | |
| Participants who agreed to notes / started / completed | |
| Task A unassisted / assisted / incomplete, denominator | |
| Task B unassisted / assisted / incomplete, denominator | |
| Task C unassisted / assisted / incomplete, denominator | |
| Actual task times and missing-time reasons | |
| Most consequential observed confusion | |
| Implemented correction and verification, if any | |
| Remaining issue disclosed to judges | |

