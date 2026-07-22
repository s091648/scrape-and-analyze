# Feature Specification: Database Schema Brush-Up & Auto-Generated Schema Diagram

**Feature Branch**: `016-db-schema-brushup`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Database schema brush-up (GitHub issue #91): all public-schema tables (other than `auth` and `vectors`, which already have their own PostgreSQL schema) are currently unorganized under `public`. Reorganize them into use-case-based PostgreSQL schemas via Alembic migrations, following the pattern already used for `auth`/`vectors`. Also add an AST-based step to the existing docs pipeline (`.github/workflows/speckit-github-pages.yml`) that reads the SQLAlchemy models and renders a database schema diagram (tables, columns, FK relationships, schema grouping) as a new page in the VitePress site."

## Clarifications

### Session 2026-07-19

- Q: How should the ~25 modeled `public` tables be grouped into use-case schemas? → A: Mirror the codebase's own DDD bounded contexts (`src/modules/collection/`, `src/modules/intelligence/`) instead of inventing new business vocabulary — 5 schemas: `core` (shared-kernel entities used by both contexts), `collection`, `intelligence`, `ai_infra` (cross-cutting LLM/metrics provider config used by both contexts), `user_prefs`.
- Q: `models/arxiv_keyword.py` maps to a table the live database no longer has — how to handle it? → A: Delete the model file. It is confirmed dead: `models/__init__.py` already deliberately excludes it from `Base.metadata` with a comment noting its table was dropped in migration 14.
- Q: What is `public.data_migrations` (added in migration 18, no ORM model) — an orphan to ignore, or something real? → A: It's an intentional, not-yet-fully-wired-up ledger for tracking legacy-data-conversion jobs (columns: `name`, `executed_at`, `rolled_back_at`) — not dead code. Treat it like `alembic_version`: leave it in `public`, out of scope for the schema move, no model added in this feature.
- Q: Should the 5 schema names be centralized as a shared Python constant instead of being hardcoded per-model? → A: Yes, in scope — add a `DbSchema(str, Enum)` (or equivalent) that every touched model's `__table_args__` references, so there's one source of truth the diagram generator can also read from.
- Q: Backend (`backend/`) reads ~23 files' worth of `os.environ`/`os.getenv` ad hoc, unlike `src/config/settings.py`'s centralized pattern — fold that cleanup into this feature? → A: Yes, in scope — add a `backend/config/settings.py` mirroring `src/config/settings.py`'s pure, side-effect-free style, and migrate the scattered call sites to read from it.
- Q: What should the 3 per-reader tables' schema be named, given `user` collides with PostgreSQL's reserved `USER` keyword? → A: `user_prefs`.

### Session 2026-07-21

- Q: Should the Swagger "Try it out" execution capability be restricted only within the docs-site embed, or at the backend's own live `/docs` endpoint? → A: At the backend source itself, via FastAPI's `swagger_ui_parameters`, toggleable through a `SWAGGER_TRY_IT_OUT_ENABLED` environment variable defaulting to disabled — so the restriction holds everywhere the live docs page is reachable, not just inside the docs-site iframe.
- Q: How should the exception catalog page organize the exception types it finds — mirror the existing UML viewer's two-stage folder→card navigation, or something simpler? → A: A single flat, searchable card grid — the actual dataset (~9-10 exception types across ~86 raise sites) is too small to justify a folder-grid navigation layer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tables Organized by DDD Bounded Context (Priority: P1)

A maintainer working on the scraper or backend opens the database and, instead of finding 26 unrelated tables dumped into `public`, finds them grouped into named PostgreSQL schemas that mirror the same bounded contexts already used in the codebase's domain layer (`core`, `collection`, `intelligence`, `ai_infra`, `user_prefs`) — the same way `auth` and `vectors` are already separated today. A table's schema membership should be predictable from knowing where its equivalent domain entity lives in `src/modules/`.

**Why this priority**: This is the core ask of issue #91 and the prerequisite for everything else — the diagram in User Story 2 is only useful once the grouping exists.

**Independent Test**: Connect to the database after the migration runs and confirm every previously-`public` table (except intentionally-excluded ones, see Assumptions) now lives under its new schema, application code still reads/writes those tables correctly, and no data was lost or altered.

**Acceptance Scenarios**:

1. **Given** the current database with 26 tables in `public` (plus `auth.users` and the `vectors` schema, already separated), **When** the migration runs, **Then** the 24 tables with a live ORM model are each moved into exactly one of the 5 new schemas (`core`, `collection`, `intelligence`, `ai_infra`, `user_prefs`) and no table remains in `public` except the 2 explicitly-excluded ones (see Assumptions).
2. **Given** the migration has run, **When** the scraper (`src/`) or backend (`backend/`) performs any existing read/write operation against a moved table, **Then** the operation succeeds exactly as before — no behavior change, no broken foreign keys, no permission errors for the database role the application connects as.
3. **Given** the migration has run, **When** an operator runs `alembic downgrade -1` (or the equivalent rollback), **Then** all moved tables return to `public` with their original structure and data intact.

---

### User Story 2 - Auto-Generated Database Diagram in the Docs Site (Priority: P2)

A maintainer (or a new engineer ramping up) opens the project's GitHub Pages documentation site and finds a dedicated page showing the full database schema as a diagram — every table, its columns, its foreign-key relationships, and which PostgreSQL schema it belongs to — without needing to run any tooling locally or connect to a database.

**Why this priority**: Delivers the visibility half of the ask, but depends on User Story 1's grouping existing first to be meaningful (the whole point is to show the new organization, not just the flat table list).

**Independent Test**: Trigger the `speckit-github-pages.yml` workflow (or run its new step locally) and confirm a new page appears in the built VitePress site containing an accurate, current diagram of all SQLAlchemy models under `models/`.

**Acceptance Scenarios**:

1. **Given** the current set of SQLAlchemy models in `models/`, **When** the docs workflow runs, **Then** it produces a diagram page listing every table, its columns, and its foreign-key relationships to other tables, grouped/labeled by PostgreSQL schema.
2. **Given** the diagram page is published, **When** a visitor navigates the VitePress site, **Then** the schema diagram page is reachable from the site's existing architecture/guide navigation (alongside the existing backend UML and frontend dependency graph pages).
3. **Given** a model in `models/` changes (a column is added, a table is renamed, a new table is introduced) on a later push, **When** the docs workflow next runs, **Then** the published diagram reflects the change automatically, with no manual step required to regenerate it.

---

### User Story 3 - Centralized Backend Configuration (Priority: P3)

A maintainer working in `backend/` wants to find and change environment-variable-driven configuration in one place, the same way `src/config/settings.py` already lets scraper maintainers do, instead of hunting through ~23 files that each call `os.environ`/`os.getenv` directly.

**Why this priority**: Genuinely useful and requested alongside this feature, but orthogonal to the DB schema move (no shared files, no shared migration risk) — it can be delivered and verified independently of User Stories 1 and 2, so it's sequenced last without blocking them.

**Independent Test**: Grep `backend/` for `os.environ`/`os.getenv` after this story ships and confirm none remain outside `backend/config.py` itself; run the backend test suite and confirm no behavior change.

**Acceptance Scenarios**:

1. **Given** the current ~23 backend files reading `os.environ`/`os.getenv` directly, **When** this story is implemented, **Then** all of them read configuration from a new `backend/config.py` module instead (pure, side-effect-free, reading env vars only — matching `src/config/settings.py`'s existing style).
2. **Given** the new `backend/config.py` module, **When** a required environment variable is missing at startup, **Then** the backend fails with the same clarity/behavior it does today (no silent fallback introduced, no behavior regression).

---

### User Story 4 - Read-Only API Docs & Exception Catalog in the Docs Site (Priority: P4)

A maintainer or new engineer browsing the project's docs site wants to explore the backend's REST API surface and see, for any exception the codebase can raise, exactly which files/functions raise it — without being able to accidentally execute a real request against the production backend from a public documentation page.

**Why this priority**: Purely additive documentation tooling, layered on top of the docs-site infrastructure already built for User Story 2's schema diagram — has no dependency on, or shared risk with, the schema move or config centralization, so it is sequenced last.

**Independent Test**:
1. Deploy the docs site with the backend URL configured; confirm the API docs page renders the live OpenAPI spec but the "Try it out" execute controls are absent, and confirm the same is true visiting the backend's own `/docs` endpoint directly.
2. Run the exception-catalog generator against the current codebase and confirm the published page lists every exception type currently raised in `backend/`, `src/`, `models/`, `shared/`, each with an accurate list of raise sites (file, line, enclosing function).

**Acceptance Scenarios**:

1. **Given** a deployed backend with the try-it-out toggle unset (default), **When** anyone visits the backend's `/docs` endpoint directly (not just through the docs site), **Then** the "Try it out" execute button is absent for every operation.
2. **Given** the docs site is built with a configured backend URL, **When** a visitor opens the new API docs page, **Then** they see the full interactive Swagger documentation (all endpoints, schemas, descriptions) embedded from the live backend, read-only.
3. **Given** the docs site is built without a configured backend URL, **When** a visitor opens the API docs page, **Then** they see a clear message explaining the URL is not configured, instead of a broken embed.
4. **Given** the current set of `raise` statements across `backend/`, `src/`, `models/`, `shared/`, **When** the exception-catalog generator runs, **Then** it produces a page listing every distinct exception type raised, each showing its definition location (for project-defined exceptions) and every file/line/function where it is raised.
5. **Given** the exception catalog page is published, **When** a maintainer searches for a specific exception name, **Then** matching exception types are filtered in place without navigating away.
6. **Given** a source file changes to add, remove, or move a `raise` statement, **When** the docs workflow next runs, **Then** the published exception catalog reflects the change automatically, with no manual step required.

---

### Edge Cases

- What happens to foreign keys that cross the new schema boundaries (e.g. `core.articles` referenced from `collection.article_metrics` and `intelligence.analyses`)? Cross-schema foreign keys are valid in PostgreSQL and MUST continue to work exactly as before — the diagram MUST clearly indicate when a relationship crosses a schema boundary.
- What happens to the database role(s) the scraper/backend connect as? They MUST retain the same read/write access to every moved table under its new schema as they had under `public`, so the migration causes zero application-level permission errors.
- What happens to any raw SQL (outside the ORM) in `src/`, `backend/`, or `alembic/` that references a table by unqualified name (e.g. `SELECT * FROM articles`)? These MUST be identified and updated to the new schema-qualified name (or rely on `search_path`) so they keep working post-migration.
- What happens if the docs workflow's model-reading step encounters a model it cannot parse (e.g. a dynamically-constructed table)? It MUST fail the workflow step loudly (matching the existing `pyreverse` step's behavior) rather than silently omitting tables from the diagram.
- What happens to tables that exist in the live database but have no corresponding SQLAlchemy model in `models/` (`data_migrations` — see Assumptions)? They are out of scope for the reorganization and MUST be left untouched in `public`.
- What happens to `models/arxiv_keyword.py`, whose table no longer exists? It MUST be deleted as part of this feature, along with the now-unnecessary exclusion comment in `models/__init__.py`.
- What happens if the exception-catalog generator encounters a bare `raise` (re-raise) whose enclosing `except` clause cannot be resolved to a single exception type? That raise site MUST be excluded from the catalog rather than misattributed to the wrong exception type.
- What happens if an operator explicitly sets the try-it-out toggle to enabled (e.g. on a staging backend)? The docs-site embed will then show a fully interactive, executable Swagger UI — this is an intentional operator escape hatch, not a scope violation, since the default remains disabled everywhere.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST reorganize the 24 in-scope tables (those with a live SQLAlchemy model) currently in the `public` PostgreSQL schema into 5 new schemas — `core`, `collection`, `intelligence`, `ai_infra`, `user_prefs` — grouped to mirror the existing DDD bounded contexts in `src/modules/`, using Alembic migrations that follow the same pattern already established for the `auth` and `vectors` schemas (`CREATE SCHEMA`, move/create tables, preserve constraints).
- **FR-002**: The migration MUST be reversible — a downgrade MUST move every affected table back to `public` with its structure and data unchanged.
- **FR-003**: The migration MUST NOT alter any table's columns, data, indexes, or foreign-key semantics — this is purely an organizational move between schemas, not a data model change.
- **FR-004**: Every SQLAlchemy model in `models/` for a moved table MUST be updated to declare its new schema via `__table_args__`, referencing a shared `DbSchema` enum (see FR-011) rather than a hardcoded string literal.
- **FR-005**: Any raw/unqualified SQL table references in `src/`, `backend/`, or `alembic/` MUST be surveyed and updated so they continue to resolve correctly after the schema reorganization.
- **FR-006**: The database role(s) used by the scraper and backend services MUST retain equivalent read/write access to every moved table under its new schema; the migration MUST include any necessary `GRANT` statements.
- **FR-007**: The system MUST generate a database schema diagram — showing tables, columns, foreign-key relationships, and each table's PostgreSQL schema — derived directly from the SQLAlchemy models in `models/` (an AST/static-analysis approach, consistent with how the existing workflow derives the backend UML via `pyreverse` and the frontend dependency graph via `madge`), not from a manually-maintained document.
- **FR-008**: Diagram generation MUST run as an additional step in the existing `.github/workflows/speckit-github-pages.yml` pipeline, using the same triggers as the rest of that workflow (version tag push, manual dispatch) — no separate workflow or manual regeneration step.
- **FR-009**: The generated diagram MUST be published as a new page in the `site/` VitePress site and be reachable through the site's existing navigation alongside the other auto-generated architecture pages.
- **FR-010**: If the diagram-generation step fails (e.g., a model cannot be introspected), the workflow step MUST fail visibly rather than publish an incomplete or silently-outdated diagram.
- **FR-011**: System MUST define the 5 schema names as a single shared Python enum (e.g. `DbSchema(str, Enum)`) that every touched model in `models/` references from its `__table_args__`, instead of each model hardcoding its own string literal.
- **FR-012**: `models/arxiv_keyword.py` MUST be deleted (dead code — its table no longer exists in the live database; `models/__init__.py` already excludes it), and the now-obsolete exclusion comment in `models/__init__.py` removed.
- **FR-013**: System MUST add a `backend/config.py` module, following `src/config/settings.py`'s existing pattern (pure functions/constants reading `os.environ` only, no database imports, no side effects), and MUST migrate every existing `os.environ`/`os.getenv` call site under `backend/` to read from it instead.
- **FR-014**: `public.data_migrations` MUST be left untouched in `public` — no schema move, no new ORM model added — since it has no corresponding SQLAlchemy model today (see Assumptions for why it's intentionally out of scope rather than overlooked).
- **FR-015**: System MUST provide a mechanism (an environment-variable toggle, defaulting to disabled) that, when disabled, removes the interactive "Try it out" / execute capability from the backend's own live Swagger UI (`/docs`) endpoint — not merely from any downstream embed of it.
- **FR-016**: The docs site MUST include a new page embedding the backend's live Swagger/OpenAPI documentation, sourced from a configurable backend URL (read from an environment variable at docs-build time, following the same mechanism already used for the existing Storybook embed), and MUST show a clear placeholder message when that URL is not configured.
- **FR-017**: System MUST generate an exception catalog — derived via static analysis of `raise` statements and exception class definitions across `backend/`, `src/`, `models/`, `shared/` (excluding test directories) — consistent with the AST/static-analysis approach already used for the backend UML and database schema diagrams (not a manually-maintained document).
- **FR-018**: For each distinct exception type found, the catalog MUST record every location where it is raised (file, line, enclosing function) and, for project-defined exception classes, their definition location.
- **FR-019**: Exception-catalog generation MUST run as an additional step in the existing `speckit-github-pages.yml` pipeline, publishing to the `site/` VitePress site and reachable through the site's existing architecture navigation, alongside the schema diagram and API docs pages.
- **FR-020**: If the exception-catalog generation step encounters a source file it cannot parse, the workflow step MUST fail visibly (matching the existing failure behavior of the UML/schema-diagram generation steps) rather than publish an incomplete catalog silently.

### Key Entities *(include if feature involves data)*

This feature reorganizes existing entities rather than introducing new ones. The final grouping mirrors the codebase's own DDD bounded contexts (`src/modules/collection/`, `src/modules/intelligence/`, and the `src/shared/domain/entities/` shared kernel) rather than a bespoke business taxonomy:

- **`core`** (shared kernel — used by both bounded contexts below, matching `src/shared/domain/entities/`) — `articles`, `articles_translation`, `topics`.
- **`collection`** (mirrors `src/modules/collection/`) — `scraper_settings`, `scraper_keywords`, `failed_tasks`, `article_metrics`, `article_metric_values`.
- **`intelligence`** (mirrors `src/modules/intelligence/`) — `analyses`, `analyses_translation`, `tags`, `article_tags`, `tags_translation`, `tag_group_definitions`, `tag_group_definitions_translation`, `tag_normalization_suggestions`, `weekly_reports`, `weekly_reports_translation`.
- **`ai_infra`** (cross-cutting provider configuration used by both `collection`, for citation-metric extraction, and `intelligence`, for LLM analysis — not itself domain logic of either) — `llm_providers`, `metric_definitions`, `metric_providers`.
- **`user_prefs`** (per-reader account data, referencing `auth.users` — already cross-schema today) — `user_topic_subscriptions`, `user_notification_settings`, `user_article_favorites`.

3 + 5 + 10 + 3 + 3 = 24 tables, plus the 1 excluded table (`data_migrations`, see Assumptions) and the already-dead `arxiv_keywords` (deleted, never really "in" `public` per FR-012) accounts for the ~26 tables originally believed to be in `public`.

Several tables have foreign keys that cross these boundaries (notably `core.topics`, referenced from `intelligence.tag_group_definitions`, `collection.scraper_keywords`, and `intelligence.weekly_reports`; and `core.articles`, referenced from `intelligence.tag_normalization_suggestions`, `collection.failed_tasks`, and `user_prefs.user_article_favorites`). These cross-schema relationships are expected and must be preserved, not eliminated — `core` exists specifically because these entities are legitimately shared.

**Exception type** (User Story 4) — every distinct exception class raised somewhere in `backend/`, `src/`, `models/`, `shared/`; classified as project-defined (has a definition location within these directories), framework (raised from an imported framework class, e.g. `HTTPException`), or built-in (raised from a Python built-in, e.g. `ValueError`). Each exception type has one or more **raise sites** (file, line, enclosing function).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 24 in-scope tables (every `public` table with a corresponding SQLAlchemy model) are assigned to exactly one of the 5 new schemas after the migration — zero in-scope tables remain in `public`.
- **SC-002**: All existing scraper and backend functionality continues to work with zero behavior change after the migration — no regressions in the existing automated test suites.
- **SC-003**: A maintainer or new engineer can find a complete, accurate, and current database diagram on the public docs site without running any local tooling, querying the database, or asking a teammate.
- **SC-004**: The published diagram never goes stale relative to `models/`: any model change is reflected the next time the docs site is deployed, with zero manual regeneration steps.
- **SC-005**: The schema migration runs against the production database via the existing `make migrate-remote` / CI `migrate` job path with zero data loss and no extended service outage.
- **SC-006**: Zero `os.environ`/`os.getenv` call sites remain in `backend/` outside `backend/config.py`, with zero behavior change in existing backend tests.
- **SC-007**: A maintainer or new engineer can browse the backend's full API surface on the public docs site without running any local tooling or connecting to the backend directly, and cannot trigger any real backend operation while doing so.
- **SC-008**: A maintainer can look up any exception type raised anywhere in the codebase and find every location it's raised from, on the public docs site, without grepping the codebase locally.

## Assumptions

- `models/arxiv_keyword.py` / table `arxiv_keywords` is confirmed dead (table dropped, `models/__init__.py` already excludes the model) and is deleted by this feature rather than migrated — see FR-012.
- `public.data_migrations` (added in migration 18) has no ORM model but is **not** dead code — it's an intentional, not-yet-fully-wired-up ledger for tracking legacy-data-conversion jobs. It is treated like `alembic_version`: left in `public`, out of scope for this feature's schema move, with no model added here (see FR-014). This is recorded in project memory so it isn't mistaken for cleanup-worthy debt in future work.
- **Correction (found during implementation)**: `arxiv_metadata` was believed to be a second no-model orphan table left in `public`. It is not — migration 22's `upgrade()` actually *drops* `arxiv_metadata` (the `create_table` block that misled the original survey is inside its `downgrade()`, restoring the table only on rollback). It does not exist in the live database at all, verified by querying `information_schema.tables` after applying this feature's migration. `data_migrations` is the only table left in `public`.
- A pre-existing mismatch was found between `models/article_chunk.py` (which FKs to public `articles.id` with a single `embedding` column) and the actual `vectors.article_chunks` table created by migration 21 (which FKs to `vectors.articles.id` and has separate `dense_vector`/`sparse_vector` columns). This is a pre-existing inconsistency unrelated to this feature's scope and is called out here only so it isn't mistaken for something this migration should fix.
- `ALTER TABLE ... SET SCHEMA` in PostgreSQL is a catalog-only metadata operation (no table rewrite, no data copy), so the migration is expected to be fast and low-risk the same way migrations 01 and 21 were; no special maintenance-window process beyond the existing CI `migrate` → `rollback-on-test-failure` safety net is assumed necessary.
- The diagram is a static, auto-generated page (image or rendered diagram-as-code, consistent with how the existing `pyreverse` UML output is presented) — not an interactive/queryable tool.
- The diagram page's exact visual format (e.g. Mermaid ER diagram vs. Graphviz image) is an implementation decision for the planning phase, not a product decision that needs to be pinned down here.
- `backend/config.py`'s exact API shape (module-level constants like `src/config/settings.py`, vs. a settings class/object) is an implementation decision for the planning phase; the binding constraint from this session is only that it must be a single centralized, pure (no DB imports, no side effects) module that every existing `os.environ`/`os.getenv` call site in `backend/` migrates to use. **Resolved in planning** (research.md §7): the module is a single flat file, `backend/config.py` — not a `config/` package — matching constitution IX's literal naming for the 3 named FastAPI microservices.
- The exception catalog (User Story 4) only covers exceptions the project's own code explicitly raises via a `raise` statement; exceptions raised deep inside third-party library internals that the project's code never explicitly raises are out of scope — not detectable via static AST analysis without tracing every dependency's source.
- Enabling the try-it-out toggle (e.g. for a staging backend) is an intentional operator escape hatch, not a scope violation — when set, the docs-site embed and the backend's own `/docs` will both show a fully interactive Swagger UI; the default everywhere remains disabled.
