# Research: Article Recommendation Signals & Weekly Summary Report

## 1. Article Metrics Storage: Separate Table vs Extending `articles`

**Decision**: Separate `article_metrics` table with 1:1 FK to `articles`.

**Rationale**: Not all scrapers provide citation counts (only OpenAlex and Semantic Scholar do). Extending the `articles` table with nullable columns for every possible signal pollutes the core entity. A separate table:
- Allows upsert-only pattern (insert on first scrape, update on re-scrape)
- Keeps the `articles` query hot-path clean
- Lets us add future signals (h-index, altmetric score, etc.) without another migration on the primary table

**Alternatives considered**:
- JSONB in `articles.metadata_` column: Already used for scraper-specific metadata but unindexable for sort; the backend `get_articles_paginated` can't efficiently sort on JSONB without a generated column
- Extending `articles` table: Would require all rows to have the new columns, causing confusing NULLs and widening a large table

---

## 2. View Count Tracking: Redis → PostgreSQL Pattern

**Decision**: Redis INCR with IP+article_id dedup (24h TTL), background periodic flush to `article_metrics.view_count`.

**Pattern**:
```
# Increment (in backend /articles/{id}/view endpoint):
key = f"view:{article_id}"          # counter
dedup_key = f"viewed:{ip}:{article_id}"  # dedup

if not redis.exists(dedup_key):
    redis.incr(key)
    redis.expire(dedup_key, 86400)  # 24h dedup window

# Periodic flush (cron or background thread, every 15 minutes):
for key in redis.scan_iter("view:*"):
    article_id = key.split(":")[1]
    count = int(redis.getdel(key))
    db.execute("UPDATE article_metrics SET view_count = view_count + :c WHERE article_id = :id", ...)
```

**Rationale**:
- Atomic INCR avoids race conditions under concurrent requests
- `GETDEL` on flush ensures counts are not lost if flush fails partially (but can double-count if GETDEL succeeds and DB write fails → acceptable for view counts)
- 24h TTL dedup prevents single-user refresh spam from inflating counts

**Alternatives considered**:
- Write directly to PostgreSQL on each view: Too slow under concurrent load; N+1 DB writes for N concurrent viewers
- Authenticated users only: Reduces data volume; excluded because guest mode is supported and guest views still matter

---

## 3. Cloudflare R2 as Blob Storage

**Decision**: boto3 with R2 S3-compatible endpoint.

**Required env vars**:
```
R2_ACCOUNT_ID=           # Cloudflare account ID
R2_ACCESS_KEY_ID=        # R2 API token access key
R2_SECRET_ACCESS_KEY=    # R2 API token secret key
R2_BUCKET_NAME=          # Bucket name (e.g. scrape-analyzer-assets)
R2_PUBLIC_URL=           # Public URL base (e.g. https://assets.yourdomain.com)
```

**Upload pattern**:
```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name='auto',
)

def upload_image(data: bytes, key: str, content_type: str = "image/png") -> str:
    s3.put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=data, ContentType=content_type)
    return f"{R2_PUBLIC_URL}/{key}"
```

**Rationale**: R2 free tier is 10GB storage + 1M Class A ops/month; sufficient for weekly report images at ~1-4MB each (≈ 250+ weeks of coverage). boto3 is already likely available (AWS SDK); if not, it's a standard Python package.

---

## 4. Gemini Imagen for Image Generation

**Decision**: Use `google-genai` SDK with `imagen-3.0-generate-001` model, registered as `LlmProvider` with `type='image'`.

**Pattern** (using newer `google.genai` client):
```python
from google import genai

client = genai.Client(api_key=api_key)
response = client.models.generate_images(
    model='imagen-3.0-generate-001',
    prompt=prompt,
    config=genai.types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio='16:9',
        safety_filter_level='BLOCK_MEDIUM_AND_ABOVE',
    ),
)
image_bytes = response.generated_images[0].image.image_bytes
```

**LlmProvider type extension**: Add `type='image'` to the `LlmProvider` model. The infrastructure layer gets a new `ImageGenerationService` interface (parallel to `LLMService`) and a `GeminiImagenProvider` implementation.

**Prompt template** for weekly report cover:
```
"Abstract digital art representing a weekly technology summary for the topic '{topic_name}'. 
Key themes this week: {top_tags}. Futuristic, clean, data visualization aesthetic."
```

**Alternatives considered**:
- DALL-E 3: Requires new OpenAI API key; Gemini already integrated via GEMINI_API_KEY
- Stable Diffusion via OpenRouter: Additional complexity; image bytes via API

---

## 5. Email Notification: Resend SDK

**Decision**: Use `resend` Python SDK for transactional email.

**Required env vars**:
```
RESEND_API_KEY=          # Resend API key
RESEND_FROM_EMAIL=       # Verified sender (e.g. weekly@yourdomain.com)
```

**Pattern**:
```python
import resend

resend.api_key = RESEND_API_KEY

resend.Emails.send({
    "from": RESEND_FROM_EMAIL,
    "to": user.email,
    "subject": f"Weekly Report: {topic.display_name} — Week of {week_start}",
    "html": render_weekly_report_email(report),
})
```

**Rationale**: Free tier 3,000 emails/month (100/day); zero SMTP infrastructure; clean Python API; no additional service to manage on Railway.

**Alternatives considered**:
- smtplib: No new dependency but requires SMTP server credentials (e.g., Gmail or Mailjet)
- SendGrid: More features but heavier to set up; overkill for weekly reports

---

## 6. Per-User Telegram Notification

**Decision**: Store `telegram_chat_id` in `user_notification_settings` table. Reuse existing `TelegramNotifier` but parameterize `chat_id` per user.

**Change**: Current `TelegramNotifier.notify(event)` always uses `self._chat_id`. New `WeeklyReportNotifier.send_telegram(user, report)` instantiates a transient sender with the user's chat_id. The existing global scraper pipeline notification is unchanged.

**User setup flow** (UI): Settings page → Notification Settings → "Enter your Telegram Chat ID" input → save to `user_notification_settings`. Users obtain their chat_id by messaging `/start` to the bot.

---

## 7. Weekly Report Runner Architecture

**Decision**: New entrypoint `src/entrypoints/cli/weekly_main.py` deployed as a separate Railway Cron Service.

**Schedule**: Every Monday at 08:00 UTC (`0 8 * * 1`).

**Bootstrap function**: New `build_weekly_pipeline()` in `src/bootstrap.py` that wires:
- `WeeklyReportRepository` (reads articles from past 7 days per topic)
- `LLMService` (reuse `ResilientLLMService`)
- `ImageGenerationService` (new, backed by `GeminiImagenProvider`)
- `BlobStorageService` (new, backed by R2)
- `NotificationService` (extended to support per-user weekly report notifications)
- `WeeklyReportUseCase` (new application use case)

**DDD layer structure** (constitution §I compliant):
```
src/modules/weekly_report/
├── domain/
│   ├── entities/weekly_report.py
│   ├── repositories/weekly_report_repository.py
│   └── services/image_generation_service.py  # interface
├── application/
│   └── use_cases/generate_weekly_report_use_case.py
src/infrastructure/
├── weekly_report/
│   └── repositories/weekly_report_repo_impl.py
└── intelligence/
    └── image/
        ├── base_image_provider.py
        └── gemini_imagen_provider.py
└── storage/
    └── r2_blob_storage.py
```

---

## 8. Sort UI Placement

**Decision**: Add sort dropdown to the right of the existing filter trigger button in `filter-bar.tsx`. No new component needed.

**Implementation**: Add `sort` and `order` props to `FilterBar`, render a `<Select>` (Shadcn UI) to the right of the filter toggle button. The sort change fires immediately (no "Apply" needed — unlike filters which are draft-based). This matches the UX expectation that sort is instant while filters require Apply.

**Sort options exposed**:
- Scraped At (default)
- Published At
- Citation Count (desc only initially)
- View Count (desc only initially)
- Source (asc)
- Title (asc)

The backend `GET /articles` already accepts `sort` and `order` params; adding `citation_count` and `view_count` requires a JOIN to `article_metrics` in `get_articles_paginated`.

---

## 9b. Metric Extensibility: Normalized Catalog vs JSONB Blob vs EAV (2026-07-12 revision)

**Decision**: Two normalized tables — `metric_definitions` (maintainer-curated catalog: which metrics exist, which provider supplies each, how to extract the value) and `article_metric_values` (one row per `(article_id, metric_key)`, the actual current value). `article_metrics.citation_count` is removed; `article_metrics` narrows to `view_count` only.

**Rationale**: The original single hardcoded `citation_count` column doesn't scale as more academic signals (impact factor, h-index, altmetric) get added — every new metric would require a new column plus scraper code changes per provider. A `metrics JSONB` blob column was considered first but rejected in favor of proper normalization (per project convention — DB normalization is preferred over denormalized blobs when the value set has stable shape and needs per-key indexing/sorting). An EAV table for *values* is reasonable here because the number of distinct `metric_key`s is small (single digits) and `article_metric_values` needs an index on `(metric_key, value DESC)` for sort/ranking queries (`GET /articles?sort=citation_count`, weekly report article selection) — a JSONB column can't be indexed per-key without a generated column per metric, which reintroduces the original scaling problem one layer down.

**Alternatives considered**:
- `article_metrics.metrics JSONB`: Simple, but un-indexable per key without generated columns (defeats the extensibility goal) and mixes usage signals (view_count, backend-owned) with academic signals (citation_count, src-owned) in one table/refresh-path, which was explicitly identified as undesirable — the two have unrelated data sources and change-frequency characteristics.
- Fully dynamic EAV including the *definitions* (i.e. let admins define new metrics via a DB row containing executable extraction code, akin to pickling a callable): rejected — deserializing/executing stored code is a remote-code-execution risk if that data path is ever reachable by anything less than fully trusted input, and pickled callables are fragile across refactors (see FR-023). Extraction is instead either a data-only JMESPath expression (`extractor_type='json_path'`) or a reference to a fixed, code-reviewed, in-process registry entry (`extractor_type='code'`) — never arbitrary stored code.
- Per-metric nullable columns on `article_metrics` (citation_count, impact_factor, h_index, ...): rejected outright — this is exactly the scaling problem being solved (FR-001).

---

## 9c. JMESPath for Declarative Field Extraction

**Decision**: Use the `jmespath` PyPI package to evaluate `metric_definitions.extractor_spec.path` (e.g. `"cited_by_count"`) against a provider's raw JSON response.

**Rationale**: JMESPath (also used by AWS CLI's `--query`) is a mature, pure-query language with no side effects and no code-execution surface — safe to store as a plain string in the database and evaluate at runtime. It supports simple field access plus light functions (numeric coercion, `min`/`max`, string ops) sufficient for "read this field" and trivial derivations, without opening an arbitrary-code execution path. Added to the `scraper` dependency group in `pyproject.toml`.

**Alternatives considered**: Plain dotted-path strings (`"cited_by_count"` via manual `dict.get()` chaining) — simpler but can't express array indexing/filtering if a future provider's response nests the field inside a list; JMESPath costs one small dependency and covers that case for free. `jsonpath-ng` — less widely used, heavier grammar than needed.

---

## 9d. `metric_definitions` Seed Data Strategy

**Decision**: Seed `metric_definitions` rows (initial `citation_count` → `openalex` priority 1, `citation_count` → `semantic_scholar` priority 2) directly inside the same `23_article_recommendation_weekly_report.py` migration that creates the table.

**Rationale**: Unlike `llm_providers`, which has an admin UI for adding rows after deploy, `metric_definitions` is deliberately **not** dashboard-editable (FR-022) — there is no runtime path to populate it after migration. If it isn't seeded declaratively in the migration, the feature ships with an empty catalog and citation counts never populate. Seeding in the same migration keeps the "what metrics exist" decision in version control and code review, consistent with the catalog being a maintainer-owned artifact.

**Alternatives considered**: Separate follow-up data migration — adds no value here since there's no reason to decouple table creation from its only population path; would just be an extra migration to keep in sync. Manual `psql` insert post-deploy — rejected, not reproducible across environments and leaves fresh deployments (a new Railway environment, a local dev DB) with an empty catalog silently.

---

## 9e. Resolving DOI / arxiv_id for the Refresh Job

**Decision**: DOI and arxiv_id remain inside `articles.metadata` (JSONB) as they are today — no new columns on `articles`. Add two Postgres expression indexes: `CREATE INDEX ... ON articles ((metadata->>'doi'))` and `CREATE INDEX ... ON articles ((metadata->>'arxiv_id'))`, both `WHERE metadata->>'doi' IS NOT NULL` / `WHERE metadata->>'arxiv_id' IS NOT NULL` (partial index — most articles, e.g. RSS/Blog sources, have neither key).

**Rationale**: `articles` is the hot-path table for the whole pipeline; research.md §1 already established the principle of not widening it for per-source signals. DOI/arxiv_id are already present in `metadata` (`openalex_scraper.py`, `semantic_scholar_scraper.py`, `arxiv_scraper.py` all copy them in) — the only gap was query performance for the refresh job's daily scan, which a targeted expression index solves without a schema change to `articles` itself or a data migration to backfill a new column.

**Alternatives considered**: Promoting `doi`/`arxiv_id` to first-class nullable columns on `articles` — rejected per the above; also would sit NULL for the majority of non-academic sources (RSS, Blog), the same "confusing NULLs on a widened hot table" concern research.md §1 raised for signal columns.

---

## 9f. Single-Paper Lookup on `OpenAlexClient` / `SemanticScholarClient`

**Decision**: Add `fetch_by_doi(doi: str) -> Optional[dict]` (and `fetch_by_arxiv_id` where the provider's API supports it) to both clients, returning the **raw parsed JSON dict** (not the existing `OpenAlexEntry`/`SemanticScholarEntry` dataclass) — the dataclass-returning `fetch_papers()` search method is unchanged and untouched.

**Rationale**: Both clients currently only support keyword search (`fetch_papers`) and immediately discard the raw response after mapping it into a dataclass — there is no existing method to fetch a single already-known paper by identifier, which `refresh_metrics.py` fundamentally needs (it already knows the article; it needs today's citation count for that specific paper, not a search). The raw dict (rather than the dataclass) is what `extractor_type='json_path'` evaluates against, since `metric_definitions.extractor_spec.path` expressions are written against the provider's actual JSON field names (e.g. `cited_by_count`), not the internal dataclass's normalized field names.

**Alternatives considered**: Reusing `fetch_papers()` with a DOI-as-query search — unreliable (search relevance ranking, not a guaranteed exact match) and wasteful (searches return multiple candidates when only one specific paper is wanted). Making the dataclasses retain the raw dict — considered, but conflates two different consumers (the existing discovery pipeline, which wants a stable typed shape; metric extraction, which wants raw provider field names) and would leak raw-JSON handling into `fetch_papers()` callers that don't need it.

---

## 9. User Subscription Tables

**Decision**: Two separate tables as suggested by the user.

`user_topic_subscriptions`: user_id (FK auth.users) + topic_id (FK topics), unique constraint on (user_id, topic_id).

`user_notification_settings`: One row per user — email_enabled (bool, default true), telegram_chat_id (nullable), telegram_enabled (bool, default false).

**Rationale**: Separating subscription (which topics) from notification preferences (how to notify) allows independent evolution. A user can subscribe to 3 topics but configure notification channels once.
