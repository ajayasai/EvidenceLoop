# Public demonstration deployment

The portable Docker image serves a **guided fictional replay**, not live AI or a clinically reviewed service. This is a deployment candidate, not a published URL. Creation of a public repository, hosting account/service, or competition submission needs the user's approval. Additional spend must remain zero.

## Hosting choice and cost boundary

As checked on 14 October 2026, [Render Free web services](https://render.com/docs/free) support a disposable Docker service. The [Free compute plan](https://render.com/docs/compute-plans) has 512 MB RAM and 0.1 CPU. The workspace's 750 monthly free instance-hours are shared across its free services. Confirm the account has no payment method and sufficient free quota before creating this service. Without a payment method, quota exhaustion can suspend service rather than purchase additional usage. Do not select paid compute, attach a persistent disk, or create an external database.

The checked-in [render.yaml](../render.yaml) explicitly sets `plan: free`: omitting this setting can select a paid default under the [Blueprint specification](https://render.com/docs/blueprint-spec). The Docker image, database, and application all run inside that one service. No paid pre-deploy command is required. Hosting availability and account eligibility remain unverified until an authorized deployment succeeds.

Hugging Face is **not a verified zero-cost creation route**. Its current [Spaces overview](https://huggingface.co/docs/hub/spaces-overview) requires a paid PRO/Team entitlement to create new Docker compute Spaces, even though CPU Basic's hourly hardware rate is free. Do not create or upgrade an account to use this route. The image remains portable if an already eligible account is later confirmed without additional spending.

## What the container does

- Node builds the production frontend in a separate image stage. The runtime contains Python, the locked dependencies, PostgreSQL 15, static assets and the synthetic evidence pack. It downloads no inference model and uses no API provider.
- The non-root UID 1000 entrypoint initializes a fresh private temporary database directory for every launch. PostgreSQL listens only on `127.0.0.1:15432`; no database port is exposed. Separate random administrative and non-owner application passwords are created at runtime. The bootstrap password file is deleted immediately after initialization. Neither password is printed or sent to the browser.
- Migrations run as the administrative identity, then the API receives only the restricted application database identity. The schema ownership checks used by local development remain active. PostgreSQL has 16 MB shared buffers, 1 MB work memory, at most 20 connections, and no parallel workers; the API uses one process and caps concurrent requests at 24. These are conservative settings, **not proof of fitting the 512 MB limit**.
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

The [deny-by-default .dockerignore](../.dockerignore) excludes private environment files, credentials, runtime data, models, sealed evaluation cases, caches, unrelated generated artifacts and evidence documents. It explicitly includes the inspected public video page, MP4, cover and captions so the required demo-video link can use the same host. Docker also copies only the required runtime files. The source archive includes these deployment definitions and selected public media, and must be regenerated after final verification; an earlier archive does not contain this work.

## Verified locally and remaining checks

Docker and Podman are absent from both Windows and the available Ubuntu WSL environment. **The Linux image has not been built or run locally.** The same Python supervisor was smoke-tested using the existing portable Windows PostgreSQL binaries: fresh database initialization, separate non-owner role, migration to schema v2, HTTP health readiness, public replay flags, Secure cookies and graceful shutdown passed. No external service was contacted by this smoke test.

The existing public-repository-only GitHub Actions workflow now includes a Docker build and a readiness/session smoke check constrained to 512 MB RAM, no swap, and 0.1 CPU. It does not publish an image or create hosting resources. The check has a bounded 210-second readiness wait and always removes the test container. This is prepared automation, not a completed CI result.

```powershell
.\.venv\Scripts\python.exe scripts/smoke_deployment.py --postgres-bin .runtime/pgsql/bin
```

The smoke script leaves its isolated generated temporary directory for diagnostics and never reuses the development database. It does not establish Linux image compatibility, public TLS behavior or memory use on a 512 MB host.

Before calling a public URL working, build the image, inspect container resource use, wait for database-ready health checks, and test the actual HTTPS URL with two browser sessions. Exercise example → confirmation → assessment → preview → consent → save → check-in → delete, verify other browsers cannot read the receipt, confirm reviewer endpoints remain forbidden, and confirm a restart loses fictional records. Use a direct app URL; this app denies framing. Render can sleep after 15 minutes without traffic and take about a minute to wake, so warm the demo shortly before the presentation. No always-on or uninterrupted availability claim is justified on this tier.
