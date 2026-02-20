## ADDED Requirements

---

### Requirement: LLM_API_TIER environment variable

`src/config.py` MUST expose a `LLM_API_TIER` constant read from the `LLM_API_TIER` environment variable. Accepted values are `"free"` and `"paid"`. When the variable is absent, `LLM_API_TIER` MUST default to `"free"`.

**Acceptance Criteria:**
- `LLM_API_TIER` equals `"free"` when the environment variable is absent
- `LLM_API_TIER` equals `"free"` when `LLM_API_TIER=free` is set
- `LLM_API_TIER` equals `"paid"` when `LLM_API_TIER=paid` is set

#### Scenario: Default tier when variable is absent
- **WHEN** `LLM_API_TIER` is not present in the environment
- **THEN** `config.LLM_API_TIER` returns `"free"`

#### Scenario: Explicit paid tier
- **WHEN** the environment contains `LLM_API_TIER=paid`
- **THEN** `config.LLM_API_TIER` returns `"paid"`

---

### Requirement: LLM_MAX_REQUESTS_PER_RUN environment variable

`src/config.py` MUST expose a `LLM_MAX_REQUESTS_PER_RUN` constant as an integer read from the `LLM_MAX_REQUESTS_PER_RUN` environment variable. When the variable is absent, `LLM_MAX_REQUESTS_PER_RUN` MUST default to `20`.

**Acceptance Criteria:**
- `LLM_MAX_REQUESTS_PER_RUN` equals `20` when the environment variable is absent
- `LLM_MAX_REQUESTS_PER_RUN` reflects the integer value of the env var when set

#### Scenario: Default cap when variable is absent
- **WHEN** `LLM_MAX_REQUESTS_PER_RUN` is not present in the environment
- **THEN** `config.LLM_MAX_REQUESTS_PER_RUN` returns `20`

#### Scenario: Custom cap is applied
- **WHEN** the environment contains `LLM_MAX_REQUESTS_PER_RUN=10`
- **THEN** `config.LLM_MAX_REQUESTS_PER_RUN` returns `10`

---

### Requirement: Strategy factory selects strategy by provider type and tier

`build_strategy(provider, tier)` in `src/analyzers/strategy.py` MUST return an object implementing the `LLMProvider` interface. The concrete strategy MUST be determined by the runtime type of `provider` and the value of `tier`. The provider name MUST be derived internally from `type(provider).__name__`; callers MUST NOT pass a separate provider-name argument.

**Mapping:**
| Provider type | tier | Strategy returned |
|---|---|---|
| `GeminiProvider` | `"free"` | `SequentialThrottleStrategy` |
| `GeminiProvider` | `"paid"` | `UnthrottledStrategy` |
| `ClaudeProvider` | any | `UnthrottledStrategy` |
| any other | any | `UnthrottledStrategy` |

When the provider is a known rate-limited type (e.g., `GeminiProvider`) but the tier value is not a recognised string, `build_strategy` MUST log a WARNING before returning `UnthrottledStrategy`.

**Acceptance Criteria:**
- `GeminiProvider` + `"free"` → `SequentialThrottleStrategy` instance is returned
- `GeminiProvider` + `"paid"` → `UnthrottledStrategy` instance is returned
- `ClaudeProvider` + any tier → `UnthrottledStrategy` instance is returned
- Unrecognised tier for a rate-limited provider → WARNING logged; `UnthrottledStrategy` returned
- The returned object exposes `analyze(content, prompt)` in all cases

#### Scenario: Gemini Free selects sequential throttle
- **WHEN** `build_strategy` is called with a `GeminiProvider` instance and `tier="free"`
- **THEN** the returned object is an instance of `SequentialThrottleStrategy`

#### Scenario: Gemini Paid selects unthrottled
- **WHEN** `build_strategy` is called with a `GeminiProvider` instance and `tier="paid"`
- **THEN** the returned object is an instance of `UnthrottledStrategy`

#### Scenario: Claude selects unthrottled regardless of tier
- **WHEN** `build_strategy` is called with a `ClaudeProvider` instance and any `tier` value
- **THEN** the returned object is an instance of `UnthrottledStrategy`

#### Scenario: Unrecognised tier on rate-limited provider logs warning
- **WHEN** `build_strategy` is called with a `GeminiProvider` instance and `tier="fere"` (typo)
- **THEN** a WARNING log entry is emitted and an `UnthrottledStrategy` is returned

---

### Requirement: RequestStrategy implements the LLMProvider interface

Every `RequestStrategy` implementation MUST expose `analyze(content: str, prompt: str) -> Optional[AnalysisResult]` with the same signature as `LLMProvider.analyze()`. A strategy instance MUST be substitutable anywhere an `LLMProvider` is accepted without type errors.

**Acceptance Criteria:**
- A strategy-wrapped provider can be passed to `analyze_article()` in `src/main.py` without modification
- `analyze()` returns `Optional[AnalysisResult]` under all non-exceptional conditions

#### Scenario: Strategy is substitutable for a bare provider
- **WHEN** a strategy-wrapped `GeminiProvider` is passed to `analyze_article()` in `src/main.py`
- **THEN** `analyze_article()` behaves identically to when a bare provider is passed

---

### Requirement: SequentialThrottleStrategy serializes concurrent calls

`SequentialThrottleStrategy` MUST ensure that at most one call to the inner provider's `analyze()` is in-flight at any given time. Concurrent calls from multiple threads MUST be queued and executed one at a time. The serialization mechanism MUST use a `with self._lock:` context manager so that the lock is guaranteed to be released on every exit path, including propagated exceptions.

**Acceptance Criteria:**
- No two inner provider calls overlap in time when multiple threads call `strategy.analyze()` concurrently
- The lock is released even when a non-429 exception propagates out of `analyze()`

#### Scenario: Concurrent calls execute one at a time
- **WHEN** three threads call `strategy.analyze()` simultaneously
- **THEN** the inner provider's `analyze()` is called three times, each starting only after the previous completes

#### Scenario: Lock released after non-429 exception
- **WHEN** the inner provider raises an `AuthenticationError` on the first call
- **THEN** a subsequent call to `strategy.analyze()` on the same instance succeeds without hanging (proving the lock was released)

---

### Requirement: SequentialThrottleStrategy enforces Start-to-Start minimum interval

`SequentialThrottleStrategy` MUST enforce a minimum elapsed time between the **start** of consecutive inner provider calls (Start-to-Start timing). The interval MUST be configurable via a `min_interval_seconds` constructor parameter; the default for Gemini Free (5 RPM) is `12.0` seconds. If less than `min_interval_seconds` has elapsed since the recorded start of the last call, the strategy MUST sleep for the remaining time before delegating.

**Acceptance Criteria:**
- The elapsed time between the recorded start of one inner provider call and the start of the next MUST NOT be less than `min_interval_seconds`
- If the natural elapsed time already exceeds `min_interval_seconds`, no additional sleep is introduced
- A log entry at INFO level MUST be emitted before sleeping, stating the sleep duration in seconds

#### Scenario: Rapid successive calls are delayed
- **WHEN** a second call arrives immediately after a first call's start time
- **THEN** the strategy sleeps approximately `min_interval_seconds - elapsed` before delegating the second call

#### Scenario: Slow calls do not incur extra delay
- **WHEN** the time since the last call's start already exceeds `min_interval_seconds`
- **THEN** the next call proceeds immediately without additional waiting

#### Scenario: Sleep duration is logged before sleeping
- **WHEN** the strategy determines a sleep of `8.5s` is required
- **THEN** an INFO log entry is emitted with the message indicating `8.5s` sleep before the sleep occurs

---

### Requirement: SequentialThrottleStrategy enforces a per-run request cap

`SequentialThrottleStrategy` MUST track the number of successfully delegated calls for the lifetime of the strategy instance. Once the count reaches `max_requests_per_run`, all subsequent `analyze()` calls MUST return `None` immediately without invoking the inner provider. A WARNING log with `event="llm_run_limit_reached"` MUST be emitted exactly once per process lifetime when the cap is first reached; subsequent cap-exceeded calls MUST NOT emit additional warnings.

**Acceptance Criteria:**
- After `max_requests_per_run` successful delegations, every subsequent `analyze()` returns `None` without calling the inner provider
- The `event="llm_run_limit_reached"` WARNING is emitted exactly once, on the first call that exceeds the cap
- Calls before the cap is reached delegate normally and return the inner provider's result

#### Scenario: Requests within the cap are delegated
- **WHEN** `request_count < max_requests_per_run`
- **THEN** `analyze()` delegates to the inner provider and returns its result

#### Scenario: First request exceeding the cap returns None and logs once
- **WHEN** `analyze()` is called and `request_count` equals `max_requests_per_run` for the first time
- **THEN** `None` is returned, the inner provider is NOT called, and `event="llm_run_limit_reached"` WARNING is emitted

#### Scenario: Subsequent cap-exceeded requests do not repeat the warning
- **WHEN** `analyze()` is called multiple times after the cap is reached
- **THEN** each call returns `None` and no additional `llm_run_limit_reached` log entries are emitted

---

### Requirement: SequentialThrottleStrategy differentiates error outcomes

`SequentialThrottleStrategy` MUST distinguish between transient rate-limit failures and permanent provider errors:
- When the inner provider raises an HTTP 429 error, `analyze()` MUST return `None` without propagating the exception, and MUST update `_last_request_time` to the current timestamp to prevent immediate re-attempts by waiting threads.
- When the inner provider raises any other exception, `analyze()` MUST re-raise it unchanged so that permanent errors (e.g., `401 Unauthorized`, invalid model) surface to the caller.

**Acceptance Criteria:**
- Inner provider raises HTTP 429 → `analyze()` returns `None`; `_last_request_time` is updated; no exception is raised
- Inner provider raises non-429 exception → the same exception is raised by `analyze()`; `None` is never returned in this case

#### Scenario: 429 returns None and updates timestamp
- **WHEN** the inner provider raises an HTTP 429 exception
- **THEN** `analyze()` returns `None`, does not raise, and the next waiting thread respects the full `min_interval_seconds` before attempting

#### Scenario: Non-429 exception propagates
- **WHEN** the inner provider raises an `AuthenticationError` (HTTP 401)
- **THEN** `analyze()` raises the same `AuthenticationError`; it does NOT return `None`

---

### Requirement: SequentialThrottleStrategy is thread-safe

A single `SequentialThrottleStrategy` instance MUST be safe to share across multiple threads. All access to `_request_count`, `_last_request_time`, and `_limit_logged` MUST be guarded so that no race conditions occur.

**Acceptance Criteria:**
- A single instance shared across N concurrent threads MUST produce at most `max_requests_per_run` inner provider calls in total, never more
- No `RuntimeError` or data corruption occurs under concurrent access

#### Scenario: Shared instance does not exceed run cap under concurrency
- **WHEN** 5 threads concurrently call `analyze()` on the same instance with `max_requests_per_run=3`
- **THEN** the inner provider is called exactly 3 times and the remaining 2 calls return `None`

---

### Requirement: SequentialThrottleStrategy rejects invalid run cap at construction

If `max_requests_per_run <= 0`, `SequentialThrottleStrategy` MUST log a WARNING at construction time identifying the invalid value. Every subsequent call to `analyze()` MUST return `None` immediately without invoking the inner provider.

**Acceptance Criteria:**
- A WARNING log is emitted during construction when `max_requests_per_run <= 0`
- Every `analyze()` call on an instance with `max_requests_per_run <= 0` returns `None`
- The inner provider is never invoked when `max_requests_per_run <= 0`

#### Scenario: Zero cap blocks all requests and logs at init
- **WHEN** `SequentialThrottleStrategy` is constructed with `max_requests_per_run=0`
- **THEN** a WARNING is logged at construction, and every `analyze()` call returns `None`

---

### Requirement: UnthrottledStrategy is a transparent pass-through

`UnthrottledStrategy` MUST delegate every `analyze()` call directly to the inner provider with no added latency, no blocking, and no request counting. Its return value MUST equal the inner provider's return value, and any exception raised by the inner provider MUST propagate unchanged.

**Acceptance Criteria:**
- `UnthrottledStrategy.analyze()` return value equals the inner provider's return value for the same inputs
- No `time.sleep()` or locking occurs inside `UnthrottledStrategy.analyze()`
- N calls to `UnthrottledStrategy.analyze()` result in exactly N calls to the inner provider
- Exceptions from the inner provider propagate unchanged

#### Scenario: Pass-through returns provider result unchanged
- **WHEN** the inner provider returns a valid `AnalysisResult`
- **THEN** `UnthrottledStrategy.analyze()` returns the same `AnalysisResult`

#### Scenario: Pass-through propagates None
- **WHEN** the inner provider returns `None`
- **THEN** `UnthrottledStrategy.analyze()` returns `None`

#### Scenario: Pass-through propagates exceptions
- **WHEN** the inner provider raises an exception
- **THEN** `UnthrottledStrategy.analyze()` raises the same exception

---

### Requirement: Strategy selection is logged by build_analyzer

`build_analyzer()` in `src/analyzers/__init__.py` MUST emit a structured log entry at INFO level each time it is called, recording the selected provider and strategy.

**Acceptance Criteria:**
- The log entry contains the fields `llm_provider`, `llm_api_tier`, and `strategy` with non-empty string values
- The log entry is emitted at INFO level on every `build_analyzer()` invocation

#### Scenario: Strategy selection is observable in logs
- **WHEN** `build_analyzer()` is called with `LLM_PROVIDER=gemini` and `LLM_API_TIER=free`
- **THEN** a log entry is emitted with `llm_provider="gemini"`, `llm_api_tier="free"`, `strategy="SequentialThrottleStrategy"`
