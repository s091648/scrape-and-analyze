def test_arxiv_metadata_defaults():
    from uuid import uuid4
    from src.modules.collection.domain.entities import ArxivMetadata
    entity = ArxivMetadata(article_id=uuid4())
    assert entity.id is not None
    assert entity.authors == []
    assert entity.pdf_available is False
    assert entity.sections == {}