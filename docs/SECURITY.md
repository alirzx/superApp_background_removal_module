# Security model

## Data and network

- Input image bytes are read into memory, decoded with Pillow, and discarded after request handling. No generated images are persisted by this application.
- The backend runtime loads a **local** ONNX file and never calls Hugging Face or executes Python custom model code as part of a request.
- Images may still appear in upstream gateway access logs if that gateway is misconfigured; never log request bodies or query parameters containing secrets.
- The UI is unprotected by itself. Public deployments **must** add TLS, access control and a request rate limiter at ingress; otherwise any public visitor can spend server CPU through the UI proxy.
- Direct API port binds to `127.0.0.1` by default; the UI port also binds to loopback unless deliberately changed.

## Authentication

- The API accepts `X-API-Key` only when configured with `API_TOKEN`.
- `APP_ENV=production` rejects tokens shorter than 24 characters or missing tokens.
- The UI Nginx proxy injects the secret in the upstream request. The React bundle does not contain the token.
- Do not give `.env` to users or store it in Git; use a secret manager in production.

## Abuse prevention

- Check allowed MIME and actual decoded image type; prevent truncated and very large decompressed images.
- Limit upload size, decoded pixel count, simultaneous ONNX inference jobs and backlog queue time.
- Cap the container's CPU, memory and PID count; run API as an unprivileged user, read-only filesystem, and drop Linux capabilities.
- Keep dependencies patched, run image vulnerability scanning, and monitor recent upstream model vulnerabilities.

## Known boundaries

- This is not an authenticated multi-tenant SaaS gateway. Ingress authentication and per-user quotas are intentionally left to the deployment platform.
- No per-user billing, long-term file storage, async job queue or resumable upload is implemented.
- P95 latency cannot be promised without hardware-specific CPU testing.

## Shared-token UI proxy boundary

The UI Nginx proxy inserts `X-API-Key` for every `/api` request. This protects the secret from JavaScript but is **not** per-user authentication. Any unauthenticated visitor who can access the public UI can consume inference CPU through its proxy. Keep default bindings on loopback and configure authenticated TLS ingress with rate limiting for any remote deployment.

## Build context boundary

Root `.dockerignore` excludes `.env`, secrets, generated weights, caches and Git metadata from BOTH image build contexts. A Git ignore file alone does not protect Docker build contexts. Ignoring accidentally committed secrets will not erase history: rotate credentials and repair history separately.
