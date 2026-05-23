#!/usr/bin/env python
# scripts/run_data_migrations.py
"""
Versioned data-migration runner (analogous to alembic for data scripts).

Usage:
    python scripts/run_data_migrations.py              # run all pending (skip API scripts)
    python scripts/run_data_migrations.py --include-api
    python scripts/run_data_migrations.py --list
    python scripts/run_data_migrations.py --name 001_backfill_tag_group_definitions
    python scripts/run_data_migrations.py --down 001_backfill_tag_group_definitions
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(
        description="Versioned data-migration runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list", action="store_true",
                        help="List all migrations with their status")
    parser.add_argument("--name", metavar="NAME",
                        help="Run one specific migration by name")
    parser.add_argument("--down", metavar="NAME",
                        help="Roll back one specific migration by name")
    parser.add_argument("--include-api", action="store_true",
                        help="Also run migrations that require external APIs")
    args = parser.parse_args()

    from src.infrastructure.persistence.database import get_session, init_db
    from scripts.data.runner import (
        list_status, run_pending, run_one, run_down,
    )

    init_db()
    session = get_session()

    try:
        if args.list:
            list_status(session)
        elif args.down:
            run_down(session, args.down)
        elif args.name:
            run_one(session, args.name, include_api=args.include_api)
        else:
            run_pending(session, include_api=args.include_api)
    finally:
        session.close()


if __name__ == "__main__":
    main()
