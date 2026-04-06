"""
Pure application settings — reads environment variables only.
No database imports, no side effects.
"""
import os

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")


def validate_config() -> None:
    """Raise ValueError if required env vars are missing."""
    errors = []
    if not os.environ.get("DATABASE_URL", DATABASE_URL):
        errors.append("DATABASE_URL is required")
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
