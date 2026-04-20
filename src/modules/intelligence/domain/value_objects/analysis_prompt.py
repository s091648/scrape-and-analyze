from dataclasses import dataclass
from typing import List

from .base_prompt import BasePrompt
from .tag_group import TagGroup

_TEMPLATE = """You are a professional technology analyst specializing in __TOPIC__.

Analyze the following article and classify it into one or more of the predefined tag groups below.
For each group that genuinely applies, generate 2-4 specific sub-tags describing the article's focus
within that group. Assign 1-3 groups total; only include groups truly relevant to the article.

TAG GROUPS (use these exact group key strings):
__TAG_GROUPS__


Also extract:
- summary: 2-3 sentences covering what the article is about, its core contribution, and why it matters. Written for a general technical audience. This will appear at the top of the article page.
- pain_points: Key challenges, problems, or barriers mentioned in the article
- insights: Important observations, trends, or takeaways
- innovations: New technologies, methods, solutions, or approaches mentioned

Return your analysis as valid JSON with these exact fields:
{
  "tag_groups": [
    {"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]},
    {"group": "manufacturing_industry", "tags": ["factory automation", "process optimization"]}
  ],
  "summary": "Brief overview of the article's core contribution and significance...",
  "pain_points": "Description of challenges mentioned...",
  "insights": "Key observations and trends...",
  "innovations": "New technologies or approaches..."
}

IMPORTANT: Output ONLY the JSON object, no other text or explanation.
"""


@dataclass(frozen=True)
class AnalysisPrompt(BasePrompt):
    """
    Prompt value object for article analysis.

    Holds the template as a class-level default; call render() with topic and
    tag_groups from the DB to produce a filled instance ready for provider injection.

    Example:
        prompt = AnalysisPrompt().render(
            topic="Digital Twins, IoT",
            tag_groups=[TagGroup("Digital Twin", "virtual replicas of physical systems")],
        )
        provider = GeminiProvider(..., prompt=prompt.content)
    """

    _content: str = _TEMPLATE

    @property
    def content(self) -> str:
        return self._content

    def render(self, topic: str, tag_groups: List[TagGroup]) -> 'AnalysisPrompt':  # type: ignore[override]
        """
        Fill __TOPIC__ and __TAG_GROUPS__ placeholders and return a new instance.

        Args:
            topic:      Display name(s) of the analysis domain, e.g. "Digital Twins, IoT".
            tag_groups: Active tag groups from the DB; each becomes one entry in the
                        TAG GROUPS section of the prompt.
        """
        filled = self._content.replace("__TOPIC__", topic)
        filled = filled.replace("__TAG_GROUPS__", self._format_tag_groups(tag_groups))
        return AnalysisPrompt(_content=filled)

    @staticmethod
    def _format_tag_groups(tag_groups: List[TagGroup]) -> str:
        return "\n".join(
            f"- {tg.display_name}: {tg.description}" for tg in tag_groups
        )
