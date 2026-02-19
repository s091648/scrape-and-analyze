import pytest


def test_llm_provider_is_abstract():
    """LLMProvider should be abstract"""
    from src.analyzers.llm_provider import LLMProvider

    with pytest.raises(TypeError):
        LLMProvider()


def test_llm_provider_requires_analyze_method():
    """Subclass must implement analyze() method"""
    from src.analyzers.llm_provider import LLMProvider

    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_analysis_result_has_all_fields():
    """AnalysisResult should have all required fields"""
    from src.analyzers.llm_provider import AnalysisResult

    result = AnalysisResult(
        tags=["tag1", "tag2"],
        pain_points="Some pain points",
        insights="Key insights",
        innovations="New innovations",
        input_tokens=100,
        output_tokens=50
    )

    assert result.tags == ["tag1", "tag2"]
    assert result.pain_points == "Some pain points"
    assert result.insights == "Key insights"
    assert result.innovations == "New innovations"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
