from src.shared.domain.exceptions import DomainError


class IntelligenceDomainError(DomainError):
    """Root of the intelligence bounded context's domain exceptions."""


class InvalidSuggestionStatusError(IntelligenceDomainError):
    """Raised when a TagNormalizationSuggestion's status is not pending/approved/rejected."""


class InvalidSimilarityScoreError(IntelligenceDomainError):
    """Raised when a TagNormalizationSuggestion's similarity_score is outside [0.0, 1.0]."""


class InvalidWeeklyReportStatusError(IntelligenceDomainError):
    """Raised when a WeeklyReport's status is not pending/completed/failed."""
