class InfrastructureConfigError(Exception):
    """Root of the infrastructure bootstrap/config exception hierarchy."""


class MissingR2ConfigError(InfrastructureConfigError):
    """Raised when required R2 blob storage environment variables are missing."""


class MissingDatabaseUrlError(InfrastructureConfigError):
    """Raised when DATABASE_URL is not configured."""


class MissingTelegramTokenError(InfrastructureConfigError):
    """Raised when a Telegram bot token is not configured."""
