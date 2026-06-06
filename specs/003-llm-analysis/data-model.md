# Data Model: LLM Article Analysis

**Feature**: 003-llm-analysis | **Date**: 2026-05-29

---

## Domain Entities

### Analysis

The result of applying a language model to a single article. One-to-one with `Article`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key (generated on creation) |
| `article_id` | UUID | FK to Article; unique constraint (one analysis per article) |
| `analysis_content` | AnalysisContent | Structured text fields extracted by the LLM |
| `analysis_metadata` | AnalysisMetadata | Model name and token counts |
| `analyzed_at` | datetime | Timestamp set on persistence |

**Invariants**:
- `article_id` must be unique across all Analysis records.
- All AnalysisContent fields may be null if the LLM response is partial, but at least one field must be non-null for the analysis to be considered successful.
- `analysis_metadata.model_used` must be non-empty.

---

### AnalysisContent (Value Object)

The textual output of the LLM analysis.

| Field | Type | Description |
|-------|------|-------------|
| `summary` | Optional[str] | 2–3 sentence overview of the article |
| `pain_points` | Optional[str] | Problems or challenges identified |
| `insights` | Optional[str] | Key learnings or observations |
| `innovations` | Optional[str] | Novel contributions or techniques |
| `tag_groups` | Optional[List[AnalysisTagGroup]] | Topic classification tags |

---

### AnalysisMetadata (Value Object)

Provenance and cost information for each analysis.

| Field | Type | Description |
|-------|------|-------------|
| `model_used` | str | Identifier of the LLM model that produced the analysis (e.g., `gemini-3-flash-preview`) |
| `input_tokens` | int | Number of tokens in the prompt sent to the provider |
| `output_tokens` | int | Number of tokens in the provider's response |

---

### AnalysisTagGroup (Value Object)

A named group of tags assigned to an article by the LLM.

| Field | Type | Description |
|-------|------|-------------|
| `group` | str | snake_case key identifying the tag category (e.g., `machine_learning`) |
| `tags` | List[str] | Individual tag values within the group |

**State transitions** (for UNSUPERVISED / SEMI_SUPERVISED modes only):
- After analysis: new `AnalysisTagGroup` keys are upserted to `TagGroupDefinition` table.
- Upsert includes computing and storing an embedding vector for cosine-similarity matching.
- If embedding fails, the tag group is still upserted without a vector.

---

### AnalysisResult (Frozen Dataclass — Application Layer)

The return type of `AnalyzeArticleUseCase.execute()`. Not persisted.

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | True if analysis was produced and persisted |
| `analysis` | Optional[Analysis] | Populated on success |
| `article_id` | UUID | Always populated (for tracking) |
| `article_url` | str | Always populated (for tracking) |
| `exception_type` | Optional[str] | Class name of the exception on failure |
| `exception_message` | Optional[str] | Human-readable error message on failure |

---

## Infrastructure Configuration Entities

### LLMProvider (ORM Model — `llm_providers` table)

Runtime configuration for each LLM backend. Loaded at pipeline startup.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | — |
| `name` | str | Provider family: `claude`, `gemini`, `openrouter` |
| `model` | str (unique) | Specific model identifier |
| `api_key_env` | str | Name of the environment variable holding the API key |
| `priority` | int | Fallback order; lower = tried first |
| `type` | str | `llm` or `embedding` |
| `is_active` | bool | Whether this provider is included in the active chain |
| `rpm` | int? | Max requests per minute (null = unlimited) |
| `tpm` | int? | Max tokens per minute (null = unlimited) |
| `rpd` | int? | Max requests per day (null = unlimited) |

**Rate-limit strategy selection**:
- All of `rpm`, `tpm`, `rpd` are null → `NoOpStrategy` (no throttling)
- Any of `rpm`, `tpm`, `rpd` is non-null → `SlidingWindowStrategy`

---

## Persistence Schema (PostgreSQL)

### `analyses` table

```
id            UUID        PK
article_id    UUID        FK(articles.id)  UNIQUE
correlation_id UUID       NOT NULL  (legacy column, generated at save time)
analyzed_at   TIMESTAMP   DEFAULT now()
model_used    VARCHAR
input_tokens  INTEGER
output_tokens INTEGER

INDEX: (article_id)
INDEX: (analyzed_at)
```

### `analyses_translation` table

```
id          UUID        PK
analysis_id UUID        FK(analyses.id)
language    VARCHAR     (e.g., 'en', 'zh-TW')
summary     TEXT
pain_points TEXT
insights    TEXT
innovations TEXT

UNIQUE: (analysis_id, language)
```

**Note**: English content is written here (language='en') as the initial analysis output. Additional languages are added by the translation pipeline (004-translation).

---

## Rate-Limit State (In-Memory)

These are not persisted; they exist only for the lifetime of a single pipeline run.

### SlidingWindowStrategy (per provider instance)

| State | Type | Description |
|-------|------|-------------|
| `_request_window` | deque[(timestamp, count)] | Rolling 60-second request events |
| `_token_window` | deque[(timestamp, count)] | Rolling 60-second token events |
| `_daily_request_count` | int | Cumulative requests since process start |
| `_rpm` | int? | Max requests per 60s window |
| `_tpm` | int? | Max tokens per 60s window |
| `_rpd` | int? | Max requests per day (raises RateLimitExhausted when exceeded) |

**Window behavior**: On each `acquire()`, entries older than 60 seconds are evicted from both deques before checking limits. If the current window sum exceeds the limit, the strategy sleeps until the oldest entry ages out.
