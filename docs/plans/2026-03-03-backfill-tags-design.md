# Backfill Tags Design

**Date:** 2026-03-03
**Status:** Approved

## Problem

Vintage data in the `analyses` table has tags stored as a flat `TEXT[]` column (e.g. `{"Digital Twin","Industry 4.0","Manufacturing"}`). Migrations 04 and 05 introduced:

- `tag_group_definitions` — 8 predefined topic groups with slugs, colors, display names
- `tags` — normalized tag rows with `(name, tag_group_name)` uniqueness
- `article_tags` — many-to-many junction between articles and tags
- Dropped `analyses.tags` and `analyses.tag_groups` columns

Articles migrated to the new schema before this backfill have an `analyses` row but zero `article_tags` entries.

## Goal

Re-analyze all such articles with Gemini LLM to populate:

1. `tags` and `article_tags` (new normalized structure)
2. Freshly overwrite `analyses.pain_points`, `analyses.insights`, `analyses.innovations`, `analyses.model_used`, `analyses.input_tokens`, `analyses.output_tokens`

## Script

**Location:** `scripts/backfill_tags.py`

**Run:**
```bash
DATABASE_URL=... LLM_API_KEY=... python scripts/backfill_tags.py [--dry-run] [--limit N]
```

## Algorithm

1. Open DB session via `src.database.get_session()`
2. Query articles needing backfill:
   ```sql
   SELECT ar.id, ar.title, ar.content, an.id AS analysis_id
   FROM articles ar
   JOIN analyses an ON an.article_id = ar.id
   LEFT JOIN article_tags at ON at.article_id = ar.id
   WHERE at.article_id IS NULL
   ```
3. Load `src/prompts/analysis.txt`
4. Instantiate `GeminiProvider(api_key=LLM_API_KEY)` (reads `LLM_API_KEY` env var)
5. For each article:
   - Call `provider.analyze(article.content, prompt_text)` → `AnalysisResult`
   - On LLM failure: log + skip, continue
   - For each `{group, tags}` in `result.tag_groups`:
     - `INSERT INTO tags (id, name, tag_group_name) ON CONFLICT DO NOTHING`
     - Resolve tag UUID via SELECT
     - `INSERT INTO article_tags (article_id, tag_id) ON CONFLICT DO NOTHING`
   - `UPDATE analyses SET pain_points=..., insights=..., innovations=..., model_used=..., input_tokens=..., output_tokens=... WHERE id=analysis_id`
6. In `--dry-run` mode: print planned writes, skip all DB mutations
7. Print final summary: processed N, skipped K

## Error Handling

- LLM failure for a single article → log error + skip, continue to next
- Missing `LLM_API_KEY` or `DATABASE_URL` → fail fast at startup with clear message
- Invalid LLM response (validation failure inside `GeminiProvider`) → treated as failure, skip

## Dependencies

No new dependencies. Uses:

- `src.database.get_session()`
- `src.analyzers.gemini.GeminiProvider`
- `src/prompts/analysis.txt`
- `structlog` (already in project)
- `argparse` (stdlib)
