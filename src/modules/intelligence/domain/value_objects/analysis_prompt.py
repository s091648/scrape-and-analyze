from dataclasses import dataclass
from typing import List
from src.modules.intelligence.domain.value_objects import TagGroup


@dataclass(frozen=True)
class AnalysisPrompt:
    content: str = """You are a professional technology analyst specializing in __TOPIC__.

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

    def render(self, topic: str, tag_groups: List[TagGroup]) -> 'AnalysisPrompt':
        _content = self.content.replace("__TOPIC__", topic)
        _content = _content.replace("__TAG_GROUPS__", self._generate_tag_groups_str(tag_groups))
        return AnalysisPrompt(content=_content)
    
    def _generate_tag_groups_str(self, tag_groups: List[TagGroup]) -> str:
        return "\n".join([f"- {tg.display_name}: {tg.description}" for tg in tag_groups])