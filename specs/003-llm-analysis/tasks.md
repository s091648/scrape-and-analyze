# Tasks: LLM Article Analysis

**Input**: Design documents from `specs/003-llm-analysis/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/llm-service.md ✓

**Scope**: Production code is already implemented. All tasks here are **test tasks** — filling coverage gaps identified by pre-task audit. Each task adds tests that verify the corresponding spec acceptance scenario.

**Audit summary**:

| Component | Status |
|-----------|--------|
| AnalyzeArticleUseCase | Partial — missing ArXiv truncation, no-topic-id, token recording |
| AnalysisPrompt value object | Partial — missing supervised + unsupervised template tests |
| ResilientLLMService | Comprehensive ✓ |
| SlidingWindowStrategy | **CRITICAL — zero behavioral tests** |
| GeminiProvider | **CRITICAL — no test file at all** |
| ClaudeProvider | Good ✓ |
| OpenRouterProvider | Minimal — missing retry logic test |
| BaseProvider | Partial — missing retry + validation flow tests |
| SqlAlchemyAnalysisRepository | Integration-only ✓ |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to user stories from spec.md (US1–US5)

---

## Phase 1: Setup

*No new project structure needed — all source files exist.*

- [ ] T001 Verify test directory structure: confirm `src/tests/unit/infrastructure/intelligence/llm/rate_limit/` and `src/tests/unit/infrastructure/intelligence/llm/providers/` exist and have `__init__.py`

---

## Phase 2: Foundational

*No blocking foundational work — existing conftest and fixtures are reusable.*

**Checkpoint**: Ready to write tests for each user story.

---

## Phase 3: User Story 1 — Analyze a Scraped Article (Priority: P1) 🎯 MVP

**Goal**: Verify that the core analysis path — LLM call → structured result → persistence — is correctly covered for all acceptance scenarios in US1.

**Independent Test**: `make test` passes with new tests; `uv run pytest src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py -v` shows green.

- [ ] T002 [P] [US1] Add `test_arxiv_content_truncated_to_15000_chars` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — assert that when `article.source == "arxiv"` and content exceeds 15000 chars, `llm_service.analyze()` receives at most 15000 chars
- [ ] T003 [P] [US1] Add `test_analysis_metadata_recorded_on_success` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — assert `analysis.analysis_metadata.model_used`, `input_tokens`, and `output_tokens` are non-null after successful execution
- [ ] T004 [P] [US1] Add `test_no_topic_id_uses_all_active_topics_auto_mode` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — assert that an article with `topic_id=None` causes all active topics to be merged into the prompt (auto-mode path)

**Checkpoint**: US1 acceptance scenarios fully covered by unit tests.

---

## Phase 4: User Story 2 — Topic-Mode Aware Tagging (Priority: P1)

**Goal**: Verify that each of the three tagging modes (SUPERVISED / SEMI_SUPERVISED / UNSUPERVISED) and the no-topic fallback produce the correct prompt variant and tag group behavior.

**Independent Test**: `uv run pytest src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py -v` passes.

- [ ] T005 [P] [US2] Add `test_render_auto_fills_topic_name` to `src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py` — assert `render_auto(topic)` returns an `AnalysisPrompt` whose text contains the topic's display name and the free-classification instruction
- [ ] T006 [P] [US2] Add `test_render_fixed_constrains_to_predefined_keys` to `src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py` — assert `render_fixed(topic, tag_groups)` includes each tag group key in the rendered prompt and contains the "predefined tag groups" instruction
- [ ] T007 [US2] Add `test_supervised_fallback_to_auto_when_no_tag_groups` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — given a SUPERVISED topic with an empty tag group list, assert the use case falls back to auto-mode prompt (not an error)
- [ ] T008 [US2] Add `test_unsupervised_mode_upserts_new_tag_groups_with_embedding` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — assert that for UNSUPERVISED mode, generated tag group names are passed to the embedding service and upserted via `tag_group_definition_repository`

**Checkpoint**: All three tagging modes and the no-topic path covered.

---

## Phase 5: User Story 3 — Provider Fallback on Rate Limit or Failure (Priority: P2)

**Goal**: Verify that GeminiProvider behaves correctly (including quota detection) and that the fallback chain handles malformed JSON responses.

**Independent Test**: `uv run pytest src/tests/unit/infrastructure/intelligence/llm/providers/test_gemini_provider.py -v` passes (new file).

- [ ] T009 [US3] Create `src/tests/unit/infrastructure/intelligence/llm/providers/test_gemini_provider.py` with the following tests (mirror ClaudeProvider test structure):
  - `test_gemini_provider_calls_api_and_returns_analysis_tuple` — happy path with mocked `google.genai.Client`
  - `test_gemini_provider_strips_markdown_code_block_before_parsing` — assert response wrapped in ` ```json ... ``` ` is correctly parsed
  - `test_gemini_provider_detects_daily_quota_exhaustion_and_raises` — assert exception containing `"RESOURCE_EXHAUSTED"` + `"PerDay"` raises `RateLimitExhausted`
  - `test_gemini_provider_tracks_input_and_output_tokens` — assert `AnalysisMetadata` token counts match `usage_metadata`
  - `test_gemini_provider_returns_none_on_invalid_json` — assert malformed JSON response returns `None` (no exception)
  - `test_gemini_provider_returns_none_on_missing_required_fields` — assert response missing `"summary"` or `"tag_groups"` returns `None`
  - `test_gemini_provider_retries_on_transient_api_error` — assert non-quota API error is retried up to max attempts
- [ ] T010 [P] [US3] Add `test_provider_returning_none_triggers_fallback_to_next` to `src/tests/unit/infrastructure/intelligence/llm/test_resilient_llm_service_extended.py` — explicitly test the `None` return path (provider parses OK but returns None after validation failure) causes the service to try the next handler, not return None immediately

**Checkpoint**: GeminiProvider fully tested; fallback-on-None path explicitly verified.

---

## Phase 6: User Story 4 — Rate-Limit Enforcement Per Provider (Priority: P2)

**Goal**: Create behavioral unit tests for `SlidingWindowStrategy` — the most critical gap (zero tests today).

**Independent Test**: `uv run pytest src/tests/unit/infrastructure/intelligence/llm/rate_limit/test_sliding_window_strategy.py -v` passes (new file).

- [ ] T011 [US4] Create `src/tests/unit/infrastructure/intelligence/llm/rate_limit/test_sliding_window_strategy.py` with the following tests:
  - `test_rpm_allows_requests_within_limit` — assert N requests within 60s window succeed without blocking when RPM=N
  - `test_rpm_blocks_when_window_full` — assert that after N requests, `acquire()` sleeps until the oldest request exits the 60s window (mock `time.sleep` and `time.time` to verify)
  - `test_tpm_blocks_when_token_budget_exhausted` — assert that `acquire(estimated_tokens)` sleeps when cumulative token estimate exceeds TPM
  - `test_record_usage_updates_token_window_with_actual_tokens` — assert that `record_usage(actual)` adds a token entry to the window deque
  - `test_rpd_raises_rate_limit_exhausted_when_exceeded` — assert that the (RPD+1)th `acquire()` call raises `RateLimitExhausted` immediately
  - `test_eviction_removes_entries_older_than_60s` — assert that events older than 60s are removed from deque on next `acquire()`, freeing quota
  - `test_noop_strategy_acquire_and_record_do_not_raise` — assert `NoOpStrategy` allows unlimited calls (already partially covered; add explicit throughput assertion)

**Checkpoint**: Rate-limit enforcement logic fully unit-tested; no DB or LLM provider required.

---

## Phase 7: User Story 5 — Analysis Failure Isolation (Priority: P3)

**Goal**: Verify that embedding failures and combined provider+DB failures are properly isolated and do not propagate exceptions to callers.

**Independent Test**: `uv run pytest src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py -k "failure or embedding" -v` passes.

- [ ] T012 [P] [US5] Add `test_embedding_failure_does_not_block_analysis_persistence` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — given an embedding service that raises an exception, assert `AnalysisResult.success == True` and the analysis is still saved (embedding error is only a warning)
- [ ] T013 [P] [US5] Add `test_all_providers_exhausted_returns_failure_result_with_llm_error_type` to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` — mock `llm_service.analyze()` to return `None` (simulating all providers exhausted) and assert `AnalysisResult(success=False, exception_type="LLMAnalysisError")`

**Checkpoint**: All five spec user stories have complete unit test coverage.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T014 Run `make test` (Docker) and confirm all new unit tests pass with zero failures
- [ ] T015 Run `make test-integration` and confirm existing integration tests still pass (no regressions)
- [ ] T016 [P] Add `test_openrouter_provider_retries_on_transient_http_error` to `src/tests/unit/infrastructure/intelligence/llm/providers/test_openrouter_provider.py` — assert that a non-200 transient error (e.g., 500) triggers retry logic consistent with BaseProvider behavior

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: No-op — proceed immediately
- **Phase 3–7 (User Stories)**: Independent of each other (different files); can run in parallel
- **Phase 8 (Polish)**: T014/T015 depend on T001–T013 all being complete

### User Story Dependencies

- **US1 (T002–T004)**: Independent — only touches `test_analyze_article_use_case.py`
- **US2 (T005–T008)**: Independent — touches `test_analysis_prompt.py` + `test_analyze_article_use_case.py`
- **US3 (T009–T010)**: Independent — new file + existing extended file
- **US4 (T011)**: Independent — new file in rate_limit directory
- **US5 (T012–T013)**: Independent — only touches `test_analyze_article_use_case.py`

### Within Each User Story

- Tasks marked [P] within a story have no file conflicts — safe to dispatch in parallel
- T007 and T008 both modify `test_analyze_article_use_case.py` — write sequentially
- T012 and T013 both modify `test_analyze_article_use_case.py` — write sequentially

---

## Parallel Example: US4 (SlidingWindowStrategy)

```
# All tests in T011 can be developed together in a single new file:
Task: "test_rpm_allows_requests_within_limit"
Task: "test_rpm_blocks_when_window_full"
Task: "test_tpm_blocks_when_token_budget_exhausted"
Task: "test_record_usage_updates_token_window_with_actual_tokens"
Task: "test_rpd_raises_rate_limit_exhausted_when_exceeded"
Task: "test_eviction_removes_entries_older_than_60s"
Task: "test_noop_strategy_acquire_and_record_do_not_raise"
```

## Parallel Example: US3 (GeminiProvider)

```
# All tests in T009 are in a single new file:
Task: "test_gemini_provider_calls_api_and_returns_analysis_tuple"
Task: "test_gemini_provider_strips_markdown_code_block_before_parsing"
Task: "test_gemini_provider_detects_daily_quota_exhaustion_and_raises"
Task: "test_gemini_provider_tracks_input_and_output_tokens"
Task: "test_gemini_provider_returns_none_on_invalid_json"
Task: "test_gemini_provider_returns_none_on_missing_required_fields"
Task: "test_gemini_provider_retries_on_transient_api_error"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete T001 (Setup check)
2. Complete T002–T004 (US1 tests)
3. Run `make test` — validate US1 passes
4. Proceed to remaining user stories

### Incremental Delivery

1. T001 → T002–T004 (US1) → `make test` ✓
2. T005–T008 (US2) → `make test` ✓
3. T009–T010 (US3, GeminiProvider) → `make test` ✓
4. T011 (US4, SlidingWindowStrategy) → `make test` ✓
5. T012–T013 (US5) → `make test` ✓
6. T014–T016 (Polish) → `make test` + `make test-integration` ✓

### Full Parallel Strategy (single session)

With `speckit-implement` subagent-driven:

1. T001 first
2. Dispatch T002–T004, T005–T006, T009, T011 in parallel (all different files)
3. T007, T008, T010, T012, T013 sequentially (shared files)
4. T014–T016 after all above complete

---

## Notes

- [P] tasks = different files, no shared state, safe to parallelize
- Each user story is independently testable via targeted pytest run
- All tests are **unit tests** (no DB required) except T015 (`make test-integration`)
- Constitution requires: unit tests via `make test` (Docker); never bare `uv run pytest` for CI acceptance
- `uv run pytest` is permitted locally for IDE feedback during development
