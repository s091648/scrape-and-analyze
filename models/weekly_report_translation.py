from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class WeeklyReportTranslation(Base):
    __tablename__ = 'weekly_reports_translation'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    weekly_report_id = Column(
        UUID(as_uuid=True),
        ForeignKey('weekly_reports.id', ondelete='CASCADE'),
        nullable=False,
    )
    language = Column(String(10), nullable=False)
    title = Column(Text, nullable=False)
    summary_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    weekly_report = relationship("WeeklyReport", backref="translations")

    __table_args__ = (
        Index('idx_weekly_reports_translation_report_id', 'weekly_report_id'),
        Index('idx_weekly_reports_translation_language', 'language'),
        UniqueConstraint(
            'weekly_report_id',
            'language',
            name='uq_weekly_reports_translation_report_language',
        ),
    )
