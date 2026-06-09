"""
Unit tests for translation prompt value objects — covers rendering,
placeholder substitution, language name mapping, and format_group helper.
"""
from src.modules.intelligence.domain.value_objects import (
    ArticleTranslationPrompt,
    ArticleBodyTranslationPrompt,
    TagTranslationPrompt,
    GroupTranslationPrompt,
    LANGUAGE_NAMES,
)


# ── ArticleTranslationPrompt ─────────────────────────────────────────────────

def test_article_prompt_render_substitutes_all_placeholders():
    prompt = ArticleTranslationPrompt()
    rendered = prompt.render(
        target_language="zh-TW",
        summary="A summary",
        pain_points="Some pain",
        insights="An insight",
        innovations="An innovation",
    )
    assert "Traditional Chinese (Taiwan)" in rendered.content
    assert "A summary" in rendered.content
    assert "Some pain" in rendered.content
    assert "An insight" in rendered.content
    assert "An innovation" in rendered.content
    assert "__TARGET_LANGUAGE__" not in rendered.content
    assert "__SUMMARY__" not in rendered.content
    assert "__PAIN_POINTS__" not in rendered.content
    assert "__INSIGHTS__" not in rendered.content
    assert "__INNOVATIONS__" not in rendered.content


def test_article_prompt_render_returns_article_prompt_instance():
    prompt = ArticleTranslationPrompt()
    rendered = prompt.render(
        target_language="zh-TW", summary="s", pain_points="p", insights="i", innovations="n"
    )
    assert isinstance(rendered, ArticleTranslationPrompt)


# ── TagTranslationPrompt ────────────────────────────────────────────────────

def test_tag_prompt_render_substitutes_target_language_and_tags():
    prompt = TagTranslationPrompt()
    rendered = prompt.render(target_language="ja", tags=["AI", "IoT", "digital twin"])
    assert "Japanese" in rendered.content
    assert "AI" in rendered.content
    assert "IoT" in rendered.content
    assert "digital twin" in rendered.content
    assert "__TARGET_LANGUAGE__" not in rendered.content
    assert "__TAGS__" not in rendered.content


def test_tag_prompt_render_returns_tag_prompt_instance():
    prompt = TagTranslationPrompt()
    rendered = prompt.render(target_language="ko", tags=["test"])
    assert isinstance(rendered, TagTranslationPrompt)


# ── GroupTranslationPrompt ──────────────────────────────────────────────────

def test_group_prompt_render_substitutes_target_language_and_groups():
    prompt = GroupTranslationPrompt()
    rendered = prompt.render(target_language="fr", groups=["Technology | Description here"])
    assert "French" in rendered.content
    assert "Technology | Description here" in rendered.content
    assert "__TARGET_LANGUAGE__" not in rendered.content
    assert "__GROUPS__" not in rendered.content


def test_group_prompt_render_returns_group_prompt_instance():
    prompt = GroupTranslationPrompt()
    rendered = prompt.render(target_language="de", groups=["test"])
    assert isinstance(rendered, GroupTranslationPrompt)


def test_format_group_with_description():
    result = GroupTranslationPrompt.format_group("AI Tools", "Tools for AI")
    assert result == "AI Tools | Tools for AI"


def test_format_group_without_description():
    result = GroupTranslationPrompt.format_group("AI Tools", None)
    assert result == "AI Tools | "


def test_format_group_with_empty_description():
    result = GroupTranslationPrompt.format_group("AI Tools", "")
    assert result == "AI Tools | "


# ── LANGUAGE_NAMES mapping ──────────────────────────────────────────────────

def test_language_names_known_codes_return_display_names():
    assert LANGUAGE_NAMES["zh-TW"] == "Traditional Chinese (Taiwan)"
    assert LANGUAGE_NAMES["zh-CN"] == "Simplified Chinese"
    assert LANGUAGE_NAMES["ja"] == "Japanese"
    assert LANGUAGE_NAMES["ko"] == "Korean"
    assert LANGUAGE_NAMES["es"] == "Spanish"
    assert LANGUAGE_NAMES["fr"] == "French"
    assert LANGUAGE_NAMES["de"] == "German"


def test_language_names_unknown_code_falls_back_to_code():
    prompt = ArticleTranslationPrompt()
    rendered = prompt.render(
        target_language="xx-YY", summary="s", pain_points="p", insights="i", innovations="n"
    )
    assert "xx-YY" in rendered.content


def test_all_supported_codes_in_language_names():
    expected_codes = {"zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de"}
    assert set(LANGUAGE_NAMES.keys()) == expected_codes


# ── ArticleBodyTranslationPrompt ─────────────────────────────────────────────

def test_body_prompt_render_substitutes_all_placeholders():
    prompt = ArticleBodyTranslationPrompt()
    rendered = prompt.render(
        target_language="zh-TW",
        title="A great paper",
        content="This paper describes...",
    )
    assert "Traditional Chinese (Taiwan)" in rendered.content
    assert "A great paper" in rendered.content
    assert "This paper describes..." in rendered.content
    assert "__TARGET_LANGUAGE__" not in rendered.content
    assert "__TITLE__" not in rendered.content
    assert "__CONTENT__" not in rendered.content


def test_body_prompt_render_returns_body_prompt_instance():
    prompt = ArticleBodyTranslationPrompt()
    rendered = prompt.render(target_language="zh-TW", title="t", content="c")
    assert isinstance(rendered, ArticleBodyTranslationPrompt)


def test_body_prompt_render_unknown_language_falls_back_to_code():
    prompt = ArticleBodyTranslationPrompt()
    rendered = prompt.render(target_language="xx-ZZ", title="t", content="c")
    assert "xx-ZZ" in rendered.content


def test_body_prompt_parse_response_splits_title_and_content():
    text = "Title: My Translated Title\nContent: This is the translated body."
    title, content = ArticleBodyTranslationPrompt.parse_response(text)
    assert title == "My Translated Title"
    assert content == "This is the translated body."


def test_body_prompt_parse_response_handles_multiline_content():
    text = "Title: Short Title\nContent: Line one.\nLine two.\nLine three."
    title, content = ArticleBodyTranslationPrompt.parse_response(text)
    assert title == "Short Title"
    assert "Line one." in content
    assert "Line two." in content


def test_body_prompt_parse_response_handles_missing_content_section():
    text = "Title: Only Title Here"
    title, content = ArticleBodyTranslationPrompt.parse_response(text)
    assert title == "Only Title Here"
    assert content is None


def test_body_prompt_parse_response_handles_full_width_colon():
    text = "Title：全形冒號標題\nContent：全形冒號內容"
    title, content = ArticleBodyTranslationPrompt.parse_response(text)
    assert title == "全形冒號標題"
    assert content == "全形冒號內容"


def test_body_prompt_parse_response_case_insensitive():
    text = "TITLE: Uppercase title\nCONTENT: Uppercase content"
    title, content = ArticleBodyTranslationPrompt.parse_response(text)
    assert title == "Uppercase title"
    assert content == "Uppercase content"
