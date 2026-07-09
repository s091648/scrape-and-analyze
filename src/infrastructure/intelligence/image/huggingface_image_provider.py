"""HuggingFace Inference API image generation provider.

Uses the HuggingFace Hub InferenceClient.text_to_image() — backed by models
such as ``stabilityai/stable-diffusion-xl-base-1.0`` or ``black-forest-labs/FLUX.1-schnell``
on the free Inference API tier.

Why this exists: Google AI Studio's free tier does not expose an image
generation endpoint (Imagen is paid-only). HuggingFace's Inference API offers
a free tier for community-hosted text-to-image models, which is sufficient for
weekly report cover images.
"""
import io

from huggingface_hub import InferenceClient

from src.modules.intelligence.domain.services.image_generation_service import ImageGenerationService


class HuggingFaceImageProvider(ImageGenerationService):
    """Generate cover images via the HuggingFace Inference API.

    The provider is stateless: every call opens a short-lived
    ``InferenceClient`` (cheap to construct) and decodes the returned
    ``PIL.Image`` to PNG bytes. The DB contract expects raw image bytes
    regardless of provider, so callers do not need to know which backend
    produced them.
    """

    def __init__(self, model: str, api_key: str, timeout: float = 60.0) -> None:
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def generate_image(self, prompt: str) -> bytes:
        client = InferenceClient(token=self._api_key, timeout=self._timeout)
        image = client.text_to_image(prompt, model=self._model)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
