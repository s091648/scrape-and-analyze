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

## 9. User Subscription Tables

**Decision**: Two separate tables as suggested by the user.

`user_topic_subscriptions`: user_id (FK auth.users) + topic_id (FK topics), unique constraint on (user_id, topic_id).

`user_notification_settings`: One row per user — email_enabled (bool, default true), telegram_chat_id (nullable), telegram_enabled (bool, default false).

**Rationale**: Separating subscription (which topics) from notification preferences (how to notify) allows independent evolution. A user can subscribe to 3 topics but configure notification channels once.
