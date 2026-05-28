"""
001_backfill_tag_group_definitions

Auto-create missing tag_group_definitions entries from two sources:
  1. Group names found in analyses.tag_groups JSONB (historical LLM output)
  2. tag_group_name values in tags that have no matching definition

All auto-created rows get display_name = "<name>_unsupervised" so admins
can distinguish them from hand-curated definitions in the dashboard.

down() only removes rows that are still unreferenced by any tag.
"""
from sqlalchemy import text

name = "001_backfill_tag_group_definitions"
description = "Auto-create missing tag_group_definitions from historical analyses + orphan tags"
requires_api = False

# The Alembic schema revision that introduced the structures this script depends on.
# Migration 17 added the embedding column to tag_group_definitions and auto_tag_groups
# to topics, which is when maintaining tag_group_definitions became critical.
alembic_revision = "17_add_vector_failed_task_and_auto_tag"

_SQL_MISSING_PAIRS = """
SELECT DISTINCT
    t.tag_group_name  AS grp_name,
    ar.topic_id
FROM tags t
JOIN article_tags at2 ON at2.tag_id   = t.id
JOIN articles     ar  ON ar.id        = at2.article_id
WHERE t.tag_group_name IS NOT NULL
  AND t.tag_group_name <> ''
  AND NOT EXISTS (
      SELECT 1
      FROM   tag_group_definitions tgd
      WHERE  tgd.name     = t.tag_group_name
        AND  tgd.topic_id = ar.topic_id
  )
ORDER BY t.tag_group_name
"""


def up(session) -> None:
    col_exists = session.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='tags' AND column_name='tag_group_name'"
    )).first()
    if not col_exists:
        print("    tags.tag_group_name no longer exists (dropped by migration 18).")
        print("    backfill was handled inline by migration 18 — nothing to do.")
        return

    rows = session.execute(text(_SQL_MISSING_PAIRS)).fetchall()
    if not rows:
        print("    no missing tag_group_definitions found")
        return

    for row in rows:
        grp_name = row[0]
        topic_id = str(row[1])
        display_name = f"{grp_name}_unsupervised"
        session.execute(
            text("""
                INSERT INTO tag_group_definitions (id, name, display_name, topic_id)
                VALUES (gen_random_uuid(), :name, :display_name, :topic_id)
                ON CONFLICT (name, topic_id) DO NOTHING
            """),
            {"name": grp_name, "display_name": display_name, "topic_id": topic_id},
        )
        print(f"    + {grp_name} (topic {topic_id[:8]}…)")

    session.commit()
    print(f"    inserted up to {len(rows)} tag_group_definitions")


def down(session) -> None:
    col_exists = session.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='tags' AND column_name='tag_group_name'"
    )).first()
    if not col_exists:
        print("    tags.tag_group_name no longer exists — down() is a no-op.")
        return

    result = session.execute(text("""
        DELETE FROM tag_group_definitions
        WHERE display_name LIKE '%_unsupervised'
          AND NOT EXISTS (
              SELECT 1 FROM tags t
              WHERE t.tag_group_name = tag_group_definitions.name
          )
        RETURNING name
    """))
    deleted = result.fetchall()
    session.commit()
    print(f"    removed {len(deleted)} unreferenced _unsupervised definitions")
