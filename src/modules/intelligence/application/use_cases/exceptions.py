from shared.domain.exceptions import ExternalDependencyError


class LLMAnalysisError(ExternalDependencyError):
    """Every configured LLM provider failed to produce an analysis."""


class LLMTranslationError(ExternalDependencyError):
    """Every configured LLM provider failed to produce a translation."""


class TranslationParseError(ExternalDependencyError):
    """The LLM's translation response could not be parsed into the expected sections."""
