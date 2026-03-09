# Design: Knowledge Graph Redesign + Frequency-Based Scraper Scheduling

**Date:** 2026-03-10
**Status:** Approved

---

## Overview

Three coordinated changes:
1. Knowledge graph visual overhaul — tag/article node interaction
2. ScraperSetting model: frequency as hours + `last_scraped_at`
3. `main.py` scheduling: DB-driven frequency-based dispatch

---

## Section 1: Knowledge Graph Visual Redesign

### Group Node (collapsed)
- `articleCount` badge: font size `bold 14px` (up from `bold 8px`)
- Radius: unchanged (12)

### Group Node (expanded) — three-layer structure: group → tags → articles
When a group node is clicked, in addition to the existing `groupData` fetch, dynamically inject overlay nodes and edges into graphData:
- **Tag nodes**: one per unique tag in the group (`id: "tag::{groupName}::{tagName}"`, type `'tag'`, same color as group)
- **Edges added**: `group → tag` (one per tag) + `tag → article` (for each article that has the tag)
- **On collapse**: remove all overlay nodes and edges

### Article Nodes
- Radius reduced from 8 → 4
- No title label rendered on canvas
- `onNodeHover` and `onNodeClick` both trigger the right panel article view

### Right Panel State Machine
| State | Content |
|---|---|
| Nothing selected | "Click a group node to explore" |
| Group expanded, no article hovered/clicked | Group header + aggregate tag badges (existing behavior) |
| Article hovered or clicked | Title + Pain Points + Insights + "View Full" button |

### "View Full" Dialog
- Reuses the `Dialog` pattern from `ArticleCard`
- Calls `GET /articles/{id}` for full detail (tags, pain_points, insights, innovations, model_used)

---

## Section 2: ScraperSetting Model + Migrations

### Model Changes (`backend/models/scraper_setting.py`)
- `frequency`: `String(20)` → `Integer` (unit: hours)
- Add `last_scraped_at`: nullable `DateTime(timezone=True)`, default `None`

### Migration 07 — alter scraper_settings
```
UP:
  ADD COLUMN last_scraped_at TIMESTAMPTZ NULL
  ADD COLUMN frequency_hours INTEGER
  UPDATE: 'daily' → 24, 'weekly' → 168
  DROP COLUMN frequency
  RENAME frequency_hours → frequency

DOWN:
  ADD COLUMN frequency_str VARCHAR(20)
  UPDATE: 24 → 'daily', 168 → 'weekly'
  DROP COLUMN frequency
  RENAME frequency_str → frequency
  DROP COLUMN last_scraped_at
```

### Migration 08 — seed ArXiv scraper setting
```
INSERT INTO scraper_settings:
  source_type     = 'arxiv'
  name            = 'arxiv'
  url             = ''
  frequency       = 6
  is_active       = True
  selector_config = {"max_results": 30, "days_back": 1}
```

---

## Section 3: main.py Scheduling Redesign

### Removed
- `parse_args()` with `daily` / `weekly` / `remediate` choices
- `run_daily_scrape()` and `run_weekly_scrape()`

### New: `get_sources_due()` in `config.py`
Query all active sources whose last scrape time has exceeded their frequency interval:
```sql
SELECT * FROM scraper_settings
WHERE is_active = TRUE
  AND (
    last_scraped_at IS NULL
    OR NOW() - last_scraped_at > frequency * INTERVAL '1 hour'
  )
```

### New `main()` flow
```
1. init_db()
2. sources_due = get_sources_due(session)
3. for each source:
     dispatch scraper by source_type:
       'rss'   → RssScraper(url=source.url, source=source.name)
       'blog'  → BlogScraper(base_url=source.url, source=source.name,
                              selectors=source.selector_config)
       'arxiv' → ArxivScraper(
                   max_results=selector_config.get('max_results', 30),
                   days_back=selector_config.get('days_back', 1)
                 )
     articles = scraper.scrape()
     for each article: process_article_safe(article, analyzer, prompt, correlation_id)
     session.execute(UPDATE scraper_settings SET last_scraped_at = NOW() WHERE id = source.id)
     session.commit()
```

### Preserved
- `run_remediate()` — invokable standalone or via direct call

### `scrape.py` Updates
- `--source` choices: `['rss', 'blog', 'arxiv']` (aligned with source_type values)
- Fetches all active sources matching source_type from DB, bypasses frequency check
- ArXiv uses default `max_results`/`days_back` from `selector_config` if present

---

## Affected Files

| File | Change |
|---|---|
| `frontend/components/knowledge-graph.tsx` | Full visual + interaction redesign |
| `backend/models/scraper_setting.py` | frequency: int, add last_scraped_at |
| `alembic/versions/07_*.py` | Alter scraper_settings |
| `alembic/versions/08_*.py` | Seed arxiv scraper setting |
| `src/config.py` | Add get_sources_due(), update get_sources() |
| `src/main.py` | Frequency-based dispatch, remove parse_args |
| `scripts/scrape.py` | Update --source choices, use source_type |
