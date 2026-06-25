import inspect


def test_topic_repository_is_abstract():
    from src.shared.domain.repositories import TopicRepository
    assert inspect.isabstract(TopicRepository)
    assert "list_active" in TopicRepository.__abstractmethods__
    assert "find_by_id" in TopicRepository.__abstractmethods__
