from pydantic import BaseModel, field_validator
from shared.enums.scraper_keyword import VALID_KEYWORD_TYPES


class ScraperKeywordOut(BaseModel):
    id: str
    keyword_type: str
    keyword: str


class ScraperKeywordCreate(BaseModel):
    keyword: str
    keyword_type: str = "rss"

    @field_validator("keyword_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in VALID_KEYWORD_TYPES:
            raise ValueError(f"keyword_type must be one of {sorted(VALID_KEYWORD_TYPES)}")
        return v
