# Data Model: Exception Handling Guideline & API Status Code Management

No database schema changes. The "entities" here are code-level types (exception classes, a mapping table, a response schema) rather than persisted data.

## 1. Domain Exception Hierarchy (extended)

```
Exception (stdlib)
└── DomainError                              # src/shared/domain/exceptions.py (existing, unchanged)
    ├── ValidationError                      # NEW — shared category, 400
    ├── NotFoundError                        # NEW — shared category, 404
    ├── ConflictError                        # NEW — shared category, 409
    ├── UnauthorizedError                    # NEW — shared category, 401
    ├── ForbiddenError                       # NEW — shared category, 403
    ├── ExternalDependencyError              # NEW — shared category, 502
    ├── CollectionDomainError                # existing, unchanged
    │   ├── InvalidUrlHashError                        # existing — becomes ValidationError too
    │   ├── InvalidScraperKeywordTypeError             # existing — becomes ValidationError too
    │   ├── UnsupportedSourceTypeError                 # existing — becomes ValidationError too
    │   ├── InvalidScraperIntervalError                # existing — becomes ValidationError too
    │   └── ...new leaf classes as the FR-010 audit finds gaps (e.g. TopicNotFoundError,
    │        ScraperKeywordConflictError) — each multiply-inherits its context root AND
    │        the relevant shared category
    └── IntelligenceDomainError               # existing, unchanged
        ├── InvalidSuggestionStatusError                # existing — becomes ValidationError too
        ├── InvalidSimilarityScoreError                 # existing — becomes ValidationError too
        ├── InvalidWeeklyReportStatusError               # existing — becomes ValidationError too
        └── ...new leaf classes as needed (multiple inheritance, as above)
```

**Rules** (from spec FR-002, FR-004, FR-004a):

- Every exception raised by domain/application/infrastructure code for an *expected, recoverable* failure MUST be a `DomainError` subclass.
- Every such exception MUST multiply-inherit exactly one shared category (for status-code mapping) and its bounded-context root (for existing/future context-scoped catches). A leaf class with no shared category is a guideline violation (falls through to the 500 default, per FR-007, which is very likely wrong for an expected error).
- Built-in exceptions (`ValueError`, etc.) remain acceptable only for genuinely unrecoverable/programmer-error conditions (FR-011) — never for anything that should produce a specific non-500 HTTP status.

## 2. Exception → HTTP Status Mapping

| Shared category | HTTP Status | Example trigger |
|---|---|---|
| `ValidationError` | 400 | A domain invariant is violated inside business logic (not caught by Pydantic's request-schema validation, which stays 422 — see research.md §5) |
| `UnauthorizedError` | 401 | Missing/invalid/expired auth token (`backend/auth/guards.py`) |
| `ForbiddenError` | 403 | Valid token, insufficient role (`backend/auth/guards.py`'s `require_admin`) |
| `NotFoundError` | 404 | Requested resource (article/topic/keyword/etc.) does not exist |
| `ConflictError` | 409 | Uniqueness violation (duplicate name/email), state conflict (replaces string-matching in `auth.py`/`tags.py` — research.md §7) |
| `ExternalDependencyError` | 502 | A call site treats an exhausted `ResilientLLMService`/`ResilientMetricsService` fallback chain (`None` result) as an unrecoverable failure (research.md; `ResilientLLMService` itself is unchanged) |
| *(any other `DomainError`, or unmapped)* | 500 | Default fallback (FR-007) |
| *(non-`DomainError` exception reaching the API boundary)* | 500 | Safety-net handler; each occurrence is a guideline-conformance gap to close, not an intended path |

This table is implemented as a single ordered structure (most-specific-first `isinstance` check) inside one exception-handler module — the single registration point required by FR-005.

## 3. API Error Response

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Topic 3fae... was not found",
    "request_id": "b6b2b6b2-....-...."
  }
}
```

| Field | Type | Source |
|---|---|---|
| `error.code` | string, `SCREAMING_SNAKE_CASE` | Derived from the shared category (`NotFoundError` → `NOT_FOUND`) — one fixed string per category, not per leaf exception class |
| `error.message` | string | The exception's human-readable message; for 500-class/unmapped exceptions this MUST be a generic message (FR-009), never `str(exc)` |
| `error.request_id` | string (UUID) | Same value `RequestLoggingMiddleware` already generates and echoes as the `X-Request-ID` response header — read via the request's structlog context, not regenerated (research.md §3) |

Represented as `backend/schemas/error.py::ErrorResponse` (Pydantic, per Constitution Principle VII), used as the `response_model` for the registered exception handlers' documented OpenAPI responses.

## 4. Router Endpoint Audit Entry

One row per route in `backend/routers/` (FR-010), tracked as a working artifact for the tasks phase (not a runtime entity):

| Field | Description |
|---|---|
| Router / route | e.g. `topics.py: DELETE /{topic_id}` |
| Current behavior | e.g. `raise HTTPException(status_code=404, detail="Topic not found")` (inline, ad hoc) |
| Required behavior | e.g. `raise TopicNotFoundError(...)` → central handler → 404 |
| Status | Compliant / Needs migration / New category needed |

Seeded from the `grep`-confirmed inventory: 12 routers, 101 `HTTPException`/`status_code=` occurrences (heaviest: `auth.py` with 36, `tags.py` with 16).
