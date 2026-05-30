# Implementation Plan: Scheduler & Pipeline Assembly

**Branch**: `007-scheduler-pipeline` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-scheduler/spec.md`

## Summary

The scheduler capability is the run-once entry point and composition root for the scraper pipeline. It covers: configuration validation, startup jitter, run-context initialization, signal handler registration, pipeline assembly (wiring all repositories, event bus, LLM services, use cases, and event handlers), due-source selection, observability emission, and teardown. As a brownfield spec, tasks focus on writing tests that verify existing behaviour matches the spec, rather than implementing new code.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: SQLAlchemy >=2.0, structlog, OpenTelemetry SDK, Sentry SDK, python-jose

**Storage**: PostgreSQL 15 + pgvector (via shared `models/` ORM)

**Testing**: pytest + pytest-cov; `make test` for unit, `make test-integration` for DB-dependent

**Target Platform**: Linux server (Docker containers, Railway deployment)

**Project Type**: CLI entry point + composition root (part of a web-service/scraper system)

**Performance Goals**: No-sources-due path completes in <5 seconds; single-run-and-exit model

**Constraints**: 50-minute hard timeout defined but not enforced; single SQLAlchemy session for entire pipeline lifecycle

**Scale/Scope**: Single-process, single-run; external scheduling triggers each invocation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD | ✅ Pass | `bootstrap.py` is the composition root; domain/application/infrastructure layers are respected |
| II. Atomic Frontend | N/A | No frontend changes |
| III. Test Discipline | ✅ Pass | Tasks will add unit tests via `make test`; integration tests via `make test-integration` |
| IV. Docker-First | ✅ Pass | Test execution via Docker Makefile targets |
| V. CI-Only Deploy | ✅ Pass | No deployment changes |
| VI. Observability | ✅ Pass | Spec explicitly covers OTel, Sentry, structlog |
| VII. Code Style | ✅ Pass | Follows existing Python conventions; no TODO comments |

No violations. All gates pass.

## Project Structure

### Documentation (this feature)

```text
specs/007-scheduler/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── entrypoints/
│   └── cli/
│       ├── main.py              # Run-once entry point (P1, P3, P5)
│       └── translate.py         # Standalone translation CLI (P4)
├── bootstrap.py                 # Composition root (P2)
├── config/
│   └── settings.py             # validate_config(), env vars
├── infrastructure/
│   └── collection/
│       ├── collection_pipeline.py  # CollectionPipeline.run()
│       └── executor/
│           └── scrape_executor.py  # ScrapeExecutor
├── modules/
│   └── collection/
│       └── domain/
│           └── entities/
│               └── scraper_setting.py  # ScraperSetting entity
└── infrastructure/
    └── persistence/
        └── collection/
            └── scraper_setting_repo_impl.py  # get_active_due()

src/tests/unit/
├── entrypoints/cli/
│   ├── test_main.py             # Existing: check_timeout() only (2 tests)
│   └── test_translate_cli.py    # Existing: translate CLI tests (4 tests)
└── test_composition_root.py     # Existing: source-inspection tests (3 tests)
```

**Structure Decision**: Existing structure — no new files needed for brownfield documentation. Test files may be expanded.

## Complexity Tracking

No constitution violations to justify.
