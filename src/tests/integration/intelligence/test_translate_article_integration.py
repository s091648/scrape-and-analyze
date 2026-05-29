"""
Integration tests for translation repository — covers exists, save/upsert,
and find_analyses_without_translation dedup queries.

Requires running PostgreSQL (make test-integration).
"""
import uuid

import pytest

from models.analyses_translation import AnalysesTranslation
from models.analysis import Analysis
from models.article import Article
from src.infrastructure.persistence.intelligence.analyses_translation_repo_impl import (
    SqlAlchemyAnalysesTranslationRepository,
)


@pytest.mark.integration
@pytest.fixture
def translation_repo(db_session):
    return SqlAlchemyAnalysesTranslationRepository(db_session)


@pytest.mark.integration
@pytest.fixture
def analysis_with_en_translation(db_session, tag_group):
    """Create an Article + Analysis + English AnalysesTranslation row."""
    from models.tag_group import TagGroupDefinition

    article = Article(
        url=f"https://example.com/integration-{uuid.uuid4()}",
        url_hash=uuid.uuid4().hex,
        source="rss",
        title="Integration Test Article",
        content="Test content",
    )
    db_session.add(article)
    db_session.flush()

    analysis = Analysis(
        article_id=article.id,
        tag_group_name=tag_group.name,
        language="en",
    )
    db_session.add(analysis)
    db_session.flush()

    en_translation = AnalysesTranslation(
        analysis_id=analysis.id,
        language="en",
        summary="English summary",
        pain_points="English pain",
        insights="English insight",
        innovations="English innovation",
    )
    db_session.add(en_translation)
    db_session.flush()

    return {
        "article": article,
        "analysis": analysis,
        "en_translation": en_translation,
    }


# ── exists() returns False for new pair, True after save ────────────────────

@pytest.mark.integration
def test_exists_returns_false_for_new_pair(db_session, translation_repo, tag_group):
    aid = uuid.uuid4()
    assert translation_repo.exists(aid, "zh-TW") is False


@pytest.mark.integration
def test_exists_returns_true_after_save(db_session, translation_repo, analysis_with_en_translation):
    aid = analysis_with_en_translation["analysis"].id
    from src.modules.intelligence.domain.entities import AnalysesContent

    content = AnalysesContent(
        analysis_id=aid,
        language="zh-TW",
        summary="翻譯摘要",
        pain_points="翻譯痛點",
        insights="翻譯洞察",
        innovations="翻譯創新",
    )
    translation_repo.save(content)

    assert translation_repo.exists(aid, "zh-TW") is True


# ── save() upserts: second save with same (analysis_id, language) updates ───

@pytest.mark.integration
def test_save_upserts_on_same_analysis_and_language(db_session, translation_repo, analysis_with_en_translation):
    aid = analysis_with_en_translation["analysis"].id
    from src.modules.intelligence.domain.entities import AnalysesContent

    content_v1 = AnalysesContent(
        analysis_id=aid, language="zh-TW",
        summary="版本一", pain_points="p1", insights="i1", innovations="n1",
    )
    translation_repo.save(content_v1)

    content_v2 = AnalysesContent(
        analysis_id=aid, language="zh-TW",
        summary="版本二", pain_points="p2", insights="i2", innovations="n2",
    )
    translation_repo.save(content_v2)

    result = translation_repo.find_by_analysis_id_and_language(aid, "zh-TW")
    assert result.summary == "版本二"
    assert result.pain_points == "p2"

    # Only one row for this (analysis_id, language)
    count = db_session.query(AnalysesTranslation).filter_by(
        analysis_id=aid, language="zh-TW"
    ).count()
    assert count == 1


# ── find_analyses_without_translation excludes already-translated ────────────

@pytest.mark.integration
def test_find_without_translation_excludes_translated(db_session, translation_repo, analysis_with_en_translation):
    aid = analysis_with_en_translation["analysis"].id
    from src.modules.intelligence.domain.entities import AnalysesContent

    # Before translation, analysis should appear
    results = translation_repo.find_analyses_without_translation("zh-TW", limit=10)
    analysis_ids = [r["analysis_id"] for r in results]
    assert aid in analysis_ids

    # After creating zh-TW translation, analysis should NOT appear
    content = AnalysesContent(
        analysis_id=aid, language="zh-TW",
        summary="翻譯", pain_points="p", insights="i", innovations="n",
    )
    translation_repo.save(content)

    results = translation_repo.find_analyses_without_translation("zh-TW", limit=10)
    analysis_ids = [r["analysis_id"] for r in results]
    assert aid not in analysis_ids
