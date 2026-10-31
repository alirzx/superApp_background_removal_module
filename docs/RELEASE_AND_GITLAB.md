# GitLab CI, server deployment and release gates

GitLab CI includes Python lint, mocked API/inference tests, React TypeScript/Vite build, and an optional manually triggered Docker build for privileged Docker-in-Docker runners. It does not download model weights, publish images, or deploy servers.

## Reproducible frontend dependencies
The initial repository does **not yet** contain `frontend/package-lock.json`. `npm install` is used during the first build, so dependency transitive versions are not fully locked. On a networked development machine:
```bash
cd frontend
npm install --package-lock-only
npm ci
npm run build
```
Commit the generated `package-lock.json`, then switch the frontend Dockerfile and GitLab CI to `npm ci`. Do not claim reproducible builds before this change is tested.

## Protected server release
- Configure GitLab runners, private Container Registry and protected credentials.
- Build and scan `api` and `ui` images, pin release tags/digests, retain rollback tags.
- Provision `.env` outside the repository. Use a high-entropy API token.
- Download weights into a persistent Volume with SHA256 verification, no downloads during inference.
- Limit CPU/RAM and request concurrency; monitor p95, RSS, 5xx and timeouts.
- Require authenticated TLS ingress for the UI: shared proxy API token is **not** user authentication.
- Validate real ONNX CPU inference and output quality before claiming production-ready.
