"""
Custom exceptions for Twelve Data API adapter.

These exceptions provide specific error handling for different failure scenarios
when interacting with the Twelve Data API.
"""

from __future__ import annotations


class TwelveDataAPIError(Exception):
    """Base exception for Twelve Data API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TwelveDataAuthError(TwelveDataAPIError):
    """Raised when API authentication fails (HTTP 401)."""

    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message, status_code=401)


class TwelveDataRateLimitError(TwelveDataAPIError):
    """Raised when rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class TwelveDataTimeoutError(TwelveDataAPIError):
    """Raised when API request times out."""

    def __init__(self, message: str = "Request timed out", timeout_seconds: int | None = None):
        super().__init__(message, status_code=None)
        self.timeout_seconds = timeout_seconds


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""

    pass
