import pytest


def test_base_provider_is_abstract():
    from src.infrastructure.intelligence.llm.providers.base_provider import BaseProvider
    with pytest.raises(TypeError):
        BaseProvider(model="test")


def test_base_provider_requires_call_api_method():
    from src.infrastructure.intelligence.llm.providers.base_provider import BaseProvider

    class Incomplete(BaseProvider):
        pass

    with pytest.raises(TypeError):
        Incomplete(model="test")


def test_analysis_content_has_all_fields():
    from src.modules.intelligence.domain.value_objects import AnalysisContent, TagGroup
    content = AnalysisContent(
        tag_groups=[],
        pain_points="Some pain points",
        insights="Key insights",
        innovations="New innovations",
        summary="A brief summary.",
    )
    assert content.pain_points == "Some pain points"
    assert content.insights == "Key insights"
    assert content.innovations == "New innovations"
    assert content.tag_groups == []


def test_analysis_metadata_has_all_fields():
    from src.modules.intelligence.domain.value_objects import AnalysisMetadata
    metadata = AnalysisMetadata(
        model_used="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
    )
    assert metadata.model_used == "claude-sonnet-4-6"
    assert metadata.input_tokens == 100
    assert metadata.output_tokens == 50


def test_analysis_content_has_no_flat_tags_field():
    import dataclasses
    from src.modules.intelligence.domain.value_objects import AnalysisContent
    field_names = {f.name for f in dataclasses.fields(AnalysisContent)}
    assert 'tags' not in field_names