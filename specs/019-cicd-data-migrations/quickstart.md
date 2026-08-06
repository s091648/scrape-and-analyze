# Quickstart: Authoring a New Data Migration

This is the practical guide the feature's SC-006 refers to: a developer should be able to answer "what do I need to write?" using only this file and one existing script as reference, in under 5 minutes.

## 1. Decide it belongs here at all

Use `scripts/data/versions/` only for a standalone data fix that is **not** caused by (and not bundled with) a schema change:
- Bug-fix data cleanup (e.g. historical rows written by a now-fixed parser bug).
- A backfill that calls an external API, is slow, or needs to be re-runnable/dry-run-able as an ops tool.

If your data change is directly caused by a schema change you're adding in the same PR (e.g. a new column that needs existing rows backfilled into it), put that logic inline in that Alembic migration's own `upgrade()`/`downgrade()` instead — see `alembic/versions/18_add_data_migrations_table.py` for an example of that pattern. Don't use this framework for that case.

## 2. Copy the shape of an existing script

Start from `scripts/data/versions/001_backfill_tag_group_definitions.py`. Every script needs:

```python
from sqlalchemy import text

name = "002_my_new_migration"                 # unique; convention: descriptive, prefix optional (not load-bearing)
description = "One sentence describing what this fixes"
requires_api = False                          # True only if up()/down() call an external network API
down_revision = "001_backfill_tag_group_definitions"   # the name of the migration this runs after
alembic_revision = None                       # set below if you have a schema dependency

def up(session) -> None:
    ...  # your data change; must be safe to retry (failed runs are never recorded)

def down(session) -> None:
    ...  # optional — manual reversal only, never auto-invoked
```

## 3. Set `down_revision`

Find the current tip of the chain: run `make data-migrate-list` (or read every script's `down_revision` and find the one no other script points to as *its* predecessor — the current tip has no successor yet). Set your new script's `down_revision` to that tip's `name`. If you're the very first script ever, use `down_revision = None` — but today that's already claimed by `001_backfill_tag_group_definitions`, so in practice every new script sets this.

## 4. Set `alembic_revision` — only if you actually depend on specific schema

If your migration reads/writes a column or table that a specific Alembic migration introduced, set:

```python
alembic_revision = "24_reorganize_public_schema_into_ddd_schemas"  # or whichever revision id introduced what you depend on
```

The runner will refuse to run your migration (with a clear error naming both revisions) until the target database has actually reached that schema state or later — you don't need to guess whether staging/production has "caught up" yet. If your migration doesn't depend on any particular schema state (e.g. it only touches tables/columns that have existed since the beginning), leave this as `None`.

## 5. Test locally, then let CI handle deployment

```bash
make data-migrate-list                 # confirm your script shows up as pending, in the right chain position
make data-migrate                      # run it locally (skips requires_api=True scripts by default)
make data-migrate --include-api        # only if you need to also run API-dependent ones locally
```

Once merged, the staging and production deploy pipelines apply it automatically — no manual step needed there. If it fails during an automatic run, the deploy is blocked and nothing is marked applied; fix the script and let CI retry it on the next deploy (no manual rollback needed unless you need to undo a migration that *did* succeed and now needs reversing, which stays a deliberate `make data-migrate-down NAME=...` action).
