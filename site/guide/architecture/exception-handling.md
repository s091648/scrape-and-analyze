---
title: Exception Handling Guideline
aside: false
---

# Exception Handling Guideline

How `src/`, `models/`, and `backend/` are expected to raise, propagate, and translate exceptions into HTTP responses. This is a hand-written convention document — it complements the auto-generated [Exceptions](./exceptions) catalog (which lists every exception class and `raise` site found by static analysis) rather than duplicating it.

## 1. Raise vs. return

Raise a `DomainError` subclass for an **expected, recoverable** failure — one the caller (a use case, a router, an API consumer) can act on: bad input, a missing resource, a state conflict, missing/invalid authorization, an exhausted external dependency.

Do **not** invent a `DomainError` subclass for a violated invariant that indicates a bug ("should never happen"). Let it propagate as whatever naturally occurs (an `AssertionError`, a `KeyError`, etc.). It should surface as an unmapped 500 and reach Sentry — polishing it into a typed, user-facing error would hide a real defect behind a normal-looking response.

Returning `None` / an empty collection remains appropriate for "absence is a normal outcome, not a failure" — e.g. `ResilientLLMService`/`ResilientMetricsService` returning `None` when every provider in a fallback chain is exhausted (see §5) is a deliberate design, not something this guideline asks you to change.

## 2. Which exception type

Every domain exception belongs to the hierarchy rooted at `DomainError` (`shared/domain/exceptions.py`):

```
DomainError
├── ValidationError            # 400 — a business-rule invariant was violated
├── NotFoundError               # 404 — a requested resource does not exist
├── ConflictError                # 409 — conflicts with existing state (e.g. a uniqueness violation)
├── UnauthorizedError           # 401 — missing/invalid/expired authentication
├── ForbiddenError                # 403 — authenticated but not authorized
├── ExternalDependencyError    # 502 — a required external dependency failed/was exhausted
├── CollectionDomainError       # per-bounded-context root (existing)
│   └── ...leaf classes, each multiply-inheriting one shared category above
└── IntelligenceDomainError     # per-bounded-context root (existing)
    └── ...leaf classes, each multiply-inheriting one shared category above
```

A new leaf exception multiply-inherits **exactly one** shared category (for the status-code mapping to key off) and its bounded context's root (for any existing context-scoped `except` blocks):

```python
class TopicNotFoundError(NotFoundError, CollectionDomainError):
    """Raised when a Topic id does not resolve to an existing row."""
```

Built-in exceptions (`ValueError`, etc.) remain acceptable only for the unrecoverable/programmer-error case from §1 — never for anything that should produce a specific non-500 HTTP status.

`backend/` routers that don't have a natural DDD home for a new leaf class (most of `backend/`'s CRUD routers query the ORM directly, with no separate use-case layer) may raise the shared category class directly, e.g. `raise NotFoundError("Topic not found")` — a new leaf subclass is not mandatory when there's nothing bounded-context-specific to attach to it.

## 3. Propagation across layers

- **Domain layer**: raises `DomainError` subclasses directly.
- **Application layer** (use cases): lets domain exceptions propagate unchanged. It does not catch-and-rewrap a `DomainError` it didn't originate.
- **Infrastructure layer** (DB, HTTP clients, external APIs): catches library-specific exceptions (`sqlalchemy.exc.IntegrityError`, `httpx.HTTPError`, etc.) and re-raises as the matching `DomainError` subclass *before* the exception crosses into the application layer. Application-layer code should never need to import `sqlalchemy.exc` or similar to handle a failure.
- **API boundary** (`backend/`): never hand-picks an HTTP status code per endpoint. A single central exception handler (`backend/exceptions/handlers.py`, registered in `backend/main.py`) converts any `DomainError` to the correct status + body automatically. Router code just raises; it doesn't construct `HTTPException`.

## 4. The 400 vs. 422 line

FastAPI's own request-shape validation (missing required field, wrong JSON type, fails Pydantic coercion at the route signature) keeps producing its native 422 response, unchanged — this happens before any router or domain code runs, so there's nothing for `DomainError` to intercept.

`ValidationError` (400) is for validation that can only be evaluated *inside* domain logic — a business-rule invariant that Pydantic's schema-level checks can't express (e.g. "email or username required" when both individually are optional, or a value object's own invariant like `InvalidUrlHashError`). If you're manually constructing a Pydantic model deep inside a route body's `try`/`except` (not via the route's own parameter typing) and catching its `ValidationError`, that's still a domain-layer concern — translate it to `shared.domain.exceptions.ValidationError`, not a hand-rolled 422.

## 5. External-dependency failures

`ResilientLLMService` and `ResilientMetricsService` walk an ordered provider fallback chain and return `None` when every provider is exhausted — a deliberate, already-tested resilience mechanism. This guideline does not ask you to change that contract.

If a call site treats that `None` as an unrecoverable failure requiring an error response, translate it into `ExternalDependencyError` at that call site (not inside the resilient service). For a request that hasn't started streaming yet, this flows through the central handler → 502. For a response where streaming has already started (e.g. Server-Sent Events, HTTP status already committed as 200), signal the failure in-band using the same `error.code`/`error.message` vocabulary as the [Error Response contract](/specs/017-exception-handling-guideline/contracts/error-response) instead of a status code — see `backend/routers/chat.py`'s `generate()` for the reference implementation.

## 6. The response shape

Every non-2xx response from `backend/` uses one shape:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Topic 3fae... was not found",
    "request_id": "b6b2b6b2-....-...."
  }
}
```

`request_id` is not a new mechanism — it's the same UUID `RequestLoggingMiddleware` already generates per request and sets as the `X-Request-ID` header; the handler reads it back from the request's structlog context rather than minting a second ID. For 500/502 responses, `error.message` is always a fixed, generic string per category — never the exception's own text, a stack trace, a file path, or raw SQL — while the real detail still goes to the structured log line and to Sentry (`sentry_sdk.capture_exception`).

See `specs/017-exception-handling-guideline/data-model.md` for the full category → status code table and `router-audit.md` for how every existing `backend/routers/` endpoint was brought in line with this guideline.
