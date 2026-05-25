# Tag Mode: Three-Tier Design

**Date:** 2026-05-25
**Branch:** feat/semantic_tag_mgr
**Status:** Approved

## Background

Article analysis currently supports two tag generation modes via `Topic.auto_tag_groups: bool`:
- `True` → **auto**: LLM freely generates tag groups
- `False` → **fixed**: LLM is constrained to predefined DB tag groups

This replaces the boolean with a three-tier `tag_mode` to reflect how admin knowledge of a domain evolves over time.

## Three Modes

| Mode | Value | Behaviour |
|------|-------|-----------|
| Unsupervised | `unsupervised` | LLM generates tag groups freely (current auto behaviour) |
| Semi-supervised | `semi_supervised` | LLM receives existing groups as reference hints; may also create new groups |
| Supervised | `supervised` | LLM is constrained to predefined groups only (current fixed behaviour) |

**New group upsert logic:**
- `unsupervised` + `semi_supervised`: LLM-generated groups are upserted to DB automatically
- `supervised`: no upsert; groups are managed manually by admin

## Architecture

### DB / Models (`models/`)

**`models/topic.py`**
- Remove `auto_tag_groups = Column(Boolean, ...)`
- Add `tag_mode = Column(String(20), nullable=False, default='unsupervised')`

**Alembic migration** (single revision):
1. `ADD COLUMN tag_mode VARCHAR(20) NOT NULL DEFAULT 'unsupervised'`
2. `UPDATE topics SET tag_mode = CASE WHEN auto_tag_groups = TRUE THEN 'unsupervised' ELSE 'supervised' END`
3. `ALTER COLUMN tag_mode DROP DEFAULT`
4. `DROP COLUMN auto_tag_groups`

### Domain (`src/`)

**New value object** — `TagMode(str, Enum)`:
```python
class TagMode(str, Enum):
    UNSUPERVISED = 'unsupervised'
    SEMI_SUPERVISED = 'semi_supervised'
    SUPERVISED = 'supervised'
```
Location: `src/shared/domain/value_objects/` or inline in `topic.py` entity.

**`src/shared/domain/entities/topic.py`**
- `auto_tag_groups: bool = True` → `tag_mode: TagMode = TagMode.UNSUPERVISED`

**`src/modules/intelligence/domain/value_objects/analysis_prompt.py`**

New `_SEMI_TEMPLATE`:
```python
_SEMI_TEMPLATE = """You are a professional technology analyst specializing in __TOPIC__.

Analyze the following article and classify it into relevant tag groups.
The following tag groups already exist for this topic — prefer reusing them when they fit,
but you may also create new snake_case groups if the article covers something genuinely different:

EXISTING TAG GROUPS:
__TAG_GROUPS__

For each applicable group, generate 2-4 specific sub-tags describing the article's focus.
Assign 1-3 groups total; only include groups truly relevant to the article.
""" + _COMMON_EXTRACTION
```

New method `render_semi(topic: str, tag_groups: List[TagGroup]) -> AnalysisPrompt` — same signature as `render_fixed` but uses `_SEMI_TEMPLATE`.

**`src/modules/intelligence/application/use_cases/analyze_article.py`**

`_build_prompt` three-tier logic:
```
SUPERVISED      → render_fixed  (constrained to predefined groups)
SEMI_SUPERVISED → render_semi   (existing groups as hints, new groups allowed)
UNSUPERVISED    → render_auto   (fully free generation)
```

`_upsert_generated_tag_groups` call site:
- Move the `if topic.auto_tag_groups` guard to allow upsert for both `UNSUPERVISED` and `SEMI_SUPERVISED`
- Skip upsert for `SUPERVISED`

**Topic repo impl** (`src/infrastructure/persistence/`):
- Update ORM → domain entity mapping: read `tag_mode` string, construct `TagMode` enum

### Backend (`backend/`)

**`backend/schemas/topic.py`**
```python
class TagMode(str, Enum):
    unsupervised = 'unsupervised'
    semi_supervised = 'semi_supervised'
    supervised = 'supervised'

class TopicCreate(BaseModel):
    # existing fields ...
    tag_mode: TagMode = TagMode.unsupervised

class TopicUpdate(BaseModel):
    # existing fields ...
    tag_mode: Optional[TagMode] = None   # replaces auto_tag_groups

class TopicOut(BaseModel):
    # existing fields ...
    tag_mode: TagMode                    # replaces auto_tag_groups: bool
```

**`backend/routers/topics.py`** — no changes needed.

### Frontend (`frontend/`)

**`lib/api/topics.ts`**
```typescript
export interface Topic {
  // existing fields ...
  tag_mode: 'unsupervised' | 'semi_supervised' | 'supervised'  // replaces auto_tag_groups
}
```

**New component: `components/features/tags/tag-mode-selector.tsx`**

Segmented control built on Radix `TabsList` + `TabsTrigger` (no TabsContent).
Props: `value`, `onChange`, `disabled?`.
Displays three labelled options using i18n keys.

**New story: `stories/TagModeSelector.stories.tsx`**

Stories covering:
- Default (unsupervised selected)
- Semi-supervised selected
- Supervised selected
- Disabled state

**`app/tags/page.tsx`**
- Remove `autoTagGroups: boolean` state
- Add `tagMode: TagMode` state (initialised from `selectedTopic?.tag_mode`)
- Replace boolean `Switch` with `TagModeSelector`
- PATCH payload: `{ tag_mode: newMode }`

**`app/admin/topics/page.tsx`**
- Add `tag_mode` to `form` state in both `TopicRow` (edit) and `AddTopicCard` (create)
- Add `TagModeSelector` to both forms
- Include `tag_mode` in `handleSave` / `handleAdd` payloads

**`i18n/` (both locales)**

New keys:
- `tags.tagMode`
- `tags.unsupervised` / `tags.unsupervisedDesc`
- `tags.semiSupervised` / `tags.semiSupervisedDesc`
- `tags.supervised` / `tags.supervisedDesc`

## File Change Summary

| Layer | File | Change |
|-------|------|--------|
| DB | `models/topic.py` | Replace column |
| DB | `alembic/versions/18_tag_mode.py` | New migration |
| Domain | `src/shared/domain/entities/topic.py` | Replace field |
| Domain | `src/shared/domain/value_objects/tag_mode.py` (new) | TagMode enum |
| Domain | `src/modules/intelligence/domain/value_objects/analysis_prompt.py` | Add `_SEMI_TEMPLATE` + `render_semi` |
| Application | `src/modules/intelligence/application/use_cases/analyze_article.py` | Three-tier prompt + upsert logic |
| Infrastructure | topic repo impl | Update mapping |
| Backend | `backend/schemas/topic.py` | Replace field in all 3 schemas |
| Frontend | `frontend/lib/api/topics.ts` | Update `Topic` type |
| Frontend | `frontend/components/features/tags/tag-mode-selector.tsx` (new) | Segmented control |
| Frontend | `frontend/stories/TagModeSelector.stories.tsx` (new) | Storybook stories |
| Frontend | `frontend/app/tags/page.tsx` | Switch → TagModeSelector |
| Frontend | `frontend/app/admin/topics/page.tsx` | Add mode selector to forms |
| Frontend | `frontend/i18n/*.json` × 2 | New translation keys |
