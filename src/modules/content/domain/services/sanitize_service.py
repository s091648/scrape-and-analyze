from bs4 import BeautifulSoup
from typing import Optional

MAX_CONTENT_LENGTH = 50_000


class SanitizeService:
    @staticmethod
    def sanitize_content(raw_html: Optional[str]) -> str:
        """Convert HTML to plain text and sanitize"""
        if not raw_html:
            return ""

        soup = BeautifulSoup(raw_html, 'html.parser')

        # Remove unwanted tags
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
            tag.decompose()

        # Extract text with newlines between elements
        text = soup.get_text(separator='\n', strip=True)

        # Truncate if needed
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + "\n[Content truncated]"

        return text
