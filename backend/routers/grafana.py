import asyncio
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.auth.guards import require_admin
from backend.config import (
    GRAFANA_PROMETHEUS_URL,
    GRAFANA_PROMETHEUS_USER,
    GRAFANA_API_KEY,
    GRAFANA_LOKI_URL,
    GRAFANA_LOKI_USER,
    GRAFANA_TEMPO_URL,
    GRAFANA_TEMPO_USER,
)
from backend.schemas.grafana import (
    MetricsBatchItem,
    LogsBatchItem,
    LokiMetricsBatchItem,
    TracesBatchItem,
)
from backend.services.grafana_service import auth_headers, grafana_get

router = APIRouter(prefix="/grafana", tags=["grafana"])


@router.get("/metrics")
async def query_metrics(
    query: str = Query(...),
    start: Optional[int] = Query(default=None),
    end: Optional[int] = Query(default=None),
    step: str = Query(default="60"),
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = GRAFANA_PROMETHEUS_URL
    user = GRAFANA_PROMETHEUS_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    now = int(time.time())
    return await grafana_get(
        f"{url}/api/v1/query_range",
        {"query": query, "start": (now - 86400) if start is None else start,
         "end": now if end is None else end, "step": step},
        user, api_key,
    )


@router.post("/metrics/batch")
async def query_metrics_batch(
    items: list[MetricsBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = GRAFANA_PROMETHEUS_URL
    user = GRAFANA_PROMETHEUS_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now = int(time.time())
    headers = auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: MetricsBatchItem) -> dict:
        try:
            resp = await client.get(
                f"{url}/api/v1/query_range",
                params={"query": item.query,
                        "start": (now - 86400) if item.start is None else item.start,
                        "end": now if item.end is None else item.end,
                        "step": item.step},
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
    url = GRAFANA_LOKI_URL
    user = GRAFANA_LOKI_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    now_ms = int(time.time() * 1000)
    return await grafana_get(
        f"{url}/query_range",
        {"query": query,
         "start": start or f"{now_ms - 6 * 3600 * 1000}000000",
         "end": end or f"{now_ms}000000",
         "limit": limit, "direction": direction},
        user, api_key,
    )


@router.post("/loki-metrics/batch")
async def query_loki_metrics_batch(
    items: list[LokiMetricsBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = GRAFANA_LOKI_URL
    user = GRAFANA_LOKI_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now = int(time.time())
    headers = auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: LokiMetricsBatchItem) -> dict:
        try:
            resp = await client.get(
                f"{url}/query_range",
                params={"query": item.query,
                        "start": (now - 86400) if item.start is None else item.start,
                        "end": now if item.end is None else item.end,
                        "step": item.step},
                headers=headers,
            )
            return resp.json()
        except Exception:
            return {"error": "invalid_response"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(*[fetch_one(client, item) for item in items])
    return JSONResponse(list(results))


@router.post("/logs/batch")
async def query_logs_batch(
    items: list[LogsBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = GRAFANA_LOKI_URL
    user = GRAFANA_LOKI_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now_ms = int(time.time() * 1000)
    headers = auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: LogsBatchItem) -> dict:
        try:
            resp = await client.get(
                f"{url}/query_range",
                params={"query": item.query,
                        "start": item.start or f"{now_ms - 6 * 3600 * 1000}000000",
                        "end": item.end or f"{now_ms}000000",
                        "limit": item.limit, "direction": item.direction},
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
    url = GRAFANA_TEMPO_URL
    user = GRAFANA_TEMPO_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)
    now = int(time.time())
    params: dict = {"start": (now - 86400) if start is None else start,
                    "end": now if end is None else end, "limit": limit}
    if q:
        params["q"] = q
    if min_duration:
        params["minDuration"] = min_duration
    return await grafana_get(f"{url}/api/search", params, user, api_key)


@router.get("/traces/{trace_id}")
async def get_trace_by_id(
    trace_id: str,
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = GRAFANA_TEMPO_URL
    user = GRAFANA_TEMPO_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse({"error": "not_configured"}, status_code=503)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{url}/api/traces/{trace_id}", headers=auth_headers(user, api_key))
    try:
        body = resp.json()
    except Exception:
        return JSONResponse({"error": "invalid_response"}, status_code=resp.status_code)

    if isinstance(body, dict) and "resourceSpans" in body and "batches" not in body:
        body["batches"] = body.pop("resourceSpans")

    return JSONResponse(body, status_code=resp.status_code)


@router.post("/traces/batch")
async def query_traces_batch(
    items: list[TracesBatchItem],
    _: dict = Depends(require_admin),
) -> JSONResponse:
    url = GRAFANA_TEMPO_URL
    user = GRAFANA_TEMPO_USER
    api_key = GRAFANA_API_KEY
    if not url or not user or not api_key:
        return JSONResponse([{"error": "not_configured"}] * len(items), status_code=503)

    now = int(time.time())
    headers = auth_headers(user, api_key)

    async def fetch_one(client: httpx.AsyncClient, item: TracesBatchItem) -> dict:
        try:
            params: dict = {"start": (now - 86400) if item.start is None else item.start,
                            "end": now if item.end is None else item.end,
                            "limit": item.limit}
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
