"""Tests for the per-module WeeklyReportEmailMessageBuilder."""
import uuid
from datetime import date


def _report(title="AI Week", summary="Lots of LLM news this week."):
    from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
    return WeeklyReport(
        id=uuid.uuid4(),
        topic_id=uuid.uuid4(),
        week_start_date=date(2026, 6, 16),
        title=title,
        summary_text=summary,
        cover_image_url="https://cdn.example.com/cover.png",
        article_ids=["Paper A", "Paper B"],
        article_count=2,
        status="completed",
    )


def test_build_uses_english_subject_and_cta_for_non_zh_locale():
    from src.infrastructure.intelligence.notifications import WeeklyReportEmailMessageBuilder

    msg = WeeklyReportEmailMessageBuilder.build(_report(), locale="en", site_url="https://example.com")
    assert msg.subject == "Your Weekly Report is Ready"
    assert "View Full Report" in msg.html


def test_build_uses_chinese_subject_and_cta_for_zh_tw_locale():
    from src.infrastructure.intelligence.notifications import WeeklyReportEmailMessageBuilder

    msg = WeeklyReportEmailMessageBuilder.build(_report(), locale="zh-TW", site_url="https://example.com")
    assert msg.subject == "您的每週報告已準備好"
    assert "查看完整報告" in msg.html


def test_build_includes_report_title_and_summary_excerpt():
    from src.infrastructure.intelligence.notifications import WeeklyReportEmailMessageBuilder

    msg = WeeklyReportEmailMessageBuilder.build(
        _report(title="My Title", summary="A" * 500),
        locale="en",
        site_url="https://example.com",
    )
    assert "My Title" in msg.html
    assert "A" * 300 in msg.html


def test_build_includes_site_url_in_cta():
    from src.infrastructure.intelligence.notifications import WeeklyReportEmailMessageBuilder

    msg = WeeklyReportEmailMessageBuilder.build(_report(), locale="en", site_url="https://my.site/x")
    assert "https://my.site/x" in msg.html
