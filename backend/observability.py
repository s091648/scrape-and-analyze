"""
Observability setup for the backend FastAPI service — Loki log shipping and
OTel request tracing to Grafana Cloud. Both are no-ops if their GRAFANA_* env
vars are unset (local dev).

backend/ mirrors rather than imports src/infrastructure/shared/observability/*:
src/ is not copied into the backend's production Docker image (see
backend/Dockerfile), so a shared implementation would not be deployable.
Label/name constants are still shared via shared/enums/observability.py, which
both services' Docker images do include.
"""
import base64
import logging
import sys

import structlog

from shared.observability.traceback_filter import format_filtered_traceback
from backend.config import (
    GRAFANA_API_KEY,
    GRAFANA_LOKI_URL,
    GRAFANA_LOKI_USER,
    GRAFANA_OTLP_ENDPOINT,
    GRAFANA_OTLP_USER,
)


class _StructlogMessageFormatter(logging.Formatter):
    """structlog's JSONRenderer already produces the complete, self-contained
    log line (including a filtered traceback under "exception" when relevant
    — see shared/observability/traceback_filter.py). Without this, the
    stdlib logging.Handler default Formatter would append a second, raw,
    unfiltered traceback whenever record.exc_info is set — which happens
    even when we never passed exc_info ourselves, because structlog's
    logger.exception() calls the underlying logging.Logger.exception(),
    whose own signature hardcodes exc_info=True."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


def _add_otel_context(logger, method_name, event_dict):
    """Structlog processor that injects the current OTel trace_id/span_id into log events."""
    try:
        from opentelemetry import trace as _otel_trace
        ctx = _otel_trace.get_current_span().get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass
    return event_dict


def configure_logging(app_env: str) -> None:
    """Attach stdout + optional Loki handler to the root logger, and configure
    structlog for JSON output. Call once at process startup, before the app
    starts handling requests."""
    from shared.enums.observability import LokiAppValue, LokiLabel

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # httpx (used by backend/services/grafana_service.py to proxy Grafana Cloud
    # queries) logs an INFO line per outbound request by default — e.g. "HTTP
    # Request: GET .../query_range ... 200 OK". Since root is at INFO, every one
    # of those propagates through and gets shipped to Loki as a backend log line,
    # burying real application logs under transport-layer noise. Raise both
    # loggers (httpcore is httpx's own transport dependency) to WARNING so only
    # actual connection problems still surface.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(_StructlogMessageFormatter())
    root_logger.addHandler(stdout_handler)

    if all([GRAFANA_LOKI_URL, GRAFANA_LOKI_USER, GRAFANA_API_KEY]):
        try:
            import queue
            from logging_loki import LokiQueueHandler
            # LokiQueueHandler (not the plain LokiHandler) — plain LokiHandler.emit() does a
            # synchronous requests.post() to Grafana Cloud on every single log line, on whatever
            # thread called logger.info(). RequestLoggingMiddleware calls it directly on the
            # asyncio event loop (it's pure ASGI, not run in a threadpool), so that one HTTP
            # round-trip blocked the entire process from making progress on any other in-flight
            # request until it returned — measured adding ~0.5-0.6s to every request (cache HIT
            # or MISS) and compounding under concurrent load. LokiQueueHandler hands the record to
            # a stdlib logging.handlers.QueueListener running on its own background thread, so the
            # actual HTTP POST never blocks the caller.
            loki_handler = LokiQueueHandler(
                queue.Queue(-1),
                url=f"{GRAFANA_LOKI_URL.rstrip('/')}/push",
                auth=(GRAFANA_LOKI_USER, GRAFANA_API_KEY),
                tags={LokiLabel.APP: LokiAppValue.BACKEND, LokiLabel.ENV: app_env},
                version="1",
            )
            loki_handler.setLevel(logging.INFO)
            loki_handler.setFormatter(_StructlogMessageFormatter())
            root_logger.addHandler(loki_handler)
        except Exception as e:
            print(f"Loki handler setup failed: {e}", file=sys.stdout)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _add_otel_context,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.ExceptionRenderer(exception_formatter=format_filtered_traceback),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def setup_tracing(app_env: str):
    """Initialize OTel tracing with a Grafana Cloud OTLP exporter and return the
    TracerProvider. Returns None (no-op tracer) if GRAFANA_OTLP_*/GRAFANA_API_KEY
    are absent."""
    if not all([GRAFANA_OTLP_USER, GRAFANA_API_KEY, GRAFANA_OTLP_ENDPOINT]):
        missing = [
            k
            for k, v in {
                "GRAFANA_OTLP_USER": GRAFANA_OTLP_USER,
                "GRAFANA_API_KEY": GRAFANA_API_KEY,
                "GRAFANA_OTLP_ENDPOINT": GRAFANA_OTLP_ENDPOINT,
            }.items()
            if not v
        ]
        print(f"[tracing] Skipping OTLP setup, missing env vars: {missing}")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from shared.enums.observability import ResourceLabel, SERVICE_NAME_BACKEND

        auth_str = f"{GRAFANA_OTLP_USER}:{GRAFANA_API_KEY}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        resource = Resource.create({
            ResourceLabel.SERVICE_NAME: SERVICE_NAME_BACKEND,
            ResourceLabel.DEPLOYMENT_ENVIRONMENT: app_env,
        })
        exporter = OTLPSpanExporter(
            endpoint=f"{GRAFANA_OTLP_ENDPOINT.rstrip('/')}/v1/traces",
            headers={"Authorization": f"Basic {encoded_auth}"},
            timeout=15,
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Without these, FastAPIInstrumentor above only ever produces one flat span per
        # request — no visibility into whether a slow request was slow because of a DB
        # query, a Redis round-trip, or actual application logic. Each is wrapped in its
        # own try/except so a failure here doesn't take down request-level tracing, which
        # already succeeded by this point.
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from backend.database import engine
            SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
        except Exception as e:
            print(f"[tracing] SQLAlchemy instrumentation failed: {e}")

        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            RedisInstrumentor().instrument(tracer_provider=provider)
        except Exception as e:
            print(f"[tracing] Redis instrumentation failed: {e}")

        # Without this, outgoing httpx calls (ChatCompletionService proxying to
        # chatbot-plugin, grafana_service.py) never carry a W3C `traceparent` header,
        # so the downstream service's own FastAPIInstrumentor has nothing to continue —
        # it just starts a brand new, disconnected trace_id. That's why a slow
        # /chat/completions request showed up here as one opaque 8s span with no
        # visibility into where the time went even after chatbot-plugin got its own
        # spans: this service's trace and chatbot-plugin's trace were never the same
        # trace to begin with. Instrumenting the client makes them one connected trace.
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        except Exception as e:
            print(f"[tracing] httpx client instrumentation failed: {e}")

        print("[tracing] OTLP setup successful")
        return provider
    except Exception as e:
        print(f"[tracing] OTLP setup failed: {e}")
        return None
