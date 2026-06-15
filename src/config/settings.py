"""
Pure application settings — reads environment variables only.
No database imports, no side effects.
"""
import os

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")
APP_ENV: str = os.environ.get("APP_ENV", "local")
TRANSLATION_LANGUAGES: list[str] = [
    lang.strip()
    for lang in os.environ.get("TRANSLATION_LANGUAGES", "zh-TW").split(",")
    if lang.strip()
]

# Vector DB connection
VECTOR_DB_NAME: str = os.environ.get("VECTOR_DB_NAME", "")
VECTOR_DB_USER: str = os.environ.get("VECTOR_DB_USER", "")
VECTOR_DB_PASSWORD: str = os.environ.get("VECTOR_DB_PASSWORD", "")
VECTOR_DB_HOST: str = os.environ.get("VECTOR_DB_HOST", "localhost")
VECTOR_DB_PORT: int = int(os.environ.get("VECTOR_DB_PORT", "5432"))
VECTOR_DB_SCHEMA: str = os.environ.get("VECTOR_DB_SCHEMA", "vectors")
VECTOR_DB_ARTICLES_TABLE: str = os.environ.get("VECTOR_DB_ARTICLES_TABLE", "articles")
VECTOR_DB_CHUNKS_TABLE: str = os.environ.get("VECTOR_DB_CHUNKS_TABLE", "article_chunks")


def missing_rag_config() -> list[str]:
    """Returns names of missing required RAG env vars.

    Only checks DB connection credentials. Embedding provider config is in
    src/infrastructure/intelligence/vector_store/rag_config.toml.
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
    """Raise ValueError if required env vars are missing."""
    errors = []
    if not os.environ.get("DATABASE_URL"):
        errors.append("DATABASE_URL is required")
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
