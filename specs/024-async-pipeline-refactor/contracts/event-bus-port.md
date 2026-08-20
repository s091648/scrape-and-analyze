# Contract: `EventBus` Port

**File**: `src/shared/application/ports/event_bus.py`
**Implementers**: `AsyncInMemoryEventBus` (this feature); future — any durable/cross-process backend (e.g. Redis Streams), not built in this feature.
**Consumers**: `src/bootstrap.py` (wiring), every application-layer event handler.

## Interface

```python
class EventBus(Protocol):
    async def subscribe(self, event_type: Type[Any], handler: Callable[[Any], Awaitable[None]]) -> None: ...
    async def publish(self, event: Any) -> bool: ...
```

## Behavioral guarantees

- **`subscribe`**: Registers `handler` to be invoked for every future `publish()` call whose event's type is exactly `event_type` (no inheritance-based matching — unchanged from today).
- **Handler ordering within one `publish()` call is preserved as strictly sequential, in `subscribe()`-call order — this is a correctness requirement, not just a nicety.** Today's `InMemoryEventBus` already dispatches sequentially, and at least one existing subscriber pair depends on it for correctness, not just presentation: `CacheWarmupHandler` is subscribed to `PipelineCompletedEvent` strictly after `CacheInvalidationHandler` (`bootstrap.py:443-448`) specifically because warming must write into the *new* cache-namespace version that invalidation just bumped to — if the two ran concurrently, warmup could race invalidation and populate the namespace about to be orphaned. (A second, weaker reason for the same ordering — the admin monitoring waterfall rendering handlers as distinct, non-overlapping bars, `bootstrap.py:420-426` — is presentation-only and would degrade gracefully, but is not the reason this guarantee exists.) Therefore: `publish(event)` MUST `await` each handler for `type(event)` one at a time, in the order they were `subscribe()`-d — never `asyncio.gather` across sibling handlers of the same event. This is the one place in the whole feature where async does **not** introduce new concurrency; it is a deliberate, preserved constraint.
- **Where the real concurrency comes from**: multiple `publish()` *calls* for *different* events (most importantly, different articles' `ArticleScrapedEvent`, each on its own `asyncio.Task` per data-model.md) run concurrently with each other. Concurrency is between independent `publish()` calls, never between sibling handlers of the same call.
- **`publish`**: Returns `True` if at least one handler ran (matches today's semantics — `False` only when there are zero subscribers for that event type, logged as `event_no_handlers`). A handler raising does not prevent the remaining handlers in its sequence from still being awaited — mirror today's `InMemoryEventBus.publish()`'s try/except-per-handler behavior, now `async`.
- **Concurrency safety of the bus itself**: the handler registry is built once at wiring time (`bootstrap.py`) and is read-only for the remainder of the run, so no additional synchronization is needed in the bus implementation to support many concurrent `publish()` calls for different event instances.
- **Delivery semantics**: In-process, at-most-once, no persistence, no replay — unchanged from today's `InMemoryEventBus`. A future durable implementation may offer stronger delivery guarantees (at-least-once via consumer groups) without this Protocol needing to change, but callers of this Protocol MUST NOT assume any guarantee beyond what's stated here (no code should depend on redelivery, for instance).

## Non-goals

- No dead-letter handling, no retry policy, no backpressure/queue-depth limiting at the port level — none of these exist today and none are introduced by this feature. A future durable implementation may add them internally without a Protocol change.
