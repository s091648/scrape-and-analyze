"""
Unit tests for the backfill_rag CLI entrypoint — covers the rag-disabled
skip path, candidate-limit derivation, per-article success/failure handling,
and the coroutine/semaphore-based concurrency shared with refresh_metrics.py.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _mock_article(article_id=None):
    article = MagicMock()
    article.id = article_id or uuid4()
    return article


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_rag_disabled_skips_find_pending_entirely(mock_validate, mock_logging, mock_http, mock_pipeline):
    backfill_repo = MagicMock()
    session = MagicMock()
    mock_pipeline.return_value = (None, backfill_repo, session)

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    backfill_repo.find_pending.assert_not_called()


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_find_pending_called_with_limit_arg(mock_validate, mock_logging, mock_http, mock_pipeline):
    use_case = MagicMock()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session)

    with patch("sys.argv", ["backfill_rag", "--limit", "50"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    backfill_repo.find_pending.assert_called_once_with(50)


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_ingests_every_candidate_article(mock_validate, mock_logging, mock_http, mock_pipeline):
    article_a = _mock_article()
    article_b = _mock_article()

    use_case = MagicMock()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = [article_a, article_b]
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session)

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

    use_case = MagicMock()
    use_case.execute.side_effect = execute_side_effect
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = [failing_article, ok_article]
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session)

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()  # must not raise

    assert use_case.execute.call_count == 2


@patch("src.bootstrap.build_rag_backfill_pipeline")
@patch("src.entrypoints.cli.backfill_rag.init_default_client")
@patch("src.entrypoints.cli.backfill_rag.configure_logging")
@patch("src.entrypoints.cli.backfill_rag.validate_config")
def test_session_closed_after_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    use_case = MagicMock()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session)

    with patch("sys.argv", ["backfill_rag"]):
        from src.entrypoints.cli.backfill_rag import main
        main()

    session.close.assert_called_once()


# ── Concurrency (asyncio.gather + semaphore) ─────────────────────────────────

def test_concurrency_flag_bounds_in_flight_execute_calls():
    """--concurrency must actually cap how many execute() calls run at once,
    not just be accepted and ignored."""
    import threading
    import time

    from src.entrypoints.cli.backfill_rag import _backfill_all

    lock = threading.Lock()
    in_flight = 0
    max_observed = 0

    def slow_execute(article):
        nonlocal in_flight, max_observed
        with lock:
            in_flight += 1
            max_observed = max(max_observed, in_flight)
        time.sleep(0.05)
        with lock:
            in_flight -= 1

    use_case = MagicMock()
    use_case.execute.side_effect = slow_execute

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
    use_case = MagicMock()
    backfill_repo = MagicMock()
    backfill_repo.find_pending.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (use_case, backfill_repo, session)

    with patch("sys.argv", ["backfill_rag"]), \
         patch("src.entrypoints.cli.backfill_rag._backfill_all", new_callable=AsyncMock) as mock_backfill_all:
        mock_backfill_all.return_value = (0, 0)
        from src.entrypoints.cli.backfill_rag import main
        main()

    assert mock_backfill_all.call_args.args[2] == 5
