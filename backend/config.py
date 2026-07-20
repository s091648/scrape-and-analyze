"""
Pure application settings — reads environment variables only.
No database imports, no side effects.
"""
import os

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

FRONTEND_ORIGIN: str = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
VIEW_COUNT_FLUSH_INTERVAL: int = int(os.environ.get("VIEW_COUNT_FLUSH_INTERVAL", "900"))

NEXTAUTH_SECRET: str = os.environ.get("NEXTAUTH_SECRET", "")

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")

CHAT_SERVICE_URL: str = os.environ.get("CHAT_SERVICE_URL", "").rstrip("/")
CHAT_SERVICE_API_KEY: str = os.environ.get("CHAT_SERVICE_API_KEY", "")

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# Grafana proxy (routers/grafana.py)
GRAFANA_PROMETHEUS_URL: str = os.environ.get("GRAFANA_PROMETHEUS_URL", "").rstrip("/")
GRAFANA_PROMETHEUS_USER: str = os.environ.get("GRAFANA_PROMETHEUS_USER", "")
GRAFANA_API_KEY: str = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_LOKI_URL: str = os.environ.get("GRAFANA_LOKI_URL", "").rstrip("/")
GRAFANA_LOKI_USER: str = os.environ.get("GRAFANA_LOKI_USER", "")
GRAFANA_TEMPO_URL: str = os.environ.get("GRAFANA_TEMPO_URL", "").rstrip("/")
GRAFANA_TEMPO_USER: str = os.environ.get("GRAFANA_TEMPO_USER", "")
