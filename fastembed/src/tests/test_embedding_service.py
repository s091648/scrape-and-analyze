"""Tests for EmbeddingService — model loading and inference, without touching real ONNX models."""
from unittest.mock import MagicMock

import pytest

from fastembed_service.services import embedding as embedding_module
from fastembed_service.services.embedding import EmbeddingService


class _FakeVector:
    """Stands in for fastembed's sparse/dense embedding result objects."""

    def __init__(self, indices=None, values=None, dense=None):
        self.indices = indices or []
        self.values = values or []
        self._dense = dense or []

    def tolist(self):
        return self._dense


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """EMBED_*_MODEL are read as module-level constants at import time, so tests
    override the names bound inside embedding.py directly rather than config.py."""
    monkeypatch.setattr(embedding_module, "EMBED_SPARSE_MODEL", "")
    monkeypatch.setattr(embedding_module, "EMBED_DENSE_MODEL", "")
    monkeypatch.setattr(embedding_module, "EMBED_SPARSE_BATCH_SIZE", 8)
    monkeypatch.setattr(embedding_module, "EMBED_DENSE_BATCH_SIZE", 32)
    monkeypatch.setattr(embedding_module, "FASTEMBED_CACHE_PATH", None)


@pytest.mark.asyncio
async def test_load_with_no_models_configured_leaves_both_unloaded():
    svc = EmbeddingService()

    await svc.load()

    assert svc.has_sparse is False
    assert svc.has_dense is False


@pytest.mark.asyncio
async def test_load_sparse_model_only(monkeypatch):
    monkeypatch.setattr(embedding_module, "EMBED_SPARSE_MODEL", "prithivida/Splade_PP_en_v1")
    fake_model = MagicMock()
    fake_model.embed.return_value = [_FakeVector(indices=[3, 7], values=[0.9, 0.4])]
    fake_cls = MagicMock(return_value=fake_model)
    monkeypatch.setattr("fastembed.SparseTextEmbedding", fake_cls, raising=False)

    svc = EmbeddingService()
    await svc.load()

    assert svc.has_sparse is True
    assert svc.has_dense is False
    fake_cls.assert_called_once_with("prithivida/Splade_PP_en_v1", cache_dir=None)
    assert svc.embed_sparse(["hello"]) == [{"3": 0.9, "7": 0.4}]


@pytest.mark.asyncio
async def test_load_dense_model_only(monkeypatch):
    monkeypatch.setattr(embedding_module, "EMBED_DENSE_MODEL", "some/dense-model")
    fake_model = MagicMock()
    fake_model.embed.return_value = [_FakeVector(dense=[0.1, 0.2, 0.3])]
    fake_cls = MagicMock(return_value=fake_model)
    monkeypatch.setattr("fastembed.TextEmbedding", fake_cls, raising=False)

    svc = EmbeddingService()
    await svc.load()

    assert svc.has_dense is True
    assert svc.has_sparse is False
    assert svc.embed_dense(["hello"]) == [[0.1, 0.2, 0.3]]


def test_embed_sparse_before_load_raises():
    svc = EmbeddingService()
    with pytest.raises(RuntimeError, match="Sparse model not loaded"):
        svc.embed_sparse(["hello"])


def test_embed_dense_before_load_raises():
    svc = EmbeddingService()
    with pytest.raises(RuntimeError, match="Dense model not loaded"):
        svc.embed_dense(["hello"])
