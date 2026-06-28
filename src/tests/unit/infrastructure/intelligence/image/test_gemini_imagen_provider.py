"""Unit tests for GeminiImagenProvider."""
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.intelligence.image.gemini_imagen_provider import GeminiImagenProvider


def _make_provider(model="imagen-3.0-generate-001", api_key="test-key"):
    return GeminiImagenProvider(model=model, api_key=api_key)


def _make_genai_response(image_bytes=b"fake-png"):
    mock_image = MagicMock()
    mock_image.image.image_bytes = image_bytes

    response = MagicMock()
    response.generated_images = [mock_image]
    return response


def test_generate_image_returns_bytes():
    provider = _make_provider()
    fake_response = _make_genai_response(b"png-bytes")

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_images.return_value = fake_response

        result = provider.generate_image("a futuristic visualization")

    assert result == b"png-bytes"


def test_generate_image_passes_prompt_to_api():
    provider = _make_provider()
    fake_response = _make_genai_response()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_images.return_value = fake_response

        provider.generate_image("test prompt")

    call_kwargs = mock_client.models.generate_images.call_args
    assert call_kwargs[1]["prompt"] == "test prompt"


def test_generate_image_uses_configured_model():
    provider = _make_provider(model="my-model-v2")
    fake_response = _make_genai_response()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_images.return_value = fake_response

        provider.generate_image("prompt")

    call_kwargs = mock_client.models.generate_images.call_args
    assert call_kwargs[1]["model"] == "my-model-v2"


def test_generate_image_initializes_client_with_api_key():
    provider = _make_provider(api_key="my-secret-key")
    fake_response = _make_genai_response()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_images.return_value = fake_response

        provider.generate_image("prompt")

    MockClient.assert_called_once_with(api_key="my-secret-key")


def test_generate_image_propagates_api_error():
    provider = _make_provider()

    with patch("google.genai.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.models.generate_images.side_effect = Exception("API quota exceeded")

        with pytest.raises(Exception, match="API quota exceeded"):
            provider.generate_image("prompt")
