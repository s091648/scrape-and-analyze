from src.infrastructure.intelligence.image.base_image_provider import BaseImageProvider
from src.modules.intelligence.domain.services.image_generation_service import ImageGenerationService


class GeminiImagenProvider(ImageGenerationService, BaseImageProvider):
    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._api_key = api_key

    def generate_image(self, prompt: str) -> bytes:
        return self.generate(prompt)

    def generate(self, prompt: str) -> bytes:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_images(
            model=self._model,
            prompt=prompt,
            config=genai_types.GenerateImagesConfig(number_of_images=1),
        )
        image = response.generated_images[0]
        return image.image.image_bytes
