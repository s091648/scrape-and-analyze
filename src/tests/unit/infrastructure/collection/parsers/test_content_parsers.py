import pytest
import responses as _responses


def test_base_content_parser_is_abstract():
    from  src.infrastructure.collection.parsers.base_parser import BaseContentParser

    with pytest.raises(TypeError):
        BaseContentParser()


def test_base_content_parser_requires_parse():
    from  src.infrastructure.collection.parsers.base_parser import BaseContentParser

    class Incomplete(BaseContentParser):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_base_content_parser_prepare_for_analysis_default():
    """Default prepare_for_analysis returns content unchanged."""
    from  src.infrastructure.collection.parsers.base_parser import BaseContentParser

    class Concrete(BaseContentParser):
        def parse(self, content: str) -> str:
            return content

    parser = Concrete()
    assert parser.prepare_for_analysis("hello", fallback="fb") == "hello"


def test_html_parser_extracts_article_element():
    from  src.infrastructure.collection.parsers.html_parser import HtmlArticleParser

    html = '<html><body><article><p>Digital twins content</p></article></body></html>'
    parser = HtmlArticleParser()
    result = parser.parse(html)
    assert 'digital twins' in result.lower()


def test_html_parser_falls_back_to_main():
    from  src.infrastructure.collection.parsers.html_parser import HtmlArticleParser

    html = '<html><body><main><p>Twin content</p></main></body></html>'
    parser = HtmlArticleParser()
    result = parser.parse(html)
    assert 'twin' in result.lower()


def test_html_parser_returns_empty_for_no_match():
    from  src.infrastructure.collection.parsers.html_parser import HtmlArticleParser

    html = '<html><body><div class="sidebar">ads</div></body></html>'
    parser = HtmlArticleParser()
    result = parser.parse(html)
    assert result == ''


def test_html_parser_custom_selectors_take_priority():
    from  src.infrastructure.collection.parsers.html_parser import HtmlArticleParser

    html = '<html><body><div class="post-body"><p>Content here</p></div><article>wrong</article></body></html>'
    parser = HtmlArticleParser(selectors=['[class*="post-body"]'])
    result = parser.parse(html)
    assert 'Content here' in result
    assert 'wrong' not in result


@_responses.activate
def test_html_parser_fetch_and_parse_raises_on_transport_failure():
    from src.infrastructure.collection.parsers.html_parser import HtmlArticleParser
    from src.modules.collection.domain.exceptions import ArticleFetchError

    # @responses.activate raises ConnectionError immediately for unregistered URLs
    # (no real DNS query) so the test doesn't wait for a network timeout.
    parser = HtmlArticleParser()
    with pytest.raises(ArticleFetchError):
        parser.fetch_and_parse('https://this-domain-does-not-exist-xyz.invalid/article', fallback='fallback text')


@_responses.activate
def test_html_parser_fetch_and_parse_returns_fallback_on_no_selector_match():
    from src.infrastructure.collection.parsers.html_parser import HtmlArticleParser

    _responses.add(
        _responses.GET, "https://example.com/no-match-article",
        body='<html><body><div class="sidebar">ads</div></body></html>', status=200,
    )
    parser = HtmlArticleParser()
    result = parser.fetch_and_parse('https://example.com/no-match-article', fallback='fallback text')
    assert result == 'fallback text'


def test_pdf_parser_extract_sections_finds_standard_headers():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    text = """
Abstract
This paper studies digital twins.

1 Introduction
Digital twins are virtual replicas.

2 Methodology
We use simulation.

5 Conclusion
In this work we showed.
"""
    parser = PdfParser()
    sections = parser.extract_sections(text)
    assert 'abstract' in sections
    assert 'introduction' in sections
    assert 'methodology' in sections
    assert 'conclusion' in sections


def test_pdf_parser_extract_sections_handles_numbered_headings():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    text = "1. Introduction\nSome intro text.\n2. Methods\nSome method text."
    parser = PdfParser()
    sections = parser.extract_sections(text)
    assert 'introduction' in sections


def test_pdf_parser_prepare_for_analysis_uses_sections_when_found():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    full_text = """
Abstract
We study digital twins systems.

1 Introduction
Background on digital twins.

2 Methodology
Experimental setup.

Conclusion
We demonstrated results.
"""
    parser = PdfParser()
    result = parser.prepare_for_analysis(full_text, fallback='original abstract')
    assert 'digital twins' in result.lower()
    # Should NOT return the fallback when sections found
    assert result != 'original abstract'


def test_pdf_parser_prepare_for_analysis_falls_back_when_no_sections():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    # Text with no recognisable section headings
    full_text = "This is a short document with no headers at all."
    parser = PdfParser()
    result = parser.prepare_for_analysis(full_text, fallback='original abstract')
    assert result == 'original abstract'


def test_pdf_parser_prepare_for_analysis_caps_at_max_chars():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    long_text = "Abstract\n" + "x" * 50_000 + "\n1 Introduction\n" + "y" * 50_000
    parser = PdfParser(max_chars=100)
    result = parser.prepare_for_analysis(long_text, fallback='fb')
    assert len(result) <= 100


@_responses.activate
def test_pdf_parser_parse_returns_text_on_http_failure():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    # @responses.activate raises ConnectionError immediately for unregistered URLs.
    parser = PdfParser()
    result = parser.parse('https://this-domain-does-not-exist-xyz.invalid/paper.pdf')
    assert result == ''


def test_pdf_parser_sanitize_removes_null_bytes():
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    parser = PdfParser()
    result = parser._sanitize("hello\x00world\x00!")
    assert "\x00" not in result
    assert result == "hello world !"


def test_pdf_parser_extract_sections_normalizes_conclusions_to_conclusion():
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    text = "\nAbstract\nSome abstract text.\n\nConclusions\nFinal thoughts here.\n"
    parser = PdfParser()
    sections = parser.extract_sections(text)
    assert "conclusion" in sections
    assert "conclusions" not in sections


def test_pdf_parser_extract_sections_normalizes_methods_to_methodology():
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    text = "\nAbstract\nSome abstract text.\n\nMethods\nOur experimental approach.\n"
    parser = PdfParser()
    sections = parser.extract_sections(text)
    assert "methodology" in sections
    assert "methods" not in sections


def test_pdf_parser_prepare_for_analysis_falls_back_when_only_one_section():
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    # Only one target section — less than 2, so falls back
    text = "\nAbstract\nOnly one section found here.\n"
    parser = PdfParser()
    result = parser.prepare_for_analysis(text, fallback="use this fallback")
    assert result == "use this fallback"


def test_pdf_parser_extract_sections_returns_empty_for_non_target_sections_only():
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    # 'Discussion' and 'Results' are not in TARGET_SECTIONS → extract_sections returns {}
    text = "\nDiscussion\nWe discuss the implications.\n\nResults\nWe found significant effects.\n"
    parser = PdfParser()
    sections = parser.extract_sections(text)
    # 'discussion' and 'results' are not in TARGET_SECTIONS frozenset
    assert "discussion" not in sections
    assert "results" not in sections


def test_pdf_parser_parse_successful_pdf(monkeypatch):
    """parse() returns extracted text when fitz opens the PDF successfully."""
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    from unittest.mock import patch, MagicMock

    mock_page = MagicMock()
    mock_page.get_text.return_value = "Page one content."
    mock_doc = MagicMock()
    mock_doc.__enter__ = lambda self: self
    mock_doc.__exit__ = MagicMock(return_value=False)
    mock_doc.__iter__ = lambda self: iter([mock_page])

    mock_response = MagicMock()
    mock_response.content = b"%PDF-1.4 fake"

    with patch("src.infrastructure.collection.parsers.pdf_parser.get_default_client") as mock_client, \
         patch("fitz.open", return_value=mock_doc):
        mock_client.return_value.get.return_value = mock_response
        parser = PdfParser()
        result = parser.parse("https://example.com/paper.pdf")

    assert result == "Page one content."


def test_pdf_parser_parse_returns_empty_when_fitz_raises(monkeypatch):
    """parse() returns '' when fitz.open raises an exception."""
    from src.infrastructure.collection.parsers.pdf_parser import PdfParser
    from unittest.mock import patch, MagicMock

    mock_response = MagicMock()
    mock_response.content = b"not a pdf"

    with patch("src.infrastructure.collection.parsers.pdf_parser.get_default_client") as mock_client, \
         patch("fitz.open", side_effect=Exception("Invalid PDF format")):
        mock_client.return_value.get.return_value = mock_response
        parser = PdfParser()
        result = parser.parse("https://example.com/bad.pdf")

    assert result == ""
