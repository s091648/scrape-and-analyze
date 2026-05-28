# Feature Specification: Article Processing

**Feature Branch**: `002-article-processing`

**Created**: 2026-05-29

**Status**: Draft

**Input**: User description: "描述 002-article-processing capability 的現有行為，包含 DedupService 和 ProcessScrapedArticleUseCase 的去重邏輯、文章儲存、事件發布等行為"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Article Saved and Queued (Priority: P1)

When a newly scraped article arrives in the system, it should be deduplicated, persisted, and queued for downstream analysis — without any manual intervention.

**Why this priority**: This is the core happy-path of the entire ingestion pipeline. Without it, no article ever enters the system.

**Independent Test**: Trigger a single scraped-article event for a URL not yet in the system. Verify the article appears in persistent storage and an `ArticleProcessed` notification is emitted.

**Acceptance Scenarios**:

1. **Given** a scraped article event arrives with a URL not previously seen, **When** the system processes the event, **Then** the article is stored exactly once and a downstream processing signal is published.
2. **Given** an article is from the ArXiv source and carries author and section metadata, **When** the system saves it, **Then** the supplementary metadata (authors, PDF availability, sections) is also persisted alongside the article.
3. **Given** the persistent store is temporarily unavailable, **When** the save attempt fails, **Then** the system logs the failure, returns a failure outcome, and does NOT publish a downstream signal.

---

### User Story 2 - Duplicate URL Silently Skipped (Priority: P2)

When a scraper re-encounters an article URL that already has a completed analysis in the system, the article should be quietly ignored to avoid duplicate processing.

**Why this priority**: Feeds often re-publish the same URLs. Without deduplication, the system would re-analyze and re-store the same article on every scrape cycle.

**Independent Test**: Insert an article with a completed analysis. Re-submit an event for the same URL. Verify no new record is created and no downstream signal is emitted.

**Acceptance Scenarios**:

1. **Given** an article with a completed analysis already exists in the system, **When** an event arrives for the same URL, **Then** the system records a "duplicate" outcome and emits no downstream signals.
2. **Given** a URL is submitted multiple times in rapid succession, **When** all events are processed, **Then** only one article record exists in the system.

---

### User Story 3 - Duplicate Without Analysis Re-Queued (Priority: P2)

When a previously saved article exists but was never analyzed (e.g., due to a prior LLM failure), the system should re-queue it for analysis without creating a duplicate storage record.

**Why this priority**: Ensures resilience across scrape cycles — articles that failed mid-pipeline are automatically recovered on the next run.

**Independent Test**: Insert an article record with no associated analysis. Submit an event for the same URL. Verify no new storage record is created but a downstream processing signal IS published for the existing article.

**Acceptance Scenarios**:

1. **Given** an article exists in storage without a completed analysis, **When** an event arrives for the same URL, **Then** the system returns the existing article and publishes a downstream processing signal — without creating a new record.
2. **Given** an ArXiv article exists without analysis and has stored section data, **When** it is re-queued, **Then** the section data is merged back into the article so the downstream analyzer has full context.

---

### Edge Cases

- What happens when the URL is empty or malformed?
- How does the system behave when the article content is empty but the URL is valid?
- What if ArXiv metadata save fails after the article itself was already saved — is the article still accepted?
- What happens when the same URL is submitted concurrently by two scrape workers?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST deduplicate incoming articles by URL before persisting, using a deterministic hash of the normalized URL.
- **FR-002**: The system MUST persist new articles with their source, title, content, publication date, topic association, and any source-specific metadata.
- **FR-003**: The system MUST distinguish three processing outcomes for any incoming article: newly saved, already-analyzed duplicate, or duplicate awaiting analysis.
- **FR-004**: The system MUST publish a downstream processing signal only when an article requires further analysis (new articles and un-analyzed duplicates).
- **FR-005**: The system MUST persist supplementary ArXiv metadata (authors, PDF availability, section text) separately from the core article record when the source is ArXiv.
- **FR-006**: The system MUST NOT publish a downstream signal when an article save fails, and MUST record the failure for observability.
- **FR-007**: When re-queueing an un-analyzed ArXiv article, the system MUST enrich the article with its previously stored section data before signaling downstream.

### Key Entities

- **Article**: Core record representing a scraped piece of content. Identified by URL hash. Carries source, title, full content, publication timestamp, topic association, and arbitrary source metadata.
- **UrlHash**: Deterministic fingerprint of a URL (SHA-256). Used as the primary deduplication key.
- **ArticleOutcome**: Classification of a processing result — one of: new, duplicate (already analyzed), duplicate awaiting analysis, or failed.
- **ArxivMetadata**: Supplementary record for ArXiv articles. Stores authors, PDF availability flag, and extracted section text, linked to an Article.
- **ArticleProcessedEvent**: Signal published when an article (new or re-queued) is ready for downstream analysis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every article URL submitted to the processing pipeline is either stored exactly once or explicitly classified as a duplicate — no silent duplicates in storage.
- **SC-002**: Re-submitted URLs for already-analyzed articles produce zero new storage records and zero downstream signals.
- **SC-003**: Re-submitted URLs for un-analyzed articles produce zero new storage records but exactly one downstream signal per re-submission.
- **SC-004**: Save failures are recoverable — articles that fail on one pipeline run can be successfully re-processed on the next run with no manual intervention.
- **SC-005**: ArXiv articles that are re-queued for analysis carry their full section text, ensuring analysis quality is equivalent to the original submission.

## Assumptions

- The upstream scrape pipeline guarantees that every incoming event carries a non-empty URL and non-empty content.
- URL deduplication is URL-exact: two articles at different URLs are always treated as distinct, even if their content is identical.
- ArXiv metadata save failure is non-fatal: the article is still accepted into the system; missing metadata is tolerable.
- Concurrent duplicate submissions of the same URL may result in a harmless race; at most one record will ultimately survive in storage (enforced by a unique constraint on URL hash at the persistence layer).
- The downstream analysis pipeline is a separate capability (003-llm-analysis) and is not part of this specification.
