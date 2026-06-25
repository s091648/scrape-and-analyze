"""Fastembed embedding service entry point.

Run with::

    uvicorn main:app --host 0.0.0.0 --port 8080
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import APP_ENV, GRAFANA_LOKI_URL, GRAFANA_LOKI_USER, GRAFANA_API_KEY
from observability import configure_logging
from routers import embed_router
from services.embedding import EmbeddingService

configure_logging(
    service="fastembed",
    loki_url=GRAFANA_LOKI_URL,
    loki_user=GRAFANA_LOKI_USER,
    loki_api_key=GRAFANA_API_KEY,
    app_env=APP_ENV,
)

_embedding_service = EmbeddingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _embedding_service.load()
    app.state.embedding_service = _embedding_service
    yield


app = FastAPI(title="Fastembed Service", version="1.0.0", lifespan=lifespan)
app.include_router(embed_router)
