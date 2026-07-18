from abc import ABC, abstractmethod


class BlobStorageService(ABC):
    @abstractmethod
    def upload(self, data: bytes, key: str, content_type: str) -> str:
        """Upload data to blob storage and return the public URL."""
