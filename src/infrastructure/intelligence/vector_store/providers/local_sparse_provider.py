from __future__ import annotations

import os

from chatbot_plugin_sdk.providers.local import LocalProvider


class LocalSparseRagProvider:
    """Sparse RAG embedding provider backed by fastembed SparseTextEmbedding (in-process).

    Implements the chatbot-plugin-sdk SparseEmbeddingProvider protocol.
    """

    def __init__(self, model: str, dimension: int) -> None:
        from fastembed import SparseTextEmbedding
        cache_dir = os.getenv("FASTEMBED_CACHE_PATH") or None
        _model = SparseTextEmbedding(model, cache_dir=cache_dir)
        self._provider = LocalProvider(
            fn=lambda texts: [
                {str(idx): float(weight) for idx, weight in zip(v.indices, v.values)}
                for v in _model.embed(texts)
            ],
            dimension=dimension,
        )
        self.dimension: int = dimension

    async def embed(self, texts: list[str]) -> list[dict[str, float]]:
        return await self._provider.embed(texts)
