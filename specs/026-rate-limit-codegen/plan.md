# Implementation Plan: API Rate Limiting & Generated Frontend Types

**Branch**: `026-rate-limit-codegen` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-rate-limit-codegen/spec.md`

## Summary

Two related hardening efforts for the public API surface: (1) protect the abuse-prone, currently-unprotected endpoints (`/auth/guest`, `/auth/verify`, `/auth/register`, `/auth/google/authorize`, `/auth/refresh`, `/auth/guest/refresh`, and the already-authenticated `/chat/completions` and `/search*`) with Redis-backed rate limits enforced in the FastAPI process, since Railway provides no edge/proxy layer to do this at; and (2) stop hand-maintaining frontend TypeScript interfaces that mirror the backend's Pydantic schemas by generating them from the backend's exported OpenAPI contract, with a CI check that fails when the generated types fall out of sync. Both reuse patterns already proven in this codebase (chat's existing Redis daily-quota limiter; the project's existing generated/derived-artifact drift-check convention) rather than introducing new infrastructure.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript (strict) / Next.js 16 (frontend) — unchanged, per constitution's Technology Stack table

**Primary Dependencies**: FastAPI, `redis.asyncio` (already a backend dependency via `chat_service.py`) for rate limiting — no new Python dependency. One new frontend devDependency: a types-only OpenAPI→TypeScript generator (research.md Decision 7)

**Storage**: Redis (`REDIS_URL`, db 0 — the existing durable-state DB chat's daily quota already lives in) for rate-limit counters; no new PostgreSQL tables/migrations (research.md Decision 4)

**Testing**: pytest (`backend/tests/`, unit-level with a mocked Redis client, mirroring `backend/tests/test_chat_router.py`'s `_make_redis` patching pattern) for rate limiting; Vitest/typecheck (`frontend/tests/unit/` or the existing `npm run build`/lint step) for generated-types consumption

**Target Platform**: Railway (backend + frontend services), no nginx/K8s edge — confirmed constraint driving Decision 1 (enforcement lives in-process, not at an edge layer)

**Project Type**: Web application (existing `backend/` FastAPI service + `frontend/` Next.js app) — Option 2 structure below

**Performance Goals**: Rate-limit check adds at most one Redis round-trip per protected request (sub-millisecond to low-single-digit ms typical); no measurable impact on unprotected endpoints (no dependency added to routers that don't opt in)

**Constraints**: No new infrastructure (must run entirely within the existing FastAPI process + already-provisioned Redis + existing CI); threshold tuning must not require touching multiple files per policy (one env-var pair per policy)

**Scale/Scope**: 9 endpoints gain rate-limit protection across 4 policies (guest-token issuance, auth attempts, chat burst, search); ~17 existing hand-written files under `frontend/lib/api/` migrate to generated types

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Applies? | Assessment |
|---|---|---|
| I. Domain-Driven Design (`src/`) | No | This feature touches only `backend/` and `frontend/`, never `src/`. No DDD layers introduced or violated. |
| II. Atomic Frontend Architecture | Partial | No new UI components; `frontend/lib/api/` is not part of the `components/` hierarchy this principle governs. Pass. |
| III. Test Discipline | Yes | Backend unit tests for the limiter (mocked Redis, no real DB/Redis required, matching "unit tests MUST NOT require a running database/service" precedent from `test_chat_router.py`) + a frontend check that generated types compile against existing call sites. `/speckit-tasks` MUST include a dedicated test phase per the mandatory-test-tasks rule. Pass (see tasks.md once generated). |
| IV. Docker-First Local Development | Yes | Regeneration exposed via a Makefile target (`make generate-api-types`), consistent with "Makefile as interface"; no new always-on service, no bare-metal run introduced. Pass. |
| V. Explicit CI/CD Deployment Boundary | Yes | New CI step is a check within the existing PR pipeline (frontend-unit stage), not a new deploy trigger; no change to staging/production deploy gating. Pass. |
| VI. Observability as a First-Class Concern | Yes | Rate-limit refusals logged at `warning` (matching existing 4xx `DomainError` treatment), not sent to Sentry (expected/recoverable, consistent with 400/401/403/404/409 precedent); Redis-unavailable fail-open path logs the failure rather than swallowing it silently. Pass. |
| VII. Code Style & Quality Standards | Yes | New `RateLimitExceededError` follows the existing `shared/domain/exceptions.py` category pattern; `ErrorBody.retry_after_seconds` added as an optional Pydantic field, consistent with "Pydantic schemas for API input/output validation." TypeScript strict mode unaffected. Pass. |
| VIII. UML Architecture Diagram Conventions | No | No `src/modules/`, `src/bootstrap.py`, domain events, or handlers touched. N/A. |
| IX. FastAPI Microservice Structure | Yes | New `backend/rate_limit/` package (mirrors the existing `backend/auth/` package shape: cross-cutting `Depends()`-based guards, not a router, not business-logic-in-router); new env vars added to `backend/config.py` only, no `os.environ` reads elsewhere. Pass. |

No violations requiring justification — Complexity Tracking table below is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/026-rate-limit-codegen/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── rate-limit-response.md
│   └── api-type-generation-workflow.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Option 2: Web application (existing backend/ + frontend/, both modified by this feature)

backend/
├── config.py                         # + RATE_LIMIT_* env vars (research.md Decision 4)
├── rate_limit/                       # NEW — mirrors backend/auth/'s shape
│   ├── __init__.py
│   ├── policies.py                   # Rate Limit Policy registry (data-model.md)
│   ├── limiter.py                    # Redis fixed-window check + check_rate_limit() + Depends() factories per policy
│   └── client_origin.py              # Shared IP-extraction helper (consolidates the logic
│                                      # duplicated today in languages.py / bootstrap.py /
│                                      # auth_service.py::compute_guest_id)
├── routers/
│   ├── auth.py                       # + Depends(guest_token_limit) on /guest,
│   │                                  #   Depends(auth_attempt_limit) on /verify /register
│   │                                  #   /google/authorize /refresh /guest/refresh
│   ├── chat.py                       # + Depends(chat_burst_limit) on /chat/completions;
│   │                                  #   raises RateLimitExceededError instead of its own
│   │                                  #   HTTPException(429) (research.md Decision 3)
│   └── search.py                     # + Depends(search_limit) on /search, /search/autocomplete
├── schemas/
│   └── error.py                      # ErrorBody + retry_after_seconds (Optional[int])
├── exceptions/
│   └── handlers.py                   # _CATEGORY_MAPPING + (RateLimitExceededError, 429, "RATE_LIMIT_EXCEEDED")
└── tests/
    └── test_rate_limit.py            # NEW — unit tests, mocked Redis (mirrors test_chat_router.py pattern)

shared/
└── domain/
    └── exceptions.py                 # + RateLimitExceededError(DomainError)

scripts/
└── export_openapi_schema.py          # NEW (research.md Decision 6)

frontend/
├── lib/api/
│   ├── generated-types.ts            # NEW — generated, never hand-edited (research.md Decision 7)
│   ├── topics.ts                     # hand-written `interface` replaced with an import from
│   ├── articles.ts                   #   generated-types.ts (repeat for all ~17 files in this
│   ├── tags.ts                       #   directory); fetch functions / apiFetch usage unchanged
│   └── ... (remaining lib/api/*.ts files)
└── package.json                      # + devDependency: types-only OpenAPI→TS generator

backend/openapi.json                  # NEW — checked-in exported contract (research.md Decision 6)

Makefile                              # + generate-api-types target (export + generate, per quickstart.md)

.github/workflows/ci.yml              # frontend-unit stage + drift-check step (research.md Decision 8)
```

**Structure Decision**: Existing Option 2 (web application) layout is unchanged at the top level — this feature adds one new backend package (`backend/rate_limit/`, sized and shaped like the existing `backend/auth/`), one new top-level script (`scripts/export_openapi_schema.py`), one new generated frontend file, and touches existing routers/config/schemas/exceptions/lib-api files rather than introducing a new service or directory tier.

## Complexity Tracking

*No entries — Constitution Check above reported no violations.*
