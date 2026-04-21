def test_article_dataclass():
    from src.shared.domain.entities import Article
    a = Article(url="http://x.com", url_hash="abc" * 21 + "ab",
                source="test", title="T", content="C")
    assert a.url == "http://x.com"
    assert a.metadata == {}
    assert a.topic_id is None


def test_article_get_analysis_content_uses_sections_for_arxiv():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://arxiv.org/abs/x", url_hash="a" * 64,
        source="arxiv", title="T", content="Abstract.",
        metadata={"sections": {"introduction": "Intro.", "conclusion": "Concl."}},
    )
    result = a.get_analysis_content()
    assert "Introduction" in result or "introduction" in result


def test_article_get_analysis_content_returns_abstract_when_no_sections():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://arxiv.org/abs/x", url_hash="a" * 64,
        source="arxiv", title="T", content="Fallback.",
        metadata={"abstract": "The abstract."},
    )
    result = a.get_analysis_content()
    assert result == "The abstract."


def test_article_get_analysis_content_returns_content_for_non_arxiv():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://example.com/a", url_hash="b" * 64,
        source="rss", title="T", content="Full article text.",
    )
    assert a.get_analysis_content() == "Full article text."