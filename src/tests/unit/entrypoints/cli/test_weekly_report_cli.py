"""Unit tests for the weekly_report CLI entrypoint's job-level completion
notification — added when unifying notification format across all five scheduled
jobs (020-redis-caching-layer follow-up). Distinct from GenerateWeeklyReportUseCase's
own per-report email/telegram notifications, tested separately in
test_generate_weekly_report.py."""
from unittest.mock import MagicMock, patch


@patch("src.bootstrap.build_weekly_pipeline")
@patch("src.entrypoints.cli.weekly_report.configure_logging")
@patch("src.entrypoints.cli.weekly_report.validate_config")
def test_publishes_completion_event_with_correct_counts(mock_validate, mock_logging, mock_pipeline):
    from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent

    pipeline = MagicMock()
    pipeline.run.return_value = ([MagicMock(), MagicMock()], 3)  # 2 generated, 3 topics attempted
    session = MagicMock()
    event_bus = MagicMock()
    mock_pipeline.return_value = (pipeline, session, event_bus)

    with patch("sys.argv", ["weekly_report"]):
        from src.entrypoints.cli.weekly_report import main
        main()

    event_bus.publish.assert_called_once()
    published = event_bus.publish.call_args.args[0]
    assert isinstance(published, WeeklyReportJobCompletedEvent)
    assert published.total_topics == 3
    assert published.generated == 2
    assert published.failed == 1


@patch("src.bootstrap.build_weekly_pipeline")
@patch("src.entrypoints.cli.weekly_report.configure_logging")
@patch("src.entrypoints.cli.weekly_report.validate_config")
def test_notification_failure_does_not_fail_the_job(mock_validate, mock_logging, mock_pipeline):
    """FR-012: a notification-sender failure must not raise out of main()."""
    from src.infrastructure.shared.events import InMemoryEventBus
    from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent

    def _raising_handler(event):
        raise ConnectionError("telegram is down")

    event_bus = InMemoryEventBus()
    event_bus.subscribe(WeeklyReportJobCompletedEvent, _raising_handler)

    pipeline = MagicMock()
    pipeline.run.return_value = ([], 0)
    session = MagicMock()
    mock_pipeline.return_value = (pipeline, session, event_bus)

    with patch("sys.argv", ["weekly_report"]):
        from src.entrypoints.cli.weekly_report import main
        main()  # must not raise


@patch("src.bootstrap.build_weekly_pipeline")
@patch("src.entrypoints.cli.weekly_report.configure_logging")
@patch("src.entrypoints.cli.weekly_report.validate_config")
def test_session_closed_after_run(mock_validate, mock_logging, mock_pipeline):
    pipeline = MagicMock()
    pipeline.run.return_value = ([], 0)
    session = MagicMock()
    event_bus = MagicMock()
    mock_pipeline.return_value = (pipeline, session, event_bus)

    with patch("sys.argv", ["weekly_report"]):
        from src.entrypoints.cli.weekly_report import main
        main()

    session.close.assert_called_once()
