import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.integration


def _make_article(topic_id):
    from src.shared.domain.entities import Article
    from src.modules.collection.domain.value_objects import UrlHash

    url = f"https://example.com/{uuid.uuid4()}"
    return Article(
        url=url,
        url_hash=UrlHash.from_url(url).value,
        source="rss",
        title="Async repo test article",
        content="body",
        published_at=datetime.now(timezone.utc),
        topic_id=topic_id,
    )


@pytest.mark.asyncio
async def test_async_article_repository_save_find_has_analysis(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository

    repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    article = _make_article(test_topic)

    saved = await repo.save(article)
    await async_db_session.commit()
    assert saved.id is not None

    found = await repo.find_by_url_hash(article.url_hash)
    assert found is not None
    assert found.id == saved.id

    assert await repo.has_analysis(saved.id) is False


@pytest.mark.asyncio
async def test_async_article_metrics_repository_upsert(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.collection.article_metrics_async_repo_impl import AsyncSqlAlchemyArticleMetricsRepository
    from sqlalchemy import text

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    metrics_repo = AsyncSqlAlchemyArticleMetricsRepository(async_db_session)
    await metrics_repo.upsert(saved.id, {"citation_count": 5})

    row = (await async_db_session.execute(
        text("SELECT value FROM article_metric_values WHERE article_id = :aid AND metric_key = 'citation_count'"),
        {"aid": str(saved.id)},
    )).first()
    assert row is not None
    assert row[0] == "5" or row[0] == 5 or float(row[0]) == 5.0


@pytest.mark.asyncio
async def test_async_topic_repository_list_and_find(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.topic_async_repo_impl import AsyncSqlAlchemyTopicRepository

    repo = AsyncSqlAlchemyTopicRepository(async_db_session)

    found = await repo.find_by_id(test_topic)
    assert found is not None
    assert found.id == test_topic

    active = await repo.list_active()
    assert any(t.id == test_topic for t in active)


@pytest.mark.asyncio
async def test_async_failed_task_repository_save(async_db_session):
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
    from src.modules.collection.domain.entities import FailedTask

    repo = AsyncSqlAlchemyFailedTaskRepository(async_db_session)
    task = FailedTask(
        task_type="analyze",
        exception_type="RuntimeError",
        exception_message="boom",
        failed_at=datetime.now(timezone.utc),
    )
    await repo.save(task)

    from sqlalchemy import text
    row = (await async_db_session.execute(
        text("SELECT task_type FROM failed_tasks WHERE id = :tid"), {"tid": str(task.id)}
    )).first()
    assert row is not None
    assert row[0] == "analyze"


@pytest.mark.asyncio
async def test_async_analysis_and_translation_repositories_save_and_find(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.intelligence.analyses_translation_async_repo_impl import AsyncSqlAlchemyAnalysesTranslationRepository
    from src.modules.intelligence.domain.entities import Analysis, AnalysesContent
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved_article = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    analysis_repo = AsyncSqlAlchemyAnalysisRepository(async_db_session)
    analysis = Analysis(
        article_id=saved_article.id,
        analysis_content=AnalysisContent(
            summary="s", pain_points="p", insights="i", innovations="n", tag_groups=None,
        ),
        analysis_metadata=AnalysisMetadata(model_used="test-model", input_tokens=1, output_tokens=1),
    )
    await analysis_repo.save(analysis)
    assert analysis.id is not None

    translation_repo = AsyncSqlAlchemyAnalysesTranslationRepository(async_db_session)
    assert await translation_repo.exists(analysis.id, "zh-TW") is False

    content = AnalysesContent(
        id=None, analysis_id=analysis.id, language="zh-TW",
        summary="摘要", pain_points="p", insights="i", innovations="n",
        created_at=None, updated_at=None,
    )
    await translation_repo.save(content)

    assert await translation_repo.exists(analysis.id, "zh-TW") is True
    found = await translation_repo.find_by_analysis_id_and_language(analysis.id, "zh-TW")
    assert found is not None
    assert found.summary == "摘要"


@pytest.mark.asyncio
async def test_async_article_translation_repository_save_find_exists(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.article_translation_async_repo_impl import AsyncSqlAlchemyArticleTranslationRepository

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    repo = AsyncSqlAlchemyArticleTranslationRepository(async_db_session)
    assert await repo.exists(saved.id, "zh-TW") is False

    await repo.save(saved.id, "zh-TW", "標題", "內文")

    assert await repo.exists(saved.id, "zh-TW") is True
    found = await repo.find_by_article_id_and_language(saved.id, "zh-TW")
    assert found is not None
    assert found.title == "標題"


@pytest.mark.asyncio
async def test_async_tag_group_definition_repository_upsert_and_find(async_db_session, test_topic):
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import AsyncSqlAlchemyTagGroupDefinitionRepository

    repo = AsyncSqlAlchemyTagGroupDefinitionRepository(async_db_session)
    name = f"async-test-group-{uuid.uuid4().hex[:8]}"

    await repo.upsert(name=name, display_name="Async Test Group", topic_id=test_topic)
    await async_db_session.commit()

    groups = await repo.find_by_topic_id(test_topic)
    assert any(g.name == name for g in groups)


@pytest.mark.asyncio
async def test_async_tag_repository_save_link_and_find_similar(async_db_session, tag_group):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved_article = await article_repo.save(_make_article(tag_group.topic_id))
    await async_db_session.commit()

    tag_repo = AsyncSqlAlchemyTagRepository(async_db_session)
    embedding = [0.1] * 768
    tag = await tag_repo.save(
        name=f"async-tag-{uuid.uuid4().hex[:8]}",
        tag_group_name=tag_group.name,
        embedding=embedding,
        topic_id=tag_group.topic_id,
    )
    await tag_repo.commit()
    assert tag.id is not None

    await tag_repo.link_to_article(tag.id, saved_article.id)
    await tag_repo.commit()

    similar = await tag_repo.find_similar(embedding, tag_group.name, tag_group.topic_id, threshold=0.99)
    assert any(t.id == tag.id for t, _score in similar)


@pytest.mark.asyncio
async def test_async_tag_translation_repository_save_and_find_without_translation(async_db_session, tag_group):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from src.infrastructure.persistence.intelligence.tag_translation_async_repo_impl import AsyncSqlAlchemyTagTranslationRepository

    tag_repo = AsyncSqlAlchemyTagRepository(async_db_session)
    tag = await tag_repo.save(
        name=f"async-tag-tr-{uuid.uuid4().hex[:8]}",
        tag_group_name=tag_group.name,
        embedding=[0.2] * 768,
        topic_id=tag_group.topic_id,
    )
    await tag_repo.commit()

    translation_repo = AsyncSqlAlchemyTagTranslationRepository(async_db_session)
    without = await translation_repo.find_tags_without_translation("zh-TW", limit=50)
    assert any(t["tag_id"] == tag.id for t in without)

    await translation_repo.save_tag_translation(tag.id, "zh-TW", "測試標籤")

    without_after = await translation_repo.find_tags_without_translation("zh-TW", limit=50)
    assert all(t["tag_id"] != tag.id for t in without_after)
