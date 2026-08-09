"""Unit tests for HuggingFaceImageProvider."""
import io
from unittest.mock import MagicMock, patch

from PIL import Image

from src.infrastructure.intelligence.image.huggingface_image_provider import HuggingFaceImageProvider


def _make_provider(model="black-forest-labs/FLUX.1-schnell", api_key="test-key"):
    return HuggingFaceImageProvider(model=model, api_key=api_key)


def test_generate_image_returns_webp_encoded_bytes():
    provider = _make_provider()
    fake_image = Image.new("RGB", (2000, 1000), color=(10, 20, 30))

    with patch("src.infrastructure.intelligence.image.huggingface_image_provider.InferenceClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.text_to_image.return_value = fake_image

        result = provider.generate_image("a futuristic visualization")

    decoded = Image.open(io.BytesIO(result))
    assert decoded.format == "WEBP"
    assert decoded.width <= 1600  # downscaled from the 2000px-wide source


def test_generate_image_passes_prompt_and_model_to_client():
    provider = _make_provider(model="stabilityai/stable-diffusion-xl-base-1.0")
    fake_image = Image.new("RGB", (100, 100))

    with patch("src.infrastructure.intelligence.image.huggingface_image_provider.InferenceClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.text_to_image.return_value = fake_image

        provider.generate_image("test prompt")

    mock_client.text_to_image.assert_called_once_with(
        "test prompt", model="stabilityai/stable-diffusion-xl-base-1.0",
    )


def test_generate_image_initializes_client_with_api_key_and_timeout():
    provider = HuggingFaceImageProvider(model="m", api_key="my-secret-key", timeout=30.0)
    fake_image = Image.new("RGB", (100, 100))

    with patch("src.infrastructure.intelligence.image.huggingface_image_provider.InferenceClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.text_to_image.return_value = fake_image

        provider.generate_image("prompt")

    MockClient.assert_called_once_with(token="my-secret-key", timeout=30.0)
