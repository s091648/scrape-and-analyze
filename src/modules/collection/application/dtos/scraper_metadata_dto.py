from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ScraperMetadataDTO:
    """
    Application DTO - 統一的 scraper metadata 結構。

    取代原本放在 domain/entities/ 的 ScrapeJobMetadata (arxiv-specific)。
    這個 DTO 支援所有 scraper 類型的 metadata 結構。

    欄位說明：
    - source_specific: 存放各 scraper 特有的欄位
      - arxiv: arxiv_id, pdf_url, abstract, authors, published
      - rss: author, description
      - blog: (目前無額外欄位)
    """
    source_type: str
    source_specific: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_arxiv(
        cls,
        arxiv_id: Optional[str] = None,
        abstract: Optional[str] = None,
        pdf_url: Optional[str] = None,
        authors: Optional[list] = None,
        published: Optional[str] = None,
    ) -> "ScraperMetadataDTO":
        return cls(
            source_type="arxiv",
            source_specific={
                "arxiv_id": arxiv_id,
                "abstract": abstract,
                "pdf_url": pdf_url,
                "authors": authors or [],
                "published": published,
            },
        )

    @classmethod
    def for_rss(
        cls,
        title: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        published: Optional[str] = None,
    ) -> "ScraperMetadataDTO":
        return cls(
            source_type="rss",
            source_specific={
                "title": title,
                "description": description,
                "author": author,
                "published": published,
            },
        )

    @classmethod
    def for_blog(cls) -> "ScraperMetadataDTO":
        return cls(source_type="blog", source_specific={})

    def get(self, key: str, default: Any = None) -> Any:
        """取得 source_specific 中的欄位"""
        return self.source_specific.get(key, default)