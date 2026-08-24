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


def _add_otel_context(record: logging.LogRecord) -> bool:
    """logging.Filter that injects the current OTel trace_id/span_id onto the
    record so Loki log lines correlate with Tempo traces by trace_id — mirrors
    chatbot-plugin/backend's own _add_otel_context. Always returns True (a
    no-op filter never drops records); safe when no TracerProvider is
    configured, since the default tracer's span context is simply invalid."""
    try:
        from opentelemetry import trace as _otel_trace
        ctx = _otel_trace.get_current_span().get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
    except Exception:
        pass
    return True


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
    stdout.addFilter(_add_otel_context)
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
            loki_handler.addFilter(_add_otel_context)
            root.addHandler(loki_handler)
        except Exception as exc:
            print(f"Loki handler setup failed: {exc}", file=sys.stdout)


def setup_tracing(app_env: str, otlp_endpoint: str, otlp_user: str, api_key: str):
    """Initialize OTel tracing with a Grafana Cloud OTLP exporter and return the
    TracerProvider. Returns None (no-op tracer) if any of otlp_endpoint/
    otlp_user/api_key are absent.

    Mirrors chatbot-plugin/backend's setup_tracing() — same Grafana Cloud
    tenant/credentials, separate service.name so traces from this service are
    distinguishable. No SQLAlchemy/httpx client instrumentation (unlike
    chatbot-plugin/backend): this service has no DB and makes no outbound
    HTTP calls of its own — it's purely a callee (src/ at ingestion time,
    chatbot-plugin at query time). FastAPIInstrumentor is what matters here:
    it continues the caller's trace via the incoming `traceparent` header
    (chatbot-plugin's own HTTPXClientInstrumentor already sends one) instead
    of starting a new, disconnected trace_id for every /embed call.
    """
    if not all([otlp_endpoint, otlp_user, api_key]):
        missing = [
            k
            for k, v in {
                "GRAFANA_OTLP_ENDPOINT": otlp_endpoint,
                "GRAFANA_OTLP_USER": otlp_user,
                "GRAFANA_API_KEY": api_key,
            }.items()
            if not v
        ]
        print(f"[tracing] Skipping OTLP setup, missing env vars: {missing}", file=sys.stdout)
        return None

    try:
        import base64
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        auth_str = f"{otlp_user}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        resource = Resource.create({
            "service.name": "fastembed",
            "deployment.environment": app_env,
        })
        exporter = OTLPSpanExporter(
            endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces",
            headers={"Authorization": f"Basic {encoded_auth}"},
            timeout=15,
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        print("[tracing] OTLP setup successful", file=sys.stdout)
        return provider
    except Exception as e:
        print(f"[tracing] OTLP setup failed: {e}", file=sys.stdout)
        return None
