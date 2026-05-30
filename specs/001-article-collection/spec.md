# Feature Specification: Article Collection

**Feature Branch**: `001-article-collection`

**Created**: 2026-05-28

**Status**: Brownfield (documents existing behaviour)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Articles Discovered and Stored (Priority: P1)

As a system operator, when the scraper pipeline runs, new articles from configured sources
(RSS feeds, arXiv, and tech blogs) are discovered, fetched, and made available for downstream
analysis — without manual intervention.

**Why this priority**: This is the core purpose of the service. Without it, nothing else works.

**Independent Test**: Trigger a pipeline run against a live or mocked RSS source; verify that
new articles appear in the article store with correct title, URL, content, and source.

**Acceptance Scenarios**:

1. **Given** an RSS source configured with a keyword filter, **when** the pipeline runs, **then**
   only articles whose title or description match at least one keyword are collected.

2. **Given** an arXiv source configured with a category and keyword filter, **when** the pipeline
   runs, **then** papers published within the configured lookback window are collected, up to the
   configured maximum.

3. **Given** a blog source configured with CSS selectors, **when** the pipeline runs, **then**
   article URLs are discovered from listing pages and full content is extracted from each article URL.

4. **Given** an article URL that returns HTML content, **when** the fetcher processes it,
   **then** the stored content is sanitised plain text (scripts, nav, footer, ads removed).

5. **Given** an arXiv paper with a publicly available PDF, **when** fetched with PDF mode enabled,
   **then** the stored content includes text extracted from the PDF.

---

### User Story 2 - Duplicate Articles Are Skipped (Priority: P2)

As a system operator, when the same article URL appears in multiple scraper runs, it is not stored
twice — but if the existing record has not been analysed yet, it is forwarded for analysis.

**Why this priority**: Prevents content duplication and unnecessary LLM costs.

**Independent Test**: Run the pipeline twice for the same source; verify the article count does not
grow on the second run, and no duplicate records exist in the article store.

**Acceptance Scenarios**:

1. **Given** an article URL already stored and already analysed, **when** the same URL is
   encountered during a subsequent pipeline run, **then** the article is silently skipped.

2. **Given** an article URL already stored but not yet analysed, **when** the same URL is
   encountered, **then** the article is forwarded to the analysis stage without creating a new record.

---

### User Story 3 - Source Failures Do Not Halt the Pipeline (Priority: P3)

As a system operator, when one scraper source is unavailable or returns errors, the pipeline
continues processing remaining sources.

**Why this priority**: A single broken RSS feed should not cancel the entire daily run.

**Independent Test**: Configure one source with an unreachable URL and one with a valid URL; verify
articles from the valid source are still collected and a failure is recorded for the broken source.

**Acceptance Scenarios**:

1. **Given** an RSS feed URL that returns a 4xx or 5xx error, **when** the pipeline runs,
   **then** the error is logged, the source is skipped, and remaining sources continue.

2. **Given** an article URL that times out during fetch, **when** the pipeline runs,
   **then** the failure is recorded and the pipeline continues with other articles.

3. **Given** the arXiv API returning a rate-limit response (HTTP 429), **when** the pipeline runs,
   **then** all remaining arXiv discover tasks for this run are skipped, a failure is recorded,
   and non-arXiv sources are unaffected.

---

### User Story 4 - Per-Host Concurrency Is Bounded (Priority: P4)

As a system operator, the pipeline respects per-host rate limits so that scraped sites are not
overwhelmed and the scraper is not blocked.

**Why this priority**: Overly aggressive scraping risks IP bans and robots.txt violations.

**Independent Test**: Instrument fetch calls to the same host; verify no two concurrent requests
to the same hostname are in-flight at the same time.

**Acceptance Scenarios**:

1. **Given** multiple articles from the same hostname, **when** the executor runs,
   **then** at most one request to that host is in-flight at any time.

2. **Given** a configured inter-fetch delay, **when** the executor runs,
   **then** successive fetches from the same worker are separated by at least the configured delay.

3. **Given** a blog source with a `robots.txt` disallowing the scraper, **when** the executor runs,
   **then** article URLs from that source are not fetched and failures are recorded.

---

### Edge Cases

- What happens when sanitised HTML content is empty or whitespace-only after stripping?
  → The article is recorded as a fetch failure; no empty-content record is stored.
- What happens when an RSS feed contains duplicate entries within the same feed response?
  → Each entry is evaluated independently; dedup by URL hash eliminates duplicates before storage.
- What happens when an article's content exceeds the maximum allowed length?
  → Content is truncated to the configured maximum before storage.
- What happens when a new source is added to configuration mid-run?
  → Sources are read at pipeline start; a mid-run config change has no effect on the current run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support three source types: RSS feeds, arXiv API, and blog listing pages.
- **FR-002**: Each source MUST be independently configurable with keyword filters, topic association, and a custom LLM prompt override.
- **FR-003**: The system MUST filter articles by keyword match against title and description/abstract before fetching full content; when no keyword filter is configured for a source, all articles MUST be accepted.
- **FR-004**: The system MUST deduplicate articles by URL before storage using a deterministic URL hash.
- **FR-005**: The system MUST forward existing articles that lack an analysis record to the analysis stage without creating duplicate storage records.
- **FR-006**: The system MUST extract plain-text content from HTML pages, removing navigation, advertisement, script, and style elements.
- **FR-007**: The system MUST extract text content from PDF documents when fetching arXiv papers with PDF mode enabled.
- **FR-008**: The system MUST publish a notification event for each successfully collected article so downstream stages can react.
- **FR-009**: The system MUST enforce at most one concurrent request per hostname across all fetch workers.
- **FR-010**: The system MUST apply a configurable delay between successive fetches per worker.
- **FR-011**: The system MUST abort all remaining arXiv discover tasks in the current run when an HTTP 429 response is received from the arXiv API.
- **FR-012**: The system MUST respect `robots.txt` directives when fetching blog article pages.
- **FR-013**: The system MUST record failures for individual article fetch errors without halting the overall pipeline run.
- **FR-014**: The system MUST support concurrent discover and fetch phases running simultaneously (streaming mode) in addition to a sequential fetch-only mode.

### Key Entities

- **ScraperSetting**: Configuration for one scraper source — source type, URL, keyword filters,
  topic association, prompt override, and operational flags.
- **ScrapeJob**: A pending fetch task produced by the discover phase — URL, source name, source type,
  topic ID, prompt override, and raw metadata (title, description, authors, published date).
- **ScrapedArticle**: The result of a successful fetch — URL, title, sanitised content, source,
  topic ID, publication date, authors, and source-specific metadata.
- **UrlHash**: A deterministic identifier derived from a normalised article URL, used as the
  deduplication key.
- **ArticleScrapedEvent**: A domain event carrying a `ScrapedArticle` payload, published to the
  event bus after a successful fetch for downstream consumption.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of articles successfully discovered in the discover phase are either
  stored or correctly identified as duplicates within a single pipeline run.
- **SC-002**: A pipeline run with one unavailable source completes and still produces articles from
  all remaining healthy sources.
- **SC-003**: No two simultaneous requests to the same hostname are ever in-flight during a pipeline
  run (zero concurrency violations per host).
- **SC-004**: An arXiv rate-limit event does not cause article loss from RSS or blog sources in the
  same run.
- **SC-005**: The article store contains no duplicate records (identical URL hash) after any number
  of pipeline runs over the same source set.

## Assumptions

- Keyword filtering for arXiv uses the same pattern-matching logic as RSS (regex, case-insensitive);
  the source-level keyword list overrides the project-level default when provided.
- PDF extraction is attempted only when the arXiv paper metadata indicates a PDF is available and
  the scraper is configured with `fetch_pdf=True`; HTML abstract is used as fallback.
- Blog sources rely on configurable CSS selectors for listing-page link extraction; no generic
  heuristic is assumed.
- The event bus is in-process and synchronous; no message broker or persistence is assumed for
  `ArticleScrapedEvent`.
- `robots.txt` compliance is enforced for blog scrapers only; RSS and arXiv API sources are
  exempt (they are purpose-built APIs or feed endpoints).
- Content length truncation limit is a configuration value; the default is 50,000 characters.
