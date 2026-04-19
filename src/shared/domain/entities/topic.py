from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Topic:
    name: str           # URL-safe slug, e.g. "digital-twins"
    display_name: str
    id: Optional[UUID] = None
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
