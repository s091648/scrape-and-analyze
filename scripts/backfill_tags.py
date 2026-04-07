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
import uuid as uuid_module

from sqlalchemy import text

# Ensure project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.providers import load_providers
from src.database import get_session
from src.utils.logging import get_logger

logger = get_logger(__name__)


def build_analyzer():
    """Build a ProviderChain from providers.toml (mirrors src/main.py logic)."""
    from src.analysis.provider_chain import ProviderChain, ProviderHandler
    from src.analysis.providers.gemini import GeminiProvider
    from src.analysis.providers.openrouter import OpenRouterProvider
    from src.analysis.strategies.leaky_bucket_strategy import LeakyBucketStrategy
    from src.analysis.strategies.no_op_strategy import NoOpStrategy

    handlers = []
    for cfg in load_providers():
        name = cfg['name']
        model = cfg['model']
        api_key = os.environ.get(cfg['api_key_env'], '')

        if name == 'gemini':
            provider = GeminiProvider(api_key=api_key, model=model)
        elif name == 'openrouter':
            provider = OpenRouterProvider(api_key=api_key, model=model)
        else:
            logger.warning("unknown_provider_skipped", name=name)
            continue

        s_cfg = cfg.get('strategy', {})
        if s_cfg.get('type') == 'leaky_bucket':
            strategy = LeakyBucketStrategy(
                rpm=s_cfg['rpm'],
                tpm=s_cfg['tpm'],
                rpd=s_cfg['rpd'],
            )
        else:
            strategy = NoOpStrategy()

        handlers.append(ProviderHandler(
            provider=provider,
            strategy=strategy,
            priority=cfg['priority'],
            name=name,
        ))

    if not handlers:
        raise ValueError("No valid providers configured in providers.toml")

    return ProviderChain(handlers=handlers)


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


def update_analysis(session, analysis_id, result, model_used, dry_run=False):
    """Overwrite pain_points/insights/innovations/token counts on the analyses row."""
    if dry_run:
        print(
            f"  [DRY RUN] Would update analysis {analysis_id}:"
            f" pain_points={result.pain_points[:50]!r}..."
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
            "pain_points":   result.pain_points,
            "insights":      result.insights,
            "innovations":   result.innovations,
            "summary":       result.summary,
            "model_used":    model_used,
            "input_tokens":  result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )


def run_backfill(session, provider, prompt, dry_run=False, limit=None):
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

        result = provider.analyze(row.content, prompt)
        if result is None:
            logger.error("backfill_llm_failed", title=row.title, article_id=str(article_id))
            skipped += 1
            continue

        upsert_tags_for_article(session, article_id, result.tag_groups, dry_run=dry_run)
        update_analysis(session, analysis_id, result, model_used=result.model_used, dry_run=dry_run)

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

    with open(_PROMPT_PATH) as f:
        prompt = f.read()

    provider = build_analyzer()
    session  = get_session()

    try:
        stats = run_backfill(
            session, provider, prompt,
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
