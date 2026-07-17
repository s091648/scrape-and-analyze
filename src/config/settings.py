"""
Pure application settings — reads environment variables only.
No database imports, no side effects.
"""
import os
from typing import Optional


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
SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
APP_ENV: str = os.environ.get("APP_ENV", "local")
TRANSLATION_LANGUAGES: list[str] = [
    lang.strip()
    for lang in os.environ.get("TRANSLATION_LANGUAGES", "zh-TW").split(",")
    if lang.strip()
]

# Scraper runtime flag — disables the 0–3 min startup jitter when set.
RUN_IMMEDIATELY: bool = _bool("RUN_IMMEDIATELY")

# Email (Resend) — used by the weekly report email notifier
RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL: str = os.environ.get("RESEND_FROM_EMAIL", "")

# Telegram (shared between scraper pipeline and weekly report)
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Web
FRONTEND_ORIGIN: str = os.environ.get("FRONTEND_ORIGIN", "https://example.com")

# HTTP — optional proxy + bot UA contact email
FIXIE_URL: Optional[str] = os.environ.get("FIXIE_URL") or None
CONTACT_EMAIL: str = os.environ.get("CONTACT_EMAIL", "contact@example.com")

# R2 blob storage (S3-compatible)
R2_ACCOUNT_ID: str = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID: str = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME: str = os.environ.get("R2_BUCKET_NAME", "")
R2_PUBLIC_URL: str = os.environ.get("R2_PUBLIC_URL", "")

# Observability — Grafana (Loki + OTel)
GRAFANA_LOKI_URL: Optional[str] = os.environ.get("GRAFANA_LOKI_URL") or None
GRAFANA_LOKI_USER: Optional[str] = os.environ.get("GRAFANA_LOKI_USER") or None
GRAFANA_API_KEY: Optional[str] = os.environ.get("GRAFANA_API_KEY") or None
GRAFANA_OTLP_USER: str = os.environ.get("GRAFANA_OTLP_USER", "").strip()
GRAFANA_OTLP_ENDPOINT: str = os.environ.get("GRAFANA_OTLP_ENDPOINT", "").strip()

# Collection API clients
# OpenAlex's polite-pool "mailto" identifier reuses CONTACT_EMAIL (same bot-identity
# contact used in scraper User-Agent/From headers) — no separate env var.
SEMANTIC_SCHOLAR_API_KEY: Optional[str] = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None

# Vector DB connection
VECTOR_DB_NAME: str = os.environ.get("VECTOR_DB_NAME", "")
VECTOR_DB_USER: str = os.environ.get("VECTOR_DB_USER", "")
VECTOR_DB_PASSWORD: str = os.environ.get("VECTOR_DB_PASSWORD", "")
VECTOR_DB_HOST: str = os.environ.get("VECTOR_DB_HOST", "localhost")
VECTOR_DB_PORT: int = int(os.environ.get("VECTOR_DB_PORT", "5432"))
VECTOR_DB_SCHEMA: str = os.environ.get("VECTOR_DB_SCHEMA", "vectors")
VECTOR_DB_ARTICLES_TABLE: str = os.environ.get("VECTOR_DB_ARTICLES_TABLE", "articles")
VECTOR_DB_CHUNKS_TABLE: str = os.environ.get("VECTOR_DB_CHUNKS_TABLE", "article_chunks")


# RAG embedding provider — dense
RAG_DENSE_PROVIDER: str = os.environ.get("RAG_DENSE_PROVIDER", "")
RAG_DENSE_MODEL: str = os.environ.get("RAG_DENSE_MODEL", "")
RAG_DENSE_DIMENSION: int = int(os.environ.get("RAG_DENSE_DIMENSION", "768"))
RAG_DENSE_API_KEY_ENV: str = os.environ.get("RAG_DENSE_API_KEY_ENV", "")
RAG_DENSE_ENDPOINT_URL: str = os.environ.get("RAG_DENSE_ENDPOINT_URL", "")
RAG_DENSE_RPM: int | None = _int_or_none("RAG_DENSE_RPM")
RAG_DENSE_TPM: int | None = _int_or_none("RAG_DENSE_TPM")
RAG_DENSE_RPD: int | None = _int_or_none("RAG_DENSE_RPD")

# RAG embedding provider — sparse
RAG_SPARSE_PROVIDER: str = os.environ.get("RAG_SPARSE_PROVIDER", "")
RAG_SPARSE_MODEL: str = os.environ.get("RAG_SPARSE_MODEL", "")
RAG_SPARSE_DIMENSION: int = int(os.environ.get("RAG_SPARSE_DIMENSION", "30522"))
RAG_SPARSE_ENDPOINT_URL: str = os.environ.get("RAG_SPARSE_ENDPOINT_URL", "")
RAG_SPARSE_RPM: int | None = _int_or_none("RAG_SPARSE_RPM")
RAG_SPARSE_TPM: int | None = _int_or_none("RAG_SPARSE_TPM")
RAG_SPARSE_RPD: int | None = _int_or_none("RAG_SPARSE_RPD")
RAG_SPARSE_TIMEOUT: float = float(os.environ.get("RAG_SPARSE_TIMEOUT", "120"))

# Number of chunks packed into a single embed() call.
# Larger values reduce total API requests. Google gemini-embedding-001 supports up to
# 100 inputs per call; 96 keeps most articles (≤80 chunks) in 1 request while staying
# safely under the limit. Reduce if you see payload errors from the API.
RAG_EMBED_BATCH_SIZE: int = int(os.environ.get("RAG_EMBED_BATCH_SIZE", "96"))

# Chunking parameters — only affect ingest, not retrieve.
# chunk_size: characters per chunk. step = chunk_size - chunk_overlap.
# A 36,000-char article with defaults (500/50) → ~80 chunks.
# Setting chunk_size=1500, overlap=150 → ~27 chunks per same article.
RAG_CHUNK_SIZE: int = int(os.environ.get("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP: int = int(os.environ.get("RAG_CHUNK_OVERLAP", "50"))


def missing_rag_config() -> list[str]:
    """Returns names of missing required RAG env vars.

    Only checks DB connection credentials. Embedding provider config comes from
    RAG_DENSE_* / RAG_SPARSE_* env vars (set at deploy time).
    RAG ingestion is enabled whenever VECTOR_DB_NAME/USER/PASSWORD are all set.
    """
    missing = []
    if not VECTOR_DB_NAME:
        missing.append("VECTOR_DB_NAME")
    if not VECTOR_DB_USER:
        missing.append("VECTOR_DB_USER")
    if not VECTOR_DB_PASSWORD:
        missing.append("VECTOR_DB_PASSWORD")
    return missing


def log_config_warnings(logger) -> None:
    """Log warnings for optional but recommended config vars."""
    if not SENTRY_DSN:
        logger.warning("sentry_dsn_not_set")
    missing = missing_rag_config()
    if missing:
        logger.warning("rag_config_incomplete_rag_disabled", missing_vars=missing)


def validate_config() -> None:
    """Raise ValueError if required env vars are missing.

    Reads os.environ directly (not the frozen DATABASE_URL constant above) so
    it reflects the environment at call time, not at module-import time.
    """
    errors = []
    if not os.environ.get("DATABASE_URL"):
        errors.append("DATABASE_URL is required")
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
