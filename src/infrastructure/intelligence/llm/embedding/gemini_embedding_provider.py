import json
from typing import List

from google import genai

from .base_embedding_provider import BaseEmbeddingProvider
from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

logger = get_logger(__name__)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        output_dimensionality: int = 768,
    ) -> None:
        super().__init__(model=model)
        self._output_dimensionality = output_dimensionality
        self._client = genai.Client(api_key=api_key)

    def _call_embed(self, texts: List[str]) -> List[List[float]]:
        try:
            response = self._client.models.embed_content(
                model=self._model,
                contents=texts,
                config={"task_type": "CLASSIFICATION", "output_dimensionality": self._output_dimensionality},
            )
            logger.debug("embedding_batch_created", model=self._model, count=len(texts))
        except Exception as e:
            error_str = str(e)
            if "RESOURCE_EXHAUSTED" in error_str and "PerDay" in error_str:
                raise RateLimitExhausted(f"Daily quota exceeded for {self._model}") from e
            raise
        return [list(e.values) for e in response.embeddings]

    def count_tokens(self, text: str) -> int:
        token_count_response = self._client.models.count_tokens(
            model=self._model,
            contents=[text],
        )
        logger.debug("token_counted", model=self._model, tokens=token_count_response.total_tokens)
        return token_count_response.total_tokens
