# Implementation Plan: Translation

**Branch**: `004-translation` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-translation/spec.md`

## Summary

The translation capability translates article analysis content (summary, pain points, insights, innovations), tag names, and tag group display names/descriptions from English into configured target languages. Two use cases orchestrate the flow: `TranslateArticleUseCase` handles per-article analysis translation with dedup and structured response parsing; `TranslateTagsUseCase` handles batch tag and group translation with positional line-matching. Translation is triggered automatically after tag normalization via `AnalysisCompletedHandler`, and manually via the `make translate` CLI. `ResilientLLMService` provides ordered provider fallback. The feature is already implemented; work for this spec is to write tests that verify each scenario is correctly covered.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: SQLAlchemy 2.0, anthropic SDK, google-genai SDK, httpx (OpenRouter), structlog, OpenTelemetry

**Storage**: PostgreSQL 15 — `analyses_translation`, `tags_translation`, `tag_group_definitions_translation` tables; `failed_tasks` table for failure persistence

**Testing**: pytest + pytest-cov; `@pytest.mark.integration` for DB-dependent tests; `make test` (Docker) for unit, `make test-integration` for integration

**Target Platform**: Linux server (Docker); single-process scraper pipeline

**Project Type**: Backend pipeline service (scraper/analyzer)

**Performance Goals**: Translation for each language completes within the same pipeline run as analysis; fallback to secondary provider completes within 2× normal latency

**Constraints**: Single-threaded rate-limit state (in-process only); tag/group batch limit of 50 during auto-triggered flow; CLI uses same limit for articles, tags, and groups; no concurrent translation of the same analysis+language pair

**Scale/Scope**: ~100–500 articles per pipeline run; 1–7 configured target languages; up to 3 concurrent LLM provider configurations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD — Layer separation | ✅ Pass | `LLMService` ABC in domain; `TranslateArticleUseCase` and `TranslateTagsUseCase` in application; `ResilientLLMService` + providers in infrastructure. `AnalysesTranslationRepository` and `TagTranslationRepository` ABCs in domain; SQLAlchemy impls in infrastructure. No infrastructure imports in domain or application layers. |
| I. DDD — Composition root | ✅ Pass | `build_translation_pipeline()` and `build_collection_pipeline()` in `src/bootstrap.py` wire all dependencies manually. |
| II. Atomic Frontend | N/A | Feature is backend-only; no UI components. |
| III. Test Discipline — Unit tests | ⚠️ Needs work | Unit tests for `TranslateArticleUseCase`, `TranslateTagsUseCase`, prompt rendering, and response parsing must not require a running database. LLM providers must be mocked. |
| III. Test Discipline — Integration tests | ⚠️ Needs work | Integration tests for translation + DB persistence must use `@pytest.mark.integration` with isolated schema and per-test rollback. |
| III. Test Discipline — Docker execution | ✅ Enforced | All acceptance runs use `make test` / `make test-integration`. |
| IV. Docker-First | ✅ Pass | No changes to Docker setup required. |
| V. CI-Only Deployment | ✅ Pass | No deploy changes needed. |
| VI. Observability | ✅ Pass | structlog used throughout; OTel spans on pipeline steps; Sentry active. `TranslationFailedEvent` flows to `FailedTaskPersistenceHandler`. New test code must not suppress structlog output. |
| VII. Code Style | ✅ Pass | Existing code follows PEP 8; uv manages dependencies. |

**Gate result**: PASS with two test-discipline gaps to close (unit + integration test coverage).

## Project Structure

### Documentation (this feature)

```text
specs/004-translation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── translation-repository.md  # Phase 1 — AnalysesTranslationRepository + TagTranslationRepository
│   └── llm-service-translate.md  # Phase 1 — LLMService.translate() contract
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/modules/intelligence/
├── domain/
│   ├── entities/
│   │   └── analyses_content.py           # AnalysesContent entity (translation persistence)
│   ├── value_objects/
│   │   ├── analyses_translation_content.py # AnalysesTranslationContent + AnalysesTranslationResult
│   │   ├── translation_prompt.py          # ArticleTranslationPrompt, TagTranslationPrompt, GroupTranslationPrompt
│   │   └── base_prompt.py                 # BasePrompt ABC
│   ├── repositories/
│   │   ├── analyses_translation_repository.py  # AnalysesTranslationRepository ABC
│   │   └── tag_translation_repository.py       # TagTranslationRepository ABC
│   └── services/
│       └── llm_service.py                # LLMService ABC (analyze + translate)
└── application/
    ├── use_cases/
    │   ├── translate_article.py           # TranslateArticleUseCase
    │   └── translate_tags.py              # TranslateTagsUseCase (tags + groups)
    ├── event_handlers/
    │   └── analysis_completed_handler.py  # AnalysisCompletedHandler (auto-trigger)
    └── events/
        ├── translation_failed.py          # TranslationFailedEvent
        └── tag_normalization_completed.py # TagNormalizationCompletedEvent (triggers translation)

src/infrastructure/
├── intelligence/
│   ├── llm/
│   │   └── resilient_llm_service.py       # ResilientLLMService.translate()
│   └── prompt/
│       └── prompt_factory.py              # ConcretePromptFactory
└── persistence/intelligence/
    ├── analyses_translation_repo_impl.py   # SqlAlchemyAnalysesTranslationRepository
    └── tag_translation_repo_impl.py       # SqlAlchemyTagTranslationRepository

models/
├── analyses_translation.py                # AnalysesTranslation ORM model
├── tag_translation.py                     # TagsTranslation ORM model
└── tag_group_translation.py               # TagGroupDefinitionsTranslation ORM model

src/entrypoints/cli/
└── translate.py                           # CLI entry point (make translate)

src/tests/unit/modules/intelligence/application/
├── test_translate_article_use_case.py     # [NEW] Unit tests for article translation
└── test_translate_tags_use_case.py        # [NEW] Unit tests for tag/group translation

src/tests/unit/modules/intelligence/domain/
└── test_translation_prompt.py             # [NEW] Unit tests for prompt rendering + parsing

src/tests/integration/intelligence/
└── test_translate_article_integration.py  # [NEW] End-to-end DB integration tests

src/tests/integration/intelligence/
└── test_translate_tags_integration.py    # [NEW] Tag/group translation DB integration tests
```

**Structure Decision**: Backend-only feature; follows the existing hexagonal/DDD directory convention. All new files are test files — no production code changes are required.

## Complexity Tracking

*No constitution violations requiring justification.*
