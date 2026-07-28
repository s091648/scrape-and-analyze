"""Covers build_selector_config's translation of the admin UI's flat blog
shape ({article_link, title, content}) into BlogConfig.selectors — the shape
BlogScraper actually reads. Without this translation, values entered in
frontend/app/admin/scraper-settings are silently discarded and BlogScraper
falls back to its wide-open defaults (links="a", title="h1", content="article").

Also covers BlogConfig's own invariant (a non-empty 'links' selector is
required) and its translation into the shared domain ValidationError at the
build_selector_config() boundary, instead of a raw pydantic.ValidationError."""
import pytest

from shared.domain.exceptions import ValidationError
from shared.selector_config import BlogConfig, build_selector_config


def test_build_selector_config_translates_admin_ui_flat_blog_shape():
    raw = {
        "article_link": ".blog-post a.title",
        "title": "h1.blog-post-title",
        "content": ".blog-post-content",
    }
    cfg = build_selector_config("blog", raw)
    assert isinstance(cfg, BlogConfig)
    assert cfg.selectors == {
        "links": ".blog-post a.title",
        "title": "h1.blog-post-title",
        "content": ".blog-post-content",
    }


def test_build_selector_config_blog_empty_raw_raises_validation_error():
    """A blog source with no 'links' selector configured must fail loudly at
    construction, not silently produce a BlogConfig that later falls back to
    BlogScraper's wide-open "a" default."""
    with pytest.raises(ValidationError):
        build_selector_config("blog", {})


def test_build_selector_config_blog_prefers_pre_nested_selectors_shape():
    """If a "selectors" key is already present (e.g. seeded/legacy data), use it as-is."""
    raw = {"selectors": {"links": "a.post", "title": "h1", "content": ".body"}}
    cfg = build_selector_config("blog", raw)
    assert cfg.selectors == {"links": "a.post", "title": "h1", "content": ".body"}


def test_build_selector_config_blog_missing_links_raises_validation_error():
    """Only title/content set, no article_link/links — must raise, not silently
    produce a config missing the one selector BlogScraper actually needs."""
    with pytest.raises(ValidationError):
        build_selector_config("blog", {"title": "h1.headline"})


def test_build_selector_config_respects_type_discriminator():
    """New-style data with an explicit 'type' key bypasses the legacy translation entirely."""
    raw = {"type": "blog", "selectors": {"links": "a.x"}}
    cfg = build_selector_config("blog", raw)
    assert cfg.selectors == {"links": "a.x"}


def test_build_selector_config_type_discriminator_still_enforces_invariant():
    """Even new-style typed data must satisfy BlogConfig's own invariant."""
    raw = {"type": "blog", "selectors": {"title": "h1"}}
    with pytest.raises(ValidationError):
        build_selector_config("blog", raw)


def test_blog_config_rejects_empty_links_selector_directly():
    """The value object itself refuses to be constructed without a 'links' selector —
    this must hold even when BlogConfig is instantiated directly, not just through
    build_selector_config()."""
    with pytest.raises(Exception):
        BlogConfig(selectors={"title": "h1", "content": ".body"})


def test_blog_config_accepts_valid_selectors():
    cfg = BlogConfig(selectors={"links": "h2.post-title a", "title": "h1", "content": ".body"})
    assert cfg.selectors["links"] == "h2.post-title a"
