import pytest
import json


def test_logger_outputs_valid_json(capsys):
    from src.infrastructure.shared.logging import get_logger, configure_logging
    configure_logging()
    logger = get_logger("test")
    logger.info("test_event", key="value")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["event"] == "test_event"
    assert parsed["key"] == "value"


def test_logger_includes_timestamp(capsys):
    from src.infrastructure.shared.logging import get_logger, configure_logging
    configure_logging()
    logger = get_logger("test")
    logger.info("test_event")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert "timestamp" in parsed


def test_logger_includes_log_level(capsys):
    from src.infrastructure.shared.logging import get_logger, configure_logging
    configure_logging()
    logger = get_logger("test")
    logger.warning("warning_event")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["level"] == "warning"


def test_correlation_id_included_in_logs(capsys):
    from src.infrastructure.shared.logging import get_logger, configure_logging, bind_correlation_id
    configure_logging()
    bind_correlation_id("test-correlation-123")
    logger = get_logger("test")
    logger.info("event_with_correlation")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["correlation_id"] == "test-correlation-123"


def test_get_correlation_id_returns_current_value():
    from src.infrastructure.shared.logging import bind_correlation_id, get_correlation_id
    bind_correlation_id("retrievable-id")
    assert get_correlation_id() == "retrievable-id"