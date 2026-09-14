"""Per-request cache outcome accumulator.

`RedisCacheGateway.get_or_set()` records each lookup's status here; the backend's
`RequestLoggingMiddleware` arms it at the start of every request and folds whatever
accumulated into a single `cache_status` field on that request's `event="request"`
log line:

- one lookup            -> that lookup's status ("HIT" / "MISS" / "BYPASS")
- several, all agreeing  -> that shared status
- several, disagreeing   -> "PARTIAL"
- endpoint touched cache zero times -> field is omitted entirely

The dashboard's Redis panels (cacheHitRate, cacheLookupsByStatusChart,
cacheHitRateByNamespaceChart) keep aggregating the separate `event="cache_lookup"`
lines — this field is only a per-request rollup for the Logs table, it does not
replace those events.

A single mutable list held in a ContextVar (armed once with ``.set([])``, then
mutated in place) rather than repeated ``.set()`` calls, so the value survives the
sync-route threadpool hop the same way ``structlog.contextvars`` does: Starlette
copies the context into the worker thread, and a copied context shares the *same*
list object, so ``.append()`` from inside the handler is visible to the middleware
afterwards. Outside a request (CLI scripts, the scraper) the var is unset and every
call here is a no-op.
"""

from __future__ import annotations

import contextvars

_statuses: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "request_cache_statuses", default=None
)


def begin_request() -> None:
    """Arm the accumulator for a new request. Call once, before the handler runs."""
    _statuses.set([])


def record_cache_lookup(status: str) -> None:
    """Note one ``get_or_set()`` outcome. No-op when called outside a request."""
    bucket = _statuses.get()
    if bucket is not None:
        bucket.append(status)


def summarize_request() -> str | None:
    """Fold this request's lookups into one label, or ``None`` if it made none."""
    bucket = _statuses.get()
    if not bucket:
        return None
    first = bucket[0]
    return first if all(s == first for s in bucket) else "PARTIAL"
