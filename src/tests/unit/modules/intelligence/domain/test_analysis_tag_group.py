def test_analysis_tag_group_holds_group_name_and_tags():
    from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
    tg = AnalysisTagGroup(group_name="digital_twin", tags=["virtual replica", "real-time sync"])
    assert tg.group_name == "digital_twin"
    assert tg.tags == ["virtual replica", "real-time sync"]


def test_analysis_content_tag_groups_uses_analysis_tag_group():
    from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
    from src.modules.intelligence.domain.value_objects.analysis_content import AnalysisContent
    tg = AnalysisTagGroup(group_name="g", tags=["t1"])
    content = AnalysisContent(tag_groups=[tg], pain_points=None, insights=None, innovations=None, summary=None)
    assert content.tag_groups[0].group_name == "g"
    assert content.tag_groups[0].tags == ["t1"]


def test_base_provider_parse_creates_analysis_tag_groups():
    from unittest.mock import MagicMock, patch
    from src.infrastructure.intelligence.llm.providers.base_provider import BaseProvider

    class ConcreteProvider(BaseProvider):
        def _call_api(self, content, prompt): return {}
        def _call_api_raw(self, content, prompt): return ""

    provider = ConcreteProvider(model="test")
    raw = {
        "tag_groups": [{"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]}],
        "pain_points": "p", "insights": "i", "innovations": "n", "summary": "s",
        "_input_tokens": 10, "_output_tokens": 5,
    }
    content, _ = provider._parse_result(raw)
    from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
    assert isinstance(content.tag_groups[0], AnalysisTagGroup)
    assert content.tag_groups[0].group_name == "digital_twin"
    assert content.tag_groups[0].tags == ["virtual replica", "real-time sync"]
