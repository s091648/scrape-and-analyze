# LLM Request Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a pluggable request strategy layer that prevents Gemini Free tier HTTP 429 errors by serializing concurrent LLM calls and enforcing RPM/RPD limits.

**Architecture:** A `RequestStrategy` ABC wraps any `LLMProvider` and itself implements the `LLMProvider` interface (Decorator pattern). `build_strategy(provider, tier)` in `src/analyzers/strategy.py` selects the concrete strategy; `build_analyzer()` in `src/analyzers/__init__.py` composes them. `ThreadPoolExecutor` workers in `main.py` are unaffected — they see only the `LLMProvider` interface.

**Tech Stack:** Python 3.11, `threading.Lock` (stdlib), `structlog` (structured logging), `pytest` + `unittest.mock` (no pytest-mock), `structlog.testing.capture_logs` for log assertions.

---

## Phase 1: Config

### Task 1.1: Add `LLM_API_TIER` to config

**Files:**
- Modify: `src/config.py`
- Modify: `tests/unit/test_config.py`

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_config.py`:

```python
def test_llm_api_tier_defaults_to_free():
    """LLM_API_TIER should default to 'free' when not set."""
    import importlib
    import src.config as config_module
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('LLM_API_TIER', None)
        importlib.reload(config_module)
        assert config_module.LLM_API_TIER == 'free'


def test_llm_api_tier_reads_from_env():
    """LLM_API_TIER should read 'paid' from environment."""
    import importlib
    import src.config as config_module
    with patch.dict(os.environ, {'LLM_API_TIER': 'paid'}):
        importlib.reload(config_module)
        assert config_module.LLM_API_TIER == 'paid'
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_config.py -k api_tier -v
```

Expected: `AttributeError: module 'src.config' has no attribute 'LLM_API_TIER'`

**Step 3: Write minimal implementation**

Add to `src/config.py` after the existing env var block:

```python
LLM_API_TIER = os.environ.get('LLM_API_TIER', 'free')
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_config.py -k api_tier -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add src/config.py tests/unit/test_config.py
git commit -m "✨ [FEAT] Add LLM_API_TIER config env var"
```

---

### Task 1.2: Add `LLM_MAX_REQUESTS_PER_RUN` to config

**Files:**
- Modify: `src/config.py`
- Modify: `tests/unit/test_config.py`

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_config.py`:

```python
def test_llm_max_requests_per_run_defaults_to_20():
    """LLM_MAX_REQUESTS_PER_RUN should default to 20 when not set."""
    import importlib
    import src.config as config_module
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('LLM_MAX_REQUESTS_PER_RUN', None)
        importlib.reload(config_module)
        assert config_module.LLM_MAX_REQUESTS_PER_RUN == 20


def test_llm_max_requests_per_run_reads_from_env():
    """LLM_MAX_REQUESTS_PER_RUN should read integer value from environment."""
    import importlib
    import src.config as config_module
    with patch.dict(os.environ, {'LLM_MAX_REQUESTS_PER_RUN': '10'}):
        importlib.reload(config_module)
        assert config_module.LLM_MAX_REQUESTS_PER_RUN == 10
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_config.py -k max_requests -v
```

Expected: `AttributeError: module 'src.config' has no attribute 'LLM_MAX_REQUESTS_PER_RUN'`

**Step 3: Write minimal implementation**

Add to `src/config.py` after `LLM_API_TIER`:

```python
LLM_MAX_REQUESTS_PER_RUN = int(os.environ.get('LLM_MAX_REQUESTS_PER_RUN', '20'))
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_config.py -k max_requests -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add src/config.py tests/unit/test_config.py
git commit -m "✨ [FEAT] Add LLM_MAX_REQUESTS_PER_RUN config env var"
```

---

### Task 1.3: Architecture diagram — Phase 1

**Files:**
- Modify: `docs/architecture/digital-twins-scraper.drawio`

**Step 1:** SKIP
**Step 2:** SKIP

**Step 3:** Open `docs/architecture/digital-twins-scraper.drawio` in draw.io. Navigate to the existing **"Phase 10 - Configuration"** page (which already shows the config.py env vars). Add two new env var boxes for `LLM_API_TIER` (default: `"free"`) and `LLM_MAX_REQUESTS_PER_RUN` (default: `20`) alongside the existing vars. Add an arrow from both boxes pointing to a new "Strategy Layer" node, showing they control which strategy `build_strategy()` selects.

**Step 4:** Confirm the updated Phase 10 page renders without errors in draw.io.

**Step 5: Commit**

```bash
git add docs/architecture/digital-twins-scraper.drawio
git commit -m "📐 [DOCS] Update architecture diagram — Phase 1 (config)"
```

---

## Phase 2: Strategy Module Foundation

### Task 2.1: Create `RequestStrategy` ABC

**Files:**
- Create: `src/analyzers/strategy.py`
- Create: `tests/unit/test_strategy.py`

---

**Step 1: Write the failing tests**

Create `tests/unit/test_strategy.py`:

```python
import pytest
from unittest.mock import MagicMock
from src.analyzers.llm_provider import AnalysisResult, LLMProvider


def make_result() -> AnalysisResult:
    """Helper: minimal valid AnalysisResult."""
    return AnalysisResult(
        tags=[], pain_points='', insights='', innovations='',
        input_tokens=0, output_tokens=0,
    )


# ── ABC ──────────────────────────────────────────────────────────────

class TestRequestStrategyABC:
    def test_cannot_instantiate_directly(self):
        """RequestStrategy is abstract and cannot be instantiated."""
        from src.analyzers.strategy import RequestStrategy
        with pytest.raises(TypeError):
            RequestStrategy(inner=MagicMock())

    def test_subclass_without_analyze_raises(self):
        """A concrete subclass that omits analyze() raises TypeError on instantiation."""
        from src.analyzers.strategy import RequestStrategy

        class Incomplete(RequestStrategy):
            pass

        with pytest.raises(TypeError):
            Incomplete(inner=MagicMock())

    def test_subclass_with_analyze_is_llm_provider(self):
        """A complete subclass is an instance of LLMProvider."""
        from src.analyzers.strategy import RequestStrategy

        class Complete(RequestStrategy):
            def analyze(self, content, prompt):
                return None

        instance = Complete(inner=MagicMock())
        assert isinstance(instance, LLMProvider)
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k abc -v
```

Expected: `ImportError: cannot import name 'RequestStrategy' from 'src.analyzers.strategy'` (file does not exist yet)

**Step 3: Write minimal implementation**

Create `src/analyzers/strategy.py`:

```python
import threading
import time
from abc import abstractmethod
from typing import Optional

from src.analyzers.llm_provider import AnalysisResult, LLMProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)

_GEMINI_FREE_MIN_INTERVAL = 12.0  # 60s / 5 RPM


class RequestStrategy(LLMProvider):
    """Abstract base class for LLM request strategies.

    Every concrete strategy wraps an inner LLMProvider and itself
    implements LLMProvider, making it transparent to callers.
    """

    def __init__(self, inner: LLMProvider):
        self._inner = inner

    @abstractmethod
    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        pass
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k abc -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add src/analyzers/strategy.py tests/unit/test_strategy.py
git commit -m "✨ [FEAT] Add RequestStrategy ABC to strategy module"
```

---

### Task 2.2: Implement `UnthrottledStrategy`

**Files:**
- Modify: `src/analyzers/strategy.py`
- Modify: `tests/unit/test_strategy.py`

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_strategy.py`:

```python
# ── UnthrottledStrategy ──────────────────────────────────────────────

class TestUnthrottledStrategy:
    def _make(self, provider=None):
        from src.analyzers.strategy import UnthrottledStrategy
        return UnthrottledStrategy(inner=provider or MagicMock())

    def test_returns_provider_result(self):
        """analyze() returns exactly what the inner provider returns."""
        expected = make_result()
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = expected

        strategy = self._make(mock_provider)
        result = strategy.analyze('content', 'prompt')

        assert result is expected

    def test_returns_none_when_provider_returns_none(self):
        """analyze() propagates None from the inner provider."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = None

        result = self._make(mock_provider).analyze('content', 'prompt')
        assert result is None

    def test_propagates_provider_exception(self):
        """analyze() does not catch exceptions from the inner provider."""
        mock_provider = MagicMock()
        mock_provider.analyze.side_effect = ValueError('unexpected failure')

        strategy = self._make(mock_provider)
        with pytest.raises(ValueError, match='unexpected failure'):
            strategy.analyze('content', 'prompt')

    def test_calls_provider_exactly_once_per_call(self):
        """Each analyze() invocation calls the inner provider exactly once."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = None
        strategy = self._make(mock_provider)

        strategy.analyze('a', 'p')
        strategy.analyze('b', 'p')
        assert mock_provider.analyze.call_count == 2

    def test_is_llm_provider(self):
        """UnthrottledStrategy is substitutable as LLMProvider."""
        from src.analyzers.strategy import UnthrottledStrategy
        assert isinstance(self._make(), LLMProvider)
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k unthrottled -v
```

Expected: `ImportError: cannot import name 'UnthrottledStrategy'`

**Step 3: Write minimal implementation**

Append to `src/analyzers/strategy.py`:

```python
class UnthrottledStrategy(RequestStrategy):
    """Pass-through strategy: delegates every call directly to the inner provider.

    No locking, sleeping, or counting. Zero overhead for paid tiers.
    """

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        return self._inner.analyze(content, prompt)
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k unthrottled -v
```

Expected: 5 PASSED

**Step 5: Commit**

```bash
git add src/analyzers/strategy.py tests/unit/test_strategy.py
git commit -m "✨ [FEAT] Implement UnthrottledStrategy pass-through"
```

---

### Task 2.3: Architecture diagram — Phase 2

**Files:**
- Modify: `docs/architecture/digital-twins-scraper.drawio`

**Step 1:** SKIP
**Step 2:** SKIP

**Step 3:** Open `docs/architecture/digital-twins-scraper.drawio` in draw.io. Navigate to the existing **"Phase 7 - LLM Analyzer"** page (which shows `LLMProvider` ABC with `ClaudeProvider` below it). Insert a new `RequestStrategy` ABC box between `LLMProvider` and the concrete providers, and add `UnthrottledStrategy` as a subclass of `RequestStrategy`. Add a note: "All strategies implement LLMProvider — transparent to callers."

**Step 4:** Confirm the updated Phase 7 page renders without errors.

**Step 5: Commit**

```bash
git add docs/architecture/digital-twins-scraper.drawio
git commit -m "📐 [DOCS] Update architecture diagram — Phase 2 (strategy foundation)"
```

---

## Phase 3: SequentialThrottleStrategy

### Task 3.1: Thread-safe serialization with context manager lock

**Files:**
- Modify: `src/analyzers/strategy.py`
- Modify: `tests/unit/test_strategy.py`

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_strategy.py`:

```python
import threading

# ── SequentialThrottleStrategy helpers ───────────────────────────────

def make_sequential(
    provider=None,
    min_interval_seconds=0.0,
    max_requests_per_run=100,
):
    from src.analyzers.strategy import SequentialThrottleStrategy
    return SequentialThrottleStrategy(
        inner=provider or MagicMock(),
        min_interval_seconds=min_interval_seconds,
        max_requests_per_run=max_requests_per_run,
    )


# ── Serialization ────────────────────────────────────────────────────

class TestSequentialThrottleSerialisation:
    def test_concurrent_calls_execute_serially(self):
        """Three threads calling analyze() simultaneously must execute one at a time.

        With min_interval_seconds=0.1 and 3 threads the total wall-clock time
        must be at least (3-1)*0.1 = 0.2 s (proves serial) and under 5 s
        (proves the real 12 s interval is not accidentally used).
        """
        call_order = []
        lock = threading.Lock()

        def mock_analyze(content, prompt):
            with lock:
                call_order.append(threading.current_thread().name)
            return make_result()

        mock_provider = MagicMock()
        mock_provider.analyze.side_effect = mock_analyze
        strategy = make_sequential(mock_provider, min_interval_seconds=0.1)

        start = time.time()
        threads = [
            threading.Thread(target=strategy.analyze, args=('c', 'p'), name=f'T{i}')
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        assert elapsed >= 0.2, f"Serial execution should take ≥0.2s, took {elapsed:.3f}s"
        assert elapsed < 5.0, f"Should finish in <5s (not using 12s interval), took {elapsed:.3f}s"
        assert mock_provider.analyze.call_count == 3

    def test_lock_released_after_non_429_exception(self):
        """Lock must be released even when a non-429 exception propagates.

        If the lock were NOT released, the second call would hang forever.
        We use a 2 s timeout on join() to detect a deadlock.
        """
        class AuthError(Exception):
            status_code = 401

        call_count = [0]

        def side_effect(content, prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                raise AuthError('Unauthorized')
            return make_result()

        mock_provider = MagicMock()
        mock_provider.analyze.side_effect = side_effect
        strategy = make_sequential(mock_provider, min_interval_seconds=0.0)

        # First call: raises AuthError
        with pytest.raises(AuthError):
            strategy.analyze('content', 'prompt')

        # Second call must complete (proves lock was released)
        result_holder = [None]
        error_holder = [None]

        def second_call():
            try:
                result_holder[0] = strategy.analyze('content', 'prompt')
            except Exception as e:
                error_holder[0] = e

        t = threading.Thread(target=second_call)
        t.start()
        t.join(timeout=2.0)

        assert not t.is_alive(), "Second call is still blocked — deadlock detected"
        assert error_holder[0] is None
        assert result_holder[0] is not None
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k "serial or lock_released" -v
```

Expected: `ImportError: cannot import name 'SequentialThrottleStrategy'`

**Step 3: Write minimal implementation**

Append to `src/analyzers/strategy.py`:

```python
def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception represents an HTTP 429 rate limit response."""
    for attr in ('status_code', 'code'):
        if getattr(exc, attr, None) == 429:
            return True
    class_name = type(exc).__name__
    return any(kw in class_name for kw in ('RateLimit', 'ResourceExhausted', 'TooManyRequests'))


class SequentialThrottleStrategy(RequestStrategy):
    """Serializes LLM API calls and enforces RPM / RPD limits.

    Uses a threading.Lock context manager so the lock is released on
    every exit path — normal return, planned None, caught 429, and
    re-raised exceptions — eliminating deadlock risk.
    """

    def __init__(
        self,
        inner: LLMProvider,
        min_interval_seconds: float = _GEMINI_FREE_MIN_INTERVAL,
        max_requests_per_run: int = 20,
    ):
        super().__init__(inner)
        self._min_interval = min_interval_seconds
        self._max_requests = max_requests_per_run
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0
        self._request_count: int = 0
        self._limit_logged: bool = False

        if max_requests_per_run <= 0:
            logger.warning(
                'llm_strategy_invalid_cap',
                max_requests_per_run=max_requests_per_run,
            )

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        with self._lock:
            return self._analyze_locked(content, prompt)

    def _analyze_locked(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        """Called inside self._lock. All state mutation happens here."""
        now = time.time()  # (A) Start-to-Start: capture on lock acquisition

        # (B) Check run cap
        if self._request_count >= self._max_requests or self._max_requests <= 0:
            if not self._limit_logged:
                logger.warning(
                    'llm_run_limit_reached',
                    request_count=self._request_count,
                    max_requests_per_run=self._max_requests,
                )
                self._limit_logged = True
            return None

        # (C) Enforce minimum interval
        sleep_duration = max(0.0, self._min_interval - (now - self._last_request_time))
        if sleep_duration > 0:
            logger.info(
                'llm_throttle_sleep',
                sleep_seconds=round(sleep_duration, 1),
            )
            time.sleep(sleep_duration)

        # (D) Record start time BEFORE delegation (Start-to-Start)
        self._last_request_time = now

        # (E) Delegate — exception handling differentiates 429 from fatal errors
        try:
            result = self._inner.analyze(content, prompt)
        except Exception as exc:
            if _is_rate_limit_error(exc):
                logger.warning('llm_rate_limit_hit', error=str(exc))
                return None
            raise  # non-429: re-raise; lock released automatically by context manager

        # (F) Count only successful delegations
        self._request_count += 1
        return result
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k "serial or lock_released" -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add src/analyzers/strategy.py tests/unit/test_strategy.py
git commit -m "✨ [FEAT] Add SequentialThrottleStrategy with context manager lock"
```

---

### Task 3.2: Start-to-Start min interval enforcement

**Files:**
- Modify: `tests/unit/test_strategy.py`

*(The implementation is already in place from Task 3.1 — these tests verify its correctness.)*

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_strategy.py`:

```python
import importlib
from unittest.mock import patch, call as mock_call

# ── Interval enforcement ──────────────────────────────────────────────

class TestSequentialThrottleInterval:
    def test_no_sleep_on_first_call(self):
        """First ever call skips sleep (initialized _last_request_time=0.0,
        so elapsed from real Unix time is enormous)."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, min_interval_seconds=12.0)

        with patch('src.analyzers.strategy.time.sleep') as mock_sleep:
            strategy.analyze('content', 'prompt')
        mock_sleep.assert_not_called()

    def test_sleeps_remaining_interval_when_elapsed_is_short(self):
        """If elapsed < min_interval, sleep the remaining duration.

        Scenario: last call at t=1000.0, next call at t=1003.5.
        elapsed = 3.5s, min_interval = 12s → sleep = 8.5s.
        """
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, min_interval_seconds=12.0)

        time_values = iter([1000.0, 1003.5])
        with patch('src.analyzers.strategy.time.sleep') as mock_sleep, \
             patch('src.analyzers.strategy.time.time', side_effect=lambda: next(time_values)):
            strategy.analyze('a', 'p')   # t=1000; last=0 → elapsed=1000>>12 → no sleep; sets last=1000
            mock_sleep.reset_mock()      # focus only on the second call
            strategy.analyze('b', 'p')  # t=1003.5; last=1000 → elapsed=3.5 → sleep=8.5

        mock_sleep.assert_called_once()
        actual_sleep = mock_sleep.call_args.args[0]
        assert actual_sleep == pytest.approx(8.5, abs=0.01)

    def test_no_extra_sleep_when_elapsed_exceeds_interval(self):
        """If elapsed > min_interval, no sleep is added."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, min_interval_seconds=12.0)

        time_values = iter([1000.0, 1100.0])  # 100s elapsed >> 12s
        with patch('src.analyzers.strategy.time.sleep') as mock_sleep, \
             patch('src.analyzers.strategy.time.time', side_effect=lambda: next(time_values)):
            strategy.analyze('a', 'p')
            mock_sleep.reset_mock()
            strategy.analyze('b', 'p')

        mock_sleep.assert_not_called()

    def test_info_log_emitted_before_sleep(self):
        """An INFO log with sleep_seconds is emitted before sleeping."""
        import structlog.testing
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, min_interval_seconds=12.0)

        time_values = iter([1000.0, 1003.5])
        with patch('src.analyzers.strategy.time.sleep'), \
             patch('src.analyzers.strategy.time.time', side_effect=lambda: next(time_values)), \
             structlog.testing.capture_logs() as cap:
            strategy.analyze('a', 'p')
            strategy.analyze('b', 'p')

        throttle_logs = [l for l in cap if l.get('event') == 'llm_throttle_sleep']
        assert len(throttle_logs) == 1
        assert throttle_logs[0]['sleep_seconds'] == pytest.approx(8.5, abs=0.1)
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k interval -v
```

Expected: Tests fail — the interval logic exists but some edge case assertions reveal bugs (or pass if logic is correct from 3.1). If they already pass, that's fine — skip to Step 5.

**Step 3: Implementation already in place**

No changes needed. The interval logic was built in Task 3.1.

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k interval -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tests/unit/test_strategy.py
git commit -m "🧪 [TEST] Add min interval enforcement tests for SequentialThrottleStrategy"
```

---

### Task 3.3: Per-run request cap with one-shot warning

**Files:**
- Modify: `tests/unit/test_strategy.py`

*(Implementation already in place from Task 3.1.)*

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_strategy.py`:

```python
import structlog.testing

# ── Run cap and one-shot warning ──────────────────────────────────────

class TestSequentialThrottleCap:
    def test_calls_within_cap_succeed(self):
        """Calls 1 and 2 delegate to provider when cap=2."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, max_requests_per_run=2)

        r1 = strategy.analyze('a', 'p')
        r2 = strategy.analyze('b', 'p')
        assert r1 is not None
        assert r2 is not None
        assert mock_provider.analyze.call_count == 2

    def test_call_exceeding_cap_returns_none(self):
        """Call 3 returns None without invoking the inner provider when cap=2."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, max_requests_per_run=2)

        strategy.analyze('a', 'p')
        strategy.analyze('b', 'p')
        result = strategy.analyze('c', 'p')  # exceeds cap

        assert result is None
        assert mock_provider.analyze.call_count == 2  # not called on 3rd invocation

    def test_warning_emitted_exactly_once_on_cap_exceeded(self):
        """llm_run_limit_reached WARNING is emitted exactly once, regardless of
        how many subsequent calls hit the cap."""
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = make_result()
        strategy = make_sequential(mock_provider, max_requests_per_run=2)

        with structlog.testing.capture_logs() as cap:
            for _ in range(5):
                strategy.analyze('x', 'p')

        limit_warnings = [
            l for l in cap
            if l.get('event') == 'llm_run_limit_reached' and l.get('log_level') == 'warning'
        ]
        assert len(limit_warnings) == 1, (
            f"Expected exactly 1 llm_run_limit_reached warning, got {len(limit_warnings)}"
        )

    def test_zero_cap_blocks_all_and_logs_at_init(self):
        """max_requests_per_run=0 emits WARNING at construction and blocks all calls."""
        with structlog.testing.capture_logs() as cap:
            strategy = make_sequential(max_requests_per_run=0)

        init_warnings = [
            l for l in cap
            if l.get('event') == 'llm_strategy_invalid_cap' and l.get('log_level') == 'warning'
        ]
        assert len(init_warnings) == 1

        mock_provider = MagicMock()
        strategy._inner = mock_provider
        result = strategy.analyze('x', 'p')
        assert result is None
        mock_provider.analyze.assert_not_called()
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k cap -v
```

Expected: Tests fail or pass depending on whether 3.1 implementation is already complete.

**Step 3: Implementation already in place**

No changes needed.

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k cap -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tests/unit/test_strategy.py
git commit -m "🧪 [TEST] Add per-run cap and one-shot warning tests"
```

---

### Task 3.4: Error differentiation (429 → None vs non-429 → re-raise)

**Files:**
- Modify: `tests/unit/test_strategy.py`

*(Implementation already in place from Task 3.1.)*

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_strategy.py`:

```python
# ── Error differentiation ─────────────────────────────────────────────

class FakeRateLimitError(Exception):
    """Simulates an SDK exception with status_code=429."""
    status_code = 429


class FakeAuthError(Exception):
    """Simulates a permanent auth failure with status_code=401."""
    status_code = 401


class TestSequentialThrottleErrorDifferentiation:
    def test_429_returns_none_without_raising(self):
        """When the inner provider raises a 429, analyze() returns None silently."""
        mock_provider = MagicMock()
        mock_provider.analyze.side_effect = FakeRateLimitError('rate limited')
        strategy = make_sequential(mock_provider, min_interval_seconds=0.0)

        result = strategy.analyze('content', 'prompt')
        assert result is None

    def test_429_updates_last_request_time(self):
        """After a 429, _last_request_time is updated so the next call waits.

        Scenario: 429 at t=1000, next call at t=1003 → should sleep 12-3=9s.
        """
        mock_provider = MagicMock()
        side_effects = [FakeRateLimitError('rate limited'), make_result()]
        mock_provider.analyze.side_effect = side_effects
        strategy = make_sequential(mock_provider, min_interval_seconds=12.0)

        time_values = iter([1000.0, 1003.0])
        with patch('src.analyzers.strategy.time.sleep') as mock_sleep, \
             patch('src.analyzers.strategy.time.time', side_effect=lambda: next(time_values)):
            strategy.analyze('a', 'p')   # 429 at t=1000; sets last=1000
            mock_sleep.reset_mock()
            strategy.analyze('b', 'p')  # t=1003; elapsed=3, sleep=9s

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args.args[0] == pytest.approx(9.0, abs=0.01)

    def test_non_429_exception_propagates(self):
        """When the inner provider raises a non-429 exception, it re-raises."""
        mock_provider = MagicMock()
        mock_provider.analyze.side_effect = FakeAuthError('Unauthorized')
        strategy = make_sequential(mock_provider, min_interval_seconds=0.0)

        with pytest.raises(FakeAuthError):
            strategy.analyze('content', 'prompt')

    def test_non_429_exception_does_not_increment_count(self):
        """A failed (non-429) delegation does not count towards the request cap."""
        mock_provider = MagicMock()
        side_effects = [FakeAuthError('err'), make_result()]
        mock_provider.analyze.side_effect = side_effects
        strategy = make_sequential(mock_provider, min_interval_seconds=0.0, max_requests_per_run=1)

        with pytest.raises(FakeAuthError):
            strategy.analyze('a', 'p')   # raises, count stays 0

        result = strategy.analyze('b', 'p')  # count=0 < 1, delegates
        assert result is not None
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k error -v
```

**Step 3: Implementation already in place**

No changes needed.

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k error -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tests/unit/test_strategy.py
git commit -m "🧪 [TEST] Add error differentiation tests for SequentialThrottleStrategy"
```

---

### Task 3.5: Architecture diagram — Phase 3

**Files:**
- Modify: `docs/architecture/digital-twins-scraper.drawio`

**Step 1:** SKIP
**Step 2:** SKIP

**Step 3:** Open `docs/architecture/digital-twins-scraper.drawio` in draw.io. Navigate to the existing **"Phase 7 - LLM Analyzer"** page. Add `SequentialThrottleStrategy` alongside `UnthrottledStrategy` (from Task 2.3), and add a companion flowchart showing the `_analyze_locked()` control flow:
- Diamond: "count ≥ max?" → Yes → "return None (one-shot warn)"
- Diamond: "elapsed < interval?" → Yes → "log INFO; sleep remaining"
- Box: "set _last_request_time = now (Start-to-Start)"
- Box: "call inner.analyze()"
- Diamond: "429?" → Yes → "return None" / No → "re-raise OR count++ return result"

**Step 4:** Confirm the updated Phase 7 page renders without errors.

**Step 5: Commit**

```bash
git add docs/architecture/digital-twins-scraper.drawio
git commit -m "📐 [DOCS] Update architecture diagram — Phase 3 (SequentialThrottleStrategy)"
```

---

## Phase 4: Factory and Integration

### Task 4.1: Implement `build_strategy()` factory

**Files:**
- Modify: `src/analyzers/strategy.py`
- Modify: `tests/unit/test_strategy.py`

---

**Step 1: Write the failing tests**

Add to `tests/unit/test_strategy.py`:

```python
# ── build_strategy factory ────────────────────────────────────────────

class TestBuildStrategy:
    def _gemini(self):
        from src.analyzers.gemini import GeminiProvider
        return MagicMock(spec=GeminiProvider)

    def _claude(self):
        from src.analyzers.claude import ClaudeProvider
        return MagicMock(spec=ClaudeProvider)

    def test_gemini_free_returns_sequential_throttle(self):
        from src.analyzers.strategy import build_strategy, SequentialThrottleStrategy
        result = build_strategy(self._gemini(), 'free')
        assert isinstance(result, SequentialThrottleStrategy)

    def test_gemini_paid_returns_unthrottled(self):
        from src.analyzers.strategy import build_strategy, UnthrottledStrategy
        result = build_strategy(self._gemini(), 'paid')
        assert isinstance(result, UnthrottledStrategy)

    def test_claude_any_tier_returns_unthrottled(self):
        from src.analyzers.strategy import build_strategy, UnthrottledStrategy
        for tier in ('free', 'paid', 'unknown'):
            result = build_strategy(self._claude(), tier)
            assert isinstance(result, UnthrottledStrategy), f"Failed for tier={tier}"

    def test_unknown_provider_returns_unthrottled(self):
        from src.analyzers.strategy import build_strategy, UnthrottledStrategy
        mystery_provider = MagicMock(spec=LLMProvider)
        result = build_strategy(mystery_provider, 'free')
        assert isinstance(result, UnthrottledStrategy)

    def test_unrecognised_tier_for_gemini_logs_warning_and_falls_back(self):
        """A typo in LLM_API_TIER for Gemini emits WARNING and returns UnthrottledStrategy."""
        from src.analyzers.strategy import build_strategy, UnthrottledStrategy
        with structlog.testing.capture_logs() as cap:
            result = build_strategy(self._gemini(), 'fere')  # typo

        assert isinstance(result, UnthrottledStrategy)
        warnings = [
            l for l in cap
            if l.get('log_level') == 'warning' and l.get('event') == 'llm_strategy_unrecognised_tier'
        ]
        assert len(warnings) == 1
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_strategy.py -k factory -v
```

Expected: `ImportError: cannot import name 'build_strategy'`

**Step 3: Write minimal implementation**

Append to `src/analyzers/strategy.py`:

```python
def build_strategy(provider: LLMProvider, tier: str) -> LLMProvider:
    """Select and construct a request strategy for the given provider and tier.

    The provider name is derived internally from type(provider).__name__,
    so callers do not pass a redundant name argument.

    Args:
        provider: The inner LLMProvider instance to wrap.
        tier: Value of LLM_API_TIER env var ('free' or 'paid').

    Returns:
        An LLMProvider-compatible strategy wrapping the provider.
    """
    # Lazy imports avoid circular import issues at module load time
    from src.analyzers.gemini import GeminiProvider  # noqa: PLC0415
    from src.analyzers.claude import ClaudeProvider  # noqa: PLC0415
    from src import config  # noqa: PLC0415

    if isinstance(provider, GeminiProvider):
        if tier == 'free':
            return SequentialThrottleStrategy(
                inner=provider,
                min_interval_seconds=_GEMINI_FREE_MIN_INTERVAL,
                max_requests_per_run=config.LLM_MAX_REQUESTS_PER_RUN,
            )
        elif tier == 'paid':
            return UnthrottledStrategy(inner=provider)
        else:
            logger.warning(
                'llm_strategy_unrecognised_tier',
                provider=type(provider).__name__,
                tier=tier,
            )
            return UnthrottledStrategy(inner=provider)

    # ClaudeProvider and all unknown providers: unthrottled
    return UnthrottledStrategy(inner=provider)
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_strategy.py -k factory -v
```

Expected: 5 PASSED

**Step 5: Commit**

```bash
git add src/analyzers/strategy.py tests/unit/test_strategy.py
git commit -m "✨ [FEAT] Implement build_strategy factory with provider/tier routing"
```

---

### Task 4.2: Update `build_analyzer()` in `src/analyzers/__init__.py`

**Files:**
- Modify: `src/analyzers/__init__.py`
- Create: `tests/unit/test_analyzers.py`

---

**Step 1: Write the failing tests**

Create `tests/unit/test_analyzers.py`:

```python
import os
import structlog.testing
from unittest.mock import patch, MagicMock


class TestBuildAnalyzer:
    def test_gemini_free_returns_sequential_throttle_strategy(self):
        """build_analyzer() with gemini+free wraps provider in SequentialThrottleStrategy."""
        env = {
            'LLM_PROVIDER': 'gemini',
            'LLM_API_TIER': 'free',
            'LLM_API_KEY': 'test-key',
            'LLM_MODEL': 'gemini-2.0-flash',
        }
        with patch.dict(os.environ, env):
            import importlib
            import src.config as cfg
            importlib.reload(cfg)

            from src.analyzers.strategy import SequentialThrottleStrategy
            with patch('src.analyzers.gemini.GeminiProvider.__init__', return_value=None):
                from src.analyzers import build_analyzer
                result = build_analyzer()

        assert isinstance(result, SequentialThrottleStrategy)

    def test_build_analyzer_emits_info_log_with_strategy_fields(self):
        """build_analyzer() must emit an INFO log with llm_provider, llm_api_tier, strategy."""
        env = {
            'LLM_PROVIDER': 'gemini',
            'LLM_API_TIER': 'free',
            'LLM_API_KEY': 'test-key',
            'LLM_MODEL': 'gemini-2.0-flash',
        }
        with patch.dict(os.environ, env):
            import importlib
            import src.config as cfg
            importlib.reload(cfg)

            with patch('src.analyzers.gemini.GeminiProvider.__init__', return_value=None), \
                 structlog.testing.capture_logs() as cap:
                from src.analyzers import build_analyzer
                build_analyzer()

        selection_logs = [
            l for l in cap
            if l.get('event') == 'llm_strategy_selected' and l.get('log_level') == 'info'
        ]
        assert len(selection_logs) >= 1
        log = selection_logs[-1]
        assert log['llm_provider'] == 'gemini'
        assert log['llm_api_tier'] == 'free'
        assert log['strategy'] == 'SequentialThrottleStrategy'

    def test_claude_returns_unthrottled_strategy(self):
        """build_analyzer() with claude returns an UnthrottledStrategy."""
        env = {
            'LLM_PROVIDER': 'claude',
            'LLM_API_TIER': 'free',
            'LLM_API_KEY': 'sk-test',
            'LLM_MODEL': 'claude-sonnet-4-20250514',
        }
        with patch.dict(os.environ, env):
            import importlib
            import src.config as cfg
            importlib.reload(cfg)

            from src.analyzers.strategy import UnthrottledStrategy
            with patch('src.analyzers.claude.ClaudeProvider.__init__', return_value=None):
                from src.analyzers import build_analyzer
                result = build_analyzer()

        assert isinstance(result, UnthrottledStrategy)
```

**Step 2: Run test to verify it fails**

```
pytest tests/unit/test_analyzers.py -v
```

Expected: `ImportError: cannot import name 'build_analyzer' from 'src.analyzers'`

**Step 3: Write minimal implementation**

Replace the contents of `src/analyzers/__init__.py`:

```python
from src.analyzers.llm_provider import LLMProvider, AnalysisResult
from src.utils.logging import get_logger

logger = get_logger(__name__)


def build_analyzer() -> LLMProvider:
    """Build an LLMProvider wrapped with the appropriate request strategy.

    Reads LLM_PROVIDER and LLM_API_TIER from config to select the provider
    and strategy. Emits an INFO log recording the selection for observability.

    Returns:
        A strategy-wrapped LLMProvider ready for use by ThreadPoolExecutor workers.
    """
    from src import config
    from src.analyzers.strategy import build_strategy

    if config.LLM_PROVIDER == 'gemini':
        from src.analyzers.gemini import GeminiProvider
        provider = GeminiProvider(api_key=config.LLM_API_KEY, model=config.LLM_MODEL)
    else:
        from src.analyzers.claude import ClaudeProvider
        provider = ClaudeProvider(api_key=config.LLM_API_KEY, model=config.LLM_MODEL)

    strategy = build_strategy(provider, config.LLM_API_TIER)

    logger.info(
        'llm_strategy_selected',
        llm_provider=config.LLM_PROVIDER,
        llm_api_tier=config.LLM_API_TIER,
        strategy=type(strategy).__name__,
    )

    return strategy
```

**Step 4: Run test to verify it passes**

```
pytest tests/unit/test_analyzers.py -v
```

Expected: 3 PASSED

Run the full test suite to verify no regressions:

```
pytest tests/ -v --tb=short
```

Expected: All existing tests pass.

**Step 5: Commit**

```bash
git add src/analyzers/__init__.py tests/unit/test_analyzers.py
git commit -m "✨ [FEAT] Integrate build_strategy into build_analyzer with selection log"
```

---

### Task 4.3: Architecture diagram — Phase 4

**Files:**
- Modify: `docs/architecture/digital-twins-scraper.drawio`

**Step 1:** SKIP
**Step 2:** SKIP

**Step 3:** Open `docs/architecture/digital-twins-scraper.drawio` in draw.io. Navigate to the existing **"Phase 8 - Full System Architecture"** page (which shows `ThreadPoolExecutor` → provider). Update the arrow from `ThreadPoolExecutor` workers to route through `SequentialThrottleStrategy` before reaching `GeminiProvider`:
- `ThreadPoolExecutor (3 workers)` → `SequentialThrottleStrategy.analyze()` → `[Lock acquired]` → `GeminiProvider.analyze()` → `[Lock released]`
- Add a startup annotation showing `build_analyzer()` calling `build_strategy(provider, tier)` and returning the strategy-wrapped provider.
- Annotate: "All workers share one strategy instance; lock serializes calls."

**Step 4:** Confirm the updated Phase 8 page renders without errors.

**Step 5: Commit**

```bash
git add docs/architecture/digital-twins-scraper.drawio
git commit -m "📐 [DOCS] Update architecture diagram — Phase 4 (factory and integration)"
```
