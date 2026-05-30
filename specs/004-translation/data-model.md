# Data Model: Translation

**Feature**: 004-translation | **Date**: 2026-05-29

## Entities

### AnalysesContent (Domain Entity)

Translation of an article's analysis content in a specific language.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, auto-generated | |
| analysis_id | UUID | FK → analyses.id, NOT NULL | Parent analysis |
| language | VARCHAR(10) | NOT NULL | Target language code (e.g., "zh-TW") |
| summary | TEXT | nullable | Translated summary |
| pain_points | TEXT | nullable | Translated pain points |
| insights | TEXT | nullable | Translated insights |
| innovations | TEXT | nullable | Translated innovations |
| created_at | DATETIME | NOT NULL | |
| updated_at | DATETIME | NOT NULL | |

**Unique constraint**: `(analysis_id, language)` — one translation per analysis per language.

**Indexes**: `analysis_id`, `language`.

**Relationships**: Many-to-one with `Analysis` (CASCADE delete).

---

### TagsTranslation (ORM Model)

Translation of a tag name in a specific language.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| tag_id | UUID | FK → tags.id, NOT NULL | Parent tag |
| language | VARCHAR(10) | NOT NULL | Target language code |
| name | TEXT | NOT NULL | Translated tag name |
| created_at | DATETIME | NOT NULL | |

**Unique constraint**: `(tag_id, language)` — one translation per tag per language.

**Indexes**: `tag_id`, `language`.

**Relationships**: Many-to-one with `Tag` (CASCADE delete).

---

### TagGroupDefinitionsTranslation (ORM Model)

Translation of a tag group display name and description in a specific language.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| tag_group_definition_id | UUID | FK → tag_group_definitions.id, NOT NULL | Parent group |
| language | VARCHAR(10) | NOT NULL | Target language code |
| display_name | VARCHAR(200) | NOT NULL | Translated display name |
| description | TEXT | nullable | Translated description |
| created_at | DATETIME | NOT NULL | |

**Unique constraint**: `(tag_group_definition_id, language)` — one translation per group per language.

**Indexes**: `tag_group_definition_id`, `language`.

**Relationships**: Many-to-one with `TagGroupDefinition` (CASCADE delete).

---

## Value Objects

### AnalysesTranslationContent

Content-only value object used in the translation result (no IDs or language).

| Field | Type | Notes |
|-------|------|-------|
| summary | Optional[str] | |
| pain_points | Optional[str] | |
| insights | Optional[str] | |
| innovations | Optional[str] | |

### AnalysesTranslationResult

Result of a translation attempt.

| Field | Type | Notes |
|-------|------|-------|
| analysis_id | UUID | |
| language | str | |
| content | AnalysesTranslationContent | |
| success | bool | False when LLM fails or save fails |

### Translation Prompt Value Objects

| Prompt Class | Placeholders | Render Method |
|--------------|-------------|---------------|
| ArticleTranslationPrompt | `__TARGET_LANGUAGE__`, `__SUMMARY__`, `__PAIN_POINTS__`, `__INSIGHTS__`, `__INNOVATIONS__` | `render(target_language, summary, pain_points, insights, innovations)` |
| TagTranslationPrompt | `__TARGET_LANGUAGE__`, `__TAGS__` | `render(target_language, tags)` |
| GroupTranslationPrompt | `__TARGET_LANGUAGE__`, `__GROUPS__` | `render(target_language, groups)` |

### LANGUAGE_NAMES Mapping

| Code | Display Name |
|------|-------------|
| zh-TW | Traditional Chinese (Taiwan) |
| zh-CN | Simplified Chinese |
| ja | Japanese |
| ko | Korean |
| es | Spanish |
| fr | French |
| de | German |

---

## State Transitions

### Translation Lifecycle (per analysis, per language)

```
Not translated → [LLM call] → Translated (success)
Not translated → [LLM call] → Failed (all providers exhausted / save error)
Not translated → [Dedup check] → Already translated (return existing)
```

No further state transitions — translations are immutable once created (only upsert on re-save with same content).
