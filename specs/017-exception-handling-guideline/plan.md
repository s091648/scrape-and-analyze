# Implementation Plan: Exception Handling Guideline & API Status Code Management

**Branch**: `017-exception-handling-guideline` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-exception-handling-guideline/spec.md`

## Summary

The domain exception hierarchy rooted at `DomainError` (`src/shared/domain/exceptions.py`, established by `016-db-schema-brushup`) currently only covers validation-type errors, and `backend/routers/` has no central mechanism translating domain failures into HTTP status codes — each router hand-picks status codes ad hoc (or lets exceptions fall through to FastAPI's default 500), and `backend/auth/guards.py` bypasses the domain hierarchy entirely by raising `HTTPException` directly. This feature (1) extends the `DomainError` hierarchy with four new shared cross-cutting categories (not-found, conflict, external-dependency-failure, unauthorized/forbidden), (2) adds a single centrally-registered FastAPI exception handler that maps every domain exception category to an HTTP status code and a consistent `{"error": {"code", "message", "request_id"}}` response body, (3) migrates `backend/auth/guards.py` onto the new authorization exception category, (4) audits every existing endpoint in `backend/routers/` against the new mapping, and (5) publishes a written guideline documenting when to raise, which exception type to use, and how exceptions propagate across the domain → application → infrastructure → API boundary.

## Technical Context

**Language/Version**: Python 3.11 (both `src/` and `backend/`); no frontend/TypeScript changes required by this feature's functional requirements — 2 existing frontend call sites read the outgoing error shape (see research.md) but degrade gracefully without a code change.

**Primary Dependencies**: FastAPI (`app.add_exception_handler`), Pydantic (new `ErrorResponse` schema per Principle VII), Sentry SDK (already integrated — 500-class errors must still reach Sentry per Constitution Principle VI), `structlog` (`src/`) / stdlib `logging` + `_JsonFormatter` (`backend/`) for the `request_id`-correlated log line.

**Storage**: N/A — no schema/migration changes. This is a pure code-and-documentation change (new exception classes, one exception handler, one guideline doc).

**Testing**: pytest via Docker (`make test`, `make test-integration`) per Constitution Principle III — unit tests for the new exception classes and the exception→status mapping (`src/tests/unit/`, `backend/tests/`), plus a `backend/tests/` sweep asserting the audited endpoints (FR-010) now return mapped status codes for not-found/invalid-input/unauthorized scenarios (Success Criteria SC-001–SC-003).

**Target Platform**: Existing Dockerized Linux services (`backend`, `app`/scraper) — no new service, no deployment topology change.

**Project Type**: Web service (existing FastAPI backend + DDD scraper service monorepo) — this feature extends the existing `src/` and `backend/` trees; no new top-level project.

**Performance Goals**: N/A — a single `except`-clause dispatch in one centrally-registered exception handler; not on any hot path distinct from existing per-router `try`/`except` blocks it replaces.

**Constraints**: The new error response body (`{"error": {"code", "message", "request_id"}}`) MUST NOT crash existing frontend callers during rollout — confirmed safe (research.md): `apiFetch()` (`frontend/lib/api/client.ts`) only branches on HTTP status, never parses the body generically, and the two call sites that do read `data?.detail` (`frontend/app/settings/settings-page-content.tsx`) use `?? fallback`, so they degrade to a generic translated message rather than erroring. 500-class responses MUST NOT leak stack traces/file paths/SQL text (FR-009) while still reaching Sentry + structured logs (Constitution Principle VI: "silent swallowing is forbidden").

**Scale/Scope**: 12 routers under `backend/routers/` (101 existing `HTTPException`/`status_code=` occurrences to audit per FR-010), 2 bounded contexts with an existing `domain/exceptions.py` (`collection`, `intelligence`) to extend with the 4 new shared categories, 1 new central FastAPI exception handler, 1 new `backend/auth/guards.py` migration, 1 new guideline document.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (DDD, NON-NEGOTIABLE)** — PASS. New exception classes live in the domain layer (`src/shared/domain/exceptions.py` and each bounded context's `domain/exceptions.py`), zero dependency on infrastructure/application code. Exceptions are not entities/value objects, so the `@dataclass`-by-default rule doesn't apply to them.
- **Principle III (Test Discipline)** — PASS, with an obligation: `tasks.md` MUST include a dedicated test phase (unit tests for new exception classes + mapping in `src/tests/unit/` and `backend/tests/`; Docker-only execution via `make test`/`make test-integration`).
- **Principle VI (Observability)** — PASS, with a design constraint carried into research.md: the central exception handler MUST still forward 500-class (unmapped/unexpected) exceptions to Sentry and emit a structured log line before returning the sanitized body — "catch inside the handler to build a safe response" is not the same as "swallow," and the plan MUST NOT introduce a bare `except Exception: pass`.
- **Principle VII (Code Style & Quality)** — PASS. The new `ErrorResponse` body is defined as a Pydantic schema in `backend/schemas/`, consistent with existing API input/output schema conventions.
- **Principle IX (FastAPI Microservice Structure)** — PASS. The exception handler is registered in `main.py` (already the place `add_middleware` calls live); `routers/*.py` files lose their per-endpoint status-code branching rather than gaining new responsibilities, keeping router files "route handlers only."
- No violations requiring Complexity Tracking — this feature extends existing layers with new leaf classes and one new cross-cutting handler; it does not introduce a new service, project, or architectural pattern.

## Project Structure

### Documentation (this feature)

```text
specs/017-exception-handling-guideline/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── error-response.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── shared/
│   └── domain/
│       └── exceptions.py            # DomainError root + 4 new shared categories
│                                     # (NotFoundError, ConflictError,
│                                     #  ExternalDependencyError, UnauthorizedError)
├── modules/
│   ├── collection/domain/exceptions.py    # existing CollectionDomainError — extend
│   └── intelligence/domain/exceptions.py  # existing IntelligenceDomainError — extend
├── infrastructure/
│   └── intelligence/llm/resilient_llm_service.py   # unchanged (None-return contract kept)
└── tests/unit/
    └── shared/domain/test_exceptions.py    # new — hierarchy + category tests

backend/
├── main.py                          # register central exception handler
├── auth/
│   └── guards.py                    # migrate HTTPException(401/403) → domain exception
├── schemas/
│   └── error.py                     # new — ErrorResponse Pydantic schema
├── middleware/ or exceptions/
│   └── exception_handlers.py        # new — DomainError → HTTP status/body mapping
├── routers/                         # 12 routers audited per FR-010; status-code
│   └── ...                          # call sites updated to raise domain exceptions
│                                     # instead of inline HTTPException where mapped
└── tests/
    ├── test_exception_handlers.py   # new — mapping + default-500 fallback tests
    └── ...                          # existing router tests extended for FR-010 audit

frontend/
└── app/settings/settings-page-content.tsx   # 2 call sites reading `data?.detail`
                                              # (research.md: non-breaking; optional
                                              # follow-up to read `error.message`)
```

**Structure Decision**: This feature extends the existing two-service monorepo layout (`src/` DDD scraper service + `backend/` FastAPI service) already documented in `CLAUDE.md`; no new top-level directory or service is introduced. Domain-layer changes are scoped to `src/shared/domain/` and the two bounded contexts that already have a `domain/exceptions.py`; API-layer changes are scoped to `backend/main.py`, a new `backend/schemas/error.py`, a new central exception-handler module, and `backend/auth/guards.py`. `frontend/` is touched only optionally, as a non-blocking follow-up.
