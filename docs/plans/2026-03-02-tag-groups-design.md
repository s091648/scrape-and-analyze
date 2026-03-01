# Tag Groups Feature — Design

**Date:** 2026-03-02

---

## Goal

Replace the flat per-tag node graph with a structured tag-group graph, where the LLM classifies each article into predefined thematic groups (each with specific sub-tags). The knowledge graph becomes readable and meaningful: users see ~8 stable group nodes instead of dozens of noisy tag nodes. Clicking a group expands it visually and populates the right panel with the group's tags and linked articles.

---

## Architecture

### Layer summary

```
LLM prompt → tag_groups JSON
     ↓
src/main.py (pipeline) → flatten tags + store tag_groups JSONB
     ↓
PostgreSQL: tag_group_definitions (seed) + analyses.tag_groups
     ↓
FastAPI: /analyses/graph returns group nodes; /analyses/graph/group/{name}
     ↓
Next.js KnowledgeGraph: collapsed group nodes → expand on click (canvas)
```

---

## Tag Group Taxonomy (predefined, 8 groups)

| name (key)                  | display_name                  | color_hex | Description |
|-----------------------------|-------------------------------|-----------|-------------|
| `digital_twin`              | Digital Twin                  | `#6366f1` | Virtual replicas, real-time synchronization, twin lifecycle, model fidelity, twin platforms |
| `ai_ml`                     | AI & Machine Learning         | `#f59e0b` | Predictive analytics, deep learning, anomaly detection, generative AI, inference |
| `iot_sensing`               | IoT & Sensing                 | `#10b981` | Sensors, edge computing, telemetry, MQTT/OPC-UA, real-time data collection |
| `simulation_modeling`       | Simulation & Modeling         | `#3b82f6` | Physics simulation, FEA, CFD, 3D modeling, game engines, digital mockups |
| `manufacturing_industry`    | Manufacturing & Industry 4.0  | `#ef4444` | Factories, industrial automation, supply chain, process optimization, robotics |
| `construction_smart_cities` | Construction & Smart Cities   | `#8b5cf6` | BIM, civil engineering, urban planning, smart infrastructure, building management |
| `software_devops`           | Software & DevOps             | `#06b6d4` | APIs, cloud architecture, cybersecurity, data pipelines, deployment, QA |
| `other_applications`        | Other Applications            | `#6b7280` | Healthcare, energy, transportation, aerospace, agriculture — any domain not above |

---

## Database Schema Changes

### New table: `tag_group_definitions`

```sql
CREATE TABLE tag_group_definitions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description  TEXT,
    color_hex    VARCHAR(7),
    sort_order   INTEGER
);
```

Seeded with the 8 rows above in the Alembic migration. Intentionally simple — ready for the future admin CRUD UI without further schema changes.

### Modified table: `analyses`

Add one column:

```sql
ALTER TABLE analyses ADD COLUMN tag_groups JSONB;
```

**Storage format:**
```json
[
  {"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]},
  {"group": "manufacturing_industry", "tags": ["factory automation", "process optimization"]}
]
```

`analyses.tags` (existing flat `ARRAY(Text)`) is kept and now stores the union of all tags across all groups. This preserves backward compatibility with all existing filter/search endpoints.

One Alembic migration handles: create `tag_group_definitions`, insert 8 seed rows, add `tag_groups` column to `analyses`.

---

## LLM Prompt Changes

`src/prompts/analysis.txt` is rewritten to request structured tag groups. The prompt:

- Lists all 8 group keys with one-line descriptions so the LLM classifies accurately
- Instructs the LLM to assign 1–3 groups per article (only genuinely relevant ones)
- Instructs 2–4 specific sub-tags per assigned group
- Returns `tag_groups` instead of `tags` (plus unchanged `pain_points`, `insights`, `innovations`)

**Output format:**
```json
{
  "tag_groups": [
    {"group": "digital_twin", "tags": ["virtual replica", "model fidelity"]},
    {"group": "manufacturing_industry", "tags": ["factory automation"]}
  ],
  "pain_points": "...",
  "insights": "...",
  "innovations": "..."
}
```

---

## Scraper / Analysis Pipeline Changes

**`src/analyzers/llm_provider.py`**
- `AnalysisResult` dataclass: replace `tags: list[str]` with `tag_groups: list[dict]`; add `tags: list[str]` computed as flat union

**`src/analyzers/claude.py`** (and `gemini.py`)
- `_validate_response()`: validate `tag_groups` is a list of `{"group": str, "tags": list[str]}` objects
- `analyze()`: populate `AnalysisResult.tag_groups` from response; compute flat `tags`

**`src/main.py`**
- `analyze_article()`: set `analysis.tag_groups = result.tag_groups`, `analysis.tags = result.tags`

**`src/models/analysis.py`**
- Add `tag_groups = Column(JSONB)` field

---

## Backend API Changes

### `GET /analyses/graph`

Returns group nodes instead of tag nodes. Each group node aggregates tag data from all analyses in the time window.

```json
{
  "nodes": [
    {
      "id": "group:digital_twin",
      "type": "group",
      "label": "Digital Twin",
      "color": "#6366f1",
      "articleCount": 12
    },
    {
      "id": "article:uuid",
      "type": "article",
      "label": "Article title",
      "articleId": "uuid"
    }
  ],
  "edges": [
    {"source": "group:digital_twin", "target": "article:uuid"}
  ]
}
```

### `GET /analyses/graph/group/{group_name}`

Replaces `GET /analyses/graph/tag/{tag}`. Returns:

```json
[
  {
    "groupName": "digital_twin",
    "displayName": "Digital Twin",
    "tags": ["virtual replica", "real-time sync", "model fidelity"],
    "articleId": "uuid",
    "title": "...",
    "source": "...",
    "url": "...",
    "published_at": "...",
    "excerpt": "...",
    "pain_points": "...",
    "insights": "...",
    "innovations": "..."
  }
]
```

Old `/analyses/graph/tag/{tag}` endpoint is removed (no consumers outside the graph component).

Graph-level cache is invalidated by the same 5-minute TTL already in place.

---

## Frontend Changes

### `components/knowledge-graph.tsx`

**Node rendering (canvas):**

| State | Rendering |
|---|---|
| Group node (collapsed) | Filled circle, radius 12, color from `node.color`; label below |
| Group node (expanded) | Large dashed-outline circle (radius 50); inner tag nodes at radius 4 drawn in a radial layout around the group center; group label above |
| Article node | Filled circle, radius 8, `#10b981`; title label below (unchanged) |

**Interaction:**
- Click group node → fetch `/analyses/graph/group/{name}`, store `expandedGroup`, render right panel, switch group node to expanded canvas state
- Click any other node (article or different group) → collapse `expandedGroup`, clear right panel

**Right panel (unchanged 40% layout):**
- Group name + description
- Tags as `<Badge>` chips
- Article list: title, source, excerpt, pain_points, insights, innovations (same layout as current tag panel)

**API fetch hook:** replace `selectedTag` / `tagArticles` state with `selectedGroup` / `groupData` (same structure, different endpoint).

**Time-window selector:** unchanged (7 / 30 / 90 / 180 days).

---

## Out of Scope (this phase)

- Admin UI for managing tag group definitions (planned for later)
- Backfilling existing articles' `tag_groups` (existing rows keep `tag_groups = NULL`; graph treats them as having no group memberships)
- Per-tag drill-down inside an expanded group node (clicking an individual tag sub-node)
