# Semantic Tag Normalization Design

**Date:** 2026-05-18
**Branch:** feat/semantic_tag_mgr
**Status:** Approved

## Overview

When the LLM produces tags during article analysis (e.g., "real time sync", "virtual copy"), the same concept often surfaces under slightly different names across articles, causing tag fragmentation. This feature introduces embedding-based semantic deduplication: before a new tag is saved, its vector is compared against existing tags in the same group via cosine similarity. Near-duplicates are either auto-merged or flagged for admin review.

---

## 1. Event Pipeline

### New Event Chain

```
ArticleProcessedEvent
  → ArticleProcessedHandler
      ↓ success
  AnalysisCompletedEvent        (extended with raw tag_groups)
      ↓ success
  TagNormalizationCompletedEvent  ← new
      ↓ success
  (TranslationHandler handles translation)

      ↓ failure at each stage
  AnalysisFailedEvent           → FailedTaskPersistenceHandler  (refactored from AnalysisFailedHandler)
  TagNormalizationFailedEvent   → FailedTaskPersistenceHandler  (same handler)
  TranslationFailedEvent        → FailedTaskPersistenceHandler  (same handler)
```

### bootstrap.py Subscription Table

| Subscribes to | Handler | Publishes |
|---|---|---|
| `ArticleProcessedEvent` | `ArticleProcessedHandler` | `AnalysisCompletedEvent` \| `AnalysisFailedEvent` |
| `AnalysisCompletedEvent` | `TagNormalizationHandler` (new) | `TagNormalizationCompletedEvent` \| `TagNormalizationFailedEvent` |
| `TagNormalizationCompletedEvent` | `AnalysisCompletedHandler` (re-wired, not renamed) | — |
| `AnalysisFailedEvent` | `FailedTaskPersistenceHandler` | — |
| `TagNormalizationFailedEvent` | `FailedTaskPersistenceHandler` | — |
| `TranslationFailedEvent` | `FailedTaskPersistenceHandler` | — |

**Naming note:** Handlers are named after their business responsibility, not the event they consume. The existing `AnalysisCompletedHandler` keeps its name despite now subscribing to `TagNormalizationCompletedEvent`; a future rename-all-handlers refactor can address this separately.

### Single FailedTaskPersistenceHandler

All failed events share the same handler. A `FailedEvent` protocol defines the common interface:

```python
class FailedEvent(Protocol):
    task_type: str
    article_id: Optional[UUID]
    analysis_id: Optional[UUID]
    exception_type: Optional[str]
    exception_message: Optional[str]
    context: Optional[dict]   # stage-specific metadata (language, similarity scores, etc.)
    traceback: Optional[str]
```

The existing `AnalysisFailedHandler` is refactored into `FailedTaskPersistenceHandler` and all three failure events are subscribed to it. Rollback logic stays inside each use case — the handler only persists the record.

---

## 2. Data Layer

### 2a. `tags` table — pgvector column

```sql
-- Enable extension (once per DB)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column (nullable; backfilled by migration)
ALTER TABLE tags ADD COLUMN embedding vector(768);

-- HNSW index for fast ANN search
CREATE INDEX idx_tags_embedding ON tags
USING hnsw (embedding vector_cosine_ops);
```

ORM (`models/tag.py`):
```python
from pgvector.sqlalchemy import Vector
embedding = Column(Vector(768), nullable=True)
```

### 2b. New table: `tag_normalization_suggestions`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `new_tag_id` | UUID FK → tags | LLM-produced tag |
| `existing_tag_id` | UUID FK → tags | Suggested merge target |
| `similarity_score` | FLOAT | Cosine similarity value |
| `status` | VARCHAR(20) | `pending` / `approved` / `rejected` |
| `article_id` | UUID FK → articles | Article that triggered the suggestion |
| `created_at` | TIMESTAMPTZ | — |
| `resolved_at` | TIMESTAMPTZ | When admin acted |
| `resolved_by` | UUID FK → auth.users | Admin who resolved it |

On `approve`: all `article_tags` rows pointing to `new_tag_id` are re-pointed to `existing_tag_id` (with `ON CONFLICT DO NOTHING`), then `new_tag_id` is deleted — all in one transaction.

### 2c. `failed_tasks` table — new columns

| New Column | Type | Notes |
|---|---|---|
| `analysis_id` | UUID FK → analyses (nullable) | For tag normalization / translation failures |
| `context` | JSONB (nullable) | Arbitrary metadata (similarity scores, target language, etc.) |
| `traceback` | Text (nullable) | Full Python stack trace |

New valid `task_type` values: `tag_normalization`, `translate_article`, `translate_tags`.

### 2d. Configuration

Thresholds live in `providers.toml`, not the DB:

```toml
[tag_normalization]
auto_merge_threshold = 0.92   # similarity >= this → auto-merge
suggest_threshold    = 0.85   # similarity in [suggest, auto_merge) → pending suggestion
embedding_model      = "text-embedding-004"
```

---

## 3. Domain Layer

### 3a. Fix: AnalysisTagGroup VO

`TagGroup(display_name, description)` was being misused in `AnalysisContent` — `description` held comma-separated tag names. Introduce a dedicated VO:

```python
# src/modules/intelligence/domain/value_objects/analysis_tag_group.py
class AnalysisTagGroup(NamedTuple):
    group_name: str      # LLM group key, e.g. "digital_twin"
    tags: List[str]      # ["virtual replica", "real-time sync"]
```

`AnalysisContent.tag_groups` changes from `List[TagGroup]` to `List[AnalysisTagGroup]`.

### 3b. AnalysisCompletedEvent — extended

```python
@dataclass(frozen=True)
class AnalysisCompletedEvent:
    analysis_id: UUID
    article_id: UUID
    tag_groups: List[Tuple[str, List[str]]]  # [(group_name, [tag_names])]
```

The raw tag data is carried in the event so `TagNormalizationHandler` needs no extra DB round-trip.

### 3c. New Domain Service Interface

```python
# src/modules/intelligence/domain/services/embedding_service.py
class EmbeddingService(ABC):
    def embed(self, text: str) -> List[float]: ...
    def embed_batch(self, texts: List[str]) -> List[List[float]]: ...
```

### 3d. New Domain Repository Interface

```python
# src/modules/intelligence/domain/repositories/tag_repository.py
class TagRepository(ABC):
    def find_by_group(self, group_name: str) -> List[Tag]: ...
    def find_similar(
        self, embedding: List[float], group_name: str, threshold: float
    ) -> List[Tuple[Tag, float]]: ...
    def save(self, tag: Tag) -> Tag: ...
    def link_to_article(self, tag_id: UUID, article_id: UUID) -> None: ...
    def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> None: ...
    def list_pending_suggestions(self) -> List[TagNormalizationSuggestion]: ...
    def approve_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None: ...
    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None: ...
```

### 3e. New Domain Entity

```python
# src/modules/intelligence/domain/entities/tag_normalization_suggestion.py
@dataclass
class TagNormalizationSuggestion:
    new_tag_id: UUID
    existing_tag_id: UUID
    similarity_score: float
    article_id: UUID
    status: str = "pending"           # pending | approved | rejected
    id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
```

### 3f. NormalizeTagsUseCase

**Location:** `src/modules/intelligence/application/use_cases/normalize_tags.py`

**Inputs:** `analysis_id`, `article_id`, `tag_groups: List[Tuple[str, List[str]]]`

**Algorithm per tag:**

```
embed(tag_name)
→ find_similar(embedding, group_name, threshold=suggest_threshold)
→ if best_similarity >= auto_merge_threshold:
      link existing_tag to article
  elif best_similarity >= suggest_threshold:
      save new_tag (with embedding)
      link new_tag to article
      save TagNormalizationSuggestion(status=pending)
  else:
      save new_tag (with embedding)
      link new_tag to article
```

**Publishes:** `TagNormalizationCompletedEvent` | `TagNormalizationFailedEvent`

---

## 4. Infrastructure Layer

### 4a. GeminiEmbeddingProvider

**Location:** `src/infrastructure/intelligence/embedding/gemini_embedding_provider.py`

- Uses `google.genai` (already a dependency)
- `task_type="CLASSIFICATION"` for tag embedding
- `embed_batch`: max 100 texts per call (Gemini API limit)
- Config read from `providers.toml [tag_normalization]`

### 4b. SqlAlchemyTagRepository

**Location:** `src/infrastructure/persistence/intelligence/tag_repo_impl.py`

`find_similar` uses pgvector cosine distance operator:

```sql
SELECT id, name, tag_group_name,
       1 - (embedding <=> :query_vec) AS similarity
FROM tags
WHERE tag_group_name = :group_name
  AND embedding IS NOT NULL
  AND 1 - (embedding <=> :query_vec) >= :threshold
ORDER BY embedding <=> :query_vec
LIMIT 5;
```

`approve_suggestion` (single transaction):
1. `UPDATE article_tags SET tag_id = existing_tag_id WHERE tag_id = new_tag_id ON CONFLICT DO NOTHING`
2. `DELETE FROM tags WHERE id = new_tag_id`
3. `UPDATE tag_normalization_suggestions SET status='approved', resolved_at=now(), resolved_by=... WHERE id=...`

### 4c. analysis_repo_impl.py — remove tag logic

The following block is removed from `save()` and ownership transferred to `NormalizeTagsUseCase`:

```python
# REMOVED — entire tag resolution block:
if article_row and content.tag_groups:
    for tg in content.tag_groups:
        group_name = tg.display_name
        for tag_name in tg.description.split(", "):
            ...
```

### 4d. Alembic Migrations

Two migrations (run in order):

**`16_add_pgvector_and_tag_normalization`**
- `CREATE EXTENSION IF NOT EXISTS vector`
- Add `embedding vector(768)` to `tags`
- Create `tag_normalization_suggestions` table
- Create HNSW index on `tags.embedding`

**`17_extend_failed_tasks`**
- Add `analysis_id`, `context`, `traceback` columns to `failed_tasks`

**Backfill script** (one-off, run after migration):
- `scripts/backfill_tag_embeddings.py`
- Iterates all existing tags in batches, calls Gemini `embed_batch`, updates `embedding` column

---

## 5. Backend API

**New router:** `backend/routers/tags.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/tag-groups` | Public | List all tag groups with tags and article counts |
| POST | `/tag-groups` | Admin | Create tag group |
| PUT | `/tag-groups/{id}` | Admin | Update tag group (name, color, etc.) |
| DELETE | `/tag-groups/{id}` | Admin | Delete tag group and all its tags |
| PUT | `/tags/{id}` | Admin | Rename tag |
| DELETE | `/tags/{id}` | Admin | Delete tag and remove all article associations |
| GET | `/tag-normalization-suggestions` | Admin | List pending suggestions |
| POST | `/tag-normalization-suggestions/{id}/approve` | Admin | Approve merge |
| POST | `/tag-normalization-suggestions/{id}/reject` | Admin | Reject merge |

`GET /tag-groups` response:
```json
[
  {
    "id": "uuid",
    "name": "digital_twin",
    "display_name": "Digital Twin",
    "color_hex": "#3b82f6",
    "topic_id": "uuid",
    "tags": [
      { "id": "uuid", "name": "virtual replica", "article_count": 12 }
    ]
  }
]
```

---

## 6. Frontend

### NavBar

Add "Tags" link after "Knowledge Graph":

```
Articles | Knowledge Graph | Tags
```

`/tags` is a public route (no login required).

### `/tags` Page

**All users:** Tag group cards, each showing tags with article counts.

**Admin extras:**
- Edit / delete buttons on each group card
- Rename / delete on each tag
- "Add tag" button per group
- **Pending Suggestions block** at the top of the page (admin-only)

### Pending Suggestions Block

Displayed only when `session.user.role === 'admin'` and there are pending suggestions.

```
┌──────────────────────────────────────────────────────────┐
│  Pending Merge Suggestions  (3)                          │
│                                                          │
│  "real time sync"  →  "real-time sync"                   │
│  Digital Twin · similarity 0.89     [Merge]  [Keep both] │
│                                                          │
│  "virtual copy"  →  "virtual replica"                    │
│  Digital Twin · similarity 0.87     [Merge]  [Keep both] │
└──────────────────────────────────────────────────────────┘
```

- **Merge** → `POST /tag-normalization-suggestions/{id}/approve`, suggestion removed, tag article counts updated
- **Keep both** → `POST /tag-normalization-suggestions/{id}/reject`, suggestion removed, both tags remain

### New Files

```
frontend/
├── app/tags/
│   └── page.tsx
├── lib/api/
│   └── tags.ts
└── components/features/tags/
    ├── tag-group-card.tsx
    └── pending-suggestions.tsx
```

---

## Implementation Order

1. Alembic migration 16 (pgvector + tag_normalization_suggestions)
2. Alembic migration 17 (extend failed_tasks)
3. ORM model updates (tags, new models)
4. Domain layer (AnalysisTagGroup VO, EmbeddingService, TagRepository, TagNormalizationSuggestion, NormalizeTagsUseCase)
5. Infrastructure (GeminiEmbeddingProvider, SqlAlchemyTagRepository)
6. Refactor analysis_repo_impl (remove tag logic)
7. New events (TagNormalizationCompletedEvent, TagNormalizationFailedEvent, TranslationFailedEvent) + FailedEvent protocol
8. Refactor AnalysisFailedHandler → FailedTaskPersistenceHandler; add TagNormalizationHandler
9. bootstrap.py re-wiring
10. Backfill script (scripts/backfill_tag_embeddings.py)
11. Backend API (tags router)
12. Frontend (/tags page + NavBar)
