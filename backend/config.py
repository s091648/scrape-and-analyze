"""
Pure application settings — reads environment variables only.
No database imports, no side effects.
"""
import os


def _int_or_none(name: str) -> int | None:
    v = os.environ.get(name, "").strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _bool(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

FRONTEND_ORIGIN: str = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
VIEW_COUNT_FLUSH_INTERVAL: int = int(os.environ.get("VIEW_COUNT_FLUSH_INTERVAL", "900"))

SWAGGER_TRY_IT_OUT_ENABLED: bool = os.environ.get("SWAGGER_TRY_IT_OUT_ENABLED", "false").lower() == "true"

NEXTAUTH_SECRET: str = os.environ.get("NEXTAUTH_SECRET", "")

APP_ENV: str = os.environ.get("APP_ENV", "local")

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# Separate logical DB from REDIS_URL (db 0): REDIS_URL holds durable operational state
# (view-count write-behind buffer, chat rate-limit counters) that must survive a FLUSHDB
# run while debugging the cache. CACHE_REDIS_URL (db 1) holds only disposable, rebuildable
# cache-aside entries (shared/cache/) — safe to FLUSHDB anytime.
CACHE_REDIS_URL: str = os.environ.get("CACHE_REDIS_URL", "redis://redis:6379/1")

CHAT_SERVICE_URL: str = os.environ.get("CHAT_SERVICE_URL", "").rstrip("/")
CHAT_SERVICE_API_KEY: str = os.environ.get("CHAT_SERVICE_API_KEY", "")

# 023-article-search follow-up: GET /search's dense/sparse query embedding, via
# chatbot_plugin_sdk's provider classes (backend/services/search_service.py). Mirrors
# src/config/settings.py's RAG_DENSE_*/RAG_SPARSE_* block exactly (same var names, same
# defaults) — query embeddings MUST use the identical provider/model/dimension as
# ingestion (src/), or the query vector lands in a different space than the stored
# article vectors and cosine distance becomes meaningless. Deliberately excludes
# VECTOR_DB_*/RAG_EMBED_BATCH_SIZE/RAG_CHUNK_*: backend queries vectors.article_chunks
# via its own existing SQLAlchemy Session (DATABASE_URL above), not the SDK's own
# SyncPgBackend/AsyncPgBackend, and batch/chunking params only affect ingest, never
# retrieve, so backend (which never ingests) has no use for them. Retires the older,
# narrower SEARCH_EMBEDDING_ENDPOINT_URL var this section replaces.
RAG_DENSE_PROVIDER: str = os.environ.get("RAG_DENSE_PROVIDER", "")
RAG_DENSE_MODEL: str = os.environ.get("RAG_DENSE_MODEL", "")
RAG_DENSE_DIMENSION: int = int(os.environ.get("RAG_DENSE_DIMENSION", "768"))
RAG_DENSE_API_KEY_ENV: str = os.environ.get("RAG_DENSE_API_KEY_ENV", "")
RAG_DENSE_ENDPOINT_URL: str = os.environ.get("RAG_DENSE_ENDPOINT_URL", "")
RAG_DENSE_RPM: int | None = _int_or_none("RAG_DENSE_RPM")
RAG_DENSE_TPM: int | None = _int_or_none("RAG_DENSE_TPM")
RAG_DENSE_RPD: int | None = _int_or_none("RAG_DENSE_RPD")
RAG_DENSE_SPLIT_BATCH_ON_TPM: bool = _bool("RAG_DENSE_SPLIT_BATCH_ON_TPM")

RAG_SPARSE_PROVIDER: str = os.environ.get("RAG_SPARSE_PROVIDER", "")
RAG_SPARSE_MODEL: str = os.environ.get("RAG_SPARSE_MODEL", "")
RAG_SPARSE_DIMENSION: int = int(os.environ.get("RAG_SPARSE_DIMENSION", "30522"))
RAG_SPARSE_ENDPOINT_URL: str = os.environ.get("RAG_SPARSE_ENDPOINT_URL", "")
RAG_SPARSE_RPM: int | None = _int_or_none("RAG_SPARSE_RPM")
RAG_SPARSE_TPM: int | None = _int_or_none("RAG_SPARSE_TPM")
RAG_SPARSE_RPD: int | None = _int_or_none("RAG_SPARSE_RPD")
RAG_SPARSE_TIMEOUT: float = float(os.environ.get("RAG_SPARSE_TIMEOUT", "120"))

# Dedicated Redis DB for the autocomplete prefix index — separate from REDIS_URL (db 0)
# and CACHE_REDIS_URL (db 1) so a full rebuild can safely FLUSHDB/SWAPDB without touching
# either. See specs/023-article-search/research.md "Decision: Redis DB allocation".
SEARCH_INDEX_REDIS_URL: str = os.environ.get("SEARCH_INDEX_REDIS_URL", "redis://redis:6379/2")

# Longest (suffix-)prefix indexed per term — must match the value the rebuild job (src/)
# used to build the index with. Autocomplete queries longer than this are truncated to
# this length for the Redis lookup, then post-filtered against the full typed text.
SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN: int = int(os.environ.get("SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN", "8"))

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")

# Grafana proxy (routers/grafana.py)
GRAFANA_PROMETHEUS_URL: str = os.environ.get("GRAFANA_PROMETHEUS_URL", "").rstrip("/")
GRAFANA_PROMETHEUS_USER: str = os.environ.get("GRAFANA_PROMETHEUS_USER", "")
GRAFANA_API_KEY: str = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_LOKI_URL: str = os.environ.get("GRAFANA_LOKI_URL", "").rstrip("/")
GRAFANA_LOKI_USER: str = os.environ.get("GRAFANA_LOKI_USER", "")
GRAFANA_TEMPO_URL: str = os.environ.get("GRAFANA_TEMPO_URL", "").rstrip("/")
GRAFANA_TEMPO_USER: str = os.environ.get("GRAFANA_TEMPO_USER", "")

# Backend's own log/trace shipping (observability.py)
GRAFANA_OTLP_ENDPOINT: str = os.environ.get("GRAFANA_OTLP_ENDPOINT", "").rstrip("/")
GRAFANA_OTLP_USER: str = os.environ.get("GRAFANA_OTLP_USER", "")
