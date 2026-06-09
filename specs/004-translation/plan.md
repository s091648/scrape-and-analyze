# Implementation Plan: Translation

**Branch**: `004-translation` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-translation/spec.md`

## Summary

The translation capability translates article analysis content (summary, pain points, insights, innovations), article title and content, tag names, and tag group display names/descriptions from English into configured target languages. Three use cases orchestrate the flow: `TranslateArticleUseCase` handles per-article analysis translation with dedup and structured response parsing; `TranslateArticleBodyUseCase` handles per-article title and content translation; `TranslateTagsUseCase` handles batch tag and group translation with positional line-matching. Translation is triggered automatically after tag normalization via `AnalysisCompletedHandler`, and manually via the `make translate` CLI. `ResilientLLMService` provides ordered provider fallback.

The feature is partially brownfield: analysis/tag/group translation is already implemented and work for those parts is to write tests. Article title and content translation is new greenfield work requiring a new ORM model, migration, domain entity, value objects, repository interface, use case, infrastructure implementation, and backend API changes — plus tests for all new code.

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
| III. Test Discipline — Unit tests | ⚠️ Needs work | Unit tests for existing use cases (brownfield) + new `TranslateArticleBodyUseCase`, `ArticleBodyTranslationPrompt`, and response parsing. LLM providers must be mocked; no DB dependency. |
| III. Test Discipline — Integration tests | ⚠️ Needs work | Integration tests for all DB persistence including new `SqlAlchemyArticleTranslationRepository`. Must use `@pytest.mark.integration` with isolated schema and per-test rollback. |
| III. Test Discipline — Docker execution | ✅ Enforced | All acceptance runs use `make test` / `make test-integration`. |
| IV. Docker-First | ✅ Pass | No changes to Docker setup required. |
| V. CI-Only Deployment | ⚠️ Needs work | New Alembic migration required; must be tested locally via `make migrate` before push. CI auto-migration will apply it to production on merge. |
| VI. Observability | ✅ Pass | structlog used throughout; OTel spans on pipeline steps; Sentry active. New `TranslateArticleBodyUseCase` must include structlog calls and OTel span attributes. `TranslationFailedEvent` reused as-is for body translation failures. |
| VII. Code Style | ✅ Pass | Existing code follows PEP 8; uv manages dependencies. New files must follow same conventions. |

**Gate result**: PASS with gaps to close — test coverage (unit + integration), Alembic migration, and new production code implementation.

## Project Structure

### Documentation (this feature)

```text
specs/004-translation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output — updated with ArticleTranslation entity
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── translation-repository.md  # Phase 1 — AnalysesTranslationRepository + TagTranslationRepository + ArticleTranslationRepository
│   └── llm-service-translate.md  # Phase 1 — LLMService.translate() contract (unchanged)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/modules/intelligence/
├── domain/
│   ├── entities/
│   │   ├── analyses_content.py              # AnalysesContent entity (existing)
│   │   └── article_translation.py           # [NEW] ArticleTranslation domain entity
│   ├── value_objects/
│   │   ├── analyses_translation_content.py  # AnalysesTranslationContent + AnalysesTranslationResult (existing)
│   │   │                                    # [EXTEND] Add ArticleBodyTranslationContent + ArticleBodyTranslationResult
│   │   ├── translation_prompt.py            # ArticleTranslationPrompt, TagTranslationPrompt, GroupTranslationPrompt (existing)
│   │   │                                    # [EXTEND] Add ArticleBodyTranslationPrompt
│   │   └── base_prompt.py                   # BasePrompt ABC (existing, unchanged)
│   ├── repositories/
│   │   ├── analyses_translation_repository.py   # AnalysesTranslationRepository ABC (existing, unchanged)
│   │   ├── tag_translation_repository.py        # TagTranslationRepository ABC (existing, unchanged)
│   │   └── article_translation_repository.py    # [NEW] ArticleTranslationRepository ABC
│   └── services/
│       └── llm_service.py                   # LLMService ABC (existing, unchanged)
└── application/
    ├── use_cases/
    │   ├── translate_article.py             # TranslateArticleUseCase (existing, unchanged)
    │   ├── translate_article_body.py        # [NEW] TranslateArticleBodyUseCase (title + content)
    │   └── translate_tags.py                # TranslateTagsUseCase (existing, unchanged)
    ├── event_handlers/
    │   └── analysis_completed_handler.py    # [MODIFY] Add TranslateArticleBodyUseCase call per language
    └── events/
        ├── translation_failed.py            # TranslationFailedEvent (existing, unchanged)
        └── tag_normalization_completed.py   # [MODIFY] Add article_title + article_content fields

src/infrastructure/
├── intelligence/
│   ├── llm/
│   │   └── resilient_llm_service.py        # ResilientLLMService (existing, unchanged)
│   └── prompt/
│       └── prompt_factory.py               # [MODIFY] Register ArticleBodyTranslationPrompt
└── persistence/intelligence/
    ├── analyses_translation_repo_impl.py    # SqlAlchemyAnalysesTranslationRepository (existing, unchanged)
    ├── tag_translation_repo_impl.py         # SqlAlchemyTagTranslationRepository (existing, unchanged)
    └── article_translation_repo_impl.py    # [NEW] SqlAlchemyArticleTranslationRepository

models/
├── analyses_translation.py                 # AnalysesTranslation ORM model (existing, unchanged)
├── tag_translation.py                      # TagsTranslation ORM model (existing, unchanged)
├── tag_group_translation.py                # TagGroupDefinitionsTranslation ORM model (existing, unchanged)
└── article_translation.py                  # [NEW] ArticleTranslation ORM model

alembic/versions/
└── 18_add_article_translation.py           # [NEW] Migration: create articles_translation table

src/entrypoints/cli/
└── translate.py                            # [MODIFY] Add article body batch translation

src/bootstrap.py                            # [MODIFY] Wire TranslateArticleBodyUseCase + ArticleTranslationRepository

backend/schemas/article.py                  # [MODIFY] Add translated_title + translated_content to ArticleDetailOut
backend/routers/articles.py                 # [MODIFY] Query articles_translation by lang and populate response

src/tests/unit/modules/intelligence/application/
├── test_translate_article_use_case.py      # [NEW] Unit tests for analysis translation (brownfield)
├── test_translate_article_body_use_case.py # [NEW] Unit tests for title/content translation (greenfield)
└── test_translate_tags_use_case.py         # [NEW] Unit tests for tag/group translation (brownfield)

src/tests/unit/modules/intelligence/domain/
└── test_translation_prompt.py              # [NEW] Unit tests for prompt rendering + parsing (brownfield + greenfield)

src/tests/integration/intelligence/
├── test_translate_article_integration.py   # [NEW] DB integration tests for analysis translation (brownfield)
├── test_translate_article_body_integration.py # [NEW] DB integration tests for title/content translation (greenfield)
└── test_translate_tags_integration.py      # [NEW] Tag/group translation DB integration tests (brownfield)
```

**Structure Decision**: Backend-only feature; follows the existing hexagonal/DDD directory convention. Brownfield parts (analysis/tag/group translation) require only test files. Greenfield part (article title/content translation) requires new production code across all DDD layers plus tests.

## Complexity Tracking

**Article title/content carried in `TagNormalizationCompletedEvent`**: The event now carries `article_title` and `article_content` in addition to `analysis_id` and `article_id`. This avoids adding a read-only `ArticleRepository` interface to the intelligence domain (which would be a cross-domain dependency). The event fields are populated by `NormalizeTagsUseCase` which already has `article_id` and can fetch title + content from the Article table at publish time. Trade-off: the event is slightly fatter but eliminates an otherwise unnecessary domain interface.
