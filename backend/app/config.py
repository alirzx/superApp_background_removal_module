"""Centralized configuration. Never log secrets or uploaded image bytes."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    model_path: Path = Path("/models/birefnet_lite_fp32.onnx")
    model_repo: str = "onnx-community/BiRefNet_lite-ONNX"
    model_revision: str = "de15b22ba131738a16dff04aab8bdf8dc32e3ac1"
    model_filename: str = "onnx/model.onnx"
    model_sha256: str = "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333"
    cpu_threads: int = 2
    max_concurrent_inference: int = 1
    max_queue_wait_seconds: float = 10.0
    max_upload_mb: int = 10
    max_image_pixels: int = 20_000_000
    api_token: str = ""
    enable_metrics: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        def integer(key: str, default: int) -> int:
            return int(os.getenv(key, str(default)))

        value = cls(
            environment=os.getenv("APP_ENV", "development").lower(),
            model_path=Path(os.getenv("MODEL_PATH", "/models/birefnet_lite_fp32.onnx")),
            model_repo=os.getenv("MODEL_REPO", "onnx-community/BiRefNet_lite-ONNX"),
            model_revision=os.getenv("MODEL_REVISION", "de15b22ba131738a16dff04aab8bdf8dc32e3ac1"),
            model_filename=os.getenv("MODEL_FILENAME", "onnx/model.onnx"),
            model_sha256=os.getenv("MODEL_SHA256", "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333").lower(),
            cpu_threads=integer("CPU_THREADS", 2),
            max_concurrent_inference=integer("MAX_CONCURRENT_INFERENCE", 1),
            max_queue_wait_seconds=float(os.getenv("MAX_QUEUE_WAIT_SECONDS", "10")),
            max_upload_mb=integer("MAX_UPLOAD_MB", 10),
            max_image_pixels=integer("MAX_IMAGE_PIXELS", 20_000_000),
            api_token=os.getenv("API_TOKEN", ""),
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
        )
        value.validate()
        return value

    def validate(self) -> None:
        if self.environment == "production" and len(self.api_token) < 24:
            raise ValueError("Production requires a strong API_TOKEN (>=24 characters)")
        if self.cpu_threads < 1 or self.max_concurrent_inference < 1:
            raise ValueError("CPU_THREADS and MAX_CONCURRENT_INFERENCE must be positive")
        if self.max_upload_mb < 1 or self.max_image_pixels < 1024 or self.max_queue_wait_seconds <= 0:
            raise ValueError("Invalid image/queue limits")
        if len(self.model_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.model_sha256):
            raise ValueError("MODEL_SHA256 must be a 64-character hexadecimal digest")
