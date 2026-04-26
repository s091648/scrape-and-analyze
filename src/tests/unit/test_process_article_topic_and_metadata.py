from unittest.mock import MagicMock
from uuid import uuid4
from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.shared.domain.entities import Article


def _make_arxiv_event(topic_id=None):
    return ScrapedArticleDTO(
        url=f"https://arxiv.org/abs/{uuid4()}v1",
        title="Paper", content="Abstract.", source="arxiv",
        topic_id=topic_id or uuid4(),
        metadata={
            "authors": ["Alice"], "arxiv_id": "2601.00001",
            "abstract": "Abstract.", "pdf_available": True,
            "sections": {"introduction": "Intro.", "conclusion": "Concl."},
        },
    )


def test_process_uc_builds_article_with_topic_id():
    from src.modules.collection.application.use_cases.process_scraped_article import (
        ProcessScrapedArticleUseCase,
    )
    from src.modules.collection.domain.services import DedupService

    topic_id = uuid4()
    event = _make_arxiv_event(topic_id=topic_id)

    article_repo = MagicMock()
    article_repo.find_by_url_hash.return_value = None
    saved = Article(
        url=event.url, url_hash="a" * 64,
        source=event.source, title=event.title,
        content=event.content, topic_id=topic_id,
    )
    article_repo.save.return_value = saved

    dedup = DedupService(article_repo=article_repo)
    event_bus = MagicMock()

    uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        event_bus=event_bus,
    )
    uc.execute(event)

    saved_article = article_repo.save.call_args[0][0]
    assert saved_article.topic_id == topic_id
    assert saved_article.source == "arxiv"


def test_process_uc_builds_article_with_metadata():
    from src.modules.collection.application.use_cases.process_scraped_article import (
        ProcessScrapedArticleUseCase,
    )
    from src.modules.collection.domain.services import DedupService

    event = _make_arxiv_event()
    article_repo = MagicMock()
    article_repo.find_by_url_hash.return_value = None
    article_repo.save.return_value = MagicMock()

    uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=DedupService(article_repo=article_repo),
        event_bus=MagicMock(),
    )
    uc.execute(event)

    saved = article_repo.save.call_args[0][0]
    assert saved.metadata["authors"] == ["Alice"]
    assert saved.metadata["pdf_available"] is True