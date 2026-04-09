def test_arxiv_metadata_entity_defaults():
    from uuid import uuid4
    from src.domain.entities.arxiv_metadata import ArxivMetadataEntity
    entity = ArxivMetadataEntity(article_id=uuid4())
    assert entity.id is None
    assert entity.authors == []
    assert entity.pdf_available is False
    assert entity.sections == {}
