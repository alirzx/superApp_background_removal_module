# LAN/VPN access and server diagnostics

## Source of truth

The latest working Compose defines two services: `api` (FastAPI / ONNX Runtime CPU, container port **8000**) and `ui` (React built to static assets, Nginx container port **80**). The default host binds are `127.0.0.1:8001` (API) and `127.0.0.1:8082` (UI). The actual deployment uses GitLab's **File** variable `ENV_FILE` copied to the server's untracked `.env`. Values in that file override the Compose defaults.

The UI is not a Docker Image that must run on the developer's workstation. A workstation `docker ps` does **not** reveal the remote server's containers.

## Safely reach the UI from another machine

**Preferred:** keep `UI_BIND_IP=127.0.0.1` and configure the organization's authenticated HTTPS ingress, or ask an authorized DevOps operator to provide an SSH tunnel.

**Limited LAN/VPN test alternative:** after DevOps confirms the server's private address, subnet routing, capacity and permitted clients, set the following **inside GitLab's `ENV_FILE`**, not in Git or the CI configuration:

```dotenv
APP_ENV=production
API_BIND_IP=127.0.0.1
API_PORT=8001
UI_BIND_IP=192.168.4.209
UI_PORT=8082
```

The private UI address is illustrative, based on the previous SSH log. Verify the interface belongs to the intended server before using it. Maintain all other `.env` values, including the actual `API_TOKEN`. Do **not** set the API bind to a LAN IP. Restrict inbound TCP 8082 to approved VPN/client addresses using the host/network firewall and apply user authentication at the organization's ingress; simply being on a shared LAN is **not** authentication. The UI injects the API shared token, so an unauthenticated UI can be abused for CPU inference. Use HTTPS through an internal proxy whenever possible.

After DevOps enforces access restrictions and re-deploys the service with the approved `ENV_FILE`, an authorized VPN client can test `http://192.168.4.209:8082/healthz` and the UI root path. The protected API still listens only at loopback on the server; browser calls to `/api/v1/...` flow through Nginx over the Docker bridge.

## Why the UI might be absent

- `docker compose build` produces images; it does **not** start services.
- In GitLab, `RUN_SERVICES=1` requests `docker compose up -d --no-build --wait --wait-timeout 240 api ui`. The **job log** must show `Requested server startup: RUN_SERVICES=1`, `Runtime explicitly enabled`, and final service status.
- `ui.depends_on.api.condition=service_started` lets the static UI start without requiring ONNX warm-up. Nginx uses Docker's `127.0.0.11` resolver for runtime upstream lookup; a momentarily unavailable API causes an API-proxy error, not a failure to serve the static UI itself.
- A successful `/health/ready` HTTP 200 from the API proves readiness at that point, not that the UI is deployed.
- A host IP request to port 8082 cannot succeed if the UI binds to `127.0.0.1`, if the container is stopped, or if a VPN/firewall policy blocks the connection.

## How to obtain actionable diagnostics without personal SSH access

**Application endpoints (not Docker logs):**
- `GET http://<approved-ui-host>:8082/healthz` checks Nginx.
- `GET http://<approved-ui-host>:8082/api/health/live` checks FastAPI through the proxy.
- `GET http://<approved-ui-host>:8082/api/health/ready` reports model readiness.
- `GET http://<approved-ui-host>:8082/api/v1/models` reports model metadata via Nginx token injection. These endpoints cannot report container OOM kills or Docker startup errors.

**Operator-only container diagnostics:** an authorized DevOps teammate can run from the server checkout:

```bash
cd /opt/apps/ai-service/background-removal
bash ops/server-diagnostics.sh
VERIFY_MODEL=1 bash ops/server-diagnostics.sh
INCLUDE_LOGS=1 LOG_TAIL=80 bash ops/server-diagnostics.sh
```

The script reports Compose validity, both service names, all containers including *created/stopped*, and state/exit/OOM/health. Model verification is optional. Container logs are **omitted by default**; a teammate must review/redact them before sharing, especially if upstream images or proxy logs might include sensitive requests.

The existing GitLab deployment job also emits diagnostic logs when it fails. For self-service visibility on successful deployments, DevOps should provide access to an authenticated central logging system (e.g., Loki/Grafana), or a permission-scoped operator workflow. There is no safe way to expose arbitrary Docker container logs directly from the FastAPI app without privileged daemon access. **Do not mount `docker.sock` into the API or publish raw logs on an unprotected endpoint.**

## Acceptance checks

1. Server images built, model SHA256 verified, `RUN_SERVICES=1` appears in actual GitLab job output.
2. Both `api` and `ui` containers appear in the server's `docker compose ps -a`; Nginx `/healthz` responds.
3. `/api/health/ready` responds with 200 when the model is loaded; OOMKilled remains false.
4. The server has sufficient RAM (the `API_MEMORY=8g` template is not benchmarked).
5. The VPN route and firewall allow only approved clients to reach the UI; user authentication and TLS are enforced where required.
6. A real, non-sensitive test image returns an RGBA PNG or grayscale mask. The previous successful Docker builds and model download do **not** establish real inference success.

## Nginx capability error fixed (2026-11-03)

The GitLab `74b9955` pipeline proved the API was **healthy** and both Docker images built, but the UI crash-looped with `nginx: [emerg] chown("/var/cache/nginx/client_temp", 101) failed (1: Operation not permitted)`. Root cause: the UI Compose service used `cap_drop: [ALL]` but re-added only `NET_BIND_SERVICE`. The official `nginx:1.27-alpine` image also requires `CHOWN` for its temporary cache and `SETUID`/`SETGID` to switch its worker processes to the nginx user. Compose now restores only these four capabilities; `read_only`, `no-new-privileges`, tmpfs caps and resource limits remain intact. CI and Dockerfiles are unchanged.

On the next deployment the UI must pass its built-in `/healthz` check. If the UI does not become healthy, inspect logs for another distinct Nginx configuration or permissions error. Do not grant `privileged: true` or remove `cap_drop: ALL` to bypass errors. Network exposure requires the separate ingress/VPN authorization described above.
