"""
AnalyzeArticleUseCase — send an article to the LLM and persist the result.

Extracted from main.py:analyze_article().
Depends only on domain interfaces; no ORM, no session management.
Tracing spans are intentionally omitted here — they are cross-cutting
concerns added by the entry point (Phase 9).
"""
from uuid import UUID

from src.domain.entities.analysis import AnalysisEntity
from src.domain.entities.article import ArticleEntity
from src.domain.repositories.analysis_repository import AnalysisRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyzeArticleUseCase:

    def __init__(self, analyzer, analysis_repo: AnalysisRepository) -> None:
        """
        Args:
            analyzer:      ProviderChain instance (from src.analyzers).
            analysis_repo: Concrete AnalysisRepository (injected by entry point).
        """
        self._analyzer = analyzer
        self._analysis_repo = analysis_repo

    def execute(self, article: ArticleEntity, prompt: str, correlation_id: str) -> bool:
        """
        Analyse *article* with the LLM and persist the Analysis.

        Returns True on success, False if the LLM returned None or saving failed.
        """
        content = self._prepare_content(article)
        result = self._analyzer.analyze(content, prompt)

        if result is None:
            logger.error("analysis_returned_none", article_id=str(article.id),
                         url=article.url)
            return False

        analysis = AnalysisEntity(
            article_id=article.id,
            correlation_id=UUID(correlation_id),
            pain_points=result.pain_points,
            insights=result.insights,
            innovations=result.innovations,
            summary=result.summary,
            model_used=result.model_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            tag_groups=result.tag_groups or [],
        )

        try:
            self._analysis_repo.save(analysis)
        except Exception as e:
            logger.error("analysis_save_failed", article_id=str(article.id), error=str(e))
            return False

        logger.info("analysis_completed",
                    article_id=str(article.id),
                    model=result.model_used,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens)
        return True

    # ── private ───────────────────────────────────────────────────────────

    def _prepare_content(self, article: ArticleEntity) -> str:
        """
        Return LLM-ready text for *article*, applying source-specific extraction.

        For arxiv: sections are pre-extracted at scrape time into metadata["sections"].
        content holds the abstract for display — we use sections for analysis.
        """
        if article.source == "arxiv":
            sections: dict = article.metadata.get("sections") or {}
            if len(sections) >= 2:
                from src.ingestion.parsers.pdf_parser import PdfParser
                max_chars = PdfParser().max_chars
                combined = "\n\n".join(
                    f"{name.title()}\n{body}" for name, body in sections.items()
                )
                return combined[:max_chars]
            return article.metadata.get("abstract", article.content[:2000])
        return article.content
