# Free hosting verification — 14 October 2026

The actual Healthcare submission form requires a browser-accessible project URL, a 5–8-minute video URL and a GitHub source URL. The handbook's optional-link wording is not the final form's requirement. The project remains a fictional engineering demonstration with unqualified live AI disabled.

## Verified account state

The user explicitly approved normal Google sign-in to Render, acceptance of its account terms if necessary, and Hobby/Free setup with no card or payment method. The authenticated dashboard showed an existing **Hobby** workspace, **No card on file**, **No pending charges**, 750 included free instance-hours, 5 GB included bandwidth and 500 included build minutes. The build-pipeline settings showed a **$0 monthly spend limit** and explicitly stated that builds stop when both the limit and included minutes are exhausted. No card, paid plan, paid disk, paid database or external model key was added.

Account and billing screenshots remain private under `.runtime/submission-approval`; they are not submission assets. These account observations do not prove deployment success. Source publication and service creation require their own concrete review; no URL should be advertised as working before an external browser check.

## Selected deployment approach

Prepare one Docker web service on explicitly selected **Free** compute, with ephemeral loopback PostgreSQL in the same container. A fresh database is initialized on startup. The public interface is a guided fictional example workflow: live inference and reviewer controls are disabled, original claim input is restricted to supplied examples, and saved steps can disappear on sleep, restart or redeployment. The video page uses the already inspected screenshot walkthrough and captions; it does not claim live inference or real-time screen recording.

Render documents 0.1 CPU and 512 MB RAM for Free compute. Cold starts, suspension and storage loss are material demonstration limits. The explicit `plan: free` setting is required; a default or omitted compute plan must not be treated as free. No payment method is to be configured. If account-specific verification demands a card, stop that route rather than enabling billing.

Primary references, checked 14 October:

- [First deployment](https://render.com/docs/your-first-deploy): free setup and supported runtimes.
- [Free service limits](https://render.com/docs/free): idle behavior, ephemeral storage, included hours, no-payment suspension behavior and limitations.
- [Compute plans](https://render.com/docs/compute-plans) and [pricing](https://render.com/pricing): current resource and workspace allowances.
- [Blueprint reference](https://render.com/docs/blueprint-spec): explicit free plan and region configuration.
- [Docker](https://render.com/docs/docker) and [web-service ports](https://render.com/docs/web-services): build/runtime behavior and public port binding.

New Hugging Face Docker Spaces are not a substitute: their current [overview](https://huggingface.co/docs/hub/spaces-overview) requires a paid plan for compute Space creation even where CPU Basic hourly hardware is free. Koyeb's current [pricing FAQ](https://www.koyeb.com/docs/faqs/pricing) requires a card and describes a prorated Pro signup charge. Neither route was provisioned.

## Verification limits

Docker/Podman are unavailable on this Windows host. A local PostgreSQL supervisor smoke test checks startup, schema migration, a non-owner API role, public replay and Secure cookies, but does not prove the Linux image fits the free memory/CPU envelope. Public-repository standard GitHub Actions runners can build and run the container without paid runner minutes; the workflow retains its public-only guard. Image build, service startup, external HTTPS flow and video access must be verified before calling the hosted demo complete.
