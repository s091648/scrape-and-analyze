from abc import ABC, abstractmethod
from typing import Optional, Tuple

from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.intelligence.domain.services import LLMService

_REQUIRED_FIELDS = ['tag_groups', 'pain_points', 'insights', 'innovations', 'summary']


class BaseProvider(LLMService, ABC):
    """
    Infrastructure base for all LLM providers.
    Implements LLMService and adds the prompt loading + response parsing helpers.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    @abstractmethod
    def _call_api(self, content: str, prompt: str) -> dict:
        """
        Call the provider API and return parsed JSON dict.
        Raises on failure.
        """
        ...

    def analyze(self, content: str) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        from src.modules.intelligence.domain.value_objects import TagGroup
        from src.modules.intelligence.domain.value_objects import AnalysisPrompt, TagGroup as TG

        prompt = self._load_prompt()
        try:
            result = self._call_api(content, prompt)
        except Exception:
            return None

        if not self._validate(result):
            return None

        tag_groups = [
            TG(display_name=tg.get("group", ""), description=", ".join(tg.get("tags", [])))
            for tg in result.get("tag_groups", [])
        ]

        analysis_content = AnalysisContent(
            pain_points=result.get("pain_points", ""),
            insights=result.get("insights", ""),
            innovations=result.get("innovations", ""),
            summary=result.get("summary", ""),
            tag_groups=tag_groups,
        )
        analysis_metadata = AnalysisMetadata(
            model_used=self._model,
            input_tokens=result.get("_input_tokens", 0),
            output_tokens=result.get("_output_tokens", 0),
        )
        return analysis_content, analysis_metadata

    def _validate(self, result: dict) -> bool:
        return all(f in result for f in _REQUIRED_FIELDS)

    def _load_prompt(self) -> str:
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
            "entrypoints", "cli", "prompts", "analysis.txt"
        )
        with open(path, "r") as f:
            return f.read()
