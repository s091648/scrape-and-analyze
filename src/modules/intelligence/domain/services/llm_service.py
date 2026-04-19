from abc import ABC, abstractmethod
from typing import Optional
from src.modules.intelligence.domain.entities import Analysis

class LLMService(ABC):
    """Abstract base class for LLM services"""

    @abstractmethod
    def analyze(self, content: str) -> Optional[Analysis]:
        """Analyze content and return structured result"""
        ...
