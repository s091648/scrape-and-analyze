"""Tests for the /health and /embed routes."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastembed_service.routers import embed_router


@pytest.mark.asyncio
async def test_health_reports_loaded_models(client: AsyncClient, mock_embedding_service: MagicMock):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "sparse": True, "dense": False}


@pytest.mark.asyncio
async def test_embed_returns_sparse_only_when_dense_not_loaded(
    client: AsyncClient, mock_embedding_service: MagicMock
):
    resp = await client.post("/embed", json={"texts": ["hello world"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sparse"] == [{"0": 0.5}]
    assert body["dense"] is None
    mock_embedding_service.embed_sparse.assert_called_once_with(["hello world"])
    mock_embedding_service.embed_dense.assert_not_called()


@pytest.mark.asyncio
async def test_embed_returns_both_when_both_loaded(client: AsyncClient, mock_embedding_service: MagicMock):
    mock_embedding_service.has_dense = True

    resp = await client.post("/embed", json={"texts": ["a", "b"]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["sparse"] == [{"0": 0.5}]
    assert body["dense"] == [[0.1, 0.2]]


@pytest.mark.asyncio
async def test_embed_rejects_empty_texts(client: AsyncClient):
    resp = await client.post("/embed", json={"texts": []})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_embed_503_when_no_models_loaded(client: AsyncClient, mock_embedding_service: MagicMock):
    mock_embedding_service.has_sparse = False
    mock_embedding_service.has_dense = False

    resp = await client.post("/embed", json={"texts": ["hello"]})

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_health_503_when_embedding_service_not_initialized():
    """No app.state.embedding_service set at all — the pre-lifespan-startup state,
    or a health check that races ahead of it — not the same as "loaded with no
    models", which is a different 503 asserted above."""
    uninitialized_app = FastAPI()
    uninitialized_app.include_router(embed_router)
    transport = ASGITransport(app=uninitialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/health")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Embedding service not initialized"
