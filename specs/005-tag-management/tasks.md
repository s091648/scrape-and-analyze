# Tasks: Tag Management

**Input**: Design documents from `/specs/005-tag-management/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Brownfield — all tasks are verification tests to confirm existing behavior matches the spec.

**Organization**: Tasks are grouped by user story to enable independent verification of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend domain/application**: `src/modules/intelligence/`
- **Backend infrastructure**: `src/infrastructure/persistence/intelligence/`
- **Backend API**: `backend/routers/tags.py`
- **ORM models**: `models/`
- **Backend unit tests**: `src/tests/unit/`
- **Backend integration tests**: `src/tests/integration/`
- **Backend API tests**: `backend/tests/`
- **Frontend components**: `frontend/components/features/tags/`
- **Frontend tests**: `frontend/tests/unit/`
- **Backfill scripts**: `scripts/`

---

## Phase 1: Setup (Shared Test Infrastructure)

**Purpose**: Establish test helpers and fixtures needed across multiple user story verification tasks.

- [ ] T001 Create shared tag test fixtures (TagData factory, mock embedding vectors, sample tag_groups input) in `src/tests/unit/modules/intelligence/application/conftest.py` or extend existing conftest
- [ ] T002 [P] Create backend tag test fixtures (sample TagGroupDefinition, Tag, TagNormalizationSuggestion ORM instances) in `backend/tests/conftest.py` or extend existing
- [ ] T003 [P] Create frontend tag test helpers (mock tag group data, mock suggestion data, mock API responses) in `frontend/tests/unit/helpers/tag-mocks.ts`

---

## Phase 2: Foundational (Cross-Story Verification)

**Purpose**: Verify shared infrastructure and cross-cutting behaviors that underpin all user stories.

- [ ] T004 Verify partial unique index `uq_tag_name_group` on `tags` table: confirm two tags with same name in same group raises constraint violation, while two ungrouped tags with same name are allowed — test in `src/tests/integration/intelligence/test_tag_constraints_integration.py`
- [ ] T005 [P] Verify `TagMode` value object handles invalid input gracefully (e.g., `TagMode('invalid')` raises ValueError) — test in `src/tests/unit/shared/domain/test_tag_mode.py`
- [ ] T006 [P] Verify `TagMode` serialization/deserialization round-trip in API contexts — test in `src/tests/unit/shared/domain/test_tag_mode.py`

---

## Phase 3: User Story 1 - Tag normalization after analysis (Priority: P1) 🎯 MVP

**Goal**: Verify that tag normalization correctly auto-merges, suggests, or creates tags based on similarity thresholds, and rolls back on error.

**Independent Test**: Run `NormalizeTagsUseCase` with controlled similarity scores; verify auto-merge (>= 0.95), suggestion (0.90–0.95), new-tag (< 0.90), and rollback on exception.

### Verification Tests for User Story 1

- [ ] T007 [US1] Verify auto-merge log entry: when similarity >= 0.95, `tag_auto_merged` structlog event is emitted — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T008 [P] [US1] Verify suggestion log entry: when similarity 0.90–0.95, `tag_suggestion_created` structlog event is emitted — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T009 [P] [US1] Verify new-tag log entry: when no similar tag found, `tag_created` structlog event is emitted — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T010 [US1] Verify rollback on exception: when `embed_batch` or `tag_repo.save` throws mid-processing, `commit()` is NOT called and no partial tags persist — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T011 [P] [US1] Verify embedding batch semantics: `embed_batch` is called once with all tag names (not once per tag) when processing multiple tag groups — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T012 [P] [US1] Verify threshold boundaries: test exact threshold values (0.90 exactly, 0.95 exactly) to confirm boundary behavior — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T013 [P] [US1] Verify multi-group processing: tag_groups with multiple groups and multiple tags per group — tags from different groups are compared independently — test in `src/tests/unit/modules/intelligence/application/test_normalize_tags_use_case.py`
- [ ] T014 [US1] Verify `TagNormalizationHandler` calls `tag_repo.commit()` on success and publishes `TagNormalizationCompletedEvent` — test in `src/tests/unit/modules/intelligence/application/test_tag_normalization_handler.py`
- [ ] T015 [P] [US1] Verify `TagNormalizationHandler` passes `tag_groups` correctly to use case `execute()` — test in `src/tests/unit/modules/intelligence/application/test_tag_normalization_handler.py`

**Checkpoint**: All normalization behaviors verified — auto-merge, suggestion, new-tag, rollback, logging, batch, boundaries.

---

## Phase 4: User Story 2 - Tag group definition management (Priority: P1)

**Goal**: Verify tag group CRUD, slug normalization, title-case, 409 conflict, merge, delete+ungroup, and reorder.

**Independent Test**: Create/update/merge/delete tag groups via API; verify slug normalization, conflict detection, merge dedup, delete ungrouping, and reorder.

### Verification Tests for User Story 2

- [ ] T016 [US2] Verify slug normalization on group creation: `"AI & ML"` → name `"ai_ml"`, display_name `"Ai And Ml"` — test in `backend/tests/test_tags.py`
- [ ] T017 [P] [US2] Verify 409 Conflict when creating a group with duplicate name in same topic — test in `backend/tests/test_tags.py`
- [ ] T018 [P] [US2] Verify 409 Conflict when updating a group with a name that conflicts with another group in same topic — test in `backend/tests/test_tags.py`
- [ ] T019 [US2] Verify `POST /tag-groups/merge`: tags with same name in both groups are deduplicated (article_tags transferred to surviving tag, duplicate deleted) — test in `backend/tests/test_tags.py`
- [ ] T020 [P] [US2] Verify `DELETE /tag-groups/{id}`: group deleted, tags become ungrouped (tag_group_id=null), tags and article_tags preserved — test in `backend/tests/test_tags.py`
- [ ] T021 [P] [US2] Verify `POST /tag-groups/reorder`: batch sort_order update persists correctly — test in `backend/tests/test_tags.py`
- [ ] T022 [P] [US2] Verify embedding auto-generation on group creation: new group gets a non-null embedding via the embedding service — test in `src/tests/unit/infrastructure/persistence/intelligence/test_tag_group_definition_repo.py`
- [ ] T023 [P] [US2] Verify slug normalization helper `_to_slug()`: strips whitespace, replaces non-alphanumerics with underscores, strips leading/trailing underscores — test in `backend/tests/test_tags.py`
- [ ] T024 [P] [US2] Verify title-case helper `_to_title()`: capitalizes first letter of each word — test in `backend/tests/test_tags.py`

**Checkpoint**: All tag group CRUD behaviors verified — normalization, conflict, merge, delete, reorder, embedding.

---

## Phase 5: User Story 3 - Tag CRUD and grouping (Priority: P2)

**Goal**: Verify tag rename (with embedding regeneration), delete, move, batch-move, and ungrouping.

**Independent Test**: Rename, delete, move, and batch-move tags via API; verify embedding regeneration and article_tags cleanup.

### Verification Tests for User Story 3

- [ ] T025 [US3] Verify embedding regeneration on tag rename: `PUT /tags/{id}` with new name triggers embedding re-creation — test in `backend/tests/test_tags.py`
- [ ] T026 [P] [US3] Verify `DELETE /tags/{id}`: tag and all its article_tags rows are removed — test in `backend/tests/test_tags.py`
- [ ] T027 [P] [US3] Verify moving tag to ungrouped: `PUT /tags/{id}` with tag_group_id=null sets tag as ungrouped — test in `backend/tests/test_tags.py`
- [ ] T028 [P] [US3] Verify `POST /tags/batch-move`: multiple tags moved to target group in single request — test already exists; extend to verify partial success (some tag_ids invalid) — test in `backend/tests/test_tags.py`
- [ ] T029 [P] [US3] Verify unique constraint violation when moving tag to a group that already has a tag with the same name — test in `backend/tests/test_tags.py`
- [ ] T030 [P] [US3] Verify tag dialog rename calls `renameTag` API and shows updated name — test in `frontend/tests/unit/tag-dialog.test.tsx`
- [ ] T031 [P] [US3] Verify tag dialog delete shows confirmation and calls `deleteTag` API on confirm — test already exists; extend to verify error handling on API failure — test in `frontend/tests/unit/tag-dialog.test.tsx`
- [ ] T032 [P] [US3] Verify `moveTag` API client with null group_id (ungrouping) — test in `frontend/tests/unit/tags-api.test.ts`

**Checkpoint**: All tag CRUD behaviors verified — rename+embedding, delete, move, batch-move, constraint, frontend.

---

## Phase 6: User Story 4 - Normalization suggestion review (Priority: P2)

**Goal**: Verify suggestion listing, approval (merge+cleanup), rejection (mark resolved), and bulk merge-all.

**Independent Test**: Create suggestions, approve one (verify article_tags re-pointed and new tag deleted), reject another (verify status updated), bulk-approve remaining.

### Verification Tests for User Story 4

- [ ] T033 [US4] Verify `GET /tag-normalization-suggestions`: returns only pending suggestions with tag names, group names, similarity scores — test in `backend/tests/test_tags.py`
- [ ] T034 [P] [US4] Verify `POST /tag-normalization-suggestions/{id}/approve`: article_tags re-pointed from new_tag to existing_tag, new_tag and its article_tags deleted, suggestion removed — test in `backend/tests/test_tags.py`
- [ ] T035 [P] [US4] Verify `POST /tag-normalization-suggestions/{id}/reject`: suggestion status set to "rejected", `resolved_at` and `resolved_by` recorded, both tags remain — test in `backend/tests/test_tags.py`
- [ ] T036 [US4] Verify `approveSuggestion` API client sends correct request and handles success — test in `frontend/tests/unit/tags-api.test.ts`
- [ ] T037 [P] [US4] Verify `rejectSuggestion` API client sends correct request and handles success — test in `frontend/tests/unit/tags-api.test.ts`
- [ ] T038 [P] [US4] Verify suggestion approval at repo level: `approve_suggestion` executes 3 SQL statements (INSERT article_tags redirect, DELETE old article_tags, DELETE tag) — test already exists in `src/tests/unit/infrastructure/persistence/intelligence/test_tag_repo.py`; verify it also deletes the suggestion row

**Checkpoint**: All suggestion review behaviors verified — list, approve, reject, bulk, repo-level cleanup.

---

## Phase 7: User Story 5 - Topic tag mode (Priority: P2)

**Goal**: Verify that each tag mode (unsupervised, semi_supervised, supervised) produces the correct LLM prompt and group auto-creation behavior.

**Independent Test**: Set topic to each mode, verify the analysis prompt content and group auto-creation behavior.

### Verification Tests for User Story 5

- [ ] T039 [US5] Verify unsupervised mode: `AnalyzeArticleUseCase` generates a prompt that allows free group key generation — test by verifying the prompt rendering method is called with correct mode — test in `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`
- [ ] T040 [P] [US5] Verify semi_supervised mode: prompt includes existing group keys as hints — test in `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`
- [ ] T041 [P] [US5] Verify supervised mode: prompt lists only predefined group keys as allowed values — test in `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`
- [ ] T042 [P] [US5] Verify group auto-creation in unsupervised/semi_supervised: `_upsert_generated_tag_groups` is called with new group keys — test in `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`
- [ ] T043 [P] [US5] Verify no group auto-creation in supervised: `_upsert_generated_tag_groups` is NOT called — test in `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`
- [ ] T044 [P] [US5] Verify tag mode selector UI: currently selected mode button has distinct active/selected visual state — test in `frontend/tests/unit/tag-mode-selector.test.tsx`
- [ ] T045 [P] [US5] Verify tag mode selector persists change: `onChange` callback triggers API call to update topic's tag_mode — test in `frontend/tests/unit/tag-mode-selector.test.tsx`

**Checkpoint**: All tag mode behaviors verified — prompt generation, group auto-creation, UI selection.

---

## Phase 8: User Story 6 - Frontend tag management interface (Priority: P3)

**Goal**: Verify drag-and-drop tag movement, pending changes panel, group reorder, guest paywall, and similarity visualization.

**Independent Test**: Interact with tag management UI as admin; verify drag staging, confirm/discard, group reorder, paywall, and similarity lines.

### Verification Tests for User Story 6

- [ ] T046 [US6] Verify drag-and-drop: dragging a tag from one group stages a move in the pending changes panel (does NOT immediately call API) — test in `frontend/tests/unit/tag-group-card.test.tsx`
- [ ] T047 [P] [US6] Verify pending changes confirmation: confirming staged moves calls `batchMoveTags` API with all pending moves — test in `frontend/app/tags/page.tsx` or component test
- [ ] T048 [P] [US6] Verify pending changes discard: discarding clears all staged moves and reverts to persisted state — test in `frontend/app/tags/page.tsx` or component test
- [ ] T049 [P] [US6] Verify multi-select drag: Ctrl+Click selects multiple tags; dragging all selected stages a multi-tag move — test in `frontend/app/tags/page.tsx` or component test
- [ ] T050 [P] [US6] Verify group reorder drag: dragging group handle triggers `reorderTagGroups` API call — test in `frontend/app/tags/page.tsx` or component test
- [ ] T051 [P] [US6] Verify guest paywall: unauthenticated user sees fake group data behind blur overlay; real tag data is NOT fetched — test in `frontend/app/tags/page.tsx` or component test
- [ ] T052 [P] [US6] Verify similarity visualization: SVG lines between similar groups (cosine >= 0.90) with hover tooltips showing similarity score and merge button — test in `frontend/app/tags/page.tsx` or component test
- [ ] T053 [P] [US6] Verify merge group dialog: pre-fills from source group, normalizes name to slug on input, display_name to title on blur — test in `frontend/app/tags/page.tsx` or component test

**Checkpoint**: All frontend tag management behaviors verified — drag, staging, paywall, similarity, merge dialog.

---

## Phase 9: User Story 7 - Backfill and maintenance operations (Priority: P3)

**Goal**: Verify backfill scripts correctly retroactively tag articles, generate embeddings, create missing group definitions, and scan for suggestions.

**Independent Test**: Run each backfill script against a controlled dataset; verify expected data changes.

### Verification Tests for User Story 7

- [ ] T054 [US7] Verify `backfill_tags.py`: articles with analyses but no article_tags are re-analyzed and tagged — test in `scripts/tests/test_backfill_tags.py` (extend existing)
- [ ] T055 [P] [US7] Verify `backfill_tag_embeddings.py`: tags and tag_group_definitions with null embeddings get embeddings generated — test in `scripts/tests/test_backfill_tag_embeddings.py` (new file)
- [ ] T056 [P] [US7] Verify `backfill_tag_group_definitions.py`: orphan group names without tag_group_definitions rows get auto-created with display_name `"{name}_unsupervised"` — test in `scripts/tests/test_backfill_tag_group_definitions.py` (new file)
- [ ] T057 [P] [US7] Verify `backfill_tag_suggestions.py`: pairwise cosine similarity scan creates `TagNormalizationSuggestion` records for pairs above 0.85 threshold, even for pairs above auto_merge threshold — test in `scripts/tests/test_backfill_tag_suggestions.py` (new file)
- [ ] T058 [P] [US7] Verify `audit_tag_groups.py`: reports orphan group names and casing variant duplicates — test in `scripts/tests/test_audit_tag_groups.py` (new file)
- [ ] T059 [P] [US7] Verify `backfill_tags.py` dry-run mode: `--dry-run` prints planned changes without writing — test in `scripts/tests/test_backfill_tags.py` (extend existing)

**Checkpoint**: All backfill behaviors verified — tag, embedding, group definition, suggestion, audit, dry-run.

---

## Phase 10: Integration Tests (Cross-Story)

**Purpose**: Verify end-to-end tag management flows against a real database.

- [ ] T060 Verify full normalization pipeline integration: scrape → analyze → normalize → verify auto-merge/suggestion/new-tag with real embeddings and pgvector similarity — test in `src/tests/integration/intelligence/test_tag_normalization_integration.py` (new file)
- [ ] T061 [P] Verify suggestion approval integration: create suggestion, approve, confirm article_tags re-pointed, new_tag deleted, against real DB — test in `src/tests/integration/intelligence/test_tag_normalization_integration.py`
- [ ] T062 [P] Verify group merge integration: merge two groups, confirm tag deduplication and article_tags consolidation against real DB — test in `src/tests/integration/intelligence/test_tag_group_operations_integration.py` (new file)
- [ ] T063 [P] Verify group delete integration: delete group, confirm tags ungrouped but preserved against real DB — test in `src/tests/integration/intelligence/test_tag_group_operations_integration.py`

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Auth verification, error handling, and documentation.

- [ ] T064 [P] Verify admin-only auth on tag group write endpoints: `POST /tag-groups`, `PUT /tag-groups/{id}`, `DELETE /tag-groups/{id}`, `POST /tag-groups/merge`, `POST /tag-groups/reorder` return 401/403 for non-admin — test in `backend/tests/test_tags.py`
- [ ] T065 [P] Verify admin-only auth on tag write endpoints: `PUT /tags/{id}`, `DELETE /tags/{id}`, `POST /tags/batch-move` return 401/403 for non-admin — test in `backend/tests/test_tags.py`
- [ ] T066 [P] Verify admin-only auth on suggestion endpoints: `GET /tag-normalization-suggestions`, `POST /.../approve`, `POST /.../reject` return 401/403 for non-admin — test in `backend/tests/test_tags.py`
- [ ] T067 [P] Verify tag dialog error handling: API failure on rename/delete shows error feedback to user — test in `frontend/tests/unit/tag-dialog.test.tsx`
- [ ] T068 [P] Verify tag mode selector error handling: API failure on mode change shows error feedback — test in `frontend/tests/unit/tag-mode-selector.test.tsx`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) for shared fixtures
- **User Stories (Phase 3–9)**: All depend on Foundational phase completion
  - US1, US2 (both P1) can proceed in parallel
  - US3, US4, US5 (all P2) can proceed in parallel after P1 stories
  - US6, US7 (both P3) can proceed after P2 stories
- **Integration (Phase 10)**: Depends on US1 and US2 unit tests passing
- **Polish (Phase 11)**: Depends on all user story phases completing

### User Story Dependencies

- **US1 (P1)**: Independent — tag normalization use case
- **US2 (P1)**: Independent — tag group CRUD API
- **US3 (P2)**: Depends on US2 for group fixture patterns, but independently testable
- **US4 (P2)**: Independent — suggestion review
- **US5 (P2)**: Independent — tag mode
- **US6 (P3)**: Depends on US2/US3 for understanding API contracts, but independently testable
- **US7 (P3)**: Independent — backfill scripts

### Within Each User Story

- Backend tests before frontend tests (API contracts drive UI)
- Repo-level tests before API-level tests
- Unit tests before integration tests
- Happy path before error cases

### Parallel Opportunities

- All tasks marked [P] within the same phase can run in parallel
- US1 and US2 phases can run entirely in parallel (different files)
- US3, US4, US5 phases can run in parallel (different files)
- US6 and US7 phases can run in parallel (different files)
- Integration tests T060–T063 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all normalization verification tests together:
Task T007: "Verify auto-merge log entry in test_normalize_tags_use_case.py"
Task T008: "Verify suggestion log entry in test_normalize_tags_use_case.py"
Task T009: "Verify new-tag log entry in test_normalize_tags_use_case.py"
Task T011: "Verify embedding batch semantics in test_normalize_tags_use_case.py"
Task T012: "Verify threshold boundaries in test_normalize_tags_use_case.py"
Task T013: "Verify multi-group processing in test_normalize_tags_use_case.py"
Task T015: "Verify handler passes tag_groups correctly in test_tag_normalization_handler.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all group CRUD verification tests together:
Task T016: "Verify slug normalization in backend/tests/test_tags.py"
Task T017: "Verify 409 Conflict on create in backend/tests/test_tags.py"
Task T018: "Verify 409 Conflict on update in backend/tests/test_tags.py"
Task T023: "Verify _to_slug helper in backend/tests/test_tags.py"
Task T024: "Verify _to_title helper in backend/tests/test_tags.py"
Task T022: "Verify embedding auto-generation in test_tag_group_definition_repo.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (shared fixtures)
2. Complete Phase 2: Foundational (constraints, TagMode)
3. Complete Phase 3: US1 verification tests
4. **STOP and VALIDATE**: Run `make test` — all US1 tests must pass
5. Tag normalization behavior confirmed

### Incremental Delivery

1. Setup + Foundational → Infrastructure verified
2. Add US1 → Test → Tag normalization confirmed (MVP!)
3. Add US2 → Test → Tag group CRUD confirmed
4. Add US3 + US4 + US5 → Test → Tag operations + suggestions + modes confirmed
5. Add US6 + US7 → Test → Frontend + backfill confirmed
6. Integration + Polish → Full coverage

---

## Notes

- Brownfield: all tasks are verification tests — no new feature implementation
- Existing tests should be EXTENDED, not replaced
- New test files are created only where no relevant test file exists
- Integration tests require a running postgres (via `make test-integration`)
- Frontend page-level tests (US6) may require component extraction for testability
- Backfill script tests (US7) use the script entry points directly with mocked LLM/DB
- [P] tasks target different test files or different describe blocks — no file conflicts
