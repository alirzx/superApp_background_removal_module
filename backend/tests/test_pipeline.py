from io import BytesIO
import numpy as np
import pytest
from PIL import Image
from app.image_pipeline import decode_image, preprocess, logits_to_mask, composite_result, InvalidImage


def png_bytes(image):
    b = BytesIO()
    image.save(b, format="PNG")
    return b.getvalue()


def test_preprocess_shape_and_mean():
    image = Image.new("RGBA", (16, 20), (255, 255, 255, 255))
    result = preprocess(image, (32, 24))
    assert result.shape == (1, 3, 24, 32)
    assert result.dtype == np.float32
    assert np.isfinite(result).all()


def test_logits_mask_half_probability_and_alpha_multiplication():
    orig = Image.new("RGBA", (12, 8), (255, 0, 0, 120))
    logits = np.zeros((1, 1, 4, 4), dtype=np.float32)
    mask = logits_to_mask(logits, orig.size)
    assert mask.getpixel((0, 0)) == 128
    output = Image.open(BytesIO(composite_result(orig, mask, False)))
    assert output.mode == "RGBA"
    assert abs(output.getpixel((0, 0))[3] - 60) <= 1


def test_invalid_data_and_pixel_limit():
    with pytest.raises(InvalidImage):
        decode_image(b"not a picture", max_pixels=200)
    image = Image.new("RGB", (20, 20), "white")
    with pytest.raises(InvalidImage):
        decode_image(png_bytes(image), max_pixels=200)


def test_png_decoding_and_original_dimensions():
    image = Image.new("RGBA", (23, 17), (20, 30, 40, 50))
    result = decode_image(png_bytes(image), max_pixels=2000)
    assert result.size == (23, 17)
    assert result.mode == "RGBA"
