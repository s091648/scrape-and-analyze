import pytest
from unittest.mock import patch
import time as time_module


def test_request_strategy_is_abstract():
    from src.analyzers.request_strategy import RequestStrategy
    with pytest.raises(TypeError):
        RequestStrategy()


def test_request_strategy_requires_acquire():
    from src.analyzers.request_strategy import RequestStrategy

    class MissingAcquire(RequestStrategy):
        def record_usage(self, actual_tokens: int) -> None:
            pass

    with pytest.raises(TypeError):
        MissingAcquire()


def test_request_strategy_requires_record_usage():
    from src.analyzers.request_strategy import RequestStrategy

    class MissingRecord(RequestStrategy):
        def acquire(self, estimated_tokens: int) -> None:
            pass

    with pytest.raises(TypeError):
        MissingRecord()


def test_rate_limit_exhausted_is_exception():
    from src.analyzers.request_strategy import RateLimitExhausted
    exc = RateLimitExhausted("daily limit hit")
    assert isinstance(exc, Exception)
    assert str(exc) == "daily limit hit"


def test_noop_strategy_acquire_does_nothing():
    from src.analyzers.request_strategy import NoOpStrategy
    s = NoOpStrategy()
    s.acquire(1000)  # must not raise or sleep


def test_noop_strategy_record_usage_does_nothing():
    from src.analyzers.request_strategy import NoOpStrategy
    s = NoOpStrategy()
    s.record_usage(500)  # must not raise

def test_leaky_bucket_acquire_passes_when_under_limits():
    from src.analyzers.request_strategy import LeakyBucketStrategy
    s = LeakyBucketStrategy(rpm=5, tpm=250_000, rpd=20)
    s.acquire(estimated_tokens=100)  # first request, must not sleep or raise


def test_leaky_bucket_record_usage_updates_tpm_window():
    from src.analyzers.request_strategy import LeakyBucketStrategy
    s = LeakyBucketStrategy(rpm=5, tpm=250_000, rpd=20)
    s.acquire(estimated_tokens=100)
    s.record_usage(actual_tokens=300)
    # Internal tpm window should have one entry with 300 tokens
    assert len(s._tpm_window) == 1
    assert s._tpm_window[0][1] == 300


def test_leaky_bucket_rpm_blocks_when_full():
    """When RPM limit is reached, acquire() should sleep until a slot opens."""
    from src.analyzers.request_strategy import LeakyBucketStrategy

    slept = []

    def fake_sleep(duration):
        slept.append(duration)

    now = time_module.monotonic()

    # Pre-fill RPM window with rpm=2 requests at t=now-5 (recent, within 60s)
    s = LeakyBucketStrategy(rpm=2, tpm=250_000, rpd=20)
    s._rpm_window.append(now - 5)
    s._rpm_window.append(now - 3)

    with patch('src.analyzers.request_strategy.time.sleep', fake_sleep), \
         patch('src.analyzers.request_strategy.time.monotonic', return_value=now):
        s.acquire(estimated_tokens=100)

    assert len(slept) >= 1
    assert slept[0] > 0


def test_leaky_bucket_tpm_blocks_when_full():
    """When TPM limit is reached, acquire() should sleep."""
    from src.analyzers.request_strategy import LeakyBucketStrategy

    slept = []

    def fake_sleep(duration):
        slept.append(duration)

    now = time_module.monotonic()

    s = LeakyBucketStrategy(rpm=5, tpm=100, rpd=20)
    # Pre-fill TPM window: 90 tokens used 10 seconds ago
    s._tpm_window.append((now - 10, 90))

    with patch('src.analyzers.request_strategy.time.sleep', fake_sleep), \
         patch('src.analyzers.request_strategy.time.monotonic', return_value=now):
        # Requesting 20 more tokens would exceed tpm=100
        s.acquire(estimated_tokens=20)

    assert len(slept) >= 1


def test_leaky_bucket_cleans_stale_rpm_entries():
    """Entries older than 60s should be evicted from RPM window."""
    from src.analyzers.request_strategy import LeakyBucketStrategy

    now = time_module.monotonic()
    s = LeakyBucketStrategy(rpm=2, tpm=250_000, rpd=20)
    # Add stale entry (65s ago) — should be cleaned on acquire
    s._rpm_window.append(now - 65)

    with patch('src.analyzers.request_strategy.time.monotonic', return_value=now):
        s.acquire(estimated_tokens=100)  # must not sleep

    # Stale entry should have been evicted; only the new one remains
    assert len(s._rpm_window) == 1


def test_leaky_bucket_raises_when_daily_cap_hit():
    from src.analyzers.request_strategy import LeakyBucketStrategy, RateLimitExhausted
    s = LeakyBucketStrategy(rpm=100, tpm=1_000_000, rpd=3)
    s._daily_count = 3  # simulate cap already reached
    with pytest.raises(RateLimitExhausted, match="Daily request limit"):
        s.acquire(estimated_tokens=100)


def test_leaky_bucket_daily_count_increments_on_acquire():
    from src.analyzers.request_strategy import LeakyBucketStrategy
    s = LeakyBucketStrategy(rpm=100, tpm=1_000_000, rpd=20)
    assert s._daily_count == 0
    s.acquire(estimated_tokens=100)
    assert s._daily_count == 1
