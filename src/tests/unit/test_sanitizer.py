import pytest


def test_sanitize_content_removes_script_tags():
    """sanitize_content should remove script tags"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService

    html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
    result = SanitizeService.sanitize_content(html)

    assert "script" not in result.lower()
    assert "alert" not in result
    assert "Hello" in result
    assert "World" in result


def test_sanitize_content_removes_style_tags():
    """sanitize_content should remove style tags"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService

    html = "<p>Hello</p><style>.hidden{display:none}</style>"
    result = SanitizeService.sanitize_content(html)

    assert "style" not in result.lower()
    assert "display" not in result


def test_sanitize_content_removes_nav_footer():
    """sanitize_content should remove nav and footer elements"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService

    html = "<nav>Navigation</nav><main>Content</main><footer>Footer</footer>"
    result = SanitizeService.sanitize_content(html)

    assert "Navigation" not in result
    assert "Footer" not in result
    assert "Content" in result


def test_sanitize_content_preserves_text_with_newlines():
    """sanitize_content should preserve text with paragraph breaks"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService

    html = "<p>Paragraph 1</p><p>Paragraph 2</p>"
    result = SanitizeService.sanitize_content(html)

    assert "Paragraph 1" in result
    assert "Paragraph 2" in result
    assert "\n" in result


def test_sanitize_content_handles_empty_input():
    """sanitize_content should handle empty input"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService

    assert SanitizeService.sanitize_content("") == ""
    assert SanitizeService.sanitize_content(None) == ""


def test_sanitize_content_truncates_long_content():
    """sanitize_content should truncate content exceeding MAX_LENGTH"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService, MAX_CONTENT_LENGTH

    long_content = "<p>" + "a" * (MAX_CONTENT_LENGTH + 1000) + "</p>"
    result = SanitizeService.sanitize_content(long_content)

    assert len(result) <= MAX_CONTENT_LENGTH + 20  # +20 for truncation message
    assert "[Content truncated]" in result


def test_sanitize_content_does_not_truncate_short_content():
    """sanitize_content should not truncate content under MAX_LENGTH"""
    from src.infrastructure.collection.parsers.sanitize_service import SanitizeService

    short_content = "<p>Short content</p>"
    result = SanitizeService.sanitize_content(short_content)

    assert "[Content truncated]" not in result


def test_generate_url_hash_returns_sha256():
    """generate_url_hash should return 64-character SHA-256 hash"""
    from src.modules.collection.domain.value_objects import UrlHash

    url = "https://example.com/article/123"
    result = UrlHash.generate_url_hash(url)

    assert len(result) == 64
    assert result.isalnum()


def test_generate_url_hash_is_deterministic():
    """Same URL should always produce same hash"""
    from src.modules.collection.domain.value_objects import UrlHash

    url = "https://example.com/article/123"
    hash1 = UrlHash.generate_url_hash(url)
    hash2 = UrlHash.generate_url_hash(url)

    assert hash1 == hash2


def test_generate_url_hash_different_for_different_urls():
    """Different URLs should produce different hashes"""
    from src.modules.collection.domain.value_objects import UrlHash

    hash1 = UrlHash.generate_url_hash("https://example.com/1")
    hash2 = UrlHash.generate_url_hash("https://example.com/2")

    assert hash1 != hash2


def test_generate_url_hash_handles_unicode():
    """generate_url_hash should handle unicode URLs"""
    from src.modules.collection.domain.value_objects import UrlHash

    url = "https://example.com/文章/数字孪生"
    result = UrlHash.generate_url_hash(url)

    assert len(result) == 64
    assert result.isalnum()


def test_generate_url_hash_handles_special_characters():
    """generate_url_hash should handle special characters in URLs"""
    from src.modules.collection.domain.value_objects import UrlHash

    url = "https://example.com/article?id=123&name=test%20article"
    result = UrlHash.generate_url_hash(url)

    assert len(result) == 64


def test_generate_url_hash_empty_string():
    """generate_url_hash should handle empty string"""
    from src.modules.collection.domain.value_objects import UrlHash

    result = UrlHash.generate_url_hash("")
    assert len(result) == 64  # SHA-256 of empty string