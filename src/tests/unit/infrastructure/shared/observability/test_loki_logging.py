"""Tests for Loki logging — no-op fallback and configured behavior."""
import json
import logging
import sys
from unittest.mock import patch, MagicMock


def test_loki_handler_not_attached_without_env(monkeypatch):
    """Only stdout handler is attached when GRAFANA_LOKI_* env vars are missing."""
    monkeypatch.delenv("GRAFANA_LOKI_URL", raising=False)
    monkeypatch.delenv("GRAFANA_LOKI_USER", raising=False)
    monkeypatch.delenv("GRAFANA_API_KEY", raising=False)
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    from src.infrastructure.shared.observability.loki_logging import configure_loki
    configure_loki()
    handler_types = [type(h).__name__ for h in root.handlers]
    assert "StreamHandler" in handler_types
    assert "LokiHandler" not in handler_types


def test_stdout_handler_always_attached(monkeypatch):
    """StreamHandler(sys.stdout) is attached regardless of Loki configuration."""
    monkeypatch.delenv("GRAFANA_LOKI_URL", raising=False)
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    from src.infrastructure.shared.observability.loki_logging import configure_loki
    configure_loki()
    has_stdout = any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        for h in root.handlers
    )
    assert has_stdout


def test_loki_handler_attached_with_env(monkeypatch):
    """LokiHandler is attached when all GRAFANA_LOKI_* env vars are set."""
    monkeypatch.setenv("GRAFANA_LOKI_URL", "http://loki:3100/loki/api/v1/push")
    monkeypatch.setenv("GRAFANA_LOKI_USER", "user")
    monkeypatch.setenv("GRAFANA_API_KEY", "key")
    root = logging.getLogger()
    initial_handlers = root.handlers[:]
    for h in root.handlers[:]:
        root.removeHandler(h)
    mock_loki_handler = MagicMock()
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.return_value = mock_loki_handler
    with patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
        from src.infrastructure.shared.observability.loki_logging import configure_loki
        configure_loki()
    assert mock_loki_handler in root.handlers
    # Restore root logger: remove test handlers, re-add original ones
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in initial_handlers:
        root.addHandler(h)


def test_sdk_logger_gets_its_own_loki_handler_with_json_formatter(monkeypatch):
    """The SDK logger must get a distinct LokiHandler instance formatted with
    _SdkJsonFormatter, not the app's LokiHandler (which uses _StructlogMessageFormatter
    and would silently drop the SDK record's real level — see module docstring)."""
    monkeypatch.setenv("GRAFANA_LOKI_URL", "http://loki:3100/loki/api/v1/push")
    monkeypatch.setenv("GRAFANA_LOKI_USER", "user")
    monkeypatch.setenv("GRAFANA_API_KEY", "key")
    root = logging.getLogger()
    initial_root_handlers = root.handlers[:]
    for h in root.handlers[:]:
        root.removeHandler(h)
    sdk_logger = logging.getLogger("chatbot_plugin_sdk")
    initial_sdk_handlers = sdk_logger.handlers[:]
    sdk_logger.handlers.clear()

    created_handlers = [MagicMock(), MagicMock()]
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.side_effect = created_handlers
    with patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
        from src.infrastructure.shared.observability.loki_logging import configure_loki
        configure_loki()

    from src.infrastructure.shared.observability.loki_logging import _SdkJsonFormatter, _StructlogMessageFormatter
    app_handler, sdk_handler = created_handlers
    assert mock_loki_module.LokiHandler.call_count == 2
    assert app_handler in root.handlers
    assert sdk_handler not in root.handlers
    assert sdk_handler in sdk_logger.handlers
    assert isinstance(app_handler.setFormatter.call_args.args[0], _StructlogMessageFormatter)
    assert isinstance(sdk_handler.setFormatter.call_args.args[0], _SdkJsonFormatter)

    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in initial_root_handlers:
        root.addHandler(h)
    sdk_logger.handlers.clear()
    for h in initial_sdk_handlers:
        sdk_logger.addHandler(h)


# ---------------------------------------------------------------------------
# _SdkJsonFormatter
# ---------------------------------------------------------------------------

def _make_log_record(name="chatbot_plugin_sdk", level=logging.INFO, msg="test message", extra=None):
    record = logging.LogRecord(
        name=name, level=level, pathname="", lineno=0,
        msg=msg, args=(), exc_info=None,
    )
    if extra:
        record.extra = extra
    return record


def test_sdk_json_formatter_basic_message():
    from src.infrastructure.shared.observability.loki_logging import _SdkJsonFormatter
    formatter = _SdkJsonFormatter()
    record = _make_log_record(msg="hello world")
    output = formatter.format(record)
    data = json.loads(output)
    assert data["event"] == "hello world"
    assert data["level"] == "info"
    assert data["logger"] == "chatbot_plugin_sdk"
    assert "timestamp" in data


def test_sdk_json_formatter_includes_extra_fields():
    from src.infrastructure.shared.observability.loki_logging import _SdkJsonFormatter
    formatter = _SdkJsonFormatter()
    record = _make_log_record(extra={"request_id": "abc123", "duration": 42})
    output = formatter.format(record)
    data = json.loads(output)
    assert data["request_id"] == "abc123"
    assert data["duration"] == 42


def test_sdk_json_formatter_includes_exc_info():
    from src.infrastructure.shared.observability.loki_logging import _SdkJsonFormatter
    formatter = _SdkJsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="chatbot_plugin_sdk", level=logging.ERROR, pathname="", lineno=0,
        msg="error occurred", args=(), exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert "exc_info" in data
    assert "ValueError" in data["exc_info"]


def test_sdk_json_formatter_omits_correlation_id_when_not_set(monkeypatch):
    """When correlation_id is not set, the key is absent from the output."""
    from src.infrastructure.shared.observability.loki_logging import _SdkJsonFormatter
    # Patch get_correlation_id to return None
    with patch("src.infrastructure.shared.observability.loki_logging._SdkJsonFormatter.format") as _:
        pass  # just ensure import works

    formatter = _SdkJsonFormatter()
    with patch("src.infrastructure.shared.logging.get_correlation_id", return_value=None):
        record = _make_log_record(msg="no corr id")
        output = formatter.format(record)
    data = json.loads(output)
    assert "correlation_id" not in data


# ---------------------------------------------------------------------------
# _configure_sdk_logging
# ---------------------------------------------------------------------------

def test_configure_sdk_logging_sets_propagate_false():
    from src.infrastructure.shared.observability.loki_logging import _configure_sdk_logging
    sdk_logger = logging.getLogger("chatbot_plugin_sdk")
    _configure_sdk_logging()
    assert sdk_logger.propagate is False


def test_configure_sdk_logging_adds_stdout_handler():
    from src.infrastructure.shared.observability.loki_logging import _configure_sdk_logging
    sdk_logger = logging.getLogger("chatbot_plugin_sdk")
    # Remove existing handlers to get a clean state
    sdk_logger.handlers.clear()
    _configure_sdk_logging()
    has_stdout = any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        for h in sdk_logger.handlers
    )
    assert has_stdout


def test_configure_sdk_logging_adds_loki_handler_when_provided():
    from src.infrastructure.shared.observability.loki_logging import _configure_sdk_logging
    sdk_logger = logging.getLogger("chatbot_plugin_sdk")
    mock_loki = MagicMock(spec=logging.Handler)
    mock_loki.level = logging.INFO
    _configure_sdk_logging(mock_loki)
    assert mock_loki in sdk_logger.handlers
    sdk_logger.removeHandler(mock_loki)


# ---------------------------------------------------------------------------
# Loki setup failure fallback
# ---------------------------------------------------------------------------

def test_loki_setup_failure_is_swallowed(monkeypatch):
    """If LokiHandler() raises, configure_loki() prints a message but does not raise."""
    monkeypatch.setenv("GRAFANA_LOKI_URL", "http://loki:3100")
    monkeypatch.setenv("GRAFANA_LOKI_USER", "user")
    monkeypatch.setenv("GRAFANA_API_KEY", "key")
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    mock_loki_module = MagicMock()
    mock_loki_module.LokiHandler.side_effect = Exception("Connection refused")
    with patch.dict("sys.modules", {"logging_loki": mock_loki_module}):
        from src.infrastructure.shared.observability.loki_logging import configure_loki
        configure_loki()  # should not raise
    # stdout handler must still be attached
    has_stdout = any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        for h in root.handlers
    )
    assert has_stdout
