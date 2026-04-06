import pytest


def test_llm_provider_is_abstract():
    """LLMProvider should be abstract"""
    from src.analysis.providers.base_llm_provider import LLMProvider

    with pytest.raises(TypeError):
        LLMProvider()


def test_llm_provider_requires_analyze_method():
    """Subclass must implement analyze() method"""
    from src.analysis.providers.base_llm_provider import LLMProvider

    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_analysis_result_has_all_fields():
    """AnalysisResult should have all required fields"""
    from src.analysis.providers.base_llm_provider import AnalysisResult

    result = AnalysisResult(
        tag_groups=[{"group": "digital_twin", "tags": ["virtual replica"]}],
        pain_points="Some pain points",
        insights="Key insights",
        innovations="New innovations",
        input_tokens=100,
        output_tokens=50
    )

    assert result.tag_groups == [{"group": "digital_twin", "tags": ["virtual replica"]}]
    assert result.pain_points == "Some pain points"
    assert result.insights == "Key insights"
    assert result.innovations == "New innovations"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_analysis_result_has_no_flat_tags_field():
    import dataclasses
    from src.analysis.providers.base_llm_provider import AnalysisResult
    field_names = {f.name for f in dataclasses.fields(AnalysisResult)}
    assert 'tags' not in field_names
