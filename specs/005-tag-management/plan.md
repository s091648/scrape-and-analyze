# Implementation Plan: Tag Management

**Branch**: `005-tag-management` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-tag-management/spec.md`

**Note**: Brownfield plan — records existing architecture and identifies verification tasks (tests) to confirm behavior matches the spec.

## Summary

The tag management capability provides automated tag normalization (embedding-based similarity, auto-merge, suggestions), tag group CRUD with merge/reorder, tag CRUD with group movement, normalization suggestion review, topic tag mode governance, a drag-and-drop frontend interface, and backfill/maintenance scripts. The existing implementation follows hexagonal/DDD architecture with domain interfaces, application use cases, infrastructure implementations, and a FastAPI/Next.js stack.

## Technical Context

**Language/Version**: Python 3.11 (backend/scraper), TypeScript + React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Next.js 16, pgvector, @dnd-kit/core (drag-and-drop), Shadcn/UI + Radix

**Storage**: PostgreSQL 15 + pgvector extension (768-dim embeddings with HNSW indexes)

**Testing**: pytest (unit + integration), Vitest (frontend unit), Playwright (E2E), Storybook (component visual)

**Target Platform**: Linux server (Docker containers via docker compose)

**Project Type**: Web application (scraper service + REST API + Next.js frontend)

**Performance Goals**: Batch embedding generation (max 100 per call), 5-worker concurrent fetch in ScrapeExecutor, HNSW index for vector similarity search

**Constraints**: Tag normalization runs synchronously after analysis; embedding service availability is a hard dependency

**Scale/Scope**: Per-topic tag vocabulary; tags scoped by (group_name, topic_id); up to 5 similar candidates per normalization check

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Domain-Driven Design | ✅ PASS | Tag entities in `models/`, domain interfaces in `src/modules/intelligence/domain/`, use cases in `application/`, repos in `infrastructure/`, composition in `bootstrap.py` |
| II. Atomic Frontend Architecture | ✅ PASS | Tag components in `components/features/tags/`, shared `grouped-tag-select` in `components/features/articles/`, UI primitives in `components/ui/` |
| III. Test Discipline | ✅ PASS | Unit tests exist for use cases, repos, handlers, value objects. Integration test for translate_tags. Frontend tests for tag components. All via Docker (`make test`) |
| IV. Docker-First Local Dev | ✅ PASS | All services run in Docker, Makefile targets for backfill/test/scrape |
| V. CI-Only Deployment | ✅ PASS | No deployment concerns in this capability |
| VI. Observability | ✅ PASS | structlog logging in use cases (tag_auto_merged, tag_suggestion_created, tag_created events) |
| VII. Code Style & Quality | ✅ PASS | Pydantic schemas for API validation, UUID PKs, Alembic migrations, no TODO comments |

No violations. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-tag-management/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md           # REST API contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
# Domain layer
src/modules/intelligence/domain/
├── entities/
│   └── tag_normalization_suggestion.py
├── repositories/
│   ├── tag_repository.py
│   ├── tag_group_definition_repository.py
│   └── tag_translation_repository.py
├── services/
│   └── embedding_service.py
└── value_objects/
    ├── tag_group.py
    └── analysis_tag_group.py

# Application layer
src/modules/intelligence/application/
├── use_cases/
│   ├── normalize_tags.py
│   └── translate_tags.py
├── event_handlers/
│   └── tag_normalization_handler.py
└── events/
    ├── tag_normalization_completed.py
    └── tag_normalization_failed.py

# Infrastructure layer
src/infrastructure/
├── persistence/intelligence/
│   ├── tag_repo_impl.py
│   ├── tag_group_definition_repo_impl.py
│   └── tag_translation_repo_impl.py
└── intelligence/llm/embedding/
    ├── base_embedding_provider.py
    └── gemini_embedding_provider.py

# ORM models
models/
├── tag.py
├── tag_group.py
├── tag_translation.py
├── tag_group_translation.py
├── tag_normalization_suggestion.py
└── topic.py               # tag_mode column

# Shared
src/shared/domain/value_objects/
└── tag_mode.py

# Backend API
backend/routers/tags.py
backend/tests/test_tags.py

# Frontend
frontend/app/tags/page.tsx
frontend/lib/api/tags.ts
frontend/components/features/tags/
├── tag-dialog.tsx
├── tag-mode-selector.tsx
└── tag-group-card.tsx
frontend/components/features/articles/
└── grouped-tag-select.tsx

# Backfill scripts
scripts/
├── backfill_tags.py
├── backfill_tag_embeddings.py
├── backfill_tag_suggestions.py
├── backfill_tag_group_definitions.py
└── audit_tag_groups.py

# Tests
src/tests/unit/modules/intelligence/
├── application/
│   ├── test_normalize_tags_use_case.py
│   ├── test_translate_tags_use_case.py
│   └── test_tag_normalization_handler.py
├── domain/
│   └── test_analysis_tag_group.py
└── infrastructure/persistence/
    ├── test_tag_repo.py
    └── test_tag_group_definition_repo.py
src/tests/unit/shared/domain/
└── test_tag_mode.py
src/tests/integration/intelligence/
└── test_translate_tags_integration.py
frontend/tests/unit/
├── tags-api.test.ts
├── tag-dialog.test.tsx
├── grouped-tag-select.test.tsx
├── tag-group-card.test.tsx
└── tag-mode-selector.test.tsx

# Migrations (tag-related)
alembic/versions/
├── 04_*_add_tag_groups.py
├── 05_normalize_tags.py
└── 17_add_vector_failed_task_and_auto_tag.py
```

**Structure Decision**: Existing hexagonal/DDD structure with three-service architecture (src/, backend/, frontend/). No new directories needed — the capability is fully implemented.
