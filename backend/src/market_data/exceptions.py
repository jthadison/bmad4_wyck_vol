"""Custom exceptions for market data providers.

This module defines exceptions for data provider failures and configuration errors.
"""


class DataProviderError(Exception):
    """Raised when all data providers fail.

    Attributes:
        symbol: Symbol that was being fetched
        providers_tried: List of provider names that were attempted
        errors: Dictionary mapping provider names to error messages
    """

    def __init__(self, symbol: str, providers_tried: list[str], errors: dict[str, str]):
        """Initialize DataProviderError.

        Args:
            symbol: Symbol that failed to fetch
            providers_tried: List of provider names attempted (e.g., ["polygon", "yahoo"])
            errors: Dict mapping provider name to error message
        """
        self.symbol = symbol
        self.providers_tried = providers_tried
        self.errors = errors
        message = (
            f"All providers failed for {symbol}. "
            f"Tried: {', '.join(providers_tried)}. "
            f"Errors: {errors}"
        )
        super().__init__(message)


class ConfigurationError(Exception):
    """Raised when provider configuration is invalid or missing.

    Attributes:
        provider: Provider name that failed configuration check
        missing_vars: List of missing environment variable names
    """

    def __init__(self, provider: str, missing_vars: list[str]):
        """Initialize ConfigurationError.

        Args:
            provider: Provider name (e.g., "Alpaca", "Polygon")
            missing_vars: List of missing environment variable names
        """
        self.provider = provider
        self.missing_vars = missing_vars
        message = (
            f"{provider} provider requires environment variables: {', '.join(missing_vars)}. "
            f"Set them in your .env file or environment before starting the server."
        )
        super().__init__(message)
