"""
Unit tests for TwelveDataAdapter.

Tests Twelve Data API integration with mocked HTTP responses.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from pytest_httpx import HTTPXMock

from src.market_data.adapters.twelvedata_adapter import RateLimiter, TwelveDataAdapter
from src.market_data.adapters.twelvedata_exceptions import (
    ConfigurationError,
    TwelveDataAPIError,
    TwelveDataAuthError,
    TwelveDataRateLimitError,
    TwelveDataTimeoutError,
)


class TestRateLimiter:
    """Test suite for RateLimiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_calls_within_limit(self):
        """Test that calls within limit are allowed immediately."""
        limiter = RateLimiter(max_calls=5, period_seconds=60)

        # Should allow 5 calls without waiting
        for _ in range(5):
            await limiter.acquire()

        assert limiter.remaining == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_remaining_property(self):
        """Test remaining calls property."""
        limiter = RateLimiter(max_calls=8, period_seconds=60)

        assert limiter.remaining == 8

        await limiter.acquire()
        assert limiter.remaining == 7

        await limiter.acquire()
        await limiter.acquire()
        assert limiter.remaining == 5

    @pytest.mark.asyncio
    async def test_rate_limiter_clears_old_calls(self):
        """Test that old calls are removed from the window."""
        limiter = RateLimiter(max_calls=2, period_seconds=1)

        await limiter.acquire()
        await limiter.acquire()
        assert limiter.remaining == 0

        # Wait for window to reset
        import asyncio

        await asyncio.sleep(1.1)

        assert limiter.remaining == 2


class TestTwelveDataAdapterInit:
    """Test suite for TwelveDataAdapter initialization."""

    def test_init_with_api_key(self, monkeypatch):
        """Test initialization with valid API key."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter.api_key == "test-api-key"
        assert adapter.base_url == "https://api.twelvedata.com"

    def test_init_without_api_key_raises_error(self, monkeypatch):
        """Test initialization without API key raises ConfigurationError."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "")

        with pytest.raises(ConfigurationError, match="TWELVEDATA_API_KEY not configured"):
            TwelveDataAdapter(api_key="")

    def test_init_uses_settings_api_key(self, monkeypatch):
        """Test initialization uses settings API key when not provided."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "settings-api-key")

        # Force settings reload
        with patch("src.market_data.adapters.twelvedata_adapter.settings") as mock_settings:
            mock_settings.twelvedata_api_key = "settings-api-key"
            mock_settings.twelvedata_base_url = "https://api.twelvedata.com"
            mock_settings.twelvedata_rate_limit = 8
            mock_settings.twelvedata_timeout = 10

            adapter = TwelveDataAdapter()
            assert adapter.api_key == "settings-api-key"


@pytest.mark.asyncio
class TestTwelveDataAdapterSearchSymbols:
    """Test suite for TwelveDataAdapter.search_symbols."""

    async def test_search_symbols_returns_results(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test successful symbol search returns parsed results."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=test-api-key",
            json={
                "data": [
                    {
                        "symbol": "EUR/USD",
                        "instrument_name": "Euro / US Dollar",
                        "exchange": "FOREX",
                        "instrument_type": "Physical Currency",
                        "currency": "USD",
                    },
                    {
                        "symbol": "EUR/GBP",
                        "instrument_name": "Euro / British Pound",
                        "exchange": "FOREX",
                        "instrument_type": "Physical Currency",
                        "currency": "GBP",
                    },
                ]
            },
        )

        results = await adapter.search_symbols("EUR")

        assert len(results) == 2
        assert results[0].symbol == "EURUSD"  # Denormalized
        assert results[0].name == "Euro / US Dollar"
        assert results[0].exchange == "FOREX"
        assert results[0].type == "Physical Currency"
        assert results[0].currency == "USD"

    async def test_search_symbols_with_asset_class_filter(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test symbol search with asset class filter."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&type=forex&apikey=test-api-key",
            json={"data": []},
        )

        results = await adapter.search_symbols("EUR", asset_class="forex")

        assert results == []

    async def test_search_symbols_empty_results(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test symbol search with no results."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=INVALID&apikey=test-api-key",
            json={"data": []},
        )

        results = await adapter.search_symbols("INVALID")

        assert results == []


@pytest.mark.asyncio
class TestTwelveDataAdapterGetSymbolInfo:
    """Test suite for TwelveDataAdapter.get_symbol_info."""

    async def test_get_symbol_info_forex(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test get_symbol_info for forex symbol."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/forex_pairs?symbol=EUR/USD&apikey=test-api-key",
            json={
                "data": [
                    {
                        "symbol": "EUR/USD",
                        "currency_group": "Major",
                        "currency_base": "Euro",
                        "currency_quote": "US Dollar",
                    }
                ]
            },
        )

        result = await adapter.get_symbol_info("EURUSD")

        assert result is not None
        assert result.symbol == "EURUSD"
        assert result.name == "Euro / US Dollar"
        assert result.exchange == "FOREX"
        assert result.currency_base == "Euro"
        assert result.currency_quote == "US Dollar"

    async def test_get_symbol_info_returns_none_for_invalid(
        self, httpx_mock: HTTPXMock, monkeypatch
    ):
        """Test get_symbol_info returns None for invalid symbol."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        # Mock all endpoints returning empty
        httpx_mock.add_response(
            url="https://api.twelvedata.com/forex_pairs?symbol=INVALID&apikey=test-api-key",
            json={"data": []},
        )
        httpx_mock.add_response(
            url="https://api.twelvedata.com/indices?symbol=INVALID&apikey=test-api-key",
            json={"data": []},
        )
        httpx_mock.add_response(
            url="https://api.twelvedata.com/cryptocurrencies?symbol=INVALID&apikey=test-api-key",
            json={"data": []},
        )

        result = await adapter.get_symbol_info("INVALID")

        assert result is None


@pytest.mark.asyncio
class TestTwelveDataAdapterForexPairs:
    """Test suite for TwelveDataAdapter.get_forex_pairs."""

    async def test_get_forex_pairs_with_symbol(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test get_forex_pairs with specific symbol."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/forex_pairs?symbol=EUR/USD&apikey=test-api-key",
            json={
                "data": [
                    {
                        "symbol": "EUR/USD",
                        "currency_group": "Major",
                        "currency_base": "Euro",
                        "currency_quote": "US Dollar",
                    }
                ]
            },
        )

        results = await adapter.get_forex_pairs("EUR/USD")

        assert len(results) == 1
        assert results[0].symbol == "EUR/USD"
        assert results[0].currency_group == "Major"
        assert results[0].currency_base == "Euro"
        assert results[0].currency_quote == "US Dollar"

    async def test_get_forex_pairs_without_symbol(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test get_forex_pairs without symbol returns all pairs."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/forex_pairs?apikey=test-api-key",
            json={
                "data": [
                    {
                        "symbol": "EUR/USD",
                        "currency_group": "Major",
                        "currency_base": "Euro",
                        "currency_quote": "US Dollar",
                    },
                    {
                        "symbol": "GBP/USD",
                        "currency_group": "Major",
                        "currency_base": "British Pound",
                        "currency_quote": "US Dollar",
                    },
                ]
            },
        )

        results = await adapter.get_forex_pairs()

        assert len(results) == 2


@pytest.mark.asyncio
class TestTwelveDataAdapterIndices:
    """Test suite for TwelveDataAdapter.get_indices."""

    async def test_get_indices_with_symbol(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test get_indices with specific symbol."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/indices?symbol=SPX&apikey=test-api-key",
            json={
                "data": [
                    {
                        "symbol": "SPX",
                        "name": "S&P 500",
                        "country": "United States",
                        "currency": "USD",
                    }
                ]
            },
        )

        results = await adapter.get_indices("SPX")

        assert len(results) == 1
        assert results[0].symbol == "SPX"
        assert results[0].name == "S&P 500"
        assert results[0].country == "United States"
        assert results[0].currency == "USD"


@pytest.mark.asyncio
class TestTwelveDataAdapterCryptocurrencies:
    """Test suite for TwelveDataAdapter.get_cryptocurrencies."""

    async def test_get_cryptocurrencies_with_symbol(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test get_cryptocurrencies with specific symbol."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/cryptocurrencies?symbol=BTC/USD&apikey=test-api-key",
            json={
                "data": [
                    {
                        "symbol": "BTC/USD",
                        "currency_base": "Bitcoin",
                        "currency_quote": "US Dollar",
                        "available_exchanges": ["Binance", "Coinbase"],
                    }
                ]
            },
        )

        results = await adapter.get_cryptocurrencies("BTC/USD")

        assert len(results) == 1
        assert results[0].symbol == "BTC/USD"
        assert results[0].currency_base == "Bitcoin"
        assert results[0].currency_quote == "US Dollar"
        assert "Binance" in results[0].available_exchanges


@pytest.mark.asyncio
class TestTwelveDataAdapterErrorHandling:
    """Test suite for TwelveDataAdapter error handling."""

    async def test_handles_401_unauthorized(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test handling of 401 Unauthorized error."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "invalid-key")
        adapter = TwelveDataAdapter(api_key="invalid-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=invalid-key",
            status_code=401,
            json={"message": "Invalid API key"},
        )

        with pytest.raises(TwelveDataAuthError, match="Invalid API key"):
            await adapter.search_symbols("EUR")

    async def test_handles_429_rate_limit(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test handling of 429 rate limit exceeded."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=test-api-key",
            status_code=429,
            json={"message": "Too many requests"},
        )

        with pytest.raises(TwelveDataRateLimitError, match="Rate limit exceeded"):
            await adapter.search_symbols("EUR")

    async def test_handles_timeout(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test handling of request timeout."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        def raise_timeout(request):
            raise httpx.TimeoutException("Request timed out")

        httpx_mock.add_callback(raise_timeout)

        with pytest.raises(TwelveDataTimeoutError, match="timed out"):
            await adapter.search_symbols("EUR")

    async def test_handles_500_server_error(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test handling of 500 server error."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=test-api-key",
            status_code=500,
            json={"message": "Internal server error"},
        )

        with pytest.raises(TwelveDataAPIError) as exc_info:
            await adapter.search_symbols("EUR")

        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
class TestTwelveDataAdapterRateLimiting:
    """Test suite for TwelveDataAdapter rate limiting."""

    async def test_rate_limit_remaining_property(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test rate_limit_remaining property."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        # Default rate limit is 8
        assert adapter.rate_limit_remaining == 8

    async def test_rate_limit_decrements_after_request(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test rate limit decrements after each request."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")

        with patch("src.market_data.adapters.twelvedata_adapter.settings") as mock_settings:
            mock_settings.twelvedata_api_key = "test-api-key"
            mock_settings.twelvedata_base_url = "https://api.twelvedata.com"
            mock_settings.twelvedata_rate_limit = 8
            mock_settings.twelvedata_timeout = 10

            adapter = TwelveDataAdapter(api_key="test-api-key")

            httpx_mock.add_response(
                url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=test-api-key",
                json={"data": []},
            )

            initial_remaining = adapter.rate_limit_remaining
            await adapter.search_symbols("EUR")

            assert adapter.rate_limit_remaining == initial_remaining - 1


@pytest.mark.asyncio
class TestTwelveDataAdapterSymbolNormalization:
    """Test suite for symbol normalization."""

    async def test_normalize_symbol_adds_slash(self, monkeypatch):
        """Test normalizing 6-char symbol adds slash."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter._normalize_symbol("EURUSD") == "EUR/USD"
        assert adapter._normalize_symbol("GBPJPY") == "GBP/JPY"

    async def test_normalize_symbol_preserves_slash(self, monkeypatch):
        """Test normalizing symbol with slash preserves it."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter._normalize_symbol("EUR/USD") == "EUR/USD"
        assert adapter._normalize_symbol("BTC/USD") == "BTC/USD"

    async def test_normalize_symbol_non_forex(self, monkeypatch):
        """Test normalizing non-forex symbols."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter._normalize_symbol("SPX") == "SPX"
        assert adapter._normalize_symbol("AAPL") == "AAPL"

    async def test_denormalize_symbol_removes_slash(self, monkeypatch):
        """Test denormalizing removes slash."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter._denormalize_symbol("EUR/USD") == "EURUSD"
        assert adapter._denormalize_symbol("BTC/USD") == "BTCUSD"
        assert adapter._denormalize_symbol("SPX") == "SPX"


@pytest.mark.asyncio
class TestTwelveDataAdapterClose:
    """Test suite for TwelveDataAdapter.close."""

    async def test_close_client(self, monkeypatch):
        """Test closing the HTTP client."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        await adapter.close()

    async def test_async_context_manager(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test async context manager properly closes client."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=test-api-key",
            json={"data": []},
        )

        async with TwelveDataAdapter(api_key="test-api-key") as adapter:
            results = await adapter.search_symbols("EUR")
            assert results == []

        # Client should be closed after exiting context
        assert True


@pytest.mark.asyncio
class TestTwelveDataAdapterAPIErrors:
    """Test suite for TwelveDataAdapter API error handling."""

    async def test_handles_200_with_error_in_body(self, httpx_mock: HTTPXMock, monkeypatch):
        """Test handling of 200 status with error in JSON body."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(
            url="https://api.twelvedata.com/symbol_search?symbol=EUR&apikey=test-api-key",
            status_code=200,
            json={"code": 400, "message": "Invalid API Key", "status": "error"},
        )

        with pytest.raises(TwelveDataAPIError, match="Invalid API Key"):
            await adapter.search_symbols("EUR")

        # Client should be closed (no exception)
        assert True
