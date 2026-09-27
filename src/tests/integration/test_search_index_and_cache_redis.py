"""Integration tests for the Redis-backed read models the scrape pipeline rebuilds at
Barrier 1 (TextPipelineCompletedEvent): shared/search_index's RedisSearchIndexGateway
(autocomplete trie, FLUSHDB + SWAPDB rebuild), shared/cache's RedisCacheGateway
(versioned cache-aside), and RebuildSearchIndexUseCase end to end against the real
test-schema Postgres + a real Redis.

Needs a reachable Redis — CI's src-integration-test job runs a redis service container;
locally, `make test-src-integration` runs inside test_service, which depends on the
compose `redis` service.

Isolation: every test here uses dedicated logical DBs (10–12) on the configured Redis
host, never the app's own SEARCH_INDEX_REDIS_URL/CACHE_REDIS_URL DBs — rebuild() SWAPDBs
its DB with the next one, which against the real DB 2/3 would wipe a local dev search
index. Each DB is flushed before and after its test."""
import uuid

import pytest
import redis

from shared.cache import RedisCacheGateway
from shared.search_index import RedisSearchIndexGateway, SearchTerm
from shared.search_index.redis_gateway import _swap_db_in_url
from src.config.settings import CACHE_REDIS_URL, SEARCH_INDEX_REDIS_URL

pytestmark = pytest.mark.integration

_INDEX_DB = 10          # rebuild() also uses _INDEX_DB + 1 as its staging DB
_CACHE_DB = 12
# Nothing listens here — used to exercise every gateway's "Redis unavailable" fallback.
_UNREACHABLE_URL = "redis://127.0.0.1:1/0"


def _flush(url: str) -> None:
    redis.Redis.from_url(url).flushdb()


@pytest.fixture
def index_url():
    url = _swap_db_in_url(SEARCH_INDEX_REDIS_URL, _INDEX_DB)
    staging = _swap_db_in_url(SEARCH_INDEX_REDIS_URL, _INDEX_DB + 1)
    _flush(url)
    _flush(staging)
    yield url
    _flush(url)
    _flush(staging)


@pytest.fixture
def cache_url():
    url = _swap_db_in_url(CACHE_REDIS_URL, _CACHE_DB)
    _flush(url)
    yield url
    _flush(url)


# ---------------------------------------------------------------------------
# RedisSearchIndexGateway
# ---------------------------------------------------------------------------

class TestRedisSearchIndexGateway:
    def test_suggest_returns_none_before_any_rebuild(self, index_url):
        gateway = RedisSearchIndexGateway(redis_url=index_url)

        # None (not []) is the "fall back to Postgres" signal.
        assert gateway.suggest(uuid.uuid4(), "qua") is None

    def test_rebuild_then_suggest_ranks_by_occurrence_and_matches_substrings(self, index_url):
        topic = uuid.uuid4()
        gateway = RedisSearchIndexGateway(redis_url=index_url)

        gateway.rebuild({topic: {"quantum": 5, "quartz": 2, "aquarium": 1}})

        by_prefix = gateway.suggest(topic, "qua")
        assert [t.term for t in by_prefix] == ["quantum", "quartz", "aquarium"]
        assert by_prefix[0].occurrence_count == 5
        # Suffix expansion: a match in the middle of a term is found too.
        assert [t.term for t in gateway.suggest(topic, "ntu")] == ["quantum"]
        # Other topics are a separate partition.
        assert gateway.suggest(uuid.uuid4(), "qua") is None

    def test_limit_caps_the_number_of_suggestions(self, index_url):
        topic = uuid.uuid4()
        gateway = RedisSearchIndexGateway(redis_url=index_url)
        gateway.rebuild({topic: {f"term{i}": i for i in range(1, 6)}})

        assert len(gateway.suggest(topic, "term", limit=2)) == 2

    def test_prefix_longer_than_max_len_is_post_filtered(self, index_url):
        topic = uuid.uuid4()
        gateway = RedisSearchIndexGateway(redis_url=index_url, max_prefix_len=4)
        gateway.rebuild({topic: {"transformer": 3, "transport": 2}})

        # Keys are capped at 4 chars ("tran"), so both terms share the key — the full
        # query must then narrow them down.
        assert [t.term for t in gateway.suggest(topic, "transf")] == ["transformer"]

    def test_rebuild_replaces_the_previous_index_atomically(self, index_url):
        topic = uuid.uuid4()
        gateway = RedisSearchIndexGateway(redis_url=index_url)
        gateway.rebuild({topic: {"alpha": 1}})

        gateway.rebuild({topic: {"beta": 1}})

        assert gateway.suggest(topic, "alp") is None
        assert [t.term for t in gateway.suggest(topic, "bet")] == ["beta"]

    def test_empty_rebuild_keeps_the_existing_index(self, index_url):
        topic = uuid.uuid4()
        gateway = RedisSearchIndexGateway(redis_url=index_url)
        gateway.rebuild({topic: {"alpha": 1}})

        gateway.rebuild({topic: {}})

        assert [t.term for t in gateway.suggest(topic, "alp")] == ["alpha"]

    def test_repopulate_writes_back_a_postgres_fallback_hit(self, index_url):
        topic = uuid.uuid4()
        gateway = RedisSearchIndexGateway(redis_url=index_url)

        gateway.repopulate(topic, "neu", [SearchTerm(term="neural", occurrence_count=4)])
        gateway.repopulate(topic, "xyz", [])  # nothing to cache — no-op

        assert [(t.term, t.occurrence_count) for t in gateway.suggest(topic, "neu")] == [("neural", 4)]
        assert gateway.suggest(topic, "xyz") is None
        ttl = redis.Redis.from_url(index_url).ttl(f"search:idx:{topic}:neu")
        assert ttl > 0, "repopulated keys must carry a TTL so they can't accumulate forever"

    def test_untopiced_key_partition(self, index_url):
        gateway = RedisSearchIndexGateway(redis_url=index_url)
        gateway.rebuild({None: {"global": 2}})

        assert [t.term for t in gateway.suggest(None, "glo")] == ["global"]

    def test_unreachable_redis_degrades_instead_of_raising(self):
        gateway = RedisSearchIndexGateway(redis_url=_UNREACHABLE_URL, socket_timeout=0.2,
                                          socket_connect_timeout=0.2)
        topic = uuid.uuid4()

        gateway.rebuild({topic: {"alpha": 1}})
        gateway.repopulate(topic, "alp", [SearchTerm(term="alpha", occurrence_count=1)])
        assert gateway.suggest(topic, "alp") is None


# ---------------------------------------------------------------------------
# RedisCacheGateway
# ---------------------------------------------------------------------------

class TestRedisCacheGateway:
    def test_miss_then_hit_calls_loader_once(self, cache_url):
        gateway = RedisCacheGateway(redis_url=cache_url)
        calls = []

        def loader():
            calls.append(1)
            return {"items": [1, 2, 3]}

        first = gateway.get_or_set("articles", {"page": 1}, 60, loader)
        second = gateway.get_or_set("articles", {"page": 1}, 60, loader)

        assert (first.status, second.status) == ("MISS", "HIT")
        assert second.value == {"items": [1, 2, 3]}
        assert len(calls) == 1

    def test_params_and_lang_are_part_of_the_key(self, cache_url):
        gateway = RedisCacheGateway(redis_url=cache_url)
        gateway.get_or_set("articles", {"page": 1}, 60, lambda: "en-page-1")

        assert gateway.get_or_set("articles", {"page": 2}, 60, lambda: "en-page-2").status == "MISS"
        zh = gateway.get_or_set("articles", {"page": 1}, 60, lambda: "zh-page-1", lang="zh-TW")
        assert (zh.status, zh.value) == ("MISS", "zh-page-1")

    def test_bump_version_orphans_existing_entries(self, cache_url):
        gateway = RedisCacheGateway(redis_url=cache_url)
        gateway.get_or_set("tags", {}, 60, lambda: "old")

        # First-ever bump must still move the version (SETNX seed), not no-op at 1.
        assert gateway.bump_version("tags") == 2
        result = gateway.get_or_set("tags", {}, 60, lambda: "new")

        assert (result.status, result.value) == ("MISS", "new")

    def test_poisoned_entry_is_reloaded_and_overwritten(self, cache_url):
        gateway = RedisCacheGateway(redis_url=cache_url)
        gateway.get_or_set("graph", {}, 60, lambda: {"ok": True})
        client = redis.Redis.from_url(cache_url)
        key = next(k for k in client.keys("graph:*"))
        client.set(key, b"{not json")

        result = gateway.get_or_set("graph", {}, 60, lambda: {"ok": "reloaded"})

        assert (result.status, result.value) == ("MISS", {"ok": "reloaded"})
        assert gateway.get_or_set("graph", {}, 60, lambda: None).value == {"ok": "reloaded"}

    def test_malformed_version_key_falls_back_to_version_one(self, cache_url):
        gateway = RedisCacheGateway(redis_url=cache_url)
        redis.Redis.from_url(cache_url).set("cache:v:weekly", b"not-a-number")

        assert gateway.get_or_set("weekly", {}, 60, lambda: "v").status == "MISS"
        assert gateway.get_or_set("weekly", {}, 60, lambda: "v").status == "HIT"

    def test_unserializable_value_is_returned_but_not_cached(self, cache_url):
        gateway = RedisCacheGateway(redis_url=cache_url)
        value = {"self": None}
        value["self"] = value  # circular — json.dumps raises

        result = gateway.get_or_set("loop", {}, 60, lambda: value)

        assert result.status == "MISS"
        assert result.value is value
        assert redis.Redis.from_url(cache_url).keys("loop:*") == []

    def test_publish_warmup_signal_reaches_subscribers(self, cache_url):
        from shared.cache.redis_gateway import WARMUP_CHANNEL

        pubsub = redis.Redis.from_url(cache_url).pubsub()
        pubsub.subscribe(WARMUP_CHANNEL)
        pubsub.get_message(timeout=1)  # subscribe confirmation

        RedisCacheGateway(redis_url=cache_url).publish_warmup_signal("pipeline_completed")

        message = pubsub.get_message(timeout=2)
        pubsub.close()
        assert message is not None and message["data"] == b"pipeline_completed"

    def test_unreachable_redis_bypasses_to_the_loader(self):
        gateway = RedisCacheGateway(redis_url=_UNREACHABLE_URL, socket_timeout=0.2,
                                    socket_connect_timeout=0.2)

        result = gateway.get_or_set("articles", {}, 60, lambda: "fresh")

        assert (result.status, result.value) == ("BYPASS", "fresh")
        assert gateway.bump_version("articles") == 0
        gateway.publish_warmup_signal("x")  # must not raise


# ---------------------------------------------------------------------------
# RebuildSearchIndexUseCase — real Postgres (test schema) + real Redis
# ---------------------------------------------------------------------------

@pytest.fixture
def indexed_topic(db_engine):
    """A fresh topic with three articles, committed (the use case's repository commits
    its own transactions, so the source rows must be committed too):
      - two analyzed articles sharing the term "quasicrystal" (doc freq 2), one of them
        with a zh-TW translation;
      - one article with no Analysis, which must be excluded from the index entirely.
    Removed again afterwards."""
    from sqlalchemy.orm import sessionmaker
    from models.analysis import Analysis
    from models.article import Article
    from models.article_translation import ArticleTranslation
    from models.article_search_token import ArticleSearchToken
    from models.topic import Topic
    from src.modules.collection.domain.value_objects import UrlHash

    session = sessionmaker(bind=db_engine)()
    topic = Topic(name=f"search-{uuid.uuid4().hex[:8]}", display_name="Search Topic")
    session.add(topic)
    session.flush()

    def _article(title, content, analyzed=True):
        url = f"https://example.com/{uuid.uuid4()}"
        a = Article(url=url, url_hash=UrlHash.generate_url_hash(url), source="test", title=title,
                    content=content, correlation_id=uuid.uuid4(), topic_id=topic.id)
        session.add(a)
        session.flush()
        if analyzed:
            session.add(Analysis(article_id=a.id, correlation_id=uuid.uuid4(), model_used="test-model"))
        return a

    first = _article("Quasicrystal lattices", "Aperiodic quasicrystal order")
    _article("Quasicrystal growth", "Photonic devices")
    unanalyzed = _article("Unanalyzed zeolite", "zeolite only here", analyzed=False)
    session.add(ArticleTranslation(article_id=first.id, language="zh-TW", title="準晶體", content="準晶體 晶格"))
    session.commit()

    yield topic.id, unanalyzed.id

    article_ids = [a.id for a in session.query(Article).filter(Article.topic_id == topic.id)]
    session.query(ArticleSearchToken).filter(ArticleSearchToken.article_id.in_(article_ids)).delete(synchronize_session=False)
    session.query(Article).filter(Article.id.in_(article_ids)).update({Article.merged_into_id: None}, synchronize_session=False)
    session.query(ArticleTranslation).filter(ArticleTranslation.article_id.in_(article_ids)).delete(synchronize_session=False)
    session.query(Analysis).filter(Analysis.article_id.in_(article_ids)).delete(synchronize_session=False)
    session.query(Article).filter(Article.id.in_(article_ids)).delete(synchronize_session=False)
    session.query(Topic).filter(Topic.id == topic.id).delete(synchronize_session=False)
    session.commit()
    session.close()


def test_rebuild_search_index_use_case_syncs_tokens_incrementally(db_session, indexed_topic, index_url):
    from datetime import datetime, timezone
    from models.article import Article
    from models.article_search_token import ArticleSearchToken
    from models.article_translation import ArticleTranslation
    from src.infrastructure.persistence.intelligence import SqlAlchemyArticleSearchTokenRepository
    from src.modules.search.application.use_cases import RebuildSearchIndexUseCase

    topic_id, unanalyzed_id = indexed_topic
    gateway = RedisSearchIndexGateway(redis_url=index_url)
    use_case = RebuildSearchIndexUseCase(
        search_token_repo=SqlAlchemyArticleSearchTokenRepository(db_session),
        search_index_gateway=gateway,
        min_doc_freq=2,
    )

    def _rows():
        db_session.expire_all()
        return {
            (r.article_id, r.language): r
            for r in db_session.query(ArticleSearchToken).filter(ArticleSearchToken.topic_id == topic_id)
        }

    first_stats = use_case.execute()

    rows = _rows()
    assert first_stats["indexed_count"] >= 3  # 2 originals + 1 translation (other topics may add more)
    assert {lang for _, lang in rows} == {"en", "zh-TW"}
    assert all(article_id != unanalyzed_id for article_id, _ in rows), "un-analyzed articles must be excluded"
    en_tokens = [set(r.tokens) for (_, lang), r in rows.items() if lang == "en"]
    assert all("quasicrystal" in tokens for tokens in en_tokens)
    assert any("lattices" in tokens for tokens in en_tokens)  # doc freq 1 — still indexed
    # Redis: only terms meeting min_doc_freq are suggested.
    assert [t.term for t in gateway.suggest(topic_id, "quasi")] == ["quasicrystal"]
    assert gateway.suggest(topic_id, "lattic") is None

    # Nothing changed -> nothing re-tokenized.
    assert use_case.execute()["indexed_count"] == 0

    # An updated translation is re-tokenized; a merged-away article's rows are removed.
    translation = db_session.query(ArticleTranslation).join(Article).filter(Article.topic_id == topic_id).one()
    translation.content = "準晶體 光子"
    translation.updated_at = datetime.now(timezone.utc)
    merged = db_session.query(Article).filter(
        Article.topic_id == topic_id, Article.id != translation.article_id, Article.id != unanalyzed_id,
    ).one()
    merged.merged_into_id = translation.article_id
    db_session.commit()

    third_stats = use_case.execute()

    rows = _rows()
    assert third_stats["indexed_count"] == 1
    assert third_stats["deleted_count"] >= 1
    assert "光子" in rows[(translation.article_id, "zh-TW")].tokens
    assert all(article_id != merged.id for article_id, _ in rows)
