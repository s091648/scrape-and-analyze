"""Unit tests for WeeklyReportPrompt — covers the numbered article list and [N] citation instruction."""
import uuid
from datetime import date

from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport
from src.modules.intelligence.domain.value_objects.weekly_report_prompt import WeeklyReportPrompt


def _article(title="Paper A", tags=None):
    return ArticleSummaryForReport(
        article_id=uuid.uuid4(),
        title=title,
        summary="A great paper.",
        tags=tags or ["ai"],
    )


def test_render_numbers_articles_starting_at_one():
    articles = [_article("Paper A"), _article("Paper B"), _article("Paper C")]
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=articles, week_start=date(2026, 6, 16))
    assert "[1] Title: Paper A" in prompt.content
    assert "[2] Title: Paper B" in prompt.content
    assert "[3] Title: Paper C" in prompt.content


def test_render_includes_citation_instruction():
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[_article()], week_start=date(2026, 6, 16))
    assert "cite it inline" in prompt.content
    assert "[1]" in prompt.content
    assert "never invent a number" in prompt.content


def test_render_does_not_expose_article_ids_to_the_llm():
    article = _article("Paper A")
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[article], week_start=date(2026, 6, 16))
    assert str(article.article_id) not in prompt.content


def test_render_json_output_format_still_title_and_summary_text():
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[_article()], week_start=date(2026, 6, 16))
    assert '"title"' in prompt.content
    assert '"summary_text"' in prompt.content


# ── Metrics line (2026-07-12) ────────────────────────────────────────────────

def test_render_shows_humanized_metric_labels_not_raw_keys():
    article = ArticleSummaryForReport(
        article_id=uuid.uuid4(), title="Paper A", tags=["ai"],
        metrics={"citation_count": 42, "impact_factor": 3.5},
    )
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[article], week_start=date(2026, 6, 16))
    assert "Citation Count: 42" in prompt.content
    assert "Impact Factor: 3.50" in prompt.content
    assert "citation_count" not in prompt.content
    assert "impact_factor" not in prompt.content


def test_render_shows_view_count_when_positive():
    article = ArticleSummaryForReport(article_id=uuid.uuid4(), title="Paper A", tags=["ai"], view_count=15)
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[article], week_start=date(2026, 6, 16))
    assert "View Count: 15" in prompt.content


def test_render_omits_metrics_line_when_no_metrics_and_zero_view_count():
    article = _article("Paper A")
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[article], week_start=date(2026, 6, 16))
    assert "Metrics:" not in prompt.content


def test_render_includes_instruction_that_metrics_are_not_the_sole_factor():
    article = ArticleSummaryForReport(article_id=uuid.uuid4(), title="Paper A", tags=["ai"], metrics={"citation_count": 1})
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[article], week_start=date(2026, 6, 16))
    assert "one input among" in prompt.content
    assert "does not by itself make an article more worth writing about" in prompt.content


def test_render_does_not_imply_the_article_list_is_ranked():
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[_article()], week_start=date(2026, 6, 16))
    assert "sorted" not in prompt.content.lower()
    assert "ranked" not in prompt.content.lower()


# ── Title format: date is composed in code, not by the LLM (2026-07-14) ─────

def test_render_instructs_the_llm_to_omit_dates_from_the_title():
    prompt = WeeklyReportPrompt().render(topic_name="AI Research", articles=[_article()], week_start=date(2026, 6, 16))
    assert "do not include any date" in prompt.content.lower()
