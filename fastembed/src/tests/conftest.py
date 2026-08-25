"""Shared test fixtures."""
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastembed_service.routers import embed_router
from fastembed_service.services.embedding import EmbeddingService


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """A MagicMock standing in for EmbeddingService, defaulting to sparse-only
    (mirrors the production default: EMBED_SPARSE_MODEL set, EMBED_DENSE_MODEL empty)."""
    svc = MagicMock(spec=EmbeddingService)
    svc.has_sparse = True
    svc.has_dense = False
    svc.embed_sparse.return_value = [{"0": 0.5}]
    svc.embed_dense.return_value = [[0.1, 0.2]]
    return svc


@pytest.fixture
def app(mock_embedding_service: MagicMock) -> FastAPI:
    """A minimal FastAPI app carrying just the embed_router, with a mock
    EmbeddingService attached to app.state — mirrors production main.py's
    lifespan wiring without loading real ONNX models."""
    test_app = FastAPI()
    test_app.state.embedding_service = mock_embedding_service
    test_app.include_router(embed_router)
    return test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
