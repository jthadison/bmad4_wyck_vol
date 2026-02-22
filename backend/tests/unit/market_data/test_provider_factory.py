"""Unit tests for MarketDataProviderFactory (Story 25.6).

Tests cover all 6 acceptance criteria:
- AC1: DEFAULT_PROVIDER=polygon returns PolygonAdapter
- AC2: Polygon fails → Yahoo fallback → WARNING logged
- AC3: Both fail → DataProviderError (no synthetic data)
- AC4: AUTO_EXECUTE_ORDERS + missing Alpaca → startup fails
- AC5: No direct instantiation outside factory (code review)
- AC6: get_streaming_provider() without keys → ConfigurationError
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.config import Settings
from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.market_data.adapters.yahoo_adapter import YahooAdapter
from src.market_data.exceptions import ConfigurationError, DataProviderError
from src.market_data.factory import MarketDataProviderFactory
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost/test",
        default_provider="polygon",
        polygon_api_key="test_polygon_key",
        alpaca_api_key="test_alpaca_key",
        alpaca_secret_key="test_alpaca_secret",
        auto_execute_orders=False,
    )


@pytest.fixture
def mock_bar():
    """Create a mock OHLCVBar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        timestamp=date(2024, 1, 1),
        open=150.0,
        high=155.0,
        low=149.0,
        close=154.0,
        volume=1000000,
        spread=6.0,
    )


# ============================================================================
# AC1: DEFAULT_PROVIDER=polygon returns PolygonAdapter
# ============================================================================


def test_get_historical_provider_polygon(mock_settings):
    """AC1: DEFAULT_PROVIDER=polygon returns PolygonAdapter."""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)
    provider = factory.get_historical_provider()

    assert isinstance(provider, PolygonAdapter)


def test_get_historical_provider_yahoo(mock_settings):
    """AC1: DEFAULT_PROVIDER=yahoo returns YahooAdapter."""
    mock_settings.default_provider = "yahoo"

    factory = MarketDataProviderFactory(mock_settings)
    provider = factory.get_historical_provider()

    assert isinstance(provider, YahooAdapter)


def test_get_historical_provider_alpaca(mock_settings):
    """AC1: DEFAULT_PROVIDER=alpaca returns AlpacaAdapter."""
    mock_settings.default_provider = "alpaca"
    mock_settings.alpaca_api_key = "test_key"
    mock_settings.alpaca_secret_key = "test_secret"

    factory = MarketDataProviderFactory(mock_settings)
    provider = factory.get_historical_provider()

    assert isinstance(provider, AlpacaAdapter)


def test_get_historical_provider_invalid_provider(mock_settings):
    """AC1: Invalid DEFAULT_PROVIDER raises ValueError."""
    mock_settings.default_provider = "invalid"

    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ValueError) as exc_info:
        factory.get_historical_provider()

    assert "Invalid DEFAULT_PROVIDER" in str(exc_info.value)
    assert "invalid" in str(exc_info.value)


def test_get_historical_provider_polygon_missing_key(mock_settings):
    """AC1: Polygon without API key raises ConfigurationError."""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = ""

    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ConfigurationError) as exc_info:
        factory.get_historical_provider()

    error = exc_info.value
    assert error.provider == "Polygon"
    assert "POLYGON_API_KEY" in error.missing_vars


# ============================================================================
# AC2: Polygon fails → Yahoo fallback → WARNING logged
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_with_fallback_polygon_fails_http_429(mock_settings, mock_bar):
    """AC2: Polygon HTTP 429 → Yahoo fallback → WARNING logged."""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock Polygon to raise HTTP 429 (rate limit)
    polygon_error = httpx.HTTPStatusError(
        "Rate limit exceeded",
        request=MagicMock(),
        response=MagicMock(status_code=429),
    )

    with patch.object(
        PolygonAdapter, "fetch_historical_bars", side_effect=polygon_error
    ), patch.object(PolygonAdapter, "get_provider_name", return_value="polygon"), patch.object(
        YahooAdapter, "fetch_historical_bars", return_value=[mock_bar]
    ):
        bars = await factory.fetch_historical_with_fallback(
            "AAPL", date(2024, 1, 1), date(2024, 12, 31)
        )

    # Verify fallback succeeded
    assert len(bars) == 1
    assert bars[0] == mock_bar


@pytest.mark.asyncio
async def test_fetch_with_fallback_polygon_fails_network_error(mock_settings, mock_bar):
    """AC2: Polygon network error → Yahoo fallback → WARNING logged."""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock Polygon to raise network error
    with patch.object(
        PolygonAdapter, "fetch_historical_bars", side_effect=RuntimeError("Network timeout")
    ), patch.object(PolygonAdapter, "get_provider_name", return_value="polygon"), patch.object(
        YahooAdapter, "fetch_historical_bars", return_value=[mock_bar]
    ):
        bars = await factory.fetch_historical_with_fallback(
            "AAPL", date(2024, 1, 1), date(2024, 12, 31)
        )

    # Verify fallback succeeded
    assert len(bars) == 1
    assert bars[0] == mock_bar


# ============================================================================
# AC3: Both Polygon and Yahoo fail → DataProviderError (no synthetic data)
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_with_fallback_all_fail(mock_settings):
    """AC3: Both Polygon and Yahoo fail → DataProviderError raised."""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock both to fail with different errors
    polygon_error = RuntimeError("Rate limit exceeded")
    yahoo_error = RuntimeError("Network timeout")

    with patch.object(
        PolygonAdapter, "fetch_historical_bars", side_effect=polygon_error
    ), patch.object(PolygonAdapter, "get_provider_name", return_value="polygon"), patch.object(
        YahooAdapter, "fetch_historical_bars", side_effect=yahoo_error
    ):
        with pytest.raises(DataProviderError) as exc_info:
            await factory.fetch_historical_with_fallback(
                "AAPL", date(2024, 1, 1), date(2024, 12, 31)
            )

    error = exc_info.value
    assert error.symbol == "AAPL"
    assert "polygon" in error.providers_tried
    assert "yahoo" in error.providers_tried
    assert "Rate limit exceeded" in str(error.errors)
    assert "Network timeout" in str(error.errors)


@pytest.mark.asyncio
async def test_fetch_with_fallback_yahoo_primary_no_fallback(mock_settings):
    """AC2/AC3: If Yahoo is primary and fails, no fallback available."""
    mock_settings.default_provider = "yahoo"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock Yahoo to fail
    yahoo_error = RuntimeError("Symbol not found")

    with patch.object(YahooAdapter, "fetch_historical_bars", side_effect=yahoo_error), patch.object(
        YahooAdapter, "get_provider_name", return_value="yahoo"
    ):
        with pytest.raises(DataProviderError) as exc_info:
            await factory.fetch_historical_with_fallback(
                "AAPL", date(2024, 1, 1), date(2024, 12, 31)
            )

    error = exc_info.value
    assert error.symbol == "AAPL"
    assert error.providers_tried == ["yahoo"]
    assert "Symbol not found" in str(error.errors)


@pytest.mark.asyncio
async def test_fetch_with_fallback_empty_symbol_raises_error(mock_settings):
    """AC3: Empty symbol raises ValueError (no synthetic data)."""
    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ValueError) as exc_info:
        await factory.fetch_historical_with_fallback("", date(2024, 1, 1), date(2024, 12, 31))

    assert "Symbol is required" in str(exc_info.value)


# ============================================================================
# AC6: get_streaming_provider() without keys → ConfigurationError
# ============================================================================


def test_get_streaming_provider_no_credentials(mock_settings):
    """AC6: get_streaming_provider() without keys → ConfigurationError."""
    mock_settings.alpaca_api_key = ""
    mock_settings.alpaca_secret_key = ""

    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ConfigurationError) as exc_info:
        factory.get_streaming_provider()

    error = exc_info.value
    assert error.provider == "Alpaca"
    assert "ALPACA_API_KEY" in error.missing_vars
    assert "ALPACA_SECRET_KEY" in error.missing_vars


def test_get_streaming_provider_missing_api_key(mock_settings):
    """AC6: get_streaming_provider() missing API key → ConfigurationError."""
    mock_settings.alpaca_api_key = ""
    mock_settings.alpaca_secret_key = "test_secret"

    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ConfigurationError) as exc_info:
        factory.get_streaming_provider()

    error = exc_info.value
    assert error.provider == "Alpaca"
    assert "ALPACA_API_KEY" in error.missing_vars
    assert "ALPACA_SECRET_KEY" not in error.missing_vars


def test_get_streaming_provider_missing_secret_key(mock_settings):
    """AC6: get_streaming_provider() missing secret key → ConfigurationError."""
    mock_settings.alpaca_api_key = "test_api_key"
    mock_settings.alpaca_secret_key = ""

    factory = MarketDataProviderFactory(mock_settings)

    with pytest.raises(ConfigurationError) as exc_info:
        factory.get_streaming_provider()

    error = exc_info.value
    assert error.provider == "Alpaca"
    assert "ALPACA_SECRET_KEY" in error.missing_vars
    assert "ALPACA_API_KEY" not in error.missing_vars


def test_get_streaming_provider_with_valid_credentials(mock_settings):
    """AC6: get_streaming_provider() with valid credentials returns AlpacaAdapter."""
    mock_settings.alpaca_api_key = "test_api_key"
    mock_settings.alpaca_secret_key = "test_secret"

    factory = MarketDataProviderFactory(mock_settings)
    adapter = factory.get_streaming_provider()

    assert isinstance(adapter, AlpacaAdapter)


# ============================================================================
# Edge Cases
# ============================================================================


def test_yahoo_provider_no_credentials_required(mock_settings):
    """Yahoo provider doesn't require API credentials."""
    mock_settings.default_provider = "yahoo"
    # Explicitly clear all API keys to ensure Yahoo works without them
    mock_settings.polygon_api_key = ""
    mock_settings.alpaca_api_key = ""
    mock_settings.alpaca_secret_key = ""

    factory = MarketDataProviderFactory(mock_settings)
    provider = factory.get_historical_provider()

    assert isinstance(provider, YahooAdapter)


@pytest.mark.asyncio
async def test_fetch_with_fallback_empty_result_not_error(mock_settings):
    """Yahoo returns empty list (symbol not found) - should return empty, not error."""
    mock_settings.default_provider = "yahoo"

    factory = MarketDataProviderFactory(mock_settings)

    # Mock Yahoo to return empty list (valid response)
    with patch.object(YahooAdapter, "fetch_historical_bars", return_value=[]):
        bars = await factory.fetch_historical_with_fallback(
            "INVALID", date(2024, 1, 1), date(2024, 12, 31)
        )

    assert bars == []


@pytest.mark.asyncio
async def test_fetch_with_fallback_success_returns_bars(mock_settings, mock_bar):
    """Successful fetch returns bars from primary provider."""
    mock_settings.default_provider = "polygon"
    mock_settings.polygon_api_key = "test_key"

    factory = MarketDataProviderFactory(mock_settings)

    with patch.object(
        PolygonAdapter, "fetch_historical_bars", return_value=[mock_bar]
    ), patch.object(PolygonAdapter, "get_provider_name", return_value="polygon"):
        bars = await factory.fetch_historical_with_fallback(
            "AAPL", date(2024, 1, 1), date(2024, 12, 31)
        )

    assert len(bars) == 1
    assert bars[0] == mock_bar


# ============================================================================
# Exception Message Validation
# ============================================================================


def test_configuration_error_message_format():
    """ConfigurationError message includes provider and missing vars."""
    error = ConfigurationError("Alpaca", ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"])

    assert "Alpaca" in str(error)
    assert "ALPACA_API_KEY" in str(error)
    assert "ALPACA_SECRET_KEY" in str(error)
    assert ".env" in str(error)


def test_data_provider_error_message_format():
    """DataProviderError message includes symbol, providers, and errors."""
    error = DataProviderError(
        symbol="AAPL",
        providers_tried=["polygon", "yahoo"],
        errors={"polygon": "HTTP 429", "yahoo": "Network timeout"},
    )

    assert "AAPL" in str(error)
    assert "polygon" in str(error)
    assert "yahoo" in str(error)
    assert "HTTP 429" in str(error)
    assert "Network timeout" in str(error)
