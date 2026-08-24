from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.collection.application.events import ArticleScrapedEvent
from src.shared.domain.entities import Article


def _make_arxiv_event(topic_id=None):
    return ArticleScrapedEvent(
        url=f"https://arxiv.org/abs/{uuid4()}v1",
        title="Paper", content="Abstract.", source="arxiv",
        topic_id=topic_id or uuid4(),
        metadata={
            "authors": ["Alice"], "arxiv_id": "2601.00001",
            "abstract": "Abstract.", "pdf_available": True,
            "sections": {"introduction": "Intro.", "conclusion": "Concl."},
        },
    )


@pytest.mark.asyncio
async def test_process_uc_builds_article_with_topic_id():
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.modules.collection.domain.services import AsyncDedupService

    topic_id = uuid4()
    event = _make_arxiv_event(topic_id=topic_id)

    article_repo = AsyncMock()
    article_repo.find_by_url_hash.return_value = None
    saved = Article(
        url=event.url, url_hash="a" * 64,
        source=event.source, title=event.title,
        content=event.content, topic_id=topic_id,
    )
    article_repo.save.return_value = saved

    dedup = AsyncDedupService(article_repo=article_repo)

    uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
    )
    await uc.execute(event)

    saved_article = article_repo.save.call_args[0][0]
    assert saved_article.topic_id == topic_id
    assert saved_article.source == "arxiv"


@pytest.mark.asyncio
async def test_process_uc_builds_article_with_metadata():
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.modules.collection.domain.services import AsyncDedupService

    event = _make_arxiv_event()
    article_repo = AsyncMock()
    article_repo.find_by_url_hash.return_value = None
    article_repo.save.return_value = AsyncMock()

    uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=AsyncDedupService(article_repo=article_repo),
    )
    await uc.execute(event)

    saved = article_repo.save.call_args[0][0]
    assert saved.metadata["authors"] == ["Alice"]
    assert saved.metadata["pdf_available"] is True
