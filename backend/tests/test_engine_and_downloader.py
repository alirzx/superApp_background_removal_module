import hashlib
import sys
import types

import numpy as np
from PIL import Image

from app.config import Settings
from app.inference import ONNXInferenceEngine
from scripts.download_model import download


class FakeIO:
    def __init__(self, name, shape):
        self.name, self.shape = name, shape


class FakeSession:
    def __init__(self, path, sess_options, providers):
        self.path = path
        assert providers == ["CPUExecutionProvider"]

    def get_providers(self):
        return ["CPUExecutionProvider"]

    def get_inputs(self):
        return [FakeIO("input_image", [1, 3, 8, 8])]

    def get_outputs(self):
        return [FakeIO("output_image", [1, 1, 8, 8])]

    def run(self, names, inputs):
        assert names == ["output_image"]
        assert inputs["input_image"].shape == (1, 3, 8, 8)
        return [np.ones((1, 1, 8, 8), dtype=np.float32)]


class FakeOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.graph_optimization_level = None


def test_cpu_engine_load_warmup_and_run(tmp_path, monkeypatch):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"test-weights")
    fake = types.SimpleNamespace(
        SessionOptions=FakeOptions,
        ExecutionMode=types.SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        GraphOptimizationLevel=types.SimpleNamespace(ORT_ENABLE_ALL="all"),
        InferenceSession=FakeSession,
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", fake)
    settings = Settings(model_path=path, model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    engine = ONNXInferenceEngine(settings)
    assert engine.warmed_up is False
    engine.warmup()
    assert engine.warmed_up is True
    image = Image.new("RGB", (10, 20), "red")
    output, elapsed = engine.process(image, mask_only=False, blur=0)
    assert output[:8] == b"\x89PNG\r\n\x1a\n"
    assert elapsed >= 0


def test_model_download_cached_and_verify_only(tmp_path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"test-weights")
    settings = Settings(model_path=path, model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    download(settings, verify_only=True)
    download(settings, verify_only=False)


def test_download_atomically_from_local_fake_hub(tmp_path, monkeypatch):
    from scripts.download_model import download
    source = tmp_path / "hf-cached.onnx"
    source.write_bytes(b"simulated-pretrained-weights")
    target = tmp_path / "volume" / "model.onnx"
    signature = hashlib.sha256(source.read_bytes()).hexdigest()
    settings = Settings(model_path=target, model_sha256=signature)
    fake_hub = types.SimpleNamespace(hf_hub_download=lambda **kwargs: str(source))
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    download(settings)
    assert target.read_bytes() == source.read_bytes()
    assert not target.with_suffix(".onnx.partial").exists()
    download(settings, verify_only=True)
