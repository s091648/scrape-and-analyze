import json


def test_logger_outputs_json_format(capsys):
    from src.infrastructure.shared.logging import get_logger, configure_logging
    configure_logging()
    logger = get_logger(__name__)
    logger.info("test_event", key="value")
    captured = capsys.readouterr()
    log_entry = json.loads(captured.out.strip())
    assert "event" in log_entry
    assert log_entry["key"] == "value"


def test_bind_correlation_id_adds_to_logs(capsys):
    from src.infrastructure.shared.logging import get_logger, bind_correlation_id, configure_logging
    configure_logging()
    bind_correlation_id("test-corr-123")
    logger = get_logger(__name__)
    logger.info("test_event")
    captured = capsys.readouterr()
    log_entry = json.loads(captured.out.strip())
    assert log_entry.get("correlation_id") == "test-corr-123"