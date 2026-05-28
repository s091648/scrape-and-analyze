# Tasks: Article Collection — Brownfield Verification

**Input**: Design documents from `specs/001-article-collection/`

**Nature**: Brownfield verification — all production code already exists. Tasks add or confirm
test coverage so that each FR and spec scenario is provably satisfied by the existing implementation.

**Run all tests inside Docker**: `make test` (unit) · `make test-integration` (integration)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story this task belongs to (US1–US4)

---

## Phase 1: Baseline (no story label)

**Purpose**: Confirm the existing test suite passes cleanly before adding new coverage.

- [x] T001 Run `make test` inside Docker and confirm all unit tests pass with zero failures
- [ ] T002 Run `make test-integration` inside Docker and confirm all integration tests pass

**Checkpoint**: Green baseline established — all new tasks must keep these suites green.

---

## Phase 2: User Story 1 — New Articles Discovered and Stored (Priority: P1) 🎯

**Goal**: Every source type discovers articles, fetches content, and the pipeline stores
them — verified by tests that exercise actual scraper + executor + event flow.

**Independent Test**: `uv run pytest src/tests/unit/infrastructure/collection/scrapers/ src/tests/integration/test_full_flow.py -v`

### US1 — RSS Scraper

- [x] T003 [P] [US1] In `src/tests/unit/infrastructure/collection/scrapers/test_rss_scraper.py`, verify an existing test asserts that keyword match checks **both title and description** (FR-003); if absent, add `test_discover_matches_on_description_when_title_misses`
- [x] T004 [P] [US1] In `src/tests/unit/infrastructure/collection/scrapers/test_rss_scraper.py`, add `test_discover_accepts_all_when_keywords_empty_list` — construct `RssScraper(keywords=[])` and assert all entries are returned regardless of content (FR-003 no-filter path)

### US1 — ArXiv Scraper

- [x] T005 [P] [US1] In `src/tests/unit/infrastructure/collection/scrapers/test_arxiv_scraper.py`, verify `test_fetch_uses_sections_and_sets_pdf_available_true` covers FR-007 (PDF extraction returns sections); confirm test doc-string or comment references FR-007
- [x] T006 [P] [US1] In `src/tests/unit/infrastructure/collection/scrapers/test_arxiv_scraper.py`, verify `test_fetch_falls_back_to_abstract_when_pdf_fails` covers the fallback scenario from FR-007 assumptions

### US1 — Blog Scraper

- [x] T007 [P] [US1] In `src/tests/unit/infrastructure/collection/scrapers/test_blog_scraper.py`, verify `test_blog_scraper_removes_nav_footer_from_content` covers FR-006 (nav/footer/script removal produces plain text); confirm the assertion checks sanitised output
- [x] T008 [P] [US1] In `src/tests/unit/infrastructure/collection/scrapers/test_blog_scraper.py`, verify `test_blog_scraper_discover_returns_empty_when_listing_fetch_fails` covers FR-013 (listing fetch failure returns empty list, no exception raised)

### US1 — Event Publication

- [x] T009 [US1] In `src/tests/unit/infrastructure/collection/executor/test_scrape_dispatcher.py`, verify `test_pipeline_publishes_events_for_each_scraped_article` asserts that one `ArticleScrapedEvent` per scraped article is published to the event bus (FR-008); if the assertion is missing, add it

**Checkpoint**: US1 — all unit tests pass; `make test` stays green.

---

## Phase 3: User Story 2 — Duplicate Articles Are Skipped (Priority: P2)

**Goal**: URL-hash dedup prevents re-storage; articles without analysis are forwarded, not dropped.

**Independent Test**: `uv run pytest src/tests/integration/test_process_article.py -v`

- [x] T010 [P] [US2] In `src/tests/integration/test_process_article.py`, verify `test_process_article_returns_false_for_fully_processed_duplicate` asserts outcome is `DUPLICATE` (FR-004) and no new Article row is created
- [x] T011 [P] [US2] In `src/tests/integration/test_process_article.py`, verify `test_process_article_analyzes_duplicate_missing_analysis` asserts outcome is `DUPLICATE_NEEDS_ANALYSIS` (FR-005) and the existing Article row is returned for downstream analysis — not a new row
- [x] T012 [US2] In `src/tests/unit/modules/collection/application/test_article_scraped_handler.py`, verify `test_handle_duplicate_article_records_duplicate_and_returns_true` confirms that when `ProcessScrapedArticleUseCase` returns `DUPLICATE`, no event is published downstream; add assertion if absent

**Checkpoint**: US2 — dedup integration tests pass; `make test-integration` stays green.

---

## Phase 4: User Story 3 — Source Failures Do Not Halt the Pipeline (Priority: P3)

**Goal**: Individual source and article failures are isolated — pipeline continues; arXiv 429
aborts remaining arXiv discovers but not other sources.

**Independent Test**: `uv run pytest src/tests/unit/infrastructure/collection/scrapers/test_rss_scraper.py src/tests/unit/infrastructure/collection/executor/ -v`

### US3 — Per-source error isolation

- [x] T013 [P] [US3] In `src/tests/unit/infrastructure/collection/scrapers/test_rss_scraper.py`, verify `test_discover_returns_empty_on_http_error` and `test_discover_returns_empty_on_network_exception` cover FR-013 — exception is swallowed and empty list returned (not re-raised)

### US3 — ArXiv 429 abort mechanism

- [x] T014 [US3] In `src/tests/unit/infrastructure/collection/executor/` add `test_executor_aborts_arxiv_on_rate_limit.py`:
  - Construct `ScrapeExecutor` with two `DiscoverTask`s for the same arXiv host
  - First discover raises `ArxivRateLimitedError`
  - Assert second discover is **never called** (host is in `_aborted_hosts`)
  - Assert `on_discover_failed` callback is invoked for both tasks (first: real error; second: skipped)
  - This covers FR-011 end-to-end in the executor layer
- [x] T015 [US3] In the same new test file, add `test_executor_non_arxiv_source_unaffected_by_arxiv_429`:
  - Combine one arXiv `DiscoverTask` (raises 429) with one RSS `DiscoverTask` (succeeds)
  - Assert RSS discover still executes and produces fetch tasks (FR-011 scope: arXiv only)

**Checkpoint**: US3 — all executor and scraper error tests pass; `make test` stays green.

---

## Phase 5: User Story 4 — Per-Host Concurrency Is Bounded (Priority: P4)

**Goal**: At most one concurrent request per hostname; fetch delay applied between fetches;
streaming mode runs discover and fetch concurrently.

**Independent Test**: `uv run pytest src/tests/unit/infrastructure/collection/executor/ -v`

### US4 — Per-host semaphore

- [x] T016 [P] [US4] In `src/tests/unit/infrastructure/collection/executor/test_worker.py`, verify `test_executor_respects_per_host_exclusion` confirms that two tasks for the same host are **never executing simultaneously** (FR-009); strengthen assertion to check temporal ordering if only order is currently asserted

### US4 — Fetch delay

- [x] T017 [P] [US4] In `src/tests/unit/infrastructure/collection/executor/test_worker.py`, add `test_executor_applies_fetch_delay_between_fetches`:
  - Mock `time.sleep` and configure `ScrapeExecutor(fetch_delay=2.0)`
  - Submit two fetch tasks for the same worker
  - Assert `time.sleep(2.0)` was called at least once after each successful fetch (FR-010)

### US4 — Streaming mode

- [x] T018 [US4] In `src/tests/unit/infrastructure/collection/executor/` add `test_scrape_executor_streaming.py`:
  - Test `run_streaming()` with two `DiscoverTask`s producing one `FetchTask` each
  - Assert discover and fetch both execute (not just mocked at pipeline level)
  - Assert `on_result` callback is called for each successfully fetched article (FR-014)
  - Use `threading.Event` or mock `time.sleep` to control timing without real delays

**Checkpoint**: US4 — executor concurrency and streaming tests pass; `make test` stays green.

---

## Phase 6: Polish & End-to-End Confirmation

**Purpose**: Confirm all success criteria hold against real integration test DB.

- [ ] T019 [P] Run `make test-integration` and verify `test_full_flow.py` exercises the complete Discover → Fetch → Event → Store path (SC-001); add a one-line comment referencing SC-001 if absent
- [ ] T020 [P] Run `make test-integration` and confirm `test_error_handling.py` covers failure recording (SC-002 proxy: a failed source does not prevent other sources from storing articles)
- [x] T021 Run `make test` to confirm overall unit test coverage has not regressed; check that newly added test files are picked up by pytest discovery

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Baseline)**: No dependencies — run first
- **Phase 2–5 (User Stories)**: Depend on Phase 1 green baseline; stories can run in parallel
- **Phase 6 (Polish)**: Depends on Phases 2–5 complete

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories
- **US2 (P2)**: No dependency on US1 (dedup logic is independent)
- **US3 (P3)**: No dependency on US1/US2
- **US4 (P4)**: No dependency on US1/US2/US3

### Within Each User Story

- [P] tasks can run in parallel (different files)
- New test files (T014, T015, T017, T018) must be written before their verify-pass step
- All tasks must keep `make test` green

---

## Parallel Example: US3 Executor Tasks

```bash
# T013 and T014/T015 touch different files — can run in parallel:
Task T013: verify test_rss_scraper.py error isolation
Task T014+T015: write test_executor_aborts_arxiv_on_rate_limit.py (new file)
```

---

## Implementation Strategy

### MVP Verification (Phase 1 + US1 only)

1. Complete Phase 1 baseline (T001, T002)
2. Complete US1 tasks (T003–T009)
3. **Validate**: `make test` passes — core discovery and fetch behaviour is verified
4. Stop here if only US1 confirmation is needed

### Full Verification (All Stories)

1. Phase 1 → US1 → US2 → US3 → US4 → Phase 6
2. Stories can proceed in parallel once Phase 1 is green
3. Each story adds test coverage without modifying production code

---

## Coverage Gap Summary (Tasks Added to Fill These)

| Gap | FR | Task |
|-----|----|------|
| `keywords=[]` → accept all not tested | FR-003 | T004 |
| `ScrapeExecutor._aborted_hosts` after 429 not tested | FR-011 | T014, T015 |
| `fetch_delay` not behaviourally asserted | FR-010 | T017 |
| `run_streaming()` not tested end-to-end (only mocked) | FR-014 | T018 |

## Notes

- [P] tasks = different files, no shared state — safe to parallelize
- **No production code changes** — all tasks modify only `src/tests/`
- Run tests with `docker compose exec test_service uv run pytest <path> -v` for single-file runs
- `make test` runs the full unit suite; `make test-integration` requires local postgres
