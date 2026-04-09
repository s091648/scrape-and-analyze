import inspect


def test_arxiv_metadata_repository_is_abstract():
    from src.domain.repositories.arxiv_metadata_repository import ArxivMetadataRepository
    assert inspect.isabstract(ArxivMetadataRepository)
    assert "save" in ArxivMetadataRepository.__abstractmethods__
    assert "find_by_article_id" in ArxivMetadataRepository.__abstractmethods__


def test_topic_repository_is_abstract():
    from src.domain.repositories.topic_repository import TopicRepository
    assert inspect.isabstract(TopicRepository)
    assert "list_active" in TopicRepository.__abstractmethods__
    assert "find_by_id" in TopicRepository.__abstractmethods__
