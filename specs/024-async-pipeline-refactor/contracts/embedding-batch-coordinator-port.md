# Contract: `EmbeddingBatchCoordinator` (chatbot-plugin-sdk)

**File**: `chatbot_plugin_sdk/batching.py` (new)
**Consumer**: `IngestProcessor` (`chatbot_plugin_sdk/processors/ingest.py`) — owns exactly one coordinator per `configure()` call, routes `_embed_in_batches_dense()` through it instead of its own per-call sequential batching loop.
**Exported from**: `chatbot_plugin_sdk/__init__.py`, alongside `SlidingWindowStrategy`, `EndpointProvider` — usable directly by any consumer, not only through `IngestProcessor`.

Added for User Story 6 (research.md item 11) — see that item for the root-cause trace this fixes.

## Interface

```python
QueueFactory = Callable[[], "asyncio.Queue[EmbedWorkItem]"]

@dataclass
class EmbedWorkItem:
    text: str
    future: "asyncio.Future[list[float]]"

class EmbeddingBatchCoordinator:
    def __init__(
        self,
        dense: DenseEmbeddingProvider,
        embed_batch_size: int = 16,
        queue_factory: QueueFactory | None = None,
    ) -> None:
        """queue_factory defaults to a plain asyncio.Queue(), built lazily on first
        use — never at __init__ time (asyncio.Queue binds to the running event loop
        at construction; deferring the call until the first embed_many() guarantees
        it binds to the loop that's actually running, not whatever loop happened to
        be current at IngestProcessor.configure() time)."""

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Submit texts as individual work items to the shared queue, await their
        futures, return vectors in the same order as texts. Safe to call
        concurrently from multiple coroutines against the same coordinator
        instance — each call's items interleave with any other concurrent call's
        items in the one shared queue."""

    async def aclose(self) -> None:
        """Cancel the background worker task. Idempotent. Any work items already
        queued but not yet dispatched at the time of cancellation resolve their
        futures with a cancellation-derived exception, not silently dropped."""

    def get_queue(self) -> "asyncio.Queue[EmbedWorkItem] | None":
        """Return the current queue, or None if no work has been submitted yet
        and set_queue() was never called."""

    async def set_queue(self, queue: "asyncio.Queue[EmbedWorkItem]") -> None:
        """Replace the queue. Before any work has been submitted, just swaps the
        reference. While a worker is running, migrates every item still sitting
        in the current queue onto the new one, then stops and restarts the
        worker against it — items the worker had already claimed and was
        mid-embed() on are cancelled along with the worker, not migrated."""
```

`IngestProcessor` exposes the same pair as thin passthroughs — `get_embed_queue()` (returns None if dense isn't configured) and `async set_embed_queue(queue)` (raises `NotConfiguredError` if dense isn't configured), both delegating to the `EmbeddingBatchCoordinator` instance it owns.

## Behavioral guarantees

- **One background worker task per coordinator instance, started lazily** on the first `embed_many()` call — not at `__init__`. Default worker count is **1**: the underlying rate limit (`dense`'s own `SlidingWindowStrategy`/equivalent) is a single shared resource regardless of worker count, so more than one worker would still serialize on it — a single worker avoids the wasted, uncoordinated collisions this contract exists to prevent, rather than merely reducing their frequency.
- **Batch composition may mix items from multiple concurrent `embed_many()` calls.** The worker drains up to `embed_batch_size` items from the queue (whatever is available, blocking only if the queue is currently empty) and issues exactly one `dense.embed(texts)` call per batch — callers have no control over, and must not assume anything about, which other calls' items land in the same physical batch as their own.
- **A batch may be smaller than `embed_batch_size` even when the queue has more items immediately available, when `dense` exposes rate-limit headroom.** (Follow-up, research.md item 11 — production RPM 429s traced to fixed-size batches leaving near-zero headroom in the shared limiter's window.) If `dense.rate_limit` is set and that object has a `headroom()` method (`SlidingWindowStrategy` does), the worker peeks the currently-available RPM/TPM window before growing the batch and stops adding items once the next one would exceed either — the excess item is held (not requeued — order-preserving) to start the *next* batch. The very first item of any batch is never gated this way (a batch is never left empty on this account) — `dense.embed()`'s own `acquire()` call remains the authoritative blocking gate either way; this only shrinks how far a batch can already be run "at the edge" before that gate is even reached. Falls back to the original count-only draining described above when `dense` has no `rate_limit`, or that `rate_limit` has no `headroom()`.
- **Batch-level failure is item-level failure.** If `dense.embed(texts)` raises for a batch, every `EmbedWorkItem` in that batch has its `future` resolved with that same exception — including items originally submitted by a different `embed_many()` call than the one whose caller is currently awaiting. This is the same effective failure granularity `IngestProcessor.ingest()` already has today (one article's ingestion fails outright on an embedding error); the only change is that "which requests shared a batch" is no longer guaranteed to be one caller's own chunks.
- **A returned vector count that doesn't match the batch's text count is itself treated as a batch failure** (raises `chatbot_plugin_sdk.exceptions.EmbeddingError`, resolved onto every item in that batch) — found during implementation: `zip(batch, vectors)` would otherwise silently drop the extra items when a provider returns fewer vectors than requested, leaving their futures unresolved forever and hanging every caller whose chunks landed in that batch (see `test_batching.py::test_vector_count_mismatch_fails_every_item_instead_of_hanging`). This makes `IngestProcessor.ingest()`'s own post-hoc `len(dense_vectors) != len(chunks)` check unreachable for a single-batch mismatch on the dense path (kept as a defensive backstop, not removed) — the sparse path (`_embed_in_batches_sparse()`, untouched) can still reach it.
- **`queue_factory` is a pure dependency-inversion seam** — the coordinator only ever calls the standard `asyncio.Queue` interface (`put`, `get`, `get_nowait`) on whatever the factory returns. A caller may pass a factory returning a subclass (e.g. a priority queue, or one that emits tracing events on `put`/`get`) with zero coordinator-side changes. Not specifying `queue_factory` produces a plain FIFO `asyncio.Queue()`.
- **`aclose()` MUST be called once the owning `IngestProcessor` (or direct coordinator user) is done for the run** — the worker task is an infinite loop (`while True: await self._queue.get()`) with no other termination condition. Not calling it leaks a running task for the lifetime of the process/event loop.
- **`set_queue()` migrates only items still sitting in the queue — not the batch the worker is actively `embed()`-ing when the swap happens.** The worker tracks its current in-flight batch specifically so cancelling it (both for `set_queue()`'s restart and for `aclose()`'s shutdown) explicitly cancels that batch's futures rather than leaving them permanently unresolved — found during implementation: the original code only drained the queue on cancellation, not the in-flight batch, which left a caller's `embed_many()` hanging forever instead of raising `CancelledError`. Callers should call `set_queue()` between runs, not while `embed_many()` calls are still in flight, to avoid losing that in-flight work.
- **`get_queue()`/`set_queue()` exist for observability and test seams, not as a general runtime-reconfiguration API** — e.g. inspecting `queue.qsize()` for backlog monitoring, or a test swapping in an instrumented queue mid-scenario. There is no current production call site that swaps the queue after `configure()`.
- **Single-caller behavior is unchanged from before this coordinator existed**: a consumer that never has two `embed_many()`/`ingest()` calls in flight at once observes the same effective batching (sequential, `embed_batch_size`-sized calls to `dense.embed()`, *when `dense` has no rate-limit headroom to consult* — see the headroom bullet above for the case where it does) as `IngestProcessor`'s previous inline loop — the coordinator adds one queue/future hop, not a behavior change, for that case.

## Non-goals

- No cross-process coordination — the coordinator's queue and worker are in-process, in-event-loop constructs (`asyncio.Queue`/`asyncio.Task`), matching this feature's existing single-process/single-event-loop constraint (plan.md Technical Context Constraints). `SlidingWindowStrategy`'s RPM/TPM/RPD state is likewise per-process — `backfill_rag.py` and `main.py` each track it independently despite drawing on the same real upstream quota (research.md item 11's "Quota sharing with main.py" note). Deferred, not implemented: see research.md item 11's "Explicitly deferred: cross-process shared RateLimiter" follow-up.
- No priority/fairness policy between concurrent callers' chunks — plain FIFO drain by default; a caller wanting different ordering supplies its own `queue_factory`.
- Does not touch `_embed_in_batches_sparse()` — sparse embedding providers in this codebase have no configured rate limit (`RAG_SPARSE_RPM` unset), so there is no observed contention to coordinate; sparse keeps `IngestProcessor`'s original per-call sequential loop.
