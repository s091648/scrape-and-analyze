from src.shared.domain.entities import Article


def to_article_entity(row) -> Article:
    """Convert an ORM Article row to a domain Article entity.

    Shared by SqlAlchemyArticleRepository and AsyncSqlAlchemyArticleRepository —
    pure row->entity mapping, no session dependency, identical for both.
    """
    return Article(
        id=row.id,
        url=row.url,
        url_hash=row.url_hash,
        source=row.source,
        title=row.title,
        content=row.content,
        published_at=row.published_at,
        scraped_at=row.scraped_at,
        metadata=row.metadata_ or {},
        topic_id=row.topic_id,
        original_source=row.original_source,
    )


def to_article_model_kwargs(article: Article) -> dict:
    """Field mapping from a domain Article to ArticleModel constructor kwargs.

    Excludes correlation_id (legacy NOT NULL column, generated fresh per save
    by the caller — not part of the domain entity).
    """
    return dict(
        id=article.id,
        url=article.url,
        url_hash=article.url_hash,
        source=article.source,
        title=article.title,
        content=article.content,
        published_at=article.published_at,
        scraped_at=article.scraped_at,
        metadata_=article.metadata or {},
        topic_id=article.topic_id,
        original_source=article.original_source,
    )
