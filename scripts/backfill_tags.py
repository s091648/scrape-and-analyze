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
