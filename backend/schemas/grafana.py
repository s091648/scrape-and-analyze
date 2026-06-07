from typing import Optional
from pydantic import BaseModel, Field


class MetricsBatchItem(BaseModel):
    query: str
    start: Optional[int] = None
    end: Optional[int] = None
    step: str = "60"


class LogsBatchItem(BaseModel):
    query: str
    start: Optional[str] = None
    end: Optional[str] = None
    limit: int = 100
    direction: str = "backward"


class LokiMetricsBatchItem(BaseModel):
    query: str
    start: Optional[int] = None
    end: Optional[int] = None
    step: str = "60"


class TracesBatchItem(BaseModel):
    q: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    limit: int = 20
    min_duration: Optional[str] = Field(default=None, alias="minDuration")

    model_config = {"populate_by_name": True}
