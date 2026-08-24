"""Fastembed embedding service entry point.

Run with::

    uvicorn fastembed_service.main:app --host 0.0.0.0 --port 8080

Package is named `fastembed_service` (not `fastembed`) deliberately — this
service imports the `fastembed` PyPI package itself (services/embedding.py),
so naming our own package `fastembed` would shadow it on sys.path.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastembed_service.config import (
    APP_ENV, GRAFANA_LOKI_URL, GRAFANA_LOKI_USER, GRAFANA_API_KEY,
    GRAFANA_OTLP_ENDPOINT, GRAFANA_OTLP_USER,
)
from fastembed_service.observability import configure_logging, setup_tracing
from fastembed_service.routers import embed_router
from fastembed_service.services.embedding import EmbeddingService

configure_logging(
    service="fastembed",
    loki_url=GRAFANA_LOKI_URL,
    loki_user=GRAFANA_LOKI_USER,
    loki_api_key=GRAFANA_API_KEY,
    app_env=APP_ENV,
)
_tracer_provider = setup_tracing(APP_ENV, GRAFANA_OTLP_ENDPOINT, GRAFANA_OTLP_USER, GRAFANA_API_KEY)

_embedding_service = EmbeddingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _embedding_service.load()
    app.state.embedding_service = _embedding_service
    yield

    if _tracer_provider:
        _tracer_provider.shutdown()


app = FastAPI(title="Fastembed Service", version="1.0.0", lifespan=lifespan)

if _tracer_provider:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider)

app.include_router(embed_router)
