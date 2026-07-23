class DomainError(Exception):
    """Root of the domain exception hierarchy shared by all bounded contexts."""


class ValidationError(DomainError):
    """A domain-layer invariant was violated (business-rule validation, not request-shape validation)."""


class NotFoundError(DomainError):
    """A requested resource does not exist."""


class ConflictError(DomainError):
    """The requested operation conflicts with existing state (e.g. a uniqueness violation)."""


class UnauthorizedError(DomainError):
    """The caller's authentication is missing, invalid, or expired."""


class ForbiddenError(DomainError):
    """The caller is authenticated but not authorized to perform this action."""


class ExternalDependencyError(DomainError):
    """A required external dependency (LLM provider, metrics API, etc.) failed or was exhausted."""
