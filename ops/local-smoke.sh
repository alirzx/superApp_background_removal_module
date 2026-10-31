#!/usr/bin/env bash
set -euo pipefail
API="${API:-http://127.0.0.1:8000}"
FILE="${1:?Usage: ops/local-smoke.sh /path/to/sample.png}"
TOKEN="${API_TOKEN:-}"
head_args=()
if [[ -n "${TOKEN}" ]]; then head_args=(-H "X-API-Key: ${TOKEN}"); fi
curl -fsS "${API}/health/ready"
echo
curl -fsS "${head_args[@]}" "${API}/v1/models"
echo
curl -fsS -X POST "${API}/v1/remove-background" "${head_args[@]}" -F "file=@${FILE}" -F "blur=0" -o /tmp/birefnet-removed.png
file /tmp/birefnet-removed.png
curl -fsS -X POST "${API}/v1/mask" "${head_args[@]}" -F "file=@${FILE}" -o /tmp/birefnet-mask.png
file /tmp/birefnet-mask.png
