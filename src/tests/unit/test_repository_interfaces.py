import inspect


def test_arxiv_metadata_repository_is_abstract():
    from src.modules.collection.domain.repositories import ArxivMetadataRepository
    assert inspect.isabstract(ArxivMetadataRepository)
    assert "save" in ArxivMetadataRepository.__abstractmethods__
    assert "find_by_article_id" in ArxivMetadataRepository.__abstractmethods__


def test_topic_repository_is_abstract():
    from src.shared.domain.repositories import TopicRepository
    assert inspect.isabstract(TopicRepository)
    assert "list_active" in TopicRepository.__abstractmethods__
    assert "find_by_id" in TopicRepository.__abstractmethods__