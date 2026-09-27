from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FailedTaskOut(BaseModel):
    id: UUID
    task_type: str
    article_url: Optional[str]
    exception_type: Optional[str]
    exception_message: Optional[str]
    failed_at: Optional[datetime]
    resolved: bool

    model_config = ConfigDict(from_attributes=True)


class PaginatedFailedTasks(BaseModel):
    items: list[FailedTaskOut]
    total: int
    page: int
    size: int


class QueryTextOut(BaseModel):
    # String, not int: pg_stat_statements.queryid is a signed 64-bit value, beyond
    # JavaScript's safe-integer range — and Prometheus already hands the frontend the
    # same id as a string label.
    queryid: str
    query: str


class QueryTextsResponse(BaseModel):
    # False when pg_stat_statements isn't installed/loaded in this database (e.g. the
    # local dev Postgres) — distinct from "installed, but none of these ids are present".
    available: bool
    items: list[QueryTextOut]
