# Implementation Plan: Public API Endpoint Authentication

**Branch**: `017-exception-handling-guideline` (implemented directly on this branch per explicit user instruction — no new branch) | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-public-api-auth/spec.md`

## Summary

Every endpoint listed as "Public" in `backend/routers/` (articles, the analysis graph, tag-group reads, topic listing, weekly reports, language resolution, and both chat endpoints) currently performs no server-side check at all — the frontend's paywall/blur for unauthenticated visitors is purely cosmetic. This feature adds a floor requirement, "does the caller present a valid token," to those endpoints via a new `require_any_token` guard, while preserving today's anonymous/guest UX by giving the backend a new capability it doesn't have today: issuing a short-lived, stateless guest JWT (access + refresh pair) that a caller with no account can obtain with zero credentials. Existing real user/admin JWTs (issued by the frontend's NextAuth layer, unchanged) satisfy the same guard. `chat.py`'s bespoke `__rag_gid` cookie/ip-hash guest identity is retired in favor of the `guest_id` now carried inside the guest token. This is a floor/authentication change only — no RBAC, no new permission tier, no change to any existing `require_admin`/`require_user` check.

## Technical Context

**Language/Version**: Python 3.11 (`backend/`, unchanged); TypeScript/React 19 (`frontend/`) — this is the first feature in this spec sequence that requires a coordinated frontend change (see research.md §9: backend gate and frontend token-attachment must ship together).

**Primary Dependencies**: `python-jose` (already a `backend` dependency; gains its first production `jwt.encode` call — today only `jwt.decode` is used in production code, per research.md §1) for signing/verifying guest tokens with the existing `NEXTAUTH_SECRET`/HS256 path. No new Python or npm dependency is introduced. Frontend: existing `next-auth/react` (`useSession`), no new package.

**Storage**: N/A — both guest token types are stateless (no DB row, no migration; spec.md Clarifications, data-model.md).

**Testing**: pytest via Docker (`make test-backend`) per Constitution Principle III — unit tests for `require_any_token` (`backend/tests/test_guards.py`, extending the existing file), the two new `/auth/guest*` endpoints (`backend/tests/test_auth.py`), the `chat.py` guest-identity migration (`backend/tests/test_chat_router.py`), and a full-audit-style sweep across every in-scope endpoint (mirroring `backend/tests/test_error_response_audit.py` from `017-exception-handling-guideline`) confirming each now 401s with no token and succeeds with a guest token. Frontend: Vitest for the guest-token provider/hook (`frontend/tests/unit/`).

**Target Platform**: Existing Dockerized services (`backend`, `frontend`) — no new service, no deployment topology change.

**Project Type**: Web service (existing FastAPI backend + Next.js frontend monorepo) — extends `backend/auth/`, `backend/routers/auth.py`, `backend/services/auth_service.py`, `backend/routers/chat.py`, and a `frontend/lib/providers/` provider; no new top-level project.

**Performance Goals**: N/A — token issuance/verification is a single HS256 sign/verify call, not on any new hot path; comparable cost to the JWT decode every protected endpoint already performs today.

**Constraints**: Guest tokens MUST remain stateless (no DB row, no revocation-before-expiry — spec.md Clarifications/Assumptions). The backend and frontend changes MUST ship together (research.md §9) — gating an endpoint without the frontend attaching a guest token would 401 the current production frontend for every anonymous visitor. `chat.py`'s existing `RateLimitService` limits/tiers MUST NOT change, only the identity source they key off (spec.md Edge Cases).

**Scale/Scope**: 1 new guard function (`require_any_token`), 2 new endpoints (`POST /auth/guest`, `POST /auth/guest/refresh`) on the existing `/auth` router, ~9 previously-public endpoints across 6 router files gaining the new guard (articles, graph, tags-read, topics-read, weekly-reports, languages) plus `chat.py`'s 2 endpoints migrated off their bespoke guest-cookie logic, 1 new/extended frontend provider plus every currently-token-free `frontend/lib/api/*.ts` call site gaining the same `token?: string` pattern already used by protected call sites.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (DDD, NON-NEGOTIABLE)** — N/A / PASS. This feature touches `backend/auth/` and `backend/routers/`, not `src/modules/*/domain/` — no domain entities or value objects are introduced, so the DDD layering and `@dataclass`-vs-Pydantic rule don't apply.
- **Principle II (Atomic Frontend Architecture)** — PASS. The new guest-token logic extends the existing `GuestModeProvider` (`frontend/lib/providers/`), following the same provider-composition pattern already established there; no new UI atom/molecule/organism is introduced.
- **Principle III (Test Discipline)** — PASS, with an obligation: `tasks.md` MUST include a dedicated backend test phase (`require_any_token`, the two new endpoints, the `chat.py` migration, a cross-endpoint audit sweep) and a frontend Vitest phase for the token provider — Docker-only execution (`make test-backend`, `make test-frontend`).
- **Principle IV (Docker-First Local Development)** — PASS, no change to service topology or Makefile targets required.
- **Principle VI (Observability)** — PASS. 401s produced by `require_any_token` flow through the existing `017-exception-handling-guideline` central handler (structured log line + no Sentry capture for 401, consistent with that feature's "expected/recoverable errors are not error-tracked as bugs" rule) — no new observability surface needed.
- **Principle VII (Code Style & Quality)** — PASS. New request/response bodies (`POST /auth/guest*`) get Pydantic schemas in `backend/schemas/`, consistent with existing API input/output schema conventions.
- **Principle IX (FastAPI Microservice Structure)** — PASS. New endpoints live in the existing `backend/routers/auth.py`; claim-construction/signing logic lives in the existing `backend/services/auth_service.py`; `backend/auth/guards.py` gains one function following its existing pattern (`_require_*_impl` + thin `Depends`-wrapped public function, per the existing `require_admin`/`require_user` shape). No new env var — `NEXTAUTH_SECRET` is already read in `backend/config.py`.
- No violations requiring Complexity Tracking — this feature adds one new guard function, two new endpoints on an existing router, and a migration of one existing router's ad hoc guest logic onto the new mechanism. It does not introduce a new service, project, database table, or architectural pattern.

## Project Structure

### Documentation (this feature)

```text
specs/018-public-api-auth/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── guest-token.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── auth/
│   └── guards.py                    # new: require_any_token (accepts real user/admin
│                                     # tokens OR guest access tokens; rejects guest
│                                     # refresh tokens and anything else)
├── routers/
│   ├── auth.py                      # new: POST /auth/guest, POST /auth/guest/refresh
│   ├── articles.py                  # gains require_any_token on public read endpoints
│   ├── graph.py                     # gains require_any_token
│   ├── tags.py                      # gains require_any_token on the read-only endpoints
│   │                                 # (write endpoints keep require_admin, unchanged)
│   ├── topics.py                    # gains require_any_token on GET /topics
│   ├── weekly_reports.py            # gains require_any_token
│   ├── languages.py                 # gains require_any_token
│   └── chat.py                      # migrated: require_any_token dependency added;
│                                     # _guest_identity()/__rag_gid retired; guest_id
│                                     # now read from the decoded guest token's claim
├── services/
│   └── auth_service.py              # new: guest token claim construction + signing
│                                     # (jwt.encode — first production use in backend/)
├── schemas/
│   └── auth.py or a new guest.py    # new: request/response Pydantic models for
│                                     # POST /auth/guest and /auth/guest/refresh
└── tests/
    ├── test_guards.py               # extended: require_any_token cases
    ├── test_auth.py                 # extended: guest issuance/refresh endpoint tests
    ├── test_chat_router.py          # extended: guest-token-based identity, cookie removal
    └── test_error_response_audit.py # extended: previously-public endpoints now 401
                                      # with no token (mirrors 017's audit pattern)

frontend/
├── lib/
│   ├── providers/
│   │   └── guest-mode-provider.tsx  # extended (or a new sibling provider): acquire/
│   │                                 # store/silently-refresh the guest token pair
│   │                                 # whenever there is no authenticated NextAuth session
│   └── api/
│       ├── articles.ts              # gains token?: string + authHeader(token), matching
│       ├── topics.ts                # the pattern already used by scraper-settings.ts /
│       ├── tags.ts                  # auth.ts for the endpoints that need it
│       ├── weekly-reports.ts (if present)
│       └── ...                      # graph/languages/chat call sites likewise
└── tests/unit/
    └── ...                          # new: guest-token provider tests (Vitest)
```

**Structure Decision**: This feature extends the existing FastAPI backend + Next.js frontend monorepo layout already documented in `CLAUDE.md`; no new top-level directory or service. Backend changes are scoped to the existing `backend/auth/`, `backend/routers/`, `backend/services/`, `backend/schemas/` layers (Principle IX). Frontend changes are scoped to the existing provider layer (Principle II) and the existing `lib/api/*.ts` call-site pattern — no new component. This is the first feature in this repo's spec history that requires backend and frontend changes to ship as one atomic unit (research.md §9); `tasks.md` should reflect that dependency explicitly rather than sequencing them as independent phases.
