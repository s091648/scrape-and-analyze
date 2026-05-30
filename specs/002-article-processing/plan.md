# Implementation Plan: Article Processing

**Branch**: `002-article-processing` | **Date**: 2026-05-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-article-processing/spec.md`

## Summary

Verify and close test coverage gaps for the article-processing capability: URL-based deduplication (`DedupService`), three-outcome processing logic (`ProcessScrapedArticleUseCase`), ArXiv metadata persistence, and event-driven orchestration (`ArticleScrapedHandler`). All production code already exists; this plan focuses on confirming spec scenarios are fully exercised by the test suite.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: SQLAlchemy ≥2.0, pytest, pytest-asyncio, structlog

**Storage**: PostgreSQL 15 (via SQLAlchemy ORM). `Article` and `ArxivMetadata` are separate tables; join is via `article_id` FK.

**Testing**: pytest inside Docker (`make test` for unit, `make test-integration` for integration). All test runs MUST use Docker targets.

**Target Platform**: Linux server (Docker container, `app` / `job_service` services)

**Project Type**: Scraper pipeline service — DDD/hexagonal, event-driven

**Performance Goals**: No specific throughput targets for this capability. Processing is per-article and I/O-bound.

**Constraints**: Strict DDD layer separation. `DedupService` must remain in domain layer. `ProcessScrapedArticleUseCase` must remain in application layer. No infrastructure imports in domain or application layers.

**Scale/Scope**: ~100–500 articles per pipeline run. Processing is sequential per article within the handler.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD Layer Separation | ✅ Pass | `DedupService` is in `domain/services/`. `ProcessScrapedArticleUseCase` is in `application/use_cases/`. `ArticleScrapedHandler` is in `application/event_handlers/`. No layer violations detected. |
| II. Atomic Frontend | ✅ N/A | This capability has no frontend surface. |
| III. Test Discipline | ✅ Pass | Unit tests do not require DB. Integration tests use `@pytest.mark.integration` with isolated schema + per-test rollback. Test runs via `make test` / `make test-integration`. |
| IV. Docker-First Dev | ✅ Pass | Tests run via Makefile Docker targets. No bare-metal execution. |
| V. CI Deployment | ✅ Pass | No deployment changes in this plan. |
| VI. Observability | ✅ Pass | `ProcessScrapedArticleUseCase` already logs via structlog at INFO/ERROR/WARNING levels. |
| VII. Code Style | ✅ Pass | PEP 8 compliant. No TODO comments. `uv` for dependency management. |

No violations. Complexity Tracking section not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-article-processing/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code (this capability)

```text
src/modules/collection/
├── domain/
│   ├── services/
│   │   └── dedup_service.py          ← DedupService (domain logic)
│   └── value_objects/
│       └── url.py                     ← UrlHash value object
├── application/
│   ├── use_cases/
│   │   ├── process_scraped_article.py ← ProcessScrapedArticleUseCase
│   │   └── article_outcome.py         ← ArticleOutcome enum
│   ├── event_handlers/
│   │   └── article_scraped_handler.py ← ArticleScrapedHandler
│   └── events/
│       └── article_scraped.py         ← ArticleScrapedEvent
└── domain/
    ├── entities/
    │   └── arxiv_metadata.py          ← ArxivMetadata entity
    └── repositories/
        └── arxiv_metadata_repository.py ← ArxivMetadataRepository ABC

src/shared/
├── domain/entities/
│   └── article.py                     ← Article entity
└── application/events/
    └── article_processed.py           ← ArticleProcessedEvent

src/tests/
├── unit/modules/collection/application/
│   ├── test_article_scraped_handler.py           ← Exists (3 cases)
│   └── test_process_article_topic_and_metadata.py ← Exists (topic/metadata)
└── integration/
    └── test_process_article.py                   ← Exists (5 integration cases)
```

**Structure Decision**: Single Python project. Tests mirror `src/` under `src/tests/unit/` and `src/tests/integration/`.

## Phase 0: Research

*All technical questions are resolved by reading the existing codebase. No external research needed.*

### Findings

| Question | Decision | Rationale |
|----------|----------|-----------|
| Does `DedupService` have dedicated unit tests? | **No** — only covered indirectly via integration tests | `src/tests/unit/modules/collection/` has no `test_dedup_service.py` |
| Does `ProcessScrapedArticleUseCase` have dedicated unit tests? | **No** — only `test_process_article_topic_and_metadata.py` which tests partial behavior | The 3-outcome flow (NEW / DUPLICATE / DUPLICATE_NEEDS_ANALYSIS) is only tested at the integration level |
| Is ArXiv metadata persistence tested? | **No** — `ProcessScrapedArticleUseCase` wires `arxiv_metadata_repo=None` in the integration test `_wire_pipeline` | The `_save_arxiv_metadata` path is not exercised in existing tests |
| Is the `DUPLICATE_NEEDS_ANALYSIS` + ArXiv section enrichment path tested? | **No** — the integration test for this outcome (`test_process_article_analyzes_duplicate_missing_analysis`) doesn't verify section data merging | Gap in FR-007 coverage |
| Is `ArticleScrapedHandler` coverage sufficient? | **Partial** — the 3 outcome-routing cases exist but `DUPLICATE_NEEDS_ANALYSIS` outcome is missing from unit tests | Unit test covers NEW, DUPLICATE, FAILED; missing DUPLICATE_NEEDS_ANALYSIS |

### Coverage Gap Summary

| Spec Scenario | Existing Coverage | Gap |
|---------------|-------------------|-----|
| US1-AC1: New article saved + event published | ✅ Integration `test_process_article_creates_article_and_analysis` | None |
| US1-AC2: ArXiv metadata persisted | ❌ Not tested | Unit + integration tests needed |
| US1-AC3: Save failure → no event published | ❌ Not tested at unit level | Unit test for `ProcessScrapedArticleUseCase` needed |
| US2-AC1: Already-analyzed duplicate skipped | ✅ Integration `test_process_article_returns_false_for_fully_processed_duplicate` | None |
| US2-AC2: No duplicate record created | ✅ Same test above (count assertion) | None |
| US3-AC1: Un-analyzed duplicate re-queued, no new record | ✅ Integration `test_process_article_analyzes_duplicate_missing_analysis` | None |
| US3-AC2: ArXiv section data merged before re-queue | ❌ Not tested | Unit test for `ProcessScrapedArticleUseCase` needed |
| Handler: DUPLICATE_NEEDS_ANALYSIS → event published | ❌ Missing from unit test | Unit test for `ArticleScrapedHandler` needed |
| DedupService: find_existing contract | ❌ No dedicated unit tests | Unit tests for `DedupService` needed |
| DedupService: needs_analysis contract | ❌ No dedicated unit tests | Unit tests for `DedupService` needed |

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) for the full entity specification.

Key relationships:
- `Article` ←1:0..1→ `ArxivMetadata` (via `article_id`)
- `Article` ←1:0..1→ `Analysis` (checked by `DedupService.needs_analysis`)
- `UrlHash` is computed (SHA-256, 64-char hex), stored as `url_hash` column with unique constraint

### Interface Contracts

This capability is purely internal — it consumes `ArticleScrapedEvent` from the event bus and produces `ArticleProcessedEvent`. No external API contracts to define.

### Agent Context

The plan reference in CLAUDE.md has been updated to point to this plan:

```
specs/002-article-processing/plan.md
```

## Implementation Tasks (Phase 2 — /speckit-tasks)

The following task categories will be expanded by `/speckit-tasks`:

1. **Unit: DedupService** — `test_dedup_service.py` covering `find_existing` (hit / miss) and `needs_analysis` (with/without analysis, unsaved article)
2. **Unit: ProcessScrapedArticleUseCase** — New test file covering all 4 outcomes (NEW, DUPLICATE, DUPLICATE_NEEDS_ANALYSIS, FAILED) with mocked repos, including ArXiv metadata save path and section merging
3. **Unit: ArticleScrapedHandler** — Add `DUPLICATE_NEEDS_ANALYSIS` case to existing test file
4. **Integration: ArXiv metadata** — Extend `_wire_pipeline` to accept `arxiv_metadata_repo`, add test asserting metadata row is created for ArXiv articles
5. **Integration: Section merging** — Add test for `DUPLICATE_NEEDS_ANALYSIS` + ArXiv sections: pre-insert article + metadata, re-submit event, assert `article.metadata["sections"]` is populated in the re-queued article
