"""Unit tests for shared/cache/redis_gateway.py — mocked redis.Redis client, no real Redis."""
import json
from unittest.mock import MagicMock, patch

import redis


def _make_gateway(client=None):
    from shared.cache import RedisCacheGateway

    with patch("redis.Redis.from_url", return_value=client or MagicMock()):
        gateway = RedisCacheGateway(redis_url="redis://unused:6379/0")
    return gateway


def test_get_or_set_cache_miss_calls_loader_and_writes():
    client = MagicMock()
    client.get.return_value = None
    gateway = _make_gateway(client)
    loader = MagicMock(return_value={"hello": "world"})

    result = gateway.get_or_set("articles", {"page": 1}, ttl_seconds=60, loader=loader)

    assert result.value == {"hello": "world"}
    assert result.status == "MISS"
    loader.assert_called_once()
    assert client.set.called
    written_key, written_value = client.set.call_args.args
    assert json.loads(written_value) == {"hello": "world"}
    assert written_key.startswith("articles:v")


def test_get_or_set_cache_hit_skips_loader():
    client = MagicMock()
    client.get.side_effect = [b"1", json.dumps({"cached": True}).encode()]
    gateway = _make_gateway(client)
    loader = MagicMock()

    result = gateway.get_or_set("articles", {"page": 1}, ttl_seconds=60, loader=loader)

    assert result.value == {"cached": True}
    assert result.status == "HIT"
    loader.assert_not_called()


def test_get_or_set_different_params_produce_different_keys():
    client = MagicMock()
    client.get.return_value = None
    gateway = _make_gateway(client)

    gateway.get_or_set("articles", {"page": 1}, ttl_seconds=60, loader=lambda: "a")
    gateway.get_or_set("articles", {"page": 2}, ttl_seconds=60, loader=lambda: "b")

    keys_written = [call.args[0] for call in client.set.call_args_list]
    assert keys_written[0] != keys_written[1]


def test_bump_version_orphans_previous_key():
    client = MagicMock()
    # First read: version key absent -> current_version() returns 1 (default)
    client.get.side_effect = [None, None]
    gateway = _make_gateway(client)

    gateway.get_or_set("articles", {"page": 1}, ttl_seconds=60, loader=lambda: "a")
    key_v1 = client.set.call_args.args[0]

    client.incr.return_value = 2
    gateway.bump_version("articles")

    client.get.side_effect = [b"2", None]
    gateway.get_or_set("articles", {"page": 1}, ttl_seconds=60, loader=lambda: "b")
    key_v2 = client.set.call_args.args[0]

    assert key_v1 != key_v2
    assert "v1" in key_v1
    assert "v2" in key_v2


def test_get_or_set_falls_through_uncached_on_redis_error():
    client = MagicMock()
    client.get.side_effect = redis.exceptions.ConnectionError("down")
    gateway = _make_gateway(client)
    loader = MagicMock(return_value="fallback")

    result = gateway.get_or_set("articles", {"page": 1}, ttl_seconds=60, loader=loader)

    assert result.value == "fallback"
    assert result.status == "BYPASS"
    loader.assert_called_once()


def test_bump_version_no_ops_on_redis_error():
    client = MagicMock()
    client.incr.side_effect = redis.exceptions.ConnectionError("down")
    gateway = _make_gateway(client)

    result = gateway.bump_version("articles")

    assert result == 0


def test_publish_warmup_signal_publishes_on_warmup_channel():
    from shared.cache import WARMUP_CHANNEL

    client = MagicMock()
    gateway = _make_gateway(client)

    gateway.publish_warmup_signal(reason="scraper_pipeline")

    client.publish.assert_called_once_with(WARMUP_CHANNEL, "scraper_pipeline")


def test_publish_warmup_signal_no_ops_on_redis_error():
    client = MagicMock()
    client.publish.side_effect = redis.exceptions.ConnectionError("down")
    gateway = _make_gateway(client)

    gateway.publish_warmup_signal(reason="scraper_pipeline")  # must not raise


def test_bump_version_seeds_missing_key_before_incr():
    """Regression: a bare INCR on a never-bumped namespace's still-missing version key
    would land on 1, coinciding with _current_version()'s default-for-missing-key
    fallback (also 1) — making a namespace's first-ever bump a no-op from the reader's
    perspective. bump_version() must SETNX the key to 1 first so the following INCR
    always lands on >= 2 (see research.md Post-Ship Addendum, Bug 3)."""
    client = MagicMock()
    client.incr.return_value = 2
    gateway = _make_gateway(client)

    result = gateway.bump_version("articles")

    client.setnx.assert_called_once()
    setnx_key = client.setnx.call_args.args[0]
    assert setnx_key == client.incr.call_args.args[0]
    assert result == 2
