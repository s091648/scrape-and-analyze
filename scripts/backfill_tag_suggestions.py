#!/usr/bin/env python
# scripts/backfill_tag_suggestions.py
"""
One-off script: scan all existing tags with embeddings within the same group,
compare them pairwise via cosine similarity, and create TagNormalizationSuggestion
records for similar pairs.

This covers tags created before NormalizeTagsUseCase was introduced, which
were never compared against each other.

Note: even pairs above auto_merge_threshold are recorded as suggestions (not
auto-merged) because pre-existing tags may already have many linked articles —
admin review is safer.

Usage:
    uv run python scripts/backfill_tag_suggestions.py [--dry-run]
    uv run python scripts/backfill_tag_suggestions.py [--suggest-threshold 0.85] [--auto-merge-threshold 0.92]
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be created without writing to DB")
    parser.add_argument("--suggest-threshold", type=float, default=0.85,
                        help="Minimum similarity to create a suggestion (default: 0.85)")
    parser.add_argument("--auto-merge-threshold", type=float, default=0.92,
                        help="Similarity at/above which to flag as high-confidence (default: 0.92)")
    args = parser.parse_args()

    from src.shared.logging import get_logger
    logger = get_logger(__name__)

    from src.infrastructure.persistence.database import get_session, init_db
    from src.infrastructure.persistence.intelligence.tag_repo_impl import SqlAlchemyTagRepository
    from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
    from sqlalchemy import text

    init_db()
    session = get_session()
    tag_repo = SqlAlchemyTagRepository(session=session)

    # ── Load all tags with embeddings ──────────────────────────────────────
    from models.tag import Tag
    all_tags = (
        session.query(Tag)
        .filter(Tag.embedding.isnot(None))
        .order_by(Tag.tag_group_id)
        .all()
    )

    by_group: dict[str, list[Tag]] = defaultdict(list)
    for tag in all_tags:
        by_group[str(tag.tag_group_id)].append(tag)

    logger.info(
        "backfill_suggestions_start",
        total_tags=len(all_tags),
        groups=len(by_group),
        suggest_threshold=args.suggest_threshold,
        auto_merge_threshold=args.auto_merge_threshold,
        dry_run=args.dry_run,
    )

    # ── Pre-load existing suggestions to skip already-known pairs ──────────
    existing_pairs: set[tuple[str, str]] = set()
    existing_rows = session.execute(text(
        "SELECT new_tag_id::text, existing_tag_id::text FROM tag_normalization_suggestions"
    )).fetchall()
    for new_id, existing_id in existing_rows:
        existing_pairs.add((min(new_id, existing_id), max(new_id, existing_id)))

    logger.info("existing_suggestions_loaded", count=len(existing_pairs))

    # ── Process each group ────────────────────────────────────────────────
    processed_pairs: set[tuple[str, str]] = set(existing_pairs)
    suggestions_created = 0
    high_confidence = 0

    for group_name, tags in by_group.items():
        if len(tags) < 2:
            continue

        logger.info("processing_group", group=group_name, tag_count=len(tags))

        for tag in tags:
            tag_id = str(tag.id)
            embedding = list(tag.embedding)

            similar = tag_repo.find_similar(embedding, group_name, args.suggest_threshold)

            for similar_tag, score in similar:
                similar_id = str(similar_tag.id)

                # Skip self-match
                if similar_id == tag_id:
                    continue

                # Skip already-processed pairs
                pair = (min(tag_id, similar_id), max(tag_id, similar_id))
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)

                is_high = score >= args.auto_merge_threshold
                if is_high:
                    high_confidence += 1

                logger.info(
                    "similar_pair_found",
                    tag_a=tag.name,
                    tag_b=similar_tag.name,
                    group=group_name,
                    similarity=round(score, 4),
                    high_confidence=is_high,
                    dry_run=args.dry_run,
                )

                if not args.dry_run:
                    # tag = "new" (potential duplicate to merge away)
                    # similar_tag = "existing" (canonical tag to keep)
                    suggestion = TagNormalizationSuggestion(
                        new_tag_id=tag.id,
                        existing_tag_id=similar_tag.id,
                        similarity_score=score,
                        article_id=None,
                        created_at=datetime.now(timezone.utc),
                    )
                    tag_repo.save_suggestion(suggestion)
                    suggestions_created += 1

        if not args.dry_run:
            session.commit()

    logger.info(
        "backfill_suggestions_complete",
        suggestions_created=suggestions_created,
        high_confidence_pairs=high_confidence,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
