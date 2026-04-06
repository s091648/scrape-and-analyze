from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class AnalysisResult:
    """Result from LLM analysis"""
    tag_groups: List[Dict[str, Any]]   # [{"group": str, "tags": [str]}]
    pain_points: str
    insights: str
    innovations: str
    input_tokens: int
    output_tokens: int
    model_used: str = ""


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        """Analyze content and return structured result"""
        pass
