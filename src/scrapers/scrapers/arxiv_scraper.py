import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List
from src.scrapers.scrapers.base_scraper import BaseScraper, ScrapedArticle
from src.scrapers.content_parsers.pdf_parser import PdfParser
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


class ArxivScraper(BaseScraper):
    """Scraper for arXiv API"""

    def __init__(self, max_results: int = 100, days_back: int = 7, fetch_pdf: bool = False):
        self.max_results = max_results
        self.days_back = days_back
        self.fetch_pdf = fetch_pdf
        self._pdf_parser = PdfParser() if fetch_pdf else None

    def _build_query(self) -> str:
        """Build arXiv search query for Digital Twins"""
        terms = [
            'ti:"digital twin"',
            'ti:"digital twins"',
            'abs:"digital twin"',
            'abs:"cyber-physical"',
        ]
        return ' OR '.join(terms)

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape arXiv API for Digital Twins papers"""
        query = self._build_query()

        params = {
            'search_query': query,
            'start': 0,
            'max_results': self.max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending',
        }

        try:
            response = requests.get(
                ARXIV_API_URL,
                params=params,
                timeout=60,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e))
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("arxiv_parse_failed", error=str(e))
            return []

        articles = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.days_back)

        for entry in root.findall(f'{ATOM_NS}entry'):
            title_elem = entry.find(f'{ATOM_NS}title')
            summary_elem = entry.find(f'{ATOM_NS}summary')
            published_elem = entry.find(f'{ATOM_NS}published')
            id_elem = entry.find(f'{ATOM_NS}id')

            title = title_elem.text.strip() if title_elem is not None else ''
            summary = (summary_elem.text or '').strip() if summary_elem is not None else ''
            published = published_elem.text if published_elem is not None else ''
            arxiv_id = id_elem.text if id_elem is not None else ''

            authors = []
            for author in entry.findall(f'{ATOM_NS}author'):
                name_elem = author.find(f'{ATOM_NS}name')
                if name_elem is not None:
                    authors.append(name_elem.text)

            link = ''
            for link_elem in entry.findall(f'{ATOM_NS}link'):
                if link_elem.get('rel') == 'alternate':
                    link = link_elem.get('href', '')
                    break

            if not link:
                link = arxiv_id

            try:
                pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
                if pub_date < cutoff_date:
                    continue
            except (ValueError, AttributeError):
                pass

            # Derive PDF URL from arxiv_id (which looks like http://arxiv.org/abs/2401.00001v1)
            pdf_url = arxiv_id.replace('/abs/', '/pdf/') if '/abs/' in arxiv_id else ''

            if self.fetch_pdf and pdf_url:
                full_text = self._pdf_parser.parse(pdf_url)
                content = full_text if full_text else summary
                pdf_available = bool(full_text)
            else:
                content = summary
                pdf_available = False

            articles.append(ScrapedArticle(
                url=link,
                title=title,
                content=content,
                published_at=published,
                source='arxiv',
                metadata={'authors': authors, 'arxiv_id': arxiv_id, 'abstract': summary, 'pdf_available': pdf_available}
            ))

        logger.info("arxiv_scrape_completed", articles_found=len(articles))
        return articles
