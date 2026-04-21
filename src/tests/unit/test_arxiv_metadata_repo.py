from unittest.mock import MagicMock
from uuid import uuid4


def _make_row(article_id=None):
    row = MagicMock()
    row.id = uuid4()
    row.article_id = article_id or uuid4()
    row.arxiv_id = "http://arxiv.org/abs/2601.00001v1"
    row.authors = ["Alice", "Bob"]
    row.pdf_available = True
    row.sections = {"introduction": "Intro.", "conclusion": "Concl."}
    return row


def test_find_by_article_id_returns_none_when_not_found():
    from src.infrastructure.persistence.sqlalchemy_repos.arxiv_metadata_repo_impl import (
        SqlAlchemyArxivMetadataRepository,
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    repo = SqlAlchemyArxivMetadataRepository(session=session)
    assert repo.find_by_article_id(uuid4()) is None


def test_find_by_article_id_maps_row_to_entity():
    from src.infrastructure.persistence.sqlalchemy_repos.arxiv_metadata_repo_impl import (
        SqlAlchemyArxivMetadataRepository,
    )
    from src.domain.entities.arxiv_metadata import ArxivMetadataEntity
    article_id = uuid4()
    row = _make_row(article_id=article_id)
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = row
    repo = SqlAlchemyArxivMetadataRepository(session=session)
    entity = repo.find_by_article_id(article_id)
    assert isinstance(entity, ArxivMetadataEntity)
    assert entity.article_id == article_id
    assert entity.authors == ["Alice", "Bob"]


def test_save_flushes_and_returns_entity():
    from src.infrastructure.persistence.sqlalchemy_repos.arxiv_metadata_repo_impl import (
        SqlAlchemyArxivMetadataRepository,
    )
    from src.domain.entities.arxiv_metadata import ArxivMetadataEntity
    entity = ArxivMetadataEntity(
        article_id=uuid4(), arxiv_id="abc", authors=["Alice"],
        pdf_available=True, sections={"introduction": "Hello."},
    )
    session = MagicMock()
    repo = SqlAlchemyArxivMetadataRepository(session=session)
    result = repo.save(entity)
    session.add.assert_called_once()
    session.flush.assert_called_once()
    assert isinstance(result, ArxivMetadataEntity)
