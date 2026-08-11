from typing import List
from pydantic import BaseModel

from backend.schemas.topic import TopicOut
from backend.schemas.language import LanguagesResponse


class BootstrapOut(BaseModel):
    """Response for POST /bootstrap — collapses the SSR-initialization chain
    (guest token + GET /topics + GET /languages) into a single round trip."""
    access_token: str
    expires_in: int
    topics: List[TopicOut]
    languages: LanguagesResponse
