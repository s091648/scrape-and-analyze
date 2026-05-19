from sqlalchemy import Column, String, Text, Table, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from models.base import Base
from models.tag_group import TagGroupDefinition  # noqa: F401 — registers mapper


article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', UUID(as_uuid=True), ForeignKey('articles.id'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('tags.id'), primary_key=True),
)


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    tag_group_name = Column(String(100), nullable=False)
    embedding = Column(Vector(768), nullable=True)

    group_def = relationship(
        'TagGroupDefinition',
        primaryjoin='Tag.tag_group_name == TagGroupDefinition.name',
        foreign_keys='[Tag.tag_group_name]',
        uselist=False,
        viewonly=True,
    )
    articles = relationship('Article', secondary=article_tags, backref='tags')

    __table_args__ = (
        UniqueConstraint('name', 'tag_group_name', name='uq_tag_name_group'),
        Index('idx_tags_group', 'tag_group_name'),
    )


