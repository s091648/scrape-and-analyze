"""
Unit tests for AsyncTranslateArticleBodyUseCase — async sibling of
TranslateArticleBodyUseCase (024-async-pipeline-refactor). Mirrors
test_translate_article_body_use_case.py's coverage, adapted for the
async/await call path, plus a parse-failure case not covered there.
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from src.modules.intelligence.application.use_cases.translate_article_body import AsyncTranslateArticleBodyUseCase
from src.modules.intelligence.domain.value_objects.translation_prompt import ArticleBodyTranslationPrompt
from src.modules.intelligence.domain.value_objects.analyses_translation_content import ArticleBodyTranslationContent


def _make_uc(repo=None, llm=None):
    if llm is None:
        llm = AsyncMock()
    if repo is None:
        repo = AsyncMock()
        repo.exists.return_value = False
    return AsyncTranslateArticleBodyUseCase(
        llm_service=llm,
        translation_repository=repo,
        prompt=ArticleBodyTranslationPrompt(),
    ), repo, llm


# ── Dedup: returns existing translation without calling LLM ──────────────────

@pytest.mark.asyncio
async def test_returns_existing_when_already_translated():
    repo = AsyncMock()
    repo.exists.return_value = True
    repo.find_by_article_id_and_language.return_value = ArticleBodyTranslationContent(
        title="已翻譯標題", content="已翻譯內容"
    )
    uc, _, llm = _make_uc(repo=repo)

    result = await uc.execute(
        article_id=uuid.uuid4(), title="Original", content="Content",
        target_language="zh-TW"
    )

    assert result.success is True
    assert result.content.title == "已翻譯標題"
    llm.translate.assert_not_awaited()


# ── LLM call + parse + save: success path ───────────────────────────────────

@pytest.mark.asyncio
async def test_calls_llm_parses_and_saves_on_success():
    article_id = uuid.uuid4()
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: Translated Title\nContent: Translated body text."

    result = await uc.execute(
        article_id=article_id,
        title="Original Title",
        content="Original content.",
        target_language="zh-TW",
    )

    assert result.success is True
    assert result.content.title == "Translated Title"
    assert result.content.content == "Translated body text."
    llm.translate.assert_awaited_once()
    repo.save.assert_awaited_once_with(
        article_id=article_id,
        language="zh-TW",
        title="Translated Title",
        content="Translated body text.",
    )


# ── LLM returns None: failure ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_llm_returns_none():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = None

    result = await uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.title is None
    assert result.content.content is None
    repo.save.assert_not_awaited()


# ── Parse failure (no recognizable headers): failure ─────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_response_has_no_parseable_sections():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "gibberish with no section headers at all"

    result = await uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.title is None
    assert result.content.content is None
    repo.save.assert_not_awaited()


# ── Empty content substituted with "(empty)" ─────────────────────────────────

@pytest.mark.asyncio
async def test_empty_title_and_content_substituted_with_empty_placeholder():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: t\nContent: c"

    await uc.execute(article_id=uuid.uuid4(), title="", content="", target_language="zh-TW")

    call_args = llm.translate.call_args
    prompt_content = call_args[0][1]
    assert "(empty)" in prompt_content


@pytest.mark.asyncio
async def test_none_title_and_content_substituted_with_empty_placeholder():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: t\nContent: c"

    await uc.execute(article_id=uuid.uuid4(), title=None, content=None, target_language="zh-TW")

    call_args = llm.translate.call_args
    prompt_content = call_args[0][1]
    assert "(empty)" in prompt_content


# ── Save raises: failure ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_save_raises():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: t\nContent: c"
    repo.save.side_effect = Exception("db error")

    result = await uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.title is None


# ── LLM raises exception: failure ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_failure_when_llm_throws_exception():
    uc, repo, llm = _make_uc()
    llm.translate.side_effect = RuntimeError("provider down")

    result = await uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    repo.save.assert_not_awaited()
