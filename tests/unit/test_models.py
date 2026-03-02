import pytest


def test_article_model_has_required_fields():
    """Article model should have all required fields"""
    from src.models.article import Article

    assert hasattr(Article, 'id')
    assert hasattr(Article, 'url')
    assert hasattr(Article, 'url_hash')
    assert hasattr(Article, 'source')
    assert hasattr(Article, 'title')
    assert hasattr(Article, 'content')
    assert hasattr(Article, 'published_at')
    assert hasattr(Article, 'scraped_at')
    assert hasattr(Article, 'metadata_')
    assert hasattr(Article, 'correlation_id')


def test_article_url_is_unique():
    """Article url should have unique constraint"""
    from src.models.article import Article

    url_column = Article.__table__.columns['url']
    assert url_column.unique is True


def test_article_url_hash_has_index():
    """Article url_hash should have an index"""
    from src.models.article import Article

    indexes = {idx.name for idx in Article.__table__.indexes}
    assert any('url_hash' in idx for idx in indexes)


def test_analysis_model_has_required_fields():
    """Analysis model should have all required fields"""
    from src.models.analysis import Analysis

    assert hasattr(Analysis, 'id')
    assert hasattr(Analysis, 'article_id')
    assert hasattr(Analysis, 'correlation_id')
    assert hasattr(Analysis, 'pain_points')
    assert hasattr(Analysis, 'insights')
    assert hasattr(Analysis, 'innovations')
    assert hasattr(Analysis, 'analyzed_at')
    assert hasattr(Analysis, 'model_used')
    assert hasattr(Analysis, 'input_tokens')
    assert hasattr(Analysis, 'output_tokens')
    # tags and tag_groups moved to tags / article_tags tables
    assert 'tags' not in Analysis.__table__.columns
    assert 'tag_groups' not in Analysis.__table__.columns


def test_analysis_has_foreign_key_to_article():
    """Analysis should have foreign key to Article"""
    from src.models.analysis import Analysis

    fk_tables = [fk.column.table.name for fk in Analysis.__table__.foreign_keys]
    assert 'articles' in fk_tables


def test_analysis_article_id_is_unique():
    """Analysis article_id should be unique (one analysis per article)"""
    from src.models.analysis import Analysis

    article_id_column = Analysis.__table__.columns['article_id']
    assert article_id_column.unique is True


def test_failed_task_model_has_required_fields():
    """FailedTask model should have required fields"""
    from src.models.failed_task import FailedTask

    assert hasattr(FailedTask, 'id')
    assert hasattr(FailedTask, 'task_type')
    assert hasattr(FailedTask, 'article_url')
    assert hasattr(FailedTask, 'article_id')
    assert hasattr(FailedTask, 'exception_type')
    assert hasattr(FailedTask, 'exception_message')
    assert hasattr(FailedTask, 'failed_at')
    assert hasattr(FailedTask, 'resolved')
    assert hasattr(FailedTask, 'resolved_at')


def test_failed_task_has_resolved_index():
    """FailedTask should have index on resolved for efficient queries"""
    from src.models.failed_task import FailedTask

    indexes = {idx.name for idx in FailedTask.__table__.indexes}
    assert any('resolved' in idx for idx in indexes)


def test_tag_model_has_required_fields():
    from src.models.tag import Tag
    assert hasattr(Tag, 'id')
    assert hasattr(Tag, 'name')
    assert hasattr(Tag, 'tag_group_name')


def test_tag_name_group_is_unique():
    from src.models.tag import Tag
    uq_names = {c.name for c in Tag.__table__.constraints}
    assert 'uq_tag_name_group' in uq_names


def test_tag_group_name_has_index():
    from src.models.tag import Tag
    idx_names = {i.name for i in Tag.__table__.indexes}
    assert 'idx_tags_group' in idx_names


def test_article_tags_table_exists():
    from src.models.tag import article_tags
    assert 'article_id' in article_tags.c
    assert 'tag_id' in article_tags.c


def test_article_has_tags_backref():
    from src.models.article import Article
    # importing tag module registers the backref
    import src.models.tag  # noqa: F401
    assert hasattr(Article, 'tags')
