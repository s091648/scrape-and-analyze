"""Integration tests for src/bootstrap.py — the composition root every scheduled
entrypoint starts from. Each build_*() normally opens its own session against the
real DATABASE_URL (init_db() + get_session()); here those are monkeypatched to the
isolated test schema, so the builders run their real wiring against real
llm_providers / metric rows instead of mocks. Catches wiring breakage (a renamed
constructor kwarg, a missing import, an unsubscribed handler) that unit tests with a
mocked composition root can't.

No network: providers are constructed but never called, RAG is either disabled or
forced to its "missing config" path, and Redis gateways only connect lazily."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.failed_task import FailedTask as FailedTaskModel
from models.llm_provider import LlmProvider

pytestmark = pytest.mark.integration

_API_KEY_ENV = "BOOTSTRAP_WIRING_TEST_API_KEY"


@pytest.fixture
def patched_db(monkeypatch, db_session):
    """Route every builder's init_db()/get_session() to the test-schema db_session.
    Patched on both src.bootstrap (module-level imports) and the database module
    (some builders re-import them inside the function)."""
    import src.bootstrap as bootstrap
    from src.infrastructure.persistence import database

    for module in (bootstrap, database):
        monkeypatch.setattr(module, "init_db", lambda: None)
        monkeypatch.setattr(module, "get_session", lambda: db_session)
    monkeypatch.setenv(_API_KEY_ENV, "test-key")
    return db_session


@pytest.fixture
def seeded_providers(patched_db):
    """Active LLM/embedding/multimodal rows (plus an unknown provider of each kind, which
    the builders must skip). Some builders' repositories commit on db_session, so rows
    are explicitly deleted afterwards rather than relying on rollback."""
    session = patched_db
    rows = [
        LlmProvider(name="claude", model=f"claude-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=1, type="llm"),
        LlmProvider(name="openrouter", model=f"or-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=2, type="llm",
                    rpm=10, tpm=1000, rpd=100),
        LlmProvider(name="gemini", model=f"gemini-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=3, type="llm"),
        LlmProvider(name="mystery", model=f"mystery-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=4, type="llm"),
        LlmProvider(name="gemini", model=f"emb-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=1, type="embedding"),
        LlmProvider(name="other", model=f"emb-other-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=2, type="embedding"),
        LlmProvider(name="huggingface", model=f"hf-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=1, type="multimodal"),
    ]
    session.add_all(rows)
    session.flush()
    models = [r.model for r in rows]

    yield session

    session.rollback()
    session.query(LlmProvider).filter(LlmProvider.model.in_(models)).delete(synchronize_session=False)
    session.commit()


# ---------------------------------------------------------------------------
# build_llm_service / build_async_llm_service
# ---------------------------------------------------------------------------

class TestBuildLlmServices:
    def test_sync_service_loads_known_providers_in_priority_order(self, seeded_providers):
        from src.bootstrap import build_llm_service

        llm_service, embedding_service, names = build_llm_service(seeded_providers)

        # "mystery" (unknown provider name) is skipped, not fatal.
        assert names == ["claude", "openrouter", "gemini"]
        assert llm_service is not None and embedding_service is not None

    def test_async_service_loads_known_providers_in_priority_order(self, seeded_providers):
        from src.bootstrap import build_async_llm_service

        llm_service, embedding_service, names = build_async_llm_service(seeded_providers)

        assert names == ["claude", "openrouter", "gemini"]
        assert llm_service is not None and embedding_service is not None

    def test_sync_service_requires_an_active_llm_provider(self, patched_db):
        from src.bootstrap import build_llm_service

        with pytest.raises(ValueError, match="no active LLM providers"):
            build_llm_service(patched_db)

    def test_async_service_requires_an_active_embedding_provider(self, patched_db):
        from shared.domain.exceptions import ValidationError
        from src.bootstrap import build_async_llm_service

        patched_db.add(LlmProvider(name="claude", model=f"only-llm-{uuid.uuid4().hex[:6]}",
                                   api_key_env=_API_KEY_ENV, priority=1, type="llm"))
        patched_db.flush()

        with pytest.raises(ValidationError, match="no active embedding providers"):
            build_async_llm_service(patched_db)


# ---------------------------------------------------------------------------
# RAG ingestion service — disabled paths only (the enabled path needs a vector DB)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("builder_name", ["build_rag_ingestion_service", "build_async_rag_ingestion_service"])
def test_rag_ingestion_service_reports_missing_config(monkeypatch, builder_name):
    import src.bootstrap as bootstrap
    from src.config import settings
    from src.modules.intelligence.application.events import RagConfigFailedEvent

    monkeypatch.setattr(settings, "missing_rag_config", lambda: ["VECTOR_DB_NAME", "VECTOR_DB_PASSWORD"])

    service, event = getattr(bootstrap, builder_name)()

    assert service is None
    assert isinstance(event, RagConfigFailedEvent)
    assert event.exception_type == "MissingConfiguration"
    assert event.context == {"missing_vars": ["VECTOR_DB_NAME", "VECTOR_DB_PASSWORD"]}


# ---------------------------------------------------------------------------
# build_collection_pipeline — the full scrape → analyze → translate wiring
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline_env(monkeypatch, seeded_providers, test_async_sessionmaker):
    """build_collection_pipeline()'s own async engine + RAG construction swapped for the
    test schema / a disabled RAG service. Returns a setter for what the RAG builder
    should report, and cleans up any FailedTask rows the builder's startup paths write."""
    import src.bootstrap as bootstrap
    from src.infrastructure.persistence import database

    async def _no_prewarm(connections=None):
        return None

    monkeypatch.setattr(database, "get_async_sessionmaker", lambda: test_async_sessionmaker)
    monkeypatch.setattr(database, "prewarm_async_engine", _no_prewarm)
    rag_result = {"value": (None, None)}
    monkeypatch.setattr(bootstrap, "build_async_rag_ingestion_service", lambda: rag_result["value"])
    marker = f"bootstrap-wiring-{uuid.uuid4().hex}"

    yield SimpleNamespace(session=seeded_providers, sessionmaker=test_async_sessionmaker,
                          rag_result=rag_result, marker=marker)

    seeded_providers.rollback()
    seeded_providers.query(FailedTaskModel).filter(
        (FailedTaskModel.exception_message.contains(marker)) | (FailedTaskModel.task_type == "wiringsrc_discover")
    ).delete(synchronize_session=False)
    seeded_providers.commit()


@pytest.mark.asyncio
async def test_build_collection_pipeline_subscribes_barrier_handlers(pipeline_env):
    from src.bootstrap import build_collection_pipeline
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.modules.collection.application.events import PipelineCompletedEvent, TextPipelineCompletedEvent

    pipeline, stats = await build_collection_pipeline(jitter_seconds=1.5)

    assert isinstance(pipeline, CollectionPipeline)
    assert pipeline._jitter_seconds == 1.5
    assert pipeline._rag_downstream_builder is None  # RAG disabled
    handlers = pipeline._event_bus._handlers
    # search index rebuild, tag-count refresh, cache invalidation, cache warmup — in that order
    assert len(handlers[TextPipelineCompletedEvent]) == 4
    # OTel metrics + notification
    assert len(handlers[PipelineCompletedEvent]) == 2
    assert stats is pipeline._pipeline_stats


@pytest.mark.asyncio
async def test_article_and_translation_downstream_builders_wire_per_article_chain(pipeline_env):
    from src.bootstrap import build_collection_pipeline
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.modules.collection.application.events import ArticleSaveFailedEvent, ArticleScrapedEvent
    from src.modules.intelligence.application.event_handlers import AnalysisCompletedHandler
    from src.modules.intelligence.application.events import (
        AnalysisCompletedEvent, AnalysisFailedEvent, TagNormalizationFailedEvent, TranslationFailedEvent,
    )
    from src.shared.application.events import ArticleProcessedEvent

    pipeline, _ = await build_collection_pipeline()
    dispatch_rag = AsyncMock()

    async with pipeline_env.sessionmaker() as session:
        bus = AsyncInMemoryEventBus()
        await pipeline._article_downstream_builder(session, bus, dispatch_rag)
        translation_handler = await pipeline._translation_downstream_builder(session)

    subscribed = bus._handlers
    for event_type in (ArticleScrapedEvent, ArticleSaveFailedEvent, ArticleProcessedEvent,
                       AnalysisCompletedEvent, AnalysisFailedEvent, TagNormalizationFailedEvent,
                       TranslationFailedEvent):
        assert subscribed[event_type], f"{event_type.__name__} has no subscriber"
    # RAG disabled — dispatch_rag must not be wired onto ArticleProcessedEvent.
    assert dispatch_rag not in subscribed[ArticleProcessedEvent]
    assert isinstance(translation_handler, AnalysisCompletedHandler)


@pytest.mark.asyncio
async def test_rag_config_failure_is_recorded_at_startup(pipeline_env):
    from sqlalchemy import select
    from src.bootstrap import build_collection_pipeline
    from src.modules.intelligence.application.events import RagConfigFailedEvent

    pipeline_env.rag_result["value"] = (None, RagConfigFailedEvent(
        exception_type="NotConfiguredError", exception_message=f"no dense provider {pipeline_env.marker}", context={},
    ))

    await build_collection_pipeline()

    async with pipeline_env.sessionmaker() as session:
        rows = (await session.execute(
            select(FailedTaskModel).where(FailedTaskModel.exception_message.contains(pipeline_env.marker))
        )).scalars().all()
    assert [r.task_type for r in rows] == ["rag_config"]


@pytest.mark.asyncio
async def test_discover_failure_callback_records_failed_task(pipeline_env):
    from src.bootstrap import build_collection_pipeline

    pipeline, _ = await build_collection_pipeline()
    task = SimpleNamespace(setting=SimpleNamespace(source="wiringsrc"))

    pipeline._executor._on_discover_failed(task, RuntimeError(f"feed down {pipeline_env.marker}"))

    row = pipeline_env.session.query(FailedTaskModel).filter_by(task_type="wiringsrc_discover").one()
    assert row.exception_type == "RuntimeError"


# ---------------------------------------------------------------------------
# The other scheduled entrypoints' builders
# ---------------------------------------------------------------------------

def test_build_translation_pipeline(seeded_providers):
    from src.bootstrap import build_translation_pipeline

    result = build_translation_pipeline()

    assert result["session"] is seeded_providers
    for key in ("use_case", "tag_use_case", "body_use_case", "analyses_translation_repository",
                "tag_translation_repository", "article_translation_repository"):
        assert result[key] is not None


def test_build_weekly_pipeline(monkeypatch, seeded_providers):
    from src.bootstrap import build_weekly_pipeline
    from src.config import settings
    from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent

    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"):
        monkeypatch.setattr(settings, name, "test")
    monkeypatch.setattr(settings, "R2_PUBLIC_URL", "https://cdn.example.com")

    pipeline, session, event_bus, llm_service = build_weekly_pipeline()

    assert pipeline is not None and llm_service is not None
    assert session is seeded_providers
    assert event_bus._handlers[WeeklyReportJobCompletedEvent]


def test_build_weekly_pipeline_requires_a_multimodal_provider(patched_db):
    from src.bootstrap import build_weekly_pipeline

    patched_db.add_all([
        LlmProvider(name="claude", model=f"wk-llm-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=1, type="llm"),
        LlmProvider(name="gemini", model=f"wk-emb-{uuid.uuid4().hex[:6]}", api_key_env=_API_KEY_ENV, priority=1, type="embedding"),
    ])
    patched_db.flush()

    with pytest.raises(ValueError, match="No active multimodal provider"):
        build_weekly_pipeline()


def test_build_metrics_refresh_pipeline(patched_db):
    from models.metric_definition import MetricDefinition
    from models.metric_provider import MetricProvider
    from src.bootstrap import build_metrics_refresh_pipeline
    from src.modules.collection.application.events import MetricsRefreshCompletedEvent

    definition = MetricDefinition(metric_key=f"wiring_{uuid.uuid4().hex[:6]}", label_i18n_key="metrics.x")
    patched_db.add(definition)
    patched_db.flush()
    patched_db.add(MetricProvider(metric_definition_id=definition.id, provider_name="openalex", priority=1,
                                  extractor_type="json_path", extractor_spec={"path": "cited_by_count"}))
    patched_db.flush()

    metrics_service, metrics_repo, session, event_bus = build_metrics_refresh_pipeline()

    assert metrics_service is not None and metrics_repo is not None
    assert session is patched_db
    assert event_bus._handlers[MetricsRefreshCompletedEvent]


def test_build_dedup_reconciliation_pipeline(patched_db):
    from src.bootstrap import build_dedup_reconciliation_pipeline
    from src.modules.collection.application.events import DedupReconcileCompletedEvent

    client, dedup_repo, session, event_bus = build_dedup_reconciliation_pipeline()

    assert client is not None and dedup_repo is not None
    assert session is patched_db
    assert event_bus._handlers[DedupReconcileCompletedEvent]


def test_build_rag_backfill_pipeline_with_rag_disabled(monkeypatch, patched_db):
    import src.bootstrap as bootstrap
    from src.modules.intelligence.application.events import RagBackfillCompletedEvent

    monkeypatch.setattr(bootstrap, "build_async_rag_ingestion_service", lambda: (None, None))

    use_case, backfill_repo, session, event_bus = bootstrap.build_rag_backfill_pipeline()

    assert use_case is None  # callers must check before use
    assert backfill_repo is not None
    assert session is patched_db
    assert event_bus._handlers[RagBackfillCompletedEvent]
