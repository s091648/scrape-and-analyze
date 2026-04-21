from uuid import uuid4
from src.shared.domain.entities import Article


def _article(**overrides):
    defaults = dict(
        url="https://arxiv.org/abs/x", url_hash="a" * 64,
        source="arxiv", title="T", content="Abstract.",
    )
    defaults.update(overrides)
    return Article(**defaults)


def test_get_analysis_content_uses_sections_for_arxiv():
    article = _article(metadata={"sections": {"introduction": "Intro.", "conclusion": "Concl."}})
    result = article.get_analysis_content()
    assert "Intro." in result
    assert "Concl." in result


def test_get_analysis_content_falls_back_to_abstract_when_single_section():
    article = _article(metadata={"sections": {"introduction": "Only one."},
                                  "abstract": "The abstract."})
    result = article.get_analysis_content()
    assert result == "The abstract."


def test_get_analysis_content_returns_content_for_rss():
    article = _article(source="rss", content="Full article body.")
    assert article.get_analysis_content() == "Full article body."