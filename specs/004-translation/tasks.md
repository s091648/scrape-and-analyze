# Tasks: Translation

**Input**: Design documents from `/specs/004-translation/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, contracts/

**Tests**: Every tasks.md MUST include at least one dedicated test phase. Tests are NOT optional — omitting test tasks violates the project constitution (§III).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. The feature is mixed brownfield/greenfield:
- **Brownfield** (analysis/tag/group translation): already implemented — tasks are test verification only
- **Greenfield** (article title/content translation): new production code + tests across all DDD layers

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create test infrastructure shared across all phases

- [ ] T001 Create test directory structure: `src/tests/unit/modules/intelligence/application/`, `src/tests/unit/modules/intelligence/domain/`, `src/tests/integration/intelligence/`
- [ ] T002 [P] Create shared unit test fixtures in `src/tests/unit/modules/intelligence/application/conftest.py` — mock `LLMService`, `AnalysesTranslationRepository`, `TagTranslationRepository`, `ArticleTranslationRepository`, prompt factories
- [X] T003 [P] Create integration test conftest in `src/tests/integration/intelligence/conftest.py` — extend base integration conftest with `analyses_translation`, `tags_translation`, `tag_group_definitions_translation`, `articles_translation` table setup and per-test rollback

**Checkpoint**: Test infrastructure ready — all phases can begin

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Unit tests for domain value objects that all phases depend on

**⚠️ CRITICAL**: No user story test phase can begin until this phase is complete

- [ ] T004 [P] Test `ArticleTranslationPrompt.render()` substitutes all placeholders (`__SUMMARY__`, `__PAIN_POINTS__`, `__INSIGHTS__`, `__INNOVATIONS__`, `__TARGET_LANGUAGE__`) and maps language codes to display names in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [X] T005 [P] Test `ArticleBodyTranslationPrompt.render()` substitutes `__TARGET_LANGUAGE__`, `__TITLE__`, `__CONTENT__` and `parse_response()` splits LLM output into Title/Content sections correctly in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [ ] T006 [P] Test `TagTranslationPrompt.render()` substitutes `__TARGET_LANGUAGE__` and `__TAGS__` in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [ ] T007 [P] Test `GroupTranslationPrompt.render()` substitutes `__TARGET_LANGUAGE__` and `__GROUPS__`, and `format_group()` formats "display_name | description" in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [ ] T008 [P] Test `LANGUAGE_NAMES` mapping returns display name for known codes and raw code for unknown codes in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`

**Checkpoint**: Domain value object tests pass — user story phases can begin

---

## Phase 3: Greenfield — Article Body Translation (Production Code)

**Purpose**: Implement all new production code for article title/content translation

**⚠️ CRITICAL**: Phase 4 US1 unit tests, Phase 5 US2 implementation, and Phase 6 US3 integration tests all depend on this phase completing first

### Data Layer

- [X] T009 Create `ArticleTranslation` ORM model in `models/article_translation.py` — columns: id (UUID PK), article_id (UUID FK → articles.id, CASCADE DELETE), language (VARCHAR 10), title (TEXT NOT NULL), content (TEXT nullable), created_at, updated_at; unique constraint on (article_id, language)
- [X] T010 Create Alembic migration `alembic/versions/20_add_article_translation.py` — create `articles_translation` table with all columns and constraints from data-model.md; run `make migrate` locally to verify

### Domain Layer

- [X] T011 [P] Create `ArticleTranslation` domain entity in `src/modules/intelligence/domain/entities/article_translation.py` — fields: id, article_id, language, title, content, created_at, updated_at
- [X] T012 [P] Add `ArticleBodyTranslationContent` dataclass (title: Optional[str], content: Optional[str]) and `ArticleBodyTranslationResult` dataclass (article_id, language, content, success) to `src/modules/intelligence/domain/value_objects/analyses_translation_content.py`
- [X] T013 [P] Add `ArticleBodyTranslationPrompt` to `src/modules/intelligence/domain/value_objects/translation_prompt.py` — placeholders: `__TARGET_LANGUAGE__`, `__TITLE__`, `__CONTENT__`; `render(target_language, title, content)` returns new instance; `parse_response()` splits LLM output by "Title:" / "Content:" section headers
- [X] T014 Create `ArticleTranslationRepository` ABC in `src/modules/intelligence/domain/repositories/article_translation_repository.py` — methods: `save(article_id, language, title, content)`, `find_by_article_id_and_language(article_id, language) -> Optional[ArticleBodyTranslationContent]`, `exists(article_id, language) -> bool`, `find_articles_without_translation(language, limit) -> list`

### Application Layer

- [X] T015 Create `TranslateArticleBodyUseCase` in `src/modules/intelligence/application/use_cases/translate_article_body.py` — `execute(article_id, title, content, target_language)`: check `repository.exists()` for dedup; substitute empty content with "(empty)"; render `ArticleBodyTranslationPrompt`; call `LLMService.translate()`; parse response into title + content sections; call `repository.save()`; return `ArticleBodyTranslationResult`
- [X] T016 Extend `TagNormalizationCompletedEvent` in `src/modules/intelligence/application/events/tag_normalization_completed.py` — add `article_title: str` and `article_content: str` fields (with empty-string defaults for backward compatibility)
- [X] T017 Update `TagNormalizationHandler` in `src/modules/intelligence/application/event_handlers/tag_normalization_handler.py` — inject a read-only article query (via SQLAlchemy `Article` model or a minimal `ArticleReadRepository` interface) to fetch `article.title` and `article.content` by `event.article_id`; populate both fields in `TagNormalizationCompletedEvent` before publishing
- [X] T018 Inject `TranslateArticleBodyUseCase` into `AnalysisCompletedHandler` in `src/modules/intelligence/application/event_handlers/analysis_completed_handler.py` — call `translate_body_uc.execute(article_id=event.article_id, title=event.article_title, content=event.article_content, target_language=lang)` per language inside the existing per-language loop; publish `TranslationFailedEvent` on failure (task_type="translate_article_body")

### Infrastructure Layer

- [X] T019 Create `SqlAlchemyArticleTranslationRepository` in `src/infrastructure/persistence/intelligence/article_translation_repo_impl.py` — implements `ArticleTranslationRepository` ABC; `save()` uses upsert on `(article_id, language)`; `find_by_article_id_and_language()` maps ORM row to `ArticleBodyTranslationContent`; `find_articles_without_translation()` left-joins `Article` with `ArticleTranslation` filtered by language and limit

### Wiring & Backend

- [X] T020 Update `src/bootstrap.py` — wire `SqlAlchemyArticleTranslationRepository`, instantiate `TranslateArticleBodyUseCase` with LLM service and repo, inject into `AnalysisCompletedHandler`; also inject article query capability into `TagNormalizationHandler`
- [X] T021 [P] Add `translated_title: Optional[str]` and `translated_content: Optional[str]` to `ArticleDetailOut` in `backend/schemas/article.py`
- [X] T022 [P] Update articles detail endpoint in `backend/routers/articles.py` — after fetching the article, query `ArticleTranslation` by (article_id, lang) where lang comes from the request's `lang` query param or `Accept-Language` header; populate `translated_title` and `translated_content` if a row exists

**Checkpoint**: All greenfield production code complete — article body translation is functional end-to-end

---

## Phase 4: User Story 1 — Auto-translation after analysis (Priority: P1) 🎯 MVP

**Goal**: Verify that `AnalysisCompletedHandler` triggers article analysis, article body, and tag/group translation for each configured language, and that failures produce `TranslationFailedEvent`.

**Independent Test**: Mock `TagNormalizationCompletedEvent` with article_title and article_content, invoke handler, assert all three use cases are called per language, and `TranslationFailedEvent` published on failure.

### Unit Tests for User Story 1

- [ ] T023 [P] [US1] Test `TranslateArticleUseCase.execute()` returns existing translation without calling LLM when `repository.exists()` is True in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T024 [P] [US1] Test `TranslateArticleUseCase.execute()` calls LLM, parses response into 4 sections (Summary/Pain Points/Insights/Innovations), and persists result in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T025 [P] [US1] Test `TranslateArticleUseCase.execute()` returns `success=False` with empty content when LLM returns None in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T026 [P] [US1] Test `TranslateArticleUseCase.execute()` substitutes empty source fields with "(empty)" in prompt render call in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T027 [P] [US1] Test `TranslateArticleUseCase._parse_sections()` handles: full response, missing sections, full-width colons, case-insensitive headers in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [X] T028 [P] [US1] Test `TranslateArticleBodyUseCase.execute()` returns existing translation without calling LLM when `repository.exists()` is True in `src/tests/unit/modules/intelligence/application/test_translate_article_body_use_case.py`
- [X] T029 [P] [US1] Test `TranslateArticleBodyUseCase.execute()` calls LLM, parses response into Title + Content sections, and persists result in `src/tests/unit/modules/intelligence/application/test_translate_article_body_use_case.py`
- [X] T030 [P] [US1] Test `TranslateArticleBodyUseCase.execute()` returns `success=False` with empty content when LLM returns None in `src/tests/unit/modules/intelligence/application/test_translate_article_body_use_case.py`
- [X] T031 [P] [US1] Test `TranslateArticleBodyUseCase.execute()` substitutes empty content with "(empty)" in prompt render call in `src/tests/unit/modules/intelligence/application/test_translate_article_body_use_case.py`
- [ ] T032 [P] [US1] Test `TranslateTagsUseCase.translate_tags()` finds untranslated tags, calls LLM, saves positional matches, returns `{total, success, failed}` in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T033 [P] [US1] Test `TranslateTagsUseCase.translate_tags()` counts unmatched lines (fewer LLM lines than tags) as failures in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T034 [P] [US1] Test `TranslateTagsUseCase.translate_groups()` parses pipe-delimited lines into display_name + description, handles missing description in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [X] T035 [US1] Test `AnalysisCompletedHandler.handle()` calls `translate_article_uc.execute()`, `translate_body_uc.execute()`, `translate_tags_uc.translate_tags()`, and `translate_groups()` for each language in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [X] T036 [US1] Test `AnalysisCompletedHandler.handle()` skips analysis translation and logs warning when English content row is missing, but still calls `translate_body_uc.execute()` in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [X] T037 [US1] Test `AnalysisCompletedHandler.handle()` publishes `TranslationFailedEvent` with task_type="translate_article" when analysis translation returns `success=False` in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [X] T038 [US1] Test `AnalysisCompletedHandler.handle()` publishes `TranslationFailedEvent` with task_type="translate_article_body" when body translation returns `success=False` in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`

**Checkpoint**: User Story 1 unit tests pass — auto-translation behavior verified

---

## Phase 5: User Story 2 — Manual batch translation via CLI (Priority: P2)

**Goal**: Verify that the CLI translate command handles article body batch translation, validates language, and calls all four translation paths (analysis, body, tags, groups).

**Independent Test**: Run CLI with mocked pipeline, verify article body use case is called per untranslated article, verify backend returns translated_title/translated_content when lang matches.

### CLI + Backend Changes

- [X] T039 [US2] Update `src/entrypoints/cli/translate.py` — after existing article/tag/group batch loops, add article body batch: call `article_translation_repo.find_articles_without_translation(language, limit)` and `translate_body_uc.execute()` for each result

### Unit Tests for User Story 2

- [ ] T040 [P] [US2] Test `build_translation_pipeline()` in `src/bootstrap.py` returns dict with `translate_body_uc` (TranslateArticleBodyUseCase) and `article_translation_repository` in `src/tests/unit/test_bootstrap.py`
- [ ] T041 [P] [US2] Test CLI `translate.py` validates language against `LANGUAGE_NAMES` keys, exits with error for unsupported code in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T042 [P] [US2] Test CLI `translate.py` calls `translate_body_uc.execute()` for each article returned by `find_articles_without_translation(language, limit)` in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T043 [P] [US2] Test CLI `translate.py` fetches untranslated analyses and calls `translate_use_case.execute()` for each in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T044 [P] [US2] Test CLI `translate.py` calls `tag_translate_use_case.translate_tags()` and `translate_groups()` with same language and limit in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T045 [P] [US2] Test `ArticleDetailOut` includes `translated_title` and `translated_content` fields, and backend articles detail endpoint returns them populated when a matching `ArticleTranslation` row exists in `backend/tests/test_articles_router.py`

**Checkpoint**: User Story 2 unit tests pass — CLI and API behavior verified

---

## Phase 6: User Story 3 — Translation deduplication (Priority: P3)

**Goal**: Verify that all four repositories apply deduplication correctly and that upsert semantics prevent duplicates.

**Independent Test**: Save a translation twice with the same key; verify one row exists, content is updated, and no LLM call is made on second `execute()` invocation.

### Integration Tests for User Story 3

- [ ] T046 [P] [US3] Test `SqlAlchemyAnalysesTranslationRepository.exists()` returns False for new pair, True after `save()` in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [ ] T047 [P] [US3] Test `SqlAlchemyAnalysesTranslationRepository.save()` upserts — second save with same (analysis_id, language) updates content, no duplicate row in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [ ] T048 [P] [US3] Test `SqlAlchemyAnalysesTranslationRepository.find_analyses_without_translation()` excludes analyses that already have a translation in the target language in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [X] T049 [P] [US3] Test `SqlAlchemyArticleTranslationRepository.exists()` returns False for new pair, True after `save()` in `src/tests/integration/intelligence/test_translate_article_body_integration.py`
- [X] T050 [P] [US3] Test `SqlAlchemyArticleTranslationRepository.save()` upserts — second save with same (article_id, language) updates title + content, no duplicate row in `src/tests/integration/intelligence/test_translate_article_body_integration.py`
- [X] T051 [P] [US3] Test `SqlAlchemyArticleTranslationRepository.find_articles_without_translation()` excludes articles that already have a translation in the target language in `src/tests/integration/intelligence/test_translate_article_body_integration.py`
- [ ] T052 [P] [US3] Test `SqlAlchemyTagTranslationRepository.save_tag_translation()` upserts, and `find_tags_without_translation()` excludes already-translated tags in `src/tests/integration/intelligence/test_translate_tags_integration.py`
- [ ] T053 [P] [US3] Test `SqlAlchemyTagTranslationRepository.save_group_translation()` upserts, and `find_groups_without_translation()` excludes already-translated groups in `src/tests/integration/intelligence/test_translate_tags_integration.py`

**Checkpoint**: User Story 3 integration tests pass — deduplication and upsert behavior verified

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end integration coverage and Docker validation

- [ ] T054 Integration test: end-to-end `TranslateArticleUseCase.execute()` with real DB — create analysis + English translation, translate to zh-TW, verify row in `analyses_translation` in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [X] T055 Integration test: end-to-end `TranslateArticleBodyUseCase.execute()` with real DB — create article, call execute() with mocked LLM, verify row in `articles_translation` in `src/tests/integration/intelligence/test_translate_article_body_integration.py`
- [ ] T056 Integration test: end-to-end `TranslateTagsUseCase.translate_tags()` + `translate_groups()` with real DB — verify rows in `tags_translation` and `tag_group_definitions_translation` in `src/tests/integration/intelligence/test_translate_tags_integration.py`
- [ ] T057 Run `make test` and verify all translation unit tests pass via Docker
- [ ] T058 Run `make test-integration` and verify all translation integration tests pass via Docker
- [ ] T059 Run `make migrate` locally and verify `articles_translation` table is created with correct schema
- [ ] T060 Validate `make translate LANG=zh-TW` translates article bodies and reports count in quickstart.md output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1
- **Greenfield Production (Phase 3)**: No test dependencies — can start immediately in parallel with Phase 2; T011–T014 can start in parallel with T009–T010
- **US1 (Phase 4)**: Depends on Phase 2 (prompt tests) AND Phase 3 (production code)
- **US2 (Phase 5)**: Depends on Phase 3 (production code for CLI + backend changes)
- **US3 (Phase 6)**: Depends on Phase 1 (integration conftest) AND Phase 3 (ArticleTranslationRepository impl)
- **Polish (Phase 7)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2) + Greenfield (Phase 3)
- **US2 (P2)**: Depends on Greenfield (Phase 3) — can run in parallel with US1
- **US3 (P3)**: Depends on Phase 1 + Greenfield (Phase 3) — can run in parallel with US1 and US2

### Parallel Opportunities

- T002, T003 can run in parallel (different conftest files)
- T004–T008 can all run in parallel (same file, different test functions)
- T009, T010 can run in parallel (ORM model and migration are independent authoring steps)
- T011–T014 can all run in parallel after T009 (different domain files)
- T015–T018 can start after T014 (use case and event modifications are independent files)
- T019 after T014 (repo impl depends on ABC)
- T020 after T015 + T019 (bootstrap wiring depends on both)
- T021, T022 can run in parallel (schema and router changes in different files)
- T023–T034 can all run in parallel (different test files and functions)
- T040–T045 can all run in parallel (different test files)
- T046–T053 can all run in parallel (different integration test files)

---

## Implementation Strategy

### Greenfield First (Phase 3 Before Tests)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational prompt tests — validates new `ArticleBodyTranslationPrompt` before use case depends on it
3. Complete Phase 3: All greenfield production code (T009–T022) — MVP pipeline is functional
4. **STOP and VALIDATE**: Run `make migrate` → `make test` → confirm pipeline runs end-to-end
5. Add Phase 4 US1 tests → verify full auto-translation behavior
6. Add Phase 5 US2 tests + backend changes → verify CLI and API delivery
7. Add Phase 6 US3 integration tests → verify deduplication
8. Polish

### MVP Scope

Complete Phases 1–4 only. This delivers:
- Article body translation in the auto-pipeline
- Unit test coverage for all translation use cases
- Verified `make test` passing

---

## Notes

- All integration tests MUST use `@pytest.mark.integration` with isolated schema and per-test rollback (Constitution III)
- Unit tests MUST NOT require a running database — mock all repo/LLM dependencies
- All test runs MUST execute inside Docker via `make test` / `make test-integration` (Constitution III)
- `TagNormalizationHandler` modification (T017) is the only change outside the `intelligence` module — it requires fetching `Article.title` and `Article.content` by `article_id`; use a direct SQLAlchemy query or a minimal read-only interface; do not couple the intelligence domain to the collection domain
- New `TranslationFailedEvent` for body translation failures uses task_type="translate_article_body" to distinguish from analysis failures (task_type="translate_article")
- Migration T010 MUST be verified locally with `make migrate` before the Polish phase
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
