# Tasks: Article Processing

**Input**: Design documents from `/specs/002-article-processing/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅

**Context**: All production code already exists. Every task here is a **test** that verifies existing behavior matches the spec. No new production code is required.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Create Missing Test Files)

**Purpose**: Create the two empty test files that will hold new unit tests.

- [x] T001 Create `src/tests/unit/modules/collection/domain/test_dedup_service.py` with imports and test stubs for `DedupService`
- [x] T002 [P] Create `src/tests/unit/modules/collection/application/test_process_scraped_article.py` with imports and test stubs for `ProcessScrapedArticleUseCase`

**Checkpoint**: Two empty test files exist and are discoverable by pytest.

---

## Phase 2: Foundational (No blocking prerequisites)

All production code is in place. No foundational tasks are required before proceeding to user story tests.

---

## Phase 3: User Story 1 — New Article Saved and Queued (Priority: P1) 🎯 MVP

**Goal**: Verify that a new article is saved exactly once, ArXiv supplementary metadata is persisted for ArXiv sources, and a save failure produces no downstream event.

**Independent Test**: `make test` passes for all T003–T006 tasks; `make test-integration` passes for T007.

### Unit Tests — US1

- [x] T003 [US1] In `src/tests/unit/modules/collection/domain/test_dedup_service.py`: add `test_find_existing_returns_none_for_unknown_url` — mock `ArticleRepository.find_by_url_hash` returning `None`, assert result is `None`
- [x] T004 [P] [US1] In `src/tests/unit/modules/collection/application/test_process_scraped_article.py`: add `test_execute_returns_new_outcome_and_article_for_unknown_url` — mock `DedupService.find_existing` returning `None`, mock `ArticleRepository.save` returning an `Article`, assert outcome is `NEW` and article is not `None`
- [x] T005 [P] [US1] In `src/tests/unit/modules/collection/application/test_process_scraped_article.py`: add `test_execute_returns_failed_outcome_when_save_raises` (covers AC3) — mock `DedupService.find_existing` returning `None`, mock `ArticleRepository.save` raising `Exception`, assert outcome is `FAILED` and article is `None`
- [x] T006 [P] [US1] In `src/tests/unit/modules/collection/application/test_process_scraped_article.py`: add `test_execute_saves_arxiv_metadata_when_source_is_arxiv` — mock `DedupService.find_existing` returning `None`, pass a real `arxiv_metadata_repo` mock, call with `source="arxiv"` and metadata dict containing `arxiv_id`/`authors`/`sections`, assert `arxiv_metadata_repo.save` was called once

### Integration Tests — US1

- [x] T007 [US1] In `src/tests/integration/test_process_article.py`: add `test_process_arxiv_article_persists_metadata` — wire pipeline with a real `SqlAlchemyArxivMetadataRepository`, submit an ArXiv event with `metadata={"arxiv_id": "2501.00001", "authors": ["Author A"], "pdf_available": True, "sections": {"intro": "text"}}`, assert an `ArxivMetadata` row exists with matching `arxiv_id` and `authors`

**Checkpoint**: US1 fully covered. `make test` and `make test-integration` both pass.

---

## Phase 4: User Story 2 — Duplicate URL Silently Skipped (Priority: P2)

**Goal**: Verify that an article whose URL has already been analyzed produces `DUPLICATE` outcome with no new record and no downstream event.

**Independent Test**: `make test` passes for all T008–T010 tasks.

### Unit Tests — US2

- [x] T008 [P] [US2] In `src/tests/unit/modules/collection/domain/test_dedup_service.py`: add `test_find_existing_returns_article_for_known_url` — mock `ArticleRepository.find_by_url_hash` returning a saved `Article`, assert result is that article
- [x] T009 [P] [US2] In `src/tests/unit/modules/collection/domain/test_dedup_service.py`: add `test_needs_analysis_returns_false_when_article_has_analysis` — mock `ArticleRepository.has_analysis` returning `True`, assert `needs_analysis` returns `False`
- [x] T010 [US2] In `src/tests/unit/modules/collection/application/test_process_scraped_article.py`: add `test_execute_returns_duplicate_outcome_for_analyzed_article` — mock `DedupService.find_existing` returning a saved article, mock `DedupService.needs_analysis` returning `False`, assert outcome is `DUPLICATE` and article is `None`

**Checkpoint**: US2 fully covered. `make test` passes.

---

## Phase 5: User Story 3 — Duplicate Without Analysis Re-Queued (Priority: P2)

**Goal**: Verify that an un-analyzed duplicate is re-queued without creating a new record, and that ArXiv section data is merged back into the article before signalling downstream.

**Independent Test**: `make test` passes for all T011–T015; `make test-integration` passes for T016.

### Unit Tests — US3

- [x] T011 [P] [US3] In `src/tests/unit/modules/collection/domain/test_dedup_service.py`: add `test_needs_analysis_returns_true_when_article_has_no_analysis` — mock `ArticleRepository.has_analysis` returning `False`, assert `needs_analysis` returns `True`
- [x] T012 [P] [US3] In `src/tests/unit/modules/collection/domain/test_dedup_service.py`: add `test_needs_analysis_returns_false_for_unsaved_article` — pass an `Article` with `id=None`, assert `needs_analysis` returns `False` without calling `has_analysis`
- [x] T013 [US3] In `src/tests/unit/modules/collection/application/test_process_scraped_article.py`: add `test_execute_returns_duplicate_needs_analysis_for_un_analyzed_article` — mock `DedupService.find_existing` returning a saved article, mock `DedupService.needs_analysis` returning `True`, assert outcome is `DUPLICATE_NEEDS_ANALYSIS` and returned article is the existing one
- [x] T014 [P] [US3] In `src/tests/unit/modules/collection/application/test_process_scraped_article.py`: add `test_execute_merges_arxiv_sections_into_article_metadata_on_requeue` (covers FR-007) — mock `DedupService.find_existing` returning an ArXiv article, mock `DedupService.needs_analysis` returning `True`, mock `ArxivMetadataRepository.find_by_article_id` returning an `ArxivMetadata` entity with `sections={"intro": "text"}`, assert `article.metadata["sections"]` equals that dict after `execute()`
- [x] T015 [US3] In `src/tests/unit/modules/collection/application/test_article_scraped_handler.py`: add `test_handle_duplicate_needs_analysis_publishes_event_and_returns_true` — mock `use_case.execute` returning `(DUPLICATE_NEEDS_ANALYSIS, article)`, assert `event_bus.publish` is called once and result is `True`

### Integration Tests — US3

- [x] T016 [US3] In `src/tests/integration/test_process_article.py`: add `test_requeue_arxiv_article_merges_sections_from_stored_metadata` — pre-insert an `Article` (source=`arxiv`) and an `ArxivMetadata` row with `sections={"intro": "full text"}`, wire pipeline with `arxiv_metadata_repo`, submit event for the same URL, capture the `ArticleProcessedEvent` from the bus, assert the emitted article's `metadata["sections"]` equals `{"intro": "full text"}`

**Checkpoint**: US3 fully covered. `make test` and `make test-integration` both pass.

---

## Phase 6: Polish & Validation

**Purpose**: Run full test suites and confirm all spec scenarios have green coverage.

- [x] T017 [P] Run `make test` — verify all unit tests in `src/tests/unit/` pass inside Docker
- [x] T018 [P] Run `make test-integration` — verify all integration tests in `src/tests/integration/` pass inside Docker

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 3 (US1)**: Depends on T001 (new domain test file) and T002 (new application test file)
- **Phase 4 (US2)**: Depends on T001, T002
- **Phase 5 (US3)**: Depends on T001, T002
- **Phase 6 (Polish)**: Depends on all test tasks complete

### User Story Dependencies

- **US1 (P1)**: T001, T002 complete → T003–T007 can proceed
- **US2 (P2)**: T001, T002 complete → T008–T010 can proceed (independent of US1 tests)
- **US3 (P2)**: T001, T002 complete → T011–T016 can proceed (independent of US1, US2 tests)

### Within Each Phase

- `[P]` tasks within a phase target different test functions and can run in parallel
- Within `test_process_scraped_article.py`, each `test_*` function is independent — write in any order
- Within `test_dedup_service.py`, all test functions are independent

### Parallel Opportunities

```bash
# After T001 + T002, all of the following can proceed in parallel:
T003 (domain unit — dedup miss)
T004 (application unit — NEW outcome)
T005 (application unit — FAILED outcome)
T006 (application unit — arxiv metadata)
T008 (domain unit — dedup hit)
T009 (domain unit — needs_analysis false)
T011 (domain unit — needs_analysis true)
T012 (domain unit — unsaved article)
T014 (application unit — section merge)
T015 (handler unit — DUPLICATE_NEEDS_ANALYSIS)
```

---

## Implementation Strategy

### MVP First (US1 only — ~4 tasks after setup)

1. Complete Phase 1: T001, T002
2. Complete Phase 3: T003–T007
3. **STOP and VALIDATE**: `make test` + `make test-integration`
4. US1 spec fully verified

### Incremental Delivery

1. T001, T002 → Files ready
2. T003–T007 (US1) → Core happy path + ArXiv metadata verified
3. T008–T010 (US2) → Dedup skip path verified
4. T011–T016 (US3) → Re-queue + section merging verified
5. T017, T018 → Full suite green

---

## Spec Coverage Map

| Spec Requirement | Covered by | Status |
|-----------------|------------|--------|
| FR-001 URL dedup via hash | T003, T008 + existing integration | ✅ After tasks |
| FR-002 Persist new articles | T004 + existing integration | ✅ After tasks |
| FR-003 Three outcome types | T004, T010, T013 | ✅ After tasks |
| FR-004 Publish event only for NEW/DUPLICATE_NEEDS_ANALYSIS | T004, T013, T015 + existing | ✅ After tasks |
| FR-005 Persist ArXiv metadata separately | T006, T007 | ✅ After tasks |
| FR-006 FAILED → no event published | T005 + existing handler unit test | ✅ After tasks |
| FR-007 Merge ArXiv sections on re-queue | T014, T016 | ✅ After tasks |

---

## Notes

- All tasks modify or create **test files only** — no production code changes
- Run tests via `make test` (unit) and `make test-integration` (integration) inside Docker — do NOT run `uv run pytest` directly per Constitution Principle III
- `[P]` tasks = different test functions in different (or same) files with no ordering dependency
- Each US phase can be independently committed and validated
