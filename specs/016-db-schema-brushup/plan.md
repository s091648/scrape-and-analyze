# Implementation Plan: Database Schema Brush-Up & Auto-Generated Schema Diagram

**Branch**: `016-db-schema-brushup` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-db-schema-brushup/spec.md`

## Summary

Reorganize the 24 `public`-schema tables that have a live SQLAlchemy model into 5 new PostgreSQL schemas (`core`, `collection`, `intelligence`, `ai_infra`, `user_prefs`) that mirror the codebase's existing DDD bounded contexts (`src/modules/collection/`, `src/modules/intelligence/`, `src/shared/domain/entities/`), via a single reversible Alembic migration plus model updates referencing a new shared `DbSchema` enum. Delete the confirmed-dead `models/arxiv_keyword.py`. Add an AST-based generator (parsing `models/*.py`, not importing them, to stay consistent with — and avoid the dependency-install cost of — the existing `pyreverse`-based `scripts/generate_uml.py` pattern) that renders a static database schema diagram as a new page in the `site/` VitePress docs, wired into the existing `.github/workflows/speckit-github-pages.yml` pipeline. Separately, add `backend/config.py` (bringing `backend/` into compliance with the constitution's already-mandated FastAPI microservice structure) and migrate ~23 files' scattered `os.environ`/`os.getenv` calls to read from it.

## Technical Context

**Language/Version**: Python 3.11 (models/, alembic/, backend/, src/, scripts/); Node 20 (site/ — already provisioned in the target workflow)

**Primary Dependencies**: SQLAlchemy >=2.0 (ORM models, `__table_args__` schema declarations), Alembic >=1.13 (migration), FastAPI (backend, unaffected API surface), VitePress (site/, existing docs pipeline), Python stdlib `ast` (new diagram generator — matches `scripts/generate_uml.py`'s static-analysis approach), Graphviz `dot` (already installed in the target workflow step "Install Graphviz", used for `.dot` → `.svg` rendering)

**Storage**: PostgreSQL 15 + pgvector (Railway-hosted production, `pgvector/pgvector:pg15` local Docker image per constitution IV)

**Testing**: pytest via `make test` / `make test-integration` (Docker-only per constitution III); migration correctness verified by existing integration test suite running against the post-migration schema (tests must keep passing unmodified — this feature intentionally changes zero query-level behavior)

**Target Platform**: Railway (backend + scraper services, CD via constitution V), GitHub Pages (VitePress docs, deployed only on `v*` tag push / manual dispatch — unrelated to Railway CD)

**Project Type**: Existing monorepo web service (backend + frontend + scraper) plus a static docs site pipeline — no new project/service is introduced

**Performance Goals**: N/A (organizational/tooling change, not a performance-sensitive feature) — `ALTER TABLE ... SET SCHEMA` is a catalog-only metadata operation with no table rewrite, so migration runtime is expected to be sub-second regardless of table row counts

**Constraints**: Zero query-level behavior change (SC-002); zero data loss and no extended outage during the production migration (SC-005); the migration must be reversible (FR-002); diagram generation must not require installing the full `backend`/`src` dependency tree in CI (drives the AST-over-runtime-import decision below); new VitePress markdown must avoid bare `<...>` outside code fences per constitution VII's "VitePress-compatible Markdown" rule (relevant because column type annotations like `list[str]` or `Vector(768)` could otherwise break the production `npm run build`)

**Scale/Scope**: 24 tables moved across 5 new schemas + 1 table intentionally left in `public` (`data_migrations`; `arxiv_metadata` was initially believed to be a second orphan but was found during implementation to not exist at all — migration 22 drops it in `upgrade()`); ~30 `ForeignKey(...)` string references across `models/*.py` need schema-qualification (see research.md); ~23 files under `backend/` currently call `os.environ`/`os.getenv` directly

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Domain-Driven Design (NON-NEGOTIABLE) | **PASS** | This feature *reinforces* principle I rather than risking it — the new PostgreSQL schema boundaries are deliberately chosen to mirror the existing `src/modules/collection/` and `src/modules/intelligence/` bounded contexts, plus a `core` schema matching the `src/shared/domain/entities/` shared kernel. No DDD layer boundary is crossed or weakened. |
| II. Atomic Frontend Architecture | N/A | No `frontend/` changes in this feature. |
| III. Test Discipline | **PASS (with obligation)** | No new business logic is introduced, but constitution III mandates a dedicated test phase in every `tasks.md` regardless. `tasks.md` MUST include: (a) a migration-correctness test (upgrade + downgrade round-trip against a disposable schema), (b) confirming the existing `src/tests/` and `backend/tests/` suites pass unmodified post-migration (proves SC-002/zero behavior change), (c) unit tests for the new AST-based diagram generator script, (d) unit tests for `backend/config.py` once populated. |
| IV. Docker-First Local Development | **PASS** | Migration ships via `make migrate` (local) / `make migrate-remote` (production) — both already Docker-mediated per `job_service`. No new services, no bare-metal execution introduced. |
| V. CI-Only Deployment Boundary | **PASS** | The schema migration is a normal Alembic revision picked up by the existing CI `migrate` → `rollback-on-test-failure` job on push to `master` — no change to that pipeline's shape. The diagram-generation step is added to the *separate*, tag-triggered `speckit-github-pages.yml` workflow (GitHub Pages, not Railway CD) — consistent with keeping CI (GitHub Actions) and CD (Railway) boundaries distinct. |
| VI. Observability as a First-Class Concern | N/A | No logging/tracing/metrics/error-tracking behavior changes. |
| VII. Code Style & Quality Standards | **PASS (with obligation)** | Alembic migration MUST use the established descriptive-prefix numbering (next is `24_...`). New/modified VitePress markdown (the diagram page) MUST follow the "no bare `<...>` outside code fences" rule — flagged explicitly since column type strings (`Vector(768)`, `list[str]`) are exactly the kind of content that trips this in `npm run build`. |
| VIII. UML Architecture Diagram Conventions | **INFORMS, does not gate** | This principle's *rules* (directory-structure-drives-classification, `Pipeline`/`_repo_impl` naming, etc.) are specific to the `src/` pipeline UML at `/guide/architecture/uml` and don't literally apply to a DB schema diagram. It does establish the *precedent pattern* this feature should follow for consistency: a standalone generator script under `scripts/`, static-analysis (not runtime-import) based, JSON/dot intermediate output, published under `site/guide/architecture/`, wired into the same workflow step group as the existing `pyreverse` step. |
| IX. FastAPI Microservice Structure | **PASS (closes a pre-existing gap)** | `backend/` is one of the 3 services this principle names but currently has *no* `config.py` — it reads `os.environ`/`os.getenv` ad hoc across ~23 files. This feature's `backend/config.py` isn't new scope invented here; it's this feature *fulfilling* an already-ratified, previously-unimplemented constitution requirement. Per IX, the file MUST be pure reads only, no side effects, no imports from the rest of `backend/`, and every other backend module MUST import config from it afterward. All env vars it reads MUST already appear in the repo-root `.env.example` (spot-checked: `NEXTAUTH_SECRET`, `FRONTEND_ORIGIN`, `VIEW_COUNT_FLUSH_INTERVAL` already are — a full audit is a task, not a plan-level risk). |

No unjustified violations. Complexity Tracking section below is empty.

**Post-design re-check** (after Phase 0/1, research.md + data-model.md): No new violations surfaced. Research confirmed the FR-006 "GRANT statements" clause resolves to a no-op (§1 — no separate app role exists to grant), which doesn't touch any constitution principle; the `ForeignKey`/`__table_args__` parsing details (§3–4) and the AST-over-runtime-import choice (§5) are implementation refinements within FR-004/FR-007's already-approved scope, not new gates. Table above stands unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/016-db-schema-brushup/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature adds no new API endpoints or external interfaces (no `backend/routers/` changes) — it is a database organization change plus a docs-pipeline addition plus an internal config-reading refactor. Skipped per plan-template guidance ("Skip if project is purely internal").

### Source Code (repository root)

This is the existing monorepo structure (`src/`, `backend/`, `models/`, `frontend/` — untouched — `alembic/`, `scripts/`, `site/`, `.github/workflows/`); no new top-level directories are introduced. Concrete paths touched by this feature:

```text
models/
├── db_schema.py                    # NEW — DbSchema(str, Enum): CORE/COLLECTION/INTELLIGENCE/AI_INFRA/USER_PREFS
├── article.py                      # __table_args__ → {'schema': DbSchema.CORE.value}  (+ articles_translation FK)
├── article_translation.py          # → core
├── topic.py                        # → core
├── scraper_setting.py              # → collection
├── scraper_keyword.py              # → collection
├── failed_task.py                  # → collection
├── article_metrics.py              # → collection
├── article_metric_value.py         # → collection
├── analysis.py                     # → intelligence
├── analyses_translation.py         # → intelligence
├── tag.py                          # → intelligence  (Tag + article_tags Table)
├── tag_group.py                    # → intelligence
├── tag_group_translation.py        # → intelligence
├── tag_translation.py              # → intelligence
├── tag_normalization_suggestion.py # → intelligence
├── weekly_report.py                # → intelligence
├── weekly_report_translation.py    # → intelligence
├── llm_provider.py                 # → ai_infra
├── metric_definition.py            # → ai_infra
├── metric_provider.py              # → ai_infra
├── user_subscription.py            # → user_prefs  (3 tables: UserTopicSubscription, UserNotificationSettings, UserArticleFavorite)
├── article_chunk.py                # UNCHANGED schema (stays `vectors`), but its `articles.id` FK MUST be requalified to `core.articles.id`
├── arxiv_keyword.py                # DELETED (dead — see spec Assumptions)
└── __init__.py                     # Drop the now-obsolete arxiv_keyword exclusion comment

alembic/versions/
└── 24_reorganize_public_schema_into_ddd_schemas.py   # NEW — CREATE SCHEMA x5, ALTER TABLE...SET SCHEMA for 24 tables, downgrade reverses

scripts/
└── generate_db_schema.py           # NEW — AST-parses models/*.py, resolves DbSchema enum refs, emits .dot → renders .svg

.github/workflows/
└── speckit-github-pages.yml        # MODIFIED — new step after "Generate backend UML (pyreverse)", same job

site/
├── guide/architecture/
│   └── db-schema.md                # NEW — static page embedding the generated SVG
└── .vitepress/config.js            # MODIFIED — nav/sidebar entry for the new page

backend/
├── config.py                       # NEW — centralized os.environ reads (constitution IX)
└── (~23 files across routers/, services/, auth/, middleware/, main.py, tests/)  # MODIFIED — import from config.py instead of calling os.environ directly
```

**Structure Decision**: All changes land inside existing directories following each directory's already-established conventions (`models/` flat module-per-table, `alembic/versions/` numbered migrations, `scripts/` for docs-generation tooling matching `generate_uml.py`'s precedent, `site/guide/architecture/` for auto-generated diagram pages). No new services, packages, or top-level directories.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
