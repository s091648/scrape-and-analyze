import os
import base64
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


def _setup_tracing() -> Optional[TracerProvider]:
    user = os.environ.get("GRAFANA_OTLP_USER", "").strip()
    api_key = os.environ.get("GRAFANA_API_KEY", "").strip()
    endpoint = os.environ.get("GRAFANA_OTLP_ENDPOINT", "").strip()

    if not all([user, api_key, endpoint]):
        missing = [k for k, v in {
            "GRAFANA_OTLP_USER": user,
            "GRAFANA_API_KEY": api_key,
            "GRAFANA_OTLP_ENDPOINT": endpoint,
        }.items() if not v]
        print(f"[tracing] Skipping OTLP setup, missing env vars: {missing}")
        return None

    try:
        auth_str = f"{user}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        resource = Resource.create({"service.name": "scrape-analyzer"})
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
_tracer = trace.get_tracer("scrape-analyzer")


def get_tracer() -> trace.Tracer:
    return _tracer


def shutdown_tracing() -> None:
    if _provider:
        _provider.shutdown()
