from sqlalchemy.orm import Session


def get_failed_tasks_paginated(db: Session, page: int, size: int):
    from models.failed_task import FailedTask
    query = db.query(FailedTask).order_by(FailedTask.failed_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return total, items


# Long statements (bulk INSERT ... VALUES lists) are capped — the dashboard only needs
# enough to recognize the query.
_QUERY_TEXT_MAX_CHARS = 2000


def get_query_texts(db: Session, queryids: list[int]) -> tuple[bool, list[tuple[int, str]]]:
    """SQL text for pg_stat_statements query ids, scoped to the current database — the
    exporter-fed Prometheus metrics (alloy/) only carry `queryid` as a label, never the
    statement itself. Returns (available, [(queryid, query)]); `available` is False when
    the extension isn't installed or preloaded here (the local dev Postgres). The lookup
    runs in a SAVEPOINT, so that failure rolls back only this statement and the session
    stays usable without discarding anything else pending in it.

    Raw text() SQL: pg_stat_statements is a system view with no ORM model. DISTINCT ON
    because one queryid can appear once per (user, database) pair."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    try:
        with db.begin_nested():
            rows = db.execute(
                text(
                    "SELECT DISTINCT ON (queryid) queryid, left(query, :max_chars) AS query "
                    "FROM pg_stat_statements "
                    "WHERE queryid = ANY(:queryids) "
                    "AND dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) "
                    "ORDER BY queryid"
                ),
                {"queryids": queryids, "max_chars": _QUERY_TEXT_MAX_CHARS},
            ).all()
    except DBAPIError:
        return False, []
    return True, [(row.queryid, row.query) for row in rows]
