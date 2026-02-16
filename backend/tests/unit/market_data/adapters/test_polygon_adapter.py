"""
Unit tests for PolygonAdapter.

Tests Polygon.io API integration with mocked HTTP responses.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pytest_httpx import HTTPXMock

from src.market_data.adapters.polygon_adapter import SYMBOL_MAP, PolygonAdapter


@pytest.mark.asyncio
class TestPolygonAdapter:
    """Test suite for PolygonAdapter."""

    async def test_fetch_historical_bars_success(self, httpx_mock: HTTPXMock):
        """Test successful fetching of historical bars."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        # Mock Polygon.io response
        mock_response = {
            "ticker": "AAPL",
            "status": "OK",
            "results": [
                {
                    "v": 120000000,
                    "o": 149.50,
                    "c": 151.00,
                    "h": 152.00,
                    "l": 149.00,
                    "t": 1609459200000,  # 2021-01-01 00:00:00 UTC
                },
                {
                    "v": 130000000,
                    "o": 151.00,
                    "c": 153.00,
                    "h": 154.00,
                    "l": 150.50,
                    "t": 1609545600000,  # 2021-01-02 00:00:00 UTC
                },
            ],
            "resultsCount": 2,
        }

        httpx_mock.add_response(
            url="https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2021-01-01/2021-01-02?apiKey=test_api_key&adjusted=true&sort=asc&limit=50000",
            json=mock_response,
        )

        # Act
        bars = await adapter.fetch_historical_bars(
            symbol="AAPL",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 2),
            timeframe="1d",
        )

        # Assert
        assert len(bars) == 2

        # Check first bar
        assert bars[0].symbol == "AAPL"
        assert bars[0].timeframe == "1d"
        assert bars[0].open == Decimal("149.50")
        assert bars[0].high == Decimal("152.00")
        assert bars[0].low == Decimal("149.00")
        assert bars[0].close == Decimal("151.00")
        assert bars[0].volume == 120000000
        assert bars[0].spread == Decimal("3.00")  # high - low
        assert bars[0].timestamp == datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)

        # Check second bar
        assert bars[1].volume == 130000000

    async def test_fetch_historical_bars_forex_uses_formatted_symbol_in_url(
        self, httpx_mock: HTTPXMock
    ):
        """Test that a non-stock asset_class formats the URL symbol but bars keep the clean symbol."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        mock_response = {
            "ticker": "C:EURUSD",
            "status": "OK",
            "results": [
                {
                    "v": 50000,
                    "o": 1.0850,
                    "c": 1.0875,
                    "h": 1.0900,
                    "l": 1.0840,
                    "t": 1609459200000,  # 2021-01-01 00:00:00 UTC
                },
            ],
            "resultsCount": 1,
        }

        httpx_mock.add_response(
            url="https://api.polygon.io/v2/aggs/ticker/C:EURUSD/range/1/day/2021-01-01/2021-01-02?apiKey=test_api_key&adjusted=true&sort=asc&limit=50000",
            json=mock_response,
        )

        # Act
        bars = await adapter.fetch_historical_bars(
            symbol="EURUSD",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 2),
            timeframe="1d",
            asset_class="forex",
        )

        # Assert - URL contained C:EURUSD (verified by the mock matching)
        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert "C:EURUSD" in str(requests[0].url)

        # Assert - returned bars use the clean original symbol
        assert len(bars) == 1
        assert bars[0].symbol == "EURUSD"

    async def test_fetch_historical_bars_rate_limit(self, httpx_mock: HTTPXMock):
        """Test rate limiting is respected."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(
            json={"ticker": "AAPL", "status": "OK", "results": []},
        )

        # Act
        start_time = datetime.now()
        await adapter.fetch_historical_bars(
            symbol="AAPL",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 1),
        )
        await adapter.fetch_historical_bars(
            symbol="AAPL",
            start_date=date(2021, 1, 2),
            end_date=date(2021, 1, 2),
        )
        end_time = datetime.now()

        # Assert - second request should be delayed by ~1 second
        duration = (end_time - start_time).total_seconds()
        assert duration >= 1.0, "Rate limiting not enforced"

    async def test_fetch_historical_bars_401_unauthorized(self, httpx_mock: HTTPXMock):
        """Test handling of 401 Unauthorized error."""
        # Arrange
        adapter = PolygonAdapter(api_key="invalid_key")

        httpx_mock.add_response(
            status_code=401,
            json={"error": "Unauthorized"},
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="authentication failed"):
            await adapter.fetch_historical_bars(
                symbol="AAPL",
                start_date=date(2021, 1, 1),
                end_date=date(2021, 1, 1),
            )

    async def test_fetch_historical_bars_404_symbol_not_found(self, httpx_mock: HTTPXMock):
        """Test handling of 404 symbol not found."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(
            status_code=404,
            json={"error": "Symbol not found"},
        )

        # Act
        bars = await adapter.fetch_historical_bars(
            symbol="INVALID",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 1),
        )

        # Assert - should return empty list, not raise
        assert bars == []

    async def test_fetch_historical_bars_429_rate_limit_exceeded(self, httpx_mock: HTTPXMock):
        """Test handling of 429 rate limit exceeded."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(
            status_code=429,
            json={"error": "Too many requests"},
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await adapter.fetch_historical_bars(
                symbol="AAPL",
                start_date=date(2021, 1, 1),
                end_date=date(2021, 1, 1),
            )

    async def test_fetch_historical_bars_500_server_error(self, httpx_mock: HTTPXMock):
        """Test handling of 500 server error."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(
            status_code=500,
            json={"error": "Internal server error"},
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="server error"):
            await adapter.fetch_historical_bars(
                symbol="AAPL",
                start_date=date(2021, 1, 1),
                end_date=date(2021, 1, 1),
            )

    async def test_fetch_historical_bars_empty_results(self, httpx_mock: HTTPXMock):
        """Test handling of empty results."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(
            json={"ticker": "AAPL", "status": "OK", "results": []},
        )

        # Act
        bars = await adapter.fetch_historical_bars(
            symbol="AAPL",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 1),
        )

        # Assert
        assert bars == []

    async def test_parse_timeframe(self):
        """Test timeframe parsing."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        # Act & Assert
        assert adapter._parse_timeframe("1d") == (1, "day")
        assert adapter._parse_timeframe("1h") == (1, "hour")
        assert adapter._parse_timeframe("5m") == (5, "minute")
        assert adapter._parse_timeframe("15m") == (15, "minute")

        # Invalid timeframe
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            adapter._parse_timeframe("invalid")

    async def test_get_provider_name(self):
        """Test provider name."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        # Act
        name = await adapter.get_provider_name()

        # Assert
        assert name == "polygon"

    async def test_health_check_success(self, httpx_mock: HTTPXMock):
        """Test health check when API is accessible."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(
            status_code=200,
            json={"status": "OK", "results": []},
        )

        # Act
        is_healthy = await adapter.health_check()

        # Assert
        assert is_healthy is True

    async def test_health_check_failure(self, httpx_mock: HTTPXMock):
        """Test health check when API is not accessible."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        httpx_mock.add_response(status_code=500)

        # Act
        is_healthy = await adapter.health_check()

        # Assert
        assert is_healthy is False

    async def test_close(self):
        """Test closing the HTTP client."""
        # Arrange
        adapter = PolygonAdapter(api_key="test_api_key")

        # Act
        await adapter.close()

        # Assert - client should be closed (no exception)
        assert True


class TestPolygonFormatSymbol:
    """Tests for PolygonAdapter._format_symbol."""

    def setup_method(self):
        self.adapter = PolygonAdapter(api_key="test-key")

    def test_none_asset_class_returns_bare_symbol(self):
        """asset_class=None should return the symbol unchanged."""
        assert self.adapter._format_symbol("AAPL", None) == "AAPL"

    def test_stock_asset_class_returns_bare_symbol(self):
        """asset_class='stock' should return the symbol unchanged."""
        assert self.adapter._format_symbol("AAPL", "stock") == "AAPL"

    def test_forex_adds_c_prefix(self):
        """Forex symbols get the C: prefix for Polygon."""
        assert self.adapter._format_symbol("EURUSD", "forex") == "C:EURUSD"

    def test_index_adds_i_prefix(self):
        """Index symbols get the I: prefix for Polygon."""
        assert self.adapter._format_symbol("DJI", "index") == "I:DJI"

    def test_crypto_adds_x_prefix(self):
        """Crypto symbols get the X: prefix for Polygon."""
        assert self.adapter._format_symbol("BTCUSD", "crypto") == "X:BTCUSD"

    def test_unknown_asset_class_returns_bare_symbol(self):
        """An unrecognised asset class should return the symbol unchanged."""
        assert self.adapter._format_symbol("FOO", "futures") == "FOO"

    def test_already_prefixed_forex_no_double_prefix(self):
        """A symbol that already carries the C: prefix should not be doubled."""
        assert self.adapter._format_symbol("C:EURUSD", "forex") == "C:EURUSD"

    def test_already_prefixed_index_no_double_prefix(self):
        """A symbol that already carries the I: prefix should not be doubled."""
        assert self.adapter._format_symbol("I:DJI", "index") == "I:DJI"

    def test_already_prefixed_crypto_no_double_prefix(self):
        """A symbol that already carries the X: prefix should not be doubled."""
        assert self.adapter._format_symbol("X:BTCUSD", "crypto") == "X:BTCUSD"

    def test_cross_prefix_mismatch_guard_returns_unchanged(self):
        """A symbol with a C: prefix passed as crypto should be returned as-is by the guard."""
        assert self.adapter._format_symbol("C:EURUSD", "crypto") == "C:EURUSD"

    def test_empty_string_forex_adds_bare_prefix(self):
        """An empty symbol with forex asset class still receives the C: prefix."""
        assert self.adapter._format_symbol("", "forex") == "C:"


class TestSymbolMap:
    """Tests for SYMBOL_MAP-based symbol translation."""

    def setup_method(self):
        self.adapter = PolygonAdapter(api_key="test-key")

    def test_us30_maps_to_dji_index(self):
        """US30 should map to I:DJI regardless of asset_class."""
        assert self.adapter._format_symbol("US30", None) == "I:DJI"
        assert self.adapter._format_symbol("US30", "stock") == "I:DJI"
        assert self.adapter._format_symbol("US30", "index") == "I:DJI"

    def test_nas100_maps_to_ndx_index(self):
        """NAS100 should map to I:NDX regardless of asset_class."""
        assert self.adapter._format_symbol("NAS100", None) == "I:NDX"
        assert self.adapter._format_symbol("NAS100", "index") == "I:NDX"

    def test_spx500_maps_to_spx_index(self):
        """SPX500 should map to I:SPX."""
        assert self.adapter._format_symbol("SPX500", None) == "I:SPX"

    def test_xauusd_maps_to_c_xauusd(self):
        """XAUUSD (gold) should map to C:XAUUSD regardless of asset_class."""
        assert self.adapter._format_symbol("XAUUSD", None) == "C:XAUUSD"
        assert self.adapter._format_symbol("XAUUSD", "forex") == "C:XAUUSD"

    def test_eurusd_maps_via_symbol_map(self):
        """EURUSD should be resolved via SYMBOL_MAP to C:EURUSD."""
        assert self.adapter._format_symbol("EURUSD", None) == "C:EURUSD"

    def test_gbpusd_maps_via_symbol_map(self):
        """GBPUSD should map to C:GBPUSD."""
        assert self.adapter._format_symbol("GBPUSD", None) == "C:GBPUSD"

    def test_unmapped_stock_passes_through(self):
        """Symbols not in SYMBOL_MAP fall through to existing logic."""
        assert self.adapter._format_symbol("SPY", None) == "SPY"
        assert self.adapter._format_symbol("DIA", None) == "DIA"
        assert self.adapter._format_symbol("QQQ", None) == "QQQ"

    def test_symbol_map_contains_expected_keys(self):
        """Verify all required mappings are present in SYMBOL_MAP."""
        assert "US30" in SYMBOL_MAP
        assert "NAS100" in SYMBOL_MAP
        assert "XAUUSD" in SYMBOL_MAP
        assert "EURUSD" in SYMBOL_MAP
        assert "GBPUSD" in SYMBOL_MAP
        assert "USDJPY" in SYMBOL_MAP
