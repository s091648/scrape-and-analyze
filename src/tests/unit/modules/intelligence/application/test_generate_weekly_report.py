"""Unit tests for GenerateWeeklyReportUseCase."""
import json
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.modules.intelligence.application.use_cases.generate_weekly_report import GenerateWeeklyReportUseCase
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport


TOPIC_ID = uuid.uuid4()
TOPIC_NAME = "AI Research"
WEEK_START = date(2026, 6, 16)


def _summary(title="Paper A", tags=None):
    return ArticleSummaryForReport(
        title=title,
        summary="A great paper.",
        pain_points=None,
        insights=None,
        innovations=None,
        tags=tags or ["ai", "ml"],
        citation_count=10,
        view_count=5,
        published_at=None,
    )


def _make_uc(
    articles=None,
    llm_response=None,
    image_bytes=b"img",
    blob_url="https://r2.example.com/img.png",
    email_notifier=None,
    telegram_notifier=None,
):
    repo = MagicMock()
    repo.fetch_top_articles.return_value = articles if articles is not None else [_summary()]
    repo.save.side_effect = lambda r: r

    llm = MagicMock()
    llm.generate.return_value = llm_response or json.dumps({"title": "AI Week", "summary_text": "Great week."})

    image = MagicMock()
    image.generate_image.return_value = image_bytes

    blob = MagicMock()
    blob.upload.return_value = blob_url

    uc = GenerateWeeklyReportUseCase(
        report_repo=repo,
        llm_service=llm,
        image_service=image,
        blob_storage=blob,
        email_notifier=email_notifier,
        telegram_notifier=telegram_notifier,
    )
    return uc, repo, llm, image, blob


def test_execute_returns_weekly_report():
    uc, _, _, _, _ = _make_uc()
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert isinstance(result, WeeklyReport)


def test_execute_uses_llm_title_and_summary():
    uc, _, _, _, _ = _make_uc(llm_response=json.dumps({"title": "LLM Title", "summary_text": "LLM Summary"}))
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.title == "LLM Title"
    assert result.summary_text == "LLM Summary"


def test_execute_calls_image_generation():
    uc, _, _, image, _ = _make_uc()
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    image.generate_image.assert_called_once()


def test_execute_uploads_image_to_blob_storage():
    uc, _, _, _, blob = _make_uc(image_bytes=b"png-data")
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    blob.upload.assert_called_once()
    args = blob.upload.call_args[0]
    assert args[0] == b"png-data"
    assert args[2] == "image/png"


def test_execute_sets_cover_image_url():
    uc, _, _, _, _ = _make_uc(blob_url="https://r2.example.com/cover.png")
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.cover_image_url == "https://r2.example.com/cover.png"


def test_execute_saves_report_with_correct_article_count():
    articles = [_summary(f"Paper {i}") for i in range(3)]
    uc, repo, _, _, _ = _make_uc(articles=articles)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.article_count == 3


def test_execute_handles_empty_articles():
    uc, repo, llm, image, _ = _make_uc(articles=[])
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
    assert result.article_count == 0
    llm.generate.assert_not_called()
    image.generate_image.assert_not_called()


def test_execute_gracefully_handles_llm_failure():
    uc, _, llm, _, _ = _make_uc()
    llm.generate.side_effect = Exception("LLM timeout")
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
    assert TOPIC_NAME in result.title


def test_execute_gracefully_handles_image_failure():
    uc, _, _, image, _ = _make_uc()
    image.generate_image.side_effect = Exception("API error")
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
    assert result.cover_image_url is None


def test_execute_notifies_email_when_provided():
    email = MagicMock()
    uc, _, _, _, _ = _make_uc(email_notifier=email)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    email.notify.assert_called_once()


def test_execute_notifies_telegram_when_provided():
    telegram = MagicMock()
    uc, _, _, _, _ = _make_uc(telegram_notifier=telegram)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    telegram.notify.assert_called_once()


def test_execute_does_not_fail_when_email_notifier_raises():
    email = MagicMock()
    email.notify.side_effect = Exception("SMTP error")
    uc, _, _, _, _ = _make_uc(email_notifier=email)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
