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

- [ ] T001 Run `make migrate` at the repo root to confirm the local Postgres is at Alembic `head` (revision `23_article_recommendation_weekly_report`) before starting — establishes the known-good pre-migration baseline referenced throughout quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one artifact every other phase in this feature reads or references

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Create `models/db_schema.py` with `DbSchema(str, Enum)` — members `CORE = "core"`, `COLLECTION = "collection"`, `INTELLIGENCE = "intelligence"`, `AI_INFRA = "ai_infra"`, `USER_PREFS = "user_prefs"` — per data-model.md §1

**Checkpoint**: `DbSchema` enum exists and is importable — US1 (model updates) and US2 (diagram generator, which statically parses this file) can now both proceed.

---

## Phase 3: User Story 1 - Tables Organized by DDD Bounded Context (Priority: P1) 🎯 MVP

**Goal**: Move the 24 modeled `public` tables into `core`/`collection`/`intelligence`/`ai_infra`/`user_prefs`, matching the codebase's existing DDD bounded contexts, with zero behavior change.

**Independent Test**: Run `make migrate`, then query `information_schema.tables` and confirm the 3/5/10/3/3 distribution from data-model.md §2; run `make test` + `make test-integration` and confirm they still pass unmodified; run `make migrate-down` and confirm every table returns to `public`.

### Tests for User Story 1

> Write these first — T003 fails until the model updates below land; T004 fails until the migration (T005) lands.

- [ ] T003 [P] [US1] Add schema-assertion tests to `src/tests/unit/infrastructure/persistence/test_orm_models.py` — one assertion per moved model, `<Model>.__table__.schema == DbSchema.<X>.value`, covering all 24 tables per the data-model.md §2 mapping (no DB required — matches this file's existing style, e.g. `test_topic_model_columns`)
- [ ] T004 [P] [US1] Add `src/tests/integration/test_db_schema_migration.py` (`@pytest.mark.integration`) — after `alembic upgrade head` has run (already guaranteed by the CI job order per `.github/workflows/ci.yml`), query `information_schema.tables` and assert: the 5 new schemas exist, contain exactly the tables listed in data-model.md §2, and `public` contains only `data_migrations`, `arxiv_metadata`, `alembic_version`

### Implementation for User Story 1

- [ ] T005 [US1] Create `alembic/versions/24_reorganize_public_schema_into_ddd_schemas.py` — `upgrade()`: 5× `CREATE SCHEMA IF NOT EXISTS`, then `ALTER TABLE public.<table> SET SCHEMA <schema>` for all 24 tables in data-model.md §2's mapping; `downgrade()`: reverse every move back to `public`, then `DROP SCHEMA IF EXISTS` the 5 schemas
- [ ] T006 [P] [US1] Update `models/article.py` — `__table_args__` → `{'schema': DbSchema.CORE.value}`; requalify `ForeignKey('topics.id')` → `ForeignKey('core.topics.id')`
- [ ] T007 [P] [US1] Update `models/article_translation.py` — `__table_args__` → `DbSchema.CORE`; requalify `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [ ] T008 [P] [US1] Update `models/topic.py` — `__table_args__` → `{'schema': DbSchema.CORE.value}` (no FKs to requalify)
- [ ] T009 [P] [US1] Update `models/scraper_setting.py` — `__table_args__` → `{'schema': DbSchema.COLLECTION.value}` (no FKs to requalify)
- [ ] T010 [P] [US1] Update `models/scraper_keyword.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('topics.id', ...)` → `'core.topics.id'`
- [ ] T011 [P] [US1] Update `models/failed_task.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('articles.id')` → `'core.articles.id'` and `ForeignKey('analyses.id', ...)` → `'intelligence.analyses.id'`
- [ ] T012 [P] [US1] Update `models/article_metrics.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [ ] T013 [P] [US1] Update `models/article_metric_value.py` — `__table_args__` → `DbSchema.COLLECTION`; requalify `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [ ] T014 [P] [US1] Update `models/analysis.py` — `__table_args__` → `{'schema': DbSchema.INTELLIGENCE.value}`; requalify `ForeignKey('articles.id')` → `'core.articles.id'`
- [ ] T015 [P] [US1] Update `models/analyses_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('analyses.id', ...)` → `'intelligence.analyses.id'`
- [ ] T016 [P] [US1] Update `models/tag.py` — `Tag.__table_args__` and the module-level `article_tags` association `Table(...)` both → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('tag_group_definitions.id', ...)`, `ForeignKey('articles.id')` → `'core.articles.id'`, `ForeignKey('tags.id')` → `'intelligence.tags.id'`
- [ ] T017 [P] [US1] Update `models/tag_group.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('topics.id')` → `'core.topics.id'`
- [ ] T018 [P] [US1] Update `models/tag_group_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('tag_group_definitions.id')` → `'intelligence.tag_group_definitions.id'`
- [ ] T019 [P] [US1] Update `models/tag_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('tags.id')` → `'intelligence.tags.id'`
- [ ] T020 [P] [US1] Update `models/tag_normalization_suggestion.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify both `ForeignKey('tags.id', ...)` → `'intelligence.tags.id'` and `ForeignKey('articles.id', ...)` → `'core.articles.id'`
- [ ] T021 [P] [US1] Update `models/weekly_report.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('topics.id', ...)` → `'core.topics.id'`
- [ ] T022 [P] [US1] Update `models/weekly_report_translation.py` — `__table_args__` → `DbSchema.INTELLIGENCE`; requalify `ForeignKey('weekly_reports.id', ...)` → `'intelligence.weekly_reports.id'`
- [ ] T023 [P] [US1] Update `models/llm_provider.py` — `__table_args__` → `{'schema': DbSchema.AI_INFRA.value}` (no FKs to requalify)
- [ ] T024 [P] [US1] Update `models/metric_definition.py` — `__table_args__` → `{'schema': DbSchema.AI_INFRA.value}` (no FKs to requalify)
- [ ] T025 [P] [US1] Update `models/metric_provider.py` — `__table_args__` → `DbSchema.AI_INFRA`; requalify `ForeignKey('metric_definitions.id', ...)` → `'ai_infra.metric_definitions.id'`
- [ ] T026 [P] [US1] Update `models/user_subscription.py` — all 3 classes' (`UserTopicSubscription`, `UserNotificationSettings`, `UserArticleFavorite`) `__table_args__` → `DbSchema.USER_PREFS`; requalify `ForeignKey('topics.id', ...)` → `'core.topics.id'` and `ForeignKey('articles.id', ...)` → `'core.articles.id'`; leave the `ForeignKey('auth.users.id', ...)` FKs unchanged
- [ ] T027 [P] [US1] Update `models/article_chunk.py` — cross-boundary fix only: requalify `ForeignKey("articles.id", ...)` → `"core.articles.id"`; do **not** change its own `__table_args__` (stays `vectors`, out of scope)
- [ ] T028 [US1] Delete `models/arxiv_keyword.py`; remove the now-obsolete `# NOTE: models.arxiv_keyword is intentionally excluded...` comment block from `models/__init__.py`
- [ ] T029 [P] [US1] Fix raw SQL in `src/entrypoints/cli/refresh_metrics.py` — `FROM articles` → `FROM core.articles`
- [ ] T030 [P] [US1] Fix raw SQL in `src/infrastructure/persistence/intelligence/tag_repo_impl.py` — requalify `tags`, `article_tags`, `articles`, `tag_group_definitions` references (multiple lines — see research.md's grep findings) to `intelligence.*`/`core.articles`
- [ ] T031 [P] [US1] Fix raw SQL in `src/infrastructure/persistence/intelligence/tag_group_definition_repo_impl.py` — requalify `tag_group_definitions` references to `intelligence.tag_group_definitions`
- [ ] T032 [P] [US1] Fix raw SQL in `backend/routers/tags.py` — requalify `article_tags`, `tags`, `tag_group_definitions`, `articles` references
- [ ] T033 [P] [US1] Fix raw SQL in `backend/services/scraper_settings_service.py` — `FROM articles` → `FROM core.articles`
- [ ] T034 [P] [US1] Fix raw SQL in `backend/services/tag_service.py` — requalify `tag_group_definitions`, `article_tags`, `tags` references
- [ ] T035 [P] [US1] Fix raw SQL in `backend/services/article_service.py` — requalify the `article_metrics` reference to `collection.article_metrics`
- [ ] T036 [US1] Extend `FIXED_SCHEMAS = {"auth", "vectors"}` in `src/tests/integration/conftest.py` to also include `"core"`, `"collection"`, `"intelligence"`, `"ai_infra"`, `"user_prefs"` (research.md §8 — required or the isolated-schema `create_all()` breaks)
- [ ] T037 [US1] Extend `FIXED_SCHEMAS = {"auth", "vectors"}` in `backend/tests/integration/conftest.py` the same way (research.md §8)

**Checkpoint**: `make test` and `make test-integration` pass with zero modifications to existing test *assertions* (only the two `conftest.py` files change); T003/T004 pass; quickstart.md §1–2 succeed end to end. User Story 1 is independently shippable here.

---

## Phase 4: User Story 2 - Auto-Generated Database Diagram in the Docs Site (Priority: P2)

**Goal**: A new VitePress page showing every table/column/FK/schema, generated by static AST analysis of `models/`, wired into the existing docs pipeline.

**Independent Test**: Run `scripts/generate_db_schema.py` locally, confirm it emits an SVG under `site/public/guide/architecture/`; build the site (`npm run build` in `site/`) and confirm the new page renders and is reachable from nav.

### Tests for User Story 2

- [ ] T038 [P] [US2] Add `scripts/tests/test_generate_db_schema.py` — cover: dict-form `__table_args__` (e.g. `auth.py`-style), tuple-form `__table_args__` (e.g. `article_chunk.py`-style), `DbSchema.<MEMBER>.value` attribute-chain resolution, cross-schema FK detection, and a fail-loud case for an unparseable model (FR-010) — matches the `scripts/tests/` convention already used for `generate_uml.py`

### Implementation for User Story 2

- [ ] T039 [US2] Implement `scripts/generate_db_schema.py` — static `ast`-parse every file in `models/` (excluding `__init__.py`, `base.py`, `types.py`, `db_schema.py`) into the `TableInfo`/`ColumnInfo`/`ForeignKeyInfo` shape from data-model.md §3, group into one Graphviz subgraph per schema, render cross-schema FK edges with a distinct style, emit `.dot` and render to `.svg` via `dot` into `site/public/guide/architecture/`; fail non-zero on any unparseable model
- [ ] T040 [US2] Add a "Generate DB schema diagram" step to `.github/workflows/speckit-github-pages.yml`, immediately after the existing "Generate backend UML (pyreverse)" step, running `python scripts/generate_db_schema.py`
- [ ] T041 [US2] Create `site/guide/architecture/db-schema.md` embedding the generated SVG (escaping any bare `<...>` in rendered column-type text per constitution VII's VitePress-markdown rule — e.g. `Vector(768)`, `list[str]`)
- [ ] T042 [US2] Add a "DB Schema" nav/sidebar entry in `site/.vitepress/config.js`, alongside the existing "Pipeline" (`/guide/architecture/uml`) and "Frontend Dependencies" (`/guide/architecture/deps`) entries

**Checkpoint**: quickstart.md §3–4 succeed; the diagram page is live in a local VitePress build. Independently shippable — does not require User Story 3.

---

## Phase 5: User Story 3 - Centralized Backend Configuration (Priority: P3)

**Goal**: `backend/config.py` becomes the single place `backend/` reads environment variables, closing the pre-existing constitution IX compliance gap.

**Independent Test**: `grep -rn "os\.environ\|os\.getenv" backend/ --include="*.py" | grep -v backend/tests | grep -v backend/config.py` returns nothing; `backend/tests/` passes unmodified.

### Tests for User Story 3

- [ ] T043 [P] [US3] Add `backend/tests/test_config.py` — for each constant in `backend/config.py`, set the env var via `monkeypatch`/`os.environ` and assert the module reflects it (matching how `src/tests/unit/config/test_config.py` tests `src/config/settings.py`)

### Implementation for User Story 3

- [ ] T044 [US3] Create `backend/config.py` per data-model.md §4 — pure `os.environ.get(...)` reads only, no side effects, no imports from the rest of `backend/`: `DATABASE_URL`, `FRONTEND_ORIGIN`, `VIEW_COUNT_FLUSH_INTERVAL` (int-cast), `REDIS_URL` (shared default `"redis://redis:6379/0"`), `NEXTAUTH_SECRET`, `CHAT_SERVICE_URL`, `CHAT_SERVICE_API_KEY`, `GRAFANA_PROMETHEUS_URL`, `GRAFANA_PROMETHEUS_USER`, `GRAFANA_API_KEY`, `GRAFANA_LOKI_URL`, `GRAFANA_LOKI_USER`, `GRAFANA_TEMPO_URL`, `GRAFANA_TEMPO_USER`, `GEMINI_API_KEY`
- [ ] T045 [P] [US3] Migrate `backend/database.py` to import `DATABASE_URL` from `config.py` instead of calling `os.environ.get` directly
- [ ] T046 [P] [US3] Migrate `backend/main.py` to import `FRONTEND_ORIGIN` and `VIEW_COUNT_FLUSH_INTERVAL` from `config.py`
- [ ] T047 [P] [US3] Migrate `backend/auth/guards.py` (3 call sites) to import `NEXTAUTH_SECRET` from `config.py`
- [ ] T048 [P] [US3] Migrate `backend/middleware/logging.py` to import `NEXTAUTH_SECRET` from `config.py`
- [ ] T049 [P] [US3] Migrate `backend/services/article_service.py` to import `REDIS_URL` from `config.py`
- [ ] T050 [P] [US3] Migrate `backend/services/chat_service.py` to import `CHAT_SERVICE_URL` and `CHAT_SERVICE_API_KEY` from `config.py`
- [ ] T051 [P] [US3] Migrate `backend/services/tag_service.py` to import `GEMINI_API_KEY` from `config.py`
- [ ] T052 [P] [US3] Migrate `backend/routers/chat.py` to import `REDIS_URL` and `NEXTAUTH_SECRET` from `config.py`
- [ ] T053 [P] [US3] Migrate `backend/routers/articles.py` to import `REDIS_URL` from `config.py`
- [ ] T054 [US3] Migrate `backend/routers/grafana.py` (7 vars × 6 near-identical call sites) to import all 7 `GRAFANA_*` constants from `config.py`
- [ ] T055 [US3] Cross-check every var read by `backend/config.py` against the repo-root `.env.example`; add any missing entries

**Checkpoint**: quickstart.md §5 succeeds. Independently shippable — touches none of the files from US1/US2.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Whole-feature verification across all three stories

- [ ] T056 [P] Run `make test` and `make test-integration` (full suites, not just the new tests) and confirm zero regressions — the concrete evidence for SC-002
- [ ] T057 Walk through quickstart.md end to end (§1–§5) as the final acceptance pass
- [ ] T058 [P] Add a one-line pointer in `CLAUDE.md`'s "### ORM Models" section noting the `core`/`collection`/`intelligence`/`ai_infra`/`user_prefs` schema grouping and linking to the new `site/guide/architecture/db-schema.md` page

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
