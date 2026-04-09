import uuid
from sqlalchemy import Column, Boolean, String, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TEXT
from sqlalchemy.orm import relationship

from models.article import Base


class ArxivMetadata(Base):
    __tablename__ = "arxiv_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    arxiv_id = Column(String(50))
    authors = Column(ARRAY(TEXT), nullable=False, default=list)
    pdf_available = Column(Boolean, nullable=False, default=False)
    sections = Column(JSONB, nullable=False, default=dict)

    article = relationship("Article", backref="arxiv_metadata")

    __table_args__ = (
        UniqueConstraint("article_id", name="uq_arxiv_metadata_article_id"),
        Index("idx_arxiv_metadata_article_id", "article_id"),
    )
