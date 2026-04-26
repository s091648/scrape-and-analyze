import inspect


def test_bootstrap_wires_arxiv_metadata_repository(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("SKIP_CONFIG_VALIDATION", "true")
    src = inspect.getsource(__import__("src.bootstrap", fromlist=["build_collection_pipeline"]).build_collection_pipeline)
    assert "SqlAlchemyArxivMetadataRepository" in src or "arxiv_metadata_repo" in src


def test_bootstrap_wires_topic_repository(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    src = inspect.getsource(__import__("src.bootstrap", fromlist=["build_collection_pipeline"]).build_collection_pipeline)
    assert "SqlAlchemyTopicRepository" in src or "topic_repo" in src


def test_bootstrap_wires_event_bus(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    src = inspect.getsource(__import__("src.bootstrap", fromlist=["build_collection_pipeline"]).build_collection_pipeline)
    assert "InMemoryEventBus" in src or "event_bus" in src