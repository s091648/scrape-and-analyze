"""
Centralised HTTP retry policy built on tenacity.

Retry matrix:
  429            → respect Retry-After header; else exponential 30→60→120→240s; max 4 attempts
  502/503/504    → exponential with jitter 5→10→20→40s; max 3 attempts
  500            → exponential with jitter; max 3 attempts
  403            → NOT retried here (UA rotation is handled by HttpClient)
  404/410        → NOT retried
  Timeout        → fixed 2s, max 3 attempts
  ConnectionError→ exponential with jitter; max 4 attempts
"""
import random
import requests
import tenacity

from src.infrastructure.shared.logging import get_logger

logger = get_logger(__name__)

_RETRYABLE_STATUS = frozenset([429, 500, 502, 503, 504])


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.exceptions.HTTPError):
        if exc.response is None:
            return True
        return exc.response.status_code in _RETRYABLE_STATUS
    # ProxyError should not be retried — it needs immediate proxy disable + outer retry
    if isinstance(exc, requests.exceptions.ProxyError):
        return False
    return isinstance(exc, (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
    ))


def _compute_wait(retry_state: tenacity.RetryCallState) -> float:
    exc = retry_state.outcome.exception()
    attempt = retry_state.attempt_number

    if (
        isinstance(exc, requests.exceptions.HTTPError)
        and exc.response is not None
        and exc.response.status_code == 429
    ):
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass
        # exponential with jitter: base 30→60→120→240s, ±25%
        base = min(30 * (2 ** (attempt - 1)), 240)
        return base * random.uniform(0.75, 1.25)

    # 5xx / connection / timeout: shorter with jitter
    base = min(5 * (2 ** (attempt - 1)), 60)
    return base * (0.5 + random.random() * 0.5)


def _compute_and_log_wait(retry_state: tenacity.RetryCallState) -> float:
    """Compute wait duration, log it, and return it — called once by tenacity."""
    exc = retry_state.outcome.exception()
    status = None
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        status = exc.response.status_code
    wait = _compute_wait(retry_state)
    logger.warning(
        "http_retry",
        attempt=retry_state.attempt_number,
        wait_seconds=round(wait, 1),
        status_code=status,
        exc_type=type(exc).__name__,
    )
    return wait


def make_retry_policy(max_attempts: int = 4) -> tenacity.Retrying:
    """
    Return a configured ``tenacity.Retrying`` instance.

    The returned object is safe to reuse across multiple calls — tenacity
    resets its internal state on each ``for attempt in policy:`` iteration.
    """
    return tenacity.Retrying(
        retry=tenacity.retry_if_exception(_is_retryable),
        wait=_compute_and_log_wait,
        stop=tenacity.stop_after_attempt(max_attempts),
        reraise=True,
    )
