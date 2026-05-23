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
WITH from_analyses AS (
    SELECT DISTINCT
        elem->>'group'  AS grp_name,
        ar.topic_id
    FROM analyses an
    JOIN articles ar ON ar.id = an.article_id
    CROSS JOIN LATERAL jsonb_array_elements(an.tag_groups) AS elem
    WHERE an.tag_groups IS NOT NULL
      AND jsonb_typeof(an.tag_groups) = 'array'
      AND (elem->>'group') IS NOT NULL
      AND (elem->>'group') <> ''
),
from_tags AS (
    SELECT DISTINCT
        t.tag_group_name  AS grp_name,
        ar.topic_id
    FROM tags t
    JOIN article_tags at2 ON at2.tag_id   = t.id
    JOIN articles     ar  ON ar.id        = at2.article_id
    WHERE t.tag_group_name IS NOT NULL
      AND t.tag_group_name <> ''
),
all_pairs AS (
    SELECT grp_name, topic_id FROM from_analyses
    UNION
    SELECT grp_name, topic_id FROM from_tags
)
SELECT ap.grp_name, ap.topic_id
FROM   all_pairs ap
WHERE  NOT EXISTS (
    SELECT 1
    FROM   tag_group_definitions tgd
    WHERE  tgd.name      = ap.grp_name
      AND  tgd.topic_id  = ap.topic_id
)
ORDER BY ap.grp_name
"""


def up(session) -> None:
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
