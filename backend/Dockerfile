# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HUB_CACHE=/models/.hf-hub OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /srv
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app
COPY backend/requirements.txt /srv/requirements.txt
# Public regional mirrors, scoped to this image build (not system-wide pip config).
# Sequential fallback is deliberate: --extra-index-url is NOT a failover mechanism.
ARG PIP_PRIMARY_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
ARG PIP_FALLBACK_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/
# The BuildKit cache keeps successful wheel downloads across build retries.
# pip's --index-url explicitly overrides any inherited index configuration.
RUN --mount=type=cache,id=superapp-bgremoval-pip-py311,target=/root/.cache/pip,sharing=locked \
    set -eu; \
    echo "Installing Python dependencies from primary PyPI mirror (Liara by default)"; \
    if ! python -m pip install --disable-pip-version-check --timeout 15 --retries 2 \
        --index-url "$PIP_PRIMARY_INDEX_URL" -r /srv/requirements.txt; then \
      echo "Primary mirror unavailable; retrying against fallback PyPI mirror (Chabokan by default)"; \
      python -m pip install --disable-pip-version-check --timeout 15 --retries 2 \
        --index-url "$PIP_FALLBACK_INDEX_URL" -r /srv/requirements.txt; \
    fi
COPY backend/app /srv/app
COPY backend/scripts /srv/scripts
RUN mkdir -p /models && chown -R app:app /models /srv
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
