def test_composition_root_wires_arxiv_metadata_and_topic_repos(monkeypatch):
    import inspect
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("SKIP_CONFIG_VALIDATION", "true")
    from src.app import composition_root
    src = inspect.getsource(composition_root.build_run_scraper_use_case)
    assert "SqlAlchemyArxivMetadataRepository" in src
    assert "arxiv_metadata_repo" in src
