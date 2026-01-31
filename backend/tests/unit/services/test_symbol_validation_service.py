"""
Unit tests for SymbolValidationService (Story 21.2).

Tests symbol validation, caching, and fallback behavior.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.twelvedata import CryptoInfo, ForexPairInfo, IndexInfo
from src.models.validation import SymbolValidationSource, ValidSymbolResult
from src.services.symbol_validation_service import SymbolValidationService


class FakeRedis:
    """Fake Redis client for testing."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._data[key] = value
        self._ttls[key] = ttl

    def clear(self):
        self._data.clear()
        self._ttls.clear()


@pytest.mark.asyncio
class TestSymbolValidationService:
    """Test suite for SymbolValidationService."""

    @pytest.fixture
    def mock_twelvedata(self):
        """Create mock TwelveData adapter."""
        adapter = AsyncMock()
        adapter.get_forex_pairs = AsyncMock(return_value=[])
        adapter.get_indices = AsyncMock(return_value=[])
        adapter.get_cryptocurrencies = AsyncMock(return_value=[])
        adapter.search_symbols = AsyncMock(return_value=[])
        return adapter

    @pytest.fixture
    def mock_alpaca(self):
        """Create mock Alpaca adapter."""
        adapter = AsyncMock()
        adapter.get_asset = AsyncMock(return_value=None)
        return adapter

    @pytest.fixture
    def fake_redis(self):
        """Create fake Redis client."""
        return FakeRedis()

    @pytest.fixture
    def service(self, mock_twelvedata, mock_alpaca, fake_redis):
        """Create service with mocks."""
        return SymbolValidationService(
            twelvedata_adapter=mock_twelvedata,
            alpaca_adapter=mock_alpaca,
            redis=fake_redis,
        )

    async def test_validate_empty_symbol_returns_error(self, service):
        """Test that empty symbol returns validation error."""
        result = await service.validate_symbol("", "forex")

        assert result.valid is False
        assert "cannot be empty" in result.error

    async def test_validate_invalid_asset_class_returns_error(self, service):
        """Test that invalid asset class returns validation error."""
        result = await service.validate_symbol("EURUSD", "invalid")

        assert result.valid is False
        assert "Invalid asset class" in result.error

    async def test_validate_invalid_symbol_format_returns_error(self, service):
        """Test that invalid symbol format returns validation error."""
        result = await service.validate_symbol("EUR@USD!", "forex")

        assert result.valid is False
        assert "Invalid symbol format" in result.error

    async def test_validate_valid_forex_symbol(self, service, mock_twelvedata):
        """Test validating a valid forex symbol."""
        mock_twelvedata.get_forex_pairs.return_value = [
            ForexPairInfo(
                symbol="EUR/USD",
                currency_group="Major",
                currency_base="Euro",
                currency_quote="US Dollar",
            )
        ]

        result = await service.validate_symbol("EURUSD", "forex")

        assert result.valid is True
        assert result.symbol == "EURUSD"
        assert result.asset_class == "forex"
        assert result.source == SymbolValidationSource.API
        assert result.info is not None
        assert result.info.currency_base == "Euro"
        assert result.info.currency_quote == "US Dollar"

    async def test_validate_invalid_forex_symbol(self, service, mock_twelvedata):
        """Test validating an invalid forex symbol."""
        mock_twelvedata.get_forex_pairs.return_value = []

        result = await service.validate_symbol("EURSUD", "forex")

        assert result.valid is False
        assert "not found" in result.error

    async def test_validate_valid_index_symbol(self, service, mock_twelvedata):
        """Test validating a valid index symbol."""
        mock_twelvedata.get_indices.return_value = [
            IndexInfo(
                symbol="SPX",
                name="S&P 500",
                country="United States",
                currency="USD",
            )
        ]

        result = await service.validate_symbol("SPX", "index")

        assert result.valid is True
        assert result.symbol == "SPX"
        assert result.asset_class == "index"
        assert result.info.name == "S&P 500"

    async def test_validate_invalid_index_symbol(self, service, mock_twelvedata):
        """Test validating an invalid index symbol."""
        mock_twelvedata.get_indices.return_value = []

        result = await service.validate_symbol("INVALID", "index")

        assert result.valid is False

    async def test_validate_valid_crypto_symbol(self, service, mock_twelvedata):
        """Test validating a valid crypto symbol."""
        mock_twelvedata.get_cryptocurrencies.return_value = [
            CryptoInfo(
                symbol="BTC/USD",
                currency_base="Bitcoin",
                currency_quote="US Dollar",
            )
        ]

        result = await service.validate_symbol("BTC/USD", "crypto")

        assert result.valid is True
        assert result.symbol == "BTCUSD"
        assert result.asset_class == "crypto"

    async def test_validate_stock_uses_alpaca(self, service, mock_alpaca):
        """Test that stock validation uses Alpaca adapter."""
        mock_asset = MagicMock()
        mock_asset.tradable = True
        mock_asset.name = "Apple Inc."
        mock_asset.exchange = "NASDAQ"
        mock_alpaca.get_asset.return_value = mock_asset

        result = await service.validate_symbol("AAPL", "stock")

        mock_alpaca.get_asset.assert_called_once_with("AAPL")
        assert result.valid is True
        assert result.source == SymbolValidationSource.ALPACA

    async def test_cache_hit_returns_cached_result(self, service, fake_redis):
        """Test that cache hit returns cached result."""
        # Pre-populate cache
        cached = ValidSymbolResult(
            valid=True,
            symbol="EURUSD",
            asset_class="forex",
            source=SymbolValidationSource.API,
        )
        key = "twelvedata:symbol:EURUSD:forex"
        fake_redis._data[key] = cached.model_dump_json()

        result = await service.validate_symbol("EURUSD", "forex")

        assert result.source == SymbolValidationSource.CACHE

    async def test_cache_miss_calls_api(self, service, mock_twelvedata, fake_redis):
        """Test that cache miss calls API."""
        mock_twelvedata.get_forex_pairs.return_value = [
            ForexPairInfo(
                symbol="EUR/USD",
                currency_base="Euro",
                currency_quote="US Dollar",
            )
        ]

        result = await service.validate_symbol("EURUSD", "forex")

        mock_twelvedata.get_forex_pairs.assert_called_once()
        assert result.source == SymbolValidationSource.API

    async def test_successful_validation_is_cached(self, service, mock_twelvedata, fake_redis):
        """Test that successful validation result is cached."""
        mock_twelvedata.get_forex_pairs.return_value = [
            ForexPairInfo(
                symbol="EUR/USD",
                currency_base="Euro",
                currency_quote="US Dollar",
            )
        ]

        await service.validate_symbol("EURUSD", "forex")

        key = "twelvedata:symbol:EURUSD:forex"
        assert key in fake_redis._data

    async def test_api_failure_falls_back_to_static(self, service, mock_twelvedata):
        """Test that API failure falls back to static validation."""
        from src.market_data.adapters.twelvedata_exceptions import TwelveDataAPIError

        mock_twelvedata.get_forex_pairs.side_effect = TwelveDataAPIError("API down")

        result = await service.validate_symbol("EURUSD", "forex")

        assert result.valid is True
        assert result.source == SymbolValidationSource.STATIC

    async def test_static_fallback_for_unknown_symbol(self, service, mock_twelvedata):
        """Test static fallback returns invalid for unknown symbol."""
        from src.market_data.adapters.twelvedata_exceptions import TwelveDataAPIError

        mock_twelvedata.get_forex_pairs.side_effect = TwelveDataAPIError("API down")

        result = await service.validate_symbol("RANDOMXYZ", "forex")

        assert result.valid is False
        assert result.source == SymbolValidationSource.STATIC
        assert "not in known" in result.error

    async def test_search_returns_results(self, service, mock_twelvedata):
        """Test symbol search returns results."""
        from src.models.twelvedata import SymbolSearchResult as TDSearchResult

        mock_twelvedata.search_symbols.return_value = [
            TDSearchResult(
                symbol="EURUSD",
                name="Euro / US Dollar",
                exchange="FOREX",
                type="Physical Currency",
            )
        ]

        results = await service.search_symbols("EUR")

        assert len(results) == 1
        assert results[0].symbol == "EURUSD"

    async def test_search_with_asset_class_filter(self, service, mock_twelvedata):
        """Test symbol search with asset class filter."""
        mock_twelvedata.search_symbols.return_value = []

        await service.search_symbols("EUR", asset_class="forex")

        mock_twelvedata.search_symbols.assert_called_once_with("EUR", "forex")

    async def test_search_respects_limit(self, service, mock_twelvedata):
        """Test symbol search respects limit parameter."""
        from src.models.twelvedata import SymbolSearchResult as TDSearchResult

        mock_twelvedata.search_symbols.return_value = [
            TDSearchResult(symbol=f"SYM{i}", name=f"Symbol {i}", exchange="EX", type="T")
            for i in range(20)
        ]

        results = await service.search_symbols("SYM", limit=5)

        assert len(results) == 5

    async def test_normalize_forex_symbol(self, service):
        """Test forex symbol normalization."""
        assert service._normalize_forex_symbol("EURUSD") == "EUR/USD"
        assert service._normalize_forex_symbol("eurusd") == "EUR/USD"
        assert service._normalize_forex_symbol("EUR/USD") == "EUR/USD"

    async def test_denormalize_symbol(self, service):
        """Test symbol denormalization."""
        assert service._denormalize_symbol("EUR/USD") == "EURUSD"
        assert service._denormalize_symbol("BTC/USD") == "BTCUSD"

    async def test_service_without_redis(self, mock_twelvedata, mock_alpaca):
        """Test service works without Redis (no caching)."""
        service = SymbolValidationService(
            twelvedata_adapter=mock_twelvedata,
            alpaca_adapter=mock_alpaca,
            redis=None,
        )

        mock_twelvedata.get_forex_pairs.return_value = [
            ForexPairInfo(
                symbol="EUR/USD",
                currency_base="Euro",
                currency_quote="US Dollar",
            )
        ]

        result = await service.validate_symbol("EURUSD", "forex")

        assert result.valid is True
        assert result.source == SymbolValidationSource.API

    async def test_service_without_adapters_uses_static(self):
        """Test service without adapters falls back to static."""
        service = SymbolValidationService(
            twelvedata_adapter=None,
            alpaca_adapter=None,
            redis=None,
        )

        result = await service.validate_symbol("EURUSD", "forex")

        assert result.valid is True
        assert result.source == SymbolValidationSource.STATIC


class TestStaticSymbols:
    """Test static symbol fallback lists."""

    def test_forex_pairs_count(self):
        """Test static forex pairs has at least 50 pairs."""
        from src.data.static_symbols import STATIC_FOREX_PAIRS

        assert len(STATIC_FOREX_PAIRS) >= 50

    def test_forex_pairs_includes_majors(self):
        """Test static forex pairs includes major pairs."""
        from src.data.static_symbols import is_known_symbol

        majors = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
        for symbol in majors:
            assert is_known_symbol(symbol, "forex"), f"{symbol} not found"

    def test_indices_count(self):
        """Test static indices has at least 20 indices."""
        from src.data.static_symbols import STATIC_INDICES

        assert len(STATIC_INDICES) >= 20

    def test_indices_includes_majors(self):
        """Test static indices includes major indices."""
        from src.data.static_symbols import is_known_symbol

        indices = ["SPX", "NDX", "DJI", "FTSE", "DAX", "NIKKEI", "HSI"]
        for symbol in indices:
            assert is_known_symbol(symbol, "index"), f"{symbol} not found"

    def test_crypto_count(self):
        """Test static crypto has at least 20 cryptocurrencies."""
        from src.data.static_symbols import STATIC_CRYPTO

        assert len(STATIC_CRYPTO) >= 20

    def test_crypto_includes_majors(self):
        """Test static crypto includes major cryptocurrencies."""
        from src.data.static_symbols import is_known_symbol

        cryptos = ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD"]
        for symbol in cryptos:
            assert is_known_symbol(symbol, "crypto"), f"{symbol} not found"

    def test_is_known_symbol_case_insensitive(self):
        """Test is_known_symbol is case insensitive."""
        from src.data.static_symbols import is_known_symbol

        assert is_known_symbol("eurusd", "forex")
        assert is_known_symbol("EURUSD", "forex")
        assert is_known_symbol("EurUsd", "forex")

    def test_get_symbol_info_from_static(self):
        """Test getting symbol info from static list."""
        from src.data.static_symbols import get_symbol_info_from_static

        info = get_symbol_info_from_static("EURUSD", "forex")

        assert info is not None
        assert info["symbol"] == "EURUSD"
        assert info["name"] == "Euro / US Dollar"
        assert info["exchange"] == "FOREX"

    def test_get_symbol_info_returns_none_for_unknown(self):
        """Test get_symbol_info returns None for unknown symbol."""
        from src.data.static_symbols import get_symbol_info_from_static

        info = get_symbol_info_from_static("UNKNOWN", "forex")

        assert info is None
