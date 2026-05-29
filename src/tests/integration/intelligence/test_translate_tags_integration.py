"""
Integration tests for tag/group translation repository — covers
upsert semantics and find_*_without_translation dedup queries.

Requires running PostgreSQL (make test-integration).
"""
import uuid

import pytest

from models.tag import Tag
from models.tag_group import TagGroupDefinition
from models.tag_translation import TagsTranslation
from models.tag_group_translation import TagGroupDefinitionsTranslation
from src.infrastructure.persistence.intelligence.tag_translation_repo_impl import (
    SqlAlchemyTagTranslationRepository,
)


@pytest.mark.integration
@pytest.fixture
def tag_repo(db_session):
    return SqlAlchemyTagTranslationRepository(db_session)


@pytest.mark.integration
@pytest.fixture
def test_tag(db_session, tag_group):
    tag = Tag(
        name=f"test_tag_{uuid.uuid4().hex[:8]}",
        tag_group_name=tag_group.name,
    )
    db_session.add(tag)
    db_session.flush()
    return tag


@pytest.mark.integration
@pytest.fixture
def test_group(db_session, test_topic):
    group = TagGroupDefinition(
        name=f"test_group_{uuid.uuid4().hex[:8]}",
        display_name="Test Group",
        description="A test group",
        color_hex="#FF0000",
        sort_order=1,
        topic_id=test_topic,
    )
    db_session.add(group)
    db_session.flush()
    return group


# ── Tag translation: save upsert ────────────────────────────────────────────

@pytest.mark.integration
def test_save_tag_translation_upserts(db_session, tag_repo, test_tag):
    tag_repo.save_tag_translation(test_tag.id, "zh-TW", "測試標籤一")

    tag_repo.save_tag_translation(test_tag.id, "zh-TW", "測試標籤二")

    count = db_session.query(TagsTranslation).filter_by(
        tag_id=test_tag.id, language="zh-TW"
    ).count()
    assert count == 1

    row = db_session.query(TagsTranslation).filter_by(
        tag_id=test_tag.id, language="zh-TW"
    ).first()
    assert row.name == "測試標籤二"


# ── Tag translation: find_without excludes translated ────────────────────────

@pytest.mark.integration
def test_find_tags_without_translation_excludes_translated(db_session, tag_repo, test_tag):
    results = tag_repo.find_tags_without_translation("zh-TW", limit=50)
    tag_ids = [t["tag_id"] for t in results]
    assert test_tag.id in tag_ids

    tag_repo.save_tag_translation(test_tag.id, "zh-TW", "已翻譯")

    results = tag_repo.find_tags_without_translation("zh-TW", limit=50)
    tag_ids = [t["tag_id"] for t in results]
    assert test_tag.id not in tag_ids


# ── Group translation: save upsert ──────────────────────────────────────────

@pytest.mark.integration
def test_save_group_translation_upserts(db_session, tag_repo, test_group):
    tag_repo.save_group_translation(test_group.id, "zh-TW", "測試群組一", "描述一")

    tag_repo.save_group_translation(test_group.id, "zh-TW", "測試群組二", "描述二")

    count = db_session.query(TagGroupDefinitionsTranslation).filter_by(
        tag_group_definition_id=test_group.id, language="zh-TW"
    ).count()
    assert count == 1

    row = db_session.query(TagGroupDefinitionsTranslation).filter_by(
        tag_group_definition_id=test_group.id, language="zh-TW"
    ).first()
    assert row.display_name == "測試群組二"
    assert row.description == "描述二"


# ── Group translation: find_without excludes translated ─────────────────────

@pytest.mark.integration
def test_find_groups_without_translation_excludes_translated(db_session, tag_repo, test_group):
    results = tag_repo.find_groups_without_translation("zh-TW", limit=50)
    group_ids = [g["id"] for g in results]
    assert test_group.id in group_ids

    tag_repo.save_group_translation(test_group.id, "zh-TW", "已翻譯群組", None)

    results = tag_repo.find_groups_without_translation("zh-TW", limit=50)
    group_ids = [g["id"] for g in results]
    assert test_group.id not in group_ids
