from dataclasses import dataclass
from typing import List, Optional

from .base_prompt import BasePrompt


_LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese (Taiwan)",
    "zh-CN": "Simplified Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}

# Public accessor for language code → display name mapping
LANGUAGE_NAMES = _LANGUAGE_NAMES


_ARTICLE_TEMPLATE = """You are a professional translator. Translate the following article analysis from English to __TARGET_LANGUAGE__.

Only translate the content, do not add any explanations or additional text.
Keep the same format and structure — use the exact section headers below.
If any field is not applicable or empty, keep it empty.

Summary:
__SUMMARY__

Pain Points:
__PAIN_POINTS__

Insights:
__INSIGHTS__

Innovations:
__INNOVATIONS__

Translation (use the same section headers: Summary, Pain Points, Insights, Innovations):"""

_TAG_TEMPLATE = """You are a professional translator. Translate the following tag names from English to __TARGET_LANGUAGE__.
These are technical tags used in a research article classification system.
Keep translations concise and natural in the target language.
IMPORTANT: Do NOT translate words or phrases that are fully uppercase (e.g., AI, IoT, IIoT, BIM, VR) — keep them as-is.

Tags (one per line):
__TAGS__

Return the translated tags, one per line, in the same order. Do not add any other text."""

_GROUP_TEMPLATE = """You are a professional translator. Translate the following tag group display names and descriptions from English to __TARGET_LANGUAGE__.
These are category headings for a research article classification system.
Keep display name translations concise and natural.
IMPORTANT: Do NOT translate words or phrases that are fully uppercase or proper nouns (e.g., Digital Twin, AI, IoT, Industry 4.0) — keep them as-is.

Groups (format: display_name | description per line):
__GROUPS__

Return the translated groups, one per line, in the same "display_name | description" format, in the same order. Do not add any other text."""


@dataclass(frozen=True)
class ArticleTranslationPrompt(BasePrompt):
    """Prompt value object for article analysis translation."""

    _content: str = _ARTICLE_TEMPLATE

    @property
    def content(self) -> str:
        """Return the current prompt text content."""
        return self._content

    def render(
        self,
        target_language: str,
        summary: str,
        pain_points: str,
        insights: str,
        innovations: str,
    ) -> 'ArticleTranslationPrompt':
        """Fill placeholders and return a new prompt with translated content fields."""
        lang_name = _LANGUAGE_NAMES.get(target_language, target_language)
        filled = self._content
        filled = filled.replace("__TARGET_LANGUAGE__", lang_name)
        filled = filled.replace("__SUMMARY__", summary)
        filled = filled.replace("__PAIN_POINTS__", pain_points)
        filled = filled.replace("__INSIGHTS__", insights)
        filled = filled.replace("__INNOVATIONS__", innovations)
        return ArticleTranslationPrompt(_content=filled)


@dataclass(frozen=True)
class TagTranslationPrompt(BasePrompt):
    """Prompt value object for tag name translation."""

    _content: str = _TAG_TEMPLATE

    @property
    def content(self) -> str:
        """Return the current prompt text content."""
        return self._content

    def render(self, target_language: str, tags: List[str]) -> 'TagTranslationPrompt':
        """Fill placeholders and return a new prompt with the tag list."""
        lang_name = _LANGUAGE_NAMES.get(target_language, target_language)
        filled = self._content
        filled = filled.replace("__TARGET_LANGUAGE__", lang_name)
        filled = filled.replace("__TAGS__", "\n".join(tags))
        return TagTranslationPrompt(_content=filled)


_ARTICLE_BODY_TEMPLATE = """You are a professional translator. Translate the following article title and content from English to __TARGET_LANGUAGE__.

Only translate the content, do not add any explanations or additional text.
Keep the same format and structure — use the exact section headers below.
If any field is not applicable or empty, keep it empty.

Title:
__TITLE__

Content:
__CONTENT__

Translation (use the same section headers: Title, Content):"""


@dataclass(frozen=True)
class ArticleBodyTranslationPrompt(BasePrompt):
    """Prompt value object for article title and content translation."""

    _content: str = _ARTICLE_BODY_TEMPLATE

    @property
    def content(self) -> str:
        return self._content

    def render(self, target_language: str, title: str, content: str) -> 'ArticleBodyTranslationPrompt':
        """Fill placeholders and return a new prompt with the article body."""
        lang_name = _LANGUAGE_NAMES.get(target_language, target_language)
        filled = self._content
        filled = filled.replace("__TARGET_LANGUAGE__", lang_name)
        filled = filled.replace("__TITLE__", title)
        filled = filled.replace("__CONTENT__", content)
        return ArticleBodyTranslationPrompt(_content=filled)

    @staticmethod
    def parse_response(text: str) -> tuple[Optional[str], Optional[str]]:
        """Parse LLM response into (title, content) by section headers. Returns (None, None) on failure."""
        import re
        parts = re.split(r'\n(?=(?:Title|Content)\s*[:：]\s*)', text, flags=re.IGNORECASE)
        fields: dict[str, Optional[str]] = {"title": None, "content": None}
        for part in parts:
            for header in ("title", "content"):
                if re.match(rf'^{header}\s*[:：]', part, re.IGNORECASE):
                    fields[header] = re.sub(rf'^{header}\s*[:：]\s*', '', part, flags=re.IGNORECASE).strip() or None
                    break
        return fields["title"], fields["content"]


@dataclass(frozen=True)
class GroupTranslationPrompt(BasePrompt):
    """Prompt value object for tag group display name translation."""

    _content: str = _GROUP_TEMPLATE

    @property
    def content(self) -> str:
        """Return the current prompt text content."""
        return self._content

    def render(self, target_language: str, groups: List[str]) -> 'GroupTranslationPrompt':
        """Fill placeholders and return a new prompt with the group list."""
        lang_name = _LANGUAGE_NAMES.get(target_language, target_language)
        filled = self._content
        filled = filled.replace("__TARGET_LANGUAGE__", lang_name)
        filled = filled.replace("__GROUPS__", "\n".join(groups))
        return GroupTranslationPrompt(_content=filled)

    @staticmethod
    def format_group(display_name: str, description: str | None) -> str:
        """Format a group for the prompt: 'display_name | description'."""
        desc = description or ""
        return f"{display_name} | {desc}"


_WEEKLY_REPORT_TEMPLATE = """You are a professional translator. Translate the following weekly report from English to __TARGET_LANGUAGE__.

Only translate the content, do not add any explanations or additional text.
Keep the same structure: respond with exactly the two sections below.
If a field is not applicable, keep it empty.

Title:
__TITLE__

Summary:
__SUMMARY__

Translation (use the exact section headers: Title, Summary):"""


@dataclass(frozen=True)
class WeeklyReportTranslationPrompt(BasePrompt):
    """Prompt value object for weekly report (title + summary) translation."""

    _content: str = _WEEKLY_REPORT_TEMPLATE

    @property
    def content(self) -> str:
        return self._content

    def render(self, target_language: str, title: str, summary: str) -> "WeeklyReportTranslationPrompt":
        lang_name = _LANGUAGE_NAMES.get(target_language, target_language)
        filled = self._content
        filled = filled.replace("__TARGET_LANGUAGE__", lang_name)
        filled = filled.replace("__TITLE__", title)
        filled = filled.replace("__SUMMARY__", summary)
        return WeeklyReportTranslationPrompt(_content=filled)

    @staticmethod
    def parse_response(text: str) -> tuple[Optional[str], Optional[str]]:
        """Parse LLM response into (title, summary) by section headers."""
        import re
        parts = re.split(r'\n(?=(?:Title|Summary)\s*[:：]\s*)', text, flags=re.IGNORECASE)
        fields: dict[str, Optional[str]] = {"title": None, "summary": None}
        for part in parts:
            for header in ("title", "summary"):
                if re.match(rf'^{header}\s*[:：]', part, re.IGNORECASE):
                    fields[header] = re.sub(rf'^{header}\s*[:：]\s*', '', part, flags=re.IGNORECASE).strip() or None
                    break
        return fields["title"], fields["summary"]
