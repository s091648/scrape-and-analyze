# Feature Specification: Async Event-Driven Collection Pipeline

**Feature Branch**: `024-async-pipeline-refactor`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Rewrite the collection pipeline's downstream stages (scrape → analyze → translate → RAG ingestion) into a genuinely concurrent, async, event-driven architecture, replacing the current fully-synchronous per-article chain. Full asyncio preferred over ThreadPoolExecutor for architectural fidelity to event-driven design. Discover/fetch/dedup stay batched as today — only downstream-of-publish stages become concurrent per-article. The event dispatch mechanism should stay swappable to an external/durable implementation later without touching stage logic. Concurrent access to shared model rate-limit capacity and to the database must be handled safely. RAG ingestion should not block other articles' processing. Includes a model-pool dispatch upgrade so concurrent requests spread across every registered, currently-available model instead of queuing behind a single model."

## Clarifications

### Session 2026-08-20

- Q: Does a completion barrier (FR-004) wait for every article to *succeed* at a stage, or for every article to *settle* (succeed or permanently fail)? → A: Settle. A permanently-failed article counts toward the barrier immediately, the same run it failed in — it is never retried until success, and it never delays either signal. It simply has no title/body/translation content to contribute, so it does not appear in the search index; its failure is still recorded and reported exactly as other failures are (Edge Cases, FR-007). This matches today's behavior, where one article's failure never blocks the rest of the run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A scheduled run finishes without one slow article blocking every other article (Priority: P1)

Today, once articles are fetched and deduplicated, the pipeline processes them one at a time — a single article's entire downstream chain (save, analyze, translate, RAG ingestion) must finish before the next article even starts. RAG ingestion is the slowest step in that chain. An operator running the scheduled scrape should see the run's downstream processing scale with how much concurrent capacity is available, not with the sum of every article's slowest step multiplied by every other article waiting behind it.

**Why this priority**: This is the core problem driving the whole feature — without it, nothing else in this spec has a reason to exist.

**Independent Test**: Run the pipeline against a batch of newly-discovered articles where at least one requires RAG ingestion. Measure the time from "all articles fetched" to "every article's analyze and translate work is done." Confirm this no longer scales with the sum of every individual article's RAG ingestion time.

**Acceptance Scenarios**:

1. **Given** a batch of N newly-fetched articles is ready for downstream processing, **When** the pipeline processes them, **Then** more than one article's downstream processing is in progress at the same time.
2. **Given** one article's RAG ingestion is unusually slow, **When** the run continues, **Then** other articles' analyze and translate work is not delayed by it.

---

### User Story 2 - Freshly scraped articles become searchable without waiting on RAG (Priority: P2)

Visitors search for articles using the autocomplete/search index, which is rebuilt once per scheduled run. Today that rebuild waits for absolutely everything in the run to finish, including RAG ingestion. A visitor should be able to find a newly scraped article as soon as its text content (title, body, translations) has been processed, without waiting on the slower RAG step for every article in the run.

**Why this priority**: This is the concrete, user-visible payoff of decoupling RAG — it's what makes the architectural change worth something beyond internal tidiness.

**Independent Test**: Trigger a run containing articles that require RAG ingestion. Artificially slow down RAG ingestion for one article and confirm the search index rebuild and cache refresh still complete — reflecting every article's text content — before that article's RAG ingestion finishes.

**Acceptance Scenarios**:

1. **Given** every article in a run has finished its text processing (scrape, analyze, translate) but RAG ingestion is still in progress for some, **When** the run reaches that point, **Then** the search index and read caches are refreshed with the new articles' content.
2. **Given** RAG ingestion later finishes for the remaining articles, **When** it completes, **Then** it does not trigger a second, redundant search-index rebuild.

---

### User Story 3 - Operators still get one accurate, complete run report (Priority: P3)

Operators currently receive a single completion notification summarizing the whole run (successes, failures, rate-limited providers). Splitting the pipeline into concurrent, decoupled stages must not degrade this — operators should still get one notification, sent once everything (including RAG) is truly done, that accurately reflects every article's outcome at every stage.

**Why this priority**: Concurrency is only safe to ship if it doesn't quietly break the operator's only visibility into whether a run actually succeeded.

**Independent Test**: In a single run, induce a RAG ingestion failure for one article and an LLM rate-limit event for another. Confirm the completion notification reports both accurately, and is sent only after RAG processing for the whole run has finished.

**Acceptance Scenarios**:

1. **Given** a run where some articles succeed and others fail at various stages (analyze, translate, RAG), **When** the run completes, **Then** the operator notification accurately summarizes every outcome, matching what today's single-threaded run would have reported.
2. **Given** every registered model for a capability becomes exhausted during the run, **When** the run completes, **Then** the notification still reports which providers were exhausted, as it does today.

---

### User Story 4 - Multiple available models are used at once instead of queuing behind one (Priority: P4)

Some registered LLM/embedding models have small daily quotas (as low as 20 requests/day). Today, even if many such models are registered, concurrent work still funnels through whichever model has the highest priority until its quota is exhausted, before ever trying the next. An operator with many low-quota models registered should see them all put to work concurrently, so the run sustains meaningfully higher throughput before the whole capability is exhausted.

**Why this priority**: Without this, the concurrency introduced by User Story 1 doesn't actually reach the analyze/translate stage — those calls would still serialize behind a single model's own rate limit, undercutting the story's own goal.

**Independent Test**: Register several low-daily-quota models for the same capability. Run a batch of articles whose combined analyze/translate calls exceed any single model's daily quota. Confirm multiple models are in concurrent use early in the run (not used one at a time in strict priority order), and total throughput before the whole capability is exhausted exceeds what the single highest-priority model alone could sustain.

**Acceptance Scenarios**:

1. **Given** several models are registered and currently have spare capacity, **When** multiple concurrent requests for that capability are made at the same time, **Then** they are distributed across those models rather than all queuing for the same one.
2. **Given** a model's daily quota is fully exhausted, **When** further requests are made, **Then** that model is excluded and requests continue to be distributed across the remaining available models, as today.
3. **Given** a model is only momentarily throttled within its per-minute window (not daily-exhausted) while another registered model has spare capacity, **When** a request is made, **Then** it is routed to the model with spare capacity rather than waiting on the throttled one.

---

### User Story 5 - The stage-handoff mechanism can later scale beyond one process without rewriting stages (Priority: P5)

The mechanism used to pass work between pipeline stages is internal today (in-process only). A maintainer should be able to later replace it with an external, durable mechanism suited to running across multiple processes, by changing only that mechanism's implementation — not by rewriting how any individual stage (analyze, translate, RAG ingestion, etc.) does its work.

**Why this priority**: This is a forward-looking extensibility goal, not something this feature's users notice directly — lowest priority, but worth stating so the design doesn't foreclose it.

**Independent Test**: Verify that every pipeline stage depends only on the abstract stage-handoff interface, never on its concrete in-process implementation. Confirm this by substituting a stub implementation of the interface and observing that no stage's processing code needs to change.

**Acceptance Scenarios**:

1. **Given** a pipeline stage's processing logic, **When** inspected, **Then** it references only the abstract stage-handoff interface, not any concrete implementation detail.

---

### Edge Cases

- What happens when RAG ingestion fails for one article while others are still being processed? It must not stop or delay any other article's processing, and must still be reflected in the run's completion notification (User Story 3).
- What happens when a registered model's daily quota is exhausted while concurrent requests are in flight for it? Those in-flight requests fail over to another available model, as today; other concurrently-running articles are unaffected.
- What happens when every registered model for a capability is simultaneously out of capacity mid-run? Requests for that capability wait rather than error out, resuming automatically once any model regains capacity — matching today's fallback behavior, just applied across a pool instead of a single active model.
- What happens if a database write for one concurrently-processing article fails or is temporarily unavailable? It must not corrupt, block, or roll back any other article's already-completed or in-progress work; the failure is recorded per-article the same way today's failures are.
- What happens when an article's text-stage work (analyze/translate) permanently fails? It counts as settled toward the text-complete signal (FR-004) immediately — the barrier does not wait for it to succeed and it is not retried. The failed article contributes no title/body/translation content, so it is simply absent from the resulting search index rebuild; its failure is still recorded and reported exactly as other failures are.
- What happens when a run contains zero articles requiring RAG ingestion? Both completion signals (text-complete and fully-complete) still fire correctly and in the right order, with no observable difference from a run that does use RAG.
- What happens if the process crashes mid-run, after some articles' text processing finished but before RAG ingestion finished for others? This feature does not add crash-recovery or durability guarantees beyond what exists today; work already committed before the crash is unaffected, and no new data-loss mode is introduced beyond what a crash already causes today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow more than one article's downstream processing (analyze, translate, RAG ingestion) to be in progress concurrently, instead of requiring one article's entire chain to finish before the next article's begins.
- **FR-002**: System MUST decouple RAG ingestion for a given article from analyze/translate processing of every other article, such that one article's RAG ingestion — however slow or failed — never delays or blocks another article's progress.
- **FR-003**: Discovery, fetching (including its existing per-source/per-host concurrency), and the existing batched pre-fetch/post-fetch deduplication MUST remain unchanged. In particular, the boundary between "the whole fetch-and-deduplicate phase has finished for every source" and "articles begin being published for downstream processing" MUST NOT move — no article's downstream processing (analyze, translate, RAG ingestion) may begin until every source's fetching and the batched deduplication check are complete. Only processing from that publish point onward becomes concurrent (FR-001).
- **FR-004**: System MUST expose two distinct completion signals for a run: one firing once every article's scrape+analyze+translate (title and body) work has *settled* — succeeded or permanently failed — and a second firing once every article's work, including RAG ingestion, has similarly settled. A permanently-failed article counts toward both signals immediately, without being retried until success, and MUST NOT delay either signal.
- **FR-005**: The search-index/autocomplete rebuild and the read-cache invalidation/warmup MUST be triggered by the first completion signal (FR-004), not wait on RAG ingestion.
- **FR-006**: The operator completion notification and the run's metrics/observability reporting MUST be triggered by the second completion signal (FR-004), and MUST accurately reflect the outcome of every article at every stage, including RAG, with no loss of detail compared to today's single-signal reporting.
- **FR-007**: A failure in any individual article's processing, at any stage, MUST NOT abort, block, or corrupt the processing of any other concurrently-running article.
- **FR-008**: The mechanism used to hand work off between pipeline stages MUST be defined behind one abstract interface, such that its concrete implementation (in-process today; a durable, cross-process mechanism potentially later) can be replaced without changing how any individual stage's processing logic is written.
- **FR-009**: When multiple concurrently-processing articles need the same underlying model capability (analysis and translation share one capability's pool; embeddings are a separate pool), System MUST route concurrent requests across every registered, currently-available model for that capability rather than funneling all requests through a single model while others have spare capacity.
- **FR-010**: System MUST continue to exclude a model only once its daily quota is fully exhausted (as today) — a model that is merely momentarily throttled within its per-minute/per-token window MUST NOT be treated as unavailable if another registered model in the same pool currently has spare capacity.
- **FR-011**: When every registered model for a capability is simultaneously out of capacity, concurrent requests for that capability MUST wait rather than fail outright, resuming automatically once any model in the pool regains capacity.
- **FR-012**: The existing reporting of which model providers hit their daily limit during a run MUST remain accurate when requests are dispatched concurrently across a pool of models, not just a single active one.
- **FR-013**: Database writes performed by concurrently-processing articles MUST be isolated from one another such that one article's in-progress write can never corrupt, block, or be silently overwritten by another's.

### Key Entities

- **Pipeline Run**: One execution of the scheduled scrape-and-process cycle; now tracked by two completion signals (text-complete, fully-complete) instead of a single one.
- **Article Processing Unit of Work**: The scrape-save→analyze→translate→RAG-ingestion chain for one discovered article, now able to progress independently and concurrently alongside other articles' units of work. It settles — succeeds or permanently fails — independently at each stage; a settled outcome (of either kind) counts toward the relevant completion signal (FR-004) and is never retried within the same run.
- **Model Capacity Pool**: The set of registered, active models for one capability (LLM generation, or embeddings), each carrying its own independent quota, from which concurrent requests are routed to whichever member currently has capacity.
- **Stage Handoff Interface**: The abstract boundary through which one pipeline stage's completed work is made available to the next stage, independent of whether the underlying mechanism is in-process or external/durable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a run containing multiple articles where at least one requires RAG ingestion, the time from "all articles fetched" to "every article's analyze and translate work done" no longer scales with the sum of every article's RAG ingestion time.
- **SC-002**: Newly scraped articles become findable through search without waiting for RAG ingestion to finish for the slowest article in the run.
- **SC-003**: 100% of run-completion notifications continue to accurately report the outcome (success, failure, or rate-limit) of every stage for every article, including RAG — zero regression from today's reporting.
- **SC-004**: A run using multiple registered low-quota models for the same capability sustains materially higher total throughput before that capability is fully exhausted, compared to the same run restricted to only its single highest-priority model.
- **SC-005**: Zero incidents, across a full run, of one article's concurrent processing corrupting or blocking another article's data.
- **SC-006**: The stage-handoff mechanism can be replaced with a different implementation by changing that implementation alone — zero changes required to any individual stage's processing logic.

## Assumptions

- This feature is scoped to the collection pipeline (discover→fetch→analyze→translate→RAG ingestion, and the notifications/cache/search-index refresh triggered by its completion). The weekly report pipeline, metrics-refresh job, dedup-reconciliation job, and RAG-backfill job are unaffected and out of scope.
- Concurrency introduced by this feature stays within a single process running a single scheduled scrape. Horizontal scaling across multiple processes/replicas, and any distributed coordination that would require, is explicitly out of scope — the Stage Handoff Interface (FR-008) exists specifically to make that a contained, separate future change rather than something this feature must solve now.
- Database access changes needed to support concurrent article processing are scoped to the repositories used by the collection pipeline (articles, analyses, translations, tags, failed tasks). Repositories used exclusively by the backend API or by other scheduled jobs are unaffected.
- The exact number of articles processed concurrently, and the degree of concurrency within a model capacity pool, are tunable implementation details — this feature does not fix a specific concurrency limit as a requirement.
- Discovery and fetching already run with per-source/per-host concurrency today; that internal concurrency is unrelated to and unchanged by this feature. What this feature deliberately leaves in place (see FR-003) is the *phase boundary* — the fact that every source's fetching and the batched deduplication check must fully finish before any article is published for downstream processing — because that batching is what lets deduplication check every fetched URL against the database in one round trip instead of one per article.
- The external RAG ingestion library already used by this pipeline supports the kind of concurrent operation this feature requires without requiring changes outside this project's own control.
