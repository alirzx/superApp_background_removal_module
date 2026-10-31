"""Input sanitization, official ImageNet normalization, alpha compositing.

The converted BiRefNet Lite ONNX graph expects RGB NCHW floats with a
1024x1024 input, ImageNet normalization, and emits unnormalized logits.
"""
from __future__ import annotations

from io import BytesIO
import warnings

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
ALLOWED = {"JPEG", "PNG", "WEBP"}


class InvalidImage(ValueError):
    pass


def decode_image(data: bytes, *, max_pixels: int) -> Image.Image:
    if not data:
        raise InvalidImage("Empty image")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ALLOWED:
                    raise InvalidImage("Only JPEG, PNG, and WEBP images are supported")
                if image.width < 2 or image.height < 2:
                    raise InvalidImage("Image dimensions are too small")
                if image.width * image.height > max_pixels:
                    raise InvalidImage("Image pixel limit exceeded")
                image.load()
                oriented = ImageOps.exif_transpose(image)
                return oriented.convert("RGBA")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, InvalidImage):
            raise
        raise InvalidImage("Invalid, truncated, or oversized image") from exc


def preprocess(image: Image.Image, size: tuple[int, int]) -> np.ndarray:
    # Existing alpha is composited onto white for segmentation only.
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image.convert("RGBA"))
    rgb = canvas.convert("RGB").resize(size, Image.Resampling.BILINEAR)
    arr = np.asarray(rgb, dtype=np.float32) / np.float32(255.0)
    arr = (arr - MEAN) / STD
    return np.ascontiguousarray(arr.transpose(2, 0, 1)[None, :, :, :], dtype=np.float32)


def logits_to_mask(logits: np.ndarray, original_size: tuple[int, int], blur: float = 0.0) -> Image.Image:
    values = np.asarray(logits, dtype=np.float32)
    if values.ndim == 4:
        values = values[0, 0]
    elif values.ndim == 3:
        values = values[0]
    if values.ndim != 2:
        raise RuntimeError(f"Unexpected output rank: {values.ndim}")
    if not np.isfinite(values).all():
        raise RuntimeError("Model returned non-finite values")
    # Converted ONNX output is LOGITS, not 0..1 probabilities.
    alpha = 1.0 / (1.0 + np.exp(-np.clip(values, -40.0, 40.0)))
    mask = Image.fromarray(np.uint8(np.round(alpha * 255.0)), "L")
    mask = mask.resize(original_size, Image.Resampling.BILINEAR)
    if blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur))
    return mask


def composite_result(image: Image.Image, mask: Image.Image, mask_only: bool) -> bytes:
    result = mask if mask_only else image.convert("RGBA")
    if not mask_only:
        # Respect existing input transparency; don't re-expose hidden pixels.
        existing_alpha = result.getchannel("A")
        result.putalpha(ImageChops.multiply(existing_alpha, mask))
    buf = BytesIO()
    result.save(buf, format="PNG", optimize=False)
    return buf.getvalue()
