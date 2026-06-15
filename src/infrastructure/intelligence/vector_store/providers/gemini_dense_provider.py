from __future__ import annotations
import asyncio

from src.infrastructure.intelligence.llm.embedding import GeminiEmbeddingProvider


class GeminiRagDenseProvider:
    """Dense RAG embedding provider backed by Google Gemini via google.genai.

    Implements the chatbot-plugin-sdk DenseEmbeddingProvider protocol:
      - ``dimension: int`` attribute
      - ``async def embed(texts) -> list[list[float]]``

    Wraps GeminiEmbeddingProvider.embed_batch() (sync) and runs it in
    an executor to satisfy the async interface required by IngestProcessor.
    Optional rpm/tpm/rpd parameters enable SDK SlidingWindowStrategy rate limiting.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        dimension: int,
        rpm: int | None = None,
        tpm: int | None = None,
        rpd: int | None = None,
    ) -> None:
        self._emb = GeminiEmbeddingProvider(
            api_key=api_key,
            model=model,
            output_dimensionality=dimension,
        )
        self.dimension: int = dimension
        self._rate_limit = None
        if all(v is not None for v in (rpm, tpm, rpd)):
            from chatbot_plugin_sdk.rate_limit import SlidingWindowStrategy
            self._rate_limit = SlidingWindowStrategy(rpm=rpm, tpm=tpm, rpd=rpd)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self._rate_limit is not None:
            estimated_tokens = max(1, sum(len(t) for t in texts) // 4)
            await self._rate_limit.acquire(estimated_tokens)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._emb.embed_batch, texts)
