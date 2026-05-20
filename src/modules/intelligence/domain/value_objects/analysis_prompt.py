from dataclasses import dataclass
from typing import List

from .base_prompt import BasePrompt
from .tag_group import TagGroup

_COMMON_EXTRACTION = """
Also extract:
- summary: 2-3 sentences covering what the article is about, its core contribution, and why it matters. Written for a general technical audience. This will appear at the top of the article page.
- pain_points: Key challenges, problems, or barriers mentioned in the article
- insights: Important observations, trends, or takeaways
- innovations: New technologies, methods, solutions, or approaches mentioned

Return your analysis as valid JSON with these exact fields:
{
  "tag_groups": [
    {"group": "research_methods", "tags": ["transformer", "attention mechanism"]},
    {"group": "applications", "tags": ["computer vision", "object detection"]}
  ],
  "summary": "Brief overview of the article's core contribution and significance...",
  "pain_points": "Description of challenges mentioned...",
  "insights": "Key observations and trends...",
  "innovations": "New technologies or approaches..."
}

IMPORTANT: Output ONLY the JSON object, no other text or explanation."""

# ── Auto mode: LLM freely generates tag groups ──────────────────────────────

_AUTO_TEMPLATE = """You are a professional technology analyst specializing in __TOPIC__.

Analyze the following article and classify it into 1-3 relevant tag groups of your choosing.
For each group, create a concise snake_case key string (e.g. "research_methods", "applications", "evaluation").
For each applicable group, generate 2-4 specific sub-tags describing the article's focus within that group.
Only include groups truly relevant to the article.
""" + _COMMON_EXTRACTION

# ── Fixed mode: LLM constrained to predefined DB tag groups ─────────────────

_FIXED_TEMPLATE = """You are a professional technology analyst specializing in __TOPIC__.

Analyze the following article and classify it into one or more of the predefined tag groups below.
For each group that genuinely applies, generate 2-4 specific sub-tags describing the article's focus
within that group. Assign 1-3 groups total; only include groups truly relevant to the article.

TAG GROUPS — use ONLY these exact key strings in the "group" field, no others:
__TAG_GROUPS__
""" + _COMMON_EXTRACTION


@dataclass(frozen=True)
class AnalysisPrompt(BasePrompt):
    """
    Prompt value object for article analysis.

    Two rendering modes:
      - render_auto(topic):              LLM freely generates tag group keys.
      - render_fixed(topic, tag_groups): LLM constrained to predefined DB tag groups.

    Use render_auto when topic.auto_tag_groups is True (default).
    Use render_fixed when topic.auto_tag_groups is False (admin has defined groups).
    """

    _content: str = _AUTO_TEMPLATE

    @property
    def content(self) -> str:
        return self._content

    def render(self, **kwargs) -> 'AnalysisPrompt':
        """Compatibility shim; prefer render_auto() or render_fixed()."""
        topic = kwargs.get("topic", "")
        tag_groups = kwargs.get("tag_groups", [])
        if tag_groups:
            return self.render_fixed(topic, tag_groups)
        return self.render_auto(topic)

    def render_auto(self, topic: str) -> 'AnalysisPrompt':
        """Fill __TOPIC__ placeholder; LLM generates tag groups freely."""
        filled = _AUTO_TEMPLATE.replace("__TOPIC__", topic)
        return AnalysisPrompt(_content=filled)

    def render_fixed(self, topic: str, tag_groups: List[TagGroup]) -> 'AnalysisPrompt':
        """Fill __TOPIC__ and __TAG_GROUPS__; LLM must use the provided group keys."""
        filled = _FIXED_TEMPLATE.replace("__TOPIC__", topic)
        filled = filled.replace("__TAG_GROUPS__", self._format_fixed_groups(tag_groups))
        return AnalysisPrompt(_content=filled)

    @staticmethod
    def _format_fixed_groups(tag_groups: List[TagGroup]) -> str:
        lines = []
        for tg in tag_groups:
            key = tg.name if tg.name else tg.display_name.lower().replace(" ", "_")
            desc = f": {tg.description}" if tg.description else ""
            lines.append(f'- "{key}" ({tg.display_name}){desc}')
        return "\n".join(lines)
