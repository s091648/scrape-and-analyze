import logging
import os
import sys
from logging_loki import LokiHandler


def configure_loki():
    url = os.environ.get("GRAFANA_LOKI_URL")
    user = os.environ.get("GRAFANA_LOKI_USER")
    key = os.environ.get("GRAFANA_API_KEY")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Always add a stdout handler so structlog messages appear in container logs
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    root_logger.addHandler(stdout_handler)

    if not all([url, user, key]):
        return

    try:
        loki_handler = LokiHandler(
            url=url,
            auth=(user, key),
            tags={"app": "scraper", "env": "production"},
            version="1",
        )
        # Only send INFO+ to avoid OTLP retry warnings causing a feedback loop
        loki_handler.setLevel(logging.INFO)
        root_logger.addHandler(loki_handler)
    except Exception as e:
        print(f"Loki handler setup failed: {e}", file=sys.stdout)