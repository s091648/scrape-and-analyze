import pytest
import json
import re


def test_logger_outputs_valid_json(capsys):
    from src.shared.logging import get_logger
    from src.infrastructure.shared.logging import configure_logging
    configure_logging()
    logger = get_logger("test")
    logger.info("test_event", key="value")
    captured = capsys.readouterr()
    # Find JSON line in output (may have log prefix like "INFO ...")
    json_match = re.search(r'\{.*"event":\s*"test_event".*\}', captured.out)
    assert json_match is not None, f"JSON not found in output: {captured.out}"
    parsed = json.loads(json_match.group())
    assert parsed["event"] == "test_event"
    assert parsed["key"] == "value"


def test_logger_includes_timestamp(capsys):
    from src.shared.logging import get_logger
    from src.infrastructure.shared.logging import configure_logging
    configure_logging()
    logger = get_logger("test")
    logger.info("test_event")
    captured = capsys.readouterr()
    json_match = re.search(r'\{.*\}', captured.out)
    assert json_match is not None
    parsed = json.loads(json_match.group())
    assert "timestamp" in parsed


def test_logger_includes_log_level(capsys):
    from src.shared.logging import get_logger
    from src.infrastructure.shared.logging import configure_logging
    configure_logging()
    logger = get_logger("test")
    logger.warning("warning_event")
    captured = capsys.readouterr()
    json_match = re.search(r'\{.*\}', captured.out)
    assert json_match is not None
    parsed = json.loads(json_match.group())
    assert parsed["level"] == "warning"


def test_correlation_id_included_in_logs(capsys):
    from src.shared.logging import get_logger
    from src.infrastructure.shared.logging import configure_logging, bind_correlation_id
    configure_logging()
    bind_correlation_id("test-correlation-123")
    logger = get_logger("test")
    logger.info("event_with_correlation")
    captured = capsys.readouterr()
    json_match = re.search(r'\{.*\}', captured.out)
    assert json_match is not None
    parsed = json.loads(json_match.group())
    assert parsed["correlation_id"] == "test-correlation-123"


def test_get_correlation_id_returns_current_value():
    from src.infrastructure.shared.logging import bind_correlation_id, get_correlation_id
    bind_correlation_id("retrievable-id")
    assert get_correlation_id() == "retrievable-id"