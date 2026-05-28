import json


def test_logger_outputs_json_format(capsys):
    from src.shared.logging import get_logger
    from src.infrastructure.shared.logging import configure_logging
    configure_logging()
    logger = get_logger(__name__)
    logger.info("test_event", key="value")
    captured = capsys.readouterr()
    import re
    json_match = re.search(r'\{.*"event":\s*"test_event".*\}', captured.out)
    assert json_match is not None, f"JSON not found in output: {captured.out}"
    log_entry = json.loads(json_match.group())
    assert "event" in log_entry
    assert log_entry["key"] == "value"


def test_bind_correlation_id_adds_to_logs(capsys):
    from src.shared.logging import get_logger
    from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
    configure_logging()
    bind_correlation_id("test-corr-123")
    logger = get_logger(__name__)
    logger.info("test_event")
    captured = capsys.readouterr()
    import re
    json_match = re.search(r'\{.*\}', captured.out)
    assert json_match is not None
    log_entry = json.loads(json_match.group())
    assert log_entry.get("correlation_id") == "test-corr-123"