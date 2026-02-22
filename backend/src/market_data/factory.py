"""Market data provider factory with fallback chain.

This module provides centralized provider selection and fallback logic for
market data fetching. Implements Story 25.6 requirements:
- Provider selection based on DEFAULT_PROVIDER configuration
- Automatic fallback chain (Polygon → Yahoo) for historical data
- Explicit errors when all providers fail (no synthetic data)
- Fail-fast validation for streaming provider credentials
"""

from __future__ import annotations

from datetime import date

import structlog

from src.config import Settings
from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.market_data.adapters.yahoo_adapter import YahooAdapter
from src.market_data.exceptions import ConfigurationError, DataProviderError
from src.market_data.provider import MarketDataProvider
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class MarketDataProviderFactory:
    """Centralized factory for market data providers.

    Selects providers based on configuration and implements automatic fallback
    chain for resilience. Enforces credential validation and provides actionable
    error messages.

    Story 25.6: Replaces hardcoded adapter instantiation throughout codebase.
    """

    def __init__(self, settings: Settings):
        """Initialize factory with application settings.

        Args:
            settings: Application settings with API keys and provider config
        """
        self.settings = settings

    def get_historical_provider(self) -> MarketDataProvider:
        """Get historical data provider based on DEFAULT_PROVIDER config.

        Returns the configured provider without performing fallback logic.
        For automatic fallback, use fetch_historical_with_fallback() instead.

        Returns:
            MarketDataProvider instance (PolygonAdapter, YahooAdapter, or AlpacaAdapter)

        Raises:
            ConfigurationError: If provider requires credentials that are missing
            ValueError: If DEFAULT_PROVIDER is invalid

        Example:
            >>> factory = MarketDataProviderFactory(settings)
            >>> provider = factory.get_historical_provider()
            >>> bars = await provider.fetch_historical_bars("AAPL", start, end)
        """
        provider_name = self.settings.default_provider.lower()

        if provider_name == "polygon":
            # Polygon requires API key
            if not self.settings.polygon_api_key:
                raise ConfigurationError(
                    provider="Polygon",
                    missing_vars=["POLYGON_API_KEY"],
                )
            return PolygonAdapter(api_key=self.settings.polygon_api_key)

        elif provider_name == "yahoo":
            # Yahoo is free, no credentials required
            return YahooAdapter()

        elif provider_name == "alpaca":
            # Alpaca requires both API key and secret
            if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
                missing = []
                if not self.settings.alpaca_api_key:
                    missing.append("ALPACA_API_KEY")
                if not self.settings.alpaca_secret_key:
                    missing.append("ALPACA_SECRET_KEY")
                raise ConfigurationError(
                    provider="Alpaca",
                    missing_vars=missing,
                )
            return AlpacaAdapter(settings=self.settings, use_paper=False)

        else:
            raise ValueError(
                f"Invalid DEFAULT_PROVIDER: {provider_name}. "
                f"Must be one of: polygon, yahoo, alpaca"
            )

    def get_streaming_provider(self) -> AlpacaAdapter:
        """Get streaming provider (Alpaca only).

        Real-time WebSocket streaming is only supported via Alpaca.

        Returns:
            AlpacaAdapter instance configured for streaming

        Raises:
            ConfigurationError: If Alpaca credentials are not configured

        Example:
            >>> factory = MarketDataProviderFactory(settings)
            >>> adapter = factory.get_streaming_provider()
            >>> await adapter.connect()
            >>> await adapter.subscribe(["AAPL", "TSLA"])
        """
        # AC6: Validate Alpaca credentials
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            missing = []
            if not self.settings.alpaca_api_key:
                missing.append("ALPACA_API_KEY")
            if not self.settings.alpaca_secret_key:
                missing.append("ALPACA_SECRET_KEY")

            raise ConfigurationError(
                provider="Alpaca",
                missing_vars=missing,
            )

        return AlpacaAdapter(settings=self.settings, use_paper=False)

    async def fetch_historical_with_fallback(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = "1d",
        asset_class: str | None = None,
    ) -> list[OHLCVBar]:
        """Fetch historical data with automatic fallback.

        Implements fallback chain respecting DEFAULT_PROVIDER:
        - If DEFAULT_PROVIDER=polygon: Try Polygon → Yahoo → Error
        - If DEFAULT_PROVIDER=yahoo: Try Yahoo → Error (no fallback)
        - If DEFAULT_PROVIDER=alpaca: Try Alpaca → Yahoo → Error

        Logs WARNING when falling back to secondary provider.
        Raises explicit DataProviderError if all providers fail (no synthetic data).

        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Bar timeframe (e.g., "1d", "1h", "5m")
            asset_class: Asset class for provider-specific formatting (optional)

        Returns:
            List of OHLCVBar objects

        Raises:
            DataProviderError: If all providers fail (includes provider list and errors)
            ValueError: If symbol is empty or dates are invalid

        Example:
            >>> factory = MarketDataProviderFactory(settings)
            >>> bars = await factory.fetch_historical_with_fallback(
            ...     "AAPL",
            ...     date(2024, 1, 1),
            ...     date(2024, 12, 31)
            ... )
        """
        if not symbol:
            raise ValueError("Symbol is required for fetching historical data")

        # Get primary provider from configuration
        try:
            primary_provider = self.get_historical_provider()
        except ConfigurationError as e:
            # Primary provider not configured - raise immediately
            logger.error(
                "primary_provider_not_configured",
                provider=self.settings.default_provider,
                error=str(e),
            )
            raise

        primary_name = await primary_provider.get_provider_name()

        # Try primary provider
        try:
            logger.info(
                "fetching_historical_data",
                symbol=symbol,
                provider=primary_name,
                start_date=str(start_date),
                end_date=str(end_date),
                timeframe=timeframe,
            )

            bars = await primary_provider.fetch_historical_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                asset_class=asset_class,
            )

            logger.info(
                "fetch_complete",
                symbol=symbol,
                provider=primary_name,
                bar_count=len(bars),
            )

            return bars

        except Exception as primary_error:
            # Primary provider failed - log and try fallback
            logger.warning(
                f"{primary_name}_provider_failed",
                symbol=symbol,
                provider=primary_name,
                error=str(primary_error),
                message=f"Primary provider {primary_name} failed for {symbol}",
            )

            # AC2: If primary is Yahoo, no fallback available
            if primary_name == "yahoo":
                raise DataProviderError(
                    symbol=symbol,
                    providers_tried=["yahoo"],
                    errors={"yahoo": str(primary_error)},
                ) from primary_error

            # AC2: Try Yahoo as fallback
            logger.warning(
                "falling_back_to_yahoo",
                symbol=symbol,
                primary_provider=primary_name,
                message=f"{primary_name} failed, falling back to Yahoo Finance",
            )

            fallback = YahooAdapter()
            try:
                fallback_bars = await fallback.fetch_historical_bars(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    asset_class=asset_class,
                )

                logger.info(
                    "fallback_success",
                    symbol=symbol,
                    fallback_provider="yahoo",
                    bar_count=len(fallback_bars),
                    message="Yahoo fallback succeeded",
                )

                return fallback_bars

            except Exception as fallback_error:
                # AC3: Both providers failed - raise DataProviderError
                logger.error(
                    "all_providers_failed",
                    symbol=symbol,
                    providers_tried=[primary_name, "yahoo"],
                    primary_error=str(primary_error),
                    fallback_error=str(fallback_error),
                )

                raise DataProviderError(
                    symbol=symbol,
                    providers_tried=[primary_name, "yahoo"],
                    errors={
                        primary_name: str(primary_error),
                        "yahoo": str(fallback_error),
                    },
                ) from fallback_error
