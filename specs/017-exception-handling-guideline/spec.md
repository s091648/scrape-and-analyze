# Feature Specification: Exception Handling Guideline & API Status Code Management

**Feature Branch**: `017-exception-handling-guideline`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "Exception handling guideline for src/ and API status code management for backend/ (GitHub issue #41). src/ 目前的 exception handling 很混亂:任何 function 都可以自行決定要不要 raise exception,exception 型別也不一致,exception propagation 也沒有良好結構。backend/ API 目前幾乎沒有妥善管理 status code。src/shared/domain/exceptions.py 已有 domain-specific exception hierarchy(016-db-schema-brushup 完成),此 feature 應以此為基礎,補齊(1) exception 使用規範/準則,(2) backend API 的 status code 對應規範與盤點。"

## Clarifications

### Session 2026-07-22

- Q: What fields belong in the default/standard API error response body template? → A: Structured + traceability — `{"error": {"code": "...", "message": "...", "request_id": "..."}}`, leveraging the existing structlog/Loki/Sentry observability stack to correlate a returned error with server-side logs.
- Q: The existing exception hierarchy (`CollectionDomainError`/`IntelligenceDomainError`) only covers validation-type errors today — should this feature build out the full cross-cutting exception category taxonomy (not-found, conflict, external-dependency-failure, unauthorized/forbidden) upfront, or only add categories reactively as the router audit finds gaps? → A: Build the full taxonomy upfront — shared base exception categories (not-found, conflict, external-dependency-failure, unauthorized/forbidden) are designed and implemented as part of this feature, ready for every bounded context to subclass, rather than deferred to future ad hoc additions.
- Q: `backend/auth/guards.py` currently raises `HTTPException(401/403, ...)` directly for authentication/authorization failures, bypassing the domain exception hierarchy entirely — should 401/403 be brought into the same central exception-to-status mapping (FR-005) as domain errors, or left as a separate framework-level mechanism (only unifying the response body format)? → A: Bring 401/403 fully into the same mechanism — authentication/authorization guards raise a shared authorization domain exception, translated to HTTP status by the same central mapping used for every other domain exception, so there is exactly one error-handling path for the entire API rather than two parallel ones.
- Q: `ResilientLLMService`/`ResilientMetricsService` currently return `None` (not raise) when every provider in their fallback chain is exhausted — should this feature change those services to raise an external-dependency-failure exception instead, or keep the `None`-return contract and only require call sites that treat `None` as an unrecoverable failure to translate it into the new external-dependency-failure category? → B: Keep the existing `None`-return contract in `ResilientLLMService`/`ResilientMetricsService` unchanged (out of scope — an already-tested resilience mechanism, not part of this feature); require call sites that treat a `None` result as an unrecoverable failure (e.g. `backend/routers/chat.py`, the weekly-report image pipeline) to translate it into the new external-dependency-failure category (FR-004a) before it can reach the central mapping (FR-005).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent error responses from the API (Priority: P1)

As a frontend developer (or any API consumer, including the Swagger UI), when I call an endpoint that fails — the resource doesn't exist, my input is invalid, I'm not authorized, or an upstream dependency (LLM provider, external metrics API) is unavailable — I receive an HTTP status code that accurately reflects the failure category and a response body that reliably tells me why, instead of a uniform/misleading status code that forces me to guess from the message text.

**Why this priority**: This is the externally-visible, highest-value outcome named directly in the issue ("從 swagger 上看幾乎所有 endpoint 都回傳一樣的預設狀態碼"). It's also the only story with a concrete, independently verifiable artifact (the OpenAPI/Swagger doc and live responses).

**Independent Test**: Call a sample of endpoints across every router with inputs designed to trigger not-found, validation, authorization, and unexpected-failure scenarios; verify each returns a status code from the documented mapping (not a blanket 200/500) and a response body with a consistent error shape.

**Acceptance Scenarios**:

1. **Given** a request for a resource that does not exist (e.g. an article, topic, or scraper keyword ID that isn't in the database), **When** the request is made, **Then** the response status is 404 with an error body identifying the missing resource.
2. **Given** a request with invalid or malformed input (e.g. violates a domain validation rule), **When** the request is made, **Then** the response status is 400 (or 422 where FastAPI's built-in request validation already applies) with an error body describing the invalid field/reason.
3. **Given** a request that requires authentication/authorization the caller doesn't have, **When** the request is made, **Then** the response status is 401 or 403 as appropriate, not a generic 500 or 404.
4. **Given** a request that triggers an unexpected internal failure (e.g. unhandled exception, downstream LLM/metrics provider failure not caused by caller input), **When** the request is made, **Then** the response status is 500 (or 502/503 for confirmed upstream-dependency failures) and no internal exception detail (stack trace, file paths) is leaked in the response body.
5. **Given** the same underlying domain error is raised from two different endpoints, **When** each is triggered, **Then** both return the same HTTP status code for that error type (no router-specific inconsistency for the same failure).

---

### User Story 2 - A written guideline developers can follow when writing new code (Priority: P2)

As a contributor adding a new use case, repository method, or infrastructure adapter in `src/`, I can consult a single guideline document that tells me when to raise an exception vs. return a null/empty/failure value, which exception type to use (built-in vs. domain-specific), and how exceptions should be allowed to propagate across the domain → application → infrastructure → API boundary — so my new code is consistent with the rest of the codebase without needing a reviewer to catch inconsistencies after the fact.

**Why this priority**: This addresses the root cause named in the issue ("Any function can decide whether to raise an exception or not... type also varies... propagation not well-structured"), and is the mechanism that keeps User Story 1's outcome from regressing as new code is added. It depends on the exception vocabulary already established in `src/shared/domain/exceptions.py`.

**Independent Test**: Give the guideline document to someone implementing a new use case/endpoint (or use it as a code-review checklist) and confirm they can, without asking a maintainer, correctly decide (a) whether to raise, (b) which exception class/hierarchy to raise, and (c) whether to let it propagate or translate it at a layer boundary.

**Acceptance Scenarios**:

1. **Given** a new validation rule is added to a domain entity or value object, **When** the guideline is consulted, **Then** it specifies that a domain-specific exception (subclassing the relevant bounded-context's root exception under `DomainError`) must be raised, not a built-in `ValueError`/`Exception`.
2. **Given** a repository or infrastructure adapter call fails (e.g. DB constraint violation, network error, external API error), **When** the guideline is consulted, **Then** it specifies whether/how that failure must be wrapped or translated before crossing into the application layer, so application-layer code never has to catch infrastructure-specific exception types directly.
3. **Given** an application-layer use case calls code that may raise a domain exception, **When** the guideline is consulted, **Then** it specifies whether the use case should let it propagate unchanged, wrap it, or handle it locally — with a stated rule (not a case-by-case judgment call).
4. **Given** a genuinely unrecoverable/programmer-error condition (e.g. violated invariant that should never happen), **When** the guideline is consulted, **Then** it distinguishes this from expected/recoverable domain errors and states how each should be treated differently.

---

### User Story 3 - A maintained mapping from domain errors to HTTP status codes (Priority: P2)

As a backend router author, when a use case raises a domain exception, I don't hand-pick an HTTP status code inline at each call site — I rely on a single, documented (and ideally enforced-by-code) mapping from exception type/category to HTTP status code, so the mapping only needs to be defined once per exception type and stays consistent across all routers automatically.

**Why this priority**: This is the mechanism that makes User Story 1 durable — without a central mapping, consistency depends on every router author remembering the right status code by hand, which is exactly the current failure mode. It's P2 (not P1) because it's the underlying mechanism for the P1 user-facing outcome rather than an independently visible outcome itself.

**Independent Test**: Pick any domain exception type; verify there is exactly one documented status-code mapping for it, and that every router endpoint capable of raising it produces that same status code without router-specific override logic.

**Acceptance Scenarios**:

1. **Given** a domain exception is raised anywhere within a request's handling, **When** it reaches the API boundary, **Then** it is converted to an HTTP response using the documented mapping without requiring each router endpoint to individually catch and translate that exception type.
2. **Given** a new domain exception type is added in the future, **When** a developer wants it to produce a specific HTTP status code, **Then** the guideline specifies exactly one place to register that mapping.
3. **Given** an exception is raised that has no explicit mapping, **When** it reaches the API boundary, **Then** it falls back to a documented default (500) rather than an undefined/inconsistent status code.

---

### Edge Cases

- What status code is returned when a domain exception could plausibly map to more than one HTTP status depending on context (e.g. a "not found" that in one endpoint means the resource never existed (404) vs. another endpoint means the resource exists but the caller can't access it (403))? The guideline must state how such ambiguity is resolved (e.g. distinct exception subtypes per case, or explicit per-call-site override permitted).
- How are validation errors raised by FastAPI/Pydantic itself (422) distinguished from domain validation errors raised by the guideline's own exception hierarchy (400)? The guideline must state which is used where so 400 and 422 aren't used interchangeably for the same kind of failure.
- What happens when an exception occurs during a background/async task (e.g. the periodic view-count flush, or the scheduled scraper pipeline) that has no HTTP request to respond to? The guideline must state how these cases are handled (e.g. logged only, vs. still required to use the domain exception hierarchy) since there's no HTTP status code to map to.
- What happens when a third-party/library exception (e.g. a SQLAlchemy or `httpx` exception) surfaces at a router boundary without having been translated by any lower layer? Is this treated as a guideline violation to fix, or is there a documented last-resort fallback behavior?
- How should an endpoint that legitimately needs multiple failure-status branches (e.g. 404 vs. 409 vs. 422 all possible from the same operation) be structured, given the guideline discourages ad hoc inline status-code decisions?
- What happens when a failure occurs after an HTTP response has already started streaming (e.g. a Server-Sent Events chat response) and the status code has already been committed as 200? The guideline must state that the exception-to-status-code mapping (FR-005) applies only before the response begins; failures after that point are signaled in-band within the stream payload using the same error identifier/message vocabulary as FR-008, not via a changed HTTP status.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The guideline MUST define, for `src/`'s domain, application, and infrastructure layers, the criteria for when code MUST raise an exception versus return a non-exception failure signal (e.g. `None`, empty collection, result/status value).
- **FR-002**: The guideline MUST define which exception types are permitted at each layer: domain-specific exceptions (subclasses of the existing `DomainError` hierarchy in `src/shared/domain/exceptions.py` and its per-bounded-context roots) for expected domain-rule violations, versus when (if ever) built-in Python exceptions remain acceptable.
- **FR-003**: The guideline MUST define exception propagation rules across layer boundaries — specifically: whether the application layer (use cases) may let domain exceptions propagate unchanged, and whether/how infrastructure-layer failures (DB, network, external API, LLM provider) must be translated into domain exceptions before reaching the application layer.
- **FR-004**: The guideline MUST require that every domain exception used across the system belongs to the existing hierarchy rooted at `DomainError` (via each bounded context's root, e.g. `CollectionDomainError`, `IntelligenceDomainError`), and MUST define the process for adding a new exception subclass or a new bounded-context root when an existing one doesn't fit.
- **FR-004a**: The feature MUST introduce, as shared/reusable base categories under the `DomainError` hierarchy, at minimum: not-found, conflict, external-dependency-failure, and unauthorized/forbidden — since the existing hierarchy (established by `016-db-schema-brushup`) covers only validation-type errors today. Each bounded context's specific exceptions for these categories MUST subclass the shared base category (not redefine an equivalent independently), so cross-cutting categories share one identity that the status-code mapping (FR-005) can key off without per-bounded-context special-casing.
- **FR-005**: The system MUST provide a single, centrally-defined mapping from domain exception types (or categories) to HTTP status codes, such that any backend router raising or receiving a mapped domain exception produces a consistent status code without per-endpoint status-code logic. This single mapping MUST be the only path from an exception to an HTTP status code across the entire API — including authentication/authorization failures (see FR-005a) — with no parallel/separate status-code mechanism left in place.
- **FR-005a**: Authentication and authorization failures currently raised directly as `HTTPException` in the request-authentication guards MUST instead raise a shared authorization-category domain exception (per FR-004a), translated to an HTTP status (401/403) by the same central mapping (FR-005) used for every other domain exception — eliminating the guards' current bypass of the domain exception hierarchy.
- **FR-006**: The mapping in FR-005 MUST cover, at minimum, the following HTTP status categories with example triggering conditions: 400 (invalid domain input), 401 (missing/invalid authentication), 403 (authenticated but not authorized), 404 (resource not found), 409 (conflicting state), 500 (unhandled/unexpected internal error), and 502/503 (confirmed failure of an external dependency such as an LLM provider or metrics API).
- **FR-006a**: Existing resilient-provider services (`ResilientLLMService`, `ResilientMetricsService`) that fall back through an ordered provider chain and return `None` when every provider is exhausted MUST NOT be changed to raise instead — their `None`-return contract is out of scope for this feature. Any call site that treats such a `None` result as an unrecoverable failure requiring an error response MUST translate it into the external-dependency-failure category (FR-004a) at that call site before it reaches the central mapping (FR-005).
- **FR-007**: The system MUST apply a documented default status code (500) for any exception reaching the API boundary that has no explicit entry in the mapping from FR-005, so unmapped exceptions never surface an inconsistent or undefined status code.
- **FR-008**: Error responses returned by the API MUST use a consistent response body shape across all endpoints: a machine-readable error code/category, a human-readable message, and a request identifier correlating the response to server-side logs (structlog/Loki), so API consumers can handle errors generically and support/debugging can trace a reported error back to its log entry.
- **FR-009**: Error responses for unexpected internal failures (500-class) MUST NOT leak internal implementation details (stack traces, file paths, raw exception class names, SQL text) to the API consumer, while still preserving that detail in server-side logs.
- **FR-010**: The feature MUST include an audit of every existing endpoint under `backend/routers/` that identifies, per endpoint, its current failure/status-code behavior versus the behavior required by the new mapping, and enumerates every endpoint that needs to change to comply.
- **FR-011**: The guideline MUST distinguish "expected/recoverable" domain errors (caller can act on the response, e.g. fix input, request a different resource) from "unrecoverable/programmer error" conditions (invariant violations that indicate a bug), and state that only the former are represented by the routine domain-exception-to-HTTP-status mapping.
- **FR-012**: The guideline MUST state how FastAPI/Pydantic's own built-in request-validation errors (422) relate to the domain-validation-error status code (400), so contributors have an explicit rule for which to use rather than choosing per endpoint.
- **FR-013**: The guideline MUST be captured as a durable, discoverable document (not just implicit in code) that a contributor can consult before writing new exception-raising or error-handling code.

### Key Entities

- **Domain Exception Hierarchy**: The existing tree rooted at `DomainError` (`src/shared/domain/exceptions.py`), with one root exception per bounded context (e.g. `CollectionDomainError`, `IntelligenceDomainError`) and specific leaf exception classes beneath each. This feature extends usage/coverage of this hierarchy; it does not replace it.
- **Exception-to-Status-Code Mapping**: The single source of truth associating each domain exception type (or category) with the HTTP status code it must produce at the API boundary, plus the documented default for unmapped exceptions.
- **API Error Response**: The consistent JSON shape returned for any failed API request, distinguished from a successful response by status code and carrying enough information for a caller to understand the failure category and (where applicable) which input/resource caused it.
- **Router Endpoint Audit Entry**: Per-endpoint record (one per route in `backend/routers/`) capturing current error/status-code behavior and required behavior under the new mapping, used to scope the remediation work.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of endpoints across all routers in `backend/routers/` return a status code from the documented mapping (not a hardcoded ad hoc value chosen independently per endpoint) when exercised with not-found, invalid-input, and unauthorized scenarios.
- **SC-002**: 100% of endpoints returning a client- or server-error status code use the single consistent error response body shape.
- **SC-003**: Zero API error responses expose internal implementation detail (stack traces, file paths, internal exception class names, or raw SQL/database error text) to the caller, verified across the full router audit.
- **SC-004**: A developer unfamiliar with a specific module can determine, using only the written guideline (without asking a maintainer), the correct exception type and HTTP status code for a new failure scenario in under 5 minutes.
- **SC-005**: Every existing domain exception class in the codebase has exactly one entry in the exception-to-status-code mapping (no domain exception type left unmapped/falling through only to the generic default when a more specific status is clearly appropriate).

## Assumptions

- This feature is a continuation of the domain exception hierarchy established in the (already merged) `016-db-schema-brushup` work (`src/shared/domain/exceptions.py` and its per-bounded-context subclasses) — that hierarchy is treated as a stable foundation to build on, not something this feature redesigns from scratch.
- "src/" in scope means the scraper/analyzer service's domain, application, and infrastructure layers as described in the project's architecture documentation; the `backend/` FastAPI service is in scope specifically for API status code management and for consuming/translating exceptions raised by shared domain logic and its own service-layer code — including `backend/auth/guards.py`, whose current direct `HTTPException` raises for 401/403 are brought into the same central mapping (see Clarifications).
- The `frontend/` and `models/` codebases are out of scope for this feature except as passive consumers of whatever error response shape the API produces.
- "API consumer" in this spec refers to any caller of the backend API — the frontend proxy, Swagger UI, or any future direct client — since the backend does not currently distinguish between them for error-handling purposes.
- Bringing every single existing endpoint into full compliance with the new mapping is in scope for the audit (FR-010) as a required inventory, but the spec does not mandate that remediation of every audited endpoint happen within this feature's initial delivery — prioritization of remediation order is a planning-phase concern, not a specification-phase constraint.
- Background/async, non-HTTP-triggered code paths (e.g. the scheduled scraper pipeline, periodic view-count flush) are expected to keep using the same domain exception hierarchy for consistency, but since they have no HTTP response to produce, the status-code mapping requirements (FR-005 through FR-007) apply only to code paths that terminate in an API response.
