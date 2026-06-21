"""JSON stdout logging + optional Loki shipping for the fastembed service."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_STANDARD_RECORD_KEYS: frozenset[str] = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None))
)


class _JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "service": self._service,
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
        }
        for key, val in vars(record).items():
            if key not in _STANDARD_RECORD_KEYS and not key.startswith("_"):
                payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    service: str,
    loki_url: str = "",
    loki_user: str = "",
    loki_api_key: str = "",
    app_env: str = "local",
) -> None:
    fmt = _JsonFormatter(service)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(logging.INFO)
    stdout.setFormatter(fmt)
    root.addHandler(stdout)

    if all([loki_url, loki_user, loki_api_key]):
        try:
            from logging_loki import LokiHandler  # type: ignore[import]
            loki_handler = LokiHandler(
                url=f"{loki_url.rstrip('/')}/push",
                auth=(loki_user, loki_api_key),
                tags={"app": service, "env": app_env},
                version="1",
            )
            loki_handler.setLevel(logging.INFO)
            loki_handler.setFormatter(fmt)
            root.addHandler(loki_handler)
        except Exception as exc:
            print(f"Loki handler setup failed: {exc}", file=sys.stdout)
