"""Unit tests for shared/search_index/redis_gateway.py — mocked redis.Redis client."""
import uuid
from unittest.mock import MagicMock, patch

import redis

from shared.search_index.redis_gateway import _expand_term, _KEY_TTL_SECONDS, RedisSearchIndexGateway
from shared.search_index.search_term import SearchTerm


# ---------------------------------------------------------------------------
# _expand_term — the suffix-capped-prefix expansion (research.md)
# ---------------------------------------------------------------------------

def test_expand_term_uncapped_short_word_produces_all_suffix_prefixes():
    # "search" has 6 distinct chars (no repeats), 6 <= cap 8, so uncapped == capped:
    # L(L+1)/2 = 21 entries exactly (a repeated-letter word like "learning" would dedupe
    # below the raw formula — see test_expand_term_dedupes_repeated_substrings below).
    keys = _expand_term("search", max_len=8)
    assert len(keys) == 21
    assert "s" in keys
    assert "search" in keys
    assert "arc" in keys  # prefix of the suffix "arch" — contains-anywhere matching


def test_expand_term_caps_long_word():
    keys = _expand_term("reinforcement", max_len=8)
    assert all(len(k) <= 8 for k in keys)
    assert "reinforce" not in keys  # would be 9 chars, over the cap


def test_expand_term_lowercases():
    assert _expand_term("Learning", max_len=8) == _expand_term("learning", max_len=8)


def test_expand_term_handles_cjk_characters_at_the_codepoint_level():
    # Python string slicing/len() is codepoint-based, not byte-based, so this needs no
    # special-casing versus the English path — verified live against a real UTF-8 round
    # trip through Redis in test_suggest_matches_cjk_terms_anywhere_not_just_prefix below,
    # not just this pure-function check.
    keys = _expand_term("機器學習", max_len=8)
    assert keys == {"機", "機器", "機器學", "機器學習", "器", "器學", "器學習", "學", "學習", "習"}


def test_expand_term_dedupes_repeated_substrings():
    # "aa" appears as a prefix of multiple suffixes of "banana" — must not inflate the set.
    keys = _expand_term("banana", max_len=8)
    assert isinstance(keys, set)
    assert "an" in keys


# ---------------------------------------------------------------------------
# RedisSearchIndexGateway
# ---------------------------------------------------------------------------

def _make_gateway(client=None, staging_client=None, max_prefix_len=8):
    client = client or MagicMock()
    client.connection_pool.connection_kwargs = {"db": 2}
    staging_client = staging_client or MagicMock()
    with patch("redis.Redis.from_url", return_value=client):
        gateway = RedisSearchIndexGateway(redis_url="redis://unused:6379/2", max_prefix_len=max_prefix_len)
    # _staging_client() is called lazily (once per rebuild()), well after construction —
    # patch it directly rather than relying on a second from_url() call's ordering.
    gateway._staging_client = MagicMock(return_value=staging_client)
    return gateway, client, staging_client


def test_rebuild_writes_via_pipeline_not_individual_calls():
    gateway, client, staging = _make_gateway()
    pipe = MagicMock()
    staging.pipeline.return_value = pipe

    topic_id = uuid.uuid4()
    gateway.rebuild({topic_id: {"learning": 5}})

    staging.flushdb.assert_called_once()
    assert pipe.zadd.called
    assert pipe.execute.called
    staging.zadd.assert_not_called()  # never a direct per-key call outside the pipeline


def test_rebuild_swaps_staging_db_into_main_after_writing():
    gateway, client, staging = _make_gateway()
    staging.pipeline.return_value = MagicMock()

    gateway.rebuild({uuid.uuid4(): {"learning": 5}})

    client.execute_command.assert_called_once_with("SWAPDB", 2, 3)


def test_rebuild_sets_rebuilt_at_marker():
    gateway, client, staging = _make_gateway()
    pipe = MagicMock()
    staging.pipeline.return_value = pipe

    gateway.rebuild({uuid.uuid4(): {"learning": 5}})

    keys_set = [call.args[0] for call in pipe.set.call_args_list]
    assert "search:idx:rebuilt_at" in keys_set


def test_rebuild_sets_ttl_on_every_term_key():
    """023-article-search follow-up: repopulate()-only writes don't participate in the
    FLUSHDB+SWAPDB replace cycle, so without a TTL they're the one thing that could
    accumulate indefinitely if rebuild() ever stopped running for an extended period —
    see _KEY_TTL_SECONDS' docstring for the full reasoning."""
    gateway, client, staging = _make_gateway()
    pipe = MagicMock()
    staging.pipeline.return_value = pipe

    gateway.rebuild({uuid.uuid4(): {"learning": 5}})

    assert pipe.expire.called
    for call in pipe.expire.call_args_list:
        assert call.args[1] == _KEY_TTL_SECONDS


def test_rebuild_does_not_ttl_the_rebuilt_at_marker():
    """_REBUILT_AT_KEY deliberately stays TTL-less — it's the "how stale is this index"
    signal, which is more useful surviving indefinitely (showing an old timestamp) than
    disappearing once its own TTL elapses."""
    gateway, client, staging = _make_gateway()
    pipe = MagicMock()
    staging.pipeline.return_value = pipe

    gateway.rebuild({uuid.uuid4(): {"learning": 5}})

    expired_keys = [call.args[0] for call in pipe.expire.call_args_list]
    assert "search:idx:rebuilt_at" not in expired_keys


def test_rebuild_never_raises_on_redis_error():
    gateway, client, staging = _make_gateway()
    staging.flushdb.side_effect = redis.exceptions.ConnectionError("down")

    gateway.rebuild({uuid.uuid4(): {"learning": 5}})  # must not raise


def test_rebuild_skips_swap_when_topic_terms_is_empty():
    # A build with zero terms must never SWAPDB in — that would blow away a good
    # live index with nothing (the incident this guard was added for).
    gateway, client, staging = _make_gateway()

    gateway.rebuild({})

    staging.flushdb.assert_not_called()
    client.execute_command.assert_not_called()


def test_rebuild_skips_swap_when_all_topics_have_no_terms():
    gateway, client, staging = _make_gateway()

    gateway.rebuild({uuid.uuid4(): {}})

    staging.flushdb.assert_not_called()
    client.execute_command.assert_not_called()


def test_suggest_returns_none_when_prefix_not_cached():
    gateway, client, staging = _make_gateway()
    client.exists.return_value = 0

    assert gateway.suggest(topic_id=uuid.uuid4(), prefix="lear") is None


def test_suggest_returns_ranked_terms_on_hit():
    gateway, client, staging = _make_gateway()
    client.exists.return_value = 1
    client.zrevrange.return_value = [(b"learning", 42.0), (b"learned", 7.0)]

    result = gateway.suggest(topic_id=uuid.uuid4(), prefix="lear")

    assert result == [SearchTerm(term="learning", occurrence_count=42), SearchTerm(term="learned", occurrence_count=7)]


def test_suggest_truncates_lookup_key_beyond_cap_and_post_filters():
    gateway, client, staging = _make_gateway(max_prefix_len=8)
    client.exists.return_value = 1
    # "learning" doesn't contain "learningx" -> must be filtered out post-lookup
    client.zrevrange.return_value = [(b"learning", 10.0), (b"learningxyz", 3.0)]

    result = gateway.suggest(topic_id=None, prefix="learningx")  # 9 chars, over cap=8

    lookup_key = client.zrevrange.call_args[0][0]
    assert lookup_key.endswith(":learningx"[:9])  # truncated to 8 chars for the actual key
    assert result == [SearchTerm(term="learningxyz", occurrence_count=3)]


def test_suggest_returns_none_on_redis_error():
    gateway, client, staging = _make_gateway()
    client.exists.side_effect = redis.exceptions.ConnectionError("down")

    assert gateway.suggest(topic_id=uuid.uuid4(), prefix="lear") is None


def test_suggest_partitions_by_topic_id():
    gateway, client, staging = _make_gateway()
    client.exists.return_value = 1
    client.zrevrange.return_value = []
    topic_id = uuid.uuid4()

    gateway.suggest(topic_id=topic_id, prefix="lear")

    key = client.zrevrange.call_args[0][0]
    assert str(topic_id) in key


def test_suggest_uses_none_partition_when_topic_id_is_none():
    gateway, client, staging = _make_gateway()
    client.exists.return_value = 1
    client.zrevrange.return_value = []

    gateway.suggest(topic_id=None, prefix="lear")

    key = client.zrevrange.call_args[0][0]
    assert ":none:" in key


def test_repopulate_writes_terms_back_to_redis():
    gateway, client, staging = _make_gateway()
    gateway.repopulate(topic_id=uuid.uuid4(), prefix="lear", terms=[SearchTerm(term="learning", occurrence_count=5)])
    assert client.zadd.called


def test_repopulate_sets_ttl_on_the_written_key():
    gateway, client, staging = _make_gateway()
    gateway.repopulate(topic_id=uuid.uuid4(), prefix="lear", terms=[SearchTerm(term="learning", occurrence_count=5)])

    assert client.expire.called
    ttl_key, ttl_seconds = client.expire.call_args[0]
    zadd_key = client.zadd.call_args[0][0]
    assert ttl_key == zadd_key
    assert ttl_seconds == _KEY_TTL_SECONDS


def test_repopulate_noop_on_empty_terms():
    gateway, client, staging = _make_gateway()
    gateway.repopulate(topic_id=uuid.uuid4(), prefix="lear", terms=[])
    client.zadd.assert_not_called()


def test_repopulate_never_raises_on_redis_error():
    gateway, client, staging = _make_gateway()
    client.zadd.side_effect = redis.exceptions.ConnectionError("down")
    gateway.repopulate(topic_id=uuid.uuid4(), prefix="lear", terms=[SearchTerm(term="learning", occurrence_count=5)])
