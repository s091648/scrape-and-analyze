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


# ── US2: render_auto ──────────────────────────────────────────────────────────

def test_render_auto_fills_topic_name():
    prompt = AnalysisPrompt()
    rendered = prompt.render_auto(topic="Robotics")
    assert "Robotics" in rendered.content
    assert isinstance(rendered, AnalysisPrompt)


def test_render_auto_uses_free_classification_instruction():
    prompt = AnalysisPrompt()
    rendered = prompt.render_auto(topic="Robotics")
    assert "of your choosing" in rendered.content
    assert "ONLY these exact key strings" not in rendered.content


# ── US2: render_fixed ─────────────────────────────────────────────────────────

def test_render_fixed_fills_topic_name():
    groups = [TagGroup(name="hardware", display_name="Hardware", description="")]
    prompt = AnalysisPrompt()
    rendered = prompt.render_fixed(topic="Robotics", tag_groups=groups)
    assert "Robotics" in rendered.content


def test_render_fixed_constrains_to_predefined_keys():
    groups = [
        TagGroup(name="hardware", display_name="Hardware", description=""),
        TagGroup(name="software", display_name="Software", description=""),
    ]
    prompt = AnalysisPrompt()
    rendered = prompt.render_fixed(topic="Robotics", tag_groups=groups)
    assert "hardware" in rendered.content
    assert "software" in rendered.content
    assert "ONLY these exact key strings" in rendered.content


def test_render_fixed_returns_analysis_prompt_instance():
    groups = [TagGroup(name="methods", display_name="Methods", description="")]
    prompt = AnalysisPrompt()
    result = prompt.render_fixed(topic="AI", tag_groups=groups)
    assert isinstance(result, AnalysisPrompt)
