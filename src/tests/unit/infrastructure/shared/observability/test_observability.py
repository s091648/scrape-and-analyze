"""Tests for structured logging — JSON format, correlation, and field validation."""
import json
import re

from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging


def _parse_log_line(capsys):
    """Helper: read captured output, find the JSON log line, parse it."""
    configure_logging()
    captured = capsys.readouterr()
    match = re.search(r'\{.*\}', captured.out)
    assert match is not None, f"JSON not found in output: {captured.out}"
    return json.loads(match.group())


def test_logger_outputs_json_format(capsys):
    logger = get_logger(__name__)
    logger.info("test_event", key="value")
    log_entry = _parse_log_line(capsys)
    assert "event" in log_entry
    assert log_entry["key"] == "value"


def test_bind_correlation_id_adds_to_logs(capsys):
    bind_correlation_id("test-corr-123")
    logger = get_logger(__name__)
    logger.info("test_event")
    log_entry = _parse_log_line(capsys)
    assert log_entry.get("correlation_id") == "test-corr-123"


def test_log_entry_has_level_field(capsys):
    """Every log entry must contain a 'level' field matching the severity."""
    logger = get_logger(__name__)
    logger.warning("warning_event")
    log_entry = _parse_log_line(capsys)
    assert "level" in log_entry
    assert log_entry["level"] == "warning"


def test_log_entry_has_iso8601_timestamp(capsys):
    """The 'timestamp' field must be a valid ISO 8601 string."""
    from datetime import datetime
    logger = get_logger(__name__)
    logger.info("ts_event")
    log_entry = _parse_log_line(capsys)
    assert "timestamp" in log_entry
    # Should parse without error
    datetime.fromisoformat(log_entry["timestamp"])


def test_correlation_id_bound_across_log_entries(capsys):
    """Multiple log entries within a single run share the same correlation_id."""
    bind_correlation_id("shared-corr-999")
    logger = get_logger(__name__)
    logger.info("first_event")
    captured1 = capsys.readouterr()
    logger.info("second_event")
    captured2 = capsys.readouterr()

    match1 = re.search(r'\{.*\}', captured1.out)
    match2 = re.search(r'\{.*\}', captured2.out)
    assert match1 and match2
    entry1 = json.loads(match1.group())
    entry2 = json.loads(match2.group())
    assert entry1.get("correlation_id") == "shared-corr-999"
    assert entry2.get("correlation_id") == "shared-corr-999"