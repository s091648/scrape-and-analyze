import base64

import httpx
from fastapi.responses import JSONResponse


def auth_headers(user: str, api_key: str) -> dict[str, str]:
    if not user or not api_key:
        return {}
    encoded = base64.b64encode(f"{user}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


async def grafana_get(url: str, params: dict, user: str, api_key: str) -> JSONResponse:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params, headers=auth_headers(user, api_key))
    try:
        body = resp.json()
    except Exception:
        body = {"error": "invalid_response"}
    return JSONResponse(body, status_code=resp.status_code)
