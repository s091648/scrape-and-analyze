"""
Integration tests for SqlAlchemyArticleTranslationRepository — covers exists,
save/upsert, find_articles_without_translation dedup, and end-to-end
TranslateArticleBodyUseCase with a real DB.

Requires running PostgreSQL (make test-integration).
"""
import uuid
from unittest.mock import MagicMock

import pytest

from models.article import Article
from models.article_translation import ArticleTranslation
from src.infrastructure.persistence.intelligence.article_translation_repo_impl import (
    SqlAlchemyArticleTranslationRepository,
)


@pytest.fixture
def translation_repo(db_session):
    return SqlAlchemyArticleTranslationRepository(db_session)


@pytest.fixture
def article(db_session):
    """Create a minimal Article row for body translation tests."""
    a = Article(
        url=f"https://example.com/body-test-{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        source="rss",
        title="Integration Test Article for Body Translation",
        content="This is the test article content.",
        correlation_id=uuid.uuid4(),
    )
    db_session.add(a)
    db_session.flush()
    return a


# ── T049: exists() returns False for new pair, True after save ───────────────

@pytest.mark.integration
def test_exists_returns_false_for_unknown_article(db_session, translation_repo, tag_group):
    assert translation_repo.exists(uuid.uuid4(), "zh-TW") is False


@pytest.mark.integration
def test_exists_returns_true_after_save(db_session, translation_repo, article, tag_group):
    translation_repo.save(
        article_id=article.id,
        language="zh-TW",
        title="翻譯標題",
        content="翻譯內容",
    )
    assert translation_repo.exists(article.id, "zh-TW") is True


# ── T050: save() upserts — second save with same (article_id, language) ──────

@pytest.mark.integration
def test_save_upserts_on_same_article_and_language(db_session, translation_repo, article, tag_group):
    translation_repo.save(
        article_id=article.id, language="zh-TW",
        title="版本一標題", content="版本一內容",
    )
    translation_repo.save(
        article_id=article.id, language="zh-TW",
        title="版本二標題", content="版本二內容",
    )

    result = translation_repo.find_by_article_id_and_language(article.id, "zh-TW")
    assert result is not None
    assert result.title == "版本二標題"
    assert result.content == "版本二內容"

    count = db_session.query(ArticleTranslation).filter_by(
        article_id=article.id, language="zh-TW"
    ).count()
    assert count == 1


# ── T051: find_articles_without_translation excludes already-translated ───────

@pytest.mark.integration
def test_find_without_translation_includes_untranslated(db_session, translation_repo, article, tag_group):
    results = translation_repo.find_articles_without_translation("zh-TW", limit=100)
    article_ids = [r["article_id"] for r in results]
    assert article.id in article_ids


@pytest.mark.integration
def test_find_without_translation_excludes_already_translated(db_session, translation_repo, article, tag_group):
    translation_repo.save(
        article_id=article.id, language="zh-TW",
        title="已翻譯", content="已翻譯內容",
    )

    results = translation_repo.find_articles_without_translation("zh-TW", limit=100)
    article_ids = [r["article_id"] for r in results]
    assert article.id not in article_ids


@pytest.mark.integration
def test_find_without_translation_respects_language_boundary(db_session, translation_repo, article, tag_group):
    translation_repo.save(
        article_id=article.id, language="ja",
        title="日本語タイトル", content="日本語コンテンツ",
    )

    # zh-TW still missing — should appear
    results = translation_repo.find_articles_without_translation("zh-TW", limit=100)
    article_ids = [r["article_id"] for r in results]
    assert article.id in article_ids


# ── T055: end-to-end TranslateArticleBodyUseCase with real DB ────────────────

@pytest.mark.integration
def test_translate_article_body_use_case_end_to_end(db_session, translation_repo, article, tag_group):
    from src.modules.intelligence.application.use_cases.translate_article_body import TranslateArticleBodyUseCase
    from src.modules.intelligence.domain.value_objects.translation_prompt import ArticleBodyTranslationPrompt

    mock_llm = MagicMock()
    mock_llm.translate.return_value = "Title: 翻譯後標題\nContent: 翻譯後內文。"

    uc = TranslateArticleBodyUseCase(
        llm_service=mock_llm,
        translation_repository=translation_repo,
        prompt=ArticleBodyTranslationPrompt(),
    )

    result = uc.execute(
        article_id=article.id,
        title=article.title,
        content=article.content,
        target_language="zh-TW",
    )

    assert result.success is True
    assert result.content.title == "翻譯後標題"
    assert result.content.content == "翻譯後內文。"

    # Verify DB row exists
    row = db_session.query(ArticleTranslation).filter_by(
        article_id=article.id, language="zh-TW"
    ).first()
    assert row is not None
    assert row.title == "翻譯後標題"


@pytest.mark.integration
def test_translate_article_body_use_case_dedup_skips_llm(db_session, translation_repo, article, tag_group):
    from src.modules.intelligence.application.use_cases.translate_article_body import TranslateArticleBodyUseCase
    from src.modules.intelligence.domain.value_objects.translation_prompt import ArticleBodyTranslationPrompt

    translation_repo.save(
        article_id=article.id, language="zh-TW",
        title="已存在翻譯", content="已存在內容",
    )

    mock_llm = MagicMock()
    uc = TranslateArticleBodyUseCase(
        llm_service=mock_llm,
        translation_repository=translation_repo,
        prompt=ArticleBodyTranslationPrompt(),
    )

    result = uc.execute(
        article_id=article.id,
        title=article.title,
        content=article.content,
        target_language="zh-TW",
    )

    assert result.success is True
    mock_llm.translate.assert_not_called()
