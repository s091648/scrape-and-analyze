"""Re-exports shared.search_index.tokenizer — moved there (023-article-search follow-up)
so backend/services/search_service.py can tokenize a query string with the exact same
algorithm src/'s RebuildSearchIndexUseCase used to tokenize article text at index-build
time (src/ is not copied into backend's production image, so the implementation can't
live only here). Kept as a re-export, not deleted, so this module's existing domain-layer
import path (`from src.modules.search.domain.services.tokenizer import tokenize`) stays
stable for callers within src/."""
from shared.search_index.tokenizer import tokenize, MIN_TERM_LENGTH  # noqa: F401

__all__ = ["tokenize", "MIN_TERM_LENGTH"]
