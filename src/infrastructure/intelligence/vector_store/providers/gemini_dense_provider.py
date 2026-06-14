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
    """

    def __init__(self, api_key: str, model: str, dimension: int) -> None:
        self._emb = GeminiEmbeddingProvider(
            api_key=api_key,
            model=model,
            output_dimensionality=dimension,
        )
        self.dimension: int = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._emb.embed_batch, texts)
