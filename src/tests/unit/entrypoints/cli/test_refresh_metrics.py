"""
Unit tests for the refresh_metrics CLI entrypoint — covers staleness-query
param derivation, identifier resolution from article metadata, and the
conditional upsert-only-on-non-empty-result behavior.
"""
from unittest.mock import MagicMock, patch
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

    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    metrics_service.fetch_all.side_effect = [
        {"citation_count": 10},  # first article resolves
        {},                       # second article resolves nothing
    ]

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

    metrics_service = MagicMock()
    metrics_service.tracked_metric_keys = ["citation_count"]
    metrics_service.fetch_all.side_effect = [Exception("network error"), {"citation_count": 3}]

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
