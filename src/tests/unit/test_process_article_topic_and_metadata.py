from unittest.mock import MagicMock
from uuid import uuid4
from src.ingestion.models.scraped_article import ScrapedArticle
from src.domain.entities.article import ArticleEntity


def _make_arxiv_scraped(topic_id="22222222-2222-2222-2222-222222222222"):
    return ScrapedArticle(
        url=f"https://arxiv.org/abs/{uuid4()}v1",
        title="Paper", content="Abstract.", published_at=None,
        source="arxiv", topic_id=topic_id,
        metadata={
            "authors": ["Alice"], "arxiv_id": "2601.00001",
            "abstract": "Abstract.", "pdf_available": True,
            "sections": {"introduction": "Intro.", "conclusion": "Concl."},
        },
    )


def _make_saved(scraped):
    return ArticleEntity(
        id=uuid4(), url=scraped.url, url_hash="abc",
        source=scraped.source, title=scraped.title,
        content=scraped.content, correlation_id=uuid4(),
        metadata=scraped.metadata or {},
        topic_id=None,
    )


def _make_uc(article_repo, arxiv_meta_repo=None):
    from src.app.use_cases.process_article import ProcessArticleUseCase
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    analyze = MagicMock()
    analyze.execute.return_value = True
    return ProcessArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        analyze_article_uc=analyze,
        arxiv_metadata_repo=arxiv_meta_repo,
    )


def test_process_article_writes_topic_id_to_entity():
    scraped = _make_arxiv_scraped(topic_id="11111111-1111-1111-1111-111111111111")
    saved_entity = _make_saved(scraped)

    article_repo = MagicMock()
    article_repo.save.return_value = saved_entity

    uc = _make_uc(article_repo)
    uc.execute(scraped, "prompt", str(uuid4()))

    saved_arg: ArticleEntity = article_repo.save.call_args[0][0]
    assert str(saved_arg.topic_id) == "11111111-1111-1111-1111-111111111111"


def test_process_article_saves_arxiv_metadata():
    from src.domain.entities.arxiv_metadata import ArxivMetadataEntity
    scraped = _make_arxiv_scraped()
    saved_entity = _make_saved(scraped)
    article_repo = MagicMock()
    article_repo.save.return_value = saved_entity
    arxiv_meta_repo = MagicMock()

    uc = _make_uc(article_repo, arxiv_meta_repo=arxiv_meta_repo)
    uc.execute(scraped, "prompt", str(uuid4()))

    arxiv_meta_repo.save.assert_called_once()
    meta: ArxivMetadataEntity = arxiv_meta_repo.save.call_args[0][0]
    assert meta.authors == ["Alice"]
    assert meta.sections == {"introduction": "Intro.", "conclusion": "Concl."}


def test_process_article_skips_arxiv_metadata_for_non_arxiv():
    scraped = ScrapedArticle(
        url=f"https://blog.example.com/{uuid4()}", title="Post",
        content="Body.", published_at=None, source="blog",
    )
    article_repo = MagicMock()
    article_repo.save.return_value = ArticleEntity(
        id=uuid4(), url=scraped.url, url_hash="x",
        source="blog", title="Post", content="Body.", correlation_id=uuid4(),
    )
    arxiv_meta_repo = MagicMock()
    uc = _make_uc(article_repo, arxiv_meta_repo=arxiv_meta_repo)
    uc.execute(scraped, "prompt", str(uuid4()))
    arxiv_meta_repo.save.assert_not_called()
