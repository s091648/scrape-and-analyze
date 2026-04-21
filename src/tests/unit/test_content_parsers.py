import pytest


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


def test_html_parser_fetch_and_parse_returns_fallback_on_error():
    from  src.infrastructure.collection.parsers.html_parser import HtmlArticleParser

    # Bad URL — should return fallback, not raise
    parser = HtmlArticleParser()
    result = parser.fetch_and_parse('https://this-domain-does-not-exist-xyz.invalid/article', fallback='fallback text')
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


def test_pdf_parser_parse_returns_text_on_http_failure():
    from  src.infrastructure.collection.parsers.pdf_parser import PdfParser

    parser = PdfParser()
    # Bad URL — should return empty string, not raise
    result = parser.parse('https://this-domain-does-not-exist-xyz.invalid/paper.pdf')
    assert result == ''
