# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HUB_CACHE=/models/.hf-hub OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /srv
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app
COPY backend/requirements.txt /srv/requirements.txt
# Persistent BuildKit pip cache. A failed DNS lookup still requires network repair.
# Keep package wheels between retried builds; do not use --no-cache-dir.
RUN --mount=type=cache,id=superapp-bgremoval-pip-py311,target=/root/.cache/pip,sharing=locked \
    python -m pip install --disable-pip-version-check --timeout 15 --retries 2 -r /srv/requirements.txt
COPY backend/app /srv/app
COPY backend/scripts /srv/scripts
RUN mkdir -p /models && chown -R app:app /models /srv
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
