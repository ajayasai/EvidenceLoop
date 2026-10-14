# Public deployment API verification — 14 October 2026

Target: https://evidenceloop-aj-001.onrender.com/  
Observed: 07:45–07:46 UTC (15:45–15:46 Singapore), 14 October 2026.  
Deployment reference supplied by the deploying agent: `6f1b125`; the HTTP responses do not attest a commit hash.

The bounded check used 33 sequential HTTP requests, two new independent `httpx` sessions, normal TLS certificate verification, and only fictional data. Both test sessions' own data were deleted afterward. No existing browser session, real health information, model service, reviewer authority, deployment settings, or billing controls were used or changed.

## Observed results

| Check | Observed result |
|---|---|
| HTTPS health | `200`; PostgreSQL; schema version `2`; status `ok`. |
| API response headers | `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`. |
| Public mode | Both sessions reported public demo, synthetic library, replay preference, and storage reset on restart. Live extraction/alignment and all reviewer roles were false; clinical review was `not_performed`. |
| Session cookies | Both `el_session` and `el_owner` were `Secure`, `HttpOnly`, and `SameSite=strict`. Independent sessions received different credentials; values were not logged. |
| Authentication and request boundaries | Saved-step request without a session: `401`. Wrong CSRF and foreign origin: `403`. Live/manual modes, noncatalog fictional wording, and an unexpected request field: `422`. |
| Reviewer controls | Queue read and fictional reviewer-login attempt: `403`, `review_disabled`. |
| Draft ownership | Second session could not confirm the first session's draft: `404`. |
| Replay receipt | Included fictional example could be captured, confirmed and assessed. Receipt was synthetic, `authored_replay`, and ephemeral before explicit save. |
| Saved-record ownership | After one consented fictional save, owning session listed one item and the second session listed none. Cross-session receipt read and check-in write returned `404`. |
| Test cleanup | Both sessions' own-data deletion returned `200` with `deleted: true`. |
| Video page | `200` HTML with the static-screenshot/synthetic-narration disclosure and captions link. |
| MP4 delivery | Request `Range: bytes=0-31` returned `206`, exactly 32 bytes, `video/mp4`, and `Content-Range: bytes 0-31/5088343`. |
| Captions | `200`, `text/vtt; charset=utf-8`, valid `WEBVTT` opening and timestamp cues. |
| Environment-file URLs | `/.env` and `/.env.ai` each returned `200` HTML byte-identical to the homepage SPA fallback, not environment-file content. |
| Encoded parent traversal | `/demo/%2e%2e/%2e%2e/.env.ai` returned a generic `400 Bad Request`, with no tested environment-key markers. The requested file was not exposed. |

The initial harness expected the local application's `404` for encoded traversal and therefore recorded a status-expectation failure. One isolated follow-up confirmed the deployed stack instead returns a generic `400` denial. The original result was preserved; no application test or implementation was weakened. The response does not identify which hosting layer rejected the path.

## Evidence and limits

Sanitized local machine-readable evidence is retained in ignored `.runtime/public-api-verification-20261014.json` and `.runtime/public-api-traversal-verification-20261014.json`. It contains no cookie values, CSRF tokens, record identifiers, API keys, or claim text.

This verifies a small public fictional-demo path and selected boundaries. It is not a load test, comprehensive penetration test, clinical validation, model qualification, proof of database-row deletion, or proof of restart durability. No provider telemetry was inspected; the no-model conclusion here is limited to disabled public-mode flags and refused live-mode requests. Full visual playback, browser consent/check-in interaction, and deployment billing verification are separate checks.
