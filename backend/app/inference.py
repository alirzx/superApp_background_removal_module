"""ONNX Runtime model manager. No trust_remote_code, no downloads in requests."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .config import Settings
from .image_pipeline import composite_result, logits_to_mask, preprocess


class ONNXInferenceEngine:
    def __init__(self, settings: Settings) -> None:
        import onnxruntime as ort

        self.settings = settings
        path = Path(settings.model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Model missing at {path}. Run 'make model' before starting.")
        with path.open("rb") as model_file:
            sha = hashlib.file_digest(model_file, "sha256").hexdigest()
        if sha != settings.model_sha256:
            raise ValueError(f"Unverified ONNX model digest: {sha}; expected {settings.model_sha256}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = settings.cpu_threads
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise RuntimeError("CPUExecutionProvider is required")
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise RuntimeError("Unsupported model I/O topology")
        self.input_name, self.output_name = inputs[0].name, outputs[0].name
        self.input_shape, self.output_shape = inputs[0].shape, outputs[0].shape
        if not (len(self.input_shape) == 4 and self.input_shape[0] in (1, "batch_size", None)):
            raise RuntimeError(f"Unsupported input shape {self.input_shape}")
        if self.input_shape[1] != 3:
            raise RuntimeError(f"Expected 3-channel NCHW input: {self.input_shape}")
        if not all(isinstance(v, int) and v > 0 for v in self.input_shape[2:4]):
            raise RuntimeError("This deployment expects a fixed spatial input shape")
        self.size = (self.input_shape[3], self.input_shape[2])  # (width, height)
        # Validate expected signature to catch swapping in an unrelated model.
        if self.input_name != "input_image" or self.output_name != "output_image":
            raise RuntimeError(f"Unexpected ONNX I/O names: {self.input_name} -> {self.output_name}")
        self.model_digest = sha
        self.warmed_up = False

    def warmup(self) -> None:
        # Warm-up can take time but avoids cold first live request.
        shape = (1, 3, self.size[1], self.size[0])
        output = self.session.run([self.output_name], {self.input_name: np.zeros(shape, dtype=np.float32)})[0]
        if np.asarray(output).ndim != 4:
            raise RuntimeError("ONNX output is not a 4D mask")
        self.warmed_up = True

    def process(self, image: Image.Image, *, mask_only: bool, blur: float) -> tuple[bytes, float]:
        inp = preprocess(image, self.size)
        start = time.perf_counter()
        out = self.session.run([self.output_name], {self.input_name: inp})[0]
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        mask = logits_to_mask(out, image.size, blur)
        return composite_result(image, mask, mask_only), elapsed_ms
