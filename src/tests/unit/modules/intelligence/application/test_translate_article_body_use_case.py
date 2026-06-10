"""
Unit tests for TranslateArticleBodyUseCase — covers dedup, LLM call,
response parsing, failure handling, and empty field substitution.
"""
import uuid
from unittest.mock import MagicMock, call

from src.modules.intelligence.application.use_cases.translate_article_body import TranslateArticleBodyUseCase
from src.modules.intelligence.domain.value_objects.translation_prompt import ArticleBodyTranslationPrompt
from src.modules.intelligence.domain.value_objects.analyses_translation_content import ArticleBodyTranslationContent


def _make_uc(repo=None, llm=None):
    if llm is None:
        llm = MagicMock()
    if repo is None:
        repo = MagicMock()
        repo.exists.return_value = False
    return TranslateArticleBodyUseCase(
        llm_service=llm,
        translation_repository=repo,
        prompt=ArticleBodyTranslationPrompt(),
    ), repo, llm


# ── Dedup: returns existing translation without calling LLM ──────────────────

def test_returns_existing_when_already_translated():
    repo = MagicMock()
    repo.exists.return_value = True
    repo.find_by_article_id_and_language.return_value = ArticleBodyTranslationContent(
        title="已翻譯標題", content="已翻譯內容"
    )
    uc, _, llm = _make_uc(repo=repo)

    result = uc.execute(
        article_id=uuid.uuid4(), title="Original", content="Content",
        target_language="zh-TW"
    )

    assert result.success is True
    assert result.content.title == "已翻譯標題"
    llm.translate.assert_not_called()


# ── LLM call + parse + save: success path ───────────────────────────────────

def test_calls_llm_parses_and_saves_on_success():
    article_id = uuid.uuid4()
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: Translated Title\nContent: Translated body text."

    result = uc.execute(
        article_id=article_id,
        title="Original Title",
        content="Original content.",
        target_language="zh-TW",
    )

    assert result.success is True
    assert result.content.title == "Translated Title"
    assert result.content.content == "Translated body text."
    llm.translate.assert_called_once()
    repo.save.assert_called_once_with(
        article_id=article_id,
        language="zh-TW",
        title="Translated Title",
        content="Translated body text.",
    )


# ── LLM returns None: failure ────────────────────────────────────────────────

def test_returns_failure_when_llm_returns_none():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = None

    result = uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.title is None
    assert result.content.content is None
    repo.save.assert_not_called()


# ── Empty content substituted with "(empty)" ─────────────────────────────────

def test_empty_title_and_content_substituted_with_empty_placeholder():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: t\nContent: c"

    uc.execute(article_id=uuid.uuid4(), title="", content="", target_language="zh-TW")

    call_args = llm.translate.call_args
    prompt_content = call_args[0][1]
    assert "(empty)" in prompt_content


def test_none_title_and_content_substituted_with_empty_placeholder():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: t\nContent: c"

    uc.execute(article_id=uuid.uuid4(), title=None, content=None, target_language="zh-TW")

    call_args = llm.translate.call_args
    prompt_content = call_args[0][1]
    assert "(empty)" in prompt_content


# ── Save raises: failure ─────────────────────────────────────────────────────

def test_returns_failure_when_save_raises():
    uc, repo, llm = _make_uc()
    llm.translate.return_value = "Title: t\nContent: c"
    repo.save.side_effect = Exception("db error")

    result = uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    assert result.content.title is None


# ── LLM raises exception: failure ────────────────────────────────────────────

def test_returns_failure_when_llm_throws_exception():
    uc, repo, llm = _make_uc()
    llm.translate.side_effect = RuntimeError("provider down")

    result = uc.execute(
        article_id=uuid.uuid4(), title="t", content="c", target_language="zh-TW"
    )

    assert result.success is False
    repo.save.assert_not_called()
