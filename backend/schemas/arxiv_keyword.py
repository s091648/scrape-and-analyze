from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ArxivKeywordCreate(BaseModel):
    keyword: str


class ArxivKeywordOut(BaseModel):
    id: UUID
    keyword: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
