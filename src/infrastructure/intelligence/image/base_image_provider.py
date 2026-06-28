from abc import ABC, abstractmethod


class BaseImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> bytes:
        """Generate an image from the prompt and return raw bytes."""
