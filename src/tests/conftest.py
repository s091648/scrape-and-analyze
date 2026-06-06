import os
import logging
from contextlib import contextmanager

# ── Clear Grafana credentials BEFORE any module import ────────────────────────
# This must happen before test modules are collected / imported so that:
#   1. otel_tracing._setup_tracing() sees no GRAFANA vars → returns None →
#      _tracer is a no-op → no BatchSpanProcessor trying to export to Grafana
#      Cloud and blocking span-related tests.
#   2. configure_loki() sees no GRAFANA_LOKI_URL → skips LokiHandler setup →
#      no synchronous blocking HTTP call on every logger.info() in subsequent
#      tests (LokiHandler is NOT async by default; each log record fires an HTTP
#      request in the calling thread, adding 5-10 s per call when Loki is down).
for _k in ('GRAFANA_OTLP_ENDPOINT', 'GRAFANA_OTLP_USER',
           'GRAFANA_LOKI_URL', 'GRAFANA_LOKI_USER', 'GRAFANA_API_KEY'):
    os.environ.pop(_k, None)

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_db')
os.environ.setdefault('APP_ENV', 'test')

import pytest


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch):
    """
    Disable per-domain rate limiting so tests don't wait between HTTP calls.
    Patching the class method covers existing module-level client instances too,
    because Python looks up instance methods on the class at call time.
    """
    from src.infrastructure.shared.http.rate_limiter import DomainRateLimiter

    @contextmanager
    def _noop(self, domain: str):
        yield

    monkeypatch.setattr(DomainRateLimiter, 'connection', _noop)
    monkeypatch.setattr(DomainRateLimiter, 'acquire', lambda self, domain: None)


@pytest.fixture(autouse=True)
def fast_http_retry(monkeypatch):
    """
    Replace HttpClient's exponential-backoff retry wait with wait_none() so
    tests that mock 4xx/5xx responses don't wait 1+2+4+8 s of tenacity sleep.

    Also resets the module-level _default_client to None so that each test that
    calls get_default_client() constructs a fresh HttpClient that picks up both
    this patch (retry wait) and the disable_rate_limiting patch (token bucket).
    """
    try:
        import tenacity as _ten
        import src.infrastructure.shared.http.retry as _retry_mod
        import src.infrastructure.shared.http.http_client as _hc_mod

        # Force a fresh client per test so the patched make_retry_policy is used
        monkeypatch.setattr(_hc_mod, '_default_client', None)

        _orig = _retry_mod.make_retry_policy

        def _fast(max_attempts=4, skip_status=frozenset()):
            policy = _orig(max_attempts, skip_status)
            policy.wait = _ten.wait_none()
            return policy

        monkeypatch.setattr(_retry_mod, 'make_retry_policy', _fast)
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def fast_scrape_executor(monkeypatch):
    """Zero out all time.sleep in scrape_executor so fetch_delay (default 5 s) and
    discover cooldowns don't stall unit tests. Per-host semaphore serialisation
    is unaffected because it relies on threading locks, not sleep."""
    try:
        import src.infrastructure.collection.executor.scrape_executor as _exec_mod
        monkeypatch.setattr(_exec_mod.time, 'sleep', lambda _secs: None)
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def fast_llm_retry(monkeypatch):
    """Replace wait_exponential(min=4, max=60) on BaseProvider._retry and
    _translate_retry with wait_none() so LLM retry tests don't wait 4-60 s
    between attempts."""
    try:
        import tenacity as _ten
        import src.infrastructure.intelligence.llm.providers.base_provider as _bp
        _orig_init = _bp.BaseProvider.__init__

        def _fast_init(self, model: str) -> None:
            _orig_init(self, model)
            self._retry.wait = _ten.wait_none()
            self._translate_retry.wait = _ten.wait_none()

        monkeypatch.setattr(_bp.BaseProvider, '__init__', _fast_init)
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def reset_root_logger():
    """
    Restore the root logger to its pre-test state after each test.

    configure_loki() unconditionally appends a new StreamHandler(stdout) to the
    root logger on every call, without deduplication.  Without this fixture the
    handlers pile up across the session: by the 10th logging-related test every
    log line is written 10+ times, making all subsequent tests measurably slower.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)
