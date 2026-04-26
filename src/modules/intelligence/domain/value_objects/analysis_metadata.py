from dataclasses import dataclass


@dataclass
class AnalysisMetadata:
    """Metadata about an analysis, separate from the core AnalysisResult."""
    model_used: str
    input_tokens: int
    output_tokens: int
    