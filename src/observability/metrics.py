import os
import requests
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

registry = CollectorRegistry()

SCRAPER_RUNS = Counter(
    "scraper_runs_total",
    "Total scraper runs",
    registry=registry,
)

SCRAPER_DURATION = Histogram(
    "scraper_run_duration_seconds",
    "Duration of scraper run",
    registry=registry,
)

SCRAPER_ARTICLES_FOUND = Counter(
    "scraper_articles_found_total",
    "Articles discovered",
    ["source"],
    registry=registry,
)

SCRAPER_ARTICLES_NEW = Counter(
    "scraper_articles_new_total",
    "New articles stored",
    ["source"],
    registry=registry,
)

SCRAPER_ARTICLES_DUPLICATE = Counter(
    "scraper_articles_duplicate_total",
    "Duplicate articles skipped",
    ["source"],
    registry=registry,
)

SCRAPER_ERRORS = Counter(
    "scraper_errors_total",
    "Errors during scraping",
    ["type"],
    registry=registry,
)


def push_metrics(job="scraper"):
    # Grafana Cloud exposes remote write instead of push gateway, so this is only used if PROMETHEUS_PUSHGATEWAY env var is set
    # gateway = os.environ.get("PROMETHEUS_PUSHGATEWAY")

    # if not gateway:
    #     return

    # push_to_gateway(
    #     gateway,
    #     job=job,
    #     registry=registry,
    # )
    endpoint = os.environ.get("PROMETHEUS_PUSH_ENDPOINT")
    user = os.environ.get("PROMETHEUS_USER")
    password = os.environ.get("PROMETHEUS_API_KEY")

    if not endpoint:
        return

    data = generate_latest(registry)

    requests.post(
        endpoint,
        data=data,
        auth=(user, password),
        headers={"Content-Type": "text/plain"},
        timeout=5,
    )