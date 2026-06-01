"""
OTel tracing implementation — satisfies TracerPort.

Exports spans to Grafana Cloud (OTLP/HTTP) when GRAFANA_* env vars are set.
Falls back to a no-op tracer automatically via the OTel SDK.

To swap backends (e.g. Jaeger, Zipkin):
  1. Return a different TracerProvider / exporter from _setup_tracing().
  2. No other file needs to change.
"""
import base64
import os


def _setup_tracing():
    user = os.environ.get("GRAFANA_OTLP_USER", "").strip()
    api_key = os.environ.get("GRAFANA_API_KEY", "").strip()
    endpoint = os.environ.get("GRAFANA_OTLP_ENDPOINT", "").strip()

    if not all([user, api_key, endpoint]):
        missing = [
            k
            for k, v in {
                "GRAFANA_OTLP_USER": user,
                "GRAFANA_API_KEY": api_key,
                "GRAFANA_OTLP_ENDPOINT": endpoint,
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

        auth_str = f"{user}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        from shared.enums.observability import SERVICE_NAME, ResourceLabel
        app_env = os.environ.get("APP_ENV", "local").strip()
        resource = Resource.create({
            ResourceLabel.SERVICE_NAME: SERVICE_NAME,
            ResourceLabel.DEPLOYMENT_ENVIRONMENT: app_env,
        })
        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
            headers={"Authorization": f"Basic {encoded_auth}"},
            timeout=15,
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        print("[tracing] OTLP setup successful")
        return provider
    except Exception as e:
        print(f"[tracing] OTLP setup failed: {e}")
        return None


_provider = _setup_tracing()

from opentelemetry import trace as _otel_trace
from shared.enums.observability import SERVICE_NAME
_tracer = _otel_trace.get_tracer(SERVICE_NAME)


def get_tracer():
    """Return the module-level OTel tracer (satisfies TracerPort)."""
    return _tracer


def shutdown_tracing() -> None:
    """Flush and shut down the tracer provider (call once at process exit)."""
    if _provider:
        _provider.shutdown()
