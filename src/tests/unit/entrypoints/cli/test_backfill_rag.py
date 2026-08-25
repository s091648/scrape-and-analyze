"""
Unit tests for the backfill_rag CLI entrypoint — covers the rag-disabled
skip path, candidate-limit derivation, per-article success/failure handling,
and the asyncio.gather + semaphore concurrency on a single event loop
(024-async-pipeline-refactor US6: use_case.execute() is awaited directly,
no asyncio.to_thread — see module docstring / research.md item 11).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _mock_article(article_id=None):
    article = MagicMock()
    article.id = article_id or uuid4()
    return article


def _mock_use_case(execute_side_effect=None):
    """A MagicMock use_case with .execute()/.aclose() as AsyncMock — matches
    AsyncIngestArticleForRagUseCase's now-async interface (execute() is
    awaited directly by _backfill_one(); aclose() is awaited by _run_backfill())."""
    use_case = MagicMock()
    use_case.execute = AsyncMock(side_effect=execute_side_effect)
    use_case.aclose = AsyncMock(return_value=None)
    return use_case


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_rag_disabled_skips_find_pending_entirely(mock_validate, mock_logging, mock_http, mock_pipeline):
    backfill_repo = MagicMock()
    session = MagicMock()
    mock_pipeline.return_value = (None, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    backfill_repo.find_pending.assert_not_called()


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_find_pending_called_with_limit_arg(mock_validate, mock_logging, mock_http, mock_pipeline):
    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag", "--limit", "50"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    backfill_repo.find_pending.assert_called_once_with(50)


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_limit_arg_defaults_to_twenty(mock_validate, mock_logging, mock_http, mock_pipeline):
    """Kept low (not refresh_metrics' 200) since RAG's dense embedding provider
    has no multi-provider rate-limit fallback and shares its daily quota with
    main.py's real-time ingestion — see module docstring."""
    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    backfill_repo.find_pending.assert_called_once_with(20)


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_ingests_every_candidate_article(mock_validate, mock_logging, mock_http, mock_pipeline):
    article_a = _mock_article()
    article_b = _mock_article()

    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = [article_a, article_b]
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    assert use_case.execute.call_count == 2
    called_articles = {call.args[0] for call in use_case.execute.call_args_list}
    assert called_articles == {article_a, article_b}


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_one_article_failure_does_not_abort_the_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    failing_article = _mock_article()
    ok_article = _mock_article()

    def execute_side_effect(article):
        if article is failing_article:
            raise Exception("embedding endpoint error")

    use_case = _mock_use_case(execute_side_effect=execute_side_effect)
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = [failing_article, ok_article]
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()  # must not raise

    assert use_case.execute.call_count == 2


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_session_closed_after_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    session.close.assert_called_once()


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_aclose_called_after_backfill_completes(mock_validate, mock_logging, mock_http, mock_pipeline):
    """024-async-pipeline-refactor US6: releases the RAG SDK's
    EmbeddingBatchCoordinator worker task once every article has settled."""
    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = [_mock_article()]
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    use_case.aclose.assert_called_once()


# ── Concurrency (asyncio.gather + semaphore, single event loop) ─────────────

def test_concurrency_flag_bounds_in_flight_execute_calls():
    """--concurrency must actually cap how many execute() calls run at once,
    not just be accepted and ignored. execute() runs on the main event loop
    now (no to_thread) — simulate "slow" work with asyncio.sleep, not a
    blocking time.sleep, which would just serialize everything."""
    from src.entrypoints.cli.backfill_rag import _backfill_all

    in_flight = 0
    max_observed = 0

    async def slow_execute(article):
        nonlocal in_flight, max_observed
        in_flight += 1
        max_observed = max(max_observed, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1

    use_case = _mock_use_case(execute_side_effect=slow_execute)
    articles = [_mock_article() for _ in range(6)]

    succeeded, failed = asyncio.run(_backfill_all(articles, use_case, concurrency=2))

    assert succeeded == 6
    assert failed == 0
    assert max_observed <= 2


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_concurrency_arg_defaults_to_five(mock_validate, mock_logging, mock_http, mock_pipeline):
    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, MagicMock())

    with patch("sys.argv", ["backfill_rag"]), \
         patch("src.entrypoints.cli.backfill_rag._backfill_all", new_callable=AsyncMock) as mock_backfill_all:
        mock_backfill_all.return_value = (0, 0)
        from src.entrypoints.cli.backfill_rag import main
        main()

    assert mock_backfill_all.call_args.args[2] == 5


# ── Completion notification (020-redis-caching-layer, US4) ──────────────────

@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_publishes_completion_event_with_correct_counts(mock_validate, mock_logging, mock_http, mock_pipeline):
    from src.modules.intelligence.application.events import RagBackfillCompletedEvent

    failing_article = _mock_article()
    ok_article = _mock_article()

    def execute_side_effect(article):
        if article is failing_article:
            raise Exception("embedding endpoint error")

    use_case = _mock_use_case(execute_side_effect=execute_side_effect)
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = [failing_article, ok_article]
    session = MagicMock()
    event_bus = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, event_bus)

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    event_bus.publish.assert_called_once()
    published = event_bus.publish.call_args.args[0]
    assert isinstance(published, RagBackfillCompletedEvent)
    assert published.total == 2
    assert published.succeeded == 1
    assert published.failed == 1


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_notification_failure_does_not_fail_the_job(mock_validate, mock_logging, mock_http, mock_pipeline):
    """FR-012: a notification-sender failure must not raise out of main()."""
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.modules.intelligence.application.events import RagBackfillCompletedEvent

    def _raising_handler(event):
        raise ConnectionError("telegram is down")

    event_bus = InMemoryEventBus()
    event_bus.subscribe(RagBackfillCompletedEvent, _raising_handler)

    use_case = _mock_use_case()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session, event_bus)

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()  # must not raise
