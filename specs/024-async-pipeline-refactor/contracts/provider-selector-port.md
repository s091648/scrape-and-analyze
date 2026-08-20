# Contract: `ProviderSelector` Port

**File**: `src/infrastructure/intelligence/llm/rate_limit/provider_selector.py` (new)
**Mirrors**: `QueueSelector` (`src/infrastructure/collection/executor/queue_selector.py`) — same shape, applied to LLM/embedding provider dispatch instead of host queues.
**Consumers**: `AsyncResilientLLMService`, `AsyncResilientEmbeddingService` (each holds its own selector instance — two independent pools, see data-model.md). These are **new** classes, siblings to the existing sync `ResilientLLMService`/`ResilientEmbeddingService` — not the same classes modified in place (research.md item 3: those sync classes are shared with the out-of-scope weekly-report and translation jobs via `build_llm_service()`). The sync classes and their existing blocking `acquire()`-only dispatch are untouched by this feature.

## Interface

```python
class ProviderSelector(ABC):
    @abstractmethod
    def select(self, handlers: list[ProviderHandler]) -> list[int]:
        """Return indices of currently-available handlers, in preferred dispatch order.
        Returns [] if none are currently available (caller falls back to blocking acquire())."""
```

```python
class PriorityFirstProviderSelector(ProviderSelector):
    """Default. Preserves today's priority ordering among handlers that currently
    have capacity — does not change *which* model is preferred, only skips ones
    that are momentarily unavailable instead of blocking on them (FR-010)."""
```

## Behavioral guarantees

- **`select` MUST be side-effect-free** — it only inspects `has_capacity()` on each handler's `SlidingWindowStrategy` (research.md item 7 / `sliding_window_strategy.py`'s new non-blocking method) and returns an ordering; it does not itself reserve capacity. Reservation happens in the caller's own check-and-record step (see below).
- **Caller contract** (`ResilientLLMService.analyze`/`translate`/`generate`, `ResilientEmbeddingService.embed`/`embed_batch`): iterate `selector.select(handlers)` in order; for each candidate index, re-check `has_capacity()` and, if still available, record the reservation (`update_batch_size`/window insert) — **with no `await` between the re-check and the record** — and use that handler. This re-check-then-reserve step, not `select()` itself, is what must stay atomic (research.md item 7). If `select()` returns `[]`, or every candidate's re-check fails (lost a race to another concurrent caller since `select()` ran), fall back to the existing blocking `acquire()` on the highest-priority handler — matching FR-011's "wait rather than fail" requirement.
- **A model is excluded from `select()`'s results only when it is currently rate-limited (RPM/TPM window full) or has hit its daily cap (`RateLimitExhausted`, unchanged existing behavior)** — never for any other reason. `select()` MUST NOT reorder or exclude handlers based on anything other than current capacity and the configured `priority` (FR-010: momentary per-minute throttling must not be conflated with daily exhaustion).
- **Swappability**: A future alternative implementation (e.g. a round-robin selector, mirroring `RoundRobinQueueSelector`) satisfies this same Protocol with no change to `ResilientLLMService`/`ResilientEmbeddingService` — this is the reason the strategy is a separate object rather than inline logic, mirroring why `QueueSelector` is already factored out for `ScrapeExecutor`.

## Non-goals

- No cross-pool coordination — the LLM pool (`ResilientLLMService`) and the embedding pool (`ResilientEmbeddingService`) each have their own selector instance and never consult each other's capacity state. RAG's own dense/sparse embedding providers are a third, entirely separate pool this feature does not touch.
- No persistence of selection history/fairness weighting across runs — `select()` is a pure function of the handlers' current in-memory capacity state, recomputed fresh on every call (research.md item 7's rationale for rejecting a heap applies equally here: no stale state to keep consistent).
