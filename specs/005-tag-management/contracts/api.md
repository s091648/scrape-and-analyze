# API Contracts: Tag Management (005)

**Date**: 2026-05-29
**Type**: Brownfield — documents existing REST API contracts

## Base URL

All endpoints proxied through Next.js at `/api/proxy` → backend at `http://backend:8000`

## Tag Group Endpoints

### GET /tag-groups

List tag groups for a topic, optionally including similar groups.

**Auth**: Public

**Query Params**:
| Param | Type | Required | Description |
|--------|------|----------|-------------|
| topic_id | UUID | Yes | Filter by topic |
| include_similar | bool | No | Include groups with cosine similarity >= 0.90 |

**Response**: Array of tag group objects, each containing `id`, `name`, `display_name`, `description`, `color_hex`, `sort_order`, `tags[]`, and optionally `similar_groups[]`. Includes a virtual "Ungrouped" group (id=null) containing ungrouped tags.

---

### POST /tag-groups

Create a new tag group.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Auto-normalized to slug format |
| display_name | string | Yes | Auto-normalized to title case |
| description | string | No | |
| color_hex | string | No | 7-char hex color |
| topic_id | UUID | Yes | |

**Response**: Created tag group object with auto-generated embedding.

**Errors**: 409 if name conflicts with existing group in same topic.

---

### GET /tag-groups/{group_id}

Get a single tag group with its tags.

**Auth**: Public

**Response**: Tag group object with `tags[]` array.

---

### PUT /tag-groups/{group_id}

Update a tag group.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | No | Auto-normalized to slug |
| display_name | string | No | Auto-normalized to title case |
| description | string | No | |
| color_hex | string | No | |

**Errors**: 409 if name conflicts with another group in same topic.

---

### DELETE /tag-groups/{group_id}

Delete a tag group. Tags become ungrouped (not deleted).

**Auth**: Admin

**Response**: 204 No Content

---

### POST /tag-groups/merge

Merge two tag groups.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_group_id | UUID | Yes | Group to merge from (deleted) |
| target_group_id | UUID | No | Group to merge into (kept). Omit to create new. |
| result_name | string | No | Name for new group (if target_group_id omitted). Auto-slugified. |
| result_display_name | string | No | Display name for new group. Auto-title-cased. |
| result_color | string | No | Color for new group. |

**Behavior**: Tags with the same name in both groups are deduplicated (article_tags transferred to surviving tag, duplicate deleted).

**Response**: Merged group object.

---

### POST /tag-groups/reorder

Batch update sort_order for tag groups.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| groups | Array<{id: UUID, sort_order: int}> | Yes | |

**Response**: 200 OK

---

## Tag Endpoints

### PUT /tags/{tag_id}

Rename a tag or move it to a different group.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | No | New name (embedding regenerated) |
| tag_group_id | UUID or null | No | New group (null = ungrouped) |

**Response**: Updated tag object.

---

### DELETE /tags/{tag_id}

Delete a tag and all its article_tags associations.

**Auth**: Admin

**Response**: 204 No Content

---

### POST /tags/batch-move

Move multiple tags to a different group.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tag_ids | Array<UUID> | Yes | Tags to move |
| tag_group_id | UUID or null | Yes | Target group (null = ungrouped) |

**Response**: 200 OK

---

## Normalization Suggestion Endpoints

### GET /tag-normalization-suggestions

List pending normalization suggestions.

**Auth**: Admin

**Response**: Array of suggestion objects with `id`, `new_tag` (name, group), `existing_tag` (name, group), `similarity_score`, `article_id`.

---

### POST /tag-normalization-suggestions/{id}/approve

Approve (merge) a suggestion. Re-points article_tags from new_tag to existing_tag, deletes new_tag.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| resolved_by | UUID | Yes | Admin user ID |

**Response**: 200 OK

---

### POST /tag-normalization-suggestions/{id}/reject

Reject a suggestion. Both tags remain.

**Auth**: Admin

**Body**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| resolved_by | UUID | Yes | Admin user ID |

**Response**: 200 OK
