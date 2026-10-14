# Source and evidence manifest for judges

Prepared 14 October 2026. Following user authorization, [source was published on GitHub](https://github.com/ajayasai/EvidenceLoop) at initial commit `6f1b125`. Render reports Live for that commit; the [public FERN journey](https://evidenceloop-aj-001.onrender.com/) through consented save/check-in and [hosted video playback](https://evidenceloop-aj-001.onrender.com/demo-video.html) were verified in Chrome. The corrected [public CI run](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) at `f51c764` and separate public API checks passed. Final form submission remains unconfirmed. Do not treat the private WorkBuddy conversation URL as a public share link.

## Prepared presentation assets — 14 October 2026

| Artifact | Contents |
| --- | --- |
| [Editable judging deck, revision 2](../../artifacts/submission-20261014/deck/EvidenceLoop-judging-deck-v2.pptx) | Ten slides with editable text and native architecture/results tables, actual app/sponsor captures, source citations and narration in speaker notes. The numerical results explicitly describe 13 October checkpoints. |
| [16:9 cover](../../artifacts/submission-20261014/cover.png) | 1280×720 title image with AJ_001, solo entry, NTU and an explicit fictional-prototype disclosure |
| [Slide image and timing map](../../artifacts/submission-20261014/deck/slides.json) | Ten rendered 1280×720 PNGs, source references and narration, with durations totaling six minutes |
| [Presentation asset manifest](../../artifacts/submission-20261014/deck/manifest.json) | Hashes for the deck, cover and rendered slides at this preparation checkpoint |
| [Recorded screenshot walkthrough](../../artifacts/submission-20261014/EvidenceLoop-recorded-walkthrough.mp4) and [editable captions](../../artifacts/submission-20261014/EvidenceLoop-recorded-walkthrough.srt) | Corrected local export: 6:03.78, H.264 1280×720 with AAC 44.1 kHz, 5,088,343 bytes. Full FFmpeg decode passed with no errors on 14 October. Static captures use synthetic offline narration and a separate SRT. |
| [Video manifest](../../artifacts/submission-20261014/video-manifest.json) | Final local media metadata and hashes, with private runtime paths removed |
| [Public video page source](../../apps/web/public/demo-video.html), [MP4](../../apps/web/public/demo/EvidenceLoop-recorded-walkthrough.mp4), [VTT captions](../../apps/web/public/demo/EvidenceLoop-recorded-walkthrough.vtt) and [poster](../../apps/web/public/demo/cover.png) | Reviewed static hosting assets for `/demo-video.html`; MP4 byte-identical to the verified export, 52 captions preserve SRT text/timings, native controls and transcript; no external scripts/assets |
| [Sponsor conversation evidence PDF](../../artifacts/submission-20261014/sponsor-evidence.pdf) | Six pages: truthful history summary, four unchanged actual captures and the sanitized 44-test log. Rendered and visually checked; 346,975 bytes, below 10 MB. SHA-256: `e3a14a614aca658d493a40fa95bab85ec911176fd88a1989035abb52fd170e0c`. |
| [Source ZIP](../../artifacts/submission-20261014/source/EvidenceLoop-source.zip), [external source manifest](../../artifacts/submission-20261014/source/EvidenceLoop-source.manifest.json) and [SHA256SUMS](../../artifacts/submission-20261014/source/SHA256SUMS.txt) | Reproducible selected source bundle and its final packaging checksums; source repackage records are distinct from the initial deployed commit |

The presentation and video label their images as a recorded screenshot walkthrough. Their engineering figures refer to 13 October checkpoints and retain failed AI qualification. Static captures and synthetic narration do not establish live screen operation, live inference, a volunteer session or clinical review. Hosted video playback was separately observed in Chrome on 14 October; local decode and hosted playback are distinct checks.

## Implementation and operation

| Artifact | Purpose |
| --- | --- |
| [Root README](../../README.md) | Local setup and current application boundary |
| [Startup script](../../scripts/start.ps1) | Existing loopback API/database launch |
| [React interface](../../apps/web/src/App.tsx) | Visible mode, navigation and library status |
| [Interpretation](../../apps/web/src/Interpretation.tsx), [receipt/save](../../apps/web/src/Assessment.tsx), [saved follow-up](../../apps/web/src/Saved.tsx) | Confirmation, exact question preview, consent and self-report UI |
| [API routes](../../services/api/app/main.py) | Server-side ownership, consent, version and current-trust boundaries |
| [Storage](../../services/api/app/storage.py) | Transactions, saved rows, idempotency, retention and check-ins |
| [Evidence review](../../services/api/app/review.py) | Quarantine, independent review capability, publication and withdrawal |
| [Domain](../../services/api/app/domain.py), [compiler](../../services/api/app/compiler.py), [provider](../../services/api/app/provider.py), [slot admission](../../services/api/app/slot_extraction.py) | Bounded interpretation/comparison and optional AI integration |
| [Contracts](../../contracts/ClaimIR.schema.json), [confirmed snapshot](../../contracts/ConfirmedClaimSnapshot.schema.json), [OpenAPI](../../contracts/openapi.json) | Eight JSON schemas, enums and OpenAPI exported against the final local implementation on 14 October |
| [Implemented architecture](../ARCHITECTURE.md), [review workflow](../REVIEW_WORKFLOW.md) | Technical and review operating explanations |

## Evidence and measured checks

| Artifact | Supported claim |
| --- | --- |
| [Fictional demonstration library](../../evidence/synthetic_nonclinical.json) | Nonclinical source passages used by the demo; not medical authority |
| [Quarantine README](../../evidence/quarantine/README.md) | Scope, provenance and limitations of six partial NCCIH packets; no qualified clinical publication |
| [AI verification, 13 Oct](../AI_EXTRACTION_VERIFICATION_20261013.md) | Actual failed/partial model probes, semantic and operational limits, dated automated checks |
| [AI experiments, 14 Oct](../AI_EXTRACTION_VERIFICATION_20261014.md) | Completed dated experiments, including the final fast but semantically failing low-reasoning candidate; no qualified candidate, no fresh final/challenge cases consumed |
| [Build status](../BUILD_STATUS.md) and [verification history](../VERIFICATION.md) | Current limitations and explicitly dated earlier results |
| [Latest engineering results](ARCHITECTURE_AND_RESULTS.md) | Public-hosting candidate: 599 Python tests plus 51 subtests, no failures/errors/skips, 87.134 seconds (650 JUnit entries); 35 frontend tests and build passed. Local JUnit: `test-results/submission-20261014-public-demo.xml`. |
| [Free-hosting record](../FREE_HOSTING_20261014.md) | Windows supervisor smoke and public CI Docker build passed; Render Live, Singapore Free 0.1 CPU/512 MB. Public journey/video and separate API checks passed; corrected CI at `f51c764` passed the constrained container smoke check. No added API secrets/card; auto-deploy off. |
| [Public check-in](../../artifacts/submission-20261014/screenshots/13-public-checkin.jpg) and [public video](../../artifacts/submission-20261014/screenshots/14-public-video.jpg) | 14 October HTTPS FERN journey through explicit save/check-in consent and Done self-reported, current trust checks, no-live-AI banner and no reviewer controls; hosted muted video playing at 11.253323s / 363.782993s, readyState 4, no error |
| [Public home capture](../../artifacts/submission-20261014/screenshots/15-public-home.jpg), [public browser report](../PUBLIC_BROWSER_VERIFICATION_20261014.md) and [public API report](../PUBLIC_API_VERIFICATION_20261014.md) | Dated hosted demonstration checks and observed restrictions; separate from live AI qualification |
| [Passing public CI run](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) | `f51c764`: 599 tests plus 51 subtests in 10.51s; 35 frontend/build, Docker and 512 MiB/no-swap/0.1 CPU startup smoke passed. About 24.45s startup; 119.5 MiB single post-smoke sample, not peak/load evidence. |
| [Browser video playback](../../artifacts/submission-20261014/screenshots/12-video-playback.jpg) | Local muted playback advanced to 8.26s of 363.783s, readyState 4 and no error; visible English captions |
| [Final authored replay](../../artifacts/submission-20261014/screenshots/10-final-replay.jpg) and [final edited claim](../../artifacts/submission-20261014/screenshots/11-final-edited-claim.jpg) | Restarted final app: authored FERN retained support/preview; negated-polarity edit withheld assessment and next-step preview, with its source current |
| [Evaluation runbook](../EVALUATION_RUNBOOK.md) | Engineering harness definitions, counting and independent-review boundaries |
| [Historical replay summary](../../evals/harness/runs/engineering-20260930-release-candidate/summary.json) and [manifest](../../evals/harness/runs/engineering-20260930-release-candidate/manifest.json) | Frozen zero-model replay result and provenance; not live inference |
| [Consent API tests](../../tests/test_api.py), [publication API tests](../../tests/test_api_review.py), [review tests](../../tests/test_review.py) | Executable related regression checks for the sponsor contribution |

## Sponsor package: include these existing public-safe artifacts

| Artifact | Recorded content |
| --- | --- |
| [Contribution and attribution](../sponsor-evidence/2026-10-13/README.md) | WorkBuddy review; Codex corrections, implementation and local execution |
| [01 request](../sponsor-evidence/2026-10-13/01-source-withdrawal-request.png) | Actual consent-boundary review request; original filename retained |
| [02 review](../sponsor-evidence/2026-10-13/02-source-withdrawal-review.png) | Substantive WorkBuddy findings |
| [03 proposal](../sponsor-evidence/2026-10-13/03-transaction-test-proposal.png) | Proposed transaction-boundary regression |
| [04 corrected closing review](../sponsor-evidence/2026-10-13/04-local-validation-review.png) | Corrected status-code/attribution discussion of locally reported validation |
| [Sanitized test result](../sponsor-evidence/2026-10-13/validation.txt) | 44 passing tests, one existing warning, 51.89 seconds |
| [Dated source/artifact hash manifest](../sponsor-evidence/2026-10-13/manifest.json) | Original capture hashes and source consistency at the sponsor-review checkpoint |

Those four captures were inspected when packaged and are not reconstructed screenshots. The original source hashes certify that checkpoint, not subsequent changes. Preserve them; create a separate final revision record rather than overwriting historical provenance.

## Submission provenance and exclusions

The [official form](https://docs.google.com/forms/d/e/1FAIpQLScr54QzuASZyUPhYYGwZ3tQ1DpU4_FEAIPsVATDrMv4I4fYbw/viewform), linked by the official event listing, was inspected in signed-in Chrome on 14 October: deadline **16 October 2026, 23:59 GMT+8**. The user completed the first page and entered captain/contact information themselves. The project page is inspected: browser-experience, 5-8-minute video and GitHub URLs are mandatory; uploads are cover up to 1 MB, one conversation-history file up to 10 MB including at least three screenshots, and one architecture PPT up to 10 MB. Title, blurb under ten words and description covering users, pain point, design/prompting and business value are required; social bonus is optional. No final submission has been made. [Sponsor verification](../planning/SPONSOR_VERIFICATION.md) preserves provenance and unresolved policies.

Exclude `.env*` except the reviewed example configuration, `.runtime`, database credentials/data, API keys, reviewer tokens, private account/voucher captures, private evaluation keys and actual personal/health data from the submission bundle. Raw local test outputs may expose fixture information; use the sanitized sponsor log. Do not redistribute the full event handbook or source photographs merely because local copies exist. Confirm source/dependency rights and repository access against the actual form requirements.

## Final location record — completed items and remaining work

| Item | Final value |
| --- | --- |
| Repository URL accessible to judges | [ajayasai/EvidenceLoop](https://github.com/ajayasai/EvidenceLoop), published after user approval; source URL filled in the form |
| Browser-experience URL accessible to judges | [Render demo](https://evidenceloop-aj-001.onrender.com/); public Chrome FERN journey completed through consented save/check-in. Supplied fictional examples only, no live AI/reviewer controls, records may reset on restart; URL filled in the form. |
| Initial published source commit | `6f1b125`; subsequent documentation synchronization and final package hash are separate records |
| Recorded build date and latest check reference | 14 October local candidate: 599 Python tests plus 51 subtests, zero failures/errors/skips, 87.134 seconds; 35 frontend tests/build passed and interfaces exported. Corrected public CI at `f51c764` passed 599 + 51 in 10.51s, 35 frontend/build, Docker and constrained smoke; separate public API checks passed. Render Live at initial `6f1b125`; public Chrome journey/video verified. See [results](ARCHITECTURE_AND_RESULTS.md). |
| Video URL / duration / access check | [Hosted video](https://evidenceloop-aj-001.onrender.com/demo-video.html), 363.782993 seconds (6:03.78). Full local decode passed; public muted playback advanced to 11.253323s, readyState 4, playing with no error; URL filled. |
| Cover filename / dimensions | [cover.png](../../artifacts/submission-20261014/cover.png), 1280×720, 16:9; uploaded to the form |
| Volunteer observation report, if actually completed | Pending; no observations collected in this package |
| Uploads / submission receipt | All three uploads show accepted chips and all three URLs are filled. Final Submit untouched; no submission acknowledgment. |

