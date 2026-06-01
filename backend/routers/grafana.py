import asyncio
import base64
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.auth.guards import require_admin

router = APIRouter(prefix="/grafana", tags=["grafana"])


def _auth_headers(user: str, api_key: str) -> dict[str, str]:
    if not user or not api_key:
        return {}
    encoded = base64.b64encode(f"{user}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


async def _grafana_get(url: str, params: dict, user: str, api_key: str) -> JSONResponse:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params, headers=_auth_headers(user, api_key))
    try:
        body = resp.json()
    except Exception:
        body = {"error": "invalid_response"}
    return JSONResponse(body, status_code=resp.status_code)


@router.get("/metrics")
async def query_metrics(
    query: str = Query(...),
    start: Optional[int] = Query(default=None),
    end: Optional[int] = Query(default=None),
    step: str = Query(default="60"),
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = os.environ.get("GRAFANA_PROMETHEUS_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_PROMETHEUS_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    now = int(time.time())
    return await _grafana_get(
        f"{url}/api/v1/query_range",
        {"query": query, "start": start or now - 86400, "end": end or now, "step": step},
        user,
        api_key,
    )


class MetricsBatchItem(BaseModel):
    query: str
    start: Optional[int] = None
    end: Optional[int] = None
    step: str = "60"


@router.post("/metrics/batch")
async def query_metrics_batch(
    items: list[MetricsBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = os.environ.get("GRAFANA_PROMETHEUS_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_PROMETHEUS_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now = int(time.time())
    headers = _auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: MetricsBatchItem) -> dict:
        try:
            resp = await client.get(
                f"{url}/api/v1/query_range",
                params={
                    "query": item.query,
                    "start": item.start or now - 86400,
                    "end": item.end or now,
                    "step": item.step,
                },
                headers=headers,
            )
            return resp.json()
        except Exception:
            return {"error": "invalid_response"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(*[fetch_one(client, item) for item in items])

    return JSONResponse(list(results))


@router.get("/logs")
async def query_logs(
    query: str = Query(...),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    limit: int = Query(default=100),
    direction: str = Query(default="backward"),
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = os.environ.get("GRAFANA_LOKI_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_LOKI_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    now_ms = int(time.time() * 1000)
    return await _grafana_get(
        f"{url}/query_range",
        {
            "query": query,
            "start": start or f"{now_ms - 6 * 3600 * 1000}000000",
            "end": end or f"{now_ms}000000",
            "limit": limit,
            "direction": direction,
        },
        user,
        api_key,
    )


class LogsBatchItem(BaseModel):
    query: str
    start: Optional[str] = None
    end: Optional[str] = None
    limit: int = 100
    direction: str = "backward"


@router.post("/logs/batch")
async def query_logs_batch(
    items: list[LogsBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = os.environ.get("GRAFANA_LOKI_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_LOKI_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now_ms = int(time.time() * 1000)
    headers = _auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: LogsBatchItem) -> dict:
        try:
            resp = await client.get(
                f"{url}/query_range",
                params={
                    "query": item.query,
                    "start": item.start or f"{now_ms - 6 * 3600 * 1000}000000",
                    "end": item.end or f"{now_ms}000000",
                    "limit": item.limit,
                    "direction": item.direction,
                },
                headers=headers,
            )
            return resp.json()
        except Exception:
            return {"error": "invalid_response"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(*[fetch_one(client, item) for item in items])

    return JSONResponse(list(results))


@router.get("/traces")
async def query_traces(
    q: Optional[str] = Query(default=None),
    start: Optional[int] = Query(default=None),
    end: Optional[int] = Query(default=None),
    limit: int = Query(default=20),
    min_duration: Optional[str] = Query(default=None, alias="minDuration"),
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = os.environ.get("GRAFANA_TEMPO_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_TEMPO_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    now = int(time.time())
    params: dict = {"start": start or now - 86400, "end": end or now, "limit": limit}
    if q:
        params["q"] = q
    if min_duration:
        params["minDuration"] = min_duration
    return await _grafana_get(f"{url}/api/search", params, user, api_key)


@router.get("/traces/{trace_id}")
async def get_trace_by_id(
    trace_id: str,
    _: dict = Depends(require_admin),
) -> JSONResponse:
    """Return the full OTLP JSON trace from Tempo for a single trace ID."""
    url = os.environ.get("GRAFANA_TEMPO_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_TEMPO_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    return await _grafana_get(f"{url}/api/traces/{trace_id}", {}, user, api_key)


class TracesBatchItem(BaseModel):
    q: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    limit: int = 20
    min_duration: Optional[str] = Field(default=None, alias="minDuration")

    model_config = {"populate_by_name": True}


@router.post("/traces/batch")
async def query_traces_batch(
    items: list[TracesBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = os.environ.get("GRAFANA_TEMPO_URL", "").rstrip("/")
    user = os.environ.get("GRAFANA_TEMPO_USER", "")
    api_key = os.environ.get("GRAFANA_API_KEY", "")
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now = int(time.time())
    headers = _auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: TracesBatchItem) -> dict:
        try:
            params: dict = {
                "start": item.start or now - 86400,
                "end": item.end or now,
                "limit": item.limit,
            }
            if item.q:
                params["q"] = item.q
            if item.min_duration:
                params["minDuration"] = item.min_duration
            resp = await client.get(f"{url}/api/search", params=params, headers=headers)
            return resp.json()
        except Exception:
            return {"error": "invalid_response"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(*[fetch_one(client, item) for item in items])

    return JSONResponse(list(results))