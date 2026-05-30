# Data Model: Tag Management (005)

**Date**: 2026-05-29
**Type**: Brownfield — documents existing data model

## Entity Relationship Diagram

```
┌──────────────────┐     ┌──────────────────────┐
│     Topic        │     │  TagGroupDefinition   │
│──────────────────│     │──────────────────────│
│ id (UUID) PK     │◄──┐ │ id (UUID) PK          │
│ tag_mode (VARCHAR)│   │ │ name (VARCHAR 100)    │
└──────────────────┘    │ │ display_name (VARCHAR)│
                        │ │ description (TEXT)    │
                        │ │ color_hex (VARCHAR 7) │
                        │ │ sort_order (INT)      │
                        │ │ topic_id (UUID) FK    │──┐
                        │ │ embedding (VECTOR 768)│  │
                        │ └──────────────────────┘  │
                        │                            │
                        │  ┌──────────────────────┐ │
                        │  │  Tag                  │ │
                        │  │──────────────────────│ │
                        ├──│ tag_group_id (UUID) FK│─┘
                        │  │ id (UUID) PK          │
                        │  │ name (TEXT)           │
                        │  │ embedding (VECTOR 768)│
                        │  └──────────────────────┘
                        │            │
                        │            │ M:N via article_tags
                        │            ▼
                        │  ┌──────────────────────┐
                        │  │  Article              │
                        │  │  id (UUID) PK         │
                        │  └──────────────────────┘
                        │
                        │  ┌─────────────────────────────┐
                        │  │  TagNormalizationSuggestion  │
                        │  │─────────────────────────────│
                        │  │ id (UUID) PK                 │
                        └──│ existing_tag_id (UUID) FK    │
                           │ new_tag_id (UUID) FK         │
                           │ similarity_score (FLOAT)     │
                           │ article_id (UUID) FK         │
                           │ status (VARCHAR)             │
                           │ resolved_at (TIMESTAMP)       │
                           │ resolved_by (UUID)           │
                           └─────────────────────────────┘

┌──────────────────────────┐     ┌──────────────────────────────────┐
│ TagsTranslation          │     │ TagGroupDefinitionsTranslation   │
│──────────────────────────│     │──────────────────────────────────│
│ id (UUID) PK             │     │ id (UUID) PK                     │
│ tag_id (UUID) FK         │     │ tag_group_definition_id (UUID) FK│
│ language (VARCHAR 10)    │     │ language (VARCHAR 10)            │
│ name (TEXT)              │     │ display_name (VARCHAR 200)       │
│ created_at (TIMESTAMP)   │     │ description (TEXT)               │
└──────────────────────────┘     │ created_at (TIMESTAMP)           │
                                 └──────────────────────────────────┘
```

## Entities

### Tag

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, auto-generated | |
| name | TEXT | NOT NULL | Tag label |
| tag_group_id | UUID | FK → tag_group_definitions.id, ON DELETE SET NULL, nullable | Ungrouped when null |
| embedding | VECTOR(768) | nullable | For cosine similarity |

**Unique constraint**: `uq_tag_name_group` — partial index on `(name, tag_group_id) WHERE tag_group_id IS NOT NULL`

**Indexes**: `idx_tags_group` on `tag_group_id`, `idx_tags_embedding` (HNSW with `vector_cosine_ops`)

### TagGroupDefinition

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, auto-generated | |
| name | VARCHAR(100) | NOT NULL | Snake_case slug |
| display_name | VARCHAR(100) | NOT NULL | Title case |
| description | TEXT | nullable | |
| color_hex | VARCHAR(7) | nullable | e.g. "#6366f1" |
| sort_order | INTEGER | nullable | For reordering |
| topic_id | UUID | FK → topics.id, NOT NULL | Topic-scoped |
| embedding | VECTOR(768) | nullable | For group similarity |

**Unique constraint**: `(name, topic_id)` — group names unique per topic

**Indexes**: `idx_tag_group_defs_embedding` (HNSW with `vector_cosine_ops`)

### TagNormalizationSuggestion

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK, auto-generated | |
| existing_tag_id | UUID | FK → tags.id | The pre-existing similar tag |
| new_tag_id | UUID | FK → tags.id | The newly created tag |
| similarity_score | FLOAT | | Cosine similarity at time of creation |
| article_id | UUID | FK → articles.id | The article that triggered the new tag |
| status | VARCHAR | Default 'pending' | 'pending' or 'rejected' |
| resolved_at | TIMESTAMP | nullable | Set on rejection |
| resolved_by | UUID | nullable | User ID of resolver |

### Article Tags (junction)

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| article_id | UUID | FK → articles.id, CASCADE DELETE | Composite PK |
| tag_id | UUID | FK → tags.id, CASCADE DELETE | Composite PK |

### TagsTranslation

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| tag_id | UUID | FK → tags.id | |
| language | VARCHAR(10) | | e.g. "zh-TW" |
| name | TEXT | NOT NULL | Translated tag name |
| created_at | TIMESTAMP(tz) | server_default=now() | |

**Unique constraint**: `(tag_id, language)`

### TagGroupDefinitionsTranslation

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| id | UUID | PK | |
| tag_group_definition_id | UUID | FK → tag_group_definitions.id | |
| language | VARCHAR(10) | | |
| display_name | VARCHAR(200) | NOT NULL | |
| description | TEXT | nullable | |
| created_at | TIMESTAMP(tz) | server_default=now() | |

**Unique constraint**: `(tag_group_definition_id, language)`

## State Transitions

### TagNormalizationSuggestion

```
        (created)
           │
           ▼
        ┌────────┐
        │ pending │
        └───┬────┘
        ┌───┴────┐
        ▼        ▼
   ┌─────────┐  ┌──────────┐
   │ approved│  │ rejected │
   │(deleted)│  │          │
   └─────────┘  └──────────┘
```

- **approved**: Suggestion is deleted; article_tags re-pointed from new_tag to existing_tag; new_tag deleted
- **rejected**: `status` set to "rejected", `resolved_at` and `resolved_by` recorded; both tags remain

### TagMode (per Topic)

```
unsupervised ◄──► semi_supervised ◄──► supervised
```

- Admin can switch between any mode at any time
- Mode change does not retroactively alter existing tags
- Mode affects only future LLM analysis prompts and group auto-creation
