"""Unit tests for image_encoding.encode_as_webp."""
import io

from PIL import Image

from src.infrastructure.intelligence.image.image_encoding import DEFAULT_MAX_WIDTH, encode_as_webp


def _make_png_bytes(width, height, mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), color=(0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_encodes_as_webp():
    result = encode_as_webp(_make_png_bytes(100, 50))
    decoded = Image.open(io.BytesIO(result))
    assert decoded.format == "WEBP"


def test_downscales_images_wider_than_max_width():
    result = encode_as_webp(_make_png_bytes(2000, 1000), max_width=800)
    decoded = Image.open(io.BytesIO(result))
    assert decoded.width == 800
    assert decoded.height == 400  # aspect ratio preserved


def test_leaves_images_narrower_than_max_width_unresized():
    result = encode_as_webp(_make_png_bytes(400, 200), max_width=800)
    decoded = Image.open(io.BytesIO(result))
    assert decoded.width == 400
    assert decoded.height == 200


def test_uses_default_max_width_when_not_specified():
    result = encode_as_webp(_make_png_bytes(3000, 1500))
    decoded = Image.open(io.BytesIO(result))
    assert decoded.width == DEFAULT_MAX_WIDTH


def test_converts_palette_mode_images():
    palette_png = _make_png_bytes(50, 50, mode="P")
    result = encode_as_webp(palette_png)
    decoded = Image.open(io.BytesIO(result))
    assert decoded.format == "WEBP"


def test_significantly_reduces_file_size_for_an_oversized_image():
    # Mirrors the real-world case that motivated this (specs/021-ssr-public-pages): a large,
    # generation-native PNG should shrink substantially once downscaled + re-encoded.
    large_png = _make_png_bytes(2400, 1200)
    result = encode_as_webp(large_png, max_width=1600, quality=80)
    assert len(result) < len(large_png)
