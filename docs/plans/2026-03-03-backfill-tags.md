# Backfill Tags Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create `scripts/backfill_tags.py` — a standalone script that re-analyzes articles with Gemini and populates the normalized `tags` + `article_tags` tables for articles that have an `analyses` row but no `article_tags` entries.

**Architecture:** Four pure helper functions (`find_articles_needing_backfill`, `upsert_tags_for_article`, `update_analysis`, `run_backfill`) wired together in a `main()` entry point. Each function takes its dependencies (session, provider) as arguments so they can be unit-tested with mocks without touching the DB or calling the LLM.

**Tech Stack:** Python 3, SQLAlchemy (raw `text()`), `src.analyzers.gemini.GeminiProvider`, `argparse`, `structlog`, `pytest` + `unittest.mock`

---

### Task 1: Make `scripts/` importable

**Files:**
- Create: `scripts/__init__.py`

**Step 1: Create empty init file**

```bash
touch scripts/__init__.py
```

**Step 2: Verify import works**

```bash
python -c "import scripts; print('ok')"
```
Expected: `ok`

**Step 3: Commit**

```bash
git add scripts/__init__.py
git commit -m "🔧 [FEAT] Make scripts/ a Python package"
```

---

### Task 2: DB query helper

**Files:**
- Create: `scripts/backfill_tags.py` (scaffold + first function)
- Create: `tests/unit/test_backfill_tags.py`

**Step 1: Write the failing test**

Create `tests/unit/test_backfill_tags.py`:

```python
import pytest
from unittest.mock import MagicMock


def test_find_articles_returns_rows():
    """find_articles_needing_backfill returns all rows from session"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        MagicMock(id="art-1", title="T1", content="C1", analysis_id="an-1"),
    ]

    rows = find_articles_needing_backfill(session)

    assert len(rows) == 1
    session.execute.assert_called_once()


def test_find_articles_passes_limit():
    """find_articles_needing_backfill passes limit to query when given"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    find_articles_needing_backfill(session, limit=5)

    call_args = session.execute.call_args
    # limit value must appear in the params dict
    assert call_args[0][1] == {"limit": 5}


def test_find_articles_no_limit_omits_param():
    """find_articles_needing_backfill omits params when no limit"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    find_articles_needing_backfill(session, limit=None)

    call_args = session.execute.call_args
    # called with just the text object, no params dict
    assert len(call_args[0]) == 1
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_backfill_tags.py -v
```
Expected: `ImportError` — `cannot import name 'find_articles_needing_backfill'`

**Step 3: Write scaffold + implementation**

Create `scripts/backfill_tags.py`:

```python
#!/usr/bin/env python3
"""
Backfill normalized tags for articles that have analyses but no article_tags entries.

Usage:
    DATABASE_URL=... LLM_API_KEY=... python scripts/backfill_tags.py [--dry-run] [--limit N]
"""
import argparse
import os
import sys
import uuid as uuid_module

from sqlalchemy import text

# Ensure project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzers.gemini import GeminiProvider
from src.database import get_session
from src.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "prompts", "analysis.txt",
)

_SQL_NEEDS_BACKFILL = """
    SELECT ar.id, ar.title, ar.content, an.id AS analysis_id
    FROM articles ar
    JOIN analyses an ON an.article_id = ar.id
    LEFT JOIN article_tags at ON at.article_id = ar.id
    WHERE at.article_id IS NULL
    ORDER BY an.analyzed_at
"""


def find_articles_needing_backfill(session, limit=None):
    """Return rows for articles with an analyses row but no article_tags entries."""
    if limit is not None:
        return session.execute(
            text(_SQL_NEEDS_BACKFILL + " LIMIT :limit"), {"limit": limit}
        ).fetchall()
    return session.execute(text(_SQL_NEEDS_BACKFILL)).fetchall()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_backfill_tags.py -v
```
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add scripts/backfill_tags.py tests/unit/test_backfill_tags.py
git commit -m "🏷️ [FEAT] Add find_articles_needing_backfill with tests"
```

---

### Task 3: Tag upsert helper

**Files:**
- Modify: `scripts/backfill_tags.py` (add `upsert_tags_for_article`)
- Modify: `tests/unit/test_backfill_tags.py` (add tests)

**Step 1: Write the failing tests**

Append to `tests/unit/test_backfill_tags.py`:

```python
def test_upsert_tags_dry_run_does_not_call_session(capsys):
    """dry_run=True must not execute any DB statements"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    tag_groups = [{"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]}]

    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=True)

    session.execute.assert_not_called()
    out = capsys.readouterr().out
    assert "virtual replica" in out
    assert "real-time sync" in out


def test_upsert_tags_executes_three_statements_per_tag():
    """Each tag triggers INSERT tag, SELECT tag id, INSERT article_tag"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    # SELECT returns a row with an id
    session.execute.return_value.first.return_value = ("tag-id-123",)

    tag_groups = [{"group": "digital_twin", "tags": ["virtual replica"]}]
    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=False)

    assert session.execute.call_count == 3  # INSERT tag, SELECT id, INSERT article_tag


def test_upsert_tags_skips_empty_tag_names():
    """Tags with empty/None name must be silently skipped"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    session.execute.return_value.first.return_value = ("tag-id",)

    tag_groups = [{"group": "digital_twin", "tags": ["", None, "valid-tag"]}]
    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=False)

    # Only 1 valid tag → 3 execute calls
    assert session.execute.call_count == 3
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_backfill_tags.py::test_upsert_tags_dry_run_does_not_call_session -v
```
Expected: `ImportError` — `cannot import name 'upsert_tags_for_article'`

**Step 3: Implement**

Append to `scripts/backfill_tags.py`:

```python
def upsert_tags_for_article(session, article_id, tag_groups, dry_run=False):
    """Insert tag rows and article_tags entries for a single article."""
    for group in tag_groups:
        group_name = group.get("group")
        for tag_name in group.get("tags", []):
            if not tag_name or not group_name:
                continue
            if dry_run:
                print(
                    f"  [DRY RUN] tag {tag_name!r} in group {group_name!r}"
                    f" -> article {article_id}"
                )
                continue
            session.execute(
                text("""
                    INSERT INTO tags (id, name, tag_group_name)
                    VALUES (:id, :name, :group_name)
                    ON CONFLICT (name, tag_group_name) DO NOTHING
                """),
                {"id": str(uuid_module.uuid4()), "name": tag_name, "group_name": group_name},
            )
            row = session.execute(
                text("SELECT id FROM tags WHERE name = :name AND tag_group_name = :group_name"),
                {"name": tag_name, "group_name": group_name},
            ).first()
            session.execute(
                text("""
                    INSERT INTO article_tags (article_id, tag_id)
                    VALUES (:article_id, :tag_id)
                    ON CONFLICT DO NOTHING
                """),
                {"article_id": str(article_id), "tag_id": str(row[0])},
            )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_backfill_tags.py -v
```
Expected: all previous + 3 new PASSED

**Step 5: Commit**

```bash
git add scripts/backfill_tags.py tests/unit/test_backfill_tags.py
git commit -m "🏷️ [FEAT] Add upsert_tags_for_article with tests"
```

---

### Task 4: Analysis update helper

**Files:**
- Modify: `scripts/backfill_tags.py` (add `update_analysis`)
- Modify: `tests/unit/test_backfill_tags.py` (add tests)

**Step 1: Write the failing tests**

Append to `tests/unit/test_backfill_tags.py`:

```python
def _make_result():
    from src.analyzers.llm_provider import AnalysisResult
    return AnalysisResult(
        tag_groups=[],
        pain_points="pain",
        insights="insight",
        innovations="innovation",
        input_tokens=10,
        output_tokens=5,
    )


def test_update_analysis_dry_run_skips_db(capsys):
    """dry_run=True must not call session.execute"""
    from scripts.backfill_tags import update_analysis

    session = MagicMock()
    update_analysis(session, "an-id", _make_result(), model_used="gemini-2.0-flash", dry_run=True)

    session.execute.assert_not_called()
    out = capsys.readouterr().out
    assert "an-id" in out


def test_update_analysis_executes_update():
    """update_analysis should call session.execute exactly once"""
    from scripts.backfill_tags import update_analysis

    session = MagicMock()
    update_analysis(session, "an-id", _make_result(), model_used="gemini-2.0-flash", dry_run=False)

    session.execute.assert_called_once()
    # Verify the params dict includes expected keys
    params = session.execute.call_args[0][1]
    assert params["pain_points"] == "pain"
    assert params["insights"] == "insight"
    assert params["innovations"] == "innovation"
    assert params["model_used"] == "gemini-2.0-flash"
    assert params["input_tokens"] == 10
    assert params["output_tokens"] == 5
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_backfill_tags.py::test_update_analysis_dry_run_skips_db -v
```
Expected: `ImportError` — `cannot import name 'update_analysis'`

**Step 3: Implement**

Append to `scripts/backfill_tags.py`:

```python
def update_analysis(session, analysis_id, result, model_used, dry_run=False):
    """Overwrite pain_points/insights/innovations/token counts on the analyses row."""
    if dry_run:
        print(
            f"  [DRY RUN] Would update analysis {analysis_id}:"
            f" pain_points={result.pain_points[:50]!r}..."
        )
        return
    session.execute(
        text("""
            UPDATE analyses
            SET pain_points   = :pain_points,
                insights      = :insights,
                innovations   = :innovations,
                model_used    = :model_used,
                input_tokens  = :input_tokens,
                output_tokens = :output_tokens
            WHERE id = :id
        """),
        {
            "id":            str(analysis_id),
            "pain_points":   result.pain_points,
            "insights":      result.insights,
            "innovations":   result.innovations,
            "model_used":    model_used,
            "input_tokens":  result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_backfill_tags.py -v
```
Expected: all PASSED

**Step 5: Commit**

```bash
git add scripts/backfill_tags.py tests/unit/test_backfill_tags.py
git commit -m "🏷️ [FEAT] Add update_analysis with tests"
```

---

### Task 5: `run_backfill` loop

**Files:**
- Modify: `scripts/backfill_tags.py` (add `run_backfill`)
- Modify: `tests/unit/test_backfill_tags.py` (add tests)

**Step 1: Write the failing tests**

Append to `tests/unit/test_backfill_tags.py`:

```python
def _make_provider(result):
    """Return a mock GeminiProvider that returns `result` from analyze()."""
    provider = MagicMock()
    provider.model_name = "gemini-2.0-flash"
    provider.analyze.return_value = result
    return provider


def test_run_backfill_processes_successful_articles():
    """Processed count increments when LLM succeeds"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [MagicMock(id="art-1", title="T", content="C", analysis_id="an-1")]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        stats = run_backfill(session, _make_provider(_make_result()), "prompt", dry_run=True)

    assert stats["processed"] == 1
    assert stats["skipped"] == 0


def test_run_backfill_skips_on_llm_failure():
    """Skipped count increments when LLM returns None"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [MagicMock(id="art-1", title="T", content="C", analysis_id="an-1")]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        stats = run_backfill(session, _make_provider(None), "prompt", dry_run=False)

    assert stats["processed"] == 0
    assert stats["skipped"] == 1


def test_run_backfill_commits_per_article_when_not_dry_run():
    """session.commit() is called once per successfully processed article"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [
        MagicMock(id="art-1", title="T1", content="C1", analysis_id="an-1"),
        MagicMock(id="art-2", title="T2", content="C2", analysis_id="an-2"),
    ]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        run_backfill(session, _make_provider(_make_result()), "prompt", dry_run=False)

    assert session.commit.call_count == 2


def test_run_backfill_dry_run_does_not_commit():
    """session.commit() must not be called in dry_run mode"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [MagicMock(id="art-1", title="T", content="C", analysis_id="an-1")]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        run_backfill(session, _make_provider(_make_result()), "prompt", dry_run=True)

    session.commit.assert_not_called()
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_backfill_tags.py::test_run_backfill_processes_successful_articles -v
```
Expected: `ImportError` — `cannot import name 'run_backfill'`

**Step 3: Implement**

Append to `scripts/backfill_tags.py`:

```python
def run_backfill(session, provider, prompt, dry_run=False, limit=None):
    """
    Main backfill loop.

    Returns dict: {"processed": int, "skipped": int}
    """
    rows = find_articles_needing_backfill(session, limit=limit)
    processed = 0
    skipped = 0

    for row in rows:
        article_id  = row.id
        analysis_id = row.analysis_id
        logger.info("backfill_start", title=row.title, article_id=str(article_id))

        result = provider.analyze(row.content, prompt)
        if result is None:
            logger.error("backfill_llm_failed", title=row.title, article_id=str(article_id))
            skipped += 1
            continue

        upsert_tags_for_article(session, article_id, result.tag_groups, dry_run=dry_run)
        update_analysis(session, analysis_id, result, model_used=provider.model_name, dry_run=dry_run)

        if not dry_run:
            session.commit()

        logger.info("backfill_done", title=row.title, article_id=str(article_id))
        processed += 1

    return {"processed": processed, "skipped": skipped}
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_backfill_tags.py -v
```
Expected: all PASSED

**Step 5: Commit**

```bash
git add scripts/backfill_tags.py tests/unit/test_backfill_tags.py
git commit -m "🔄 [FEAT] Add run_backfill loop with tests"
```

---

### Task 6: `main()` — argument parsing and wiring

**Files:**
- Modify: `scripts/backfill_tags.py` (add `main()`)
- Modify: `tests/unit/test_backfill_tags.py` (add env-var validation tests)

**Step 1: Write the failing tests**

Append to `tests/unit/test_backfill_tags.py`:

```python
def test_main_exits_without_llm_api_key(monkeypatch, capsys):
    """main() must exit(1) when LLM_API_KEY is missing"""
    from scripts.backfill_tags import main

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "LLM_API_KEY" in capsys.readouterr().err


def test_main_exits_without_database_url(monkeypatch, capsys):
    """main() must exit(1) when DATABASE_URL is missing"""
    from scripts.backfill_tags import main

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "DATABASE_URL" in capsys.readouterr().err
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_backfill_tags.py::test_main_exits_without_llm_api_key -v
```
Expected: `ImportError` — `cannot import name 'main'`

**Step 3: Implement**

Append to `scripts/backfill_tags.py`:

```python
def main():
    parser = argparse.ArgumentParser(
        description="Backfill normalized tags via Gemini re-analysis."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print planned changes without writing to the database.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of articles to process.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("ERROR: LLM_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("DATABASE_URL"):
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    with open(_PROMPT_PATH) as f:
        prompt = f.read()

    provider = GeminiProvider(api_key=api_key)
    session  = get_session()

    try:
        stats = run_backfill(
            session, provider, prompt,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    finally:
        session.close()

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(
        f"\n{prefix}Backfill complete: "
        f"{stats['processed']} processed, {stats['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
```

**Step 4: Run all tests**

```bash
pytest tests/unit/test_backfill_tags.py -v
```
Expected: all PASSED

**Step 5: Commit**

```bash
git add scripts/backfill_tags.py tests/unit/test_backfill_tags.py
git commit -m "🚀 [FEAT] Add main() with env validation, wire complete backfill script"
```

---

### Task 7: Smoke-test the full test suite

**Step 1: Run the full unit test suite**

```bash
pytest tests/unit/ -v
```
Expected: all existing tests PASS + new backfill tests PASS

**Step 2: Verify the script help output**

```bash
python scripts/backfill_tags.py --help
```
Expected output includes `--dry-run` and `--limit` in the help text.

**Step 3: Commit if any fixes were needed**

```bash
git add -p
git commit -m "🔧 [FIX] Fix any issues found during smoke test"
```
(Skip if no fixes needed.)
