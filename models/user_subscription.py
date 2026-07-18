from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class UserTopicSubscription(Base):
    __tablename__ = 'user_topic_subscriptions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey('topics.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_id', 'topic_id', name='uq_user_topic_subscriptions'),
    )


class UserNotificationSettings(Base):
    __tablename__ = 'user_notification_settings'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    email_enabled = Column(Boolean, nullable=False, default=True)
    telegram_chat_id = Column(String(50), nullable=True)
    telegram_enabled = Column(Boolean, nullable=False, default=False)
    locale = Column(String(10), nullable=False, default='en')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint('user_id', name='uq_user_notification_settings_user_id'),
    )


class UserArticleFavorite(Base):
    __tablename__ = 'user_article_favorites'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('auth.users.id', ondelete='CASCADE'), nullable=False)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_id', 'article_id', name='uq_user_article_favorites'),
    )
