import hashlib
import json
import logging
from typing import Any, Callable

import redis
import structlog

from .gateway import CacheResult

logger = logging.getLogger(__name__)
# Separate from `logger` above (plain stdlib, used for warnings only): this one is a structlog
# bound logger so "cache_lookup" gets JSON-rendered with an "event" field, matching the
# `| json | event = "..."` LogQL pattern the monitoring dashboard's other panels already rely on
# (backend/observability.py's configure_logging()) — a plain stdlib call wouldn't be structured.
event_logger = structlog.get_logger(__name__)

_VERSION_KEY_PREFIX = "cache:v:"


def _param_hash(params: dict) -> str:
    """Stable hash of params — canonical (sorted-keys) JSON, so callers can pass a
    plain dict and hashing logic stays centralized (contracts/cache-gateway.md)."""
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


class RedisCacheGateway:
    """Sync redis.Redis-backed CacheGateway implementation.

    Uses a synchronous client (not redis.asyncio) because every call site in scope
    is a synchronous FastAPI route/service function or a synchronous CLI script —
    see research.md "Decision: Redis client — synchronous".
    """

    def __init__(
        self,
        redis_url: str,
        socket_timeout: float = 1.0,
        socket_connect_timeout: float = 1.0,
    ) -> None:
        self._client = redis.Redis.from_url(
            redis_url,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
        )

    def _current_version(self, namespace: str) -> int:
        try:
            raw = self._client.get(_VERSION_KEY_PREFIX + namespace)
            return int(raw) if raw is not None else 1
        except redis.exceptions.RedisError as e:
            logger.warning("cache_version_read_failed", extra={"namespace": namespace, "error": str(e)})
            return 1
        except (TypeError, ValueError) as e:
            logger.warning("cache_version_malformed", extra={"namespace": namespace, "error": str(e)})
            return 1

    def _build_key(self, namespace: str, version: int, lang: str, params: dict) -> str:
        return f"{namespace}:v{version}:{lang}:{_param_hash(params)}"

    def get_or_set(
        self,
        namespace: str,
        params: dict,
        ttl_seconds: int,
        loader: Callable[[], Any],
        lang: str = "en",
    ) -> CacheResult:
        result = self._get_or_set(namespace, params, ttl_seconds, loader, lang)
        # Single structured event per lookup, covering every namespace this gateway serves
        # (articles/graph/tag_groups/weekly_reports) — see contracts/cache-gateway.md and
        # monitoring-content.tsx's Operations tab for the "admin.cacheHitRate" panel that reads it.
        event_logger.info("cache_lookup", namespace=namespace, status=result.status, lang=lang)
        return result

    def _get_or_set(
        self,
        namespace: str,
        params: dict,
        ttl_seconds: int,
        loader: Callable[[], Any],
        lang: str,
    ) -> CacheResult:
        try:
            version = self._current_version(namespace)
            key = self._build_key(namespace, version, lang, params)
            cached = self._client.get(key)
        except redis.exceptions.RedisError as e:
            logger.warning("cache_read_failed", extra={"namespace": namespace, "error": str(e)})
            return CacheResult(value=loader(), status="BYPASS")

        if cached is not None:
            try:
                return CacheResult(value=json.loads(cached), status="HIT")
            except ValueError as e:
                # Poisoned entry (truncated, or written by an incompatible producer):
                # fall through to loader(), which overwrites it below.
                logger.warning("cache_decode_failed", extra={"namespace": namespace, "error": str(e)})

        value = loader()

        try:
            self._client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
        except (redis.exceptions.RedisError, ValueError, TypeError, RecursionError) as e:
            logger.warning("cache_write_failed", extra={"namespace": namespace, "error": str(e)})

        return CacheResult(value=value, status="MISS")

    def bump_version(self, namespace: str) -> int:
        key = _VERSION_KEY_PREFIX + namespace
        try:
            # _current_version() reads a missing key as version 1 (the "no cache yet"
            # default). If a namespace has never been bumped before, a bare INCR on
            # that still-missing key would *also* land on 1 — making the first-ever
            # bump a no-op, since pre- and post-bump reads would resolve to the same
            # version and orphan nothing. SETNX seeds the key at 1 first so the
            # following INCR always produces >= 2 on a namespace's first bump.
            self._client.setnx(key, 1)
            return int(self._client.incr(key))
        except redis.exceptions.RedisError as e:
            logger.warning("cache_bump_version_failed", extra={"namespace": namespace, "error": str(e)})
            return 0
