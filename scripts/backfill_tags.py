#!/usr/bin/env python3
"""
Backfill normalized tags for articles that have analyses but no article_tags entries.

Usage:
    DATABASE_URL=... LLM_API_KEY=... python scripts/backfill_tags.py [--dry-run] [--limit N]
"""
import argparse
import os
import sys
import uuid as uuid_module

from sqlalchemy import text

# Ensure project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzers.gemini import GeminiProvider
from src.database import get_session
from src.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "prompts", "analysis.txt",
)

_SQL_NEEDS_BACKFILL = """
    SELECT ar.id, ar.title, ar.content, an.id AS analysis_id
    FROM articles ar
    JOIN analyses an ON an.article_id = ar.id
    LEFT JOIN article_tags at ON at.article_id = ar.id
    WHERE at.article_id IS NULL
    ORDER BY an.analyzed_at
"""


def find_articles_needing_backfill(session, limit=None):
    """Return rows for articles with an analyses row but no article_tags entries."""
    if limit is not None:
        return session.execute(
            text(_SQL_NEEDS_BACKFILL + " LIMIT :limit"), {"limit": limit}
        ).fetchall()
    return session.execute(text(_SQL_NEEDS_BACKFILL)).fetchall()


def upsert_tags_for_article(session, article_id, tag_groups, dry_run=False):
    """Insert tag rows and article_tags entries for a single article."""
    for group in tag_groups:
        group_name = group.get("group")
        for tag_name in group.get("tags", []):
            if not tag_name or not group_name:
                continue
            if dry_run:
                print(
                    f"  [DRY RUN] tag {tag_name!r} in group {group_name!r}"
                    f" -> article {article_id}"
                )
                continue
            session.execute(
                text("""
                    INSERT INTO tags (id, name, tag_group_name)
                    VALUES (:id, :name, :group_name)
                    ON CONFLICT (name, tag_group_name) DO NOTHING
                """),
                {"id": str(uuid_module.uuid4()), "name": tag_name, "group_name": group_name},
            )
            row = session.execute(
                text("SELECT id FROM tags WHERE name = :name AND tag_group_name = :group_name"),
                {"name": tag_name, "group_name": group_name},
            ).first()
            session.execute(
                text("""
                    INSERT INTO article_tags (article_id, tag_id)
                    VALUES (:article_id, :tag_id)
                    ON CONFLICT DO NOTHING
                """),
                {"article_id": str(article_id), "tag_id": str(row[0])},
            )
