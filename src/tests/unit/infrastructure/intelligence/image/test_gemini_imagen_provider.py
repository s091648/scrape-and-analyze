"""Unit tests for GeminiImagenProvider."""
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.infrastructure.intelligence.image.gemini_imagen_provider import GeminiImagenProvider


def _make_provider(model="gemini-3.1-flash-image", api_key="test-key"):
    return GeminiImagenProvider(model=model, api_key=api_key)


def _make_png_bytes(width=20, height=10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _make_genai_response(image_bytes=None):
    if image_bytes is None:
        image_bytes = _make_png_bytes()
    part = MagicMock()
    part.inline_data.data = image_bytes

    content = MagicMock()
    content.parts = [part]

    candidate = MagicMock()
    candidate.content = content

    response = MagicMock()
    response.candidates = [candidate]
    return response


def test_generate_image_returns_webp_encoded_bytes():
    provider = _make_provider()
    original_png = _make_png_bytes(width=2000, height=1000)  # wider than DEFAULT_MAX_WIDTH
    fake_response = _make_genai_response(original_png)

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_content.return_value = fake_response

        result = provider.generate_image("a futuristic visualization")

    # Not a passthrough — every provider's raw output is re-encoded via encode_as_webp()
    # (downscaled + converted), so the result must differ from and be smaller than the input.
    assert result != original_png
    assert len(result) < len(original_png)
    decoded = Image.open(io.BytesIO(result))
    assert decoded.format == "WEBP"
    assert decoded.width <= 1600


def test_generate_image_passes_prompt_to_api():
    provider = _make_provider()
    fake_response = _make_genai_response()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_content.return_value = fake_response

        provider.generate_image("test prompt")

    call_kwargs = mock_client.models.generate_content.call_args
    assert call_kwargs[1]["contents"] == "test prompt"


def test_generate_image_uses_configured_model():
    provider = _make_provider(model="my-model-v2")
    fake_response = _make_genai_response()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_content.return_value = fake_response

        provider.generate_image("prompt")

    call_kwargs = mock_client.models.generate_content.call_args
    assert call_kwargs[1]["model"] == "my-model-v2"


def test_generate_image_initializes_client_with_api_key():
    provider = _make_provider(api_key="my-secret-key")
    fake_response = _make_genai_response()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_content.return_value = fake_response

        provider.generate_image("prompt")

    MockClient.assert_called_once_with(api_key="my-secret-key")


def test_generate_image_raises_when_no_image_in_response():
    provider = _make_provider()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        response = MagicMock()
        response.candidates = []
        mock_client.models.generate_content.return_value = response

        with pytest.raises(RuntimeError, match="未包含任何圖片數據"):
            provider.generate_image("prompt")


def test_generate_image_propagates_api_error():
    provider = _make_provider()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_content.side_effect = Exception("API quota exceeded")

        with pytest.raises(Exception, match="API quota exceeded"):
            provider.generate_image("prompt")
