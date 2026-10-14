# Public browser verification — 14 October 2026

The public service at https://evidenceloop-aj-001.onrender.com/ was exercised in Chrome after Render reported its first deployment Live. Render deployed application commit `6f1b125f20f9d49bdba2cccb2b2ea4ef67002d91`. The subsequent CI-probe-only fix did not change application code.

## Observed workflow

1. The home page displayed “Guided fictional demo · No live AI”, the nonclinical scope and temporary storage notice. Reviewer navigation was absent and the claim input used supplied fictional examples.
2. “A finding within its scope” loaded the fictional Fern Lab example. The interpretation explicitly identified its deterministic example origin.
3. Explicit confirmation enabled evidence assessment. The unchanged authored example displayed “Supported within the studied scope”, its fictional source passage and limitations.
4. The preview displayed the exact question and separate consent checkbox. Saving was disabled until consent was given. The saved question then appeared in this browser.
5. A separate self-report consent enabled “I discussed it”. The saved item changed to “Done · self-reported” and explicitly said that this did not verify an outcome.
6. The browser was returned to an empty example-selection page. The fictional check-in remains temporary demonstration data; no personal health information was entered.

This was an engineering verification performed by the developer's agent, not a volunteer usability study or clinical review. The hosted source-withdrawal reviewer controls are intentionally disabled; withdrawal behavior is demonstrated in the recorded local walkthrough and covered by automated tests.

## Public video

https://evidenceloop-aj-001.onrender.com/demo-video.html loaded the recorded screenshot walkthrough with its fictional/static/synthetic-narration disclosures. Chrome playback reached 11.253 seconds of a 363.783-second duration with `readyState=4`, muted playback and visible English captions. It was later paused at 72.079 seconds. This is a playback spot check, not a complete manual review of the hosted video. The local final MP4 had separately passed full decode verification.

## Captures

- [Hosted saved check-in](../artifacts/submission-20261014/screenshots/13-public-checkin.jpg)
- [Hosted captioned playback](../artifacts/submission-20261014/screenshots/14-public-video.jpg)
- [Hosted home](../artifacts/submission-20261014/screenshots/15-public-home.jpg)

The screenshots contain fictional demonstration content. Account, billing and entry-contact screenshots remain private and are excluded from public artifacts. Independent bounded HTTP checks are recorded in [the API verification](PUBLIC_API_VERIFICATION_20261014.md).

## Entry draft

The Tencent form accepted the cover PNG, sponsor-evidence PDF and judging-deck revision 2 PPTX as selected upload files. The live app, video page and public GitHub URLs were entered. This verifies a prepared draft only: final Submit has not been performed and no organizer acknowledgment has been received.
