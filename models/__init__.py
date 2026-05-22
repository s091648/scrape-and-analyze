from models.base import Base
from models.article import Article
from models.analysis import Analysis
from models.analyses_translation import AnalysesTranslation
from models.failed_task import FailedTask
from models.tag import Tag, article_tags
from models.tag_group import TagGroupDefinition
from models.auth import AuthBase, User
from models.scraper_setting import ScraperBase, ScraperSetting
from sqlalchemy.orm import configure_mappers

configure_mappers()