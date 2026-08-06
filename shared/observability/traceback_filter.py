"""
Traceback filtering — keeps only stack frames from this project's own code
(backend/, src/, models/, shared/) plus a maintained whitelist of first-party
packages, so a logged/persisted traceback isn't dominated by framework/stdlib
noise. Never touches Sentry, which already has its own in-app frame handling.

Used by backend/observability.py and src/infrastructure/shared/logging.py
(structlog exc_info rendering), and by use cases that persist a traceback
directly (e.g. FailedTask.traceback via format_filtered_exc()).
"""
import importlib.util
import os
import sys
import traceback
from typing import Optional

# Installed packages (beyond this repo's own backend/src/models/shared) whose
# frames should also count as in-app. Maintained by hand — add an entry here
# when a new first-party dependency's internals are worth seeing in full.
_IN_APP_PACKAGES = ["chatbot_plugin_sdk"]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_prefixes() -> list:
    prefixes = [_PROJECT_ROOT]
    for name in _IN_APP_PACKAGES:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            continue
        if spec and spec.origin:
            prefixes.append(os.path.dirname(spec.origin))
    return prefixes


_IN_APP_PREFIXES = _resolve_prefixes()


def _select_in_app(frames):
    """Keep only frames under an in-app prefix; fall back to every frame if
    that would otherwise discard the entire traceback."""
    selected = [f for f in frames if any(f.filename.startswith(p) for p in _IN_APP_PREFIXES)]
    return selected if selected else list(frames)


def _format_single(exc_type, exc, tb) -> str:
    frames = traceback.extract_tb(tb)
    selected = _select_in_app(frames)
    lines = ["Traceback (most recent call last):\n"]
    omitted = len(frames) - len(selected)
    if omitted > 0:
        lines.append(f"  ... {omitted} frame(s) outside this project/whitelisted packages omitted ...\n")
    lines += traceback.format_list(selected)
    lines += traceback.format_exception_only(exc_type, exc)
    return "".join(lines)


def format_filtered_traceback(exc_info) -> str:
    """Render an (exc_type, exc, tb) tuple as plain text, keeping only in-app
    frames at every level of the __cause__/__context__ chain (mirrors how
    traceback.format_exception() itself walks chained exceptions — a
    "raise X from Y" is common when wrapping a library/HTTP-client error,
    and the original cause is usually the actually useful diagnostic).
    Compatible with structlog's ExceptionTransformer signature."""
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
    chain.reverse()  # oldest cause first

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


def format_filtered_exc(exc: Optional[BaseException] = None) -> str:
    """Drop-in replacement for traceback.format_exc() that filters frames to
    this project's own code plus the package whitelist above."""
    if exc is None:
        _, exc, _ = sys.exc_info()
    if exc is None:
        return "NoneType: None\n"
    return format_filtered_traceback((type(exc), exc, exc.__traceback__))
