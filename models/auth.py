from sqlalchemy import Column, String, Text, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

AuthBase = declarative_base()


class User(AuthBase):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True)
    name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default='user')
    is_allowed = Column(Boolean, nullable=False, default=True, server_default='true')

    username = Column(String(100), unique=True, nullable=True)
    hashed_password = Column(String, nullable=True)

    google_id = Column(String(255), unique=True, nullable=True)
    icon = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        server_default=text('NOW()'),
                        onupdate=lambda: datetime.now(timezone.utc))
