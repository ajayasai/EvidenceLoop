# Sponsor and competition verification

Handbook inspected 30 September 2026; status updated 14 October 2026. CONFIRMED means observed; NEEDS VERIFICATION means unresolved. Proposed choices do not establish installations, entitlements or working integrations.

Update, 14 October 2026: the user explicitly confirmed registration for **Healthcare Challenge 2: long-term self-care**. The official Tencent-hosted Luma listing gives 16 October for submission, 23 October for finalists and 3 November for Demo Day. Its linked [submission form](https://docs.google.com/forms/d/e/1FAIpQLScr54QzuASZyUPhYYGwZ3tQ1DpU4_FEAIPsVATDrMv4I4fYbw/viewform), inspected in signed-in Chrome, confirms **Friday, 16 October 2026 at 23:59 GMT+8**. Sponsor access, event-credit redemption and genuine authenticated development review were verified on 13 October; team eligibility and submission acceptance remain separate checks.

## Verified sponsor progress — 13 October 2026

The user approved the legal terms, and normal Google sign-in succeeded in Chrome. Event redemption added **1,000 credits**. The WorkBuddy web UI at `codebuddy.ai/agents` showed the **Free** plan and **1,350 credits** after redemption and again at the ending check at **22:23 Singapore time**. No paid setup was used.

**Hy3**, listed at **0.00×**, was genuinely used in an authenticated account conversation for source-only consent and source-withdrawal review. The conversation contains the real request, findings and a corrected test proposal. Codex applied the test changes and ran local tests; WorkBuddy did not execute them. Production logic was unchanged. The five added parameter cases cover denied save with fresh and existing data, denied check-in, and source withdrawal after the API precheck but before the storage transaction for save and check-in. The withdrawal cases establish those ordered scenarios, not general concurrency correctness.

The initial consent selection passed **5 tests, with 8 deselected**. The combined run passed **44 tests in 51.89 seconds**, with one existing Starlette/httpx deprecation warning:

```text
.venv/Scripts/python.exe -m pytest -o addopts='' tests/test_api.py tests/test_api_review.py tests/test_review.py -q -rs --tb=short
```

The [completed sponsor evidence package](../sponsor-evidence/2026-10-13/README.md) contains **four inspected public-safe PNGs** showing the consent-boundary request, source-withdrawal review, transaction-test proposal and corrected closing review of locally reported validation. The first capture retains its original source-withdrawal filename, but its visible request concerns consent. All were captured directly with the account sidebar collapsed and contain no visible account email or voucher. A sanitized test log and hash manifest record the validation and confirm that the three inspected production source files remained unchanged. The closing review distinguishes consent denial (422) from source-withdrawal conflict (409) and attributes the corrections and local tests to Codex. Sponsor development use and its local proof package are complete; organizer acceptance, complete submission readiness, clinical review and runtime AI qualification remain separate.

Historical access note: an earlier CodeBuddy CLI sign-in failed with `getaddrinfo ENOENT www.codebuddy.ai`; read-only DNS inspection returned `0.0.0.1`. No network or security protection was changed. Successful browser access supersedes that access blocker, without establishing that the CLI now works.

## Authoritative sources and provenance

The exact event is [Tencent Cloud AI CAN DO IT Hackathon Singapore 2026](https://tch.tencentcloud.com/contest/44), co-hosted with AI Singapore. Its [Tencent-hosted Luma listing](https://luma.com/26fqf3hy) confirms the five tracks and the Healthcare Challenge 2 title. Do not borrow deadlines, eligibility or benefits from the separate Singapore Agent Development Challenge, Age Well challenge, or [UTM Malaysia event](https://tch.tencentcloud.com/contest/41).

The event's Developer Guides button opened the [official 43-page handbook](https://heikesong-global-1256915710.cos.ap-hongkong.myqcloud.com/online_video/3af2d08d-d3f0-4998-98a5-a820bd245910.pdf). Page numbers below refer to physical PDF pages. Downloaded copy: `tmp/pdfs/Tencent_AI_Singapore_2026_Handbook.pdf`; SHA-256: `7ed86bbc897308d188aa80aa7f4bf68c0de687e2a0465a858af0438a2cf29e87`. Preserve this provenance alongside any later rule revision. Its presence is not permission to redistribute the full handbook.

## Confirmed competition requirements

| Topic | Verified fact and source |
|---|---|
| Entry | 1–3 people; all must be based in Singapore; one team registration (handbook p39). |
| Track | Choose one healthcare case; identify it in the presentation. Challenge 2 permits focused long-term self-care; medication explanation must not become medication advice (pp27,32–35). |
| Sponsor use | Original project using CodeBuddy or WorkBuddy; proof is mandatory for scoring. At least three development-chat screenshots or a recording (p37). |
| Submission copy | Actual form page 2, inspected 14 October: Project Title; blurb under ten words; description covering target users, pain point, design/prompting and business value. |
| Required links | Actual form page 2 requires a Project Web Link providing a browser experience, a 5–8-minute Demo Video Link, and a GitHub source URL. This supersedes handbook p37's optional video/live-link summary for form completion. |
| Required uploads | Cover: maximum 1 MB; WorkBuddy/CodeBuddy Conversation History: one file, maximum 10 MB, including history and at least three screenshots; Architecture Diagram PPT: one file, maximum 10 MB. Handbook p37 specifies a 16:9 cover and recommends 380×216 pixels. |
| Social bonus | Optional in the actual form; no post or bonus is claimed. |
| Healthcare materials | Live demonstration, architecture/trust boundaries/tradeoffs and complete GitHub source (p35). |
| Dates | Submission Friday, 16 October 2026 at 23:59 GMT+8 (official form, inspected 14 October); finalists 23 October; Demo Day 3 November 2026. Handbook calls Demo Day TBC; current Luma omits that qualifier (p38; Luma). |
| Judging | Track details follow registration; ten equal-weight final dimensions; top two teams per track shortlisted (pp38,40). |
| Rights | Entrants retain IP; limited noncommercial promotional license covers submitted project/team materials (p42). |

These are compact rule summaries, not a substitute for registration terms. The handbook includes apparent template errors, including unrelated banking and game references; ask for clarification when wording affects acceptance. Follow its explicit CodeBuddy/WorkBuddy minimum rather than assuming the looser participation paragraph makes Miora-only usage sufficient.

## Development, design, runtime and provisioning

**Development: WorkBuddy review is the demonstrated sponsor use.** The authenticated source-only review above replaces the earlier proposed CodeBuddy CLI exercise. Preserve dated conversation evidence and its connection to the test changes; attribute implementation and local test execution to Codex. Do not manufacture a retrospective conversation or call Codex work CodeBuddy work. [CodeBuddy's Agent SDK documentation](https://www.codebuddy.ai/docs/cli/sdk) describes TypeScript/JavaScript and Python programmatic access but labels the SDK Preview. This project does not require that SDK to power the patient interface.

**Coordination: further WorkBuddy use is optional.** The verified development review used the web UI. Its [quick start](https://www.workbuddy.ai/docs/workbuddy/Quickstart) describes a desktop agent workstation, and its [model configuration documentation](https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model) describes consuming custom model endpoints. Neither those documents nor the completed review establish a production WorkBuddy inference API, a stable WorkBuddy SDK, or permission to transmit patient data. Keep any further task within the source-only or fictional-data scope and verified free allowance.

**Design: Miora is optional.** Consider it for a nonclinical cover or visual asset only. No reliable public Miora runtime API, account availability, usable entitlement or output license was verified here. Do not place it on the critical path or describe design-tool use as clinical inference.

**Runtime: select independently.** A provider-neutral application adapter should isolate the two planned model stages. Validate the actual endpoint, model identifier, structured-output/tool behavior, input limits, latency, failures and costs on the account that will run the demonstration. [CodeBuddy authentication documentation](https://www.codebuddy.ai/docs/cli/env-vars) distinguishes model API keys and platform tokens; neither should be inferred from a desktop login or credit balance. Credentials remain server-side and out of screenshots.

**Provisioning: optional Tencent infrastructure.** [Agent Runtime's quick start](https://cloud.tencent.com/document/product/1814/123816) documents E2B-compatible sandbox access and an example Guangzhou domain; its [sandbox API documentation](https://cloud.tencent.com/document/product/1814/124816) establishes documented APIs. This proves product documentation exists, not Singapore region availability, account entitlement, privacy suitability or a deployed EvidenceLoop service. A sandbox is infrastructure, not a medical reasoning model. Avoid adding it merely for branding.

## Verification and evidence checklist

Owners are proposed roles; none is confirmed. One builder may hold several operational roles; clinical sign-off requires suitable independent expertise. Changed models, evidence or safety behavior require regression.

| Complete | Owner / issue | Evidence and acceptance | Fallback / consequence |
|---|---|---|---|
| [ ] | Team lead: eligibility | User confirmed AJ_001 solo entry, international student at NTU, Master's in AI; captain/contact details were entered by the user. Organizer acceptance and any additional eligibility declarations remain separate. | Do not infer citizenship, legal name or contact details from student status or copy private form values into public files. |
| [x] | Submission owner: form requirements inspected | User completed page 1. Page 2's copy, required links and upload limits are recorded above. | Form completion is not final submission; verify required link access, upload acceptance and acknowledgment. |
| [x] | Submission owner: cutoff | Official submission form confirms Friday, 16 October 2026 at 23:59 GMT+8; inspected 14 October. | Internal ready target remains 15 October. |
| [ ] | Submission owner: edit/late policy | Confirm whether submitted answers can be edited and how late submissions are handled. | Do not assume edits or late acceptance are permitted. |
| [ ] | Team lead: rubric/format | Retrieve registered-track criteria, judging round rules, live-demo duration and Q&A format. | Use the published rubric provisionally; keep scoring claims qualified. |
| [x] | Developer: sponsor proof package | Genuine WorkBuddy review, four inspected captures, applied test changes, sanitized validation log and source/artifact hashes are recorded in [the evidence package](../sponsor-evidence/2026-10-13/README.md); original evidence retained. | Organizer acceptance remains unverified and separate from local package completion. |
| [ ] | Developer: runtime access | Dated smoke-call log records provider, model, region, limits and billing configuration; no secrets in logs. | Test an approved alternative; otherwise only labeled replay/architecture can be demonstrated. |
| [ ] | Infrastructure owner: regional services | Account console plus written service documentation confirm available region, quotas and needed permissions. | Use the simplest approved deployment; disclose unavailable sponsor infrastructure. |
| [ ] | Privacy owner: data handling | Review provider retention, logging, training use, deletion, subprocessors and cross-border handling for actual data flows. | Synthetic-only deployment; no real medical uploads or implied privacy certification. |
| [x] | Submission owner: source publication | User approved publication, free deployment and form uploads; [GitHub source](https://github.com/ajayasai/EvidenceLoop) published at initial commit `6f1b125`, and source URL filled in the form. | Publication does not establish hosted app availability or final entry acceptance. Keep source/artifact rights and privacy boundaries intact. |
| [ ] | Design owner: assets/license | Keep asset origin, generation record, permitted use and required attribution; inspect screenshots for third-party images. | Use original typography and simple shapes with known rights. |
| [ ] | Clinical/evaluation owners: claims | Signed source mappings and actual run artifacts support every demo claim, count and limitation. | Reduce scope and report incompleteness; never replace missing evidence with estimates presented as results. |
| [ ] | Submission owner: final package | Validate links in a clean browser, archive exact submitted versions, and retain the submission acknowledgment. | Repair access before cutoff; local readiness is not proof of submission. |

## Unresolved access and publication questions

The [submission form](https://docs.google.com/forms/d/e/1FAIpQLScr54QzuASZyUPhYYGwZ3tQ1DpU4_FEAIPsVATDrMv4I4fYbw/viewform) was reached through the official Luma listing's new `forms.gle` shortcut, which resolves to the same underlying form. The user completed its first page in Chrome, including captain/contact details and the Healthcare/Case Study 2 selection; private contact values are not copied into public documentation. The second page has now been inspected and its mandatory copy, link and upload requirements are recorded above. Edit/late-submission policy, accepted repository access arrangements, any remaining declarations and final receipt procedure are still unverified. No final submission has occurred through this work.

The prepared [single sponsor PDF](../../artifacts/submission-20261014/sponsor-evidence.pdf) contains a clearly labeled history summary, four actual conversation captures and the sanitized 44-test result, with truthful WorkBuddy/Codex attribution. It is 346,975 bytes, below 10 MB, and has been rendered and visually checked. It preserves selected conversation excerpts rather than claiming a complete account transcript. The cover is 51,994 bytes and deck revision 2 is 455,581 bytes, below their limits. All three uploads show accepted chips and all three required URLs are filled. Final Submit is untouched; no submission acknowledgment has been received.

The user explicitly approved source publication, free deployment and uploads. The [public repository](https://github.com/ajayasai/EvidenceLoop) was created at initial commit `6f1b125`. Render reports Live for that commit in Singapore on Free compute (0.1 CPU, 512 MB), with no added API secrets or card; auto-deploy is off. The [public HTTPS FERN journey](https://evidenceloop-aj-001.onrender.com/) completed confirmation, assessment, preview, explicit save consent and a consented Done self-reported check-in in Chrome; the no-live-AI banner and absence of reviewer controls were observed. The [hosted video](https://evidenceloop-aj-001.onrender.com/demo-video.html) was playing muted at 11.253323s / 363.782993s with readyState 4 and no error. The account remains Hobby with a $0 build-spend limit. The corrected [public CI run](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) at `f51c764` passed 599 tests plus 51 subtests in 10.51 seconds, 35 frontend/build, Docker and constrained container smoke; separate public API checks passed. Application code matches deployed `6f1b125`; the earlier readiness-harness connection reset remains recorded. These checks do not establish clinical validation or final form submission.

Before a later publication action, reconcile the actual form terms with the handbook, source licenses and collaborator permissions. A public-health fact sheet can be appropriate to cite while an embedded photograph has separate rights. Keep evidence excerpts narrowly necessary and do not assume rights to redistribute full publications. Establish an explicit evidence cutoff, approved-library manifest and latest trust check for the release; “current” must describe that bounded library, not all medical knowledge.
