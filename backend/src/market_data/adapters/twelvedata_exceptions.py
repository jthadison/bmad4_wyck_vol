"""
TwelveData API Exception Classes (Story 21.1)

Provides custom exceptions for TwelveData API error handling:
- TwelveDataAPIError: Base exception for all TwelveData errors
- TwelveDataAuthError: Invalid API key (HTTP 401)
- TwelveDataRateLimitError: Rate limit exceeded (HTTP 429)
- TwelveDataTimeoutError: Request timeout
- TwelveDataConfigurationError: Missing configuration
"""


class TwelveDataAPIError(Exception):
    """Base exception for TwelveData API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TwelveDataAuthError(TwelveDataAPIError):
    """Raised when API key is invalid (HTTP 401)."""

    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message, status_code=401)


class TwelveDataRateLimitError(TwelveDataAPIError):
    """Raised when rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__(message, status_code=429)


class TwelveDataTimeoutError(TwelveDataAPIError):
    """Raised when request times out."""

    def __init__(self, message: str = "Request timeout"):
        super().__init__(message)


class TwelveDataConfigurationError(TwelveDataAPIError):
    """Raised when configuration is missing or invalid."""

    def __init__(self, message: str = "Configuration error"):
        super().__init__(message)
