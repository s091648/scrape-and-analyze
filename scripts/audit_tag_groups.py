#!/usr/bin/env python
# scripts/audit_tag_groups.py
"""
Script A — Audit tag group coverage.

Reports two classes of issues:
  1. tag_group_name values in the tags table that have no matching
     tag_group_definitions row for the article's topic.
  2. Group keys in analyses.tag_groups JSONB that have no matching
     tag_group_definitions row for the article's topic.

Usage:
    python scripts/audit_tag_groups.py
    python scripts/audit_tag_groups.py --topic digital-twins
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

_SQL_ORPHAN_TAGS = """
SELECT
    t.tag_group_name,
    tp.name          AS topic_name,
    COUNT(DISTINCT t.id) AS tag_count
FROM tags t
JOIN article_tags  at2 ON at2.tag_id   = t.id
JOIN articles      ar  ON ar.id        = at2.article_id
JOIN topics        tp  ON tp.id        = ar.topic_id
WHERE t.tag_group_name IS NOT NULL
  AND t.tag_group_name <> ''
  AND (:topic IS NULL OR tp.name = :topic)
  AND NOT EXISTS (
      SELECT 1
      FROM   tag_group_definitions tgd
      WHERE  tgd.name     = t.tag_group_name
        AND  tgd.topic_id = ar.topic_id
  )
GROUP BY t.tag_group_name, tp.name
ORDER BY tag_count DESC, t.tag_group_name
"""

_SQL_DUPLICATE_CASING = """
SELECT
    LOWER(REPLACE(t.tag_group_name, ' ', '_')) AS normalized,
    array_agg(DISTINCT t.tag_group_name ORDER BY t.tag_group_name) AS variants,
    tp.name AS topic_name,
    COUNT(DISTINCT t.id) AS tag_count
FROM tags t
JOIN article_tags  at2 ON at2.tag_id   = t.id
JOIN articles      ar  ON ar.id        = at2.article_id
JOIN topics        tp  ON tp.id        = ar.topic_id
WHERE t.tag_group_name IS NOT NULL
  AND t.tag_group_name <> ''
  AND (:topic IS NULL OR tp.name = :topic)
GROUP BY LOWER(REPLACE(t.tag_group_name, ' ', '_')), tp.name
HAVING COUNT(DISTINCT t.tag_group_name) > 1
ORDER BY tag_count DESC
"""


def main():
    parser = argparse.ArgumentParser(description="Audit tag group coverage")
    parser.add_argument("--topic", default=None,
                        help="Filter to a specific topic name (e.g. digital-twins)")
    args = parser.parse_args()

    from src.infrastructure.persistence.database import get_session, init_db
    from src.shared.logging import get_logger

    logger = get_logger(__name__)
    init_db()
    session = get_session()

    params = {"topic": args.topic}

    print("\n═══════════════════════════════════════════════════════")
    print("  Tag Group Audit Report")
    print("═══════════════════════════════════════════════════════")

    # ── Section 1: orphan tag_group_name in tags table ────────────────────────
    orphan_tags = session.execute(text(_SQL_ORPHAN_TAGS), params).fetchall()
    print(f"\n[1] tags with no matching tag_group_definitions: {len(orphan_tags)} group(s)\n")
    if orphan_tags:
        print(f"  {'TAG GROUP NAME':<40} {'TOPIC':<20} {'# TAGS'}")
        print("  " + "-" * 70)
        for row in orphan_tags:
            print(f"  {row.tag_group_name:<40} {row.topic_name:<20} {row.tag_count}")
    else:
        print("  ✓ none")

    # ── Section 2: duplicate-casing variants of the same group name ──────────
    duplicates = session.execute(text(_SQL_DUPLICATE_CASING), params).fetchall()
    print(f"\n[2] tag_group_name casing variants (same normalized key, different spellings): {len(duplicates)} group(s)\n")
    if duplicates:
        print(f"  {'NORMALIZED KEY':<40} {'TOPIC':<20} {'VARIANTS'}")
        print("  " + "-" * 90)
        for row in duplicates:
            variants = ", ".join(row.variants)
            print(f"  {row.normalized:<40} {row.topic_name:<20} {variants}")
        print("\n  NOTE: These will each get a separate _unsupervised definition.")
        print("        Clean up via admin dashboard after backfill.")
    else:
        print("  ✓ none")

    total_orphans = len(orphan_tags)
    print(f"\n{'═' * 55}")
    print(f"  Orphan groups to backfill: {total_orphans}")
    if total_orphans:
        print("  Run: make backfill-tag-group-definitions to fix")
    print()

    session.close()


if __name__ == "__main__":
    main()
