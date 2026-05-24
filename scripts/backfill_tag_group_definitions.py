#!/usr/bin/env python
# scripts/backfill_tag_group_definitions.py
"""
Script B — Auto-create missing tag_group_definitions.

Scans two sources for (group_name, topic_id) pairs that have no matching
tag_group_definitions row, then inserts them with:
    display_name = "<name>_unsupervised"

This is the standalone version of data migration 001. The data migration
framework (run_data_migrations.py) tracks whether this has been run.

Sources:
  1. analyses.tag_groups JSONB — historical LLM-generated group keys
  2. tags.tag_group_name      — orphaned denormalized group names

Usage:
    python scripts/backfill_tag_group_definitions.py [--dry-run] [--topic NAME]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

_SQL_MISSING_PAIRS = """
SELECT DISTINCT
    t.tag_group_name  AS grp_name,
    ar.topic_id,
    tp.name           AS topic_name
FROM tags t
JOIN article_tags at2 ON at2.tag_id   = t.id
JOIN articles     ar  ON ar.id        = at2.article_id
JOIN topics       tp  ON tp.id        = ar.topic_id
WHERE t.tag_group_name IS NOT NULL
  AND t.tag_group_name <> ''
  AND (:topic IS NULL OR tp.name = :topic)
  AND NOT EXISTS (
      SELECT 1
      FROM   tag_group_definitions tgd
      WHERE  tgd.name     = t.tag_group_name
        AND  tgd.topic_id = ar.topic_id
  )
ORDER BY tp.name, t.tag_group_name
"""


def main():
    parser = argparse.ArgumentParser(
        description="Auto-create missing tag_group_definitions"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned inserts without writing")
    parser.add_argument("--topic", default=None,
                        help="Restrict to a specific topic name")
    args = parser.parse_args()

    from src.infrastructure.persistence.database import get_session, init_db
    from src.shared.logging import get_logger

    logger = get_logger(__name__)
    init_db()
    session = get_session()

    rows = session.execute(
        text(_SQL_MISSING_PAIRS), {"topic": args.topic}
    ).fetchall()

    logger.info("backfill_tag_group_defs_start",
                total=len(rows), dry_run=args.dry_run)

    inserted = 0
    for row in rows:
        grp_name = row.grp_name
        topic_id = str(row.topic_id)
        topic_name = row.topic_name
        display_name = f"{grp_name}_unsupervised"

        if args.dry_run:
            print(f"  [DRY RUN] INSERT tag_group_definitions"
                  f" name={grp_name!r} display_name={display_name!r}"
                  f" topic={topic_name}")
            inserted += 1
            continue

        session.execute(
            text("""
                INSERT INTO tag_group_definitions
                    (id, name, display_name, topic_id)
                VALUES
                    (gen_random_uuid(), :name, :display_name, :topic_id)
                ON CONFLICT (name, topic_id) DO NOTHING
            """),
            {"name": grp_name, "display_name": display_name, "topic_id": topic_id},
        )
        inserted += 1
        logger.info("tag_group_def_created", name=grp_name, topic=topic_name)

    if not args.dry_run:
        session.commit()

    prefix = "[DRY RUN] " if args.dry_run else ""
    logger.info("backfill_tag_group_defs_complete",
                inserted=inserted, dry_run=args.dry_run)
    print(f"\n{prefix}Done: {inserted} tag_group_definitions created "
          f"(out of {len(rows)} missing)")

    session.close()


if __name__ == "__main__":
    main()
