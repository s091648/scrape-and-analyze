import logging
import os
from logging_loki import LokiHandler


def configure_loki():

    url = os.environ.get("LOKI_URL")
    username = os.environ.get("LOKI_USER")
    password = os.environ.get("LOKI_API_KEY")

    if not url:
        return

    handler = LokiHandler(
        url=url,
        auth=(username, password),
        tags={"app": "scraper"},
        version="1",
    )

    logging.getLogger().addHandler(handler)