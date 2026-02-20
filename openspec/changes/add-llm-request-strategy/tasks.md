## 1. Config

- [ ] 1.1 Add `LLM_API_TIER` env var to `src/config.py`
  - **Files**: `src/config.py` (modify), `tests/test_config.py` (create)
  - **Step 1**: Write failing tests in `tests/test_config.py` — assert `config.LLM_API_TIER == "free"` when env var is absent, and `"paid"` when `LLM_API_TIER=paid` is set (Spec: *LLM_API_TIER environment variable*)
  - **Step 2**: Verify tests fail with `AttributeError` because `LLM_API_TIER` does not yet exist in `config.py`
  - **Step 3**: Add `LLM_API_TIER: str` to `src/config.py`, reading from the environment with default `"free"`
  - **Step 4**: Run `pytest tests/test_config.py -k api_tier` and confirm all assertions pass
  - **Step 5**: `✨ [FEAT] Add LLM_API_TIER config env var`

- [ ] 1.2 Add `LLM_MAX_REQUESTS_PER_RUN` env var to `src/config.py`
  - **Files**: `src/config.py` (modify), `tests/test_config.py` (modify)
  - **Step 1**: Write failing tests in `tests/test_config.py` — assert `config.LLM_MAX_REQUESTS_PER_RUN == 20` when absent, and `10` when `LLM_MAX_REQUESTS_PER_RUN=10` is set (Spec: *LLM_MAX_REQUESTS_PER_RUN environment variable*)
  - **Step 2**: Verify tests fail with `AttributeError` because the constant does not yet exist
  - **Step 3**: Add `LLM_MAX_REQUESTS_PER_RUN: int` to `src/config.py`, reading from the environment with default `20`
  - **Step 4**: Run `pytest tests/test_config.py -k max_requests` and confirm all assertions pass
  - **Step 5**: `✨ [FEAT] Add LLM_MAX_REQUESTS_PER_RUN config env var`

- [ ] 1.3 Update architecture diagram — Phase 1
  - **Files**: `docs/architecture/digital-twins-scraper.drawio` (modify)
  - **Step 1**: SKIP
  - **Step 2**: SKIP
  - **Step 3**: Add or update the diagram page for Phase 1 (Config) in `docs/architecture/digital-twins-scraper.drawio`, showing the two new env vars feeding into the strategy layer
  - **Step 4**: Open the drawio file and confirm the new page renders correctly
  - **Step 5**: `📐 [DOCS] Update architecture diagram — Phase 1 (config)`

## 2. Strategy Module Foundation

- [ ] 2.1 Create `RequestStrategy` ABC in `src/analyzers/strategy.py`
  - **Files**: `src/analyzers/strategy.py` (create), `tests/test_strategy.py` (create)
  - **Step 1**: Write failing tests in `tests/test_strategy.py` — assert that `RequestStrategy` cannot be instantiated directly and that a concrete subclass without `analyze()` raises `TypeError` (Spec: *RequestStrategy implements the LLMProvider interface*)
  - **Step 2**: Verify tests fail with `ImportError` because `src/analyzers/strategy.py` does not exist
  - **Step 3**: Create `src/analyzers/strategy.py` with a `RequestStrategy` ABC that extends `LLMProvider` and declares `analyze(content, prompt)` as an abstract method
  - **Step 4**: Run `pytest tests/test_strategy.py -k abc` and confirm instantiation and subclass enforcement tests pass
  - **Step 5**: `✨ [FEAT] Add RequestStrategy ABC to strategy module`

- [ ] 2.2 Implement `UnthrottledStrategy`
  - **Files**: `src/analyzers/strategy.py` (modify), `tests/test_strategy.py` (modify)
  - **Step 1**: Write failing tests in `tests/test_strategy.py` — assert that `UnthrottledStrategy.analyze()` returns the inner provider's result unchanged, returns `None` when the inner provider returns `None`, and propagates exceptions without catching them (Spec: *UnthrottledStrategy is a transparent pass-through*)
  - **Step 2**: Verify tests fail with `ImportError` because `UnthrottledStrategy` does not yet exist
  - **Step 3**: Add `UnthrottledStrategy` to `src/analyzers/strategy.py`, delegating `analyze()` directly to the inner provider with no locking, sleeping, or counting
  - **Step 4**: Run `pytest tests/test_strategy.py -k unthrottled` and confirm all pass-through assertions pass
  - **Step 5**: `✨ [FEAT] Implement UnthrottledStrategy pass-through`

- [ ] 2.3 Update architecture diagram — Phase 2
  - **Files**: `docs/architecture/digital-twins-scraper.drawio` (modify)
  - **Step 1**: SKIP
  - **Step 2**: SKIP
  - **Step 3**: Add or update the diagram page for Phase 2 (Strategy foundation) in `docs/architecture/digital-twins-scraper.drawio`, showing `RequestStrategy` ABC and `UnthrottledStrategy` in relation to `LLMProvider`
  - **Step 4**: Open the drawio file and confirm the new page renders correctly
  - **Step 5**: `📐 [DOCS] Update architecture diagram — Phase 2 (strategy foundation)`

## 3. SequentialThrottleStrategy

- [ ] 3.1 Implement thread-safe serialization with context manager lock
  - **Files**: `src/analyzers/strategy.py` (modify), `tests/test_strategy.py` (modify)
  - **Step 1**: Write failing concurrency tests in `tests/test_strategy.py` (Design T2 and T4) — T2: spawn 3 threads with `min_interval_seconds=0.1`, assert wall-clock ≥ 0.2s and < 5s, assert inner provider called exactly 3 times serially; T4 (lock safety): after a 401 exception on call 1, verify call 2 succeeds without hanging (Spec: *SequentialThrottleStrategy serializes concurrent calls*)
  - **Step 2**: Verify tests fail with `ImportError` because `SequentialThrottleStrategy` does not exist
  - **Step 3**: Add `SequentialThrottleStrategy` to `src/analyzers/strategy.py` — constructor accepts `min_interval_seconds` and `max_requests_per_run`; `analyze()` uses `with self._lock:` as its outermost guard so the lock is released on all exit paths including propagated exceptions
  - **Step 4**: Run `pytest tests/test_strategy.py -k "sequential and (concurrency or lock)"` and confirm serialization and lock-release tests pass
  - **Step 5**: `✨ [FEAT] Add SequentialThrottleStrategy with context manager lock`

- [ ] 3.2 Implement Start-to-Start min interval enforcement
  - **Files**: `src/analyzers/strategy.py` (modify), `tests/test_strategy.py` (modify)
  - **Step 1**: Write failing tests in `tests/test_strategy.py` (Design T1) — mock `time.time` to return controlled timestamps; assert `time.sleep` is called with `pytest.approx` of the correct remaining duration; assert no sleep when elapsed already exceeds `min_interval_seconds`; assert INFO log is emitted before any sleep (Spec: *SequentialThrottleStrategy enforces Start-to-Start minimum interval*)
  - **Step 2**: Verify tests fail because interval enforcement and `_last_request_time` tracking are not yet implemented
  - **Step 3**: Add `_last_request_time` state to `SequentialThrottleStrategy`; capture `now = time.time()` at the start of each `analyze()` call; compute `sleep_duration`; emit INFO log before sleeping; set `_last_request_time = now` before delegation (Start-to-Start)
  - **Step 4**: Run `pytest tests/test_strategy.py -k interval` and confirm all timing and logging assertions pass
  - **Step 5**: `✨ [FEAT] Enforce Start-to-Start min interval in SequentialThrottleStrategy`

- [ ] 3.3 Implement per-run request cap with one-shot warning
  - **Files**: `src/analyzers/strategy.py` (modify), `tests/test_strategy.py` (modify)
  - **Step 1**: Write failing tests in `tests/test_strategy.py` (Design T3 and T6) — T3: `max_requests_per_run=2`, 5 sequential calls — assert calls 1–2 delegate and return results, calls 3–5 return `None` without calling inner provider, `event="llm_run_limit_reached"` WARNING emitted exactly once; T6: `max_requests_per_run=0` — assert WARNING at construction and all calls return `None` (Spec: *SequentialThrottleStrategy enforces a per-run request cap*, *SequentialThrottleStrategy rejects invalid run cap at construction*)
  - **Step 2**: Verify tests fail because `_request_count` and `_limit_logged` state do not yet exist
  - **Step 3**: Add `_request_count: int` and `_limit_logged: bool` to `SequentialThrottleStrategy`; add cap check inside the lock before the sleep step; emit `llm_run_limit_reached` WARNING only when `_limit_logged` is `False`, then set it to `True`; increment `_request_count` only on successful delegation; emit construction WARNING and treat all calls as cap-exceeded when `max_requests_per_run <= 0`
  - **Step 4**: Run `pytest tests/test_strategy.py -k cap` and confirm all cap and one-shot-warning assertions pass
  - **Step 5**: `✨ [FEAT] Add per-run cap and one-shot warning to SequentialThrottleStrategy`

- [ ] 3.4 Implement error differentiation (429 → None vs non-429 → re-raise)
  - **Files**: `src/analyzers/strategy.py` (modify), `tests/test_strategy.py` (modify)
  - **Step 1**: Write failing tests in `tests/test_strategy.py` (Design T4 re-raise path and T5) — T5: mock inner provider raises `HTTPError(429)` — assert `None` returned, no exception raised, `_last_request_time` is updated so the next call waits the full interval; T4 re-raise: mock raises `AuthenticationError` — assert the same exception propagates out of `analyze()` (Spec: *SequentialThrottleStrategy differentiates error outcomes*)
  - **Step 2**: Verify tests fail because exception handling is not yet implemented
  - **Step 3**: Inside the `with self._lock:` block in `SequentialThrottleStrategy.analyze()`, wrap the inner provider call in a `try/except`: HTTP 429 → log WARNING, return `None` (lock released by context manager; `_last_request_time` was already set at the start-to-start point before delegation); all other exceptions → re-raise (lock released automatically by context manager)
  - **Step 4**: Run `pytest tests/test_strategy.py -k error` and confirm all error-path assertions pass; verify the hammering test (T5's interval assertion) passes
  - **Step 5**: `✨ [FEAT] Add 429 vs non-429 error differentiation to SequentialThrottleStrategy`

- [ ] 3.5 Update architecture diagram — Phase 3
  - **Files**: `docs/architecture/digital-twins-scraper.drawio` (modify)
  - **Step 1**: SKIP
  - **Step 2**: SKIP
  - **Step 3**: Add or update the diagram page for Phase 3 (SequentialThrottleStrategy) in `docs/architecture/digital-twins-scraper.drawio`, showing the lock, interval, cap, and error-differentiation paths
  - **Step 4**: Open the drawio file and confirm the new page renders correctly
  - **Step 5**: `📐 [DOCS] Update architecture diagram — Phase 3 (SequentialThrottleStrategy)`

## 4. Factory and Integration

- [ ] 4.1 Implement `build_strategy()` factory with routing table
  - **Files**: `src/analyzers/strategy.py` (modify), `tests/test_strategy.py` (modify)
  - **Step 1**: Write failing tests in `tests/test_strategy.py` — assert `build_strategy(GeminiProvider, "free")` returns `SequentialThrottleStrategy`; `build_strategy(GeminiProvider, "paid")` returns `UnthrottledStrategy`; `build_strategy(ClaudeProvider, any)` returns `UnthrottledStrategy`; `build_strategy(GeminiProvider, "fere")` (typo) emits WARNING and returns `UnthrottledStrategy` (Spec: *Strategy factory selects strategy by provider type and tier*)
  - **Step 2**: Verify tests fail because `build_strategy()` does not yet exist
  - **Step 3**: Add `build_strategy(provider: LLMProvider, tier: str) -> LLMProvider` to `src/analyzers/strategy.py`; derive provider name via `type(provider).__name__`; implement routing table using `isinstance` checks; log WARNING for unrecognised tier on known rate-limited providers before returning `UnthrottledStrategy`
  - **Step 4**: Run `pytest tests/test_strategy.py -k factory` and confirm all routing and warning assertions pass
  - **Step 5**: `✨ [FEAT] Implement build_strategy factory with provider/tier routing`

- [ ] 4.2 Update `build_analyzer()` to use `build_strategy()`
  - **Files**: `src/analyzers/__init__.py` (modify), `tests/test_analyzers.py` (create)
  - **Step 1**: Write a failing integration test in `tests/test_analyzers.py` — assert that `build_analyzer()` called with `LLM_PROVIDER=gemini` and `LLM_API_TIER=free` returns a `SequentialThrottleStrategy` instance; assert the INFO log emitted by `build_analyzer()` contains the fields `llm_provider`, `llm_api_tier`, and `strategy` (Spec: *Strategy selection is logged by build_analyzer*, *RequestStrategy implements the LLMProvider interface*)
  - **Step 2**: Verify test fails because `build_analyzer()` does not yet call `build_strategy()`
  - **Step 3**: Update `src/analyzers/__init__.py` — after constructing the provider, call `build_strategy(provider, config.LLM_API_TIER)` and return the result; emit a structured INFO log with fields `llm_provider`, `llm_api_tier`, and `strategy` (the class name of the returned strategy)
  - **Step 4**: Run `pytest tests/test_analyzers.py` and confirm the integration test passes; run `python -m src.main` locally and verify the strategy selection INFO log appears in output
  - **Step 5**: `✨ [FEAT] Integrate build_strategy into build_analyzer with selection log`

- [ ] 4.3 Update architecture diagram — Phase 4
  - **Files**: `docs/architecture/digital-twins-scraper.drawio` (modify)
  - **Step 1**: SKIP
  - **Step 2**: SKIP
  - **Step 3**: Add or update the diagram page for Phase 4 (Factory and integration) in `docs/architecture/digital-twins-scraper.drawio`, showing `build_analyzer()` calling `build_strategy()` and the full request path from `ThreadPoolExecutor` through the strategy layer to the provider
  - **Step 4**: Open the drawio file and confirm the new page renders correctly
  - **Step 5**: `📐 [DOCS] Update architecture diagram — Phase 4 (factory and integration)`
