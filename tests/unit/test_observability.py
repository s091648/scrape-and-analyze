import pytest
import json
from io import StringIO


def test_logger_outputs_valid_json(capsys):
    """Logger should output valid JSON"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger("test")
    logger.info("test_event", key="value")

    captured = capsys.readouterr()
    log_line = captured.out.strip()

    parsed = json.loads(log_line)
    assert parsed["event"] == "test_event"
    assert parsed["key"] == "value"


def test_logger_includes_timestamp(capsys):
    """Logger should include ISO timestamp"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger("test")
    logger.info("test_event")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert "timestamp" in parsed
    assert "T" in parsed["timestamp"]


def test_logger_includes_log_level(capsys):
    """Logger should include log level"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger("test")
    logger.warning("warning_event")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["level"] == "warning"


def test_correlation_id_included_in_logs(capsys):
    """Logs should include correlation_id when bound"""
    from src.utils.logging import get_logger, configure_logging, bind_correlation_id

    configure_logging()
    bind_correlation_id("test-correlation-123")
    logger = get_logger("test")
    logger.info("event_with_correlation")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["correlation_id"] == "test-correlation-123"


def test_correlation_id_propagates_across_loggers(capsys):
    """correlation_id should propagate to all loggers in same context"""
    from src.utils.logging import get_logger, configure_logging, bind_correlation_id

    configure_logging()
    bind_correlation_id("shared-correlation-456")

    logger1 = get_logger("module1")
    logger2 = get_logger("module2")

    logger1.info("event1")
    logger2.info("event2")

    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')

    for line in lines:
        parsed = json.loads(line)
        assert parsed["correlation_id"] == "shared-correlation-456"


def test_get_correlation_id_returns_current_value():
    """get_correlation_id should return currently bound value"""
    from src.utils.logging import bind_correlation_id, get_correlation_id

    bind_correlation_id("retrievable-id")
    assert get_correlation_id() == "retrievable-id"
