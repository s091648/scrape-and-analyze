from pydantic import BaseModel


class SearchSuggestion(BaseModel):
    term: str
    occurrence_count: int


class AutocompleteResponse(BaseModel):
    suggestions: list[SearchSuggestion]
