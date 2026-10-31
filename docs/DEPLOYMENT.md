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

Visit `http://127.0.0.1:8080`. API at `http://127.0.0.1:8000` (loopback by default). Choose a local image to exercise both outputs. For remote server access, reverse-proxy to TLS ingress, or use SSH port forwarding; never directly expose unprotected loopback ports.

The `model_cache` volume survives `docker compose down`, code updates, and image rebuilds; `docker compose down -v` **deletes weights and the HF cache**.

## Deployment on GitLab server

1. Set up GitLab Runner and immutable image tags; protect registry credentials in GitLab CI variables.
2. Build/publish api + ui images, then pin images by digest in server Compose.
3. Deploy `.env` out of repository using secrets management and rotate API token.
4. Download model once on an attached persistent volume using the pinned revision/hash; no model download at API startup.
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

Start with `CPU_THREADS=2`, one worker, `MAX_CONCURRENT_INFERENCE=1`, 3 GB API memory limit. These are **defaults to benchmark**, not a performance claim. Increase concurrency only if latency SLO improves under real hardware and concurrent memory stays acceptable. Monitor frequency throttling and CPU contention from other modules.

## CLI benchmark

```bash
cd backend
python -m scripts.benchmark --file ../example.png --requests 30 --concurrency 2
```

A container is also available: `docker compose exec api python -m scripts.benchmark --url http://127.0.0.1:8000/v1/remove-background --file /path/in/container` (mount a test image intentionally rather than storing real customer data).
