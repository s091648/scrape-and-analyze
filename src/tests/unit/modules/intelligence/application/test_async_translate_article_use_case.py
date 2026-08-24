"""
Unit tests for AsyncTranslateArticleUseCase — async sibling of
TranslateArticleUseCase (024-async-pipeline-refactor). Mirrors
test_translate_article_use_case.py's coverage, adapted for the
async/await call path. _parse_sections is shared (delegated to the sync
class as a staticmethod) so it isn't re-tested here.
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from src.modules.intelligence.application.use_cases.translate_article import AsyncTranslateArticleUseCase
from src.modules.intelligence.domain.entities import AnalysesContent
from src.modules.intelligence.domain.value_objects import ArticleTranslationPrompt


@pytest.fixture
def deps():
    llm_service = AsyncMock()
    repo = AsyncMock()
    prompt = ArticleTranslationPrompt()
    return {
        "llm_service": llm_service,
        "translation_repository": repo,
        "prompt": prompt,
    }


def _make_uc(deps):
    return AsyncTranslateArticleUseCase(
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

@pytest.mark.asyncio
async def test_returns_existing_translation_when_already_exists(deps):
    existing = _fake_existing_translation()
    deps["translation_repository"].exists.return_value = True
    deps["translation_repository"].find_by_analysis_id_and_language.return_value = existing
    uc = _make_uc(deps)

    result = await uc.execute(
        analysis_id=existing.analysis_id, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is True
    assert result.content.summary == "existing_s"
    deps["llm_service"].translate.assert_not_awaited()


# ── LLM call + parse + save: success path ───────────────────────────────────

@pytest.mark.asyncio
async def test_calls_llm_and_parses_and_saves_when_no_existing(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = (
        "Summary: translated s\n\nPain Points: translated p\n\n"
        "Insights: translated i\n\nInnovations: translated n"
    )
    uc = _make_uc(deps)

    result = await uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is True
    assert result.content.summary == "translated s"
    assert result.content.pain_points == "translated p"
    assert result.content.insights == "translated i"
    assert result.content.innovations == "translated n"
    deps["llm_service"].translate.assert_awaited_once()
    deps["translation_repository"].save.assert_awaited_once()


# ── LLM returns None: failure result ────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_llm_returns_none(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = None
    uc = _make_uc(deps)

    result = await uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.summary is None
    assert result.content.pain_points is None
    assert result.content.insights is None
    assert result.content.innovations is None


# ── Save failure: returns failure ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_save_raises(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = (
        "Summary: s\n\nPain Points: p\n\nInsights: i\n\nInnovations: n"
    )
    deps["translation_repository"].save.side_effect = Exception("db error")
    uc = _make_uc(deps)

    result = await uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.summary is None


# ── Empty field substitution: "(empty)" ─────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_fields_substituted_with_empty_string_in_prompt(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.return_value = (
        "Summary: s\n\nPain Points: p\n\nInsights: i\n\nInnovations: n"
    )
    uc = _make_uc(deps)

    await uc.execute(
        analysis_id=aid, summary=None, pain_points=None,
        insights=None, innovations=None, target_language="zh-TW"
    )

    call_args = deps["llm_service"].translate.call_args
    prompt_content = call_args[0][1]
    assert "(empty)" in prompt_content


# ── LLM exception: returns failure ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_llm_throws_exception(deps):
    aid = _analysis_id()
    deps["translation_repository"].exists.return_value = False
    deps["llm_service"].translate.side_effect = Exception("provider down")
    uc = _make_uc(deps)

    result = await uc.execute(
        analysis_id=aid, summary="s", pain_points="p",
        insights="i", innovations="n", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.summary is None
