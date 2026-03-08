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
