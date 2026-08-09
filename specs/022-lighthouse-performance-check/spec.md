# Feature Specification: Lighthouse Performance Check

**Feature Branch**: `020-redis-caching-layer` (reused; see Assumptions — this feature intentionally shares the branch with 020/021 and lives in its own spec directory)

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "我希望能夠在 Makefile 跟 scripts/ 裡面加上一個使用 lighthouse CLI 來去做 performance check 的一個腳本，並且最後出具一份report。可能需要涵蓋說我要使用哪個url，用甚麼身分(應該是用 guest)登入，以及指定要測試那些 route。然後出來的 report 希望是以繁體中文彙整。且之後會希望可以把他做在 .github/workflows/ci.yml 或是其他的 action 裡面。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-command performance check across key routes (Priority: P1)

As a developer working on this project, I want to run a single command that checks page-load performance (Performance score, LCP, TBT, CLS) across the site's key public routes, using guest-level access so the check works against pages that require at least guest authentication, so that I can catch performance regressions without manually opening each page in DevTools/Lighthouse one at a time.

**Why this priority**: This is the core value of the feature — everything else (report formatting, CI integration) is built on top of having a working, repeatable local check. Without this, there is nothing to integrate into CI.

**Independent Test**: Can be fully tested by running the new `make` target against a locally running frontend/backend stack and confirming it produces performance metrics for each configured route without requiring any manual login step.

**Acceptance Scenarios**:

1. **Given** the frontend and backend are running and reachable at a configured base URL, **When** the developer runs the performance-check command, **Then** the system automatically obtains guest-level access and runs a performance audit against every configured route without prompting for credentials.
2. **Given** the developer wants to test a different set of routes or a different base URL (e.g. staging instead of local), **When** they pass route and URL parameters to the command, **Then** the system tests exactly the specified routes against the specified base URL.
3. **Given** all configured routes were reachable, **When** the check completes, **Then** each route has a recorded Performance score, LCP, TBT, and CLS value.

---

### User Story 2 - Consolidated report in Traditional Chinese (Priority: P2)

As a developer/stakeholder reviewing results, I want the performance check to produce one consolidated, human-readable report written in Traditional Chinese summarizing every tested route, so that the results are immediately understandable to the team without needing to read raw Lighthouse JSON or translate anything.

**Why this priority**: Raw Lighthouse output (JSON/English HTML report) is not what was asked for and isn't easily shared or skimmed; a summarized Traditional-Chinese report is what makes the check's output actually useful day-to-day.

**Independent Test**: Can be fully tested by running the check and confirming a single report file is produced, saved to disk, containing per-route metrics and narrative text in Traditional Chinese, independent of whether CI integration exists yet.

**Acceptance Scenarios**:

1. **Given** the performance check has finished running against all configured routes, **When** the report is generated, **Then** it contains a summary table (or equivalent) listing every tested route with its Performance score, LCP, TBT, and CLS.
2. **Given** the report is generated, **When** a Traditional-Chinese-reading developer opens it, **Then** all labels, headings, and narrative commentary are in Traditional Chinese (metric names and raw numeric values may remain in their standard technical form, e.g. "LCP", "ms").
3. **Given** a route fails to load or audit (e.g. server unreachable, page errors), **When** the report is generated, **Then** that route is clearly listed as failed with a reason, rather than being silently omitted from the report.

---

### User Story 3 - Automated check in CI (Priority: P3)

As a maintainer, I want this performance check to eventually run automatically as part of the GitHub Actions workflow (e.g. on pull requests and/or on a schedule), so that performance regressions are caught before/soon after they reach `master`, and results are visible to reviewers (e.g. as a workflow artifact or PR comment) without anyone needing to run the check manually.

**Why this priority**: This is the stated end-goal, but it depends on User Story 1 and 2 already being solid (a script that reliably runs headlessly and produces a report). It is lower priority because the local script must exist and prove reliable before it's worth wiring into CI.

**Independent Test**: Can be tested independently once User Stories 1–2 exist, by adding a CI job that invokes the same `make` target used locally and uploading/publishing its resulting report, and confirming the job succeeds on a real PR/schedule run.

**Acceptance Scenarios**:

1. **Given** the performance check script works headlessly locally, **When** it is invoked from a GitHub Actions job, **Then** it runs to completion without requiring interactive input and exits with a status reflecting whether the check itself ran successfully (see Assumptions re: pass/fail thresholds).
2. **Given** the CI job has completed, **When** a reviewer looks at the workflow run (or the PR), **Then** the Traditional-Chinese report is available to them (e.g. as a downloadable artifact and/or inline in the job summary/PR comment).

---

### Edge Cases

- What happens when the configured base URL is unreachable (server not running / wrong URL)? → The check must fail fast with a clear error identifying the unreachable URL, rather than producing an empty or misleading report.
- What happens when obtaining guest access fails (e.g. `/auth/guest` endpoint errors or is unreachable)? → The check must abort with a clear error before attempting any route audits, since none of the target routes can be meaningfully tested without it.
- What happens when one route in the configured list fails (404, client-side error, timeout) but others succeed? → The overall check should still complete and report results for the routes that succeeded, while clearly flagging the failed route(s) rather than crashing the whole run.
- What happens when no routes are explicitly specified? → The system uses a documented default set of key public routes (see Assumptions).
- What happens when the check is run twice in a row? → Each run produces its own report (previous reports are not silently overwritten without at least being distinguishable by timestamp, unless the developer is only ever interested in the latest run — see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a way to specify the base URL against which performance checks run (e.g. local dev, a staging deployment).
- **FR-002**: The system MUST provide a way to specify which route(s) to test, and MUST fall back to a documented default set of routes when none are specified.
- **FR-003**: The system MUST obtain guest-level access on its own before auditing any route, without requiring a human to manually log in or supply real user credentials.
- **FR-004**: The system MUST run a performance audit against each configured route while presenting itself as an authenticated guest, so pages behind guest-mode access restrictions can be audited.
- **FR-005**: The system MUST capture, at minimum, the Performance score, Largest Contentful Paint (LCP), Total Blocking Time (TBT), and Cumulative Layout Shift (CLS) for each tested route.
- **FR-006**: The system MUST consolidate results from all tested routes into a single report (not one disconnected file per route requiring manual aggregation).
- **FR-007**: The consolidated report's labels and narrative content MUST be written in Traditional Chinese (zh-TW).
- **FR-008**: The system MUST be invocable through a single `make` target, consistent with how other one-off/maintenance scripts in this project are exposed (see `Makefile`).
- **FR-009**: The system MUST run non-interactively (no manual prompts) so that it can later be invoked from an unattended CI job.
- **FR-010**: The system MUST report a per-route failure clearly (route + reason) if that route could not be audited, rather than omitting it silently.
- **FR-011**: The system MUST persist the consolidated report to a file on disk (not only print to the console), so it can later be uploaded as a CI artifact or otherwise shared.

### Key Entities

- **Performance Check Run**: One invocation of the check; has a base URL, a set of target routes, a timestamp, and produces one consolidated report.
- **Route Target**: A single route/path under test (e.g. `/`, `/articles`, `/graph`, `/tags`) with its own Performance/LCP/TBT/CLS results (or a failure reason).
- **Guest Credential**: The short-lived guest-level access obtained automatically for the run, used only to reach guest-gated pages during the audit; not tied to any real user identity.
- **Consolidated Report**: The Traditional-Chinese summary artifact produced by a run, containing one entry per Route Target.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can go from "nothing running" to "consolidated report in hand" for the default set of routes using a single command, with zero manual authentication steps.
- **SC-002**: 100% of configured routes appear in the resulting report — either with metrics or with a clearly stated failure reason — with no route silently missing.
- **SC-003**: 100% of the report's section headings, labels, and narrative commentary are in Traditional Chinese, verified by inspection of a sample report.
- **SC-004**: The check can complete a run against 4 key routes (`/`, `/articles`, `/graph`, `/tags`) in under 10 minutes, making it practical to run routinely (locally or in CI) without becoming a bottleneck.
- **SC-005**: Once CI integration (User Story 3) is added, a reviewer can find that run's Traditional-Chinese report from the workflow run without needing repo/local access to reproduce it themselves.

## Assumptions

- **Branch/spec-directory convention**: Per this project's established pattern (see the 021-ssr-public-pages precedent), this feature reuses the current git branch `020-redis-caching-layer` rather than opening a new one, but lives in its own spec directory (`specs/022-lighthouse-performance-check/`) since it is functionally unrelated to Redis caching.
- **Default routes**: When not overridden, the default route set is the site's main public pages: `/`, `/articles`, `/graph`, `/tags` — matching the routes explicitly named in the request and the ones already gated by guest-mode access per `require_any_token`.
- **Default target environment**: When not overridden, the check targets a locally running stack (frontend at `http://localhost:3000`, proxying to backend at `http://backend:8000`/`http://localhost:8000` as applicable), consistent with how other `make` targets in this repo default to local/dev behavior unless a `REMOTE_URL`/`ENV` override is given.
- **Guest access mechanism**: "Guest login" means calling the existing `POST /auth/guest` endpoint (see `018-public-api-auth`) to obtain a guest access token, then supplying it to Lighthouse's request so gated pages render as they would for a real guest user — no new auth mechanism is introduced.
- **Report format**: The consolidated report is a Traditional-Chinese Markdown file (plus the option to retain raw Lighthouse JSON per route alongside it for anyone who needs the underlying data) rather than a new bespoke report viewer/UI.
- **Pass/fail semantics for v1**: The check is informational for this iteration — it does not enforce hard performance-score thresholds that fail the run/CI job. Turning specific metrics into CI-blocking gates is a possible future enhancement, not part of this spec.
- **CI integration timing**: Wiring this into `.github/workflows/ci.yml` (or a dedicated workflow) is in-scope for this spec's overall vision (User Story 3) but is explicitly the lowest priority — the local script and report must work and be validated first, per the user's own phrasing ("之後會希望可以...").
- **Multiple runs**: Each run's report is distinguishable (e.g. by timestamp in the filename), so repeated local runs don't require the developer to manually rename/move prior reports before comparing them.
