from io import BytesIO
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


class FakeEngine:
    def __init__(self, settings):
        self.warmed_up = False
        self.size = (1024, 1024)

    def warmup(self):
        self.warmed_up = True

    def process(self, image, *, mask_only, blur):
        from app.image_pipeline import composite_result
        return composite_result(image, Image.new("L", image.size, 255), mask_only), 12.5


def make_app(token="test_secret"):
    settings = Settings(environment="development", model_path=Path("/unused"), api_token=token)
    return create_app(settings=settings, engine_factory=FakeEngine)


def image_data():
    image = Image.new("RGB", (24, 24), (250, 100, 10))
    buf = BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def test_health_and_auth():
    with TestClient(make_app()) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/v1/models").status_code == 401
        assert client.get("/v1/models", headers={"X-API-Key": "test_secret"}).status_code == 200


def test_inference_png_and_mask():
    with TestClient(make_app()) as client:
        for route, mode in [("remove-background", "RGBA"), ("mask", "L")]:
            resp = client.post(f"/v1/{route}", files={"file": ("test.png", image_data(), "image/png")}, headers={"X-API-Key": "test_secret"})
            assert resp.status_code == 200, resp.text
            assert resp.headers["content-type"] == "image/png"
            output = Image.open(BytesIO(resp.content))
            assert output.size == (24, 24)
            assert output.mode == mode


def test_bad_image_and_unsupported_media():
    with TestClient(make_app()) as client:
        head = {"X-API-Key": "test_secret"}
        r = client.post("/v1/remove-background", files={"file": ("bad.png", b"not image", "image/png")}, headers=head)
        assert r.status_code == 422
        r = client.post("/v1/remove-background", files={"file": ("bad.svg", b"<svg/>", "image/svg+xml")}, headers=head)
        assert r.status_code == 415


def test_production_requires_token():
    from pytest import raises
    with raises(ValueError):
        make = Settings(environment="production", api_token="")
        make.validate()
