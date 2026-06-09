# Tasks: Translation

**Input**: Design documents from `/specs/004-translation/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Brownfield — all tasks are verification tests. No production code changes required.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create test infrastructure shared across all user story test phases

- [ ] T001 Create test directory structure: `src/tests/unit/modules/intelligence/application/`, `src/tests/unit/modules/intelligence/domain/`, `src/tests/integration/intelligence/`
- [ ] T002 [P] Create shared test fixtures for translation use cases in `src/tests/unit/modules/intelligence/application/conftest.py` — mock `LLMService`, `AnalysesTranslationRepository`, `TagTranslationRepository`, prompt factories
- [ ] T003 [P] Create integration test conftest for translation tables in `src/tests/intelligence/conftest.py` — extends existing integration conftest with `analyses_translation`, `tags_translation`, `tag_group_definitions_translation` table setup

**Checkpoint**: Test infrastructure ready — all user story test phases can begin

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Unit tests for domain value objects that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] Test `ArticleTranslationPrompt.render()` substitutes all placeholders and maps language codes to display names in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [ ] T005 [P] Test `TagTranslationPrompt.render()` substitutes `__TARGET_LANGUAGE__` and `__TAGS__` in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [ ] T006 [P] Test `GroupTranslationPrompt.render()` substitutes `__TARGET_LANGUAGE__` and `__GROUPS__`, and `format_group()` formats "display_name | description" in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`
- [ ] T007 [P] Test `LANGUAGE_NAMES` mapping returns display name for known codes and raw code for unknown codes in `src/tests/unit/modules/intelligence/domain/test_translation_prompt.py`

**Checkpoint**: Domain value object tests pass — user story verification can begin

---

## Phase 3: User Story 1 - Auto-translation after analysis (Priority: P1) 🎯 MVP

**Goal**: Verify that `AnalysisCompletedHandler` correctly triggers article, tag, and group translation after tag normalization, and that `TranslationFailedEvent` is published on failure.

**Independent Test**: Mock `TagNormalizationCompletedEvent`, invoke handler, assert `TranslateArticleUseCase.execute()` called for each target language, `TranslateTagsUseCase.translate_tags()` and `translate_groups()` called, and `TranslationFailedEvent` published on failure.

### Unit Tests for User Story 1

- [ ] T008 [P] [US1] Test `TranslateArticleUseCase.execute()` returns existing translation without calling LLM when `repository.exists()` is True in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T009 [P] [US1] Test `TranslateArticleUseCase.execute()` calls LLM when no existing translation, parses response sections (Summary, Pain Points, Insights, Innovations), and persists result in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T010 [P] [US1] Test `TranslateArticleUseCase.execute()` returns `success=False` with empty content when LLM returns None (all providers exhausted) in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T011 [P] [US1] Test `TranslateArticleUseCase.execute()` returns `success=False` when repository save raises exception in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T012 [P] [US1] Test `TranslateArticleUseCase._parse_sections()` handles: full response, missing sections, full-width colons, case-insensitive headers in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T013 [P] [US1] Test `TranslateArticleUseCase.execute()` substitutes empty source fields with "(empty)" in prompt render call in `src/tests/unit/modules/intelligence/application/test_translate_article_use_case.py`
- [ ] T014 [P] [US1] Test `TranslateTagsUseCase.translate_tags()` finds tags without translation, calls LLM, saves positional matches, returns `{total, success, failed}` in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T015 [P] [US1] Test `TranslateTagsUseCase.translate_tags()` counts unmatched lines (fewer LLM lines than tags) as failures in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T016 [P] [US1] Test `TranslateTagsUseCase.translate_tags()` returns all-failed when LLM returns None in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T017 [P] [US1] Test `TranslateTagsUseCase.translate_groups()` finds groups without translation, calls LLM, parses pipe-delimited lines into display_name + description, saves results in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T018 [P] [US1] Test `TranslateTagsUseCase.translate_groups()` handles groups with no description (pipe with empty second part) in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T019 [P] [US1] Test `TranslateTagsUseCase.translate_groups()` counts unmatched lines as failures in `src/tests/unit/modules/intelligence/application/test_translate_tags_use_case.py`
- [ ] T020 [US1] Test `AnalysisCompletedHandler` calls `translate_article_uc.execute()` for each language in `target_languages` after `TagNormalizationCompletedEvent` in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [ ] T021 [US1] Test `AnalysisCompletedHandler` skips translation and logs warning when English translation row is missing in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [ ] T022 [US1] Test `AnalysisCompletedHandler` publishes `TranslationFailedEvent` when article translation returns `success=False` in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [ ] T023 [US1] Test `AnalysisCompletedHandler` publishes `TranslationFailedEvent` when article translation throws exception in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`
- [ ] T024 [US1] Test `AnalysisCompletedHandler` calls `translate_tags()` and `translate_groups()` for each language after article translation, swallowing exceptions with log in `src/tests/unit/modules/intelligence/application/test_analysis_completed_handler.py`

**Checkpoint**: User Story 1 unit tests pass — auto-translation behavior verified

---

## Phase 4: User Story 2 - Manual batch translation via CLI (Priority: P2)

**Goal**: Verify that the CLI translate command correctly validates language, fetches untranslated analyses/tags/groups, and calls the translation use cases.

**Independent Test**: Run CLI entry point with mocked pipeline, verify correct limit and language passed, verify unsupported language exits with error.

### Unit Tests for User Story 2

- [ ] T025 [P] [US2] Test `build_translation_pipeline()` returns dict with `use_case` (TranslateArticleUseCase), `tag_use_case` (TranslateTagsUseCase), `session`, `analyses_translation_repository`, `tag_translation_repository` in `src/tests/unit/test_bootstrap.py`
- [ ] T026 [P] [US2] Test CLI `translate.py` validates language against `LANGUAGE_NAMES` keys, exits with error for unsupported code in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T027 [P] [US2] Test CLI `translate.py` fetches untranslated analyses via `find_analyses_without_translation(language, limit)` and calls `translate_use_case.execute()` for each in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T028 [P] [US2] Test CLI `translate.py` calls `tag_translate_use_case.translate_tags(language, limit)` and `translate_groups(language, limit)` after article loop in `src/tests/unit/entrypoints/cli/test_translate_cli.py`
- [ ] T029 [P] [US2] Test CLI `translate.py` uses `--limit` default of 10 and passes same limit to articles, tags, and groups in `src/tests/unit/entrypoints/cli/test_translate_cli.py`

**Checkpoint**: User Story 2 unit tests pass — CLI translation behavior verified

---

## Phase 5: User Story 3 - Translation deduplication (Priority: P3)

**Goal**: Verify that deduplication prevents re-translation at both the query level and use-case level, and that repository save uses upsert semantics.

**Independent Test**: Call translation twice for same analysis+language, verify no LLM call on second invocation. Query for untranslated tags/groups, verify already-translated entities are excluded.

### Integration Tests for User Story 3

- [ ] T030 [P] [US3] Test `SqlAlchemyAnalysesTranslationRepository.exists()` returns False for new pair, True after save in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [ ] T031 [P] [US3] Test `SqlAlchemyAnalysesTranslationRepository.save()` upserts — second save with same `(analysis_id, language)` updates content instead of duplicating in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [ ] T032 [P] [US3] Test `SqlAlchemyAnalysesTranslationRepository.find_analyses_without_translation()` excludes analyses that already have a translation in the target language in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [ ] T033 [P] [US3] Test `SqlAlchemyTagTranslationRepository.save_tag_translation()` upserts — second save with same `(tag_id, language)` updates name in `src/tests/integration/intelligence/test_translate_tags_integration.py`
- [ ] T034 [P] [US3] Test `SqlAlchemyTagTranslationRepository.find_tags_without_translation()` excludes tags that already have a translation in the target language in `src/tests/integration/intelligence/test_translate_tags_integration.py`
- [ ] T035 [P] [US3] Test `SqlAlchemyTagTranslationRepository.save_group_translation()` upserts — second save with same `(group_id, language)` updates display_name and description in `src/tests/integration/intelligence/test_translate_tags_integration.py`
- [ ] T036 [P] [US3] Test `SqlAlchemyTagTranslationRepository.find_groups_without_translation()` excludes groups that already have a translation in the target language in `src/tests/integration/intelligence/test_translate_tags_integration.py`

**Checkpoint**: User Story 3 integration tests pass — deduplication and upsert behavior verified

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration test coverage and validation across user stories

- [ ] T037 Integration test: end-to-end `TranslateArticleUseCase.execute()` with real DB — create analysis + English translation, translate to zh-TW, verify row in `analyses_translation` table in `src/tests/integration/intelligence/test_translate_article_integration.py`
- [ ] T038 Integration test: end-to-end `TranslateTagsUseCase.translate_tags()` + `translate_groups()` with real DB — create tags and groups, translate to ja, verify rows in `tags_translation` and `tag_group_definitions_translation` tables in `src/tests/integration/intelligence/test_translate_tags_integration.py`
- [ ] T039 Run `make test` and verify all translation unit tests pass via Docker
- [ ] T040 Run `make test-integration` and verify all translation integration tests pass via Docker
- [ ] T041 Validate quickstart.md — verify `make translate LANG=zh-TW` command works as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1
- **US1 (Phase 3)**: Depends on Phase 2 — prompt value object tests must pass
- **US2 (Phase 4)**: Depends on Phase 2 — can run in parallel with Phase 3
- **US3 (Phase 5)**: Depends on Phase 1 (integration test conftest) — can run in parallel with Phases 3 & 4
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2) — no dependencies on other stories
- **US2 (P2)**: Depends on Foundational (Phase 2) — no dependencies on US1
- **US3 (P3)**: Depends on Setup (Phase 1) — no dependencies on US1 or US2

### Parallel Opportunities

- T002, T003 can run in parallel (different conftest files)
- T004–T007 can all run in parallel (same file, different test functions)
- T008–T019 can all run in parallel (different test files for different use cases)
- T025–T029 can all run in parallel (CLI tests are independent)
- T030–T036 can all run in parallel (different integration test files)
- US1, US2, US3 test phases can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 unit test tasks in parallel (different test files):
Task T008-T013: "Unit tests for TranslateArticleUseCase in test_translate_article_use_case.py"
Task T014-T019: "Unit tests for TranslateTagsUseCase in test_translate_tags_use_case.py"
Task T020-T024: "Unit tests for AnalysisCompletedHandler in test_analysis_completed_handler.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (prompt value object tests)
3. Complete Phase 3: US1 tests (auto-translation verification)
4. **STOP and VALIDATE**: Run `make test` — verify all US1 tests pass
5. Auto-translation behavior is now spec-verified

### Incremental Delivery

1. Setup + Foundational → Test infrastructure ready
2. Add US1 → Verify auto-translation → MVP checkpoint
3. Add US2 → Verify CLI translation → Operational tooling verified
4. Add US3 → Verify deduplication → Data integrity verified
5. Polish → End-to-end integration + Docker validation

---

## Notes

- All tasks are verification tests — no production code changes required
- Integration tests MUST use `@pytest.mark.integration` with isolated schema and per-test rollback (Constitution III)
- Unit tests MUST NOT require a running database — mock all repo/LLM dependencies
- All test runs MUST execute inside Docker via `make test` / `make test-integration` (Constitution III)
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
