from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.intelligence.application.use_cases.ingest_article_for_rag import AsyncIngestArticleForRagUseCase
from src.modules.intelligence.domain.services.rag_ingestion_service import AsyncRagIngestionService
from src.shared.domain.entities.article import Article


def _make_article(content="Abstract text.", metadata=None):
    return Article(
        id=uuid4(),
        url="https://arxiv.org/abs/2401.00001",
        url_hash="abc",
        source="arxiv",
        title="A Research Paper",
        content=content,
        metadata=metadata or {},
    )


def _make_use_case():
    service = MagicMock(spec=AsyncRagIngestionService)
    service.ingest = AsyncMock()
    return AsyncIngestArticleForRagUseCase(service), service


@pytest.mark.asyncio
async def test_async_execute_passes_full_text_to_service():
    uc, service = _make_use_case()
    article = _make_article()
    full_text = "Complete PDF text including all sections."

    await uc.execute(article, full_text)

    service.ingest.assert_awaited_once_with(article, full_text)


@pytest.mark.asyncio
async def test_async_execute_fallback_uses_content_when_no_full_text():
    uc, service = _make_use_case()
    article = _make_article(content="Abstract only.")

    await uc.execute(article, "")

    service.ingest.assert_awaited_once()
    _, full_text_arg = service.ingest.call_args[0]
    assert "Abstract only." in full_text_arg


@pytest.mark.asyncio
async def test_async_execute_skips_bot_detection_content():
    uc, service = _make_use_case()
    article = _make_article()

    await uc.execute(article, "Please verify that you're not a robot to continue.")

    service.ingest.assert_not_awaited()
