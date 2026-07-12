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

Some articles list a Metrics line (e.g. citation or view counts). Treat these as one input among \
several — alongside each article's actual content — when judging which articles are most worth \
covering; a high metric value does not by itself make an article more worth writing about than one \
with richer or more novel content. Articles with no Metrics line simply have none tracked for this \
deployment and should be judged on content alone.

When a sentence in your summary draws on a specific article, cite it inline using that article's \
bracket number from the list above, e.g. "...launched a new model [1], while...". The number refers \
only to that article's position in the list above — never invent a number, and never cite an article \
by its title or any other identifier.

Respond with ONLY valid JSON in this exact format:
{{"title": "<compelling report title>", "summary_text": "<2-4 paragraph summary of key themes, insights, and innovations, with inline [N] citations>"}}
"""


def _humanize_metric_key(key: str) -> str:
    return key.replace("_", " ").title()


def _format_metric_value(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:.2f}"


def _metrics_line(article: ArticleSummaryForReport) -> str:
    parts = []
    if article.view_count > 0:
        parts.append(f"View Count: {article.view_count}")
    for key, value in article.metrics.items():
        parts.append(f"{_humanize_metric_key(key)}: {_format_metric_value(value)}")
    return f"\n    Metrics: {', '.join(parts)}" if parts else ""


class WeeklyReportPrompt(BasePrompt):
    def __init__(self, filled: str = "") -> None:
        self._content = filled

    @property
    def content(self) -> str:
        return self._content

    def render(self, topic_name: str, articles: List[ArticleSummaryForReport], week_start: date) -> "WeeklyReportPrompt":
        week_label = week_start.strftime("%B %d, %Y")
        articles_text = "\n\n".join(
            f"[{i}] Title: {a.title}\n    Summary: {a.summary or 'N/A'}\n    Tags: {', '.join(a.tags)}{_metrics_line(a)}"
            for i, a in enumerate(articles, start=1)
        )
        filled = _TEMPLATE.format(
            count=len(articles),
            topic_name=topic_name,
            week_label=week_label,
            articles_text=articles_text,
        )
        return WeeklyReportPrompt(filled=filled)
