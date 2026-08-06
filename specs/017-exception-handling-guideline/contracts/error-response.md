# Contract: API Error Response

Applies to every endpoint under `backend/routers/` for every non-2xx response, replacing the current per-endpoint, inconsistent `HTTPException(status_code=..., detail=...)` shapes.

## Shape

```json
{
  "error": {
    "code": "string, SCREAMING_SNAKE_CASE, one of a fixed set (see mapping table in data-model.md)",
    "message": "string, human-readable",
    "request_id": "string, UUID v4 — matches the X-Request-ID response header for the same request"
  }
}
```

## Status codes in scope

`400`, `401`, `403`, `404`, `409`, `500`, `502` (see data-model.md §2 for the full trigger table). `422` remains FastAPI/Pydantic's native request-validation response and is explicitly **not** reshaped by this contract (research.md §5) — FastAPI's default `{"detail": [...]}` shape stays as-is for 422.

## Guarantees

1. **Consistency**: Every endpoint returning 400/401/403/404/409/500/502 uses this exact shape — no endpoint-specific fields, no bare string bodies.
2. **No leakage** (FR-009): For 500/502, `error.message` is a fixed generic string per category (e.g. `"An unexpected error occurred"` / `"An upstream dependency is unavailable"`), never `str(exception)`, a stack trace, a file path, or raw SQL/DB error text.
3. **Traceability**: `error.request_id` always matches the `X-Request-ID` header already set by `RequestLoggingMiddleware` for that request, and that same ID appears in the corresponding structured server-side log line.
4. **Streaming exception**: For responses where the HTTP status has already been committed before the failure occurs (e.g. Server-Sent Events), this contract does not apply to the (already-sent) HTTP status; the in-stream error payload MUST still use the same `error.code`/`error.message` vocabulary as this contract, without a `request_id`/status-code field that no longer has meaning mid-stream.

## Non-goals

- This contract does not change the *success* (2xx) response shape of any endpoint.
- This contract does not change FastAPI's native 422 validation-error shape.
