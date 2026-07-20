# Data Model: Database Schema Brush-Up & Auto-Generated Schema Diagram

This feature reorganizes existing entities; it does not introduce new business entities. This document defines the three concrete artifacts `/speckit-tasks` needs to turn into work items: the `DbSchema` enum, the full table→schema migration mapping (with FK requalification), and the `backend/config.py` env-var inventory.

## 1. `DbSchema` enum (`models/db_schema.py`)

```python
from enum import Enum

class DbSchema(str, Enum):
    CORE = "core"
    COLLECTION = "collection"
    INTELLIGENCE = "intelligence"
    AI_INFRA = "ai_infra"
    USER_PREFS = "user_prefs"
```

- Every touched model's `__table_args__` schema key references this (e.g. `{'schema': DbSchema.CORE.value}`), never a hardcoded string.
- `auth` and `vectors` are **not** members — those schemas are untouched by this feature and keep their existing literal-string `__table_args__` (`models/auth.py`, `models/article_chunk.py`).
- The AST-based diagram generator (see §3) also statically parses this file to resolve `DbSchema.<MEMBER>` references found in other models' `__table_args__`.

## 2. Table → schema migration mapping

24 tables move; `data_migrations` stays in `public` untouched (no model, see spec.md Assumptions); `arxiv_keywords` model is deleted (dead — see spec.md Assumptions), not moved. `arxiv_metadata` was initially believed to be a second no-model orphan in `public` but turned out not to exist at all — migration 22's `upgrade()` drops it (the `create_table` survives only in `downgrade()`), confirmed empirically post-migration via `information_schema.tables`.

| Table | Model file | New schema | `ForeignKey` strings in this file needing requalification |
| --- | --- | --- | --- |
| `articles` | `article.py` | `core` | `topics.id` → `core.topics.id` |
| `articles_translation` | `article_translation.py` | `core` | `articles.id` → `core.articles.id` |
| `topics` | `topic.py` | `core` | (none) |
| `scraper_settings` | `scraper_setting.py` | `collection` | (none) |
| `scraper_keywords` | `scraper_keyword.py` | `collection` | `topics.id` → `core.topics.id` |
| `failed_tasks` | `failed_task.py` | `collection` | `articles.id` → `core.articles.id`; `analyses.id` → `intelligence.analyses.id` |
| `article_metrics` | `article_metrics.py` | `collection` | `articles.id` → `core.articles.id` |
| `article_metric_values` | `article_metric_value.py` | `collection` | `articles.id` → `core.articles.id` |
| `analyses` | `analysis.py` | `intelligence` | `articles.id` → `core.articles.id` |
| `analyses_translation` | `analyses_translation.py` | `intelligence` | `analyses.id` → `intelligence.analyses.id` |
| `tags` | `tag.py` | `intelligence` | `tag_group_definitions.id` → `intelligence.tag_group_definitions.id` |
| `article_tags` (assoc. `Table`) | `tag.py` | `intelligence` | `articles.id` → `core.articles.id`; `tags.id` → `intelligence.tags.id` |
| `tag_group_definitions` | `tag_group.py` | `intelligence` | `topics.id` → `core.topics.id` |
| `tag_group_definitions_translation` | `tag_group_translation.py` | `intelligence` | `tag_group_definitions.id` → `intelligence.tag_group_definitions.id` |
| `tags_translation` | `tag_translation.py` | `intelligence` | `tags.id` → `intelligence.tags.id` |
| `tag_normalization_suggestions` | `tag_normalization_suggestion.py` | `intelligence` | `tags.id` → `intelligence.tags.id` (×2); `articles.id` → `core.articles.id` |
| `weekly_reports` | `weekly_report.py` | `intelligence` | `topics.id` → `core.topics.id` |
| `weekly_reports_translation` | `weekly_report_translation.py` | `intelligence` | `weekly_reports.id` → `intelligence.weekly_reports.id` |
| `llm_providers` | `llm_provider.py` | `ai_infra` | (none) |
| `metric_definitions` | `metric_definition.py` | `ai_infra` | (none) |
| `metric_providers` | `metric_provider.py` | `ai_infra` | `metric_definitions.id` → `ai_infra.metric_definitions.id` |
| `user_topic_subscriptions` | `user_subscription.py` | `user_prefs` | `auth.users.id` unchanged; `topics.id` → `core.topics.id` |
| `user_notification_settings` | `user_subscription.py` | `user_prefs` | `auth.users.id` unchanged |
| `user_article_favorites` | `user_subscription.py` | `user_prefs` | `auth.users.id` unchanged; `articles.id` → `core.articles.id` |

**Cross-boundary edge case** (model not itself moving, but its FK target is): `models/article_chunk.py` (`vectors.article_chunks`) has `ForeignKey("articles.id")` → must become `ForeignKey("core.articles.id")`.

**Alembic migration** (`alembic/versions/24_reorganize_public_schema_into_ddd_schemas.py`) `upgrade()` shape:

```python
for schema in ("core", "collection", "intelligence", "ai_infra", "user_prefs"):
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

for table, schema in TABLE_TO_SCHEMA.items():  # the 24-row mapping above
    op.execute(f"ALTER TABLE public.{table} SET SCHEMA {schema}")
```

`downgrade()` reverses each `ALTER TABLE <schema>.<table> SET SCHEMA public`, then drops the 5 schemas (`DROP SCHEMA IF EXISTS <x>` — safe since nothing else lives in them after the reverse-move).

## 3. Diagram generator data model (`scripts/generate_db_schema.py`)

Internal representation the AST parser builds per model class found in `models/*.py`, mirroring what `scripts/generate_uml.py` does for classes but sourced from SQLAlchemy declarative syntax instead of generic Python structure:

```python
@dataclass
class ColumnInfo:
    name: str
    type_repr: str          # e.g. "UUID", "String(255)", "Vector(768)" — rendered as text, not executed
    nullable: bool
    is_primary_key: bool

@dataclass
class ForeignKeyInfo:
    column: str
    target_schema: str       # resolved from the literal string OR DbSchema.<MEMBER> attribute chain
    target_table: str
    target_column: str

@dataclass
class TableInfo:
    name: str                 # __tablename__
    schema: str                # resolved schema (default "public" if no __table_args__ schema key found)
    model_class: str
    source_file: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]
```

Parsing rules (see research.md §4 for the `__table_args__` dict-vs-tuple and enum-resolution details):

1. Walk every `.py` file directly under `models/` (excluding `__init__.py`, `base.py`, `types.py`, `db_schema.py` itself).
2. For each `ast.ClassDef` whose bases include `Base`, extract `__tablename__` (string literal) and resolve `schema` from `__table_args__` (dict literal, or last element of a tuple literal) — defaulting to `"public"` only for models this feature doesn't touch that have no explicit schema key (none currently exist among in-scope models, but the parser must not crash if one appears later).
3. For `Table(...)` calls at module level (the `article_tags` association table in `tag.py`) — same extraction logic, since it isn't a `ClassDef`.
4. For each `Column(...)` call assigned to a class attribute, extract the column name (from the assignment target), and if a `ForeignKey(...)` call appears among its arguments, parse the literal string argument into `schema.table.column` (splitting on `.`; a 2-part string with no schema prefix means the target is `public`-schema-implicit as of this feature's completion, e.g. a `data_migrations`-referencing FK, none of which currently exist).
5. Output: one `TableInfo` per table, grouped by `schema` for the `.dot` subgraph rendering (one visual cluster per PostgreSQL schema, matching the existing UML diagram's per-layer subgraph convention), with cross-schema FK edges rendered distinctly (e.g. a different edge color/style) per spec.md's edge-case requirement ("the diagram MUST clearly indicate when a relationship crosses a schema boundary").
6. Any model that fails to parse (unexpected AST shape) MUST raise and fail the script (FR-010 — no silent omission), matching `generate_uml.py`'s existing fail-loud behavior for pyreverse errors.

## 4. `backend/config.py` — env var inventory

Every current `os.environ.get`/`os.getenv`/`os.environ[...]` **read** call site under `backend/` (excludes test-fixture *writes* like `os.environ["NEXTAUTH_SECRET"] = "test-secret"`, which stay in test setup — `config.py` is only for reads):

| Env var | Current call site(s) | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `database.py` | Also read directly in `tests/integration/conftest.py:17` — candidate to keep as direct test-infra read; verify during implementation whether importing `config.py` there is safe (import-time DB engine creation risk). |
| `FRONTEND_ORIGIN` | `main.py` | |
| `VIEW_COUNT_FLUSH_INTERVAL` | `main.py` | Parsed as `int(...)` — `config.py` should own the cast, matching `src/config/settings.py`'s `_int_or_none` helper style. |
| `REDIS_URL` | `services/article_service.py`, `routers/chat.py`, `routers/articles.py` | 3 call sites, all with the same fallback default `"redis://redis:6379/0"` — good DRY candidate. |
| `NEXTAUTH_SECRET` | `auth/guards.py` (×3), `middleware/logging.py`, `routers/chat.py` | Also set directly by ~7 test files before import — those are legitimate test fixtures, not migration targets. |
| `CHAT_SERVICE_URL`, `CHAT_SERVICE_API_KEY` | `services/chat_service.py` | |
| `GRAFANA_PROMETHEUS_URL`, `GRAFANA_PROMETHEUS_USER`, `GRAFANA_API_KEY`, `GRAFANA_LOKI_URL`, `GRAFANA_LOKI_USER`, `GRAFANA_TEMPO_URL`, `GRAFANA_TEMPO_USER` | `routers/grafana.py` | Same 7 vars re-read in 6 different functions in this one file — highest-value single-file cleanup target. |
| `GEMINI_API_KEY` | `services/tag_service.py` | |

All of the above already appear in the repo-root `.env.example` except none found missing in the spot-check during planning; `/speckit-tasks` should include a task to re-verify the full set against `.env.example` and add any gaps (constitution IX requirement).
