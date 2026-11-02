# Deployment, ops and acceptance checklist

## First time

```bash
cp .env.example .env
# Set API_TOKEN (>=24 characters for production) and other values.
docker compose build
make model                   # one-shot downloader: no extra long-lived service
make model-verify
make up
make ps
make health
```

Visit `http://127.0.0.1:8082`. API at `http://127.0.0.1:8001` (loopback by default). Choose a local image to exercise both outputs. For remote server access, reverse-proxy to TLS ingress, or use SSH port forwarding; never directly expose unprotected loopback ports.

The `model_cache` volume survives `docker compose down`, code updates, and image rebuilds; `docker compose down -v` **deletes weights and the HF cache**.

**Frontend startup policy:** the UI now waits for the API container to be **started**, not **healthy**. The Nginx reverse proxy still targets `api:8000` on Docker's internal network. The React UI can display the backend readiness state while BiRefNet initializes; a healthy API is still required for successful image processing and for the `RUN_SERVICES=1` CI deployment gate. This change does **not** override `RUN_SERVICES=0`, launch containers by itself, or expose the UI to the LAN.

**Diagnose missing UI (DevOps on server):** run `docker compose ps -a`, `docker compose logs --tail=100 ui`, `docker inspect birefnet-lite-ui-1 --format '{{.State.Status}} {{.State.ExitCode}}'`, and `docker compose config --services`. To confirm CI really started containers, its log must include `Requested server startup: RUN_SERVICES=1`, `=== Runtime explicitly enabled`, and the final Compose status.


## Current local OOM finding

Model weights (~224MB on disk) were downloaded and checksum-verified, but ONNX Runtime loads intermediate tensors at fixed 1024×1024 resolution. During initial session creation / warm-up, the local API container was OOM-killed at memory limits of 3g, 4g and 5g. The UI depends on `api: healthy` and could not run. Avoid repeated local startup on the 14-GiB workstation with full swap. This does not mean the Docker images or ONNX file are corrupt.

## Deployment on GitLab server

1. GitLab `master` triggers the single SSH `deploy` job on the organizational shell runner tagged `linux`, `bina` and `shell`.
2. Set `SSH_PRIVATE_KEY` (existing plain-text or File), `SSH_USER`, `SSH_PORT`, `VM_IPADDRESS` and `ENV_FILE` (**File** containing the production `.env`). Optional verified `SSH_KNOWN_HOSTS` (File) avoids the original `ssh-keyscan` trust-on-first-use fallback.
3. The job transfers the production `.env` to `/opt/apps/ai-service/background-removal/.env`, fast-forwards the server's GitLab checkout, checks Compose, builds `api` and `ui`, downloads the pinned ONNX model into the persistent Docker volume, and verifies SHA256. Missing Hugging Face connectivity or a checksum mismatch will fail the job **before a new runtime start**.
4. The default GitLab variable `RUN_SERVICES=0` performs build/model preparation only. With an approved server memory budget, set `RUN_SERVICES=1` as a **GitLab CI/CD variable** to attempt startup and verify health. It is not a Compose `.env` variable.
5. On failure, CI emits `docker compose ps -a`, recent API/UI logs, and container exit/OOM/health status. It will stop only this module's previously unhealthy/restarting containers when preparing in `RUN_SERVICES=0` mode.
6. Server RAM and actual inference remain unverified: an `API_MEMORY=8g` trial value is not a measured minimum. Provide authenticated HTTPS ingress, rate limiting and resource monitoring before production exposure.

## Release acceptance

- [ ] Verify ONNX SHA256 and Hub revision.
- [ ] Confirm model/converted weights license and legal-use conditions.
- [ ] Startup completes with CPUExecutionProvider exclusively.
- [ ] API handles JPEG/PNG/WEBP, EXIF rotation, alpha compositing, corrupted files, oversized bytes, decompression bombs.
- [ ] Compare outputs against official PyTorch for same images; evaluate silhouettes, hair, glass, transparency.
- [ ] Run at least 30 warm requests each on small, typical, and complex high-resolution photos, with 1, 2, 4 concurrent clients.
- [ ] Measure p50/p95 end-to-end latency, isolated ONNX inference ms, RSS memory, resident cache size, load time.
- [ ] Validate CPU saturation, 503 under heavy load, client behavior and memory recovery.
- [ ] Threat-test API key, unsafe MIME, large multipart, malicious images, and resource exhaustion.
- [ ] Keep image data out of persisted logs; set retention policies for reverse proxies.
- [ ] Configure monitored alerts and rollback deployment plan.

## CPU memory and throughput

One Uvicorn worker, `CPU_THREADS=2`, and `MAX_CONCURRENT_INFERENCE=1` are current baseline settings. The original 3g memory limit **failed** on the Ubuntu workstation, as did 4g and 5g. An 8g *server test profile* in `.env.production.example` is provisional and NOT a validated sufficient minimum. Do not enable `RUN_SERVICES=1` until server memory headroom and model warm-up have been measured. Increase concurrency only if latency SLO improves under real hardware and concurrent memory stays acceptable. Monitor frequency throttling and CPU contention from other modules.

## CLI benchmark

```bash
cd backend
python -m scripts.benchmark --file ../example.png --requests 30 --concurrency 2
```

A container is also available: `docker compose exec api python -m scripts.benchmark --url http://127.0.0.1:8000/v1/remove-background --file /path/in/container` (mount a test image intentionally rather than storing real customer data).

## DNS / build troubleshooting

Before clearing anything, see [راهنمای فارسی رفع خطای Docker Build و DNS](NETWORK_BUILD_TROUBLESHOOT_FA.md). Project-scoped remediation retains all other Docker workloads and preserves build caches and model weights.

## Default regional PyPI mirrors

API image builds use Liara as the primary mirror (`https://package-mirror.liara.ir/repository/pypi/simple`) and retry with Chabokan (`https://mirror2.chabokan.net/pypi/simple/`) on installation failure. This is configured by the two `PIP_*_INDEX_URL` Docker build arguments; they are not needed at runtime. These mirrors do not cover Hugging Face model downloads. The current host port defaults are API 8001 and UI 8082; internal container ports remain 8000 and 80. Existing `.env` overrides must be updated explicitly.
