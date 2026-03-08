from src.scrapers.content_parsers.base_parser import BaseContentParser
from src.scrapers.content_parsers.html_parser import HtmlArticleParser
from src.scrapers.content_parsers.pdf_parser import PdfParser


def prepare_content_for_analysis(article) -> str:
    """Return LLM-ready content for an article, applying source-specific extraction."""
    if article.source == 'arxiv':
        parser = PdfParser()
        sections = parser.extract_sections(article.content)
        if len(sections) >= 2:
            combined = '\n\n'.join(
                f'{name.title()}\n{body}' for name, body in sections.items()
            )
            return combined[:parser.max_chars]
        # Fallback: original abstract stored at scrape time
        metadata = article.metadata_ or {}
        return metadata.get('abstract', article.content[:2000])
    return article.content


__all__ = ["BaseContentParser", "HtmlArticleParser", "PdfParser", "prepare_content_for_analysis"]
