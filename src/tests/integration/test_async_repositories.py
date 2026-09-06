import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

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
async def test_async_failed_task_repository_save_many_persists_all_rows_in_one_commit(async_db_session):
    """fix/scraper_failure: the RAG circuit breaker queues one FailedTask per
    skipped article and flushes them in a single bulk write at run end, rather
    than a per-article session/commit."""
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
    from src.modules.collection.domain.entities import FailedTask
    from sqlalchemy import text

    repo = AsyncSqlAlchemyFailedTaskRepository(async_db_session)
    tasks = [
        FailedTask(
            task_type="rag_ingest",
            article_url=f"https://example.com/bulk/{i}",
            exception_type="RateLimitExhausted",
            exception_message="RAG daily request cap (RPD) already exhausted this run",
            context={"deferred": True, "reason": "RateLimitExhausted"},
            failed_at=datetime.now(timezone.utc),
        )
        for i in range(3)
    ]

    await repo.save_many(tasks)

    ids = [str(t.id) for t in tasks]
    rows = (await async_db_session.execute(
        text("SELECT id, task_type FROM failed_tasks WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": ids},
    )).all()
    assert {str(r[0]) for r in rows} == set(ids)
    assert all(r[1] == "rag_ingest" for r in rows)


@pytest.mark.asyncio
async def test_async_failed_task_repository_save_many_empty_is_a_noop(async_db_session):
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository

    repo = AsyncSqlAlchemyFailedTaskRepository(async_db_session)
    async_db_session.commit = AsyncMock()

    await repo.save_many([])

    async_db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_failed_task_repository_save_many_rolls_back_on_commit_failure(async_db_session):
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
    from src.modules.collection.domain.entities import FailedTask

    repo = AsyncSqlAlchemyFailedTaskRepository(async_db_session)
    tasks = [FailedTask(
        task_type="rag_ingest",
        exception_type="RateLimitExhausted",
        exception_message="boom",
        failed_at=datetime.now(timezone.utc),
    )]

    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.save_many(tasks)

    async_db_session.rollback.assert_awaited_once()


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


# ---------------------------------------------------------------------------
# Batch 3 (024-async-pipeline-refactor follow-up): branch coverage the tests
# above don't reach — not-found lookups, update-existing paths, validation/
# not-found errors, and the commit-fails-then-rollback branch every repo
# shares. Grouped by repo file, mirroring the file layout under
# src/infrastructure/persistence/intelligence/ and .../shared/.
# ---------------------------------------------------------------------------

# ── AsyncSqlAlchemyAnalysesTranslationRepository ────────────────────────────

@pytest.mark.asyncio
async def test_async_analyses_translation_repository_find_returns_none_when_missing(async_db_session):
    from src.infrastructure.persistence.intelligence.analyses_translation_async_repo_impl import (
        AsyncSqlAlchemyAnalysesTranslationRepository,
    )

    repo = AsyncSqlAlchemyAnalysesTranslationRepository(async_db_session)
    found = await repo.find_by_analysis_id_and_language(uuid.uuid4(), "zh-TW")
    assert found is None


@pytest.mark.asyncio
async def test_async_analyses_translation_repository_updates_existing_translation(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.intelligence.analyses_translation_async_repo_impl import (
        AsyncSqlAlchemyAnalysesTranslationRepository,
    )
    from src.modules.intelligence.domain.entities import Analysis, AnalysesContent
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved_article = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    analysis_repo = AsyncSqlAlchemyAnalysisRepository(async_db_session)
    analysis = Analysis(
        article_id=saved_article.id,
        analysis_content=AnalysisContent(summary="s", pain_points="p", insights="i", innovations="n", tag_groups=None),
        analysis_metadata=AnalysisMetadata(model_used="test-model", input_tokens=1, output_tokens=1),
    )
    await analysis_repo.save(analysis)

    translation_repo = AsyncSqlAlchemyAnalysesTranslationRepository(async_db_session)
    await translation_repo.save(AnalysesContent(
        id=None, analysis_id=analysis.id, language="zh-TW",
        summary="第一版", pain_points="p", insights="i", innovations="n",
        created_at=None, updated_at=None,
    ))
    await translation_repo.save(AnalysesContent(
        id=None, analysis_id=analysis.id, language="zh-TW",
        summary="第二版", pain_points="p2", insights="i2", innovations="n2",
        created_at=None, updated_at=None,
    ))

    found = await translation_repo.find_by_analysis_id_and_language(analysis.id, "zh-TW")
    assert found is not None
    assert found.summary == "第二版"
    assert found.pain_points == "p2"


@pytest.mark.asyncio
async def test_async_analyses_translation_repository_save_rolls_back_on_commit_failure(async_db_session):
    from src.infrastructure.persistence.intelligence.analyses_translation_async_repo_impl import (
        AsyncSqlAlchemyAnalysesTranslationRepository,
    )
    from src.modules.intelligence.domain.entities import AnalysesContent

    repo = AsyncSqlAlchemyAnalysesTranslationRepository(async_db_session)
    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.save(AnalysesContent(
            id=None, analysis_id=uuid.uuid4(), language="zh-TW",
            summary="s", pain_points="p", insights="i", innovations="n",
            created_at=None, updated_at=None,
        ))

    async_db_session.rollback.assert_awaited_once()


# ── AsyncSqlAlchemyAnalysisRepository ────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_analysis_repository_save_rolls_back_on_commit_failure(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.modules.intelligence.domain.entities import Analysis
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved_article = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    analysis_repo = AsyncSqlAlchemyAnalysisRepository(async_db_session)
    analysis = Analysis(
        article_id=saved_article.id,
        analysis_content=AnalysisContent(summary="s", pain_points="p", insights="i", innovations="n", tag_groups=None),
        analysis_metadata=AnalysisMetadata(model_used="test-model", input_tokens=1, output_tokens=1),
    )

    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await analysis_repo.save(analysis)

    async_db_session.rollback.assert_awaited_once()


# ── AsyncSqlAlchemyArticleTranslationRepository ─────────────────────────────

@pytest.mark.asyncio
async def test_async_article_translation_repository_find_returns_none_when_missing(async_db_session):
    from src.infrastructure.persistence.intelligence.article_translation_async_repo_impl import (
        AsyncSqlAlchemyArticleTranslationRepository,
    )

    repo = AsyncSqlAlchemyArticleTranslationRepository(async_db_session)
    found = await repo.find_by_article_id_and_language(uuid.uuid4(), "zh-TW")
    assert found is None


@pytest.mark.asyncio
async def test_async_article_translation_repository_updates_existing_translation(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.article_translation_async_repo_impl import (
        AsyncSqlAlchemyArticleTranslationRepository,
    )

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    repo = AsyncSqlAlchemyArticleTranslationRepository(async_db_session)
    await repo.save(saved.id, "zh-TW", "第一版標題", "第一版內文")
    await repo.save(saved.id, "zh-TW", "第二版標題", "第二版內文")

    found = await repo.find_by_article_id_and_language(saved.id, "zh-TW")
    assert found is not None
    assert found.title == "第二版標題"
    assert found.content == "第二版內文"


@pytest.mark.asyncio
async def test_async_article_translation_repository_save_rolls_back_on_commit_failure(async_db_session, test_topic):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.article_translation_async_repo_impl import (
        AsyncSqlAlchemyArticleTranslationRepository,
    )

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    repo = AsyncSqlAlchemyArticleTranslationRepository(async_db_session)
    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.save(saved.id, "zh-TW", "標題", "內文")

    async_db_session.rollback.assert_awaited_once()


# ── AsyncSqlAlchemyTagRepository ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_tag_repository_find_similar_returns_empty_when_topic_id_none():
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository

    repo = AsyncSqlAlchemyTagRepository(session=None)  # never touched: short-circuits before any query
    result = await repo.find_similar([0.1] * 768, "some-group", None, threshold=0.9)
    assert result == []


@pytest.mark.asyncio
async def test_async_tag_repository_save_raises_validation_error_when_topic_id_none(async_db_session):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from shared.domain.exceptions import ValidationError

    repo = AsyncSqlAlchemyTagRepository(async_db_session)
    with pytest.raises(ValidationError):
        await repo.save(name="x", tag_group_name="any-group", embedding=[0.1] * 768, topic_id=None)


@pytest.mark.asyncio
async def test_async_tag_repository_save_raises_not_found_when_group_missing(async_db_session, test_topic):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from shared.domain.exceptions import NotFoundError

    repo = AsyncSqlAlchemyTagRepository(async_db_session)
    with pytest.raises(NotFoundError):
        await repo.save(
            name="x",
            tag_group_name=f"nonexistent-group-{uuid.uuid4().hex[:8]}",
            embedding=[0.1] * 768,
            topic_id=test_topic,
        )


@pytest.mark.asyncio
async def test_async_tag_repository_save_suggestion_persists_and_backfills_id(async_db_session, tag_group, test_topic):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion

    tag_repo = AsyncSqlAlchemyTagRepository(async_db_session)
    new_tag = await tag_repo.save(
        name=f"async-sugg-new-{uuid.uuid4().hex[:8]}", tag_group_name=tag_group.name,
        embedding=[0.3] * 768, topic_id=tag_group.topic_id,
    )
    existing_tag = await tag_repo.save(
        name=f"async-sugg-existing-{uuid.uuid4().hex[:8]}", tag_group_name=tag_group.name,
        embedding=[0.4] * 768, topic_id=tag_group.topic_id,
    )
    await tag_repo.commit()

    article_repo = AsyncSqlAlchemyArticleRepository(async_db_session)
    saved_article = await article_repo.save(_make_article(test_topic))
    await async_db_session.commit()

    suggestion = TagNormalizationSuggestion(
        new_tag_id=new_tag.id,
        existing_tag_id=existing_tag.id,
        similarity_score=0.95,
        article_id=saved_article.id,
    )
    assert suggestion.id is None

    result = await tag_repo.save_suggestion(suggestion)
    await tag_repo.commit()

    assert result is suggestion
    assert suggestion.id is not None


@pytest.mark.asyncio
async def test_async_tag_repository_commit_rolls_back_on_failure(async_db_session):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository

    repo = AsyncSqlAlchemyTagRepository(async_db_session)
    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.commit()

    async_db_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_tag_repository_rollback_delegates_to_session(async_db_session):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository

    repo = AsyncSqlAlchemyTagRepository(async_db_session)
    async_db_session.rollback = AsyncMock()

    await repo.rollback()

    async_db_session.rollback.assert_awaited_once()


# ── AsyncSqlAlchemyTagGroupDefinitionRepository ──────────────────────────────

@pytest.mark.asyncio
async def test_async_tag_group_definition_repository_sets_embedding_on_create(async_db_session, test_topic):
    from sqlalchemy import text
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import (
        AsyncSqlAlchemyTagGroupDefinitionRepository,
    )

    repo = AsyncSqlAlchemyTagGroupDefinitionRepository(async_db_session)
    name = f"async-test-group-embed-{uuid.uuid4().hex[:8]}"

    await repo.upsert(name=name, display_name="Embedded Group", topic_id=test_topic, embedding=[0.1] * 768)
    await async_db_session.commit()

    row = (await async_db_session.execute(
        text("SELECT embedding IS NOT NULL FROM tag_group_definitions WHERE name = :name"),
        {"name": name},
    )).first()
    assert row is not None
    assert row[0] is True


@pytest.mark.asyncio
async def test_async_tag_group_definition_repository_updates_embedding_when_existing_without_one(async_db_session, test_topic):
    from sqlalchemy import text
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import (
        AsyncSqlAlchemyTagGroupDefinitionRepository,
    )

    repo = AsyncSqlAlchemyTagGroupDefinitionRepository(async_db_session)
    name = f"async-test-group-noembed-{uuid.uuid4().hex[:8]}"

    await repo.upsert(name=name, display_name="No Embedding Yet", topic_id=test_topic)
    await async_db_session.commit()

    await repo.upsert(name=name, display_name="No Embedding Yet", topic_id=test_topic, embedding=[0.2] * 768)
    await async_db_session.commit()

    row = (await async_db_session.execute(
        text("SELECT embedding IS NOT NULL FROM tag_group_definitions WHERE name = :name"),
        {"name": name},
    )).first()
    assert row is not None
    assert row[0] is True


# ── AsyncSqlAlchemyTagTranslationRepository ──────────────────────────────────

@pytest.mark.asyncio
async def test_async_tag_translation_repository_save_group_translation_insert_and_update(async_db_session, tag_group):
    from src.infrastructure.persistence.intelligence.tag_translation_async_repo_impl import (
        AsyncSqlAlchemyTagTranslationRepository,
    )
    from sqlalchemy import select
    from models.tag_group import TagGroupDefinition

    result = await async_db_session.execute(
        select(TagGroupDefinition).filter_by(name=tag_group.name, topic_id=tag_group.topic_id)
    )
    group_row = result.scalars().first()

    translation_repo = AsyncSqlAlchemyTagTranslationRepository(async_db_session)
    await translation_repo.save_group_translation(group_row.id, "zh-TW", display_name="第一版", description="desc1")
    await translation_repo.save_group_translation(group_row.id, "zh-TW", display_name="第二版", description="desc2")

    groups_without = await translation_repo.find_groups_without_translation("zh-TW", limit=200)
    assert all(g["id"] != group_row.id for g in groups_without)


@pytest.mark.asyncio
async def test_async_tag_translation_repository_save_group_translation_rolls_back_on_commit_failure(async_db_session, tag_group):
    from sqlalchemy import select
    from models.tag_group import TagGroupDefinition
    from src.infrastructure.persistence.intelligence.tag_translation_async_repo_impl import (
        AsyncSqlAlchemyTagTranslationRepository,
    )

    result = await async_db_session.execute(
        select(TagGroupDefinition).filter_by(name=tag_group.name, topic_id=tag_group.topic_id)
    )
    group_row = result.scalars().first()

    repo = AsyncSqlAlchemyTagTranslationRepository(async_db_session)
    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.save_group_translation(group_row.id, "zh-TW", display_name="無效群組", description=None)

    async_db_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_tag_translation_repository_find_groups_without_translation(async_db_session, test_topic):
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import (
        AsyncSqlAlchemyTagGroupDefinitionRepository,
    )
    from src.infrastructure.persistence.intelligence.tag_translation_async_repo_impl import (
        AsyncSqlAlchemyTagTranslationRepository,
    )
    from sqlalchemy import select
    from models.tag_group import TagGroupDefinition

    group_repo = AsyncSqlAlchemyTagGroupDefinitionRepository(async_db_session)
    name = f"async-group-no-translation-{uuid.uuid4().hex[:8]}"
    await group_repo.upsert(name=name, display_name="Needs Translation", topic_id=test_topic)
    await async_db_session.commit()

    result = await async_db_session.execute(select(TagGroupDefinition).filter_by(name=name, topic_id=test_topic))
    group_row = result.scalars().first()

    translation_repo = AsyncSqlAlchemyTagTranslationRepository(async_db_session)
    without = await translation_repo.find_groups_without_translation("zh-TW", limit=200)
    assert any(g["id"] == group_row.id for g in without)


@pytest.mark.asyncio
async def test_async_tag_translation_repository_save_tag_translation_rolls_back_on_commit_failure(async_db_session, tag_group):
    from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
    from src.infrastructure.persistence.intelligence.tag_translation_async_repo_impl import (
        AsyncSqlAlchemyTagTranslationRepository,
    )

    tag_repo = AsyncSqlAlchemyTagRepository(async_db_session)
    tag = await tag_repo.save(
        name=f"async-tag-rollback-{uuid.uuid4().hex[:8]}",
        tag_group_name=tag_group.name,
        embedding=[0.5] * 768,
        topic_id=tag_group.topic_id,
    )
    await tag_repo.commit()

    repo = AsyncSqlAlchemyTagTranslationRepository(async_db_session)
    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.save_tag_translation(tag.id, "zh-TW", "無效標籤")

    async_db_session.rollback.assert_awaited_once()


# ── AsyncSqlAlchemyFailedTaskRepository ──────────────────────────────────────

@pytest.mark.asyncio
async def test_async_failed_task_repository_save_rolls_back_on_commit_failure(async_db_session):
    from src.infrastructure.persistence.shared.failed_task_async_repo_impl import AsyncSqlAlchemyFailedTaskRepository
    from src.modules.collection.domain.entities import FailedTask

    repo = AsyncSqlAlchemyFailedTaskRepository(async_db_session)
    task = FailedTask(
        task_type="analyze",
        exception_type="RuntimeError",
        exception_message="boom",
        failed_at=datetime.now(timezone.utc),
    )

    async_db_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    async_db_session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="commit failed"):
        await repo.save(task)

    async_db_session.rollback.assert_awaited_once()
