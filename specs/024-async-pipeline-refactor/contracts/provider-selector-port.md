# Contract: `ProviderSelector` Port

**File**: `src/infrastructure/intelligence/llm/rate_limit/provider_selector.py` (new)
**Mirrors**: `QueueSelector` (`src/infrastructure/collection/executor/queue_selector.py`) — same shape, applied to LLM/embedding provider dispatch instead of host queues.
**Consumers**: `AsyncResilientLLMService`, `AsyncResilientEmbeddingService` (each holds its own selector instance — two independent pools, see data-model.md). These are **new** classes, siblings to the existing sync `ResilientLLMService`/`ResilientEmbeddingService` — not the same classes modified in place (research.md item 3: those sync classes are shared with the out-of-scope weekly-report and translation jobs via `build_llm_service()`). The sync classes and their existing blocking `acquire()`-only dispatch are untouched by this feature.

## Interface

```python
class ProviderSelector(ABC):
    @abstractmethod
    def select(self, handlers: list[ProviderHandler], estimated_tokens: int = 0) -> list[int]:
        """Return indices of currently-available handlers, in preferred dispatch order, for a
        request estimated at estimated_tokens (the same estimate the caller will use for
        reservation). Returns [] if none are currently available (caller falls back to blocking
        acquire())."""
```

```python
class PriorityFirstProviderSelector(ProviderSelector):
    """Default. Preserves today's priority ordering among handlers that currently
    have capacity — does not change *which* model is preferred, only skips ones
    that are momentarily unavailable instead of blocking on them (FR-010)."""
```

## Behavioral guarantees

- **`select` MUST be side-effect-free** — it only inspects `has_capacity(estimated_tokens)` on each handler's `SlidingWindowStrategy` (research.md item 7 / `sliding_window_strategy.py`'s new non-blocking method), called with the same token estimate the caller will use for reservation, and returns an ordering; it does not itself reserve capacity. Reservation happens in the caller's own check-and-record step (see below).
- **Caller contract** (`AsyncResilientLLMService.analyze`/`translate`/`generate`, `AsyncResilientEmbeddingService.embed`/`embed_batch`): iterate `selector.select(handlers, estimated_tokens)` in order and use the first candidate, whose own `strategy.try_acquire(estimated_tokens)` performs the actual re-check-and-reserve — **synchronously, on the event loop thread, with no `await` in between** — so it's atomic with respect to every other concurrently-gathered task (nothing else runs until this coroutine hits a real `await`). Only when `try_acquire()` returns `False` (capacity genuinely isn't free right now) does the caller fall back to `asyncio.to_thread(strategy.acquire, estimated_tokens)`, which blocks on a worker thread since `SlidingWindowStrategy.acquire()` sleeps synchronously. An earlier version of this design always went through the thread-offloaded `acquire()`, even when capacity was free — that introduced a real race (the previous task's reservation landing on a worker thread after the next task's `select()` snapshot had already run, so both could pick the same handler); `try_acquire()` closes it by keeping the common case fully synchronous. If `select()` returns `[]`, the fallback list (every remaining handler in priority order) still goes through `try_acquire()` then `acquire()` the same way — matching FR-011's "wait rather than fail" requirement.
- **A model is excluded from `select()`'s results only when it is currently rate-limited (RPM/TPM window full) or has hit its daily cap (`RateLimitExhausted`, unchanged existing behavior)** — never for any other reason. `select()` MUST NOT reorder or exclude handlers based on anything other than current capacity and the configured `priority` (FR-010: momentary per-minute throttling must not be conflated with daily exhaustion).
- **Swappability**: A future alternative implementation (e.g. a round-robin selector, mirroring `RoundRobinQueueSelector`) satisfies this same Protocol with no change to `ResilientLLMService`/`ResilientEmbeddingService` — this is the reason the strategy is a separate object rather than inline logic, mirroring why `QueueSelector` is already factored out for `ScrapeExecutor`.

## Non-goals

- No cross-pool coordination — the LLM pool (`ResilientLLMService`) and the embedding pool (`ResilientEmbeddingService`) each have their own selector instance and never consult each other's capacity state. RAG's own dense/sparse embedding providers are a third, entirely separate pool this feature does not touch.
- No persistence of selection history/fairness weighting across runs — `select()` is a pure function of the handlers' current in-memory capacity state, recomputed fresh on every call (research.md item 7's rationale for rejecting a heap applies equally here: no stale state to keep consistent).
