import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import redis

from shared.search_index.search_term import SearchTerm

logger = logging.getLogger(__name__)

_REBUILT_AT_KEY = "search:idx:rebuilt_at"
_PIPELINE_BATCH_SIZE = 1000
_DEFAULT_MAX_PREFIX_LEN = 8

# 023-article-search follow-up: none of search:idx:* keys had a TTL before this — under
# healthy operation that's mostly fine (rebuild()'s FLUSHDB+SWAPDB cycle already retires a
# given cycle's repopulate()-only writes within ~2 rebuild cycles, since they get demoted
# into the staging slot on one SWAPDB and wiped by the next cycle's flushdb()) — but if
# the rebuild job (the daily scrape pipeline's PipelineCompletedEvent →
# SearchIndexRebuildHandler) stops running entirely, keys stop being retired and
# repopulate()'s ad-hoc cache-aside writes can accumulate indefinitely, unrecoverable by
# `redis-server --maxmemory-policy volatile-lru` since that only evicts TTL'd keys. A TTL
# well beyond the ~daily rebuild cadence (7 days — roughly a week of missed rebuilds
# before anything expires) means normal operation never actually hits it (every
# successful rebuild/repopulate touch resets the clock via EXPIRE), while a prolonged
# outage still self-heals: expired keys make suggest()'s `exists()` check correctly fall
# through to the Postgres fallback (intelligence.search_terms), which repopulates with a
# fresh TTL — textbook cache-aside, not just a memory bound.
_KEY_TTL_SECONDS = 7 * 24 * 60 * 60


def _expand_term(term: str, max_len: int) -> set[str]:
    """Every prefix of every suffix of `term`, capped at `max_len` characters —
    the flattened "suffix trie" construction (research.md's contains-anywhere decision).
    A set, not a list: overlapping substrings (e.g. repeated letters) can otherwise
    produce the same (suffix-)prefix more than once."""
    term = term.lower()
    keys: set[str] = set()
    for start in range(len(term)):
        suffix = term[start:]
        max_plen = min(len(suffix), max_len)
        for plen in range(1, max_plen + 1):
            keys.add(suffix[:plen])
    return keys


def _swap_db_in_url(redis_url: str, db_index: int) -> str:
    """redis://host:port/N -> redis://host:port/{db_index}, preserving everything else."""
    return re.sub(r"/\d+(\?.*)?$", f"/{db_index}\\1", redis_url) if re.search(r"/\d+", redis_url) else f"{redis_url}/{db_index}"


class RedisSearchIndexGateway:
    """Redis-backed SearchIndexGateway — flattened `search:idx:{topic}:{prefix} -> ZSET`
    per data-model.md. `rebuild()` builds into a staging DB index (main db + 1 on the
    same Redis instance) and atomically SWAPDBs it live, so readers never see a
    half-rebuilt index (and skips the swap entirely if the new build has zero terms,
    rather than swapping an empty index over a good one). `suggest()` gates on the
    per-prefix key itself (not a global "index ever built" marker), so `repopulate()`
    writes from individual Postgres-fallback hits are actually read back on the next
    lookup instead of being masked by a coarser gate."""

    def __init__(self, redis_url: str, max_prefix_len: int = _DEFAULT_MAX_PREFIX_LEN,
                 socket_timeout: float = 2.0, socket_connect_timeout: float = 2.0) -> None:
        self._redis_url = redis_url
        self._max_prefix_len = max_prefix_len
        self._client = redis.Redis.from_url(
            redis_url, socket_timeout=socket_timeout, socket_connect_timeout=socket_connect_timeout,
        )
        self._db_index = self._client.connection_pool.connection_kwargs.get("db", 0)
        self._staging_db_index = self._db_index + 1

    def _staging_client(self) -> redis.Redis:
        return redis.Redis.from_url(_swap_db_in_url(self._redis_url, self._staging_db_index))

    @staticmethod
    def _key(topic_id: Optional[UUID], prefix: str) -> str:
        topic_part = str(topic_id) if topic_id is not None else "none"
        return f"search:idx:{topic_part}:{prefix}"

    def rebuild(self, topic_terms: dict[Optional[UUID], dict[str, int]]) -> None:
        term_count = sum(len(terms) for terms in topic_terms.values())
        if term_count == 0:
            # Never SWAPDB an empty build in — that would blow away a good live index
            # with nothing, which is exactly what happened when a rebuild ran against
            # a transiently-empty term set (see incident notes in search_service.py).
            logger.warning("search_index_rebuild_skipped_empty")
            return

        try:
            staging = self._staging_client()
            staging.flushdb()
            pipe = staging.pipeline(transaction=False)
            pending = 0
            for topic_id, terms in topic_terms.items():
                for term, count in terms.items():
                    for prefix in _expand_term(term, self._max_prefix_len):
                        key = self._key(topic_id, prefix)
                        pipe.zadd(key, {term: count})
                        pipe.expire(key, _KEY_TTL_SECONDS)
                        pending += 2
                        if pending >= _PIPELINE_BATCH_SIZE:
                            pipe.execute()
                            pipe = staging.pipeline(transaction=False)
                            pending = 0
            pipe.set(_REBUILT_AT_KEY, datetime.now(timezone.utc).isoformat())
            pipe.execute()

            self._client.execute_command("SWAPDB", self._db_index, self._staging_db_index)
            logger.info("search_index_rebuild_swapped", extra={"term_count": term_count})
        except redis.exceptions.RedisError as e:
            logger.warning("search_index_rebuild_failed", extra={"error": str(e)})

    def suggest(self, topic_id: Optional[UUID], prefix: str, limit: int = 10) -> Optional[list[SearchTerm]]:
        try:
            lookup = prefix.lower()[: self._max_prefix_len]
            key = self._key(topic_id, lookup)
            if not self._client.exists(key):
                return None  # this prefix isn't cached — caller falls back to Postgres and repopulates it

            raw = self._client.zrevrange(key, 0, limit - 1, withscores=True)
            terms = [SearchTerm(term=t.decode() if isinstance(t, bytes) else t, occurrence_count=int(score)) for t, score in raw]
            if len(prefix) > self._max_prefix_len:
                terms = [t for t in terms if prefix.lower() in t.term]
            return terms
        except redis.exceptions.RedisError as e:
            logger.warning("search_index_suggest_failed", extra={"error": str(e)})
            return None

    def repopulate(self, topic_id: Optional[UUID], prefix: str, terms: list[SearchTerm]) -> None:
        """Cache-aside write-back after a Postgres fallback hit — never raises. TTL'd
        (see _KEY_TTL_SECONDS) same as rebuild()'s keys — these ad-hoc, one-off writes
        don't participate in the FLUSHDB+SWAPDB replace cycle, so without their own
        expiry they'd be the one thing that could accumulate indefinitely if rebuild()
        stopped running for an extended period."""
        if not terms:
            return
        try:
            key = self._key(topic_id, prefix.lower()[: self._max_prefix_len])
            self._client.zadd(key, {t.term: t.occurrence_count for t in terms})
            self._client.expire(key, _KEY_TTL_SECONDS)
        except redis.exceptions.RedisError as e:
            logger.warning("search_index_repopulate_failed", extra={"error": str(e)})
