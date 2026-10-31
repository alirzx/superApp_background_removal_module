"""Security and configuration regressions for pre-build readiness."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class ReadyEngine:
    def __init__(self, settings):
        self.warmed_up = False
        self.size = (1024, 1024)

    def warmup(self):
        self.warmed_up = True

    def process(self, *args, **kwargs):
        raise AssertionError("Large request must not reach inference")


def test_production_requires_strong_secret():
    with pytest.raises(ValueError):
        Settings(environment="production", api_token="short").validate()
    Settings(environment="production", api_token="x" * 32).validate()


def test_declared_oversized_upload_rejected():
    app = create_app(settings=Settings(model_path=Path("/unused"), max_upload_mb=1), engine_factory=ReadyEngine)
    with TestClient(app) as client:
        response = client.post("/v1/mask", headers={"content-length": str(3 * 1024 * 1024)}, content=b"small-body")
    assert response.status_code == 413


def test_no_store_and_nosniff_headers():
    app = create_app(settings=Settings(model_path=Path("/unused")), engine_factory=ReadyEngine)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
