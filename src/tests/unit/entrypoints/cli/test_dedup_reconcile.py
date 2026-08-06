"""
Unit tests for the dedup_reconcile CLI entrypoint — covers the three outcomes
per candidate article (still-canonical / healed / merged), per-article
failure isolation, and query construction.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4


def _mock_row(article_id, work_id):
    row = MagicMock()
    row.article_id = article_id
    row.work_id = work_id
    return row


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_no_candidates_skips_everything(mock_validate, mock_logging, mock_http, mock_pipeline):
    client = MagicMock()
    dedup_repo = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    client.fetch_by_id.assert_not_called()
    dedup_repo.merge.assert_not_called()


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_limit_arg_passed_to_query(mock_validate, mock_logging, mock_http, mock_pipeline):
    client = MagicMock()
    dedup_repo = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = []
    session = MagicMock()
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile", "--limit", "50"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    dedup_repo.find_pending_reconciliation.assert_called_once_with(50)


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_unchanged_work_id_marks_reconciled_only(mock_validate, mock_logging, mock_http, mock_pipeline):
    article_id = uuid4()
    client = MagicMock()
    client.fetch_by_id.return_value = {"id": "https://openalex.org/W1"}
    dedup_repo = MagicMock()
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = [_mock_row(article_id, "https://openalex.org/W1")]
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    dedup_repo.mark_reconciled.assert_called_once_with(article_id)
    dedup_repo.heal_identifiers.assert_not_called()
    dedup_repo.merge.assert_not_called()


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_merged_work_id_without_local_survivor_heals_identifiers(mock_validate, mock_logging, mock_http, mock_pipeline):
    """OpenAlex merged this article's work_id away, but we never scraped the
    survivor separately — no local duplicate to merge with, just heal metadata."""
    article_id = uuid4()
    client = MagicMock()
    client.fetch_by_id.return_value = {
        "id": "https://openalex.org/W2",
        "ids": {"doi": "https://doi.org/10.5555/new"},
    }
    dedup_repo = MagicMock()
    dedup_repo.find_by_work_id.return_value = None
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = [_mock_row(article_id, "https://openalex.org/W1")]
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    dedup_repo.heal_identifiers.assert_called_once_with(article_id, "https://openalex.org/W2", "10.5555/new")
    dedup_repo.merge.assert_not_called()


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_merged_work_id_with_local_survivor_triggers_merge(mock_validate, mock_logging, mock_http, mock_pipeline):
    loser_id = uuid4()
    survivor_id = uuid4()
    client = MagicMock()
    client.fetch_by_id.return_value = {"id": "https://openalex.org/W2"}
    dedup_repo = MagicMock()
    dedup_repo.find_by_work_id.return_value = survivor_id
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = [_mock_row(loser_id, "https://openalex.org/W1")]
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    dedup_repo.merge.assert_called_once_with(loser_id=loser_id, survivor_id=survivor_id)
    dedup_repo.heal_identifiers.assert_not_called()


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_fetch_failure_is_skipped_without_repo_calls(mock_validate, mock_logging, mock_http, mock_pipeline):
    article_id = uuid4()
    client = MagicMock()
    client.fetch_by_id.return_value = None
    dedup_repo = MagicMock()
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = [_mock_row(article_id, "https://openalex.org/W1")]
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    dedup_repo.mark_reconciled.assert_not_called()
    dedup_repo.heal_identifiers.assert_not_called()
    dedup_repo.merge.assert_not_called()


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_one_article_failure_does_not_abort_the_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    failing_article = uuid4()
    ok_article = uuid4()
    client = MagicMock()
    client.fetch_by_id.side_effect = [Exception("network error"), {"id": "https://openalex.org/W-ok"}]
    dedup_repo = MagicMock()
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = [
        _mock_row(failing_article, "https://openalex.org/W-fail"),
        _mock_row(ok_article, "https://openalex.org/W-ok"),
    ]
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()  # must not raise

    dedup_repo.mark_reconciled.assert_called_once_with(ok_article)


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_session_closed_after_run(mock_validate, mock_logging, mock_http, mock_pipeline):
    client = MagicMock()
    dedup_repo = MagicMock()
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = []
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    session.close.assert_called_once()


@patch("src.bootstrap.build_dedup_reconciliation_pipeline")
@patch("src.entrypoints.cli.dedup_reconcile.init_default_client")
@patch("src.entrypoints.cli.dedup_reconcile.configure_logging")
@patch("src.entrypoints.cli.dedup_reconcile.validate_config")
def test_session_closed_even_when_an_article_raises(mock_validate, mock_logging, mock_http, mock_pipeline):
    client = MagicMock()
    client.fetch_by_id.side_effect = Exception("boom")
    dedup_repo = MagicMock()
    session = MagicMock()
    dedup_repo.find_pending_reconciliation.return_value = [_mock_row(uuid4(), "https://openalex.org/W1")]
    mock_pipeline.return_value = (client, dedup_repo, session)

    with patch("sys.argv", ["dedup_reconcile"]):
        from src.entrypoints.cli.dedup_reconcile import main
        main()

    session.close.assert_called_once()
