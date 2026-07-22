import re
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator


def _to_slug(v: str) -> str:
    v = v.lower().strip()
    v = re.sub(r'[^a-z0-9]+', '_', v)
    return v.strip('_')


def _to_title(v: str) -> str:
    return ' '.join(w.capitalize() for w in v.strip().split())


class TagOut(BaseModel):
    id: UUID
    name: str
    article_count: int

    model_config = ConfigDict(from_attributes=True)


class SimilarGroupOut(BaseModel):
    id: UUID
    similarity_score: float


class TagGroupOut(BaseModel):
    id: Optional[UUID] = None
    name: str
    display_name: str
    description: Optional[str]
    color_hex: Optional[str]
    topic_id: Optional[UUID] = None
    tags: List[TagOut]
    similar_groups: List[SimilarGroupOut] = []

    model_config = ConfigDict(from_attributes=True)


class TagGroupCreate(BaseModel):
    name: str
    display_name: str
    color_hex: Optional[str] = None
    topic_id: UUID
    description: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return _to_slug(v)

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, v: str) -> str:
        return _to_title(v)


class TagGroupUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    color_hex: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return _to_slug(v)

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, v: str) -> str:
        return _to_title(v)


class TagUpdate(BaseModel):
    name: Optional[str] = None
    tag_group_id: Optional[UUID] = None
    ungroup: Optional[bool] = None


class TagMoveItem(BaseModel):
    tag_id: UUID
    tag_group_id: UUID


class BatchMoveResult(BaseModel):
    succeeded: List[str]
    failed: List[dict]


class SuggestionOut(BaseModel):
    id: UUID
    new_tag_id: UUID
    new_tag_name: str
    existing_tag_id: UUID
    existing_tag_name: str
    group_name: str
    similarity_score: float
    article_id: Optional[UUID]

    model_config = ConfigDict(from_attributes=True)


class TagGroupMergeRequest(BaseModel):
    group_a_id: UUID
    group_b_id: UUID
    result_name: str
    result_display_name: str
    result_color_hex: Optional[str] = None
    result_description: Optional[str] = None

    @field_validator('result_name')
    @classmethod
    def normalize_result_name(cls, v: str) -> str:
        return _to_slug(v)

    @field_validator('result_display_name')
    @classmethod
    def normalize_result_display_name(cls, v: str) -> str:
        return _to_title(v)


class TagGroupReorderItem(BaseModel):
    id: UUID
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
