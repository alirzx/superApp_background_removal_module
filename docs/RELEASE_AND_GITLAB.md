# GitLab CI: Background Removal release preparation

## Confirmed initial failure and correction

The first GitLab Shell Runner deployment successfully transferred the environment and built both API/UI Docker images. It then created a fresh `birefnet-lite_model_cache` volume, attempted to start API, and failed the API health dependency. The original CI did not download the ONNX file; missing weights are the leading hypothesis, but the old logs do not prove it was the only cause.

The revised CI **preserves the original DevOps runner tags and SSH variable contract** while adding model acquisition, checksum verification and error diagnostics:

1. GitLab `master` runs a single `deploy` job on Runner tags `linux`, `bina`, `shell`.
2. SSH to the existing checkout at `/opt/apps/ai-service/background-removal`; copy the server `.env` from GitLab's `ENV_FILE` File variable.
3. `git fetch`/`merge --ff-only`, `docker compose config --quiet`, then `docker compose build api ui`.
4. `docker compose run --rm --no-deps --entrypoint python api -m scripts.download_model`: acquire immutable ONNX weights, or reuse a verified cached file. Repeat with `--verify-only`.
5. Default `RUN_SERVICES=0`: report **BUILD_AND_MODEL_READY**; do not attempt a new API/UI start. Previously unhealthy/restarting containers of this module are stopped to avoid loops.
6. Explicit GitLab CI variable `RUN_SERVICES=1`: `docker compose up -d --no-build --wait --wait-timeout 240 api ui`; if startup fails, output logs, OOMKilled flag, health and exit codes.

## GitLab CI/CD variables

| Variable | Type | Purpose |
|---|---|---|
| `SSH_PRIVATE_KEY` | Existing text Variable or File | SSH private key, both forms accepted |
| `SSH_USER` | Variable | Deployment SSH login |
| `SSH_PORT` | Variable | SSH port |
| `VM_IPADDRESS` | Variable | Server destination |
| `ENV_FILE` | **File** | Production `.env` contents, including the API token |
| `SSH_KNOWN_HOSTS` | Optional **File** | Verified SSH host key; preferred to `ssh-keyscan` fallback |
| `RUN_SERVICES` | Optional Variable | `0` (safe default) / `1` (start and health-check) |

The job does not use a compulsory `SSH_KNOWN_HOSTS` variable (which broke the previous integrated CI). Never print or commit production secrets.

## Model and runtime

Model: `onnx-community/BiRefNet_lite-ONNX`, revision `de15b22ba131738a16dff04aab8bdf8dc32e3ac1`; SHA256 `5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333`. Persistent volume: `birefnet-lite_model_cache`. The first server download requires Hugging Face access; regional PyPI mirrors cover dependencies only.

Current host defaults: API `127.0.0.1:8001`, UI `127.0.0.1:8082`. Internal API and Nginx ports remain `8000`/`80`.

The Ubuntu workstation failed ONNX initialization under 3g/4g/5g container memory caps. The production template's 8g memory limit is an **unverified candidate**, not a guarantee; first validate server RAM. The corrected CI can confirm model availability without claiming real-image inference success.

## Remaining release gates

Current CI does not separately execute Python pytest/Ruff or React tests, does not publish immutable versioned registry images, and cannot benchmark real inference when `RUN_SERVICES=0`. Authenticate HTTPS ingress and monitor RAM/latency before production promotion. `frontend/package-lock.json` is not yet committed; `npm install` remains in the Dockerfile, not fully reproducible.
