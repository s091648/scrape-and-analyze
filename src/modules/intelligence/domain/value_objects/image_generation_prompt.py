from typing import List

from src.modules.intelligence.domain.value_objects.base_prompt import BasePrompt

_MAX_SUMMARY_CHARS = 400

_TEMPLATE_WITH_SUMMARY = """\
Create a 16:9 editorial cover illustration for the "{topic_name}" weekly digest ({week_label}). \
The image must depict the specific subject matter of this week's stories below — concrete objects, scenes, \
or symbols tied to the actual content — not generic abstract tech decoration. \
This week's stories: {summary_snippet} \
Key topics: {tags_text}. \
Style: modern conceptual illustration or digital painting, cohesive color palette, professional editorial tone, \
no text or letters, no generic circuit-board or network-node patterns.\
"""

_TEMPLATE_FALLBACK = """\
Create a 16:9 editorial cover illustration for the "{topic_name}" weekly digest ({week_label}). \
The image should depict concrete scenes or symbols tied to these topics: {tags_text}. \
Style: modern conceptual illustration or digital painting, cohesive color palette, professional editorial tone, \
no text or letters, no generic circuit-board or network-node patterns.\
"""


class ImageGenerationPrompt(BasePrompt):
    def __init__(self, filled: str = "") -> None:
        self._content = filled

    @property
    def content(self) -> str:
        return self._content

    def render(
        self,
        topic_name: str,
        top_tags: List[str],
        week_label: str,
        summary_text: str = "",
    ) -> "ImageGenerationPrompt":
        tags_text = ", ".join(top_tags[:8]) if top_tags else "technology, innovation"
        summary_snippet = summary_text.strip().replace("\n", " ")[:_MAX_SUMMARY_CHARS]

        if summary_snippet:
            filled = _TEMPLATE_WITH_SUMMARY.format(
                topic_name=topic_name,
                week_label=week_label,
                summary_snippet=summary_snippet,
                tags_text=tags_text,
            )
        else:
            filled = _TEMPLATE_FALLBACK.format(
                topic_name=topic_name,
                week_label=week_label,
                tags_text=tags_text,
            )
        return ImageGenerationPrompt(filled=filled)
