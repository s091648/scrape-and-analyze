"""Tests for Loki logging — no-op fallback and configured behavior."""
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
