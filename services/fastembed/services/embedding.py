"""EmbeddingService — loads ONNX models and runs inference.

Models are loaded once at startup via load() and then reused across requests.
Inference is exposed as plain sync methods; FastAPI runs sync route handlers
in a thread-pool executor automatically, which is the correct pattern for
CPU-bound ONNX work.

Closure note: _make_*_fn() factories capture the model object by parameter
binding (not by name), so reassigning local variables between sparse/dense
loading does not corrupt either closure.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from config import (
    EMBED_SPARSE_MODEL,
    EMBED_SPARSE_BATCH_SIZE,
    EMBED_DENSE_MODEL,
    EMBED_DENSE_BATCH_SIZE,
    FASTEMBED_CACHE_PATH,
)

logger = logging.getLogger(__name__)


def _make_sparse_fn(
    model: Any, batch_size: int
) -> Callable[[list[str]], list[dict[str, float]]]:
    def fn(texts: list[str]) -> list[dict[str, float]]:
        return [
            {str(idx): float(w) for idx, w in zip(v.indices, v.values)}
            for v in model.embed(texts, batch_size=batch_size)
        ]
    return fn


def _make_dense_fn(
    model: Any, batch_size: int
) -> Callable[[list[str]], list[list[float]]]:
    def fn(texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in model.embed(texts, batch_size=batch_size)]
    return fn


class EmbeddingService:
    def __init__(self) -> None:
        self._sparse_fn: Callable[[list[str]], list[dict[str, float]]] | None = None
        self._dense_fn: Callable[[list[str]], list[list[float]]] | None = None

    async def load(self) -> None:
        """Load models in a thread-pool executor to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync)

    def _load_sync(self) -> None:
        cache = FASTEMBED_CACHE_PATH

        if EMBED_SPARSE_MODEL:
            from fastembed import SparseTextEmbedding
            logger.info("loading_sparse_model", extra={"model": EMBED_SPARSE_MODEL})
            sparse_model = SparseTextEmbedding(EMBED_SPARSE_MODEL, cache_dir=cache)
            self._sparse_fn = _make_sparse_fn(sparse_model, EMBED_SPARSE_BATCH_SIZE)
            logger.info(
                "sparse_model_ready",
                extra={"model": EMBED_SPARSE_MODEL, "batch_size": EMBED_SPARSE_BATCH_SIZE},
            )

        if EMBED_DENSE_MODEL:
            from fastembed import TextEmbedding
            logger.info("loading_dense_model", extra={"model": EMBED_DENSE_MODEL})
            dense_model = TextEmbedding(EMBED_DENSE_MODEL, cache_dir=cache)
            self._dense_fn = _make_dense_fn(dense_model, EMBED_DENSE_BATCH_SIZE)
            logger.info(
                "dense_model_ready",
                extra={"model": EMBED_DENSE_MODEL, "batch_size": EMBED_DENSE_BATCH_SIZE},
            )

        if not EMBED_SPARSE_MODEL and not EMBED_DENSE_MODEL:
            logger.warning("no_models_configured")

    @property
    def has_sparse(self) -> bool:
        return self._sparse_fn is not None

    @property
    def has_dense(self) -> bool:
        return self._dense_fn is not None

    def embed_sparse(self, texts: list[str]) -> list[dict[str, float]]:
        if self._sparse_fn is None:
            raise RuntimeError("Sparse model not loaded")
        return self._sparse_fn(texts)

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        if self._dense_fn is None:
            raise RuntimeError("Dense model not loaded")
        return self._dense_fn(texts)
