# Research: Exception Handling Guideline & API Status Code Management

## 1. Shared exception category taxonomy — class design

**Decision**: Add four new classes directly under `DomainError` in `src/shared/domain/exceptions.py`, parallel to (not replacing) the existing per-bounded-context roots:

```python
class DomainError(Exception): ...

class NotFoundError(DomainError): ...
class ConflictError(DomainError): ...
class ExternalDependencyError(DomainError): ...
class UnauthorizedError(DomainError): ...
class ForbiddenError(DomainError): ...
```

Each bounded context subclasses the relevant shared category alongside its existing context root, e.g. `class TopicNotFoundError(NotFoundError, CollectionDomainError): ...` (multiple inheritance: category for the status-code mapping to key off via `isinstance`, context root for existing bounded-context-scoped catch blocks, if any, to keep working).

**Rationale**: FR-004a requires shared, reusable base categories so the FR-005 mapping can key off `isinstance(exc, NotFoundError)` once instead of enumerating every leaf class. Multiple inheritance preserves the existing per-context hierarchy (`CollectionDomainError`, `IntelligenceDomainError`) established by `016-db-schema-brushup` rather than replacing it, satisfying the spec's Assumption that the existing hierarchy is a stable foundation.

**Alternatives considered**:
- *Single flat category enum on `DomainError` (a `category` class attribute instead of subclassing)* — rejected: makes `isinstance`-based `except` blocks impossible for callers that want to catch "any not-found" within a specific bounded context; subclassing is the existing idiom in this codebase (`CollectionDomainError`, `IntelligenceDomainError` already use it).
- *Put the 4 shared categories under each bounded-context root independently (`CollectionNotFoundError(CollectionDomainError)`, no shared cross-context type)* — rejected: this is exactly the "type also varies" problem from the issue; the FR-005 mapping needs one shared ancestor per category so it doesn't need a per-bounded-context registration.

## 2. HTTP status code mapping mechanism

**Decision**: A single dict-based mapping `Dict[type[DomainError], int]` keyed by the shared category classes (`NotFoundError: 404, ConflictError: 409, UnauthorizedError: 401, ForbiddenError: 403, ExternalDependencyError: 502`), consulted via `isinstance` walk (most-specific-first) in one `@app.exception_handler(DomainError)` registered in `backend/main.py`. Any `DomainError` (or subclass) not matching a specific category falls back to 500 (FR-007). A second, separate `@app.exception_handler(Exception)` catches genuinely unexpected (non-`DomainError`) exceptions — third-party/library exceptions that reached the router boundary untranslated — and also returns 500, satisfying the Edge Case about untranslated library exceptions (treated as a guideline violation to fix over time, with this handler as the safety net, not the intended path).

**Rationale**: FastAPI's `add_exception_handler` dispatches on the *exact* exception type registered, not on subclasses, by default — but since `DomainError` is the single type registered and the handler itself does the `isinstance` walk internally, new leaf exception classes automatically get correct status codes with zero changes to `main.py` (only the shared-category mapping dict, one place, per FR-005's "developer wants it to produce a specific HTTP status... exactly one place to register" requirement).

**Alternatives considered**:
- *Register one `@app.exception_handler(X)` per leaf exception class* — rejected: reintroduces "every router/exception needs its own registration," the opposite of FR-005's single-mapping requirement, and doesn't scale as new leaf classes are added.
- *`400 (invalid domain input)` handled the same way as the other categories via a shared `ValidationError(DomainError)` category* — adopted as a fifth shared category (see data-model.md) for symmetry with FR-006, distinct from FastAPI/Pydantic's own 422 (see §5).

## 3. Error response body & request correlation

**Decision**: `{"error": {"code": "<CATEGORY_SCREAMING_SNAKE>", "message": "<human-readable>", "request_id": "<uuid>"}}`. The `request_id` is **not new infrastructure** — `RequestLoggingMiddleware` (`backend/middleware/logging.py:39`) already generates a `uuid.uuid4()` per request, binds it into `structlog.contextvars` for that request's log lines, and sets it as the `X-Request-ID` response header. The exception handler reads the same value (via `structlog.contextvars.get_contextvars()` or `request.state`) and echoes it into the JSON body too, so a user-visible error and its full server-side log trail share one identifier without adding a second ID scheme.

**Rationale**: Directly answers the accepted clarification (Session 2026-07-22, Q1) and reuses existing, already-tested middleware rather than inventing a parallel correlation mechanism.

**Alternatives considered**: Generating a fresh UUID inside the exception handler — rejected: would produce a *different* ID than the one already in that request's log lines, defeating the purpose of correlation.

## 4. Sentry reporting for the central handler (Constitution Principle VI)

**Decision**: `sentry_sdk.init(dsn=SENTRY_DSN)` is added to `backend/main.py` at module top level (mirroring the existing pattern in `src/entrypoints/cli/main.py:24-26`), gated on `SENTRY_DSN` being non-empty (no-op fallback, consistent with Constitution "Missing Sentry/Loki/OTel config MUST NOT crash the application"). `SENTRY_DSN` is read into `backend/config.py` (it already exists in `.env.example` but backend currently never reads it — confirmed gap). Inside the central exception handler, any exception mapped to 500/502/503 calls `sentry_sdk.capture_exception(exc)` explicitly before building the sanitized response body.

**Rationale**: Research confirmed `backend/` currently has **zero** Sentry integration (`grep sentry_sdk` matches only `src/entrypoints/cli/*.py`), despite Constitution Principle VI stating Sentry "MUST be active in production" and "unhandled exceptions MUST propagate to Sentry; silent swallowing is forbidden." Today, every bare `except Exception:`/`except Exception as e:` across `backend/routers/*.py` (12+ occurrences, e.g. `grafana.py`, `chat.py`, `auth.py`) already violates this — this feature's new central handler is the first place in `backend/` where fixing it is both in-scope and nearly free (one `sentry_sdk.init()` call + one `capture_exception()` call in the handler). Explicit `capture_exception()` is used rather than relying solely on Sentry's auto-instrumentation, because FastAPI's own exception-handler dispatch intercepts the exception before it would otherwise propagate as "unhandled" to Sentry's default hook.

**Alternatives considered**: Leaving backend Sentry wiring out of scope (pure exception-handling-guideline feature, not an observability feature) — rejected: the central handler is specifically the piece that decides what happens to a 500-class error, and shipping it without Sentry reporting would be introducing new code that violates an existing NON-NEGOTIABLE-adjacent constitution principle on day one.

## 5. FastAPI/Pydantic 422 vs. domain-validation 400

**Decision**: FastAPI's built-in request-shape validation (missing required field, wrong JSON type, fails Pydantic schema coercion) continues to produce its native 422 response, unchanged — this happens before a router function body (and therefore before any domain code) ever runs, so there is nothing for the new domain-exception hierarchy to intercept. A new shared `ValidationError(DomainError)` category (400) is for validation that can only be evaluated *inside* domain logic — business-rule validation such as a value object's invariant (e.g. `InvalidUrlHashError`, `InvalidSimilarityScoreError` — both already exist and already fit this category) that Pydantic's schema-level checks cannot express.

**Rationale**: Directly resolves the Edge Case in spec.md ("How are validation errors raised by FastAPI/Pydantic itself (422) distinguished from domain validation errors...") with a mechanical rule (before-router-body vs. inside-domain-logic) rather than a judgment call.

**Alternatives considered**: Converting all 422s to 400 by overriding FastAPI's `RequestValidationError` handler — rejected: 422 for malformed requests is standard REST/FastAPI convention consumers already expect from the framework; overriding it would be surprising and provides no benefit since it's a different failure class (malformed request vs. valid-request-but-violates-a-business-rule).

## 6. `backend/auth/guards.py` migration

**Decision**: The 6 existing `raise HTTPException(status_code=401/403, ...)` call sites in `backend/auth/guards.py` (lines 35, 38, 40, 42, 61, 64, 66) are replaced with `raise UnauthorizedError(...)` / `raise ForbiddenError(...)` from `src/shared/domain/exceptions.py`, letting the new central handler (§2) produce the response. `backend/auth/guards.py` already centralizes every 401/403 decision in a handful of `Depends()` functions, so this is a small, mechanical, low-risk change confirmed to touch exactly those 7 lines.

**Rationale**: Directly implements the accepted clarification (Session 2026-07-22, Q3): "exactly one error-handling path for the entire API rather than two parallel ones."

## 7. `ConflictError` — concrete precedent already in the codebase

**Decision**: `ConflictError` (409) formalizes a pattern that already exists informally: `backend/routers/auth.py:65-66,102-103` currently does `if "duplicate" in str(e).lower() or "unique" in str(e).lower(): raise HTTPException(409, ...)` — string-matching a caught `IntegrityError`'s message text. `backend/routers/tags.py:210-212` does the same via a bare `except IntegrityError:`. Both become `raise ConflictError(...)` at the point the domain/application layer detects the conflict (or a thin repository-layer translation of `IntegrityError` → `ConflictError`, per FR-003's infra→domain translation rule), removing the string-matching entirely.

**Rationale**: Concrete evidence that ConflictError is not speculative — it replaces a real, fragile pattern (matching on exception message text) with a typed exception, directly serving FR-002's "which exception types are permitted" and FR-003's "infrastructure-layer failures...translated into domain exceptions."

## 8. Frontend compatibility of the new error body shape

**Decision**: No frontend code change is required for this feature's HTTP-response-shape change to be non-breaking. `apiFetch()` (`frontend/lib/api/client.ts`) only branches on `response.status` (for the 401→sign-out case), never parses the body generically. Two call sites read `data?.detail` today (`frontend/app/settings/settings-page-content.tsx:158,178`), both with `?? <translated fallback>` — under the new shape `data.detail` is `undefined`, so both fall back to their existing translated generic message rather than throwing. This is a UX regression (loses the specific backend message), not a functional break.

**Rationale**: Confirms the spec's Assumption ("frontend...out of scope...except as passive consumer") is safe to rely on for the initial delivery. Documented here so the audit (FR-010) / tasks phase can decide whether updating these 2 call sites to read `error.message` is bundled into this feature or filed as a fast-follow — it is not a blocking dependency either way.

**Alternatives considered**: Keeping a duplicate top-level `detail` field alongside the new `error` object for backward compatibility — rejected: perpetuates exactly the inconsistent shape this feature exists to eliminate, for a two-call-site, non-crashing gap that's trivial to fix directly.

## 9. Guideline document location

**Decision**: `site/guide/architecture/exception-handling.md`, alongside the existing auto-generated `site/guide/architecture/db-schema.md` and `uml` pages (VitePress-rendered architecture docs), cross-referenced from `CLAUDE.md`'s "Key Conventions" section with a one-line pointer (matching how `CLAUDE.md` already points to `specs/016-db-schema-brushup/plan.md`-style deep dives elsewhere in this project's docs pattern).

**Rationale**: FR-013 requires a "durable, discoverable document." `site/guide/architecture/` is the existing home for hand-authored + auto-generated architecture reference material in this repo (per Constitution Principle VIII), making it the natural location for a new architecture-level convention doc, discoverable the same way `db-schema.md` already is. Must follow the VitePress-compatible Markdown constraint (Constitution Principle VII: no bare `<...>` outside code fences) since this file is rendered by `npm run build`.

**Alternatives considered**: Embedding the full guideline directly in `CLAUDE.md` — rejected: `CLAUDE.md` is scoped to concise, session-level AI-assistant guidance (per its own stated purpose) and already delegates deep architectural topics to `specs/*/plan.md` or `site/guide/`; a multi-section guideline with code examples belongs in the latter.
