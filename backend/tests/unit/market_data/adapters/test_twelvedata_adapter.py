"""
Unit tests for TwelveDataAdapter (Story 21.1).

Tests TwelveData API integration with mocked HTTP responses.
"""

import pytest
from pytest_httpx import HTTPXMock

from src.market_data.adapters.twelvedata_adapter import RateLimiter, TwelveDataAdapter
from src.market_data.adapters.twelvedata_exceptions import (
    TwelveDataAPIError,
    TwelveDataAuthError,
    TwelveDataConfigurationError,
    TwelveDataRateLimitError,
    TwelveDataTimeoutError,
)


@pytest.mark.asyncio
class TestTwelveDataAdapter:
    """Test suite for TwelveDataAdapter."""

    def test_init_without_api_key_raises_error(self, monkeypatch):
        """Test that initialization without API key raises ConfigurationError."""
        monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)

        with pytest.raises(TwelveDataConfigurationError, match="TWELVEDATA_API_KEY not configured"):
            TwelveDataAdapter()

    def test_init_with_api_key_succeeds(self, monkeypatch):
        """Test successful initialization with API key."""
        monkeypatch.setenv("TWELVEDATA_API_KEY", "test-api-key")

        adapter = TwelveDataAdapter()

        assert adapter.api_key == "test-api-key"
        assert adapter.base_url == "https://api.twelvedata.com"

    def test_init_with_explicit_api_key(self, monkeypatch):
        """Test initialization with explicit API key parameter."""
        monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)

        adapter = TwelveDataAdapter(api_key="explicit-key")

        assert adapter.api_key == "explicit-key"

    def test_init_with_custom_config(self, monkeypatch):
        """Test initialization with custom configuration."""
        adapter = TwelveDataAdapter(
            api_key="test-key",
            base_url="https://custom.api.com",
            rate_limit=10,
            timeout=30,
        )

        assert adapter.base_url == "https://custom.api.com"
        assert adapter._timeout == 30

    async def test_search_symbols_returns_results(self, httpx_mock: HTTPXMock):
        """Test symbol search returns parsed results."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        mock_response = {
            "data": [
                {
                    "symbol": "EUR/USD",
                    "instrument_name": "Euro / US Dollar",
                    "exchange": "FOREX",
                    "instrument_type": "Physical Currency",
                    "currency": "USD",
                    "country": "",
                }
            ]
        }

        httpx_mock.add_response(json=mock_response)

        results = await adapter.search_symbols("EUR")

        assert len(results) == 1
        assert results[0].symbol == "EURUSD"  # Denormalized
        assert results[0].name == "Euro / US Dollar"
        assert results[0].exchange == "FOREX"
        assert results[0].type == "Physical Currency"

        await adapter.close()

    async def test_search_symbols_with_asset_class(self, httpx_mock: HTTPXMock):
        """Test symbol search with asset class filter."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(json={"data": []})

        await adapter.search_symbols("EUR", asset_class="forex")

        # Verify the request included the type filter
        request = httpx_mock.get_request()
        assert "type=Physical+Currency" in str(request.url) or "type=Physical%20Currency" in str(
            request.url
        )

        await adapter.close()

    async def test_search_symbols_handles_401(self, httpx_mock: HTTPXMock):
        """Test search symbols handles 401 Unauthorized."""
        adapter = TwelveDataAdapter(api_key="invalid-key")

        httpx_mock.add_response(status_code=401)

        with pytest.raises(TwelveDataAuthError, match="Invalid API key"):
            await adapter.search_symbols("EUR")

        await adapter.close()

    async def test_search_symbols_handles_429(self, httpx_mock: HTTPXMock):
        """Test search symbols handles 429 Rate Limit."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        httpx_mock.add_response(status_code=429)

        with pytest.raises(TwelveDataRateLimitError, match="Rate limit exceeded"):
            await adapter.search_symbols("EUR")

        await adapter.close()

    async def test_get_symbol_info_returns_forex_info(self, httpx_mock: HTTPXMock):
        """Test get_symbol_info returns forex pair info."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        mock_response = {
            "data": [
                {
                    "symbol": "EUR/USD",
                    "currency_group": "Major",
                    "currency_base": "Euro",
                    "currency_quote": "US Dollar",
                }
            ]
        }

        httpx_mock.add_response(json=mock_response)

        result = await adapter.get_symbol_info("EURUSD")

        assert result is not None
        assert result.symbol == "EURUSD"
        assert result.type == "forex"
        assert result.currency_base == "Euro"
        assert result.currency_quote == "US Dollar"

        await adapter.close()

    async def test_get_symbol_info_returns_none_for_invalid(self, httpx_mock: HTTPXMock):
        """Test get_symbol_info returns None for invalid symbol."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        # Mock all three endpoints returning empty results
        httpx_mock.add_response(json={"data": []})  # forex_pairs
        httpx_mock.add_response(json={"data": []})  # indices
        httpx_mock.add_response(json={"data": []})  # cryptocurrencies

        result = await adapter.get_symbol_info("INVALID")

        assert result is None

        await adapter.close()

    async def test_get_forex_pairs(self, httpx_mock: HTTPXMock):
        """Test get_forex_pairs returns list."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        mock_response = {
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
        }

        httpx_mock.add_response(json=mock_response)

        results = await adapter.get_forex_pairs()

        assert len(results) == 2
        assert results[0].symbol == "EUR/USD"
        assert results[1].symbol == "GBP/USD"

        await adapter.close()

    async def test_get_indices(self, httpx_mock: HTTPXMock):
        """Test get_indices returns list."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        mock_response = {
            "data": [
                {
                    "symbol": "SPX",
                    "name": "S&P 500",
                    "country": "United States",
                    "currency": "USD",
                },
            ]
        }

        httpx_mock.add_response(json=mock_response)

        results = await adapter.get_indices()

        assert len(results) == 1
        assert results[0].symbol == "SPX"
        assert results[0].name == "S&P 500"

        await adapter.close()

    async def test_get_cryptocurrencies(self, httpx_mock: HTTPXMock):
        """Test get_cryptocurrencies returns list."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        mock_response = {
            "data": [
                {
                    "symbol": "BTC/USD",
                    "currency_base": "Bitcoin",
                    "currency_quote": "US Dollar",
                },
            ]
        }

        httpx_mock.add_response(json=mock_response)

        results = await adapter.get_cryptocurrencies()

        assert len(results) == 1
        assert results[0].symbol == "BTC/USD"
        assert results[0].currency_base == "Bitcoin"

        await adapter.close()

    async def test_rate_limit_remaining(self, httpx_mock: HTTPXMock):
        """Test rate_limit_remaining property."""
        adapter = TwelveDataAdapter(api_key="test-api-key", rate_limit=8)

        # Initially should have 8 remaining
        assert adapter.rate_limit_remaining == 8

        httpx_mock.add_response(json={"data": []})
        await adapter.search_symbols("EUR")

        # After one call, should have 7 remaining
        assert adapter.rate_limit_remaining == 7

        await adapter.close()

    async def test_close_client(self):
        """Test closing the HTTP client."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        await adapter.close()

        # Should be able to close again without error
        await adapter.close()

    def test_normalize_symbol(self):
        """Test symbol normalization."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter._normalize_symbol("EURUSD") == "EUR/USD"
        assert adapter._normalize_symbol("eurusd") == "EUR/USD"
        assert adapter._normalize_symbol("EUR/USD") == "EUR/USD"
        assert adapter._normalize_symbol("SPX") == "SPX"
        assert adapter._normalize_symbol("BTC/USD") == "BTC/USD"

    def test_denormalize_symbol(self):
        """Test symbol denormalization."""
        adapter = TwelveDataAdapter(api_key="test-api-key")

        assert adapter._denormalize_symbol("EUR/USD") == "EURUSD"
        assert adapter._denormalize_symbol("EURUSD") == "EURUSD"
        assert adapter._denormalize_symbol("BTC/USD") == "BTCUSD"


@pytest.mark.asyncio
class TestRateLimiter:
    """Test suite for RateLimiter."""

    async def test_acquire_within_limit(self):
        """Test acquiring slots within limit."""
        limiter = RateLimiter(max_calls=3, period_seconds=60)

        # Should be able to acquire 3 times without waiting
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        assert limiter.remaining == 0

    async def test_remaining_property(self):
        """Test remaining property."""
        limiter = RateLimiter(max_calls=5, period_seconds=60)

        assert limiter.remaining == 5

        await limiter.acquire()
        assert limiter.remaining == 4

        await limiter.acquire()
        assert limiter.remaining == 3


class TestTwelveDataExceptions:
    """Test suite for TwelveData exceptions."""

    def test_api_error(self):
        """Test TwelveDataAPIError."""
        error = TwelveDataAPIError("Test error", status_code=500)

        assert str(error) == "Test error"
        assert error.status_code == 500

    def test_auth_error(self):
        """Test TwelveDataAuthError."""
        error = TwelveDataAuthError()

        assert "Invalid API key" in str(error)
        assert error.status_code == 401

    def test_rate_limit_error(self):
        """Test TwelveDataRateLimitError."""
        error = TwelveDataRateLimitError(retry_after=30)

        assert "Rate limit exceeded" in str(error)
        assert error.status_code == 429
        assert error.retry_after == 30

    def test_timeout_error(self):
        """Test TwelveDataTimeoutError."""
        error = TwelveDataTimeoutError()

        assert "Request timeout" in str(error)

    def test_configuration_error(self):
        """Test TwelveDataConfigurationError."""
        error = TwelveDataConfigurationError("Missing config")

        assert "Missing config" in str(error)
