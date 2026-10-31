# BiRefNet Lite Background Removal Service

Standalone CPU-only background removal for the AI Super App: two long-running Docker containers, **FastAPI + ONNX Runtime CPU** and **React + Nginx**. Supports RGBA transparent PNG, grayscale mask, Persian RTL UI, health/metrics, bounded concurrency, and explicit checksum-verified model download.

## Quick start

**Requirements:** Docker Engine with Compose v2, about 1 GB free disk for model cache plus images, sufficient CPU/RAM (start with 3 GB cap for API). Internet access required **only for initial model download and building dependency images**.

```bash
cp .env.example .env
# Optional: edit CPU limits, ports, and API_TOKEN.
make build
make model          # download ~224 MB ONNX from Hugging Face and SHA256-verify it
make model-verify   # works offline once cached
make up             # starts ONLY api and ui containers
make ps
make health
```

UI: `http://127.0.0.1:8080` • API: `http://127.0.0.1:8000` • API OpenAPI (dev): `http://127.0.0.1:8000/docs`

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
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8000/v1/models -H "X-API-Key: ${API_TOKEN:-}"
curl -fsS -X POST http://127.0.0.1:8000/v1/remove-background \
  -H "X-API-Key: ${API_TOKEN:-}" -F 'file=@photo.jpg' -F 'blur=0' \
  --output removed.png
curl -fsS -X POST http://127.0.0.1:8000/v1/mask \
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
- `.gitlab-ci.yml`: backend lint/test, UI build, optional Docker images.
- `docs/`: architecture, deployment, model provenance and limitations.

### Important notes

1. This ZIP contains **all source and deployment artifacts, but not ~224 MB pretrained weights**. Due to sandbox network limits, a live Hugging Face download and real ONNX inference could not be executed here. `make model` is designed for your network-enabled machine.
2. No code is downloaded or executed dynamically from Hugging Face during inference.
3. The UI is not itself a security boundary; protect it with authenticated HTTPS ingress before exposing to external users.
4. Quantization, 512px mode, caching inference outputs and async batch processing are **not enabled** until benchmarked for quality and security.
5. UI build uses `npm install` due unavailable package registry in the build sandbox. On your first network-enabled install, generate and commit `package-lock.json` and switch Docker/CI to `npm ci` for fully reproducible installs.
6. ONNX Runtime model signature and CPU compatibility must be confirmed during first E2E smoke test, and performance may exceed 10 seconds on some CPUs.

License: MIT for this repository's own source. Upstream model and ONNX artifact licenses are separate and must be reviewed before commercial release.

## Prebuild polish (2026-10-31)

The original Git push excluded hidden files. This update adds the Git/Docker ignore files, local/server environment templates and GitLab CI. The pinned ONNX revision is now the full immutable commit. The React UI no longer requests a remote Google Fonts CSS asset, and `make health` checks container-internal endpoints (independent of custom host ports). `make up` now starts prebuilt containers; always run `make build` first.

**Important:** the UI Nginx proxy adds the shared API token to all `/api` requests. It does **not** authenticate users. Never expose UI externally without authenticated HTTPS ingress and request rate limits. Consult [Persian prebuild checklist](docs/PREBUILD_CHECKLIST_FA.md), [security](docs/SECURITY.md), and [GitLab workflow](docs/RELEASE_AND_GITLAB.md). Live model inference and Docker builds must be validated on your CPU host.
