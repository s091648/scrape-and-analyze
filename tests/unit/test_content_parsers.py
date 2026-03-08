import pytest


def test_base_content_parser_is_abstract():
    from src.scrapers.content_parsers.base_parser import BaseContentParser

    with pytest.raises(TypeError):
        BaseContentParser()


def test_base_content_parser_requires_parse():
    from src.scrapers.content_parsers.base_parser import BaseContentParser

    class Incomplete(BaseContentParser):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_base_content_parser_prepare_for_analysis_default():
    """Default prepare_for_analysis returns content unchanged."""
    from src.scrapers.content_parsers.base_parser import BaseContentParser

    class Concrete(BaseContentParser):
        def parse(self, content: str) -> str:
            return content

    parser = Concrete()
    assert parser.prepare_for_analysis("hello", fallback="fb") == "hello"


def test_html_parser_extracts_article_element():
    from src.scrapers.content_parsers.html_parser import HtmlArticleParser

    html = '<html><body><article><p>Digital twins content</p></article></body></html>'
    parser = HtmlArticleParser()
    result = parser.parse(html)
    assert 'digital twins' in result.lower()


def test_html_parser_falls_back_to_main():
    from src.scrapers.content_parsers.html_parser import HtmlArticleParser

    html = '<html><body><main><p>Twin content</p></main></body></html>'
    parser = HtmlArticleParser()
    result = parser.parse(html)
    assert 'twin' in result.lower()


def test_html_parser_returns_empty_for_no_match():
    from src.scrapers.content_parsers.html_parser import HtmlArticleParser

    html = '<html><body><div class="sidebar">ads</div></body></html>'
    parser = HtmlArticleParser()
    result = parser.parse(html)
    assert result == ''


def test_html_parser_custom_selectors_take_priority():
    from src.scrapers.content_parsers.html_parser import HtmlArticleParser

    html = '<html><body><div class="post-body"><p>Content here</p></div><article>wrong</article></body></html>'
    parser = HtmlArticleParser(selectors=['[class*="post-body"]'])
    result = parser.parse(html)
    assert 'Content here' in result
    assert 'wrong' not in result


def test_html_parser_fetch_and_parse_returns_fallback_on_error():
    from src.scrapers.content_parsers.html_parser import HtmlArticleParser

    # Bad URL — should return fallback, not raise
    parser = HtmlArticleParser()
    result = parser.fetch_and_parse('https://this-domain-does-not-exist-xyz.invalid/article', fallback='fallback text')
    assert result == 'fallback text'
