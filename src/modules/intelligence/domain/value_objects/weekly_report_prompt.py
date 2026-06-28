import json
from datetime import date
from typing import List

from src.modules.intelligence.domain.value_objects.base_prompt import BasePrompt
from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport

_TEMPLATE = """\
You are an expert technical editor. Based on the following {count} articles about "{topic_name}" \
from the week of {week_label}, generate a weekly summary report.

Articles:
{articles_text}

Respond with ONLY valid JSON in this exact format:
{{"title": "<compelling report title>", "summary_text": "<2-4 paragraph summary of key themes, insights, and innovations>"}}
"""


class WeeklyReportPrompt(BasePrompt):
    def __init__(self, filled: str = "") -> None:
        self._content = filled

    @property
    def content(self) -> str:
        return self._content

    def render(self, topic_name: str, articles: List[ArticleSummaryForReport], week_start: date) -> "WeeklyReportPrompt":
        week_label = week_start.strftime("%B %d, %Y")
        articles_text = "\n\n".join(
            f"- Title: {a.title}\n  Summary: {a.summary or 'N/A'}\n  Tags: {', '.join(a.tags)}"
            for a in articles
        )
        filled = _TEMPLATE.format(
            count=len(articles),
            topic_name=topic_name,
            week_label=week_label,
            articles_text=articles_text,
        )
        return WeeklyReportPrompt(filled=filled)
