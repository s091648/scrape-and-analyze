from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

AuthBase = declarative_base()


class User(AuthBase):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String(20), nullable=False, default='admin')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
