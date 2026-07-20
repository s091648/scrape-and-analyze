import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.generate_db_schema import (  # noqa: E402
    ModelParseError,
    collect_all_tables,
    parse_model_file,
    render_dot,
    _load_db_schema_enum,
)


DB_SCHEMA_SOURCE = '''
from enum import Enum

class DbSchema(str, Enum):
    CORE = "core"
    INTELLIGENCE = "intelligence"
'''


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def enum_members(tmp_path, monkeypatch):
    import scripts.generate_db_schema as gen
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    _write(models_dir, "db_schema.py", DB_SCHEMA_SOURCE)
    monkeypatch.setattr(gen, "MODELS_DIR", models_dir)
    return _load_db_schema_enum(), models_dir


def test_load_db_schema_enum_parses_members(enum_members):
    members, _ = enum_members
    assert members == {"CORE": "core", "INTELLIGENCE": "intelligence"}


def test_dict_form_table_args_with_enum_value(enum_members):
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema

class Article(Base):
    __tablename__ = 'articles'
    __table_args__ = {'schema': DbSchema.CORE.value}
    id = Column(UUID(as_uuid=True), primary_key=True)
'''
    path = _write(models_dir, "article.py", src)
    tables = parse_model_file(path, _load_db_schema_enum())
    assert len(tables) == 1
    assert tables[0].schema == "core"
    assert tables[0].name == "articles"
    assert tables[0].columns[0].is_primary_key is True


def test_tuple_form_table_args_with_bare_enum_member(enum_members):
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema

class Tag(Base):
    __tablename__ = 'tags'
    __table_args__ = (
        UniqueConstraint('name'),
        {'schema': DbSchema.INTELLIGENCE},
    )
    id = Column(UUID(as_uuid=True), primary_key=True)
'''
    path = _write(models_dir, "tag.py", src)
    tables = parse_model_file(path, _load_db_schema_enum())
    assert tables[0].schema == "intelligence"


def test_literal_string_schema_still_supported(enum_members):
    """auth.py / article_chunk.py predate DbSchema and use literal strings."""
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base

class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}
    id = Column(UUID(as_uuid=True), primary_key=True)
'''
    path = _write(models_dir, "auth.py", src)
    tables = parse_model_file(path, _load_db_schema_enum())
    assert tables[0].schema == "auth"


def test_cross_schema_foreign_key_detected(enum_members):
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema

class Analysis(Base):
    __tablename__ = 'analyses'
    __table_args__ = {'schema': DbSchema.INTELLIGENCE.value}
    id = Column(UUID(as_uuid=True), primary_key=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey('core.articles.id'))
'''
    path = _write(models_dir, "analysis.py", src)
    tables = parse_model_file(path, _load_db_schema_enum())
    fk = tables[0].foreign_keys[0]
    assert fk.target_schema == "core"
    assert fk.target_table == "articles"
    assert fk.target_column == "id"


def test_association_table_parsed(enum_members):
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column, Table, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema

article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', UUID(as_uuid=True), ForeignKey('core.articles.id'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('intelligence.tags.id'), primary_key=True),
    schema=DbSchema.INTELLIGENCE.value,
)
'''
    path = _write(models_dir, "assoc.py", src)
    tables = parse_model_file(path, _load_db_schema_enum())
    assert len(tables) == 1
    assert tables[0].name == "article_tags"
    assert tables[0].schema == "intelligence"
    assert len(tables[0].foreign_keys) == 2


def test_column_name_override_not_mistaken_for_type(enum_members):
    """Column('metadata', JSONB) — first positional arg is a DB-column-name
    override, not the type."""
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from models.base import Base
from models.db_schema import DbSchema

class Article(Base):
    __tablename__ = 'articles'
    __table_args__ = {'schema': DbSchema.CORE.value}
    id = Column(UUID(as_uuid=True), primary_key=True)
    metadata_ = Column('metadata', JSONB)
'''
    path = _write(models_dir, "article.py", src)
    tables = parse_model_file(path, _load_db_schema_enum())
    metadata_col = next(c for c in tables[0].columns if c.name == "metadata_")
    assert metadata_col.type_repr == "JSONB"


def test_unresolvable_table_args_raises(enum_members):
    _, models_dir = enum_members
    src = '''
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base

def _dynamic_schema():
    return "whatever"

class Weird(Base):
    __tablename__ = 'weird'
    __table_args__ = {'schema': _dynamic_schema()}
    id = Column(UUID(as_uuid=True), primary_key=True)
'''
    path = _write(models_dir, "weird.py", src)
    with pytest.raises(ModelParseError):
        parse_model_file(path, _load_db_schema_enum())


def test_render_dot_produces_cluster_per_schema_and_colors_cross_schema_edges(enum_members):
    _, models_dir = enum_members
    _write(models_dir, "article.py", '''
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema

class Article(Base):
    __tablename__ = 'articles'
    __table_args__ = {'schema': DbSchema.CORE.value}
    id = Column(UUID(as_uuid=True), primary_key=True)
''')
    _write(models_dir, "analysis.py", '''
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base
from models.db_schema import DbSchema

class Analysis(Base):
    __tablename__ = 'analyses'
    __table_args__ = {'schema': DbSchema.INTELLIGENCE.value}
    id = Column(UUID(as_uuid=True), primary_key=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey('core.articles.id'))
''')
    # collect_all_tables() reads the module-level MODELS_DIR global directly,
    # patched by the enum_members fixture — exercise it like the CLI entrypoint does.
    all_tables = collect_all_tables()

    dot = render_dot(all_tables)
    assert 'cluster_core' in dot
    assert 'cluster_intelligence' in dot
    assert '#e94560' in dot  # cross-schema edge color present
