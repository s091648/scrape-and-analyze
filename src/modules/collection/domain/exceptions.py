from shared.domain.exceptions import DomainError, ExternalDependencyError, ValidationError


class CollectionDomainError(DomainError):
    """Root of the collection bounded context's domain exceptions."""


class ArticleFetchError(ExternalDependencyError, CollectionDomainError):
    """Raised when fetching an article's full HTML body fails (network error, timeout, non-2xx after retries)."""


class InvalidUrlHashError(ValidationError, CollectionDomainError):
    """Raised when a UrlHash value is not a valid 64-char hex SHA-256 digest."""


class InvalidScraperKeywordTypeError(ValidationError, CollectionDomainError):
    """Raised when a scraper keyword's type does not match any known ScraperKeywordVO variant."""


class UnsupportedSourceTypeError(ValidationError, CollectionDomainError):
    """Raised when a ScraperSetting's source_type cannot be resolved to a scraper implementation."""


class InvalidScraperIntervalError(ValidationError, CollectionDomainError):
    """Raised when a ScraperSetting's interval_hours is not a positive number."""
