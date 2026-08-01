"""
Unit tests for the refresh_metrics CLI entrypoint — covers staleness-query
param derivation, identifier resolution from article metadata, the
conditional upsert-only-on-non-empty-result behavior, and the
coroutine/semaphore-based concurrency introduced for article refreshes.

Articles now refresh concurrently (asyncio.gather under a semaphore), so
fetch_all.side_effect must be keyed by the actual call arguments rather than
positional list order — concurrent execution doesn't guarantee row order.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _mock_row(article_id, metadata):
    row = MagicMock()
    row.id = article_id
    row.metadata = metadata
    return row


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_no_enabled_metrics_skips_query_entirely(mock_validate, mock_logging, mock_http, mock_pipeline):
    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = []
    session = MagicMock()
    mock_pipeline.return_value = (metrics_service, MagicMock(), session)

    with patch("sys.argv", ["refresh_metrics"]):
        from src.entrypoints.cli.refresh_metrics import main
        main()

    session.execute.assert_not_called()


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_query_uses_tracked_metric_keys_and_limit_arg(mock_validate, mock_logging, mock_http, mock_pipeline):
    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    metrics_service.fetch_all.return_value = {}
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []
    mock_pipeline.return_value = (metrics_service, MagicMock(), session)

    with patch("sys.argv", ["refresh_metrics", "--limit", "50"]):
        from src.entrypoints.cli.refresh_metrics import main
        main()

    args, kwargs = session.execute.call_args
    params = args[1]
    assert params["metric_keys"] == ["citation_count"]
    assert params["limit"] == 50


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_upserts_only_when_metrics_resolved(mock_validate, mock_logging, mock_http, mock_pipeline):
    article_with_result = uuid4()
    article_without_result = uuid4()

    def fetch_all_side_effect(identifiers):
        # Articles refresh concurrently now — key off the actual identifiers
        # passed in rather than assuming a fixed call order.
        return {"citation_count": 10} if identifiers.get("doi") == "10.1234/a" else {}

    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    metrics_service.fetch_all.side_effect = fetch_all_side_effect

    metrics_repo = MagicMock()
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        _mock_row(article_with_result, {"doi": "10.1234/a"}),
        _mock_row(article_without_result, {"doi": "10.1234/b"}),
    ]
    mock_pipeline.return_value = (metrics_service, metrics_repo, session)

    with patch("sys.argv", ["refresh_metrics"]):
        from src.entrypoints.cli.refresh_metrics import main
        main()

    metrics_repo.upsert.assert_called_once_with(article_with_result, {"citation_count": 10})


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_articles_without_any_identifier_are_skipped(mock_validate, mock_logging, mock_http, mock_pipeline):
    article_id = uuid4()

    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]

    metrics_repo = MagicMock()
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        _mock_row(article_id, {}),  # no doi/arxiv_id at all
    ]
    mock_pipeline.return_value = (metrics_service, metrics_repo, session)

    with patch("sys.argv", ["refresh_metrics"]):
        from src.entrypoints.cli.refresh_metrics import main
        main()

    metrics_service.fetch_all.assert_not_called()
    metrics_repo.upsert.assert_not_called()


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_one_article_failure_does_not_abort_the_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    failing_article = uuid4()
    ok_article = uuid4()

    def fetch_all_side_effect(identifiers):
        if identifiers.get("doi") == "10.1234/fail":
            raise Exception("network error")
        return {"citation_count": 3}

    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    metrics_service.fetch_all.side_effect = fetch_all_side_effect

    metrics_repo = MagicMock()
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        _mock_row(failing_article, {"doi": "10.1234/fail"}),
        _mock_row(ok_article, {"doi": "10.1234/ok"}),
    ]
    mock_pipeline.return_value = (metrics_service, metrics_repo, session)

    with patch("sys.argv", ["refresh_metrics"]):
        from src.entrypoints.cli.refresh_metrics import main
        main()  # must not raise

    metrics_repo.upsert.assert_called_once_with(ok_article, {"citation_count": 3})


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_session_closed_after_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []
    mock_pipeline.return_value = (metrics_service, MagicMock(), session)

    with patch("sys.argv", ["refresh_metrics"]):
        from src.entrypoints.cli.refresh_metrics import main
        main()

    session.close.assert_called_once()


# ── Concurrency (asyncio.gather + semaphore) ─────────────────────────────────

def test_concurrency_flag_bounds_in_flight_fetch_all_calls():
    """--concurrency must actually cap how many fetch_all() calls run at once,
    not just be accepted and ignored."""
    import threading
    import time

    from src.entrypoints.cli.refresh_metrics import _refresh_all

    lock = threading.Lock()
    in_flight = 0
    max_observed = 0

    def slow_fetch_all(identifiers):
        nonlocal in_flight, max_observed
        with lock:
            in_flight += 1
            max_observed = max(max_observed, in_flight)
        time.sleep(0.05)
        with lock:
            in_flight -= 1
        return {"citation_count": 1}

    metrics_service = MagicMock()
    metrics_service.fetch_all.side_effect = slow_fetch_all
    metrics_repo = MagicMock()

    rows = [_mock_row(uuid4(), {"doi": f"10.1234/{i}"}) for i in range(6)]

    refreshed, failed = asyncio.run(_refresh_all(rows, metrics_service, metrics_repo, concurrency=2))

    assert refreshed == 6
    assert failed == 0
    assert max_observed <= 2


def test_refresh_all_upserts_never_run_concurrently():
    """metrics_repo.upsert() must never be observed mid-call by another article's
    refresh — it shares one non-thread-safe SQLAlchemy session across the run."""
    import threading

    from src.entrypoints.cli.refresh_metrics import _refresh_all

    lock = threading.Lock()
    upserting = False
    violation = False

    def upsert(article_id, metrics):
        nonlocal upserting, violation
        with lock:
            if upserting:
                violation = True
            upserting = True
        with lock:
            upserting = False

    metrics_service = MagicMock()
    metrics_service.fetch_all.return_value = {"citation_count": 1}
    metrics_repo = MagicMock()
    metrics_repo.upsert.side_effect = upsert

    rows = [_mock_row(uuid4(), {"doi": f"10.1234/{i}"}) for i in range(8)]

    asyncio.run(_refresh_all(rows, metrics_service, metrics_repo, concurrency=8))

    assert violation is False


@patch("src.bootstrap.build_metrics_refresh_pipeline")
@patch("src.entrypoints.cli.refresh_metrics.init_default_client")
@patch("src.entrypoints.cli.refresh_metrics.configure_logging")
@patch("src.entrypoints.cli.refresh_metrics.validate_config")
def test_concurrency_arg_defaults_to_five(mock_validate, mock_logging, mock_http, mock_pipeline):
    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []
    mock_pipeline.return_value = (metrics_service, MagicMock(), session)

    with patch("sys.argv", ["refresh_metrics"]), \
         patch("src.entrypoints.cli.refresh_metrics._refresh_all", new_callable=AsyncMock) as mock_refresh_all:
        mock_refresh_all.return_value = (0, 0)
        from src.entrypoints.cli.refresh_metrics import main
        main()

    assert mock_refresh_all.call_args.args[3] == 5
