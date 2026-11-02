# GitLab CI, server build and release gates

## Current workflow (verified against `.gitlab-ci.yml`, 2026-11-02)

- GitHub personal branch: `main`. Organization GitLab branch: `master`.
- Shell Runner tags: `linux`, `bina`, `shell`.
- `validate-source` checks required repository files; **it does not run Ruff, pytest, frontend tests or Docker builds**.
- `deploy` is a **manual** GitLab `master` job. It uses SSH to update the pre-existing checkout at `/opt/apps/ai-service/background-removal`, copies the production environment file, and builds both images with `docker compose build api ui`.
- CI default `RUN_SERVICES=0` means **build only**. With `RUN_SERVICES=1`, the job verifies an already downloaded model and attempts `docker compose up -d --no-build --wait --wait-timeout 240 api ui`. It does **not** download model weights or publish container images to a registry.

## Required GitLab CI/CD variables

| Key | Type | Usage |
|---|---|---|
| `SSH_PRIVATE_KEY` | File | SSH private key for deployment user |
| `SSH_KNOWN_HOSTS` | File | Trusted server host key(s); provision from a verified channel |
| `ENV_FILE` | File | Complete contents of the server production `.env`, including `API_TOKEN` |
| `SSH_USER` | Variable | Server SSH user |
| `SSH_PORT` | Variable | Server SSH port |
| `VM_IPADDRESS` | Variable | Server address |
| `DEPLOY_DIR` | Variable (optional) | Defaults to `/opt/apps/ai-service/background-removal` |
| `RUN_SERVICES` | Variable (optional) | Defaults to `0`; do not set `1` until memory and model checks pass |

For protected branches, follow the organization's protected variable rules. Never commit real credentials, `.env` files, private SSH keys or `ENV_FILE` contents.

## Port and environment contract

- Current Docker Compose host defaults: `API_PORT=8001`, `UI_PORT=8082`; both bound to `127.0.0.1`.
- Container ports remain API `8000` and Nginx `80`. Nginx proxy still targets `http://api:8000/`.
- If the server's ingress is on another host, the DevOps team must design a restricted bind/firewall or private network route; do not expose an unauthenticated UI publicly.
- Existing local `.env` and server `ENV_FILE` override Compose defaults. Keep templates synchronized with the DevOps ports.
- The production API needs `APP_ENV=production` and a strong `API_TOKEN` (at least 24 characters).

## Model and memory gate

The pinned `onnx-community/BiRefNet_lite-ONNX` FP32 weight file was successfully downloaded and SHA256-verified on the Ubuntu workstation; it is **not present in Git** and the GitLab deploy job does not fetch it. Local real inference startup was OOM-killed with API memory limits of **3g, 4g and 5g**, including a temporary low-memory ONNX Runtime experiment. The app has **not passed real-image end-to-end tests**.

The suggested `API_MEMORY=8g` in `.env.production.example` is only an **unverified server-test candidate**, conditional on adequate free memory and reservations for other services. Do not treat it as the measured requirement. After the server images build, download and verify the model separately, monitor cgroup peak memory, then perform an explicitly authorized startup and UI/API smoke test.

## Reproducible frontend dependencies

`frontend/package-lock.json` is not yet committed. The current frontend Dockerfile uses `npm install`, so transitive dependencies are not fully locked. On a networked development machine:

```bash
cd frontend
npm install --package-lock-only
npm ci
npm run build
```

Commit and test the lockfile before changing the Dockerfile to `npm ci`. Do not claim reproducible builds before this is verified.

## Future release improvements

Restore Ruff, mocked Backend pytest, and React/Vite build checks to CI; scan and version image artifacts; add rollback and runtime resource measurements; ensure authenticated HTTPS ingress, rate limiting, monitoring and appropriate firewalling. The current manual SSH build is an acceptance-test preparation workflow, not a production release gate.
