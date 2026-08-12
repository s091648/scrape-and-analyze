"""Unit tests for GenerateWeeklyReportUseCase."""
import json
import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.modules.intelligence.application.use_cases.generate_weekly_report import GenerateWeeklyReportUseCase
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.modules.intelligence.domain.value_objects.article_summary_for_report import ArticleSummaryForReport
from src.modules.intelligence.domain.value_objects.translation_prompt import WeeklyReportTranslationPrompt


TOPIC_ID = uuid.uuid4()
TOPIC_NAME = "AI Research"
WEEK_START = date(2026, 6, 16)
WEEK_RANGE = "2026/06/16–2026/06/22"


def _summary(title="Paper A", tags=None, article_id=None):
    return ArticleSummaryForReport(
        article_id=article_id or uuid.uuid4(),
        title=title,
        summary="A great paper.",
        pain_points=None,
        insights=None,
        innovations=None,
        tags=tags or ["ai", "ml"],
        metrics={"citation_count": 10},
        view_count=5,
        published_at=None,
    )


def _make_uc(
    articles=None,
    llm_response=None,
    image_bytes=b"img",
    blob_url="https://r2.example.com/img.webp",
    email_notifier=None,
    telegram_notifier=None,
    translation_languages=(),
    cache_gateway=None,
):
    repo = MagicMock()
    repo.fetch_top_articles.return_value = articles if articles is not None else [_summary()]
    repo.find_by_topic_and_week.return_value = None
    repo.save.side_effect = lambda r: r

    llm = MagicMock()
    llm.generate.return_value = llm_response or json.dumps({"title": "AI Week", "summary_text": "Great week."})

    image = MagicMock()
    image.generate_image.return_value = image_bytes

    blob = MagicMock()
    blob.upload.return_value = blob_url

    translation_repo = MagicMock()
    translation_prompt = WeeklyReportTranslationPrompt()

    uc = GenerateWeeklyReportUseCase(
        report_repo=repo,
        llm_service=llm,
        image_service=image,
        blob_storage=blob,
        translation_repository=translation_repo,
        translation_prompt=translation_prompt,
        email_notifier=email_notifier,
        telegram_notifier=telegram_notifier,
        translation_languages=translation_languages,
        cache_gateway=cache_gateway,
    )
    return uc, repo, llm, image, blob, translation_repo


def test_execute_returns_weekly_report():
    uc, _, _, _, _, _ = _make_uc()
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert isinstance(result, WeeklyReport)


def test_execute_uses_llm_title_and_summary():
    uc, _, _, _, _, _ = _make_uc(llm_response=json.dumps({"title": "LLM Title", "summary_text": "LLM Summary"}))
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.title == f"LLM Title ({WEEK_RANGE})"
    assert result.summary_text == "LLM Summary"


def test_execute_calls_image_generation():
    uc, _, _, image, _, _ = _make_uc()
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    image.generate_image.assert_called_once()


def test_execute_uploads_image_to_blob_storage():
    # image_service is a mock here — the use case doesn't re-encode, it trusts that whatever
    # ImageGenerationService.generate_image() returns is already WebP (every real provider routes
    # through image_encoding.encode_as_webp before returning; see their own unit tests).
    uc, _, _, _, blob, _ = _make_uc(image_bytes=b"webp-data")
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    blob.upload.assert_called_once()
    args = blob.upload.call_args[0]
    assert args[0] == b"webp-data"
    assert args[1].endswith(".webp")
    assert args[2] == "image/webp"


def test_execute_sets_cover_image_url():
    uc, _, _, _, _, _ = _make_uc(blob_url="https://r2.example.com/cover.webp")
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.cover_image_url == "https://r2.example.com/cover.webp"


def test_execute_saves_report_with_correct_article_count():
    articles = [_summary(f"Paper {i}") for i in range(3)]
    uc, repo, _, _, _, _ = _make_uc(articles=articles)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.article_count == 3


def test_execute_handles_empty_articles():
    uc, repo, llm, image, _, _ = _make_uc(articles=[])
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
    assert result.article_count == 0
    assert result.title == f"No Articles This Week ({WEEK_RANGE})"
    llm.generate.assert_not_called()
    image.generate_image.assert_not_called()


def test_execute_translates_the_empty_week_template_via_the_same_llm_translation_path():
    """No-article reports still go through _translate_report per configured language — the
    template isn't hardcoded per language, it's translated like any other report's title/summary."""
    uc, _, llm, _, _, translation_repo = _make_uc(articles=[], translation_languages=["zh-TW"])
    llm.translate.return_value = json.dumps({"title": "本週尚無文章", "summary_text": "本週該主題暫無發布文章。"})

    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)

    llm.translate.assert_called_once()
    saved = translation_repo.save.call_args[0][0]
    assert saved.title == f"本週尚無文章 ({WEEK_RANGE})"
    assert saved.summary_text == "本週該主題暫無發布文章。"
    assert result.article_count == 0


def test_execute_gracefully_handles_llm_failure():
    uc, _, llm, _, _, _ = _make_uc()
    llm.generate.side_effect = Exception("LLM timeout")
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
    assert TOPIC_NAME in result.title


def test_execute_gracefully_handles_image_failure():
    uc, _, _, image, _, _ = _make_uc()
    image.generate_image.side_effect = Exception("API error")
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"
    assert result.cover_image_url is None


def test_execute_notifies_email_when_provided():
    email = MagicMock()
    uc, _, _, _, _, _ = _make_uc(email_notifier=email)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    email.notify.assert_called_once()


def test_execute_notifies_telegram_when_provided():
    telegram = MagicMock()
    uc, _, _, _, _, _ = _make_uc(telegram_notifier=telegram)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    telegram.notify.assert_called_once()


def test_execute_does_not_fail_when_email_notifier_raises():
    email = MagicMock()
    email.notify.side_effect = Exception("SMTP error")
    uc, _, _, _, _, _ = _make_uc(email_notifier=email)
    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    assert result.status == "completed"


def test_execute_skips_regeneration_when_completed_report_exists():
    uc, repo, llm, image, _, _ = _make_uc()
    existing = WeeklyReport(
        id=uuid.uuid4(),
        topic_id=TOPIC_ID,
        week_start_date=WEEK_START,
        title="Existing Title",
        summary_text="Existing Summary",
        cover_image_url=None,
        article_ids=[],
        article_count=1,
        status="completed",
    )
    repo.find_by_topic_and_week.return_value = existing

    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)

    assert result is existing
    llm.generate.assert_not_called()
    image.generate_image.assert_not_called()
    repo.save.assert_not_called()


def test_execute_force_regenerates_even_when_completed_report_exists():
    uc, repo, llm, image, _, _ = _make_uc(llm_response=json.dumps({"title": "New Title", "summary_text": "New Summary"}))
    existing = WeeklyReport(
        id=uuid.uuid4(),
        topic_id=TOPIC_ID,
        week_start_date=WEEK_START,
        title="Existing Title",
        summary_text="Existing Summary",
        cover_image_url=None,
        article_ids=[],
        article_count=1,
        status="completed",
    )
    repo.find_by_topic_and_week.return_value = existing

    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START, force=True)

    assert result.title == f"New Title ({WEEK_RANGE})"
    llm.generate.assert_called_once()
    repo.save.assert_called_once()


# ── Citations: article_ids regression test (was populated with titles, now real UUIDs) ──

def test_execute_populates_article_ids_with_real_uuids_in_prompt_order():
    a1 = _summary("Paper A", article_id=uuid.uuid4())
    a2 = _summary("Paper B", article_id=uuid.uuid4())
    a3 = _summary("Paper C", article_id=uuid.uuid4())
    uc, repo, _, _, _, _ = _make_uc(articles=[a1, a2, a3])

    result = uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)

    assert result.article_ids == [str(a1.article_id), str(a2.article_id), str(a3.article_id)]
    # None of the stored ids are article titles (regression guard for the original bug)
    assert "Paper A" not in result.article_ids


# ── Translation citation preservation (FR-026) ──

def test_translate_report_falls_back_to_english_summary_when_citations_mismatch():
    uc, _, llm, _, _, translation_repo = _make_uc(translation_languages=["zh-TW"])
    original_summary = "AI models improved this week [1], and infra advanced too [2]."
    report = WeeklyReport(
        id=uuid.uuid4(),
        topic_id=TOPIC_ID,
        week_start_date=WEEK_START,
        title="AI Week",
        summary_text=original_summary,
        cover_image_url=None,
        article_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
        article_count=2,
        status="completed",
    )
    # Translated response drops citation [2] — should trigger the fallback.
    llm.translate.return_value = json.dumps({
        "title": "AI 週報",
        "summary_text": "AI 模型本週有所改進 [1]，基礎設施也有進步。",
    })

    uc._translate_report(report, "zh-TW")

    saved = translation_repo.save.call_args[0][0]
    assert saved.title == f"AI 週報 ({WEEK_RANGE})"
    assert saved.summary_text == original_summary


def test_translate_report_strips_week_range_before_sending_title_to_llm():
    """report.title already carries the '(YYYY/MM/DD–YYYY/MM/DD)' suffix — the translation LLM should
    only see the headline, since re-translating the date range risks reformatting it inconsistently."""
    uc, _, llm, _, _, _ = _make_uc(translation_languages=["zh-TW"])
    report = WeeklyReport(
        id=uuid.uuid4(),
        topic_id=TOPIC_ID,
        week_start_date=WEEK_START,
        title=f"AI Week ({WEEK_RANGE})",
        summary_text="AI models improved this week [1].",
        cover_image_url=None,
        article_ids=[str(uuid.uuid4())],
        article_count=1,
        status="completed",
    )
    llm.translate.return_value = json.dumps({"title": "AI 週報", "summary_text": "AI 模型本週有所改進 [1]。"})

    uc._translate_report(report, "zh-TW")

    sent_prompt = llm.translate.call_args[0][1]
    assert WEEK_RANGE not in sent_prompt
    assert "AI Week" in sent_prompt


def test_translate_report_keeps_translation_when_citations_match():
    uc, _, llm, _, _, translation_repo = _make_uc(translation_languages=["zh-TW"])
    report = WeeklyReport(
        id=uuid.uuid4(),
        topic_id=TOPIC_ID,
        week_start_date=WEEK_START,
        title="AI Week",
        summary_text="AI models improved this week [1].",
        cover_image_url=None,
        article_ids=[str(uuid.uuid4())],
        article_count=1,
        status="completed",
    )
    translated_summary = "AI 模型本週有所改進 [1]。"
    llm.translate.return_value = json.dumps({"title": "AI 週報", "summary_text": translated_summary})

    uc._translate_report(report, "zh-TW")

    saved = translation_repo.save.call_args[0][0]
    assert saved.summary_text == translated_summary


# ---------------------------------------------------------------------------
# Cache invalidation (020-redis-caching-layer, US3)
# ---------------------------------------------------------------------------

def test_execute_bumps_weekly_reports_cache_when_report_saved():
    from unittest.mock import MagicMock

    cache = MagicMock()
    uc, _, _, _, _, _ = _make_uc(cache_gateway=cache)
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    cache.bump_version.assert_called_once_with("weekly_reports")
    cache.publish_warmup_signal.assert_called_once_with(reason="weekly_report")


def test_execute_bumps_weekly_reports_cache_for_empty_week():
    from unittest.mock import MagicMock

    cache = MagicMock()
    uc, _, _, _, _, _ = _make_uc(articles=[], cache_gateway=cache)
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)
    cache.bump_version.assert_called_once_with("weekly_reports")
    cache.publish_warmup_signal.assert_called_once_with(reason="weekly_report")


def test_execute_does_not_bump_cache_when_no_gateway_configured():
    uc, _, _, _, _, _ = _make_uc(cache_gateway=None)
    # Should not raise — cache_gateway=None is the default, matching every other
    # existing test in this file that doesn't pass one.
    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)


def test_execute_does_not_bump_cache_when_regeneration_skipped():
    from unittest.mock import MagicMock

    cache = MagicMock()
    uc, repo, _, _, _, _ = _make_uc(cache_gateway=cache)
    existing = WeeklyReport(
        id=uuid.uuid4(),
        topic_id=TOPIC_ID,
        week_start_date=WEEK_START,
        title="Existing Title",
        summary_text="Existing Summary",
        cover_image_url=None,
        article_ids=[],
        article_count=1,
        status="completed",
    )
    repo.find_by_topic_and_week.return_value = existing

    uc.execute(TOPIC_ID, TOPIC_NAME, WEEK_START)

    cache.bump_version.assert_not_called()
    cache.publish_warmup_signal.assert_not_called()
