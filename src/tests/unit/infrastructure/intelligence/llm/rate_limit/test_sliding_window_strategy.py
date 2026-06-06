"""
Unit tests for SlidingWindowStrategy — RPM, TPM, RPD enforcement and eviction.
Uses time mocking to avoid real sleeps.
"""
from unittest.mock import patch, MagicMock

import pytest

from src.infrastructure.intelligence.llm.rate_limit.sliding_window_strategy import (
    SlidingWindowStrategy,
    RateLimitExhausted,
)
from src.infrastructure.intelligence.llm.rate_limit import NoOpStrategy


# ── RPM: within limit ─────────────────────────────────────────────────────────

def test_rpm_allows_requests_within_limit():
    with patch('time.sleep') as mock_sleep, \
         patch('time.monotonic', return_value=0.0):
        strategy = SlidingWindowStrategy(rpm=5, tpm=1_000_000, rpd=1000)
        for _ in range(5):
            strategy.acquire(10)
        mock_sleep.assert_not_called()


# ── RPM: blocks when window full ─────────────────────────────────────────────

def test_rpm_blocks_when_window_full():
    with patch('time.sleep') as mock_sleep, \
         patch('time.monotonic', return_value=0.0):
        mock_sleep.side_effect = StopIteration  # break infinite loop on first sleep

        strategy = SlidingWindowStrategy(rpm=2, tpm=1_000_000, rpd=1000)
        strategy.acquire(10)  # slot 1 at t=0
        strategy.acquire(10)  # slot 2 at t=0 — window now full

        with pytest.raises(StopIteration):
            strategy.acquire(10)  # should call sleep

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] > 0


# ── TPM: blocks when token budget exhausted ───────────────────────────────────

def test_tpm_blocks_when_token_budget_exhausted():
    with patch('time.sleep') as mock_sleep, \
         patch('time.monotonic', return_value=0.0):
        mock_sleep.side_effect = StopIteration

        strategy = SlidingWindowStrategy(rpm=1000, tpm=100, rpd=10000)
        strategy.acquire(60)  # uses 60 tokens — OK

        with pytest.raises(StopIteration):
            strategy.acquire(60)  # 60+60=120 > 100 tpm — should sleep

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] > 0


# ── RPD: raises RateLimitExhausted ───────────────────────────────────────────

def test_rpd_raises_rate_limit_exhausted_when_exceeded():
    with patch('time.monotonic', return_value=0.0):
        strategy = SlidingWindowStrategy(rpm=1000, tpm=1_000_000, rpd=2)
        strategy.acquire(10)  # daily_count → 1
        strategy.acquire(10)  # daily_count → 2

        with pytest.raises(RateLimitExhausted):
            strategy.acquire(10)  # daily_count(2) >= rpd(2) → raise


# ── record_usage replaces estimated token entry ───────────────────────────────

def test_record_usage_updates_token_window_with_actual_tokens():
    with patch('time.monotonic', return_value=0.0):
        strategy = SlidingWindowStrategy(rpm=100, tpm=10000, rpd=10000)
        strategy.acquire(50)  # estimated 50 tokens recorded

        assert strategy._tpm_window[-1][1] == 50

        strategy.record_usage(200)  # actual was 200 — replaces last entry

        assert strategy._tpm_window[-1][1] == 200


# ── Eviction removes stale entries ───────────────────────────────────────────

def test_eviction_removes_entries_older_than_60s():
    monotonic_values = [0.0, 0.0, 0.0, 0.0, 61.0, 61.0, 61.0, 61.0]
    call_count = 0

    def advancing_monotonic():
        nonlocal call_count
        val = monotonic_values[min(call_count, len(monotonic_values) - 1)]
        call_count += 1
        return val

    with patch('time.monotonic', side_effect=advancing_monotonic), \
         patch('time.sleep'):
        strategy = SlidingWindowStrategy(rpm=2, tpm=1_000_000, rpd=1000)
        strategy.acquire(10)  # t=0, slot 1
        strategy.acquire(10)  # t=0, slot 2 — window full

        # Time advances to 61s; old entries (t=0) should be evicted → room available
        strategy.acquire(10)  # should succeed without sleeping

    # Only the new entry remains
    assert len(strategy._rpm_window) == 1


# ── NoOpStrategy: unlimited pass-through ─────────────────────────────────────

def test_noop_strategy_acquire_and_record_do_not_raise():
    strategy = NoOpStrategy()
    for _ in range(100):
        strategy.acquire(1_000_000)
        strategy.record_usage(1_000_000)
