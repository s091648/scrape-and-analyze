def test_topic_model_columns():
    from models.topic import Topic
    cols = {c.name for c in Topic.__table__.columns}
    assert cols >= {"id", "name", "display_name", "prompt_override", "is_active"}


def test_article_model_has_topic_id():
    from models.article import Article
    assert "topic_id" in {c.name for c in Article.__table__.columns}


def test_tag_group_model_has_topic_id():
    from models.tag_group import TagGroupDefinition
    assert "topic_id" in {c.name for c in TagGroupDefinition.__table__.columns}


def test_scraper_setting_model_has_topic_id():
    from models.scraper_setting import ScraperSetting
    assert "topic_id" in {c.name for c in ScraperSetting.__table__.columns}


# --- 016-db-schema-brushup: every moved table declares its new schema via DbSchema ---

def test_core_schema_tables():
    from models.db_schema import DbSchema
    from models.article import Article
    from models.article_translation import ArticleTranslation
    from models.topic import Topic
    for model in (Article, ArticleTranslation, Topic):
        assert model.__table__.schema == DbSchema.CORE.value, model.__tablename__


def test_collection_schema_tables():
    from models.db_schema import DbSchema
    from models.scraper_setting import ScraperSetting
    from models.scraper_keyword import ScraperKeyword
    from models.failed_task import FailedTask
    from models.article_metrics import ArticleMetrics
    from models.article_metric_value import ArticleMetricValue
    for model in (ScraperSetting, ScraperKeyword, FailedTask, ArticleMetrics, ArticleMetricValue):
        assert model.__table__.schema == DbSchema.COLLECTION.value, model.__tablename__


def test_intelligence_schema_tables():
    from models.db_schema import DbSchema
    from models.analysis import Analysis
    from models.analyses_translation import AnalysesTranslation
    from models.tag import Tag, article_tags
    from models.tag_group import TagGroupDefinition
    from models.tag_group_translation import TagGroupDefinitionsTranslation
    from models.tag_translation import TagsTranslation
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    from models.weekly_report import WeeklyReport
    from models.weekly_report_translation import WeeklyReportTranslation
    from models.search_term import SearchTerm
    from models.search_term_article import SearchTermArticle
    for model in (
        Analysis, AnalysesTranslation, Tag, TagGroupDefinition,
        TagGroupDefinitionsTranslation, TagsTranslation,
        TagNormalizationSuggestion, WeeklyReport, WeeklyReportTranslation,
        SearchTerm, SearchTermArticle,
    ):
        assert model.__table__.schema == DbSchema.INTELLIGENCE.value, model.__tablename__
    assert article_tags.schema == DbSchema.INTELLIGENCE.value


def test_search_term_model_columns():
    from models.search_term import SearchTerm
    cols = {c.name for c in SearchTerm.__table__.columns}
    assert cols == {"id", "topic_id", "term", "language", "occurrence_count"}


def test_search_term_article_model_columns_and_fks():
    from models.search_term_article import SearchTermArticle
    cols = {c.name for c in SearchTermArticle.__table__.columns}
    assert cols == {"id", "search_term_id", "article_id"}
    fk_targets = {fk.target_fullname for fk in SearchTermArticle.__table__.foreign_keys}
    assert "intelligence.search_terms.id" in fk_targets
    assert "core.articles.id" in fk_targets


def test_ai_infra_schema_tables():
    from models.db_schema import DbSchema
    from models.llm_provider import LlmProvider
    from models.metric_definition import MetricDefinition
    from models.metric_provider import MetricProvider
    for model in (LlmProvider, MetricDefinition, MetricProvider):
        assert model.__table__.schema == DbSchema.AI_INFRA.value, model.__tablename__


def test_user_prefs_schema_tables():
    from models.db_schema import DbSchema
    from models.user_subscription import UserTopicSubscription, UserNotificationSettings, UserArticleFavorite
    for model in (UserTopicSubscription, UserNotificationSettings, UserArticleFavorite):
        assert model.__table__.schema == DbSchema.USER_PREFS.value, model.__tablename__


def test_auth_schema_unchanged():
    """auth predates DbSchema and is out of this feature's scope."""
    from models.auth import User
    assert User.__table__.schema == "auth"
