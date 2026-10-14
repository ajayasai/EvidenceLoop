# EvidenceLoop submission draft

Prepared 14 October 2026 for **Healthcare Challenge 2: long-term self-care**. Following the user's approval, [GitHub source](https://github.com/ajayasai/EvidenceLoop) was published and the [public Render demo](https://evidenceloop-aj-001.onrender.com/) passed a Chrome walkthrough through replay, confirmation, assessment, preview, explicit save consent and a consented self-reported check-in. The [hosted video](https://evidenceloop-aj-001.onrender.com/demo-video.html) played successfully. Render is Live at initial commit `6f1b125`. The corrected [public CI run](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) at `f51c764` and separate public API checks passed. No volunteer study or final competition submission has been completed.

The user supplied **AJ_001** as the entry/team identifier and confirmed a solo entry as an international student at **NTU**, studying for a Master's in AI. They completed captain/contact form details themselves; those private details are not reproduced here.

The official form deadline is **Friday, 16 October 2026, 23:59 GMT+8**. The internal recording/package target is 15 October. The first page is complete and project-page requirements are inspected; final submission is not complete. Form provenance and outstanding policies are in [sponsor and competition verification](../planning/SPONSOR_VERIFICATION.md).

## Use these assets

| File | Ready-to-use content |
| --- | --- |
| [ENTRY_DRAFT.md](ENTRY_DRAFT.md) | Title, nine-word blurb, short and full descriptions, Challenge 2 fit, sponsor attribution, cover copy and concise judge Q&A |
| [DEMO_6MIN.md](DEMO_6MIN.md) | Timed narration, matching shots, operating instructions and a one-minute demonstration cut |
| [ARCHITECTURE_AND_RESULTS.md](ARCHITECTURE_AND_RESULTS.md) | Implemented architecture, trust boundaries, engineering results and limits |
| [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md) | Exact source, evidence, test and sponsor artifact locations; publication exclusions |
| [USABILITY_TASKS.md](USABILITY_TASKS.md) | Facilitator script and three fictional tasks to run with three volunteers |
| [observations-template.csv](observations-template.csv) | Nine blank task records; no participants or results asserted |
| [Judging deck, revision 2](../../artifacts/submission-20261014/deck/EvidenceLoop-judging-deck-v2.pptx) and [cover](../../artifacts/submission-20261014/cover.png) | Ten editable slides and a 1280×720 cover; numerical slide results explicitly describe 13 October checkpoints |
| [Local video](../../artifacts/submission-20261014/EvidenceLoop-recorded-walkthrough.mp4) and [captions](../../artifacts/submission-20261014/EvidenceLoop-recorded-walkthrough.srt) | Static app captures with synthetic offline narration; corrected 6:03.78 export passed full decode checks |
| [Hosted video page](https://evidenceloop-aj-001.onrender.com/demo-video.html) and [page source](../../apps/web/public/demo-video.html) | Native controls, English VTT captions and narration transcript; hosted muted playback verified on 14 October |
| [Sponsor evidence PDF](../../artifacts/submission-20261014/sponsor-evidence.pdf) | One 346,975-byte PDF with a history summary, four actual conversation captures and the sanitized 44-test result; under the 10 MB upload limit |
| [Source bundle instructions](SOURCE_BUNDLE.md) | Reproducible local source archive preparation and exclusions; rebuild after the final source and documentation changes |

The existing [demo runbook](../DEMO_RUNBOOK.md) remains the application operating reference. Use a separate demo browser identity and fictional records. The produced video presents captured screens, not a recording of continuous live operation. Its narration does not establish a successful live-model run.

## Baseline to preserve until verified evidence changes

Live AI remains disabled and no candidate is qualified. The [14 October AI report](../AI_EXTRACTION_VERIFICATION_20261014.md) records the completed dated experiments, including known-regression semantic failures and bounded timeouts. The final low-reasoning run completed quickly but failed: 9/12 exact under the original labels and 10/12 under the separately recorded annotation interpretation. No further model experiments are planned for this package, and the fresh final/challenge partitions remain unrun. The deck and narration deliberately retain the historical [13 October checkpoint](../AI_EXTRACTION_VERIFICATION_20261013.md): 10/12 exact known-regression cases, with qualification failed. The installed demonstration library is fictional and nonclinical. Six partial NCCIH packets remain quarantined, with no qualified clinical approval. See [current build status](../BUILD_STATUS.md).

The latest local 14 October public-hosting candidate passed **599 Python tests plus 51 subtests in 87.134 seconds**, with no failures, errors or skips (650 JUnit entries). The frontend passed **35 tests** and its production build; eight JSON schemas, enums and OpenAPI were exported. The corrected [public CI run](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) at `f51c764` passed 599 tests plus 51 subtests in 10.51 seconds, 35 frontend tests/build, Docker build and the constrained container smoke check. The earlier readiness-harness connection reset is retained as history; application code is identical to deployed `6f1b125`. Windows isolated-PostgreSQL supervisor smoke passed. Public Chrome checks completed the original FERN replay through consented saving and a Done self-reported check-in, with current trust checks. Hosted video playback advanced beyond 11 seconds without error. The separate public API checks also passed; see [their dated report](../PUBLIC_API_VERIFICATION_20261014.md). See [results](ARCHITECTURE_AND_RESULTS.md) and [captures](EVIDENCE_MANIFEST.md). These are engineering checks, not AI qualification or clinical validation.

The public mode is a guided fictional-only experience: live AI and reviewer controls are disabled, and claim input is restricted to supplied examples. The public banner and absence of reviewer controls were observed. Saved demonstration records may reset when the free host restarts; it is not durable personal record storage. The user authorized publication, free deployment and uploads. Render reports Live in Singapore on Free compute (0.1 CPU, 512 MB), within Hobby/no-card/$0 build-spend limits; no additional API secrets or card were added. Auto-deploy is off. [Free-hosting verification](../FREE_HOSTING_20261014.md) records the bounded walkthrough and remaining checks.

The narrative demonstrates the labeled replay/manual workflow. It must not imply that the same sequence was produced by live AI. Manual and live extraction cannot establish support for an exact directional effect from the current claim representation; their boundary is evidence context without a saved next step. Authored, unchanged replay has its own demonstration path. A better extraction score alone does not change that comparison boundary.

## Update points before the final package

| Update point | Replace only with observed facts |
| --- | --- |
| AI status in entry copy, demo segment 8 and results table | Exact model/revision, prompt/code hashes, dated complete qualification result, observed browser behavior and enabled stages. Preserve prior failed results. Until then, keep the disabled-AI copy. |
| Volunteer findings in results and closing narration | Actual participant/task denominators, unassisted versus assisted completion, time and corrections. The CSV is blank; no usability result exists in this package. |
| Clinical evidence statement | An actual qualified review and publication record, if obtained. A source import or AI review is insufficient. Otherwise keep the fictional demonstration boundary. |
| Release/build facts | Final frozen source revision/hash, checks on that revision, recording date and locally observed startup. Dated test runs below are not a test of future edits. |
| Submission locations | Real judge-accessible repository and video URLs, final cover filename, access check and submission acknowledgment. Do not use localhost as a public link. |

The user completed the first form page, including captain/contact fields. The project page requires a title, blurb under ten words, description covering users/pain point/design and prompting/business value, a cover up to 1 MB, a browser-experience URL, a 5-8-minute video URL, one conversation-history file up to 10 MB with at least three screenshots, one architecture PPT up to 10 MB, and a GitHub source URL. Social bonus is optional. All three URLs are filled and the cover, sponsor PDF and deck show accepted upload chips. The final Submit control is untouched; no final submission or acknowledgment has occurred. Edit/late policies remain unresolved.

## Finish the package

1. Rehearse [the six-minute sequence](DEMO_6MIN.md) three times, noting actual failures and timing. Use the same source/evidence state for the recording.
2. Run the fictional usability sessions if volunteers are available; retain blanks if they are not. Obtain separate permission before any recording or attributable quote.
3. Retain the verified local video, deck revision 2 and 16:9 cover; check the final upload's captions, playback and judge access. The video is a recorded screenshot walkthrough with synthetic narration; do not describe it as continuous live operation.
4. Use the single sponsor PDF for the observed conversation-history upload and the existing PPTX for architecture material. Keep private account/voucher captures and credentials excluded.
5. Supply and check the mandatory browser-experience, video and GitHub URLs, verify upload acceptance and any remaining form terms, then retain exact submitted assets and acknowledgment after authorized submission.

