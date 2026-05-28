# Research: Article Collection

**Phase**: 0 — Architectural Decision Record (Brownfield)
**Date**: 2026-05-28

This document records the architectural decisions already made in the existing codebase,
replacing speculative research with confirmed facts derived from code inspection.

---

## Decision 1: Domain Interface + Infrastructure Implementation Split

**Decision**: `Scraper` ABC lives in `src/modules/collection/domain/services/scraper.py`;
concrete implementations (`RssScraper`, `ArxivScraper`, `BlogScraper`) live in
`src/infrastructure/collection/scrapers/`.

**Rationale**: Hexagonal architecture — domain layer defines the contract; infrastructure
implements it. Allows swapping or mocking scrapers in tests without touching domain logic.

**Alternatives considered**: Monolithic scraper classes mixing discovery and HTTP concerns
(rejected — violates DDD, untestable without real HTTP).

---

## Decision 2: BaseScraper Adds `fetch()` to Domain Interface

**Decision**: `BaseScraper` extends the domain `Scraper` interface by adding an abstract
`fetch(job: ScrapeJob) -> Optional[ScrapedArticle]` method. The domain `Scraper` only declares
`discover()` and `fetch()` at the abstract level; `BaseScraper` is the infrastructure base that
forces concrete scrapers to implement both.

**Rationale**: `discover()` and `fetch()` are always paired in the executor — keeping them on the
same object simplifies the `ScrapeExecutor`'s task dispatch without requiring a separate fetcher
registry.

**Alternatives considered**: Separate `Discoverer` and `Fetcher` interfaces (rejected — overly
complex for a codebase where every source has exactly one discover + one fetch implementation).

---

## Decision 3: Per-Host Semaphore Serialization in ScrapeExecutor

**Decision**: `ScrapeExecutor` groups tasks into per-host queues (`HostQueueMap`) and uses
`BoundedSemaphore(1)` per host. Workers claim a queue index by acquiring the semaphore; if a host
queue is busy, the worker tries the next host. `WeightedRoundRobinQueueSelector` distributes
attempt order to avoid starvation.

**Rationale**: Simple, deterministic per-host serialization without a coordinator process.
Semaphore(1) guarantees at most one concurrent request per host at all times.

**Alternatives considered**: Global rate limiter (rejected — too coarse, allows bursts to one host
while another is idle); asyncio (rejected — existing codebase is sync; thread-based approach is
consistent with the rest of the service).

---

## Decision 4: Streaming vs Fetch-Only Executor Modes

**Decision**: `ScrapeExecutor` exposes two modes — `run()` (fetch-only, backward compatible) and
`run_streaming()` (concurrent discover + fetch). Streaming mode runs discover workers and fetch
workers in the same `ThreadPoolExecutor`, with discover workers routing `FetchTask`s back into
host queues as they become available.

**Rationale**: Streaming reduces wall-clock time by pipelining discovery and fetching. The
fetch-only mode is kept for sources that pre-populate a full job list (e.g., pre-dedup filtered
list from a DB query).

**Alternatives considered**: Sequential discover-then-fetch (retained as `run()` for backward
compat); pure async pipeline (rejected — same reason as Decision 3).

---

## Decision 5: ArXiv 429 → Abort All Remaining ArXiv Discovers This Run

**Decision**: When `ArxivClient` receives HTTP 429, it raises `ArxivRateLimitedError`. The
executor's discover worker loop catches this, adds the host to `_aborted_hosts`, and skips all
subsequent `DiscoverTask`s for that host in the current run. A `on_discover_failed` callback
propagates the failure for recording.

**Rationale**: ArXiv enforces strict rate limits; retrying within the same run will only compound
the violation. Aborting all remaining discovers for the run is safer than per-task retry.

**Alternatives considered**: Per-task retry with exponential backoff (rejected — a 50-minute
pipeline run cannot afford multiple multi-minute backoff windows for a cron job that is expected
to complete within the window).

---

## Decision 6: URL Hash Deduplication

**Decision**: `UrlHash.from_url(url)` produces a SHA-256 hash of a normalised URL (lowercased,
trailing slash stripped, fragment removed). Dedup is performed by `DedupService.find_existing()`
before storage. An existing article without an `Analysis` record is forwarded for re-analysis
instead of being silently dropped.

**Rationale**: Hash-based dedup is O(1) index lookup per article regardless of total article count.
The "duplicate needs analysis" path prevents permanent loss of analysis for articles that were
scraped but not yet analysed in a prior run.

**Alternatives considered**: Full URL string comparison (rejected — case and trailing slash
differences cause false negatives); storing all seen URLs in a set in memory (rejected — not
persistent across cron invocations).

---

## Decision 7: Keyword Filter — Regex, Case-Insensitive, Per-Source Override

**Decision**: Each `RssScraper` holds a compiled regex pattern from a list of keyword strings.
If `keywords=None`, the scraper uses project-level defaults (`_DEFAULT_KEYWORDS`). If
`keywords=[]` (empty list), the scraper accepts all articles (no filter). Source-specific keyword
lists fully replace the default when provided.

**Rationale**: Regex allows multi-word phrases and word-boundary patterns. The three-state
design (default / override / no-filter) covers all practical source configurations without
requiring a separate "accept-all" flag.

**Alternatives considered**: Simple string `in` check (rejected — misses phrase patterns and
produces more false positives); server-side filtering via DB query (rejected — filtering before
fetch saves HTTP requests).

---

## Decision 8: HTML Content Extraction — Selector Cascade with SanitizeService

**Decision**: `HtmlArticleParser` tries a cascade of CSS selectors (`article`, `main`,
`[class*="article-body"]`, etc.) in order, returning the first non-empty match.
`SanitizeService.sanitize_content()` strips scripts, styles, nav, footer, ads, and normalises
whitespace. `BlogScraper` passes a custom selector from its configuration as the first candidate.

**Rationale**: A selector cascade handles the majority of news/blog sites without per-site custom
parsers. The custom selector from `BlogScraper` configuration allows overrides for known layouts.

**Alternatives considered**: ML-based content extraction (rejected — adds heavyweight dependency
for marginal gain on structured news/tech blog content); Readability.js port (rejected — Python
port maintenance overhead).

---

## Decision 9: PDF Extraction for ArXiv

**Decision**: `ArxivScraper` with `fetch_pdf=True` uses `PdfParser` to extract text from the
arXiv PDF URL. HTML abstract from the API response is always available as fallback.

**Rationale**: arXiv papers are primary literature; full PDF content is significantly richer than
the abstract alone for LLM analysis.

**Alternatives considered**: Abstract-only (retained as default when `fetch_pdf=False` or PDF
unavailable); LaTeX source extraction (rejected — parsing complexity disproportionate to gain).
