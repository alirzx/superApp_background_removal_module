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

## Current local OOM finding

Model weights (~224MB on disk) were downloaded and checksum-verified, but ONNX Runtime loads intermediate tensors at fixed 1024×1024 resolution. During initial session creation / warm-up, the local API container was OOM-killed at memory limits of 3g, 4g and 5g. The UI depends on `api: healthy` and could not run. Avoid repeated local startup on the 14-GiB workstation with full swap. This does not mean the Docker images or ONNX file are corrupt.

## Deployment on GitLab server

1. Existing CI uses the shell runner tagged `linux`, `bina`, `shell`, and a **manual** `deploy` job on GitLab `master`.
2. Set `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS`, and `ENV_FILE` as **File** CI/CD variables; set `SSH_USER`, `SSH_PORT`, and `VM_IPADDRESS` as standard variables. The `ENV_FILE` value is the complete production `.env` contents, not a pathname.
3. The job transfers `.env` to `/opt/apps/ai-service/background-removal/.env`, fast-forwards checked-out `master`, and runs `docker compose config --quiet` followed by `docker compose build api ui`.
4. `RUN_SERVICES=0` is the default. The manual job **does not download the model or start containers**. Before authorizing startup, download the ONNX once with `docker compose run --rm --no-deps --entrypoint python api -m scripts.download_model`, verify its SHA256 in the persistent volume, and confirm actual server RAM capacity.
5. Block direct Internet access to API where possible. Limit UI ingress to HTTPS, proper ACL/auth at gateway, and prevent unauthorized image uploads.
6. Turn on central metrics/logging; **do not log image contents or model secrets**.
7. Ensure server cores, memory and thread counts are reserved so other CPU modules stay responsive.

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
