## Why

The current implementation uses `ThreadPoolExecutor` (max_workers=3) to analyze articles concurrently, sending multiple LLM API calls simultaneously. When deployed to Railway with `LLM_PROVIDER=gemini` on the Free tier (5 RPM / 250K TPM / 20 RPD), this causes HTTP 429 rate-limit errors that result in ~70% task failure (6/20 articles succeed). There is no mechanism to adapt request behaviour based on the provider or API tier in use.

## What Changes

- Add a new `llm-request-strategy` module under `src/analyzers/` implementing the Strategy pattern
- Introduce `LLM_API_TIER` environment variable (`free` | `paid`) to select the active strategy at runtime
- The strategy is selected by combining `LLM_PROVIDER` + `LLM_API_TIER` (e.g., `gemini:free` → sequential with delay)
- `build_analyzer()` in `src/analyzers/__init__.py` is updated to wrap the chosen `LLMProvider` with the selected strategy
- `src/config.py` is updated to expose `LLM_API_TIER`
- `.env.example` is updated to document the new variable

## Capabilities

### New Capabilities

- `llm-request-strategy`: Strategy pattern that controls how LLM API requests are executed (concurrency, delays, retry behaviour) based on the `LLM_PROVIDER` + `LLM_API_TIER` combination read from environment variables

### Modified Capabilities

*(none — no existing spec-level requirements are changing)*

## Impact

- `src/analyzers/` — new strategy module and updated `build_analyzer()` factory
- `src/config.py` — new `LLM_API_TIER` env var
- `src/main.py` — no direct changes; impact is through `build_analyzer()`
- `.env.example` — documentation update
- No breaking changes to `LLMProvider` ABC or existing provider implementations
