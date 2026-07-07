from sqlalchemy.orm import configure_mappers

from models.base import Base
from models.article import Article
from models.article_chunk import ArticleChunk  # noqa: F401
from models.article_metrics import ArticleMetrics  # noqa: F401
from models.analysis import Analysis
from models.analyses_translation import AnalysesTranslation
from models.failed_task import FailedTask
from models.llm_provider import LlmProvider  # noqa: F401
from models.scraper_keyword import ScraperKeyword  # noqa: F401
from models.tag import Tag, article_tags
from models.tag_group import TagGroupDefinition
from models.tag_translation import TagsTranslation  # noqa: F401 — registers Tag.translations backref
from models.tag_group_translation import TagGroupDefinitionsTranslation  # noqa: F401 — registers TagGroupDefinition.translations backref
from models.topic import Topic  # noqa: F401
from models.auth import AuthBase, User
from models.scraper_setting import ScraperBase, ScraperSetting
from models.tag_normalization_suggestion import TagNormalizationSuggestion  # noqa: F401
from models.article_translation import ArticleTranslation  # noqa: F401 — registers Article.article_translations backref
from models.user_subscription import UserTopicSubscription, UserNotificationSettings, UserArticleFavorite  # noqa: F401
from models.weekly_report import WeeklyReport  # noqa: F401
# NOTE: models.arxiv_keyword is intentionally excluded — legacy model, its table
# was dropped in migration 14 (superseded by ScraperKeyword). Importing it here
# would make Base.metadata expect a table that no longer exists.
configure_mappers()