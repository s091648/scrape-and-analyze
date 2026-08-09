import requests

from src.modules.collection.application.events import PipelineCompletedEvent
from src.shared.logging import get_logger

logger = get_logger(__name__)

_REQUEST_TIMEOUT_SECONDS = 15


class CacheWarmupHandler:
    """Re-populates the default (no-customization) reads right after CacheInvalidationHandler
    bumps their namespace versions, so the first visitor after a scrape run doesn't pay a
    cache-miss cost — only user-customized filter combinations remain lazily populated via
    cache-aside (research.md decision, 020-redis-caching-layer).

    Must run strictly after CacheInvalidationHandler.bump_version() for the same event, or the
    warmed entries would land under a namespace version that's about to be orphaned — bootstrap.py
    subscribes this handler second to guarantee that ordering (InMemoryEventBus dispatches
    subscribers in subscribe()-call order).

    Warms via real HTTP calls to backend's own endpoints (not by duplicating its query-building
    logic here) — src/ and backend/ are separate services, and this way the warmed cache entry
    is always produced by the exact same code path a real browser request would hit.
    """

    def __init__(self, backend_url: str) -> None:
        self._backend_url = backend_url.rstrip("/")

    def handle(self, event: PipelineCompletedEvent) -> None:
        try:
            headers = {"Authorization": f"Bearer {self._get_guest_token()}"}
            topic_ids = self._get_active_topic_ids(headers)
        except Exception as e:
            logger.warning("cache_warmup_setup_failed", error=str(e))
            return

        self._warm_default_reads(headers, params=None)
        for topic_id in topic_ids:
            self._warm_default_reads(headers, params={"topic_id": topic_id})

    def _warm_default_reads(self, headers: dict, params: dict | None) -> None:
        self._get("/articles", headers, params)
        self._get("/analyses/graph", headers, params)
        self._get("/tag-groups", headers, params)
        if params is not None:
            # /weekly-reports/latest requires topic_id — no topic-less variant exists.
            self._get("/weekly-reports/latest", headers, params)

    def _get_guest_token(self) -> str:
        resp = requests.post(f"{self._backend_url}/auth/guest", timeout=_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _get_active_topic_ids(self, headers: dict) -> list[str]:
        resp = requests.get(f"{self._backend_url}/topics", headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return [t["id"] for t in resp.json()]

    def _get(self, path: str, headers: dict, params: dict | None) -> None:
        try:
            resp = requests.get(
                f"{self._backend_url}{path}", headers=headers, params=params, timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("cache_warmup_request_failed", path=path, params=params, error=str(e))
