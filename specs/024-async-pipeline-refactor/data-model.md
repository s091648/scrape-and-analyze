# Phase 1 Data Model: Async Event-Driven Collection Pipeline

This feature introduces no new persisted database tables or columns (no Alembic migration — see plan.md's Constitution Check, Principle V). "Data model" here means the runtime/domain constructs the spec's Key Entities map onto, plus the port (interface) shapes that carry them. Concrete Python signatures below are illustrative of the contract, not a final implementation — exact naming is a `/speckit-tasks`/implementation decision.

## Pipeline Run

Tracks one execution of `CollectionPipeline.run()`. Where today's implementation has one implicit "finished" state (the point at which `PipelineCompletedEvent` is published), this feature splits it into two explicit, sequential barrier states.

| Field | Type | Notes |
|---|---|---|
| `started_at` | `datetime` | Unchanged from today. |
| `text_complete_at` | `datetime \| None` | New. Set once Barrier 1 (research.md item 6) resolves — every `Article Processing Unit of Work`'s text stage has settled. |
| `fully_complete_at` | `datetime \| None` | New. Set once Barrier 2 resolves — every RAG task has also settled. |
| `pipeline_stats` | `PipelineStats` | Unchanged (`src/modules/collection/application/use_cases/pipeline_stats.py`) — already thread/task-safe (internal `threading.Lock`; remains correct under `asyncio` since a lock held only across non-`await`ing critical sections never actually contends). |
| `rate_limited_llm_providers` | `tuple[str, ...]` | Unchanged shape; now must reflect providers exhausted across concurrent model-pool dispatch (FR-012), not just a single active provider. |

**State transitions**: `started` → (Barrier 1 resolves) → `text_complete` → (Barrier 2 resolves) → `fully_complete`. No other states or transitions — a run does not partially retry; per-article failures are captured at the `Article Processing Unit of Work` level and reported, never retried within the same run (Clarifications, FR-004).

**Events replacing/extending `PipelineCompletedEvent`**: Two events instead of one, per FR-004/FR-005/FR-006:
- `TextPipelineCompletedEvent` (new) — fired when `text_complete_at` is set. Subscribers: `SearchIndexRebuildHandler`, `CacheInvalidationHandler`, `CacheWarmupHandler` (moved off `PipelineCompletedEvent`).
- `PipelineCompletedEvent` (existing, semantics unchanged — still "everything, including RAG") — fired when `fully_complete_at` is set. Subscribers: `OtelMetricsHandler`, the Telegram `notification_handler` (stay where they are).

Both event classes keep the existing UML-convention name suffix (`...Event`; constitution Principle VIII) so `generate_uml.py` classifies them without changes.

## Article Processing Unit of Work

The scrape-save→analyze→translate(→RAG-ingestion as a detached child, research.md item 5) chain for one discovered article. Concretely, one `asyncio.Task` created per article by `CollectionPipeline.run()` once the batched fetch+dedup phase (unchanged, FR-003) has produced the run's article list.

| Aspect | Shape |
|---|---|
| Identity | The article's `UrlHash` (unchanged — existing dedup identity, not a new concept). |
| Session | Its own fresh `AsyncSession`, opened at task start, closed at task end (research.md item 2). Never shared with another task. |
| Outcome | Settles to either a normal return (success) or a raised exception (permanent failure) — collected by `asyncio.gather(..., return_exceptions=True)` at Barrier 1. A failed unit of work still records a `FailedTask` via the existing `FailedTaskPersistenceHandler` path (unchanged handler, now invoked from within a concurrently-running task rather than the single synchronous call stack). |
| RAG relationship | On reaching the point that triggers RAG today (`ArticleProcessedEvent`), spawns a detached `asyncio.Task` for RAG ingestion (research.md item 5) and returns from *its own* text-stage work without awaiting it. The RAG task is independently tracked for Barrier 2 — it is not part of this unit of work's own settlement for Barrier 1 purposes. |

**Invariant (FR-007, FR-013)**: No two concurrently-running units of work may share a session, a repository instance holding a session, or any other mutable per-request state. Shared state they *do* legitimately read/write concurrently (the model capacity pool, `PipelineStats`) must be safe for that by construction (research.md item 7's no-`await`-critical-section invariant; `PipelineStats`'s existing lock).

## Model Capacity Pool

**New** `AsyncResilientLLMService`/`AsyncResilientEmbeddingService` classes (`src/infrastructure/intelligence/llm/resilient_llm_service.py`, new siblings alongside — not replacing — the existing sync `ResilientLLMService`/`ResilientEmbeddingService`). Necessary because those sync classes, and the `build_llm_service()` function that constructs them, are shared with the out-of-scope `build_weekly_pipeline()` and `build_translation_pipeline()` (research.md item 3) — converting them in place was rejected for the same reason the repository conversion was.

| Field | Type | Notes |
|---|---|---|
| `_handlers` | `list[ProviderHandler]` (or an async-flavored equivalent wrapping the same `provider`/`strategy`/`priority`/`name` shape) | Loaded via a new `build_async_llm_service()` from the same `llm_providers` DB table rows as the sync path (`shared/llm_provider.py::load_active_providers`/`load_active_embedding_providers` — read-only, reused as-is, no schema change; the table already supports multiple rows per `name` with distinct `model`/`priority`, unique constraint is on `model` and `(priority, type)`, not `name`). Distinct `ProviderHandler` *instances* from the sync path's — see `_rate_limit_tracker` note below on why that's fine. |
| `_selector` | `ProviderSelector` (new) | Strategy object, same shape as `QueueSelector` (`src/infrastructure/collection/executor/queue_selector.py`): `select(handlers: list[ProviderHandler]) -> list[int]`, returning capacity-filtered candidate indices in preference order. Default implementation: priority order, filtered by `has_capacity()`. |
| `_rate_limit_tracker` | `RateLimitedProviderTracker` | Its own fresh instance, independent of the sync path's. Not a new risk: each pipeline (`build_collection_pipeline()`, `build_weekly_pipeline()`, `build_translation_pipeline()`) already runs as a separate OS process with its own fresh, zeroed rate-limiter state today — this feature doesn't add cross-process quota coordination, it just doesn't remove the (pre-existing, unrelated to this feature) absence of it either. |

`SlidingWindowStrategy` (`.../rate_limit/sliding_window_strategy.py`) gains one new method alongside its existing ones:

```python
def has_capacity(self, estimated_tokens: int) -> bool:
    """Non-blocking: True if a request could be recorded right now without waiting."""
```

`acquire()` (existing, blocking) is unchanged and remains the fallback path when `has_capacity()` is `False` for every handler in the pool (FR-011).

**Two independent pools, not one** (Clarifications-adjacent, matches spec.md's Key Entities): `ResilientLLMService` (analysis + translation share this pool — FR-009) and `ResilientEmbeddingService` (separate pool) each get their own `ProviderSelector` instance. RAG's own dense/sparse embedding providers (configured via env vars, not the `llm_providers` table) are a third, already-independent pool this feature does not touch (per the original scoping discussion — RAG's rate limiting was already independent before this feature).

## Stage Handoff Interface

`EventBus` Protocol (`src/shared/application/ports/event_bus.py`), modified in place (it is already the seam every call site uses, per constitution Principle I):

```python
class EventBus(Protocol):
    async def subscribe(self, event_type: Type[Any], handler: Callable[[Any], Awaitable[None]]) -> None: ...
    async def publish(self, event: Any) -> bool:
        """Await every handler subscribed to type(event); return True if any handler ran."""
```

Concrete implementation: `AsyncInMemoryEventBus` (new, replaces `InMemoryEventBus` at the call sites this feature touches — `src/infrastructure/shared/events/`). Same `defaultdict(list)` handler registry shape as today; `publish()` becomes `for handler in handlers: await handler(event)` — sequential, in subscription order, **not** `asyncio.gather` (see contracts/event-bus-port.md — at least one existing handler pair, `CacheInvalidationHandler` → `CacheWarmupHandler` on `PipelineCompletedEvent`, depends on strict ordering for correctness, not just presentation).

**Extensibility note** (User Story 5 / FR-008, deferred implementation): a future `RedisStreamsEventBus` would implement the same `Protocol` — `publish()` would `XADD` and await acknowledgement, `subscribe()` would register a consumer-group handler loop — with zero change required to any stage's handler code, since handlers only ever see the `EventBus` Protocol, never a concrete class. Not built in this feature; the Protocol shape above is deliberately unchanged from what a Redis-backed implementation would need to satisfy.

## Async Repository Ports (new, alongside existing sync ones)

New domain-layer Protocols in `src/modules/*/domain/repositories/`, one per repository listed in research.md item 3, each mirroring its existing sync Protocol's method set but with `async def` signatures returning the same domain entities/value objects (unchanged — `Article`, `Analysis`, `Tag`, etc. stay plain `@dataclass`, no Pydantic, per constitution Principle I). Example shape (illustrative):

```python
class AsyncArticleRepository(Protocol):
    async def save(self, article: Article) -> None: ...
    # find_analyzed_url_hashes intentionally NOT duplicated here — that
    # method is only ever called from the still-synchronous batched
    # fetch/dedup phase (FR-003), which keeps using the existing sync
    # ArticleRepository/SqlAlchemyArticleRepository unchanged.
```

Concrete implementations: `AsyncSqlAlchemy<Name>Repository` classes in `src/infrastructure/persistence/{shared,collection,intelligence}/`, filenames ending in `_async_repo_impl.py` (parallel to the existing `_repo_impl.py` convention so `generate_uml.py`'s filename-suffix classification, constitution Principle VIII, can be extended to recognize both suffixes — a one-line change to that script, tracked as a task, not a design change here).

Each async repository is constructed per-`Article Processing Unit of Work` task, taking that task's own `AsyncSession` — never shared, never constructed once and reused across tasks (research.md item 2's invariant applies here directly: a repository instance is only as safe for concurrent use as the session it holds).
