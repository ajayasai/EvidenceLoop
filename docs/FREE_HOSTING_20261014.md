# Free hosting verification — 14 October 2026

The actual Healthcare submission form requires a browser-accessible project URL, a 5–8-minute video URL and a GitHub source URL. The handbook's optional-link wording is not the final form's requirement. The project remains a fictional engineering demonstration with unqualified live AI disabled.

## Verified account state

The user explicitly approved normal Google sign-in to Render, acceptance of its account terms if necessary, and Hobby/Free setup with no card or payment method. The authenticated dashboard showed an existing **Hobby** workspace, **No card on file**, **No pending charges**, 750 included free instance-hours, 5 GB included bandwidth and 500 included build minutes. The build-pipeline settings showed a **$0 monthly spend limit** and explicitly stated that builds stop when both the limit and included minutes are exhausted. No card, paid plan, paid disk, paid database or external model key was added.

Account and billing screenshots remain private under `.runtime/submission-approval`; they are not submission assets. After reviewing the concrete source/media package, the user authorized public GitHub publication, free CI, Render Free deployment and the three prepared form-file uploads. The final Submit action remains reserved for the user. The completed deployment and external checks are recorded below; account access alone was not treated as a working application.

## Selected deployment approach

One Docker web service is deployed in **Singapore** on explicitly selected **Free** compute, with ephemeral loopback PostgreSQL in the same container. The dashboard showed **Live**. It uses **0.1 CPU / 512 MB**, **PORT=10000**, health path **`/api/health`** and automatic deployment **Off**. No model API key, reviewer secret, paid disk or external database was configured.

The public [guided demo](https://evidenceloop-aj-001.onrender.com/), [captioned video page](https://evidenceloop-aj-001.onrender.com/demo-video.html) and [GitHub source](https://github.com/ajayasai/EvidenceLoop) are accessible. A fresh database is initialized on startup. The public interface is a guided fictional example workflow: live inference and reviewer controls are disabled, original claim input is restricted to supplied examples, and saved steps can disappear on sleep, restart or redeployment. The video uses the inspected screenshot walkthrough and captions; it does not claim live inference or real-time screen recording.

Render documents 0.1 CPU and 512 MB RAM for Free compute. Cold starts, suspension and storage loss are material demonstration limits. The explicit `plan: free` setting is required; a default or omitted compute plan must not be treated as free. No payment method is to be configured. If account-specific verification demands a card, stop that route rather than enabling billing.

Primary references, checked 14 October:

- [First deployment](https://render.com/docs/your-first-deploy): free setup and supported runtimes.
- [Free service limits](https://render.com/docs/free): idle behavior, ephemeral storage, included hours, no-payment suspension behavior and limitations.
- [Compute plans](https://render.com/docs/compute-plans) and [pricing](https://render.com/pricing): current resource and workspace allowances.
- [Blueprint reference](https://render.com/docs/blueprint-spec): explicit free plan and region configuration.
- [Docker](https://render.com/docs/docker) and [web-service ports](https://render.com/docs/web-services): build/runtime behavior and public port binding.

New Hugging Face Docker Spaces are not a substitute: their current [overview](https://huggingface.co/docs/hub/spaces-overview) requires a paid plan for compute Space creation even where CPU Basic hourly hardware is free. Koyeb's current [pricing FAQ](https://www.koyeb.com/docs/faqs/pricing) requires a card and describes a prorated Pro signup charge. Neither route was provisioned.

## Executed verification and limits

Docker/Podman are unavailable on this Windows host. A local PostgreSQL supervisor smoke test passed startup, schema migration, a non-owner API role, public replay and Secure cookies. The public-only [Linux CI run 38530016145](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) subsequently passed on commit `f51c7641a22b09a0b976462f3bdd102fef017341`: 599 backend tests plus 51 subtests in 10.51 seconds, 35 frontend tests, production build, Linux Docker image build and resource-limited startup. The container reached readiness in about 24 seconds under 512 MiB, no swap and 0.1 CPU. Its post-startup memory sample was 119.5 MiB / 512 MiB; this is not a peak or load-test measurement.

The service runs commit `6f1b125f20f9d49bdba2cccb2b2ea4ef67002d91`. Its application/container code matches the passing CI commit; that later commit only fixes the readiness harness's handling of connection resets during startup and adds failure diagnostics. Auto-deploy remains off, so subsequent documentation commits do not silently restart the service.

External Chrome checks completed confirmation → source assessment → consent → save → **Done · self-reported** check-in. The hosted video played to 11.25 seconds of its 363.783-second duration, with readyState 4 and captions visibly rendered. [The browser record](PUBLIC_BROWSER_VERIFICATION_20261014.md) and [separate 33-request API boundary check](PUBLIC_API_VERIFICATION_20261014.md) preserve the details. The demo remains fictional, nonclinical and without live AI. These checks establish an observed working demonstration, not uninterrupted uptime, durable storage, clinical validation or competition acceptance. No final form submission is claimed.
