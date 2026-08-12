"""Integration tests for shared/cache/redis_gateway.py against a real Redis instance."""
import uuid

import pytest

from backend.config import REDIS_URL
from shared.cache import RedisCacheGateway

pytestmark = pytest.mark.integration


@pytest.fixture
def gateway():
    return RedisCacheGateway(redis_url=REDIS_URL)


@pytest.fixture
def namespace():
    """A unique namespace per test so runs don't interfere with each other's version counters."""
    return f"test_ns_{uuid.uuid4().hex[:8]}"


def test_cache_miss_then_hit_round_trip(gateway, namespace):
    calls = []

    def loader():
        calls.append(1)
        return {"value": 42}

    first = gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=loader)
    second = gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=loader)

    assert first.value == {"value": 42}
    assert first.status == "MISS"
    assert second.value == {"value": 42}
    assert second.status == "HIT"
    assert len(calls) == 1  # loader only ran once — second call was a cache hit


def test_different_params_are_cached_independently(gateway, namespace):
    result_a = gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=lambda: "a")
    result_b = gateway.get_or_set(namespace, {"page": 2}, ttl_seconds=60, loader=lambda: "b")

    assert result_a.value == "a"
    assert result_b.value == "b"


def test_bump_version_invalidates_previous_entries(gateway, namespace):
    """Also the regression case for the first-bump-is-a-no-op off-by-one (research.md
    Post-Ship Addendum, Bug 3): `namespace` here has never been bumped before, so this
    exercises exactly the scenario where a bare INCR on a still-missing version key
    would coincide with _current_version()'s default and fail to invalidate anything."""
    calls = []

    def loader():
        calls.append(1)
        return "value"

    gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=loader)
    gateway.bump_version(namespace)
    gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=loader)

    assert len(calls) == 2  # loader ran again after the version bump orphaned the old entry


def test_lang_is_part_of_the_cache_key(gateway, namespace):
    calls = []

    def loader():
        calls.append(1)
        return "value"

    gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=loader, lang="en")
    gateway.get_or_set(namespace, {"page": 1}, ttl_seconds=60, loader=loader, lang="zh-TW")

    assert len(calls) == 2  # different lang -> different cache entry
