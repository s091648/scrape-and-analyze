# Contract: `CacheGateway`

Module: `shared/cache/gateway.py` (Protocol) + `shared/cache/redis_gateway.py` (`RedisCacheGateway`, the only implementation).

This is the one shared interface both `backend/` and `src/` depend on. Every read endpoint in scope and every write call site in scope MUST go through this contract rather than talking to Redis directly, so the key-building logic (namespace + version + param hash, per data-model.md) lives in exactly one place and cannot drift between the read side and the write side.

## Interface

```python
class CacheGateway(Protocol):
    def get_or_set(
        self,
        namespace: str,
        params: dict,
        ttl_seconds: int,
        loader: Callable[[], Any],
        lang: str = "en",
    ) -> Any:
        """Cache-aside read. Returns the cached value for (namespace, params, lang) if present
        and still valid for the namespace's current version; otherwise calls loader(), caches
        the result under the current version, and returns it."""
        ...

    def bump_version(self, namespace: str) -> int:
        """Invalidate every previously-cached entry in `namespace` at once by incrementing its
        version counter. Returns the new version. Idempotent-safe to call more than once per
        logical write (e.g. a batch of tag edits) — extra bumps only cost one wasted cache
        generation, never incorrect data."""
        ...
```

## Behavioral requirements

1. **Never raises to the caller on Redis unavailability.** Both methods MUST catch connection errors internally, log a warning (`get_logger(__name__)`), and:
   - `get_or_set`: fall through to calling `loader()` directly and return its result, uncached.
   - `bump_version`: no-op, log and return (the caller doesn't need the new version for anything but observability).
   This is what makes FR-009 / Constitution Principle VI's graceful-degradation rule hold — a Redis outage degrades performance, never correctness or availability.
2. **`params` must be JSON-serializable** and is hashed into the cache key via a canonical (sorted-keys) JSON encoding — callers pass a plain `dict` of whatever distinguishes one response from another (filters, sort, page, etc.), not pre-hashed strings, so the hashing logic stays centralized.
3. **`loader` is only ever invoked on a cache miss** — `get_or_set` must not call it speculatively or more than once per miss.
4. **Versions are namespace-scoped**, never global — bumping `articles` must not affect `tag_groups` entries.

## Call sites in scope (who uses this contract)

**Reads** (`get_or_set`):
- `backend/services/article_service.py::get_articles_paginated` (namespace `articles`)
- `backend/services/graph_service.py` query functions (namespace `graph`)
- `backend/routers/tags.py::list_tag_groups` / `get_tag_group` (namespace `tag_groups`)
- `backend/services/weekly_report_service.py` read functions (namespace `weekly_reports`)

**Writes** (`bump_version`):
- `src/modules/collection/application/event_handlers/cache_invalidation_handler.py` (`CacheInvalidationHandler.handle(PipelineCompletedEvent)`) — bumps `articles` and `graph`
- weekly report job's existing per-report notification hook point — bumps `weekly_reports`
- `backend/routers/topics.py` create/update/delete — bumps `articles`, `graph`, `tag_groups`
- `backend/services/tag_service.py` write functions — bumps `articles`, `graph`, `tag_groups`
