"""Tests for the small run-scoped rate-limit tracking primitive shared by
ScrapeExecutor, ResilientMetricsService, ResilientLLMService, and
ResilientEmbeddingService — each holds its own instance; see the class
docstring for why the state itself is never shared across them."""
from src.infrastructure.shared.rate_limit_tracker import RateLimitedProviderTracker


def test_starts_empty():
    tracker = RateLimitedProviderTracker()
    assert tracker.exhausted == []
    assert tracker.is_exhausted("gemini") is False


def test_mark_exhausted_is_reflected_immediately():
    tracker = RateLimitedProviderTracker()
    tracker.mark_exhausted("gemini")
    assert tracker.is_exhausted("gemini") is True
    assert tracker.exhausted == ["gemini"]


def test_mark_exhausted_is_idempotent():
    tracker = RateLimitedProviderTracker()
    tracker.mark_exhausted("gemini")
    tracker.mark_exhausted("gemini")
    assert tracker.exhausted == ["gemini"]


def test_exhausted_is_sorted():
    tracker = RateLimitedProviderTracker()
    tracker.mark_exhausted("openrouter")
    tracker.mark_exhausted("claude")
    tracker.mark_exhausted("gemini")
    assert tracker.exhausted == ["claude", "gemini", "openrouter"]


def test_unrelated_identifier_stays_unaffected():
    tracker = RateLimitedProviderTracker()
    tracker.mark_exhausted("gemini")
    assert tracker.is_exhausted("claude") is False
