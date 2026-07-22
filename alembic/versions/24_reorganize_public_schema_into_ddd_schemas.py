# alembic/versions/24_reorganize_public_schema_into_ddd_schemas.py
"""reorganize_public_schema_into_ddd_schemas

Move the 24 modeled `public`-schema tables into 5 new PostgreSQL schemas that
mirror the existing DDD bounded contexts (src/modules/collection/,
src/modules/intelligence/, src/shared/domain/entities/), following the same
CREATE SCHEMA + move pattern already used for `auth` (migration 01) and
`vectors` (migration 21). Purely organizational — no column/data/FK changes.

`data_migrations` (18) and `arxiv_metadata` (22) intentionally stay in
`public` — neither has a corresponding SQLAlchemy model. See spec.md
Assumptions (specs/016-db-schema-brushup) for why.

Revision ID: 24_reorganize_public_schema_into_ddd_schemas
Revises: 23_article_recommendation_weekly_report
Create Date: 2026-07-19
"""
from alembic import op

revision = '24_reorganize_public_schema_into_ddd_schemas'
down_revision = '23_article_recommendation_weekly_report'
branch_labels = None
depends_on = None


TABLE_TO_SCHEMA = {
    # core — shared kernel (src/shared/domain/entities/)
    'articles': 'core',
    'articles_translation': 'core',
    'topics': 'core',
    # collection — mirrors src/modules/collection/
    'scraper_settings': 'collection',
    'scraper_keywords': 'collection',
    'failed_tasks': 'collection',
    'article_metrics': 'collection',
    'article_metric_values': 'collection',
    # intelligence — mirrors src/modules/intelligence/
    'analyses': 'intelligence',
    'analyses_translation': 'intelligence',
    'tags': 'intelligence',
    'article_tags': 'intelligence',
    'tag_group_definitions': 'intelligence',
    'tag_group_definitions_translation': 'intelligence',
    'tags_translation': 'intelligence',
    'tag_normalization_suggestions': 'intelligence',
    'weekly_reports': 'intelligence',
    'weekly_reports_translation': 'intelligence',
    # ai_infra — cross-cutting LLM/metrics provider config
    'llm_providers': 'ai_infra',
    'metric_definitions': 'ai_infra',
    'metric_providers': 'ai_infra',
    # user_prefs — per-reader account data
    'user_topic_subscriptions': 'user_prefs',
    'user_notification_settings': 'user_prefs',
    'user_article_favorites': 'user_prefs',
}

SCHEMAS = ('core', 'collection', 'intelligence', 'ai_infra', 'user_prefs')


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    for table, schema in TABLE_TO_SCHEMA.items():
        op.execute(f"ALTER TABLE public.{table} SET SCHEMA {schema}")

    # Application code (both src/ and backend/) has raw SQL that references
    # these tables unqualified (e.g. `FROM articles`), relying on Postgres's
    # search_path resolution the same way it always has — the ORM already
    # resolves correctly regardless of search_path since SQLAlchemy compiles
    # explicit schema-qualified names from each model's __table_args__. Set
    # the database-level default search_path so unqualified references keep
    # finding the moved tables without touching every raw-SQL call site.
    db_name = op.get_bind().engine.url.database
    op.execute(
        f'ALTER DATABASE "{db_name}" SET search_path TO '
        "core, collection, intelligence, ai_infra, user_prefs, public"
    )


def downgrade() -> None:
    db_name = op.get_bind().engine.url.database
    op.execute(f'ALTER DATABASE "{db_name}" RESET search_path')

    for table, schema in TABLE_TO_SCHEMA.items():
        op.execute(f"ALTER TABLE {schema}.{table} SET SCHEMA public")

    for schema in SCHEMAS:
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
