from typing import List
from pydantic import BaseModel


class LanguageInfo(BaseModel):
    code: str
    name: str
    native_name: str


class LanguagesResponse(BaseModel):
    available: List[LanguageInfo]
    resolved: str