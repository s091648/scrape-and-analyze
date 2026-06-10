from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from models.base import Base


class ArticleTranslation(Base):
    __tablename__ = 'articles_translation'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    language = Column(String(10), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    article = relationship("Article", backref="article_translations")

    __table_args__ = (
        Index('idx_articles_translation_article_id', 'article_id'),
        Index('idx_articles_translation_language', 'language'),
        UniqueConstraint('article_id', 'language', name='uq_articles_translation_article_language'),
    )
