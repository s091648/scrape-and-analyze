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


# ── semantic_scholar source tests ─────────────────────────────────────────────

def test_get_analysis_content_semantic_scholar_with_sections():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://www.semanticscholar.org/paper/abc",
        url_hash="c" * 64,
        source="semantic_scholar",
        title="S2 Paper",
        content="Abstract.",
        metadata={"sections": {"intro": "text1", "methods": "text2"}, "abstract": "Abstract."},
    )
    result = a.get_analysis_content()
    assert "text1" in result
    assert "text2" in result


def test_get_analysis_content_semantic_scholar_no_sections():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://www.semanticscholar.org/paper/abc",
        url_hash="c" * 64,
        source="semantic_scholar",
        title="S2 Paper",
        content="Fallback content.",
        metadata={"abstract": "The abstract text."},
    )
    result = a.get_analysis_content()
    assert result == "The abstract text."


def test_get_analysis_content_semantic_scholar_empty_sections():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://www.semanticscholar.org/paper/abc",
        url_hash="c" * 64,
        source="semantic_scholar",
        title="S2 Paper",
        content="Fallback content.",
        metadata={"sections": {}, "abstract": "Short abstract."},
    )
    result = a.get_analysis_content()
    assert result == "Short abstract."


def test_get_analysis_content_non_paper_source():
    from src.shared.domain.entities import Article
    a = Article(
        url="https://example.com/post",
        url_hash="d" * 64,
        source="rss",
        title="Blog Post",
        content="rss content",
    )
    assert a.get_analysis_content() == "rss content"


def test_get_analysis_content_truncates_at_15000():
    from src.shared.domain.entities import Article
    long_body = "x" * 10_000
    a = Article(
        url="https://www.semanticscholar.org/paper/abc",
        url_hash="e" * 64,
        source="semantic_scholar",
        title="Big Paper",
        content="Abstract.",
        metadata={
            "sections": {
                "introduction": long_body,
                "methods": long_body,
            },
            "abstract": "Abstract.",
        },
    )
    result = a.get_analysis_content()
    assert len(result) <= 15_000