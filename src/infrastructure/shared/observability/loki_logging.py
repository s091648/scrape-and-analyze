"""
Loki log handler — optional sink that ships structlog JSON to Grafana Loki.
Called once by configure_logging() at process startup.

SDK log integration
-------------------
Third-party libraries (e.g. chatbot_plugin_sdk) use stdlib ``logging.getLogger(__name__)``.
Their records would propagate to the root logger and appear in plain text format, mixed with
the main app's structlog JSON.

To normalise them, ``_configure_sdk_logging()`` attaches a dedicated ``_SdkJsonFormatter``
to a named handler on ``logging.getLogger("chatbot_plugin_sdk")``.
``propagate=False`` prevents the plain-text root handler from duplicating the record;
the LokiHandler is added directly to the SDK logger instead so records still reach Loki.

In Grafana / Loki, filter SDK records with:
    ``{app="scraper"} | json | logger =~ "chatbot_plugin_sdk.*"``
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone

from src.config.settings import APP_ENV


# --- SDK JSON formatter (reads correlation_id from the ContextVar) ------------------

class _SdkJsonFormatter(logging.Formatter):
    """Formats stdlib LogRecord from chatbot_plugin_sdk as a JSON line matching
    the main app's structlog output shape."""

    def format(self, record: logging.LogRecord) -> str:
        extra = record.__dict__.get("extra") or {}
        # ContextVar is imported lazily to avoid a circular import at module load
        try:
            from src.infrastructure.shared.logging import get_correlation_id
            corr_id = get_correlation_id() or None
        except Exception:
            corr_id = None

        payload: dict = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
        }
        if corr_id:
            payload["correlation_id"] = corr_id
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _configure_sdk_logging(loki_handler: logging.Handler | None = None) -> None:
    """Route chatbot_plugin_sdk stdlib logs through _SdkJsonFormatter.

    Sets propagate=False so the root handler does not emit a second, plain-text copy.
    If a LokiHandler is provided it is added directly so SDK records still reach Loki.
    """
    fmt = _SdkJsonFormatter()

    sdk_stdout = logging.StreamHandler(sys.stdout)
    sdk_stdout.setLevel(logging.DEBUG)
    sdk_stdout.setFormatter(fmt)

    sdk_logger = logging.getLogger("chatbot_plugin_sdk")
    sdk_logger.setLevel(logging.DEBUG)
    sdk_logger.addHandler(sdk_stdout)
    if loki_handler is not None:
        sdk_logger.addHandler(loki_handler)
    sdk_logger.propagate = False  # prevent double-printing to root's plain-text handler


def configure_loki() -> None:
    """Set up stdout handler and optional Loki handler for the root logger,
    then configure SDK logging separately."""
    # Read directly from os.environ (not the frozen settings constants) so tests
    # that set/unset these env vars per-case take effect without a module reload.
    url = os.environ.get("GRAFANA_LOKI_URL") or None
    user = os.environ.get("GRAFANA_LOKI_USER") or None
    key = os.environ.get("GRAFANA_API_KEY") or None

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Always attach stdout so structlog messages appear in container logs
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    root_logger.addHandler(stdout_handler)

    loki_handler: logging.Handler | None = None
    if all([url, user, key]):
        try:
            from logging_loki import LokiHandler
            from shared.enums.observability import LokiLabel, LokiAppValue
            app_env = APP_ENV.strip()
            loki_handler = LokiHandler(
                url=f"{url.rstrip('/')}/push",
                auth=(user, key),
                tags={LokiLabel.APP: LokiAppValue.SCRAPER, LokiLabel.ENV: app_env},
                version="1",
            )
            loki_handler.setLevel(logging.INFO)
            root_logger.addHandler(loki_handler)
        except Exception as e:
            print(f"Loki handler setup failed: {e}", file=sys.stdout)

    _configure_sdk_logging(loki_handler)
