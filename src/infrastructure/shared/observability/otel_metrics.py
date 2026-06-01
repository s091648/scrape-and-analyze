"""
OTel metrics implementation — satisfies CounterPort and HistogramPort.

Exports to Grafana Cloud (OTLP/HTTP) when GRAFANA_* env vars are set.
Falls back to a no-op Dummy when env vars are missing so the app starts
in any environment without requiring a metrics backend.

To swap backends (e.g. Prometheus):
  1. Implement CounterPort / HistogramPort from ports.py.
  2. Replace the module-level exports (SCRAPER_RUNS, etc.) here.
  3. No other file needs to change.
"""
import base64
import os


def _setup_otel():
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
        print(f"[metrics] Skipping OTLP setup, missing env vars: {missing}")
        return None, None

    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        auth_str = f"{user}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        from shared.enums.observability import SERVICE_NAME, ResourceLabel
        resource = Resource.create({ResourceLabel.SERVICE_NAME: SERVICE_NAME})
        exporter = OTLPMetricExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/metrics",
            headers={"Authorization": f"Basic {encoded_auth}"},
            timeout=15,
        )
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=30_000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)

        from shared.enums.observability import SERVICE_NAME
        print("[metrics] OTLP setup successful")
        return provider, metrics.get_meter(f"{SERVICE_NAME}_metrics")

    except Exception as e:
        print(f"[metrics] OTLP setup failed: {e}")
        return None, None


class _Dummy:
    """No-op Counter / Histogram satisfying CounterPort and HistogramPort."""
    def add(self, *a, **k): pass
    def record(self, *a, **k): pass


_provider, _meter = _setup_otel()

if _meter:
    from shared.enums.observability import MetricName
    SCRAPER_RUNS = _meter.create_counter(MetricName.RUNS_TOTAL)
    SCRAPER_DURATION = _meter.create_histogram(MetricName.RUN_DURATION_SECONDS)
    SCRAPER_ARTICLES_FOUND = _meter.create_counter(MetricName.ARTICLES_FOUND_TOTAL)
    SCRAPER_ARTICLES_NEW = _meter.create_counter(MetricName.ARTICLES_NEW_TOTAL)
    SCRAPER_ARTICLES_DUPLICATE = _meter.create_counter(MetricName.ARTICLES_DUPLICATE_TOTAL)
    SCRAPER_ERRORS = _meter.create_counter(MetricName.ERRORS_TOTAL)
else:
    SCRAPER_RUNS = _Dummy()
    SCRAPER_DURATION = _Dummy()
    SCRAPER_ARTICLES_FOUND = _Dummy()
    SCRAPER_ARTICLES_NEW = _Dummy()
    SCRAPER_ARTICLES_DUPLICATE = _Dummy()
    SCRAPER_ERRORS = _Dummy()


def push_metrics() -> None:
    """Flush and shut down the metric provider (call once at process exit)."""
    if _provider:
        _provider.shutdown()
