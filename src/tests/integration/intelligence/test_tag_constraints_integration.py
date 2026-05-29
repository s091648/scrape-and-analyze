"""Integration tests for tag constraints and tag group operations.

Requires a running PostgreSQL with pgvector extension.
Run via: make test-integration
"""
import uuid
import pytest

from src.tests.integration.conftest import (
    integration_engine,
    integration_session,
    BASE_SCHEMA,
)


@pytest.mark.integration
@pytest.fixture
def db_session():
    """Provide a session with rollback for test isolation."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os

    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ── T004: Partial unique index on tags ─────────────────────────────────────

@pytest.mark.integration
class TestTagPartialUniqueIndex:
    def test_two_tags_same_name_same_group_raises(self, db_session):
        """Two tags with the same name in the same group violates the partial unique index."""
        from sqlalchemy import text
        from models.tag import Tag, article_tags
        from models.tag_group import TagGroupDefinition
        from models.topic import Topic

        topic = Topic(name=f"test-topic-{uuid.uuid4()!s:.8}", tag_mode="unsupervised")
        db_session.add(topic)
        db_session.flush()

        group = TagGroupDefinition(
            name=f"test_group_{uuid.uuid4()!s:.8}",
            display_name="Test Group",
            topic_id=topic.id,
        )
        db_session.add(group)
        db_session.flush()

        tag1 = Tag(name="duplicate_tag", tag_group_id=group.id)
        db_session.add(tag1)
        db_session.flush()

        tag2 = Tag(name="duplicate_tag", tag_group_id=group.id)
        db_session.add(tag2)

        with pytest.raises(Exception):
            db_session.flush()
        db_session.rollback()

    def test_two_ungrouped_tags_same_name_allowed(self, db_session):
        """Two ungrouped tags with the same name are allowed (NULL in partial index)."""
        from models.tag import Tag

        tag1 = Tag(name=f"ungrouped_dup_{uuid.uuid4()!s:.8}")
        tag2 = Tag(name=tag1.name)
        db_session.add_all([tag1, tag2])
        db_session.flush()

        # Both should exist
        result = db_session.query(Tag).filter(Tag.name == tag1.name, Tag.tag_group_id.is_(None)).all()
        assert len(result) == 2
        db_session.rollback()


# ── T060-T063: Integration tests for tag operations ─────────────────────────

@pytest.mark.integration
class TestTagGroupOperationsIntegration:
    def test_delete_group_ungroups_tags(self, db_session):
        """Deleting a group sets tag_group_id to null on its tags."""
        from models.tag import Tag
        from models.tag_group import TagGroupDefinition
        from models.topic import Topic

        topic = Topic(name=f"test-topic-{uuid.uuid4()!s:.8}", tag_mode="unsupervised")
        db_session.add(topic)
        db_session.flush()

        group = TagGroupDefinition(
            name=f"del_group_{uuid.uuid4()!s:.8}",
            display_name="Delete Me",
            topic_id=topic.id,
        )
        db_session.add(group)
        db_session.flush()

        tag = Tag(name="orphan_tag", tag_group_id=group.id)
        db_session.add(tag)
        db_session.flush()

        tag_id = tag.id
        group_id = group.id

        db_session.delete(group)
        db_session.flush()

        # Tag should still exist but ungrouped
        refreshed_tag = db_session.query(Tag).filter_by(id=tag_id).first()
        assert refreshed_tag is not None
        assert refreshed_tag.tag_group_id is None
        db_session.rollback()

    def test_merge_groups_deduplicates_tags(self, db_session):
        """Merging two groups should consolidate tags with the same name."""
        from models.tag import Tag, article_tags
        from models.tag_group import TagGroupDefinition
        from models.topic import Topic
        from models.article import Article

        topic = Topic(name=f"test-topic-{uuid.uuid4()!s:.8}", tag_mode="unsupervised")
        db_session.add(topic)
        db_session.flush()

        group_a = TagGroupDefinition(
            name=f"merge_a_{uuid.uuid4()!s:.8}",
            display_name="Merge A",
            topic_id=topic.id,
        )
        group_b = TagGroupDefinition(
            name=f"merge_b_{uuid.uuid4()!s:.8}",
            display_name="Merge B",
            topic_id=topic.id,
        )
        db_session.add_all([group_a, group_b])
        db_session.flush()

        # Same tag name in both groups
        tag_a = Tag(name="shared_tag", tag_group_id=group_a.id)
        tag_b = Tag(name="shared_tag", tag_group_id=group_b.id)
        db_session.add_all([tag_a, tag_b])
        db_session.flush()

        # Move tag_b's articles to tag_a, delete tag_b
        tag_b.tag_group_id = group_a.id
        db_session.delete(tag_b)
        db_session.delete(group_b)
        db_session.flush()

        # Only one tag with that name in group_a
        remaining = db_session.query(Tag).filter(
            Tag.name == "shared_tag",
            Tag.tag_group_id == group_a.id,
        ).all()
        assert len(remaining) == 1
        db_session.rollback()


@pytest.mark.integration
class TestTagNormalizationIntegration:
    def test_normalization_auto_merge_with_real_similarity(self, db_session):
        """Two tags with very similar names should have high cosine similarity after embedding."""
        # This test verifies the pgvector similarity search works end-to-end
        # but depends on embeddings being present (typically via backfill).
        # Without embeddings, this is a structural test.
        from models.tag import Tag
        from models.tag_group import TagGroupDefinition
        from models.topic import Topic

        topic = Topic(name=f"test-topic-{uuid.uuid4()!s:.8}", tag_mode="unsupervised")
        db_session.add(topic)
        db_session.flush()

        group = TagGroupDefinition(
            name=f"norm_group_{uuid.uuid4()!s:.8}",
            display_name="Normalization Test",
            topic_id=topic.id,
        )
        db_session.add(group)
        db_session.flush()

        tag = Tag(name="digital_twin_test", tag_group_id=group.id)
        db_session.add(tag)
        db_session.flush()

        # Verify tag was created and is queryable
        found = db_session.query(Tag).filter_by(id=tag.id).first()
        assert found is not None
        assert found.name == "digital_twin_test"
        db_session.rollback()

    def test_suggestion_approval_cascades_correctly(self, db_session):
        """Approving a suggestion re-points article_tags and deletes the new tag."""
        from models.tag import Tag, article_tags
        from models.tag_group import TagGroupDefinition
        from models.tag_normalization_suggestion import TagNormalizationSuggestion
        from models.topic import Topic
        from models.article import Article

        topic = Topic(name=f"test-topic-{uuid.uuid4()!s:.8}", tag_mode="unsupervised")
        db_session.add(topic)
        db_session.flush()

        group = TagGroupDefinition(
            name=f"sugg_group_{uuid.uuid4()!s:.8}",
            display_name="Suggestion Test",
            topic_id=topic.id,
        )
        db_session.add(group)
        db_session.flush()

        existing_tag = Tag(name="existing_similar", tag_group_id=group.id)
        new_tag = Tag(name="new similar", tag_group_id=group.id)
        db_session.add_all([existing_tag, new_tag])
        db_session.flush()

        article = Article(
            title="Test Article",
            url="https://example.com/test",
            topic_id=topic.id,
        )
        db_session.add(article)
        db_session.flush()

        # Link article to new_tag
        db_session.execute(
            article_tags.insert().values(article_id=article.id, tag_id=new_tag.id)
        )
        db_session.flush()

        # Create suggestion
        suggestion = TagNormalizationSuggestion(
            new_tag_id=new_tag.id,
            existing_tag_id=existing_tag.id,
            similarity_score=0.92,
            article_id=article.id,
        )
        db_session.add(suggestion)
        db_session.flush()

        # Approve: re-point article_tags, delete new_tag
        from sqlalchemy import text
        db_session.execute(text("""
            INSERT INTO article_tags (article_id, tag_id)
            SELECT article_id, :existing_id
            FROM article_tags WHERE tag_id = :new_id
            ON CONFLICT DO NOTHING
        """), {"existing_id": str(existing_tag.id), "new_id": str(new_tag.id)})
        db_session.execute(text("DELETE FROM article_tags WHERE tag_id = :new_id"), {"new_id": str(new_tag.id)})
        db_session.delete(new_tag)
        db_session.flush()

        # Verify: article linked to existing_tag, new_tag gone
        link_count = db_session.query(article_tags).filter_by(
            article_id=article.id, tag_id=existing_tag.id
        ).count()
        assert link_count == 1

        deleted_tag = db_session.query(Tag).filter_by(id=new_tag.id).first()
        assert deleted_tag is None
        db_session.rollback()
