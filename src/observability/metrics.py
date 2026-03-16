import os
import base64
import requests
from opentelemetry import metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

def _setup_otel():
    user = os.environ.get("GRAFANA_OTLP_USER", "").strip()
    api_key = os.environ.get("GRAFANA_API_KEY", "").strip()
    endpoint = os.environ.get("GRAFANA_OTLP_ENDPOINT", "").strip()

    # ✅ 三個變數都要檢查
    if not all([user, api_key, endpoint]):
        missing = [k for k, v in {
            "GRAFANA_OTLP_USER": user,
            "GRAFANA_API_KEY": api_key,
            "GRAFANA_OTLP_ENDPOINT": endpoint,
        }.items() if not v]
        print(f"[metrics] Skipping OTLP setup, missing env vars: {missing}")
        return None, None

    auth_str = f"{user}:{api_key}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()

    try:
        resource = Resource.create({"service.name": "scrape-analyzer"})

        exporter = OTLPMetricExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/metrics",
            headers={"Authorization": f"Basic {encoded_auth}"},
            timeout=15,
        )

        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=30_000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)

        print("[metrics] OTLP setup successful")
        return provider, metrics.get_meter("scraper_metrics")

    except Exception as e:
        # ✅ 至少印出錯誤，方便 debug
        print(f"[metrics] OTLP setup failed: {e}")
        return None, None

provider, meter = _setup_otel()

# --- 指標定義保持不變 ---
if meter:
    SCRAPER_RUNS = meter.create_counter("scraper_runs_total")
    SCRAPER_DURATION = meter.create_histogram("scraper_run_duration_seconds")
    SCRAPER_ARTICLES_FOUND = meter.create_counter("scraper_articles_found_total")
    SCRAPER_ARTICLES_NEW = meter.create_counter("scraper_articles_new_total")
    SCRAPER_ARTICLES_DUPLICATE = meter.create_counter("scraper_articles_duplicate_total")
    SCRAPER_ERRORS = meter.create_counter("scraper_errors_total")
else:
    class Dummy:
        def add(self, *a, **k): pass
        def record(self, *a, **k): pass
    SCRAPER_RUNS = SCRAPER_DURATION = SCRAPER_ARTICLES_FOUND = SCRAPER_ARTICLES_NEW = SCRAPER_ARTICLES_DUPLICATE = SCRAPER_ERRORS = Dummy()

def push_metrics():
    if provider:
        provider.shutdown()