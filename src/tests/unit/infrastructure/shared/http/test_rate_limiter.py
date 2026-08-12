"""
Regression tests for DomainRateLimiter's circuit-breaker + concurrency race.

Context (see refresh_metrics.py production log, 2026-08-12): with several
concurrent callers racing into acquire() before any of them has failed yet,
one gets the domain's only available token and trips the circuit on failure —
but the others are already past the entry check and blocked inside the
token bucket's wait for the *next* token (up to 60s on a 1 RPM domain).
Without re-checking mid-wait, each straggler would still wake up and send its
own real, doomed request once its token came due.
"""
import threading
import time

import pytest

import src.infrastructure.shared.http.rate_limiter as rate_limiter_module
from src.infrastructure.shared.http.rate_limiter import (
    DomainCircuitOpenError,
    DomainRateLimiter,
)

# src/tests/conftest.py's autouse disable_rate_limiting fixture replaces
# DomainRateLimiter.acquire()/connection() with no-ops for every other test
# suite (so they don't block on real token buckets) — captured here, at
# collection time, before that fixture ever runs.
_REAL_ACQUIRE = rate_limiter_module.DomainRateLimiter.acquire
_REAL_CONNECTION = rate_limiter_module.DomainRateLimiter.connection


@pytest.fixture(autouse=True)
def use_real_rate_limiter(monkeypatch):
    """This module tests DomainRateLimiter.acquire()'s actual circuit-breaker
    logic, so undo conftest.py's global no-op patch for these tests."""
    monkeypatch.setattr(rate_limiter_module.DomainRateLimiter, "acquire", _REAL_ACQUIRE)
    monkeypatch.setattr(rate_limiter_module.DomainRateLimiter, "connection", _REAL_CONNECTION)


def test_acquire_raises_immediately_once_tripped():
    limiter = DomainRateLimiter()
    limiter.note_rate_limited("example.com")

    with pytest.raises(DomainCircuitOpenError):
        limiter.acquire("example.com")


def test_acquire_does_not_raise_when_not_tripped():
    limiter = DomainRateLimiter(overrides={"example.com": 1000.0})  # high RPM — no blocking
    limiter.acquire("example.com")  # should return normally


def test_tripping_one_domain_does_not_affect_another():
    limiter = DomainRateLimiter(overrides={"a.example.com": 1000.0, "b.example.com": 1000.0})
    limiter.note_rate_limited("a.example.com")

    with pytest.raises(DomainCircuitOpenError):
        limiter.acquire("a.example.com")
    limiter.acquire("b.example.com")  # unaffected, should not raise


def test_straggler_bails_within_poll_interval_after_mid_wait_trip():
    """A caller already blocked waiting for the next token must notice a trip
    from another thread within ~_TRIP_POLL_INTERVAL_SECONDS (1s), not ride out
    the full refill interval (up to 60s at 1 RPM) before sending a real request."""
    limiter = DomainRateLimiter(overrides={"slow.example.com": 1.0})  # 1 RPM
    limiter.acquire("slow.example.com")  # consumes the only starting token

    result: dict = {}

    def straggler():
        start = time.monotonic()
        try:
            limiter.acquire("slow.example.com")
            result["raised"] = False
        except DomainCircuitOpenError:
            result["raised"] = True
        result["elapsed"] = time.monotonic() - start

    t = threading.Thread(target=straggler)
    t.start()
    time.sleep(0.3)  # let the straggler enter the bucket's wait loop first
    limiter.note_rate_limited("slow.example.com")
    t.join(timeout=10)

    assert not t.is_alive()
    assert result["raised"] is True
    # Should bail within ~1 poll interval of the trip, nowhere near the ~60s
    # the straggler would otherwise have waited for its own token.
    assert result["elapsed"] < 5.0
