"""
Unit tests for TranslateArticleUseCase — covers dedup, LLM call,
response parsing, failure handling, and empty field substitution.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.modules.intelligence.application.use_cases.translate_article import TranslateArticleUseCase
from src.modules.intelligence.domain.entities import AnalysesContent
from src.modules.intelligence.domain.value_objects import (
    AnalysesTranslationContent,
    AnalysesTranslationResult,
    ArticleTranslationPrompt,
)


@pytest.fixture
def deps():
    llm_service = MagicMock()
    repo = MagicMock()
    prompt = ArticleTranslationPrompt()
    return {
        "llm_service": llm_service,
        "translation_repository": repo,
        "prompt": prompt,
    }


def _make_uc(deps):
    return TranslateArticleUseCase(
        llm_service=deps["llm_service"],
        translation_repository=deps["translation_repository"],
        prompt=deps["prompt"],
    )


def _analysis_id():
    return uuid.uuid4()


def _fake_existing_translation(summary="existing_s", pain_points="existing_p",
                                insights="existing_i", innovations="existing_n"):
    return AnalysesContent(
        analysis_id=uuid.uuid4(),
        language="zh-TW",
        summary=summary,
        pain_points=pain_points,
        insights=insights,
        innovations=innovations,
    )


# ── Dedup: returns existing translation without calling LLM ──────────────────

def test_returns_existing_translation_when_already_exists(deps):
    existing = _fake_existing_translation()
    deps["translation_repository"].exists.return_value = True
    deps["translation_repository"].find_by_analysis_id_and_language.return_value = existing
    uc = _make_uc(deps)

    result = uc.execute(
        analysis_id=existing.analysis_id, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is True
    assert result.content.summary == "existing_s"
    deps["llm_service"].translate.assert_not_called()


# ── LLM call + parse + save: success path ───────────────────────────────────

def test_calls_llm_and_parses_and_saves_when_no_existing(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = (
        "Summary: translated s\n\nPain Points: translated p\n\n"
        "Insights: translated i\n\nInnovations: translated n"
    )
    uc = _make_uc(deps)

    result = uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is True
    assert result.content.summary == "translated s"
    assert result.content.pain_points == "translated p"
    assert result.content.insights == "translated i"
    assert result.content.innovations == "translated n"
    deps["llm_service"].translate.assert_called_once()
    deps["translation_repository"].save.assert_called_once()


# ── LLM returns None: failure result ────────────────────────────────────────

def test_returns_failure_when_llm_returns_none(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = None
    uc = _make_uc(deps)

    result = uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.summary is None
    assert result.content.pain_points is None
    assert result.content.insights is None
    assert result.content.innovations is None


# ── Save failure: returns failure ───────────────────────────────────────────

def test_returns_failure_when_save_raises(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = (
        "Summary: s\n\nPain Points: p\n\nInsights: i\n\nInnovations: n"
    )
    deps["translation_repository"].save.side_effect = Exception("db error")
    uc = _make_uc(deps)

    result = uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.summary is None


# ── _parse_sections: various formats ─────────────────────────────────────────

def test_parse_sections_handles_full_response():
    text = "Summary: The summary\n\nPain Points: The pains\n\nInsights: The insights\n\nInnovations: The innovations"
    result = TranslateArticleUseCase._parse_sections(text)
    assert result.summary == "The summary"
    assert result.pain_points == "The pains"
    assert result.insights == "The insights"
    assert result.innovations == "The innovations"


def test_parse_sections_handles_missing_sections():
    text = "Summary: Only a summary"
    result = TranslateArticleUseCase._parse_sections(text)
    assert result.summary == "Only a summary"
    assert result.pain_points == ""
    assert result.insights == ""
    assert result.innovations == ""


def test_parse_sections_handles_full_width_colons():
    text = "Summary：Full-width colon\nPain Points：Also full-width"
    result = TranslateArticleUseCase._parse_sections(text)
    assert result.summary == "Full-width colon"
    assert result.pain_points == "Also full-width"


def test_parse_sections_case_insensitive_headers():
    text = "SUMMARY: Uppercase\npain points: Lowercase\nInsights: Mixed\nINNOVATIONS: All caps"
    result = TranslateArticleUseCase._parse_sections(text)
    assert result.summary == "Uppercase"
    assert result.pain_points == "Lowercase"
    assert result.insights == "Mixed"
    assert result.innovations == "All caps"


# ── Empty field substitution: "(empty)" ─────────────────────────────────────

def test_empty_fields_substituted_with_empty_string_in_prompt(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = (
        "Summary: s\n\nPain Points: p\n\nInsights: i\n\nInnovations: n"
    )
    uc = _make_uc(deps)

    uc.execute(
        analysis_id=aid, summary=None, pain_points=None,
        insights=None, innovations=None, target_language="zh-TW"
    )

    call_args = deps["llm_service"].translate.call_args
    prompt_content = call_args[0][1]
    assert "(empty)" in prompt_content


# ── LLM exception: returns failure ──────────────────────────────────────────

def test_returns_failure_when_llm_throws_exception(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.side_effect = Exception("provider down")
    uc = _make_uc(deps)

    result = uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.summary is None
