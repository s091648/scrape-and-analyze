from abc import ABC, abstractmethod


class ImageGenerationService(ABC):
    @abstractmethod
    def generate_image(self, prompt: str) -> bytes:
        """Generate an image from the prompt and return raw bytes."""
