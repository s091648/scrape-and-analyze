from sqlalchemy.orm import configure_mappers

from models.base import Base
from models.article import Article
from models.analysis import Analysis
from models.analyses_translation import AnalysesTranslation
from models.failed_task import FailedTask
from models.tag import Tag, article_tags
from models.tag_group import TagGroupDefinition
from models.tag_translation import TagsTranslation  # noqa: F401 — registers Tag.translations backref
from models.tag_group_translation import TagGroupDefinitionsTranslation  # noqa: F401 — registers TagGroupDefinition.translations backref
from models.auth import AuthBase, User
from models.scraper_setting import ScraperBase, ScraperSetting
from models.tag_normalization_suggestion import TagNormalizationSuggestion  # noqa: F401
from models.article_translation import ArticleTranslation  # noqa: F401 — registers Article.article_translations backref

configure_mappers()