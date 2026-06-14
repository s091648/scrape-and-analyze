from __future__ import annotations

from chatbot_plugin_sdk.providers import LocalProvider


class LocalDenseRagProvider:
    """Dense RAG embedding provider backed by fastembed TextEmbedding (in-process).

    Implements the chatbot-plugin-sdk DenseEmbeddingProvider protocol.
    fastembed is loaded lazily on first instantiation; import errors propagate
    to build_rag_ingestion_service() which handles them gracefully.
    """

    def __init__(self, model: str, dimension: int) -> None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model)
        self._provider = LocalProvider(
            fn=lambda texts: [v.tolist() for v in _model.embed(texts)],
            dimension=dimension,
        )
        self.dimension: int = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._provider.embed(texts)
