#!/usr/bin/env bash
# Operator-only server diagnostics. Do not expose Docker logs over HTTP.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo '=== Compose syntax ==='
docker compose config --quiet
echo '=== Defined services ==='
docker compose config --services
echo '=== Containers ==='
docker compose ps -a
for service in api ui; do
  cid="$(docker compose ps -a -q "$service")"
  if [ -n "$cid" ]; then
    docker inspect --format 'service='"$service"' container={{.Name}} state={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid"
  else
    echo "service=$service container=absent"
  fi
done
if [ "${VERIFY_MODEL:-0}" = '1' ]; then
  echo '=== Model checksum verification (one-shot container) ==='
  docker compose run -T --rm --no-deps --entrypoint python api -m scripts.download_model --verify-only </dev/null
fi
if [ "${INCLUDE_LOGS:-0}" = '1' ]; then
  count="${LOG_TAIL:-80}"
  case "$count" in *[!0-9]*|'') echo 'LOG_TAIL must be numeric' >&2; exit 2 ;; esac
  echo '=== Logs (review/redact before sharing) ==='
  docker compose logs --no-color --tail="$count" api ui
else
  echo 'Container logs omitted. Run INCLUDE_LOGS=1 only for operator-reviewed logs.'
fi
