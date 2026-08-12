"""Shared post-processing for weekly-report cover images.

Both image-generation providers (Gemini, HuggingFace) route their raw output through
``encode_as_webp`` before it's uploaded to R2. Generation-native PNGs were found to be far larger
than needed for a background-cover use case — a real example was ~1.1MB, of which Lighthouse's
image-delivery-insight audit estimated ~85% (951KB) was wasted purely from format/compression
choice, directly costing ~4.6s of LCP (specs/021-ssr-public-pages). Downscaling to a sane display
width and re-encoding as WebP addresses both causes at the source, for every future report.
"""
import io

from PIL import Image

DEFAULT_MAX_WIDTH = 1600
DEFAULT_QUALITY = 80


def encode_as_webp(data: bytes, max_width: int = DEFAULT_MAX_WIDTH, quality: int = DEFAULT_QUALITY) -> bytes:
    """Decode arbitrary image bytes, downscale if wider than max_width, and re-encode as WebP."""
    image = Image.open(io.BytesIO(data))
    if image.mode == "P":
        image = image.convert("RGBA")
    elif image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    if image.width > max_width:
        new_height = round(image.height * (max_width / image.width))
        image = image.resize((max_width, new_height), Image.LANCZOS)

    buf = io.BytesIO()
    image.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()
