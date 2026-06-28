from typing import List

from src.modules.intelligence.domain.value_objects.base_prompt import BasePrompt

_TEMPLATE = """\
Create a 16:9 abstract digital art image representing the topic "{topic_name}" for the week of {week_label}. \
Key themes: {tags_text}. Style: futuristic data visualization aesthetic, dark background with glowing \
geometric shapes and network nodes, professional and modern, no text or letters.\
"""


class ImageGenerationPrompt(BasePrompt):
    def __init__(self, filled: str = "") -> None:
        self._content = filled

    @property
    def content(self) -> str:
        return self._content

    def render(self, topic_name: str, top_tags: List[str], week_label: str) -> "ImageGenerationPrompt":
        tags_text = ", ".join(top_tags[:8]) if top_tags else "technology, innovation"
        filled = _TEMPLATE.format(
            topic_name=topic_name,
            week_label=week_label,
            tags_text=tags_text,
        )
        return ImageGenerationPrompt(filled=filled)
