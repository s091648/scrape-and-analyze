# Tasks: Observability

**Input**: Design documents from `/specs/006-observability/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/logging-contract.md, quickstart.md

**Tests**: Brownfield verification — tasks are primarily test-writing to confirm existing behavior matches spec.

**Organization**: Tasks grouped by user story. Each story validates a slice of the existing observability stack.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Phase 1: Setup (No-Op Fallback Baseline)

**Purpose**: Establish test infrastructure and verify the core graceful degradation guarantee before validating individual components.

- [ ] T001 Create test file `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` with imports and fixtures for testing OTel metrics no-op behavior
- [ ] T002 [P] Create test file `src/tests/unit/infrastructure/shared/observability/test_otel_tracing_noop.py` with imports and fixtures for testing OTel tracing no-op behavior
- [ ] T003 [P] Create test file `src/tests/unit/infrastructure/shared/observability/test_loki_logging.py` with imports and fixtures for testing Loki logging no-op and configured behavior
- [ ] T004 [P] Create test file `src/tests/unit/infrastructure/shared/notifications/test_notification_build.py` with imports and fixtures for testing `build_notification_handler()` with Telegram enabled
- [ ] T005 [P] Create test file `src/tests/unit/infrastructure/shared/observability/test_sentry_init.py` with imports and fixtures for testing Sentry initialization in CLI entrypoints
- [ ] T006 [P] Create test file `frontend/__tests__/lib/loki-logger.test.ts` with imports and fixtures for testing frontend Loki logger

---

## Phase 2: Foundational (No-Op Fallback Tests — Constitution VI)

**Purpose**: Verify the constitutionally mandated graceful degradation — every observability component must not crash the app when unconfigured.

**⚠️ CRITICAL**: These tests validate the core architectural guarantee (Constitution VI) that all downstream stories depend on.

- [ ] T007 Write test `test_dummy_counter_add_is_noop` in `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` — verify `_Dummy.add()` does not raise and returns None
- [ ] T008 [P] Write test `test_dummy_histogram_record_is_noop` in `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` — verify `_Dummy.record()` does not raise and returns None
- [ ] T009 [P] Write test `test_metrics_setup_returns_none_without_env` in `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` — verify that when `GRAFANA_OTLP_*` env vars are missing, all 6 metric objects become `_Dummy` instances
- [ ] T010 [P] Write test `test_tracer_is_noop_without_env` in `src/tests/unit/infrastructure/shared/observability/test_otel_tracing_noop.py` — verify `get_tracer()` returns a no-op tracer when `GRAFANA_OTLP_*` env vars are missing
- [ ] T011 [P] Write test `test_shutdown_tracing_safe_without_provider` (already exists in `test_tracing.py` — verify it still passes; add `test_start_span_noop_without_provider` to confirm `start_as_current_span()` does not raise)
- [ ] T012 [P] Write test `test_loki_handler_not_attached_without_env` in `src/tests/unit/infrastructure/shared/observability/test_loki_logging.py` — verify only stdout handler is attached when `GRAFANA_LOKI_*` env vars are missing
- [ ] T013 [P] Write test `test_sentry_not_initialized_without_dsn` in `src/tests/unit/infrastructure/shared/observability/test_sentry_init.py` — verify `sentry_sdk.init()` is not called when `SENTRY_DSN` is empty
- [ ] T014 [P] Write test `test_build_notification_handler_without_env` in `src/tests/unit/infrastructure/shared/notifications/test_notification_build.py` — verify `build_notification_handler()` returns handler with empty notifiers list when `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is missing
- [ ] T015 [P] Write test `test_push_to_loki_returns_early_without_env` in `frontend/__tests__/lib/loki-logger.test.ts` — verify `pushToLoki()` returns immediately when `GRAFANA_LOKI_URL` is missing

**Checkpoint**: All no-op fallback tests pass — constitution VI guarantee is verified for every component.

---

## Phase 3: User Story 1 — Operator Monitors Scraping Pipeline Health (Priority: P1) 🎯 MVP

**Goal**: Verify OTel metrics instruments emit correct values on pipeline completion.

**Independent Test**: Run `make test` and confirm all metric tests pass — no OTel backend required.

- [ ] T016 [US1] Write test `test_otel_metrics_handler_increments_all_counters` in `src/tests/unit/modules/collection/application/test_otel_metrics_handler.py` — extend existing test to verify all three counters (new, duplicate, errors) are called with correct values and `{"source": ...}` attributes for multiple sources
- [ ] T017 [P] [US1] Write test `test_scraper_runs_counter_incremented_on_start` in `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` — verify `SCRAPER_RUNS.add(1)` is called in the CLI entrypoint (mock the counter)
- [ ] T018 [P] [US1] Write test `test_scraper_duration_recorded_on_exit` in `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` — verify `SCRAPER_DURATION.record(duration)` is called in the CLI entrypoint finally block (mock the histogram)
- [ ] T019 [P] [US1] Write test `test_push_metrics_called_on_exit` in `src/tests/unit/infrastructure/shared/observability/test_otel_metrics_noop.py` — verify `push_metrics()` is called during process shutdown

**Checkpoint**: OTel metrics behavior fully verified — 6 instruments + handler + teardown.

---

## Phase 4: User Story 2 — Operator Investigates Issues via Structured Logs (Priority: P1)

**Goal**: Verify all log entries are valid JSON with required fields (level, timestamp, correlation_id).

**Independent Test**: Run `make test` and confirm structured logging tests pass.

- [ ] T020 [US2] Write test `test_log_entry_has_level_field` in `src/tests/unit/infrastructure/shared/observability/test_observability.py` — verify every log entry contains `level` field matching the severity
- [ ] T021 [P] [US2] Write test `test_log_entry_has_iso8601_timestamp` in `src/tests/unit/infrastructure/shared/observability/test_observability.py` — verify `timestamp` field is valid ISO 8601 format
- [ ] T022 [P] [US2] Write test `test_correlation_id_bound_across_log_entries` in `src/tests/unit/infrastructure/shared/observability/test_observability.py` — verify multiple log entries within a single run share the same `correlation_id` after `bind_correlation_id()` is called
- [ ] T023 [P] [US2] Write test `test_loki_handler_attached_with_env` in `src/tests/unit/infrastructure/shared/observability/test_loki_logging.py` — verify LokiHandler is attached to root logger when all `GRAFANA_LOKI_*` env vars are set (mock `logging_loki` import)
- [ ] T024 [P] [US2] Write test `test_stdout_handler_always_attached` in `src/tests/unit/infrastructure/shared/observability/test_loki_logging.py` — verify a StreamHandler(sys.stdout) is always attached regardless of Loki configuration

**Checkpoint**: Structured logging contract fully verified — JSON format, correlation, Loki transport.

---

## Phase 5: User Story 3 — Operator Receives Pipeline Completion Notifications (Priority: P2)

**Goal**: Verify Telegram notifier sends correctly formatted messages and fault isolation works.

**Independent Test**: Run `make test` and confirm Telegram notification tests pass.

- [ ] T025 [US3] Write test `test_build_notification_handler_with_telegram_env` in `src/tests/unit/infrastructure/shared/notifications/test_notification_build.py` — verify `build_notification_handler()` creates a `TelegramNotifier` when both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set
- [ ] T026 [P] [US3] Write test `test_telegram_notifier_posts_to_correct_url` in `src/tests/unit/infrastructure/shared/notifications/test_telegram_notifier.py` — verify the POST URL matches `https://api.telegram.org/bot{token}/sendMessage`
- [ ] T027 [P] [US3] Write test `test_telegram_notifier_sends_markdownv2` in `src/tests/unit/infrastructure/shared/notifications/test_telegram_notifier.py` — verify `parse_mode="MarkdownV2"` is in the POST payload
- [ ] T028 [P] [US3] Write test `test_notification_handler_catches_notifier_exception` in `src/tests/unit/infrastructure/shared/notifications/test_notification_handler.py` — verify `NotificationHandler.handle()` logs warning and continues when one notifier raises

**Checkpoint**: Telegram notification behavior fully verified — factory, formatting, fault isolation.

---

## Phase 6: User Story 4 — Operator Traces Requests Across Services (Priority: P2)

**Goal**: Verify OTel tracing creates `scraper.run` span with correct attributes.

**Independent Test**: Run `make test` and confirm tracing tests pass.

- [ ] T029 [US4] Write test `test_scraper_run_span_created_with_attributes` in `src/tests/unit/infrastructure/shared/observability/test_otel_tracing_noop.py` — verify the CLI entrypoint creates a span named `scraper.run` with `run.id` and `run.correlation_id` attributes (mock tracer)
- [ ] T030 [P] [US4] Write test `test_span_status_set_on_exception` in `src/tests/unit/infrastructure/shared/observability/test_otel_tracing_noop.py` — verify span status is set to ERROR and exception is recorded when the pipeline raises

**Checkpoint**: OTel tracing span lifecycle fully verified.

---

## Phase 7: User Story 5 — Developer Captures Unhandled Errors via Sentry (Priority: P2)

**Goal**: Verify Sentry SDK is initialized with correct DSN and 10% sampling in CLI entrypoints.

**Independent Test**: Run `make test` and confirm Sentry init tests pass.

- [ ] T031 [US5] Write test `test_sentry_initialized_with_dsn` in `src/tests/unit/infrastructure/shared/observability/test_sentry_init.py` — verify `sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)` is called when `SENTRY_DSN` is set (mock `sentry_sdk`)
- [ ] T032 [P] [US5] Write test `test_sentry_init_in_scraper_entrypoint` in `src/tests/unit/infrastructure/shared/observability/test_sentry_init.py` — verify Sentry init happens before `main()` is called in `src/entrypoints/cli/main.py`
- [ ] T033 [P] [US5] Write test `test_sentry_init_in_translate_entrypoint` in `src/tests/unit/infrastructure/shared/observability/test_sentry_init.py` — verify Sentry init happens before `main()` is called in `src/entrypoints/cli/translate.py`

**Checkpoint**: Sentry initialization verified in both CLI entrypoints.

---

## Phase 8: User Story 6 — API Consumer Sees Request IDs for Support (Priority: P3)

**Goal**: Verify `X-Request-ID` header and structured request logging in backend middleware.

**Independent Test**: Run `make test-integration` and confirm request middleware tests pass.

- [ ] T034 [US6] Write test `test_middleware_logs_user_identity_when_authenticated` in `backend/tests/test_request_logging_middleware.py` — verify log entry includes `user_id`, `user_email`, and `user_role` when valid JWT is present
- [ ] T035 [P] [US6] Write test `test_middleware_logs_duration_ms` in `backend/tests/test_request_logging_middleware.py` — verify `duration_ms` field is present and non-negative in log output
- [ ] T036 [P] [US6] Write test `test_middleware_sets_request_id_header` in `backend/tests/test_request_logging_middleware.py` — verify response contains `X-Request-ID` header with a valid UUID4 format (extend existing test)

**Checkpoint**: RequestLoggingMiddleware fully verified — headers, user identity, duration, GeoIP.

---

## Phase 9: User Story 7 — Frontend Operator Sees Proxy Request Logs (Priority: P3)

**Goal**: Verify frontend proxy logs to Loki with correct fields and sensitive field redaction.

**Independent Test**: Run `cd frontend && npm run test` and confirm frontend logging tests pass.

- [ ] T037 [US7] Write test `test_push_to_loki_sends_correct_payload` in `frontend/__tests__/lib/loki-logger.test.ts` — verify `pushToLoki()` constructs a Loki push API payload with correct stream labels and nanosecond timestamp
- [ ] T038 [P] [US7] Write test `test_push_to_loki_uses_basic_auth` in `frontend/__tests__/lib/loki-logger.test.ts` — verify `fetch()` is called with `Authorization: Basic` header
- [ ] T039 [P] [US7] Write test `test_push_to_loki_catches_errors` in `frontend/__tests__/lib/loki-logger.test.ts` — verify `pushToLoki()` catches fetch errors and logs to `console.error` without throwing
- [ ] T040 [US7] Write test `test_proxy_redacts_sensitive_fields` in `frontend/__tests__/api/proxy/redact.test.ts` — verify `redact()` replaces values for keys in `REDACT_KEYS` (case-insensitive) with `"[REDACTED]"`, including nested objects

**Checkpoint**: Frontend Loki logging and redaction fully verified.

---

## Phase 10: User Story 8 — Visitor Sees Localized Content via GeoIP (Priority: P3)

**Goal**: Verify GeoIP-based language resolution with graceful fallback.

**Independent Test**: Run `make test` and confirm GeoIP tests pass.

- [ ] T041 [US8] Write test `test_resolve_language_returns_zh_tw_for_taiwan` in `backend/tests/test_language_resolution.py` — verify `resolve_language_from_ip()` returns `"zh-TW"` when GeoIP returns `{"country": "TW"}`
- [ ] T042 [P] [US8] Write test `test_resolve_language_returns_en_for_other_countries` in `backend/tests/test_language_resolution.py` — verify `resolve_language_from_ip()` returns `"en"` when GeoIP returns a non-TW country
- [ ] T043 [P] [US8] Write test `test_resolve_language_defaults_to_en_on_geoip_failure` in `backend/tests/test_language_resolution.py` — verify `resolve_language_from_ip()` returns `"en"` when GeoIP returns `{}`

**Checkpoint**: GeoIP language resolution fully verified — TW → zh-TW, others → en, failure → en.

---

## Phase 11: User Story 9 — Operator Views Embedded Grafana Dashboards (Priority: P3)

**Goal**: Verify Grafana embed proxy enforces authentication and SSRF protection.

**Independent Test**: Run `cd frontend && npm run test` and confirm Grafana embed tests pass.

- [ ] T044 [US9] Write test `test_grafana_embed_requires_authentication` in `frontend/__tests__/api/grafana-embed/route.test.ts` — verify unauthenticated requests return 401
- [ ] T045 [P] [US9] Write test `test_grafana_embed_rejects_non_grafana_urls` in `frontend/__tests__/api/grafana-embed/route.test.ts` — verify requests with URLs not starting with `GRAFANA_URL` return 403
- [ ] T046 [P] [US9] Write test `test_grafana_embed_proxies_with_service_token` in `frontend/__tests__/api/grafana-embed/route.test.ts` — verify authenticated requests to valid Grafana URLs are proxied with `Authorization: Bearer {GRAFANA_SA_TOKEN}` header

**Checkpoint**: Grafana embed proxy security fully verified — auth + SSRF + token.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup across all stories.

- [ ] T047 Run `make test` and verify all unit tests pass in Docker
- [ ] T048 [P] Run `cd frontend && npm run test` and verify all frontend tests pass
- [ ] T049 Run `make test-integration` and verify all integration tests pass
- [ ] T050 Verify no test imports production observability backends (all tests use mocks/env patches)
- [ ] T051 Run quickstart.md validation — confirm all file paths and commands in `specs/006-observability/quickstart.md` are accurate

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — create test files first
- **Foundational (Phase 2)**: Depends on Setup (test files must exist)
- **US1–US9 (Phase 3–11)**: All depend on Foundational (no-op baseline verified), but are independent of each other
- **Polish (Phase 12)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: No story dependencies — only needs Foundational
- **US2 (P1)**: No story dependencies — only needs Foundational
- **US3 (P2)**: No story dependencies
- **US4 (P2)**: No story dependencies
- **US5 (P2)**: No story dependencies
- **US6 (P3)**: No story dependencies
- **US7 (P3)**: No story dependencies
- **US8 (P3)**: No story dependencies
- **US9 (P3)**: No story dependencies

### Parallel Opportunities

- Phase 1: T001–T006 all create different test files → **all parallel**
- Phase 2: T007–T015 test different components → **all parallel**
- Phase 3–11: US1–US9 all test independent components → **all parallel after Foundational**
- Within each story: tasks marked [P] can run in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch all no-op fallback tests together:
Task: "test_dummy_counter_add_is_noop (test_otel_metrics_noop.py)"
Task: "test_dummy_histogram_record_is_noop (test_otel_metrics_noop.py)"
Task: "test_metrics_setup_returns_none_without_env (test_otel_metrics_noop.py)"
Task: "test_tracer_is_noop_without_env (test_otel_tracing_noop.py)"
Task: "test_loki_handler_not_attached_without_env (test_loki_logging.py)"
Task: "test_sentry_not_initialized_without_dsn (test_sentry_init.py)"
Task: "test_build_notification_handler_without_env (test_notification_build.py)"
Task: "test_push_to_loki_returns_early_without_env (loki-logger.test.ts)"
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (create test files)
2. Complete Phase 2: Foundational (no-op fallback tests)
3. Complete Phase 3: US1 (OTel metrics verification)
4. Complete Phase 4: US2 (structured logging verification)
5. **STOP and VALIDATE**: Run `make test` — all P1 tests green

### Incremental Delivery

1. Setup + Foundational → No-op guarantee verified
2. Add US1 + US2 → P1 observability verified (MVP!)
3. Add US3–US5 → P2 observability verified
4. Add US6–US9 → P3 observability verified
5. Polish → All tests green, quickstart validated

### Parallel Team Strategy

1. Complete Setup + Foundational together
2. Once Foundational is done:
   - Agent A: US1 + US4 (OTel metrics + tracing)
   - Agent B: US2 + US5 (logging + Sentry)
   - Agent C: US3 (Telegram notifications)
   - Agent D: US6 + US8 (middleware + GeoIP)
   - Agent E: US7 + US9 (frontend logging + Grafana)
3. Each story completes independently

---

## Notes

- Brownfield: tasks write TESTS to verify existing behavior, not new production code
- All tests use mocks/env patches — no real OTel/Loki/Sentry/Telegram backends needed
- Constitution VI (graceful degradation) is the foundational guarantee being validated
- Test files follow project conventions: `src/tests/unit/` for Python, `frontend/__tests__/` for TS
- Integration tests (`make test-integration`) only for middleware — everything else is unit tests
