# Feature Specification: Tag Management

**Feature Branch**: `005-tag-management`

**Created**: 2026-05-29

**Status**: Draft

**Input**: Brownfield spec — describes existing behavior of the tag management capability as it currently stands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tag normalization after analysis (Priority: P1)

After an article is analyzed by the LLM, the system automatically normalizes the generated tags. For each tag, the system generates a semantic embedding and searches for similar existing tags within the same tag group and topic. Tags that closely match an existing tag (similarity >= 0.95) are auto-merged — the existing tag is linked to the article instead of creating a duplicate. Tags with moderate similarity (0.90–0.95) are created but also produce a pending normalization suggestion for admin review. Tags with no similar match are created as new.

**Why this priority**: Tag normalization is the core value — it prevents tag proliferation and keeps the tag vocabulary coherent without requiring manual deduplication after every analysis.

**Independent Test**: Run the full pipeline on a new article. After analysis succeeds, verify that: (a) no near-duplicate tags were created (auto-merged instead), (b) pending suggestions exist for borderline-similar tags, and (c) genuinely novel tags were created.

**Acceptance Scenarios**:

1. **Given** an article has been analyzed and the LLM returned tag groups with tag names, **When** tag normalization runs, **Then** the system generates embeddings for all new tag names in a single batch, then checks each against existing tags in the same group and topic.
2. **Given** a new tag has cosine similarity >= 0.95 to an existing tag in the same group and topic, **When** normalization processes that tag, **Then** the existing tag is linked to the article (via article_tags), the new tag is NOT created, and a `tag_auto_merged` log entry is emitted.
3. **Given** a new tag has cosine similarity between 0.90 and 0.95 to an existing tag in the same group and topic, **When** normalization processes that tag, **Then** the new tag is created and linked to the article, a `TagNormalizationSuggestion` record is created (status: pending), and a `tag_suggestion_created` log entry is emitted.
4. **Given** a new tag has no similar tag above the suggest threshold (0.90), **When** normalization processes that tag, **Then** the new tag is created and linked to the article, and a `tag_created` log entry is emitted.
5. **Given** normalization encounters an exception mid-processing, **When** the error occurs, **Then** no commit is made (all changes are rolled back) and the result carries `success=False` with exception details.

---

### User Story 2 - Tag group definition management (Priority: P1)

An administrator can create, update, reorder, merge, and delete tag group definitions. Each group belongs to a specific topic and has a name (snake_case slug), display name, optional description, optional color, and sort order. The system auto-normalizes group names to slug format and display names to title case on creation and update. Groups can be merged, which deduplicates tags by name and consolidates article associations.

**Why this priority**: Group management is the structural backbone of the tag vocabulary. Without it, there is no way to organize or govern the tag taxonomy.

**Independent Test**: Create a tag group via the API, verify the name is slug-normalized and display_name is title-cased. Update it. Merge it with another group. Delete it and confirm tags become ungrouped.

**Acceptance Scenarios**:

1. **Given** an admin creates a tag group with name `"AI & ML"` and display name `"ai and ml"`, **When** the request is processed, **Then** the group is stored with name `"ai_ml"` and display_name `"Ai And Ml"`, and an embedding is auto-generated for the group name.
2. **Given** an admin creates a tag group with a name that already exists in the same topic, **When** the request is processed, **Then** the system returns a 409 Conflict error.
3. **Given** an admin merges two tag groups, **When** tags with the same name exist in both groups, **Then** the duplicate tag is removed, its article associations are transferred to the surviving tag, and the merged group contains all unique tags.
4. **Given** an admin deletes a tag group, **When** the deletion completes, **Then** the group is removed and all its tags become ungrouped (tag_group_id set to null), but the tags themselves and their article associations are preserved.
5. **Given** an admin reorders tag groups, **When** the batch reorder request is processed, **Then** the sort_order of each specified group is updated to the requested position.
6. **Given** an admin updates a tag group with a name that conflicts with another group in the same topic, **When** the request is processed, **Then** the system returns a 409 Conflict error.

---

### User Story 3 - Tag CRUD and grouping (Priority: P2)

An administrator can rename tags, delete tags, and move tags between groups (individually or in batch). Moving a tag changes its group association. Deleting a tag removes it and its article associations.

**Why this priority**: Individual tag management is essential for correcting misnamed tags, removing irrelevant ones, and reorganizing the tag taxonomy.

**Independent Test**: Rename a tag via the API and verify the new name. Move a tag to a different group. Delete a tag and confirm its article_tags rows are removed.

**Acceptance Scenarios**:

1. **Given** an admin renames a tag, **When** the update request is processed, **Then** the tag name is updated and the tag's embedding is regenerated to reflect the new name.
2. **Given** an admin moves a tag to a different group, **When** the update request is processed, **Then** the tag's group association is changed and the tag appears under the new group.
3. **Given** an admin moves a tag with no group (ungrouped), **When** the update request sets the group to null, **Then** the tag becomes ungrouped.
4. **Given** an admin deletes a tag, **When** the deletion completes, **Then** the tag and all its article_tags rows are removed.
5. **Given** an admin batch-moves multiple tags to a different group, **When** the batch request is processed, **Then** all specified tags are moved to the target group in a single operation.

---

### User Story 4 - Normalization suggestion review (Priority: P2)

An administrator can view, approve, or reject pending tag normalization suggestions. Approving a suggestion merges the new tag into the existing tag (transferring article associations and deleting the new tag). Rejecting a suggestion marks it as resolved without merging. Bulk "merge all" is supported.

**Why this priority**: Suggestion review closes the loop on the semi-automated normalization flow. Without it, pending suggestions accumulate and the tag vocabulary drifts.

**Independent Test**: Create two similar tags and a suggestion. Approve the suggestion and verify the new tag is deleted and its articles are re-linked to the existing tag. Reject another suggestion and verify it is marked resolved.

**Acceptance Scenarios**:

1. **Given** a pending normalization suggestion exists, **When** an admin approves it, **Then** all article_tags rows referencing the new tag are re-pointed to the existing tag, the new tag and its article_tags are deleted, and the suggestion is removed.
2. **Given** a pending normalization suggestion exists, **When** an admin rejects it, **Then** the suggestion status is set to "rejected", `resolved_at` and `resolved_by` are recorded, and both tags remain as-is.
3. **Given** multiple pending suggestions exist, **When** an admin clicks "Merge All", **Then** all pending suggestions are approved in bulk.
4. **Given** an admin views the suggestions list, **When** the page loads, **Then** only pending suggestions are displayed with their tag names, group names, and similarity scores.

---

### User Story 5 - Topic tag mode (Priority: P2)

Each topic has a tag mode that controls how the LLM generates tags during analysis. In unsupervised mode, the LLM freely creates tag group keys and the system auto-creates missing groups. In semi-supervised mode, the LLM sees existing groups as hints and may create new ones. In supervised mode, the LLM is constrained to only use predefined groups. The tag mode can be changed by an admin at any time.

**Why this priority**: Tag mode governs the autonomy of tag creation. It is a governance knob that determines whether the tag vocabulary grows freely or is strictly controlled.

**Independent Test**: Set a topic to supervised mode. Analyze an article. Verify the LLM only uses predefined group keys and no new groups are created. Switch to unsupervised and verify new groups can be created.

**Acceptance Scenarios**:

1. **Given** a topic is in unsupervised mode, **When** article analysis runs, **Then** the LLM prompt allows free generation of group keys, and any new group keys returned by the LLM are auto-created as tag group definitions (with display name derived from the group key).
2. **Given** a topic is in semi-supervised mode, **When** article analysis runs, **Then** the LLM prompt includes existing group keys as hints, the LLM may also generate new keys, and any new group keys are auto-created.
3. **Given** a topic is in supervised mode, **When** article analysis runs, **Then** the LLM prompt lists only the predefined group keys as allowed values, no new groups are auto-created, and tags must belong to existing groups.

---

### User Story 6 - Frontend tag management interface (Priority: P3)

Administrators can manage tags and groups through a visual interface with drag-and-drop tag movement between groups, group reordering, tag rename/delete, group merge, and a pending changes panel that stages moves before confirming. Unauthenticated users see a blurred preview of the tag structure (guest paywall).

**Why this priority**: The UI is the primary interaction surface for tag management, but the underlying API behaviors are the foundation that the UI exposes.

**Independent Test**: Log in as admin. Drag a tag from one group to another. Verify the pending changes panel shows the move. Confirm and verify the tag's group has changed. Attempt tag management as a guest and verify the paywall.

**Acceptance Scenarios**:

1. **Given** an admin drags a tag from one group to another, **When** the drag completes, **Then** the move is staged in a pending changes panel (not immediately persisted).
2. **Given** pending tag moves exist, **When** the admin confirms the changes, **Then** a batch-move API call is made with all pending moves, and the UI reflects the new group assignments.
3. **Given** pending tag moves exist, **When** the admin discards the changes, **Then** all staged moves are cleared and the UI reverts to the persisted state.
4. **Given** an admin selects multiple tags (Ctrl+Click) and drags them, **When** the drag completes, **Then** all selected tags are staged for the same group move.
5. **Given** an admin reorders groups by dragging group handles, **When** the reorder completes, **Then** the new sort order is persisted via the reorder API.
6. **Given** an unauthenticated user visits the tags page, **When** the page loads, **Then** fake group data is shown behind a blur overlay (guest paywall), and no real tag data is exposed.
7. **Given** an admin views the tags page, **When** similar groups exist (cosine similarity >= 0.90), **Then** SVG similarity lines are drawn between similar groups with hover tooltips showing the similarity score and a merge button.

---

### User Story 7 - Backfill and maintenance operations (Priority: P3)

Operators can run backfill scripts to retroactively tag articles that lack tags, generate embeddings for tags and groups that lack them, create missing tag group definitions for orphaned group names, and scan for tag normalization suggestions among existing tags.

**Why this priority**: Backfill operations are essential for data hygiene and catching up after schema changes or feature additions, but they are not part of the real-time flow.

**Independent Test**: Run each backfill command. Verify the expected data changes: articles gain tags, tags/groups gain embeddings, orphaned groups gain definitions, and suggestions are created for similar tag pairs.

**Acceptance Scenarios**:

1. **Given** articles have analyses but no article_tags entries, **When** the tag backfill script runs, **Then** those articles are re-analyzed via LLM, tags are created/upserted, and article_tags associations are created.
2. **Given** tags or tag groups have null embeddings, **When** the embedding backfill script runs, **Then** embeddings are generated via the embedding provider and persisted for all tags and groups with null embeddings.
3. **Given** tag group names exist in tags that have no corresponding tag_group_definitions row, **When** the group definition backfill script runs, **Then** missing tag_group_definitions rows are auto-created with display_name set to `"{name}_unsupervised"`.
4. **Given** tags with embeddings exist within the same group, **When** the suggestion backfill script runs, **Then** pairwise cosine similarity is computed, and `TagNormalizationSuggestion` records are created for pairs above the suggestion threshold, even for pairs above the auto-merge threshold (since admin review is preferred for existing data).

---

### Edge Cases

- What happens when a tag is moved to a group that already contains a tag with the same name? The partial unique index `(name, tag_group_id) WHERE tag_group_id IS NOT NULL` prevents this — the move would fail with a unique constraint violation.
- What happens when two ungrouped tags have the same name? They are allowed — the partial unique index does not cover NULL group IDs.
- What happens when a tag group is deleted that has pending normalization suggestions referencing its tags? The group deletion sets `tag_group_id` to null on its tags, but suggestions reference tag IDs (not group IDs), so suggestions remain valid but the tags become ungrouped.
- What happens when the embedding service is unavailable during tag normalization? Embedding generation fails, the use case returns `success=False`, and no tags are committed. The article remains without tags until the pipeline is retried.
- What happens when a group merge target already has tags with the same name as the source group? The duplicate tag is removed from the source, its article_tags are transferred to the surviving tag in the target, and the source tag is deleted.
- What happens when backfill re-analyzes an article that already has tags? The backfill script only targets articles with no article_tags entries, so already-tagged articles are skipped.
- What happens when the LLM returns a group key that doesn't match any predefined group in supervised mode? The analysis still proceeds, but tags with unrecognized group keys are not persisted (or may be assigned to a fallback group). The exact behavior depends on the prompt constraints.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically normalize tags after every successful article analysis by generating embeddings and checking for similar existing tags within the same group and topic.
- **FR-002**: System MUST auto-merge new tags into existing tags when cosine similarity >= 0.95 (auto_merge_threshold), linking the existing tag to the article instead of creating a duplicate.
- **FR-003**: System MUST create a pending normalization suggestion when cosine similarity is between 0.90 (suggest_threshold) and 0.95, creating the new tag but also recording the suggestion for admin review.
- **FR-004**: System MUST create a new tag without a suggestion when no similar tag is found above 0.90.
- **FR-005**: System MUST roll back all tag changes if normalization encounters an exception (no partial commits).
- **FR-006**: System MUST allow administrators to create tag group definitions with auto-normalized names (slug format) and display names (title case), scoped to a specific topic.
- **FR-007**: System MUST reject creation or update of a tag group when the normalized name conflicts with an existing group in the same topic (409 Conflict).
- **FR-008**: System MUST auto-generate an embedding for each new tag group definition name.
- **FR-009**: System MUST allow administrators to merge two tag groups, deduplicating tags by name and consolidating article associations into the surviving tag.
- **FR-010**: System MUST allow administrators to delete a tag group, which ungroups (sets group_id to null) all its tags without deleting the tags themselves.
- **FR-011**: System MUST allow administrators to reorder tag groups via batch sort_order updates.
- **FR-012**: System MUST allow administrators to rename tags, delete tags, and move tags between groups (individually or in batch).
- **FR-013**: System MUST regenerate a tag's embedding when the tag is renamed.
- **FR-014**: System MUST delete a tag and all its article_tags associations when an administrator deletes the tag.
- **FR-015**: System MUST allow administrators to view, approve, or reject pending tag normalization suggestions.
- **FR-016**: System MUST, on suggestion approval, re-point all article_tags from the new tag to the existing tag, delete the new tag, and remove the suggestion.
- **FR-017**: System MUST, on suggestion rejection, mark the suggestion as rejected with a resolved_at timestamp and resolved_by identifier, leaving both tags intact.
- **FR-018**: System MUST support three tag modes per topic: unsupervised (LLM freely generates groups, auto-created), semi_supervised (LLM sees existing groups as hints, may create new), and supervised (LLM constrained to predefined groups only).
- **FR-019**: System MUST auto-create tag group definitions for any new group keys returned by the LLM in unsupervised or semi_supervised mode, with display name derived from the group key.
- **FR-020**: System MUST NOT auto-create tag group definitions in supervised mode — all groups must be predefined.
- **FR-021**: System MUST enforce the partial unique constraint on tags: `(name, tag_group_id)` is unique where `tag_group_id IS NOT NULL`. Two ungrouped tags with the same name are allowed.
- **FR-022**: System MUST provide a guest paywall on the tags page: unauthenticated users see blurred fake data instead of real tag information.
- **FR-023**: System MUST allow administrators to batch-move multiple tags between groups in a single request.
- **FR-024**: System MUST provide backfill operations for: retroactive tagging of articles without tags, embedding generation for tags/groups missing embeddings, creation of missing tag group definitions, and pairwise similarity scanning for normalization suggestions.
- **FR-025**: System MUST use a suggestion threshold of 0.85 for backfill-initiated pairwise similarity scans, which is lower than the real-time threshold (0.90), to catch more borderline pairs for admin review.
- **FR-026**: System MUST not auto-merge tags during backfill suggestion scans even for pairs above the auto-merge threshold, preferring admin review for existing data.

### Key Entities

- **Tag**: A labeled concept attached to articles. Identified by (name, tag_group_id) when grouped, or just (name) when ungrouped. Has a semantic embedding for similarity comparison. Belongs to zero or one tag group. Many-to-many relationship with articles via article_tags.
- **Tag Group Definition**: A named category that organizes tags. Identified by (name, topic_id). Has a display name, optional description, optional color, sort order, and a semantic embedding. Belongs to one topic. When deleted, its tags become ungrouped but are not deleted.
- **Tag Normalization Suggestion**: A pending or resolved recommendation to merge a new tag into an existing similar tag. Contains the new tag ID, existing tag ID, similarity score, and article ID. Has status (pending/rejected) and resolution metadata.
- **Tag Mode**: A per-topic governance setting (unsupervised, semi_supervised, supervised) controlling LLM freedom in generating tag group keys during analysis.
- **Article Tags**: A junction associating articles with tags. Composite key of (article_id, tag_id). Cascade-deleted when either side is removed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No near-duplicate tags (cosine similarity >= 0.95 within the same group and topic) are created by the pipeline — they are auto-merged into existing tags.
- **SC-002**: All borderline-similar tags (cosine similarity 0.90–0.95) produce pending suggestions that administrators can review, keeping the tag vocabulary under control.
- **SC-003**: Tag group operations (create, update, merge, delete, reorder) complete without data loss — tag associations are preserved or consolidated as specified.
- **SC-004**: The tag vocabulary remains coherent within each topic regardless of tag mode, with supervised mode enforcing strict control and unsupervised mode allowing organic growth.
- **SC-005**: Backfill operations successfully retroactively apply the same normalization rules to historical data that the real-time pipeline applies to new data.

## Assumptions

- Embeddings are 768-dimensional vectors generated by the configured embedding provider. Switching embedding models would require regenerating all embeddings.
- The auto_merge_threshold (0.95) and suggest_threshold (0.90) are sensible defaults; the backfill script uses a lower threshold (0.85) to cast a wider net for admin review.
- Tag group names are always stored in snake_case slug format. The normalization from human input to slug is lossy (special characters are replaced with underscores).
- The guest paywall on the tags page is a display-only concern; the backend APIs remain publicly accessible where indicated.
- Backfill re-analysis of articles uses the same LLM analysis pipeline as the real-time flow, which may produce different tags than the original analysis if the LLM model has changed.
- The `ArxivKeyword` model/table is legacy and superseded by `ScraperKeyword`; it is not part of this capability's active behavior.
- Tag translations are handled by the translation capability (004) and are not re-specified here.
- Scraper keywords (`ScraperKeyword`) are part of the article-collection capability (001), not tag management.
