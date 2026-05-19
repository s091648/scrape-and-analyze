from typing import List

from google import genai

from src.modules.intelligence.domain.services.embedding_service import EmbeddingService
from src.shared.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 100


class GeminiEmbeddingProvider(EmbeddingService):

    def __init__(self, api_key: str, model: str = "text-embedding-004") -> None:
        self._model = model
        self._client = genai.Client(api_key=api_key)

    def embed(self, text: str) -> List[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=[text],
            config={"task_type": "CLASSIFICATION"},
        )
        logger.debug("embedding_created", model=self._model)
        return list(response.embeddings[0].values)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config={"task_type": "CLASSIFICATION"},
            )
            results.extend(list(e.values) for e in response.embeddings)
            logger.debug("embedding_batch_created", model=self._model, count=len(batch))
        return results
