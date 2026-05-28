from src.modules.intelligence.domain.value_objects import AnalysisPrompt, TagGroup


def _groups():
    return [
        TagGroup(name="research_methods", display_name="Research Methods", description=""),
        TagGroup(name="applications", display_name="Applications", description="Practical uses"),
    ]


def test_render_semi_fills_topic():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert "AI" in rendered.content


def test_render_semi_includes_existing_group_names():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert "research_methods" in rendered.content
    assert "applications" in rendered.content


def test_render_semi_allows_new_groups_in_instructions():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert "new" in rendered.content.lower() or "create" in rendered.content.lower()


def test_render_semi_returns_analysis_prompt_instance():
    prompt = AnalysisPrompt()
    result = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert isinstance(result, AnalysisPrompt)


def test_render_semi_with_empty_groups_still_renders():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=[])
    assert "AI" in rendered.content
