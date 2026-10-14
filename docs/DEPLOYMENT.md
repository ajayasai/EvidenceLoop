# Public demonstration deployment

The Docker image serves a **guided fictional replay**, not live AI or a clinically reviewed service. The user approved public source/media publication, free CI and Render Free deployment on 14 October 2026. The [public application](https://evidenceloop-aj-001.onrender.com/), [captioned walkthrough](https://evidenceloop-aj-001.onrender.com/demo-video.html) and [source repository](https://github.com/ajayasai/EvidenceLoop) are now verified. The three prepared form-file uploads are authorized; the final Submit action remains reserved for the user. Additional spend must remain zero.

## Hosting choice and cost boundary

As checked on 14 October 2026, [Render Free web services](https://render.com/docs/free) support a disposable Docker service. The deployed Singapore service uses the [Free compute plan](https://render.com/docs/compute-plans): 512 MB RAM and 0.1 CPU. The account showed Hobby, no card, no pending charges and a $0 build-spend cap. The workspace's 750 monthly free instance-hours are shared across its free services. Without a payment method, quota exhaustion can suspend service rather than purchase additional usage. Do not select paid compute, attach a persistent disk, or create an external database.

The checked-in [render.yaml](../render.yaml) explicitly sets `plan: free`: omitting this setting can select a paid default under the [Blueprint specification](https://render.com/docs/blueprint-spec). The Docker image, database, and application all run inside one service. The live service is named `evidenceloop-aj-001`, uses port 10000 and health path `/api/health`, and has automatic deployment **Off**. Its dashboard showed **Live**. No paid pre-deploy command, API secret or external database is configured. Account observations and the completed deployment are recorded in [free hosting verification](FREE_HOSTING_20261014.md).

Hugging Face is **not a verified zero-cost creation route**. Its current [Spaces overview](https://huggingface.co/docs/hub/spaces-overview) requires a paid PRO/Team entitlement to create new Docker compute Spaces, even though CPU Basic's hourly hardware rate is free. Do not create or upgrade an account to use this route. The image remains portable if an already eligible account is later confirmed without additional spending.

## What the container does

- Node builds the production frontend in a separate image stage. The runtime contains Python, the locked dependencies, PostgreSQL 15, static assets and the synthetic evidence pack. It downloads no inference model and uses no API provider.
- The non-root UID 1000 entrypoint initializes a fresh private temporary database directory for every launch. PostgreSQL listens only on `127.0.0.1:15432`; no database port is exposed. Separate random administrative and non-owner application passwords are created at runtime. The bootstrap password file is deleted immediately after initialization. Neither password is printed or sent to the browser.
- Migrations run as the administrative identity, then the API receives only the restricted application database identity. The schema ownership checks used by local development remain active. PostgreSQL has 16 MB shared buffers, 1 MB work memory, at most 20 connections, and no parallel workers; the API uses one process and caps concurrent requests at 24. A resource-limited CI startup passed as recorded below; sustained or peak-load capacity remains unmeasured.
- The public mode accepts only catalog text in replay mode. Judges can inspect and edit its interpretation; edited meanings retain the existing context-only comparison restriction. All reviewer and source-withdrawal endpoints are blocked. Live inference and alignment are disabled even if platform environment variables accidentally contain provider/reviewer configuration.
- Cookies are `Secure`, `HttpOnly`, and `SameSite=Strict`. The exact HTTPS app origin is validated and allowed as a host. Mutations retain origin and CSRF checks. Anonymous saved records remain isolated by their secret browser owner cookie. The process does not trust forwarded headers, and the public mode allows at most 32 concurrent anonymous sessions.
- There is no persistence guarantee. Render can erase the local filesystem on restart, redeploy, or idle spin-down. Sessions and saved fictional steps disappear. The application displays this notice throughout the public demonstration. Raw claim drafts are still temporary and saving still needs explicit consent.

## Local build and checks

From the repository root on a computer with Docker:

```sh
docker build -t evidenceloop-demo .
docker run --rm -p 7860:7860 -e APP_ORIGIN=https://demo.example.org evidenceloop-demo
```

An HTTP localhost health request is supported at `http://127.0.0.1:7860/api/health`. Browser mutations require the configured HTTPS origin and secure cookies, so this command alone is a health/bootstrap check. Use a trusted local HTTPS reverse proxy or an authorized HTTPS host for the complete public-mode browser workflow. Do not weaken cookie or origin settings to make an HTTP test work. Normal local development remains available through the existing local runbook.

`PORT` defaults to 7860 and accepts 1024–65535. Render's blueprint sets 10000. `APP_ORIGIN` is the exact HTTPS origin, with no credentials, path, query, or fragment. If absent, the entrypoint uses Render's provided `RENDER_EXTERNAL_URL`. No database URL, API key, reviewer token, persistent volume, or billing setup should be configured.

The [deny-by-default .dockerignore](../.dockerignore) excludes private environment files, credentials, runtime data, models, sealed evaluation cases, caches, unrelated generated artifacts and evidence documents. It explicitly includes the inspected public video page, MP4, cover and captions so the required demo-video link uses the same host. Docker also copies only the required runtime files. The published source includes these deployment definitions and selected public media. Source archives remain immutable checkpoints and must be regenerated when documentation or source changes.

## Executed verification

Docker and Podman are absent from both Windows and the available Ubuntu WSL environment. The same Python supervisor was first smoke-tested using the existing portable Windows PostgreSQL binaries: fresh database initialization, separate non-owner role, migration to schema v2, HTTP health readiness, public replay flags, Secure cookies and graceful shutdown passed. No external service was contacted by that local smoke test.

The public-repository-only [GitHub Actions run 38530016145](https://github.com/ajayasai/EvidenceLoop/actions/runs/38530016145) passed on commit `f51c7641a22b09a0b976462f3bdd102fef017341`: 599 backend tests plus 51 subtests in 10.51 seconds, 35 frontend tests, production frontend build, Linux Docker build and readiness/session smoke constrained to **512 MiB, no swap and 0.1 CPU**. Readiness took about **24 seconds** and the subsequent memory sample was **119.5 MiB / 512 MiB**. The check has a bounded 210-second readiness wait and always removes the test container; it does not upload an image or create hosting resources. The sampled memory is not a sustained-load or peak-memory guarantee.

The live service runs commit `6f1b125f20f9d49bdba2cccb2b2ea4ef67002d91`, with application/container code identical to the passing CI commit. That later commit only corrects the readiness probe to retry a connection reset during startup and adds CI failure diagnostics. Automatic deployment remains off, so documentation-only source updates do not restart the live app.

```powershell
.\.venv\Scripts\python.exe scripts/smoke_deployment.py --postgres-bin .runtime/pgsql/bin
```

The local smoke script leaves its isolated generated temporary directory for diagnostics and never reuses the development database. Linux image/resource and public TLS results come from the separate CI and hosted checks, not from this Windows command.

On the actual public HTTPS URL, Chrome passed example confirmation → source assessment → preview → consent → save → **Done · self-reported** check-in. Video playback reached **11.25 seconds** of **363.783 seconds**, with readyState **4** and visible captions. [The browser record](PUBLIC_BROWSER_VERIFICATION_20261014.md) preserves the workflow and captures. [A separate 33-request API check](PUBLIC_API_VERIFICATION_20261014.md) verified independent-session ownership, CSRF/origin/mode/reviewer restrictions, own-data deletion, MP4 range delivery and captions. These are small fictional engineering checks; restart durability, sustained load and uninterrupted service are not established.

Use a direct app URL; this app denies framing. Render can sleep after 15 minutes without traffic and take about a minute to wake, so warm the demo shortly before the presentation. Saved demo records remain disposable. No always-on or uninterrupted availability claim is justified on this tier.
