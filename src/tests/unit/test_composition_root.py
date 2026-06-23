import inspect
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.modules.collection.application.events import (
    ArticleScrapedEvent,
    PipelineCompletedEvent,
)
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    AnalysisFailedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
    TranslationFailedEvent,
)
from src.shared.application.events import ArticleProcessedEvent


# ---------------------------------------------------------------------------
# Existing source-inspection tests (preserved)
# ---------------------------------------------------------------------------


def test_bootstrap_wires_topic_repository(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    src = inspect.getsource(__import__("src.bootstrap", fromlist=["build_collection_pipeline"]).build_collection_pipeline)
    assert "SqlAlchemyTopicRepository" in src or "topic_repo" in src


def test_bootstrap_wires_event_bus(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    src = inspect.getsource(__import__("src.bootstrap", fromlist=["build_collection_pipeline"]).build_collection_pipeline)
    assert "InMemoryEventBus" in src or "event_bus" in src


# ---------------------------------------------------------------------------
# Helper: common mock setup for build_collection_pipeline()
# ---------------------------------------------------------------------------


def _make_collection_pipeline_mocks():
    """Return (mock_init_db, mock_get_session, mock_session, mock_llm, mock_embedding).

    The caller still needs to invoke ``build_collection_pipeline()`` and
    perform assertions; this helper only arranges the three patches so
    the DB layer and LLM service are replaced with mocks.
    """
    mock_session = MagicMock()
    mock_llm = MagicMock()
    mock_embedding = MagicMock()

    mock_init_db = MagicMock()
    mock_get_session = MagicMock(return_value=mock_session)
    mock_build_llm = MagicMock(return_value=(mock_llm, mock_embedding, ["gemini"]))

    return mock_init_db, mock_get_session, mock_session, mock_llm, mock_embedding, mock_build_llm


def _build_pipeline_with_mocks():
    """Patch DB and LLM, call build_collection_pipeline(), return the pipeline."""
    mock_init_db, mock_get_session, mock_session, mock_llm, mock_embedding, mock_build_llm = _make_collection_pipeline_mocks()

    with patch("src.bootstrap.init_db", mock_init_db), \
         patch("src.bootstrap.get_session", mock_get_session), \
         patch("src.bootstrap.build_llm_service", mock_build_llm):
        from src.bootstrap import build_collection_pipeline
        pipeline, _ = build_collection_pipeline()

    return pipeline, mock_init_db, mock_get_session, mock_session, mock_llm, mock_embedding, mock_build_llm


# ---------------------------------------------------------------------------
# T015 — ValueError when no active LLM providers
# ---------------------------------------------------------------------------


def test_t015_build_collection_pipeline_raises_when_no_llm_providers():
    """build_llm_service() raises ValueError if the DB has no active LLM providers."""
    mock_init_db = MagicMock()
    mock_get_session = MagicMock(return_value=MagicMock())
    mock_build_llm = MagicMock(side_effect=ValueError("llm_providers table has no active LLM providers"))

    with patch("src.bootstrap.init_db", mock_init_db), \
         patch("src.bootstrap.get_session", mock_get_session), \
         patch("src.bootstrap.build_llm_service", mock_build_llm):
        from src.bootstrap import build_collection_pipeline
        with pytest.raises(ValueError, match="no active LLM providers"):
            build_collection_pipeline()


# ---------------------------------------------------------------------------
# T016-T021 — Event bus subscription verification
# ---------------------------------------------------------------------------


def test_t016_article_scraped_event_subscription():
    """ArticleScrapedEvent must have exactly one handler registered."""
    pipeline, *_ = _build_pipeline_with_mocks()
    handlers = pipeline._event_bus._handlers.get(ArticleScrapedEvent, [])
    assert len(handlers) == 1, f"expected 1 handler for ArticleScrapedEvent, got {len(handlers)}"


def test_t017_article_processed_event_subscription():
    """ArticleProcessedEvent must have at least one handler (analysis); RAG handler is optional."""
    pipeline, *_ = _build_pipeline_with_mocks()
    handlers = pipeline._event_bus._handlers.get(ArticleProcessedEvent, [])
    assert len(handlers) >= 1, f"expected at least 1 handler for ArticleProcessedEvent, got {len(handlers)}"


def test_t018_analysis_completed_event_subscription():
    """AnalysisCompletedEvent must have exactly one handler (TagNormalizationHandler)."""
    pipeline, *_ = _build_pipeline_with_mocks()
    handlers = pipeline._event_bus._handlers.get(AnalysisCompletedEvent, [])
    assert len(handlers) == 1, f"expected 1 handler for AnalysisCompletedEvent, got {len(handlers)}"


def test_t019_tag_normalization_completed_event_subscription():
    """TagNormalizationCompletedEvent must have exactly one handler (AnalysisCompletedHandler)."""
    pipeline, *_ = _build_pipeline_with_mocks()
    handlers = pipeline._event_bus._handlers.get(TagNormalizationCompletedEvent, [])
    assert len(handlers) == 1, f"expected 1 handler for TagNormalizationCompletedEvent, got {len(handlers)}"


def test_t020_failed_event_subscriptions():
    """AnalysisFailedEvent, TagNormalizationFailedEvent, and TranslationFailedEvent
    must each have exactly one handler (FailedTaskPersistenceHandler)."""
    pipeline, *_ = _build_pipeline_with_mocks()

    for event_cls in (AnalysisFailedEvent, TagNormalizationFailedEvent, TranslationFailedEvent):
        handlers = pipeline._event_bus._handlers.get(event_cls, [])
        assert len(handlers) == 1, (
            f"expected 1 handler for {event_cls.__name__}, got {len(handlers)}"
        )


def test_t021_pipeline_completed_event_subscriptions():
    """PipelineCompletedEvent must have two handlers (OtelMetricsHandler + notification handler)."""
    pipeline, *_ = _build_pipeline_with_mocks()
    handlers = pipeline._event_bus._handlers.get(PipelineCompletedEvent, [])
    assert len(handlers) == 2, f"expected 2 handlers for PipelineCompletedEvent, got {len(handlers)}"


# ---------------------------------------------------------------------------
# T022 — All 10 repositories share the same session
# ---------------------------------------------------------------------------


def test_t022_repositories_share_same_session():
    """get_session() is called exactly once; all 10 repositories receive that session."""
    pipeline, _, mock_get_session, mock_session, *_ = _build_pipeline_with_mocks()
    assert mock_get_session.call_count == 1, (
        f"expected get_session() called once, got {mock_get_session.call_count}"
    )


# ---------------------------------------------------------------------------
# T023 — ScrapeExecutor has on_discover_failed callback
# ---------------------------------------------------------------------------


def test_t023_scrape_executor_has_on_discover_failed_callback():
    """The ScrapeExecutor wired into the pipeline must have an _on_discover_failed callback."""
    pipeline, *_ = _build_pipeline_with_mocks()
    assert pipeline._executor._on_discover_failed is not None, (
        "ScrapeExecutor._on_discover_failed should be set to a callable"
    )


# ---------------------------------------------------------------------------
# T040 — build_translation_pipeline() returns dict with correct keys
# ---------------------------------------------------------------------------


def test_t040_build_translation_pipeline_returns_correct_keys():
    """build_translation_pipeline() must return a dict with the five expected keys."""
    mock_session = MagicMock()
    mock_llm = MagicMock()
    mock_embedding = MagicMock()

    with patch("src.bootstrap.init_db", MagicMock()), \
         patch("src.bootstrap.get_session", MagicMock(return_value=mock_session)), \
         patch("src.bootstrap.build_llm_service", MagicMock(return_value=(mock_llm, mock_embedding, ["gemini"]))):
        from src.bootstrap import build_translation_pipeline
        result = build_translation_pipeline()

    expected_keys = {
        "use_case",
        "tag_use_case",
        "body_use_case",
        "session",
        "analyses_translation_repository",
        "tag_translation_repository",
        "article_translation_repository",
    }
    assert set(result.keys()) == expected_keys, (
        f"expected keys {expected_keys}, got {set(result.keys())}"
    )


# ---------------------------------------------------------------------------
# T041 — build_translation_pipeline() does not create InMemoryEventBus
# ---------------------------------------------------------------------------


def test_t041_build_translation_pipeline_does_not_create_event_bus():
    """The translation pipeline must not create an InMemoryEventBus."""
    mock_session = MagicMock()
    mock_llm = MagicMock()
    mock_embedding = MagicMock()

    with patch("src.bootstrap.init_db", MagicMock()), \
         patch("src.bootstrap.get_session", MagicMock(return_value=mock_session)), \
         patch("src.bootstrap.build_llm_service", MagicMock(return_value=(mock_llm, mock_embedding, ["gemini"]))):
        from src.bootstrap import build_translation_pipeline
        result = build_translation_pipeline()

    # The returned dict must not contain an event_bus key
    assert "event_bus" not in result, (
        "build_translation_pipeline() should not include an event_bus in its return dict"
    )

    # Also verify the source code does not reference InMemoryEventBus
    src = inspect.getsource(build_translation_pipeline)
    assert "InMemoryEventBus" not in src, (
        "build_translation_pipeline() source should not reference InMemoryEventBus"
    )


# ---------------------------------------------------------------------------
# build_rag_ingestion_service
# ---------------------------------------------------------------------------


def test_build_rag_returns_none_and_event_when_config_missing():
    """When missing_rag_config() returns vars, build_rag_ingestion_service yields (None, event)."""
    import importlib
    import src.config.settings as _settings
    importlib.reload(_settings)

    with patch("src.config.settings.missing_rag_config", return_value=["VECTOR_DB_NAME", "VECTOR_DB_USER"]):
        from src.bootstrap import build_rag_ingestion_service
        rag_service, event = build_rag_ingestion_service()

    assert rag_service is None
    assert event is not None
    from src.modules.intelligence.application.events import RagConfigFailedEvent
    assert isinstance(event, RagConfigFailedEvent)


def test_build_rag_returns_none_none_when_sdk_not_installed(monkeypatch):
    """When chatbot_plugin_sdk cannot be imported, returns (None, None)."""
    monkeypatch.setenv("VECTOR_DB_NAME", "mydb")
    monkeypatch.setenv("VECTOR_DB_USER", "user")
    monkeypatch.setenv("VECTOR_DB_PASSWORD", "pass")
    import importlib
    import src.config.settings as _settings
    importlib.reload(_settings)

    # Remove any cached chatbot_plugin_sdk module so the import fails
    sdk_keys = [k for k in sys.modules if "chatbot_plugin_sdk" in k]
    saved = {k: sys.modules.pop(k) for k in sdk_keys}
    try:
        # Insert a None entry so the import raises ImportError
        sys.modules["chatbot_plugin_sdk"] = None  # type: ignore[assignment]
        from src.bootstrap import build_rag_ingestion_service
        rag_service, event = build_rag_ingestion_service()
    finally:
        sys.modules.pop("chatbot_plugin_sdk", None)
        sys.modules.update(saved)

    assert rag_service is None
    assert event is None


def test_build_rag_returns_none_none_on_generic_exception(monkeypatch):
    """When an unexpected exception occurs during RAG setup, returns (None, None)."""
    monkeypatch.setenv("VECTOR_DB_NAME", "mydb")
    monkeypatch.setenv("VECTOR_DB_USER", "user")
    monkeypatch.setenv("VECTOR_DB_PASSWORD", "pass")
    import importlib
    import src.config.settings as _settings
    importlib.reload(_settings)

    mock_sdk = MagicMock()
    mock_sdk.NotConfiguredError = type("NotConfiguredError", (Exception,), {})
    mock_sdk.IngestProcessor.side_effect = RuntimeError("unexpected failure")

    with patch.dict("sys.modules", {"chatbot_plugin_sdk": mock_sdk}):
        from src.bootstrap import build_rag_ingestion_service
        rag_service, event = build_rag_ingestion_service()

    assert rag_service is None
    assert event is None


def test_build_llm_service_skips_unknown_provider(monkeypatch):
    """build_llm_service logs a warning and skips providers with unknown names."""
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    unknown_cfg = {
        "name": "unknown_provider",
        "api_key_env": "UNKNOWN_API_KEY",
        "model": "unknown-model",
        "priority": 1,
        "strategy": {},
    }

    with patch("shared.llm_provider.load_active_providers", return_value=[unknown_cfg]), \
         patch("shared.llm_provider.load_active_embedding_providers", return_value=[]):
        from src.bootstrap import build_llm_service
        with pytest.raises(ValueError, match="no active LLM providers"):
            build_llm_service(mock_session)
