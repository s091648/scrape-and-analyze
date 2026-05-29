# Implementation Plan: LLM Article Analysis

**Branch**: `003-llm-analysis` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-llm-analysis/spec.md`

## Summary

The LLM analysis capability analyzes scraped articles by sending their content to a configured LLM provider and persisting the structured result (summary, pain points, insights, innovations, tag groups). `AnalyzeArticleUseCase` orchestrates the flow; `ResilientLLMService` provides ordered provider fallback with per-provider sliding-window rate limiting via `SlidingWindowStrategy`. The feature is already implemented; work for this spec is to write tests that verify each scenario in the specification is correctly covered.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: SQLAlchemy 2.0, anthropic SDK, google-genai SDK, httpx (OpenRouter), structlog, OpenTelemetry, pgvector

**Storage**: PostgreSQL 15 + pgvector extension — `analyses` and `analyses_translation` tables; `llm_providers` table for runtime provider configuration

**Testing**: pytest + pytest-cov; `@pytest.mark.integration` for DB-dependent tests; `make test` (Docker) for unit, `make test-integration` for integration

**Target Platform**: Linux server (Docker); single-process scraper pipeline

**Project Type**: Backend pipeline service (scraper/analyzer)

**Performance Goals**: ≥95% of analyses succeed per pipeline run; fallback to secondary provider completes within 2× normal latency

**Constraints**: Single-threaded rate-limit state (in-process only); ArXiv content capped at 15,000 chars; no concurrent analysis of the same article; tag group embedding is optional

**Scale/Scope**: ~100–500 articles per pipeline run; up to 3 concurrent LLM provider configurations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD — Layer separation | ✅ Pass | `LLMService` ABC in domain; `AnalyzeArticleUseCase` in application; `ResilientLLMService` + providers in infrastructure. No infrastructure imports in domain or application layers. |
| I. DDD — Composition root | ✅ Pass | `build_llm_service()` in `src/bootstrap.py` wires all dependencies manually. |
| II. Atomic Frontend | N/A | Feature is backend-only; no UI components. |
| III. Test Discipline — Unit tests | ⚠️ Needs work | Unit tests for `AnalyzeArticleUseCase`, `ResilientLLMService`, and `SlidingWindowStrategy` must not require a running database. LLM providers must be mocked. |
| III. Test Discipline — Integration tests | ⚠️ Needs work | Integration tests for `AnalyzeArticleUseCase.execute()` + DB persistence must use `@pytest.mark.integration` with isolated schema and per-test rollback. |
| III. Test Discipline — Docker execution | ✅ Enforced | All acceptance runs use `make test` / `make test-integration`. |
| IV. Docker-First | ✅ Pass | No changes to Docker setup required. |
| V. CI-Only Deployment | ✅ Pass | No deploy changes needed. |
| VI. Observability | ✅ Pass | structlog used throughout; OTel spans on analysis pipeline steps; Sentry active. New test code must not suppress structlog output. |
| VII. Code Style | ✅ Pass | Existing code follows PEP 8; uv manages dependencies. |

**Gate result**: PASS with two test-discipline gaps to close (unit + integration test coverage).

## Project Structure

### Documentation (this feature)

```text
specs/003-llm-analysis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── llm-service.md   # Phase 1 output — LLMService interface contract
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/modules/intelligence/
├── domain/
│   ├── entities/
│   │   └── analysis.py                  # Analysis entity + AnalysisResult
│   ├── value_objects/
│   │   ├── analysis_prompt.py           # AnalysisPrompt (render_auto/fixed/semi)
│   │   └── analysis_content.py          # AnalysisContent, AnalysisMetadata, AnalysisTagGroup
│   └── services/
│       └── llm_service.py               # LLMService ABC (analyze + translate)
└── application/
    └── use_cases/
        └── analyze_article.py           # AnalyzeArticleUseCase

src/infrastructure/intelligence/
└── llm/
    ├── resilient_llm_service.py         # ResilientLLMService + ProviderHandler
    ├── rate_limit/
    │   ├── sliding_window_strategy.py   # SlidingWindowStrategy
    │   └── noop_strategy.py             # NoOpStrategy
    └── providers/
        ├── base_provider.py             # BaseProvider (retry + validation)
        ├── claude_provider.py
        ├── gemini_provider.py
        └── openrouter_provider.py

src/infrastructure/persistence/intelligence/
└── analysis_repo_impl.py               # SqlAlchemyAnalysisRepository

models/
├── analysis.py                         # Analysis ORM model
├── analyses_translation.py             # AnalysisTranslation ORM model
└── llm_provider.py                     # LLMProvider ORM model

src/tests/unit/modules/intelligence/application/
└── test_analyze_article_use_case.py    # [NEW] Unit tests for use case

src/tests/unit/infrastructure/intelligence/llm/
├── test_resilient_llm_service.py       # [NEW] Fallback + reorder tests
├── test_sliding_window_strategy.py     # [NEW] Rate-limit window tests
└── providers/
    ├── test_base_provider.py           # [NEW] Retry + validation tests
    ├── test_claude_provider.py         # [NEW] Claude-specific tests
    ├── test_gemini_provider.py         # [NEW] Gemini quota detection tests
    └── test_openrouter_provider.py     # [NEW] OpenRouter HTTP tests

src/tests/integration/intelligence/
└── test_analyze_article_integration.py # [NEW] End-to-end DB integration tests
```

**Structure Decision**: Backend-only feature; follows the existing hexagonal/DDD directory convention. All new files are test files — no production code changes are required.

## Complexity Tracking

*No constitution violations requiring justification.*
