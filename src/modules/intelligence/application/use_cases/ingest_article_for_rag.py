from src.modules.intelligence.domain.services.rag_ingestion_service import RagIngestionService
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Phrases that indicate a bot-detection or access-denied page was scraped
# instead of real article content.
_BOT_DETECTION_MARKERS = (
    "verify that you're not a robot",
    "enable javascript and then reload",
    "javascript is disabled",
    "this requires javascript",
    "access denied",
    "please enable cookies",
)


class IngestArticleForRagUseCase:
    """
    Accepts pre-assembled full text from the event pipeline and delegates
    ingestion to the RAG infrastructure service.

    ``full_text`` carries the complete PDF text for arxiv/openalex sources,
    or the full article body for blog/RSS sources.  It is passed in-memory
    through the event chain and never persisted to the main database.

    Falls back to assembling text from article fields when ``full_text`` is
    empty (e.g. direct calls in tests or retry scenarios without event context).
    Silently skips ingestion when content is detected as bot-detection garbage.
    """

    def __init__(self, rag_ingestion_service: RagIngestionService) -> None:
        self._rag_ingestion_service = rag_ingestion_service

    def execute(self, article, full_text: str = "") -> None:
        if not full_text or not full_text.strip():
            full_text = self._build_full_text(article)

        if not full_text.strip():
            logger.warning("rag_ingest_skipped_empty", article_id=str(article.id), url=str(article.url))
            return

        if self._is_bot_detection(full_text):
            logger.warning(
                "rag_ingest_skipped_bot_content",
                article_id=str(article.id),
                url=str(article.url),
                preview=full_text[:120],
            )
            return

        # PostgreSQL rejects NUL bytes in text columns; strip them before ingestion.
        # PyMuPDF occasionally leaves \x00 in PDF-extracted text.
        full_text = full_text.replace('\x00', ' ')

        self._rag_ingestion_service.ingest(article, full_text)
        logger.debug("rag_ingested", article_id=str(article.id), chars=len(full_text))

    def _build_full_text(self, article) -> str:
        """Fallback: assemble text from persisted article fields."""
        parts: list[str] = []
        if article.title:
            parts.append(article.title)
        if article.content:
            parts.append(article.content)
        _meta = getattr(article, 'metadata', None) or getattr(article, 'metadata_', None) or {}
        sections: dict = _meta.get("sections") or {}
        for section_name, section_body in sections.items():
            if section_body and section_body.strip():
                parts.append(f"## {section_name}\n{section_body.strip()}")
        return "\n\n".join(parts)

    @staticmethod
    def _is_bot_detection(text: str) -> bool:
        lower = text.lower()
        return any(marker in lower for marker in _BOT_DETECTION_MARKERS)
