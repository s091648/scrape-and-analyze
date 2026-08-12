# Implementation Plan: Lighthouse Performance Check

**Branch**: `020-redis-caching-layer` (reused — see spec.md Assumptions) | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/022-lighthouse-performance-check/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a `make lighthouse-check` target backed by a new Node script (`frontend/scripts/lighthouse-check.mjs`) that runs the `lighthouse` CLI against a configurable base URL and route list (defaulting to `frontend_prod` + `/`, `/articles`, `/graph`, `/tags`), driving Chrome via Playwright's already-installed Chromium binary. It obtains a guest identity via a pre-flight `POST /auth/guest` call for traceability and fail-fast error handling, then lets each route's Lighthouse run bootstrap its own guest session exactly as a real anonymous visitor's browser would (see research.md §3 for why manual header injection isn't actually load-bearing here). Results are consolidated into one Traditional-Chinese Markdown report (plus per-route raw JSON) under a new, gitignored `lighthouse-reports/<runId>/` directory. GitHub Actions/CI integration (User Story 3) is explicitly deferred — this phase only needs to produce a script + Makefile target reliable enough to later wire into `ci.yml`.

## Technical Context

**Language/Version**: Node.js 20 (ESM `.mjs`), matching `frontend/scripts/generate-frontend-context.mjs` and the `frontend` Docker image's existing runtime.

**Primary Dependencies**: `lighthouse` (new frontend devDependency, CLI invoked via `child_process`); `playwright` (existing devDependency, reused only for `chromium.executablePath()` to locate an already-downloaded Chromium binary — see research.md §2). No new backend dependency: guest auth reuses the existing `POST /auth/guest` endpoint (`018-public-api-auth`) as-is.

**Storage**: N/A — output is plain files (`lighthouse-reports/<runId>/report.md` + per-route raw Lighthouse JSON) on the container/host filesystem, no database involved.

**Testing**: Vitest unit tests (`frontend/tests/unit/`) for the pure logic — extracting `RouteMetrics` from a fixture LHR JSON blob, and rendering a `ConsolidatedReport` from a set of `RouteTarget`s (including the failed-route case). The actual Lighthouse/Chrome execution and the `/auth/guest` network call are integration-shaped and are exercised manually via `quickstart.md` instead of mocked in unit tests, matching how this repo already treats other one-off scripts (e.g. `generate_uml.py`) that aren't unit-tested against a live dependency.

**Target Platform**: Linux container (`frontend` Docker service), invoked via `docker compose run --rm frontend ...` — Docker-first per Constitution Principle IV, no bare-metal `node` execution path.

**Project Type**: Dev-tooling CLI (a `make` target + script), not a library/service with its own deploy target.

**Performance Goals**: SC-004 — a full run over the 4 default routes completes in under 10 minutes.

**Constraints**: Zero manual/interactive steps (FR-003, FR-009 — must be CI-safe later); a single route's failure must not abort the whole run or silently disappear from the report (FR-010, edge cases).

**Scale/Scope**: Single-digit route counts per run; not designed to fan out to dozens of routes or run concurrently across multiple base URLs in one invocation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicability | Status |
|---|---|---|
| I. Domain-Driven Design (NON-NEGOTIABLE) | Scoped to `src/`'s hexagonal architecture. This feature adds no `src/` code. | N/A |
| II. Atomic Frontend Architecture | Scoped to React UI components. This feature adds a build/dev-tooling script, not a component. | N/A |
| III. Test Discipline | Applies — "every feature implementation MUST include at least one dedicated test phase" using established frameworks. | **PASS (planned)**: Vitest unit tests land in `frontend/tests/unit/`, the project's established frontend-unit location; `tasks.md` (Phase 2, not this command) must include that test phase. Docker-only test execution (`make test-frontend`) applies unchanged. |
| IV. Docker-First Local Development | Applies — all developer-facing operations MUST be a Makefile target executing inside the right Docker service. | **PASS**: `make lighthouse-check` runs via `docker compose run --rm frontend ...`, no bare-metal invocation path introduced. |
| V. Explicit CI/CD Deployment Boundary | Applies once User Story 3 (CI integration) is implemented; not yet, per spec.md Assumptions. | N/A (deferred) |
| VI. Observability as a First-Class Concern | Scoped to long-running services (structured logs to Loki, OTel traces/metrics, Sentry). A one-shot local/CI dev-tool invocation is not a "service" in this sense. | N/A — plain stdout progress lines (contracts/cli-interface.md) are sufficient for a script whose entire output is itself a report artifact. |
| VII. Code Style & Quality Standards | Applies — TypeScript/React strict-mode rules are frontend-wide, but `frontend/scripts/*.mjs` are plain ESM (no build step), matching `generate-frontend-context.mjs`'s existing precedent. | **PASS**: new script follows that same plain-`.mjs` convention; no TODOs/placeholder implementations. |
| VIII. UML Architecture Diagram Conventions | Scoped to `src/modules/*` DDD pipeline structure. | N/A |
| IX. FastAPI Microservice Structure | Applies to `backend/`/`chatbot-plugin/`/`services/fastembed/` internals. This feature adds zero backend code (reuses the existing `/auth/guest` endpoint unmodified). | N/A |

No violations requiring justification — Complexity Tracking table below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/022-lighthouse-performance-check/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── cli-interface.md
│   └── report-format.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/
├── scripts/
│   └── lighthouse-check.mjs        # NEW — orchestrator: guest pre-flight, per-route `lighthouse` CLI runs, report generation
├── tests/
│   └── unit/
│       └── lighthouse-check.test.ts  # NEW — pure-function tests: LHR → RouteMetrics extraction, ConsolidatedReport rendering
└── package.json                     # MODIFIED — add `lighthouse` devDependency

Makefile                              # MODIFIED — new `lighthouse-check` target + `LIGHTHOUSE_URL`/`LIGHTHOUSE_ROUTES` vars
.gitignore                            # MODIFIED — add `lighthouse-reports/`
lighthouse-reports/                   # NEW at runtime, gitignored — one subdir per run (report.md + per-route raw JSON)
```

**Structure Decision**: This repo is already the "web application" layout (`backend/` + `frontend/` + shared `models/`) described in the plan template's Option 2 — no new top-level project/service is introduced. This feature is purely additive within the existing `frontend/` tree (a new `scripts/` entry + a new `tests/unit/` file) plus a `Makefile` target and a new gitignored, repo-root output directory (`lighthouse-reports/`) mirroring the existing `db_dumps/` convention for generated artifacts that shouldn't be committed.

## Complexity Tracking

*No entries — Constitution Check above recorded no violations.*
