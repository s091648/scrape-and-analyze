#!/usr/bin/env python3
"""
Backfill normalized tags for articles that have analyses but no article_tags entries.

Usage:
    DATABASE_URL=... python scripts/backfill_tags.py [--dry-run] [--limit N]

Provider selection and rate limiting are controlled by providers.toml (same as main.py).
"""
import argparse
import os
import sys

from sqlalchemy import text

# Ensure project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bootstrap import build_llm_service
from src.infrastructure.persistence.database import get_session
from src.shared.logging import get_logger

from src.modules.intelligence.domain.value_objects import TagGroup

logger = get_logger(__name__)


_SQL_NEEDS_BACKFILL = """
    SELECT ar.id, ar.title, ar.content, ar.metadata_, ar.source, an.id AS analysis_id
    FROM articles ar
    JOIN analyses an ON an.article_id = ar.id
    LEFT JOIN article_tags at ON at.article_id = ar.id
    WHERE at.article_id IS NULL
    ORDER BY an.analyzed_at
"""


def find_articles_needing_backfill(session, limit=None):
    """Return rows for articles with an analyses row but no article_tags entries."""
    sql = _SQL_NEEDS_BACKFILL
    if limit is not None:
        return session.execute(text(sql + " LIMIT :limit"), {"limit": limit}).fetchall()
    return session.execute(text(sql)).fetchall()


def upsert_tags_for_article(session, article_id, tag_groups, dry_run=False):
    """Insert tag rows and article_tags entries for a single article.

    tag_groups is a list of TagGroup(display_name, description) NamedTuples.
    Tags are stored as comma-separated values in description.
    """
    import uuid as uuid_module
    for tg in tag_groups:
        group_name = tg.display_name
        for tag_name in tg.description.split(", "):
            tag_name = tag_name.strip()
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


def update_analysis(session, analysis_id, content, metadata, dry_run=False):
    """Overwrite pain_points/insights/innovations/token counts on the analyses row."""
    if dry_run:
        pain_points_preview = content.pain_points[:50] if content.pain_points else ""
        print(
            f"  [DRY RUN] Would update analysis {analysis_id}:"
            f" pain_points={pain_points_preview!r}..."
        )
        return
    session.execute(
        text("""
            UPDATE analyses
            SET pain_points   = :pain_points,
                insights      = :insights,
                innovations   = :innovations,
                summary       = :summary,
                model_used    = :model_used,
                input_tokens  = :input_tokens,
                output_tokens = :output_tokens
            WHERE id = :id
        """),
        {
            "id":            str(analysis_id),
            "pain_points":   content.pain_points,
            "insights":      content.insights,
            "innovations":   content.innovations,
            "summary":       content.summary,
            "model_used":    metadata.model_used,
            "input_tokens":  metadata.input_tokens,
            "output_tokens": metadata.output_tokens,
        },
    )


def run_backfill(session, llm_service, prompt, dry_run=False, limit=None):
    """
    Main backfill loop.

    Returns dict: {"processed": int, "skipped": int}
    """

    rows = find_articles_needing_backfill(session, limit=limit)
    processed = 0
    skipped = 0

    for row in rows:
        article_id  = row.id
        analysis_id = row.analysis_id
        logger.info("backfill_start", title=row.title, article_id=str(article_id))

        result = llm_service.analyze(row.content, prompt)
        if result is None:
            logger.error("backfill_llm_failed", title=row.title, article_id=str(article_id))
            skipped += 1
            continue

        content, metadata = result

        if content.tag_groups:
            upsert_tags_for_article(session, article_id, content.tag_groups, dry_run=dry_run)
        update_analysis(session, analysis_id, content, metadata, dry_run=dry_run)

        if not dry_run:
            session.commit()

        logger.info("backfill_done", title=row.title, article_id=str(article_id))
        processed += 1

    return {"processed": processed, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(
        description="Backfill normalized tags via LLM re-analysis (providers.toml)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print planned changes without writing to the database.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of articles to process.",
    )
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    from src.modules.intelligence.domain.value_objects import AnalysisPrompt
    prompt = AnalysisPrompt().content

    llm_service = build_llm_service()
    session = get_session()

    try:
        stats = run_backfill(
            session, llm_service, prompt,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    finally:
        session.close()

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(
        f"\n{prefix}Backfill complete: "
        f"{stats['processed']} processed, {stats['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
