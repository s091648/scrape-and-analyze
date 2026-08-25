"""Fastembed service settings — reads from environment variables only."""
import os

# Models to serve (prefix EMBED_ avoids collision with RAG_SPARSE_MODEL in scraper)
EMBED_SPARSE_MODEL: str = os.environ.get("EMBED_SPARSE_MODEL", "prithivida/Splade_PP_en_v1")
EMBED_SPARSE_BATCH_SIZE: int = int(os.environ.get("EMBED_SPARSE_BATCH_SIZE", "8"))
EMBED_DENSE_MODEL: str = os.environ.get("EMBED_DENSE_MODEL", "")
EMBED_DENSE_BATCH_SIZE: int = int(os.environ.get("EMBED_DENSE_BATCH_SIZE", "32"))

FASTEMBED_CACHE_PATH: str | None = os.environ.get("FASTEMBED_CACHE_PATH") or None

# Observability
APP_ENV: str = os.environ.get("APP_ENV", "local")
GRAFANA_LOKI_URL: str = os.environ.get("GRAFANA_LOKI_URL", "")
GRAFANA_LOKI_USER: str = os.environ.get("GRAFANA_LOKI_USER", "")
GRAFANA_API_KEY: str = os.environ.get("GRAFANA_API_KEY", "")
# Same Grafana Cloud tenant/credentials as the rest of scrape-analyzer
# (backend/src/chatbot-plugin) — OTel traces just land under this service's
# own service.name, no new secrets needed.
GRAFANA_OTLP_ENDPOINT: str = os.environ.get("GRAFANA_OTLP_ENDPOINT", "")
GRAFANA_OTLP_USER: str = os.environ.get("GRAFANA_OTLP_USER", "")
