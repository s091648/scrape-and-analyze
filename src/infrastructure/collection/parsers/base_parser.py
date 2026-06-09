from abc import ABC, abstractmethod


class BaseContentParser(ABC):
    """Abstract base class for content parsers that extract text from raw input."""

    @abstractmethod
    def parse(self, content: str) -> str:
        """Parse raw input and return the full extracted content."""

    def prepare_for_analysis(self, content: str, fallback: str = '') -> str:
        """Return LLM-ready excerpt. Default: return content unchanged."""
        return content
