# BiRefNet Lite Background Removal Service

Standalone CPU-only background removal for the AI Super App: two long-running Docker containers, **FastAPI + ONNX Runtime CPU** and **React + Nginx**. Supports RGBA transparent PNG, grayscale mask, Persian RTL UI, health/metrics, bounded concurrency, and explicit checksum-verified model download.

## Current deployment state (2026-11-02)

`personal/main` and the organization GitLab `origin/master` synchronized through `0252972` before this documentation update. Local API/UI Docker builds and ONNX checksum verification succeeded. The real ONNX session/warm-up caused container OOM (exit 137) under 3g/4g/5g memory limits; UI cannot become healthy until API is healthy. **No production performance or readiness claim is made.** The GitLab shell-runner CI validates source layout and offers a manual SSH Docker image build, defaulting to `RUN_SERVICES=0`. A new server-side RAM benchmark is required before enabling runtime startup.

## Quick start

**Requirements:** Docker Engine with Compose v2, about 1 GB free disk for model cache plus images, sufficient CPU/RAM (**3 GB, 4 GB and 5 GB API limits all failed warm-up on the local workstation**). Internet access required **only for initial model download and building dependency images**.

```bash
cp .env.example .env
# Optional: edit CPU limits, ports, and API_TOKEN.
make build
make model          # download ~224 MB ONNX from Hugging Face and SHA256-verify it
make model-verify   # works offline once cached
make up             # ONLY on a machine with benchmarked memory headroom: starts api and ui
make ps
make health
```

UI: `http://127.0.0.1:8082` • API: `http://127.0.0.1:8001` • API OpenAPI (dev): `http://127.0.0.1:8001/docs`

If production, set `APP_ENV=production` and a long random `API_TOKEN` before startup. UI proxy uses token server-side. Public deployment **requires** HTTPS ingress, identity/rate controls, and appropriate firewalling.

### Architecture

```text
 React browser → nginx UI (container 2) → /api/ proxy with server-side API key
                                          ↓
                       FastAPI service (container 1)
                                          ↓
                   load-once, warmed ONNX Runtime CPU session
                                          ↓
                         ImageNet preproc → 1024×1024 inference
                                          ↓
                         sigmoid alpha → resize → composite PNG
                                          ↑
                       persistent named Docker volume: model_cache
```

### Download pipeline

`make model` uses a temporary `docker compose run --rm api ...` invocation, **not** a third background service. `huggingface_hub.hf_hub_download` places the model into `/models/.hf-hub` (HF cache), verifies pinned SHA256, copies atomically into `/models/birefnet_lite_fp32.onnx`; subsequent invocations reuse the existing verified file. At API startup, the model must already be present. No runtime network access is needed.

Source model is `ZhengPeng7/BiRefNet_lite`; the deployable ONNX file is published separately by `onnx-community/BiRefNet_lite-ONNX` (MIT per card). See [Model provenance](docs/MODEL_PROVENANCE.md) for caveats and the exact weight digest.

### API examples

```bash
curl -fsS http://127.0.0.1:8001/health/ready
curl -fsS http://127.0.0.1:8001/v1/models -H "X-API-Key: ${API_TOKEN:-}"
curl -fsS -X POST http://127.0.0.1:8001/v1/remove-background \
  -H "X-API-Key: ${API_TOKEN:-}" -F 'file=@photo.jpg' -F 'blur=0' \
  --output removed.png
curl -fsS -X POST http://127.0.0.1:8001/v1/mask \
  -H "X-API-Key: ${API_TOKEN:-}" -F 'file=@photo.jpg' \
  --output mask.png
```

### Local tests

```bash
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend pytest backend/tests -q
cd frontend && npm install && npm run build
```

Tests mock ONNX inference; they validate API contract and processing without downloading weights. Real model E2E tests and CPU latency require a host with Internet and ONNX Runtime. See [Deployment checklist](docs/DEPLOYMENT.md).

### File layout

- `backend/app/`: API, model loading, inference and image processing.
- `backend/scripts/download_model.py`: acquisition, cache, checksum and atomic install.
- `backend/scripts/benchmark.py`: CPU latency benchmark driver.
- `backend/tests/`: API, auth, image processing tests with a fake engine.
- `frontend/src/`: React UI (Persian RTL, drag-and-drop, previews, mask, PNG download).
- `ops/nginx.conf.template`: static serving and reverse proxy; no browser API secret.
- `.gitlab-ci.yml`: source-layout validation and manual SSH server build; service startup requires RUN_SERVICES=1.
- `docs/`: architecture, deployment, model provenance and limitations.

### Important notes

1. The Git repository contains source/deployment files, **not the ~224 MB pretrained weights**. Model download and SHA256 verification succeeded on the Ubuntu workstation; real ONNX startup failed with cgroup OOM under 3g, 4g and 5g limits. UI end-to-end inference remains unverified and must be tested on a higher-memory server.
2. No code is downloaded or executed dynamically from Hugging Face during inference.
3. The UI is not itself a security boundary; protect it with authenticated HTTPS ingress before exposing to external users.
4. Quantization, 512px mode, caching inference outputs and async batch processing are **not enabled** until benchmarked for quality and security.
5. UI build uses `npm install` due unavailable package registry in the build sandbox. On your first network-enabled install, generate and commit `package-lock.json` and switch Docker/CI to `npm ci` for fully reproducible installs.
6. ONNX Runtime model signature and CPU compatibility must be confirmed during first E2E smoke test, and performance may exceed 10 seconds on some CPUs.

License: MIT for this repository's own source. Upstream model and ONNX artifact licenses are separate and must be reviewed before commercial release.

## Prebuild polish (2026-10-31)

The original Git push excluded hidden files. This update adds the Git/Docker ignore files, local/server environment templates and GitLab CI. The pinned ONNX revision is now the full immutable commit. The React UI no longer requests a remote Google Fonts CSS asset, and `make health` checks container-internal endpoints (independent of custom host ports). `make up` now starts prebuilt containers; always run `make build` first.

**Important:** the UI Nginx proxy adds the shared API token to all `/api` requests. It does **not** authenticate users. Never expose UI externally without authenticated HTTPS ingress and request rate limits. Consult [Persian prebuild checklist](docs/PREBUILD_CHECKLIST_FA.md), [security](docs/SECURITY.md), and [GitLab workflow](docs/RELEASE_AND_GITLAB.md). Live model inference and Docker builds must be validated on your CPU host.

## Regional Python package mirrors (default)

The **API Docker build** first installs Python dependencies using the Liara PyPI mirror (`https://package-mirror.liara.ir/repository/pypi/simple`) and automatically retries once using Chabokan (`https://mirror2.chabokan.net/pypi/simple/`) if the first installation fails. Mirror URLs can be overridden per project using `PIP_PRIMARY_INDEX_URL` / `PIP_FALLBACK_INDEX_URL` in an untracked `.env` or Docker Compose build arguments. BuildKit's pip cache is preserved. No host-level pip configuration, Docker daemon settings, shared images or other containers are changed. This does **not** mirror Hugging Face model weights or Docker Hub base images. Sources: https://docs.liara.ir/mirrors/pypi/ and https://iran.chabokan.net/.

The current Compose host defaults are **API_PORT=8001** and **UI_PORT=8082** (DevOps update `0252972`); internal API/Nginx ports remain `8000`/`80`. Existing untracked `.env` values take precedence over Compose defaults, so update local and GitLab `ENV_FILE` configurations explicitly. The server deploy CI is manual and defaults to `RUN_SERVICES=0` while OOM remains unresolved. See `docs/NETWORK_BUILD_TROUBLESHOOT_FA.md`.
