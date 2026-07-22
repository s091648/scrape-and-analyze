"""Verifies migration 24 (016-db-schema-brushup) against the real, already-migrated
database — not the per-test isolated schema (see conftest.py's FIXED_SCHEMAS).
CI runs `alembic upgrade head` before this suite, so the target schemas are
guaranteed to exist by the time these tests run.
"""
import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "core": {"articles", "articles_translation", "topics"},
    "collection": {
        "scraper_settings", "scraper_keywords", "failed_tasks",
        "article_metrics", "article_metric_values",
    },
    "intelligence": {
        "analyses", "analyses_translation", "tags", "article_tags",
        "tag_group_definitions", "tag_group_definitions_translation",
        "tags_translation", "tag_normalization_suggestions",
        "weekly_reports", "weekly_reports_translation",
    },
    "ai_infra": {"llm_providers", "metric_definitions", "metric_providers"},
    "user_prefs": {
        "user_topic_subscriptions", "user_notification_settings",
        "user_article_favorites",
    },
}


@pytest.fixture(scope="module")
def root_engine():
    engine = create_engine(os.environ["DATABASE_URL"])
    yield engine
    engine.dispose()


def _tables_in_schema(root_engine, schema: str) -> set:
    with root_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
            {"schema": schema},
        )
        return {r[0] for r in rows}


@pytest.mark.parametrize("schema,tables", EXPECTED_TABLES.items())
def test_schema_contains_expected_tables(root_engine, schema, tables):
    assert _tables_in_schema(root_engine, schema) == tables


def test_public_has_no_leftover_app_tables(root_engine):
    public_tables = _tables_in_schema(root_engine, "public")
    moved_tables = {t for tables in EXPECTED_TABLES.values() for t in tables}
    assert not (public_tables & moved_tables)
    assert "data_migrations" in public_tables
