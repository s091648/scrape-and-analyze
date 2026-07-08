from abc import ABC, abstractmethod
from typing import Optional


class TextGenerationService(ABC):
    """
    Domain interface for one-shot LLM text generation from a single
    self-contained prompt (e.g. weekly report title/summary synthesis).

    Deliberately separate from LLMService: consumers that only need
    this capability (no per-article content, no required-field
    validation) shouldn't be coupled to analyze()/translate().
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
    ) -> Optional[str]:
        """
        Run a one-shot generation task from the given prompt.

        Returns raw text response, or None on failure.
        """
        ...
