"""
MetricExtractor — abstraction for fetching + extracting a recommendation-signal
metric value for an article from an external source.

Mirrors the LLMService / ResilientLLMService pattern (src/infrastructure/intelligence/llm/):
a domain interface here, concrete implementations in src/infrastructure/collection/metrics/.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MetricExtractor(ABC):
    @abstractmethod
    def fetch(self, article_identifiers: Dict[str, str]) -> Optional[dict]:
        """Fetch the raw response for one article from this extractor's source.
        article_identifiers e.g. {"doi": "...", "arxiv_id": "..."} — extractor uses whichever key it needs."""

    @abstractmethod
    def extract(self, raw_response: dict, extractor_spec: Dict[str, Any]) -> Optional[Any]:
        """Pull the metric value out of a raw response already fetched via fetch()."""
