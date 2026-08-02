"""JSON stdout logging + optional Loki shipping for the fastembed service."""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone

_STANDARD_RECORD_KEYS: frozenset[str] = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None))
)

# In-app prefix for traceback filtering: this service's own source directory.
_IN_APP_PREFIXES = [os.path.dirname(os.path.abspath(__file__))]


def _format_single(exc_type, exc, tb) -> str:
    """Plain-text traceback keeping only frames under _IN_APP_PREFIXES; falls
    back to the full traceback if that would discard every frame."""
    frames = traceback.extract_tb(tb)
    selected = [f for f in frames if any(f.filename.startswith(p) for p in _IN_APP_PREFIXES)]
    if not selected:
        selected = list(frames)
    lines = ["Traceback (most recent call last):\n"]
    omitted = len(frames) - len(selected)
    if omitted > 0:
        lines.append(f"  ... {omitted} frame(s) outside this project/whitelisted packages omitted ...\n")
    lines += traceback.format_list(selected)
    lines += traceback.format_exception_only(exc_type, exc)
    return "".join(lines)


def _format_filtered_exception(exc_info) -> str:
    """Render exc_info as plain text, keeping only in-app frames at every
    level of the __cause__/__context__ chain (mirrors how
    traceback.format_exception() walks chained exceptions)."""
    _, top_exc, top_tb = exc_info

    chain = []
    current = top_exc
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        if current.__cause__ is not None:
            current = current.__cause__
        elif current.__context__ is not None and not current.__suppress_context__:
            current = current.__context__
        else:
            current = None
    chain.reverse()

    parts = []
    for i, exc in enumerate(chain):
        if i > 0:
            prev = chain[i - 1]
            connector = (
                "\nThe above exception was the direct cause of the following exception:\n\n"
                if exc.__cause__ is prev
                else "\nDuring handling of the above exception, another exception occurred:\n\n"
            )
            parts.append(connector)
        tb = top_tb if exc is top_exc else exc.__traceback__
        parts.append(_format_single(type(exc), exc, tb))
    return "".join(parts)


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
            payload["exception"] = _format_filtered_exception(record.exc_info)
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
