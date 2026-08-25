"""Embed router — POST /embed and GET /health."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from fastembed_service.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

embed_router = APIRouter()


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    sparse: list[dict[str, float]] | None = None
    dense: list[list[float]] | None = None


def _get_service(request: Request) -> EmbeddingService:
    svc: EmbeddingService | None = getattr(request.app.state, "embedding_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")
    return svc


@embed_router.get("/health")
def health(request: Request):
    svc = _get_service(request)
    return {"status": "ok", "sparse": svc.has_sparse, "dense": svc.has_dense}


@embed_router.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest, request: Request):
    """Compute embeddings for a list of texts.

    Sync handler — FastAPI runs it in a thread-pool executor, which is correct
    for CPU-bound ONNX inference (avoids blocking the async event loop).
    """
    if not req.texts:
        raise HTTPException(status_code=422, detail="texts must be non-empty")

    svc = _get_service(request)
    if not svc.has_sparse and not svc.has_dense:
        raise HTTPException(status_code=503, detail="No models loaded")

    logger.debug("embed_request", extra={"text_count": len(req.texts)})
    response = EmbedResponse()
    if svc.has_sparse:
        response.sparse = svc.embed_sparse(req.texts)
    if svc.has_dense:
        response.dense = svc.embed_dense(req.texts)
    logger.debug("embed_done", extra={"text_count": len(req.texts)})
    return response
