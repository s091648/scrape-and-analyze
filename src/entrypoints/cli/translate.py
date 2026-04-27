"""
Translation CLI — translate article analyses to other languages.

Usage:
    python -m src.entrypoints.cli.translate --language zh-TW

This can be run as a scheduled job to continuously translate new content.

Architecture:
    - Domain: Translation entity, TranslationRepository interface
    - Application: TranslateArticleUseCase (depends on LLMService, TranslationRepository)
    - Infrastructure: SqlAlchemyTranslationRepository
    - Bootstrap: build_translation_pipeline() assembles dependencies
"""
import argparse
import os
import sys

from src.config.settings import SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)

logger = get_logger(__name__)


SUPPORTED_LANGUAGES = {
    "zh-TW": "Traditional Chinese (Taiwan)",
    "zh-CN": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}


def main():
    parser = argparse.ArgumentParser(description="Translate article analyses")
    parser.add_argument(
        "--language",
        type=str,
        required=True,
        help="Target language code (e.g., zh-TW, zh-CN)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of articles to translate per run"
    )
    args = parser.parse_args()

    # ── 初始化 ─────────────────────────────────────────────────────────────
    validate_config()
    configure_logging()
    init_default_client(HttpClient.build_default())

    # ── 驗證語言 ───────────────────────────────────────────────────────────
    if args.language not in SUPPORTED_LANGUAGES:
        logger.error("unsupported_language", language=args.language)
        print(f"Error: Unsupported language '{args.language}'")
        print(f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}")
        sys.exit(1)

    # ── 組裝依賴（bootstrap）────────────────────────────────────────────────
    from src.bootstrap import build_translation_pipeline

    pipeline = build_translation_pipeline()
    translate_use_case = pipeline["use_case"]
    translation_repo = pipeline["translation_repository"]
    tag_translate_use_case = pipeline.get("tag_use_case")
    tag_translation_repo = pipeline.get("tag_translation_repository")

    # ── 取得需要翻譯的 analyses ────────────────────────────────────────────
    analyses = translation_repo.find_analyses_without_translation(args.language, args.limit)
    logger.info("translations_to_process", count=len(analyses), language=args.language)

    if not analyses:
        logger.info("no_translations_needed", language=args.language)
        print(f"No articles need translation to {args.language}")
    else:
        # ── 執行翻譯 ───────────────────────────────────────────────────────
        success_count = 0
        failed_count = 0

        for analysis_data in analyses:
            analysis_id = analysis_data["analysis_id"]

            logger.info(
                "translating_article",
                analysis_id=str(analysis_id),
                article_id=str(analysis_data["article_id"])
            )

            result = translate_use_case.execute(
                analysis_id=analysis_id,
                summary=analysis_data["summary"],
                pain_points=analysis_data["pain_points"],
                insights=analysis_data["insights"],
                innovations=analysis_data["innovations"],
                target_language=args.language,
            )

            if result.success:
                success_count += 1
                logger.info("translation_completed", analysis_id=str(analysis_id))
            else:
                failed_count += 1
                logger.warning("translation_failed", analysis_id=str(analysis_id))

        # ── 完成 ───────────────────────────────────────────────────────────
        logger.info(
            "translation_batch_completed",
            total=len(analyses),
            success=success_count,
            failed=failed_count
        )
        print(f"Article translation complete: {success_count}/{len(analyses)} successful")

    # ── 翻譯 tags & tag groups ─────────────────────────────────────────────
    if tag_translate_use_case and tag_translation_repo:
        tag_result = tag_translate_use_case.translate_tags(args.language, args.limit)
        if tag_result["total"] > 0:
            print(f"Tag translation: {tag_result['success']}/{tag_result['total']} successful")

        group_result = tag_translate_use_case.translate_groups(args.language, args.limit)
        if group_result["total"] > 0:
            print(f"Group translation: {group_result['success']}/{group_result['total']} successful")


if __name__ == "__main__":
    main()