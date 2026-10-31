"""Standalone FastAPI service with CPU admission control and safe image uploads."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hmac
import logging
from time import perf_counter
from typing import Callable

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.concurrency import run_in_threadpool
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .config import Settings
from .image_pipeline import InvalidImage, decode_image
from .inference import ONNXInferenceEngine

logger = logging.getLogger("birefnet_lite")
REQUESTS = Counter("birefnet_requests_total", "Image processing requests", ["route", "status"])
DURATION = Histogram("birefnet_request_duration_seconds", "Total image processing duration", ["route"])
INFERENCE = Histogram("birefnet_inference_seconds", "ONNX CPU inference duration", ["route"])


def create_app(*, settings: Settings | None = None, engine_factory: Callable | None = None) -> FastAPI:
    config = settings if settings is not None else Settings.from_env()
    config.validate()
    factory = engine_factory or ONNXInferenceEngine

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = await run_in_threadpool(factory, config)
        await run_in_threadpool(app.state.engine.warmup)
        app.state.semaphore = asyncio.Semaphore(config.max_concurrent_inference)
        yield
        app.state.engine = None

    app = FastAPI(title="BiRefNet Lite Background Removal", version="0.1.0", docs_url="/docs" if config.environment != "production" else None, redoc_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def security_headers(request, call_next):
        # Early bound for declared multipart bodies. Chunked uploads must also
        # be bounded at authenticated ingress; UploadFile reads cap file bytes.
        if request.method == "POST" and request.url.path.startswith("/v1/"):
            value = request.headers.get("content-length")
            if value is not None:
                try:
                    declared = int(value)
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
                if declared > config.max_upload_mb * 1024 * 1024 + 1024 * 1024:
                    return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    def authorize(x_api_key: str | None = Header(default=None)) -> None:
        if config.api_token and not hmac.compare_digest(x_api_key or "", config.api_token):
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.get("/health/live", tags=["health"])
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def ready():
        engine = getattr(app.state, "engine", None)
        if engine is None or not getattr(engine, "warmed_up", False):
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready", "model": "BiRefNet_lite", "backend": "onnxruntime-cpu"}

    @app.get("/v1/models", dependencies=[Depends(authorize)], tags=["models"])
    async def models():
        engine = getattr(app.state, "engine", None)
        return {"model": "ZhengPeng7/BiRefNet_lite", "onnx_repo": config.model_repo,
                "revision": config.model_revision, "runtime": "CPUExecutionProvider",
                "input_size": list(getattr(engine, "size", (1024, 1024))),
                "max_upload_mb": config.max_upload_mb}

    @app.get("/metrics", tags=["health"])
    async def metrics(_: None = Depends(authorize)):
        if not config.enable_metrics:
            raise HTTPException(status_code=404)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    async def handle(file: UploadFile, blur: float, *, mask_only: bool, route: str) -> Response:
        started = perf_counter()
        if not 0 <= blur <= 8:
            raise HTTPException(status_code=422, detail="blur must be between 0 and 8")
        if file.content_type not in {"image/png", "image/jpeg", "image/webp", "application/octet-stream"}:
            raise HTTPException(status_code=415, detail="Unsupported content type")
        data = await file.read(config.max_upload_mb * 1024 * 1024 + 1)
        await file.close()
        if len(data) > config.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image upload too large")
        try:
            image = await run_in_threadpool(decode_image, data, max_pixels=config.max_image_pixels)
        except InvalidImage as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        semaphore = app.state.semaphore
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=config.max_queue_wait_seconds)
        except asyncio.TimeoutError as exc:
            REQUESTS.labels(route, "busy").inc()
            raise HTTPException(status_code=503, detail="Inference queue is full", headers={"Retry-After": "3"}) from exc
        try:
            output, inference_ms = await run_in_threadpool(app.state.engine.process, image, mask_only=mask_only, blur=blur)
        except Exception:
            REQUESTS.labels(route, "failed").inc()
            logger.exception("Model inference failed")
            raise HTTPException(status_code=500, detail="Inference failed")
        finally:
            semaphore.release()
        REQUESTS.labels(route, "ok").inc()
        DURATION.labels(route).observe(perf_counter() - started)
        INFERENCE.labels(route).observe(inference_ms / 1000)
        return Response(content=output, media_type="image/png", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "X-Model-Id": "ZhengPeng7/BiRefNet_lite", "X-Inference-Ms": f"{inference_ms:.1f}",
        })

    @app.post("/v1/remove-background", dependencies=[Depends(authorize)], tags=["inference"])
    async def remove_background(file: UploadFile = File(...), blur: float = Form(default=0.0)):
        return await handle(file, blur, mask_only=False, route="remove-background")

    @app.post("/v1/mask", dependencies=[Depends(authorize)], tags=["inference"])
    async def make_mask(file: UploadFile = File(...), blur: float = Form(default=0.0)):
        return await handle(file, blur, mask_only=True, route="mask")

    return app


app = create_app()
