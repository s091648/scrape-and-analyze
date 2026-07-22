from sqlalchemy import Column, Text, Table, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from models.base import Base
from models.db_schema import DbSchema
from models.tag_group import TagGroupDefinition  # noqa: F401 — registers mapper


article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', UUID(as_uuid=True), ForeignKey('core.articles.id'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('intelligence.tags.id'), primary_key=True),
    schema=DbSchema.INTELLIGENCE.value,
)


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    tag_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey('intelligence.tag_group_definitions.id', ondelete='SET NULL'),
        nullable=True,
    )
    embedding = Column(Vector(768), nullable=True)

    group_def = relationship(
        'TagGroupDefinition',
        foreign_keys='[Tag.tag_group_id]',
        uselist=False,
    )
    articles = relationship('Article', secondary=article_tags, backref='tags')

    __table_args__ = (
        Index(
            'uq_tag_name_group', 'name', 'tag_group_id',
            unique=True,
            postgresql_where=text('tag_group_id IS NOT NULL'),
        ),
        Index('idx_tags_group', 'tag_group_id'),
        {'schema': DbSchema.INTELLIGENCE.value},
    )
