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

_SQL_ORPHAN_ANALYSES = """
SELECT
    elem->>'group'   AS grp_name,
    tp.name          AS topic_name,
    COUNT(DISTINCT an.id) AS analysis_count
FROM analyses an
JOIN articles ar ON ar.id = an.article_id
JOIN topics   tp ON tp.id = ar.topic_id
CROSS JOIN LATERAL jsonb_array_elements(an.tag_groups) AS elem
WHERE an.tag_groups IS NOT NULL
  AND jsonb_typeof(an.tag_groups) = 'array'
  AND (elem->>'group') IS NOT NULL
  AND (elem->>'group') <> ''
  AND (:topic IS NULL OR tp.name = :topic)
  AND NOT EXISTS (
      SELECT 1
      FROM   tag_group_definitions tgd
      WHERE  tgd.name     = elem->>'group'
        AND  tgd.topic_id = ar.topic_id
  )
GROUP BY elem->>'group', tp.name
ORDER BY analysis_count DESC, grp_name
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

    # ── Section 2: orphan group keys in analyses.tag_groups ───────────────────
    orphan_analyses = session.execute(text(_SQL_ORPHAN_ANALYSES), params).fetchall()
    print(f"\n[2] analyses.tag_groups keys with no matching definition: {len(orphan_analyses)} group(s)\n")
    if orphan_analyses:
        print(f"  {'GROUP KEY':<40} {'TOPIC':<20} {'# ANALYSES'}")
        print("  " + "-" * 70)
        for row in orphan_analyses:
            print(f"  {row.grp_name:<40} {row.topic_name:<20} {row.analysis_count}")
    else:
        print("  ✓ none")

    total = len(orphan_tags) + len(orphan_analyses)
    print(f"\n{'═' * 55}")
    print(f"  Total issues: {total}")
    if total:
        print("  Run: make backfill-tag-group-definitions to fix")
    print()

    session.close()


if __name__ == "__main__":
    main()
