import re
import fitz  # pymupdf
from .base_parser import BaseContentParser
from src.shared.logging import get_logger
from src.infrastructure.shared.http import get_default_client

logger = get_logger(__name__)

# Regex patterns for common academic section headings
_HEADING_PATTERN = re.compile(
    r'^\s*(?:\d+[\.\s]+)?\s*'
    r'(abstract|introduction|related\s+work|background|method(?:ology|s)?'
    r'|experiment(?:s|al\s+setup)?|result(?:s)?|discussion|conclusion(?:s)?|summary)'
    r'\s*$',
    re.IGNORECASE | re.MULTILINE,
)

TARGET_SECTIONS = frozenset([
    'abstract', 'introduction', 'methodology', 'methods',
    'conclusion', 'conclusions', 'summary',
])


class PdfParser(BaseContentParser):
    """Downloads PDFs and extracts full text plus heuristic section splitting."""

    def __init__(self, max_chars: int = 15_000):
        self.max_chars = max_chars

    def parse(self, pdf_url: str) -> str:
        """Download PDF from URL and return full extracted text. Returns '' on failure."""
        try:
            response = get_default_client().get(pdf_url, timeout=60)
        except Exception as e:
            logger.warning('pdf_download_failed', url=pdf_url, error=str(e))
            return ''

        try:
            with fitz.open(stream=response.content, filetype='pdf') as doc:
                pages = [page.get_text() for page in doc]
            return self._sanitize('\n'.join(pages))
        except Exception as e:
            logger.warning('pdf_parse_failed', url=pdf_url, error=str(e))
            return ''

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove characters that are invalid in PostgreSQL text columns."""
        return text.replace('\x00', ' ')

    def extract_sections(self, text: str) -> dict[str, str]:
        """
        Heuristic extraction of target sections from plain text.
        Returns dict mapping normalised section name → content.
        """
        matches = list(_HEADING_PATTERN.finditer(text))
        if not matches:
            return {}

        sections: dict[str, str] = {}
        for i, match in enumerate(matches):
            name = match.group(1).lower().strip()
            if name in ('methods', 'methodology'):
                name = 'methodology'
            if name in ('conclusions',):
                name = 'conclusion'
            if name not in TARGET_SECTIONS:
                continue
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[name] = self._sanitize(text[start:end].strip())

        return sections

    def prepare_for_analysis(self, content: str, fallback: str = '') -> str:
        """
        Returns LLM-ready text:
        - If >= 2 target sections found: concatenated sections (capped at max_chars)
        - Otherwise: fallback (original arXiv abstract)
        """
        sections = self.extract_sections(content)
        if len(sections) >= 2:
            combined = '\n\n'.join(
                f'{name.title()}\n{body}' for name, body in sections.items()
            )
            return combined[:self.max_chars]
        return fallback