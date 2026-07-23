from src.shared.domain.exceptions import DomainError, ValidationError


class IntelligenceDomainError(DomainError):
    """Root of the intelligence bounded context's domain exceptions."""


class InvalidSuggestionStatusError(ValidationError, IntelligenceDomainError):
    """Raised when a TagNormalizationSuggestion's status is not pending/approved/rejected."""


class InvalidSimilarityScoreError(ValidationError, IntelligenceDomainError):
    """Raised when a TagNormalizationSuggestion's similarity_score is outside [0.0, 1.0]."""


class InvalidWeeklyReportStatusError(ValidationError, IntelligenceDomainError):
    """Raised when a WeeklyReport's status is not pending/completed/failed."""
