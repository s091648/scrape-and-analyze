"""
Loki log handler — optional sink that ships structlog JSON to Grafana Loki.
Called once by configure_logging() at process startup.
"""
import logging
import os
import sys


def configure_loki() -> None:
    """Set up stdout handler and optional Loki handler for the root logger."""
    url = os.environ.get("GRAFANA_LOKI_URL")
    user = os.environ.get("GRAFANA_LOKI_USER")
    key = os.environ.get("GRAFANA_API_KEY")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Always attach stdout so structlog messages appear in container logs
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    root_logger.addHandler(stdout_handler)

    if not all([url, user, key]):
        return

    try:
        from logging_loki import LokiHandler
        from shared.enums.observability import LokiLabel, LokiAppValue
        app_env = os.environ.get("APP_ENV", "local").strip()
        loki_handler = LokiHandler(
            url=f"{url.rstrip('/')}/push",
            auth=(user, key),
            tags={LokiLabel.APP: LokiAppValue.SCRAPER, LokiLabel.ENV: app_env},
            version="1",
        )
        loki_handler.setLevel(logging.INFO)
        root_logger.addHandler(loki_handler)
    except Exception as e:
        print(f"Loki handler setup failed: {e}", file=sys.stdout)
