# Tasks: Database Schema Brush-Up & Auto-Generated Schema Diagram

**Input**: Design documents from `/specs/016-db-schema-brushup/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all present)

**Tests**: Included — mandatory per constitution §III ("Mandatory test tasks in every tasks.md"). Test locations used: `src/tests/unit/`, `src/tests/integration/` (`@pytest.mark.integration`), `backend/tests/`, `scripts/tests/`.

**Organization**: Tasks are grouped by user story (US1/US2/US3, matching spec.md's priorities P1/P2/P3) so each story can be implemented, tested, and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- File paths are exact and relative to the repository root

---

## Phase 1: Setup

**Purpose**: Confirm a clean starting baseline before touching schema/model code

- [X] T001 Run `make migrate` at the repo root to confirm the local Postgres is at Alembic `head` (revision `23_article_recommendation_weekly_report`) before starting — establishes the known-good pre-migration baseline referenced throughout quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one artifact every other phase in this feature reads or references

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Create `models/db_schema.py` with `DbSchema(str, Enum)` — members `CORE = "core"`, `COLLECTION = "collection"`, `INTELLIGENCE = "intelligence"`, `AI_INFRA = "ai_infra"`, `USER_PREFS = "user_prefs"` — per data-model.md §1

**Checkpoint**: `DbSchema` enum exists and is importable — US1 (model updates) and US2 (diagram generator, which statically parses this file) can now both proceed.

---

## Phase 3: User Story 1 - Tables Organized by DDD Bounded Context (Priority: P1) 🎯 MVP

**Goal**: Move the 24 modeled `public` tables into `core`/`collection`/`intelligence`/`ai_infra`/`user_prefs`, matching the codebase's existing DDD bounded contexts, with zero behavior change.

**Independent Test**: Run `make migrate`, then query `information_schema.tables` and confirm the 3/5/10/3/3 distribution from data-model.md §2; run `make test` + `make test-integration` and confirm they still pass unmodified; run `make migrate-down` and confirm every table returns to `public`.

### Tests for User Story 1

> Write these first — T003 fails until the model updates below land; T004 fails until the migration (T005) lands.

- [X] T003 [P] [US1] Add schema-assertion tests to `src/tests/unit/infrastructure/persistence/test_orm_models.py` — one assertion per moved model, `<Model>.__table__.schema == DbSchema.<X>.value`, covering all 24 tables per the data-model.md §2 mapping (no DB required — matches this file's existing style, e.g. `test_topic_model_columns`)
- [X] T004 [P] [US1] Add `src/tests/integration/test_db_schema_migration.py` (`@pytest.mark.integration`) — after `alembic upgrade head` has run (already guaranteed by the CI job order per `.github/workflows/ci.yml`), query `information_schema.tables` and assert: the 5 new schemas exist, contain exactly the tables listed in data-model.md §2, and `public` contains only `data_migrations` (plus `alembic_version`)

### Implementation for User Story 1

- [X] T005 [US1] Create `alembic/versions/24_reorganize_public_schema_into_ddd_schemas.py` — `upgrade()`: 5× `CREATE SCHEMA IF NOT EXISTS`, then `ALTER TABLE public.<table> SET SCHEMA <schema>` for all 24 tables in data-model.md §2's mapping; **plus** (added during implementation, research.md §8) `ALTER DATABASE ... SET search_path TO core, collection, intelligence, ai_infra, user_prefs, public` so pre-existing unqualified raw SQL keeps resolving; `downgrade()`: reverse every move back to `public`, `RESET search_path`, then `DROP SCHEMA IF EXISTS` the 5 schemas — verified reversible (downgrade -1 → upgrade head) on both a fresh throwaway DB and the local dev DB
- [X] T006 [P] [US1] Update `models/article.py` — `__table_args__` → `{'schema': DbSchema.CORE.value}`; requalify `ForeignKey('topics.id')` → `ForeignKey('core.topics.id')`
- [X] T007 [P] [US1] Update `models/article_translation.py` — `__table_args__` → `DbSchema.CORE`; requalify `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [X] T008 [P] [US1] Update `models/topic.py` — `__table_args__` → `{'schema': DbSchema.CORE.value}` (no FKs to requalify)
- [X] T009 [P] [US1] Update `models/scraper_setting.py` — `__table_args__` → `{'schema': DbSchema.COLLECTION.value}` (no FKs to requalify)
- [X] T010 [P] [US1] Update `models/scraper_keyword.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('topics.id', ...)` → `'core.topics.id'`
- [X] T011 [P] [US1] Update `models/failed_task.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('articles.id')` → `'core.articles.id'` and `ForeignKey('analyses.id', ...)` → `'intelligence.analyses.id'`
- [X] T012 [P] [US1] Update `models/article_metrics.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [X] T013 [P] [US1] Update `models/article_metric_value.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [X] T014 [P] [US1] Update `models/analysis.py` — `__table_args__` → `{'schema': DbSchema.INTELLIGENCE.value}`; requalify `ForeignKey('articles.id')` → `'core.articles.id'`
- [X] T015 [P] [US1] Update `models/analyses_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('analyses.id', ...)` → `'intelligence.analyses.id'`
- [X] T016 [P] [US1] Update `models/tag.py` — `Tag.__table_args__` and the module-level `article_tags` association `Table(...)` both → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('tag_group_definitions.id', ...)`, `ForeignKey('articles.id')` → `'core.articles.id'`, `ForeignKey('tags.id')` → `'intelligence.tags.id'`
- [X] T017 [P] [US1] Update `models/tag_group.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('topics.id')` → `'core.topics.id'`
- [X] T018 [P] [US1] Update `models/tag_group_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('tag_group_definitions.id')` → `'intelligence.tag_group_definitions.id'`
- [X] T019 [P] [US1] Update `models/tag_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('tags.id')` → `'intelligence.tags.id'`
- [X] T020 [P] [US1] Update `models/tag_normalization_suggestion.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify both `ForeignKey('tags.id', ...)` → `'intelligence.tags.id'` and `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [X] T021 [P] [US1] Update `models/weekly_report.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('topics.id', ...)` → `'core.topics.id'`
- [X] T022 [P] [US1] Update `models/weekly_report_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('weekly_reports.id', ...)` → `'intelligence.weekly_reports.id'`
- [X] T023 [P] [US1] Update `models/llm_provider.py` — `__table_args__` → `{'schema': DbSchema.AI_INFRA.value}` (no FKs to requalify)
- [X] T024 [P] [US1] Update `models/metric_definition.py` — `__table_args__` → `{'schema': DbSchema.AI_INFRA.value}` (no FKs to requalify)
- [X] T025 [P] [US1] Update `models/metric_provider.py` — `__table_args__` → `DbSchema.AI_INFRA`; requalify `ForeignKey('metric_definitions.id', ...)` → `'ai_infra.metric_definitions.id'`
- [X] T026 [P] [US1] Update `models/user_subscription.py` — all 3 classes' (`UserTopicSubscription`, `UserNotificationSettings`, `UserArticleFavorite`) `__table_args__` → `DbSchema.USER_PREFS`; requalify `ForeignKey('topics.id', ...)` → `'core.topics.id'` and `ForeignKey('articles.id', ...)` → `'core.articles.id'`; leave the `ForeignKey('auth.users.id', ...)` FKs unchanged
- [X] T027 [P] [US1] Update `models/article_chunk.py` — cross-boundary fix only: requalify `ForeignKey("articles.id", ...)` → `"core.articles.id"`; do **not** change its own `__table_args__` (stays `vectors`, out of scope)
- [X] T028 [US1] Delete `models/arxiv_keyword.py`; remove the now-obsolete `# NOTE: models.arxiv_keyword is intentionally excluded...` comment block from `models/__init__.py`
- [X] T029 [P] [US1] Surveyed raw SQL in `src/entrypoints/cli/refresh_metrics.py` — **superseded, see research.md §8**: initially schema-qualified (`FROM core.articles`), then reverted to unqualified (`FROM articles`) once `schema_translate_map` was found to not apply to raw `text()` SQL — resolves correctly via the new database-level `search_path` (T005) instead
- [X] T030 [P] [US1] Surveyed raw SQL in `src/infrastructure/persistence/intelligence/tag_repo_impl.py` — same supersession as T029; left unqualified, relies on `search_path`
- [X] T031 [P] [US1] Surveyed raw SQL in `src/infrastructure/persistence/intelligence/tag_group_definition_repo_impl.py` — same supersession as T029
- [X] T032 [P] [US1] Surveyed raw SQL in `backend/routers/tags.py` — same supersession as T029
- [X] T033 [P] [US1] Surveyed raw SQL in `backend/services/scraper_settings_service.py` — same supersession as T029
- [X] T034 [P] [US1] Surveyed raw SQL in `backend/services/tag_service.py` — same supersession as T029
- [X] T035 [P] [US1] Surveyed raw SQL in `backend/services/article_service.py` — same supersession as T029
- [X] T036 [US1] `src/tests/integration/conftest.py` — **expanded beyond the original task description** (research.md §8): added `schema_translate_map={schema: TEST_SCHEMA for schema in DDD_SCHEMAS}` on the test engine (not just a `FIXED_SCHEMAS` set addition — a plain exclusion broke isolation for the ~35 tests exercising these tables, since several moved tables carry migration-seeded rows even on a fresh DB); `FIXED_SCHEMAS` itself stays `{"auth", "vectors"}`, its original pre-feature value
- [X] T037 [US1] `backend/tests/integration/conftest.py` — same `schema_translate_map` approach as T036
- [X] (unplanned, found via full-suite verification) Fixed 2 test files with raw SQL against moved tables to match the unqualified convention: `src/tests/integration/test_metrics_refresh_pipeline.py` (also scoped `_STALE_ARTICLES_QUERY` assertions by `article_id` instead of relying on `LIMIT 200` over what is, outside full isolation, a much larger real table; changed `_make_article`'s `commit()` to `flush()` to stay within the session's rollback boundary) and `src/tests/integration/intelligence/test_tag_constraints_integration.py`

**Checkpoint**: ✅ Verified against a disposable freshly-migrated throwaway Postgres container AND the local dev DB: `src/tests/unit/` 701 passed, `backend/tests/` (unit) 332 passed, `src/tests/integration/` 80 passed, `backend/tests/integration/` 224 passed (304 total integration, 1033 total unit — 1337 tests green). `make migrate-down` → `make migrate` round-trip verified reversible. Quickstart.md §1–2 succeed end to end. User Story 1 is independently shippable here.

---

## Phase 4: User Story 2 - Auto-Generated Database Diagram in the Docs Site (Priority: P2)

**Goal**: A new VitePress page showing every table/column/FK/schema, generated by static AST analysis of `models/`, wired into the existing docs pipeline.

**Independent Test**: Run `scripts/generate_db_schema.py` locally, confirm it emits an SVG under `site/public/guide/architecture/`; build the site (`npm run build` in `site/`) and confirm the new page renders and is reachable from nav.

### Tests for User Story 2

- [X] T038 [P] [US2] Added `scripts/tests/test_generate_db_schema.py` — 9 tests covering dict-form/tuple-form `__table_args__`, literal-string schema (auth-style), `DbSchema.<MEMBER>.value` resolution, cross-schema FK detection, association `Table()` parsing, the `Column('db_name', Type)` name-override edge case (found while dogfooding against real `models/article.py`), and fail-loud on unparseable `__table_args__` — all 9 pass

### Implementation for User Story 2

- [X] T039 [US2] Implemented `scripts/generate_db_schema.py` — static `ast`-parses `models/*.py`, emits `site/public/guide/architecture/db-schema.dot` — **design change from the plan**: outputs only `.dot` (no server-side `.svg` render step); discovered `site/guide/architecture/viewer.html` already renders `.dot` client-side via `@viz-js/viz` (loaded from CDN) rather than pre-rendering SVG server-side, so this reuses that exact established pattern instead of introducing a second one — no `dot` CLI/Graphviz dependency needed for this script at all (confirmed: runs with plain stdlib-only `python`, no `uv sync` required). Verified against real `models/`: discovers all 26 tables (24 moved + `auth.users` + `vectors.article_chunks`) across 7 schema clusters, 27 FK edges, cross-schema edges correctly flagged (e.g. `vectors.article_chunks → core.articles`)
- [X] T040 [US2] Added "Generate DB schema diagram" step to `.github/workflows/speckit-github-pages.yml` after "Generate backend UML (pyreverse)"
- [X] T041 [US2] Created `site/guide/architecture/db-schema.md` + `site/.vitepress/theme/DbSchemaViewer.vue` (registered globally in `site/.vitepress/theme/index.js`, matching the existing `UmlViewer`/`DepGraphViewer` pattern) — fetches `./db-schema.dot` and renders client-side via the same `@viz-js/viz` CDN build `viewer.html` already uses
- [X] T042 [US2] Added "DB Schema" nav/sidebar entry — in `site/scripts/generate-config.mjs` (the actual source of truth: `site/.vitepress/config.js` is auto-generated by `npm run generate`, so hand-editing only `config.js` would be overwritten) and reflected in the current `config.js` via running that generator

**Checkpoint**: ✅ `npm run generate && npm run build` (production build, the stricter one per constitution VII) succeeds with zero errors; `dist/guide/architecture/db-schema.html` and `db-schema.dot` both present in build output. Independently shippable — does not require User Story 3.

---

## Phase 5: User Story 3 - Centralized Backend Configuration (Priority: P3)

**Goal**: `backend/config.py` becomes the single place `backend/` reads environment variables, closing the pre-existing constitution IX compliance gap.

**Independent Test**: `grep -rn "os\.environ\|os\.getenv" backend/ --include="*.py" | grep -v backend/tests | grep -v backend/config.py` returns nothing; `backend/tests/` passes unmodified.

### Tests for User Story 3

- [X] T043 [P] [US3] Added `backend/tests/test_config.py` — 8 tests covering every constant

### Implementation for User Story 3

- [X] T044 [US3] Created `backend/config.py` per data-model.md §4 — all 15 vars, matching `src/config/settings.py`'s pure-reads style
- [X] T045 [P] [US3] Migrated `backend/database.py`
- [X] T046 [P] [US3] Migrated `backend/main.py` (also dropped the now-unused `import os`)
- [X] T047 [P] [US3] Migrated `backend/auth/guards.py` (3 call sites)
- [X] T048 [P] [US3] Migrated `backend/middleware/logging.py`
- [X] T049 [P] [US3] Migrated `backend/services/article_service.py`
- [X] T050 [P] [US3] Migrated `backend/services/chat_service.py`
- [X] T051 [P] [US3] Migrated `backend/services/tag_service.py`
- [X] T052 [P] [US3] Migrated `backend/routers/chat.py`
- [X] T053 [P] [US3] Migrated `backend/routers/articles.py`
- [X] T054 [US3] Migrated `backend/routers/grafana.py` (7 vars × 6 call sites)
- [X] T055 [US3] Cross-checked all 15 vars against `.env.example` — all already present, no additions needed
- [X] (unplanned, found via full-suite verification) **Frozen-constant test regression, fixed**: `backend/config.py` reads env vars once at import time (by design, matching `src/config/settings.py` and constitution IX) — several existing tests relied on the *old* per-request `os.environ.get()` behavior via `patch.dict(os.environ, ...)` around individual requests, expecting live reads. Fixed by reloading the affected module chain (`backend.config` → the router/module that imports from it → `backend.main`, since `app.include_router()` bakes in handler closures that only refresh on a `backend.main` reload) inside a test-local context manager, mirroring the reload pattern `backend/tests/test_cors.py` had already established pre-this-feature for `FRONTEND_ORIGIN`. Fixed 3 files: `backend/tests/test_cors.py` (extended its existing reload fixture to also reload `backend.config` first), `backend/tests/test_grafana.py` (new `_grafana_env()` helper, all 21 `patch.dict` call sites), `backend/tests/integration/test_grafana.py` (new `_grafana_env()` helper that also re-applies the `get_db` dependency override to the rebuilt app, all 16 call sites)

**Checkpoint**: ✅ Verified against both a disposable freshly-migrated throwaway Postgres container and the local dev DB: full suite (`src/tests/unit/` + `src/tests/integration/` + `backend/tests/` unit + `backend/tests/integration/`) = **1345 passed, 0 failed** on both databases. `grep -rn "os\.environ\|os\.getenv" backend/ --include="*.py" | grep -v backend/tests | grep -v backend/config.py` returns nothing. Independently shippable — touches none of the files from US1/US2.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Whole-feature verification across all three stories

- [X] T056 [P] Ran `make test-src test-backend test-src-integration test-backend-integration` (the actual Makefile target names — `test`/`test-integration` in the original task description were approximate) — **1345 passed, 0 failed**, confirmed against both the local dev DB and a disposable freshly-migrated throwaway Postgres container
- [X] T057 Walked through quickstart.md §1–§5 end to end during implementation (migration round-trip verified, `arxiv_keyword.py` deletion verified, diagram generator + `npm run build` verified, `backend/config.py` zero-`os.environ`-outside-config verified)
- [X] T058 [P] Added a pointer in `CLAUDE.md`'s "### ORM Models" section (also fixed a now-stale line: `ArxivKeyword` was documented as "legacy" but is now fully deleted, not just superseded)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (both US1's model edits and US2's diagram-generator design reference the `DbSchema` enum)
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only, technically — but is only *meaningful* once US1 has landed (spec.md's own stated priority rationale: the diagram's value is showing the new grouping). No hard file-level dependency exists between the two, so they *can* proceed in parallel if needed.
- **User Story 3 (Phase 5)**: Depends on Foundational only — fully independent of US1 and US2 (disjoint file sets: `backend/config.py` + call sites vs. `models/`/`alembic/`/`scripts/`/`site/`)
- **Polish (Final Phase)**: Depends on all three user stories being complete

### Within User Story 1

- T003/T004 (tests) should be written first and observed failing, then T005 (migration) and T006–T027 (model updates) make them pass
- T005 (migration) has no code dependency on T006–T027 (models) or vice versa — they can be authored in parallel, but T004's integration test needs T005 applied to a real database to pass
- T028 (delete arxiv_keyword) is independent of everything else in this phase
- T029–T035 (raw SQL fixes) are independent of each other and of the model-file tasks — same schema-naming facts, different files
- T036/T037 (conftest fixes) should land after the model tasks are understood but have no code dependency on them; they must land before re-running `make test-integration` in the Checkpoint

### Parallel Opportunities

- All of T006–T027 (22 model files) are mutually independent — full-team parallel batch
- All of T029–T035 (7 raw-SQL files) are mutually independent
- T036 and T037 (the two `conftest.py` files) are independent of each other
- T045–T053 (9 of the 10 backend call-site migrations) are mutually independent; only T054 (`grafana.py`, denser) is separated out as its own task
- US2 and US3 can be staffed entirely in parallel with each other and (after Foundational) with US1

---

## Parallel Example: User Story 1

```bash
# After T002 (DbSchema enum) and T005 (migration) exist, launch the model-file batch together:
Task: "Update models/article.py — schema + FK requalification"
Task: "Update models/topic.py — schema"
Task: "Update models/scraper_setting.py — schema"
Task: "Update models/analysis.py — schema + FK requalification"
# ... (all of T006-T027)

# Independently, launch the raw-SQL batch together:
Task: "Fix raw SQL in src/entrypoints/cli/refresh_metrics.py"
Task: "Fix raw SQL in backend/services/scraper_settings_service.py"
Task: "Fix raw SQL in backend/services/article_service.py"
# ... (all of T029-T035)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1)
2. **STOP and VALIDATE**: quickstart.md §1–2, `make test` + `make test-integration` green
3. This alone satisfies issue #91's core ask — schemas are reorganized, app behavior unchanged

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate independently → the schemas exist, everything still works (MVP)
3. User Story 2 → validate independently → the diagram is live and accurate
4. User Story 3 → validate independently → `backend/config.py` closes the constitution IX gap
5. Polish → whole-feature regression pass + doc pointer

### Parallel Team Strategy

Once Foundational (T002) is merged: one contributor can take US1 (by far the largest phase — 35 tasks, but 29 of them are mutually [P]), a second can take US2 (5 tasks), a third can take US3 (13 tasks, 9 of them [P]). None of the three touch overlapping files.
