"""
Unit Tests for CorrelationMapper (Story 16.1a)

Test Coverage:
--------------
1. AssetCategory enum values
2. Forex correlation group mapping (USD_MAJOR, EUR_CROSS, JPY_CROSS)
3. Crypto correlation group mapping (BTC_CORRELATED, ETH_CORRELATED, ALT_CORRELATED)
4. Equity sector mapping (TECH, FINANCE, ENERGY, etc.)
5. Commodity correlation group mapping
6. Index correlation group mapping
7. Auto-detection of asset category
8. Campaign correlation info helper
9. Unknown/fallback handling
10. Case insensitivity

Author: Story 16.1a
"""

import pytest

from src.campaign_management.correlation_mapper import CorrelationMapper
from src.models.campaign import AssetCategory


class TestAssetCategoryEnum:
    """Tests for AssetCategory enum."""

    def test_all_categories_exist(self):
        """Verify all expected category values exist."""
        assert AssetCategory.FOREX == "FOREX"
        assert AssetCategory.EQUITY == "EQUITY"
        assert AssetCategory.CRYPTO == "CRYPTO"
        assert AssetCategory.COMMODITY == "COMMODITY"
        assert AssetCategory.INDEX == "INDEX"
        assert AssetCategory.UNKNOWN == "UNKNOWN"

    def test_enum_is_string_subclass(self):
        """Verify AssetCategory is a str enum for JSON serialization."""
        assert isinstance(AssetCategory.FOREX, str)
        assert AssetCategory.FOREX == "FOREX"

    def test_enum_count(self):
        """Verify exactly 6 categories exist."""
        assert len(AssetCategory) == 6


class TestForexCorrelationGroups:
    """Tests for forex correlation group mappings."""

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("EURUSD", "USD_MAJOR"),
            ("GBPUSD", "USD_MAJOR"),
            ("AUDUSD", "USD_MAJOR"),
            ("NZDUSD", "USD_MAJOR"),
            ("USDCAD", "USD_MAJOR"),
            ("USDCHF", "USD_MAJOR"),
        ],
    )
    def test_usd_major_pairs(self, symbol: str, expected_group: str):
        """USD major pairs should map to USD_MAJOR group."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.FOREX)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("EURGBP", "EUR_CROSS"),
            ("EURJPY", "EUR_CROSS"),
            ("EURAUD", "EUR_CROSS"),
            ("EURNZD", "EUR_CROSS"),
            ("EURCHF", "EUR_CROSS"),
        ],
    )
    def test_eur_cross_pairs(self, symbol: str, expected_group: str):
        """EUR cross pairs should map to EUR_CROSS group."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.FOREX)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("USDJPY", "JPY_CROSS"),
            ("GBPJPY", "JPY_CROSS"),
            ("AUDJPY", "JPY_CROSS"),
            ("NZDJPY", "JPY_CROSS"),
            ("CADJPY", "JPY_CROSS"),
            ("CHFJPY", "JPY_CROSS"),
        ],
    )
    def test_jpy_cross_pairs(self, symbol: str, expected_group: str):
        """JPY cross pairs should map to JPY_CROSS group."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.FOREX)
        assert result == expected_group

    def test_unknown_forex_pair(self):
        """Unknown forex pair should return FOREX_OTHER."""
        result = CorrelationMapper.get_correlation_group("ZARJPY", AssetCategory.FOREX)
        assert result == "FOREX_OTHER"


class TestCryptoCorrelationGroups:
    """Tests for crypto correlation group mappings."""

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("BTCUSD", "BTC_CORRELATED"),
            ("BTCUSDT", "BTC_CORRELATED"),
            ("XBTUSD", "BTC_CORRELATED"),
        ],
    )
    def test_btc_correlated(self, symbol: str, expected_group: str):
        """BTC and BTC derivatives should map to BTC_CORRELATED."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.CRYPTO)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("ETHUSD", "ETH_CORRELATED"),
            ("ETHUSDT", "ETH_CORRELATED"),
            ("SOLUSD", "ETH_CORRELATED"),
            ("AVAXUSD", "ETH_CORRELATED"),
        ],
    )
    def test_eth_correlated(self, symbol: str, expected_group: str):
        """ETH and smart contract platforms should map to ETH_CORRELATED."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.CRYPTO)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("ADAUSD", "ALT_CORRELATED"),
            ("DOTUSD", "ALT_CORRELATED"),
            ("LINKUSD", "ALT_CORRELATED"),
            ("MATICUSD", "ALT_CORRELATED"),
            ("XRPUSD", "ALT_CORRELATED"),
            ("DOGEUSD", "ALT_CORRELATED"),
        ],
    )
    def test_alt_correlated(self, symbol: str, expected_group: str):
        """Altcoins should map to ALT_CORRELATED."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.CRYPTO)
        assert result == expected_group

    def test_unknown_crypto(self):
        """Unknown crypto should return CRYPTO_OTHER."""
        result = CorrelationMapper.get_correlation_group("SHIBUSD", AssetCategory.CRYPTO)
        assert result == "CRYPTO_OTHER"


class TestEquitySectorMapping:
    """Tests for equity sector mapping."""

    @pytest.mark.parametrize(
        "symbol,expected_sector",
        [
            ("AAPL", "TECH"),
            ("MSFT", "TECH"),
            ("GOOGL", "TECH"),
            ("NVDA", "TECH"),
            ("META", "TECH"),
            ("TSLA", "TECH"),
            ("AMZN", "TECH"),
        ],
    )
    def test_tech_sector(self, symbol: str, expected_sector: str):
        """Tech stocks should map to TECH sector."""
        result = CorrelationMapper.get_sector(symbol)
        assert result == expected_sector

    @pytest.mark.parametrize(
        "symbol,expected_sector",
        [
            ("JPM", "FINANCE"),
            ("BAC", "FINANCE"),
            ("GS", "FINANCE"),
            ("V", "FINANCE"),
            ("MA", "FINANCE"),
        ],
    )
    def test_finance_sector(self, symbol: str, expected_sector: str):
        """Finance stocks should map to FINANCE sector."""
        result = CorrelationMapper.get_sector(symbol)
        assert result == expected_sector

    @pytest.mark.parametrize(
        "symbol,expected_sector",
        [
            ("XOM", "ENERGY"),
            ("CVX", "ENERGY"),
            ("COP", "ENERGY"),
        ],
    )
    def test_energy_sector(self, symbol: str, expected_sector: str):
        """Energy stocks should map to ENERGY sector."""
        result = CorrelationMapper.get_sector(symbol)
        assert result == expected_sector

    @pytest.mark.parametrize(
        "symbol,expected_sector",
        [
            ("JNJ", "HEALTHCARE"),
            ("UNH", "HEALTHCARE"),
            ("PFE", "HEALTHCARE"),
        ],
    )
    def test_healthcare_sector(self, symbol: str, expected_sector: str):
        """Healthcare stocks should map to HEALTHCARE sector."""
        result = CorrelationMapper.get_sector(symbol)
        assert result == expected_sector

    def test_unknown_equity(self):
        """Unknown equity should return UNKNOWN sector."""
        result = CorrelationMapper.get_sector("UNKNOWN_TICKER")
        assert result == "UNKNOWN"

    def test_equity_correlation_group_format(self):
        """Equity correlation group should be EQUITY_{SECTOR}."""
        result = CorrelationMapper.get_correlation_group("AAPL", AssetCategory.EQUITY)
        assert result == "EQUITY_TECH"

        result = CorrelationMapper.get_correlation_group("JPM", AssetCategory.EQUITY)
        assert result == "EQUITY_FINANCE"

        result = CorrelationMapper.get_correlation_group("XOM", AssetCategory.EQUITY)
        assert result == "EQUITY_ENERGY"


class TestCommodityCorrelationGroups:
    """Tests for commodity correlation group mappings."""

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("XAUUSD", "COMMODITY_METALS"),
            ("GOLD", "COMMODITY_METALS"),
            ("XAGUSD", "COMMODITY_METALS"),
            ("SILVER", "COMMODITY_METALS"),
        ],
    )
    def test_metals_group(self, symbol: str, expected_group: str):
        """Precious metals should map to COMMODITY_METALS."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.COMMODITY)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("USOIL", "COMMODITY_ENERGY"),
            ("CL", "COMMODITY_ENERGY"),
            ("WTI", "COMMODITY_ENERGY"),
            ("BRENT", "COMMODITY_ENERGY"),
        ],
    )
    def test_energy_commodities(self, symbol: str, expected_group: str):
        """Energy commodities should map to COMMODITY_ENERGY."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.COMMODITY)
        assert result == expected_group

    def test_unknown_commodity(self):
        """Unknown commodity should return COMMODITY_OTHER."""
        result = CorrelationMapper.get_correlation_group("UNKNOWN", AssetCategory.COMMODITY)
        assert result == "COMMODITY_OTHER"


class TestIndexCorrelationGroups:
    """Tests for index correlation group mappings."""

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("SPX", "INDEX_US"),
            ("SPX500", "INDEX_US"),
            ("NAS100", "INDEX_US"),
            ("US30", "INDEX_US"),
        ],
    )
    def test_us_indices(self, symbol: str, expected_group: str):
        """US indices should map to INDEX_US."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.INDEX)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("DAX", "INDEX_EU"),
            ("FTSE", "INDEX_EU"),
            ("UK100", "INDEX_EU"),
        ],
    )
    def test_eu_indices(self, symbol: str, expected_group: str):
        """EU indices should map to INDEX_EU."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.INDEX)
        assert result == expected_group

    @pytest.mark.parametrize(
        "symbol,expected_group",
        [
            ("NIKKEI", "INDEX_ASIA"),
            ("JP225", "INDEX_ASIA"),
            ("HSI", "INDEX_ASIA"),
        ],
    )
    def test_asia_indices(self, symbol: str, expected_group: str):
        """Asia indices should map to INDEX_ASIA."""
        result = CorrelationMapper.get_correlation_group(symbol, AssetCategory.INDEX)
        assert result == expected_group

    def test_unknown_index(self):
        """Unknown index should return INDEX_OTHER."""
        result = CorrelationMapper.get_correlation_group("UNKNOWN", AssetCategory.INDEX)
        assert result == "INDEX_OTHER"


class TestAssetCategoryDetection:
    """Tests for auto-detection of asset category."""

    @pytest.mark.parametrize(
        "symbol,expected_category",
        [
            ("EURUSD", AssetCategory.FOREX),
            ("GBPUSD", AssetCategory.FOREX),
            ("USDJPY", AssetCategory.FOREX),
        ],
    )
    def test_detect_forex(self, symbol: str, expected_category: AssetCategory):
        """Known forex pairs should be detected as FOREX."""
        result = CorrelationMapper.detect_asset_category(symbol)
        assert result == expected_category

    @pytest.mark.parametrize(
        "symbol,expected_category",
        [
            ("BTCUSD", AssetCategory.CRYPTO),
            ("ETHUSD", AssetCategory.CRYPTO),
            ("ADAUSD", AssetCategory.CRYPTO),
        ],
    )
    def test_detect_crypto(self, symbol: str, expected_category: AssetCategory):
        """Known crypto symbols should be detected as CRYPTO."""
        result = CorrelationMapper.detect_asset_category(symbol)
        assert result == expected_category

    @pytest.mark.parametrize(
        "symbol,expected_category",
        [
            ("AAPL", AssetCategory.EQUITY),
            ("MSFT", AssetCategory.EQUITY),
            ("JPM", AssetCategory.EQUITY),
        ],
    )
    def test_detect_equity(self, symbol: str, expected_category: AssetCategory):
        """Known equity symbols should be detected as EQUITY."""
        result = CorrelationMapper.detect_asset_category(symbol)
        assert result == expected_category

    @pytest.mark.parametrize(
        "symbol,expected_category",
        [
            ("SPX", AssetCategory.INDEX),
            ("NAS100", AssetCategory.INDEX),
            ("DAX", AssetCategory.INDEX),
        ],
    )
    def test_detect_index(self, symbol: str, expected_category: AssetCategory):
        """Known index symbols should be detected as INDEX."""
        result = CorrelationMapper.detect_asset_category(symbol)
        assert result == expected_category

    @pytest.mark.parametrize(
        "symbol,expected_category",
        [
            ("XAUUSD", AssetCategory.COMMODITY),
            ("USOIL", AssetCategory.COMMODITY),
        ],
    )
    def test_detect_commodity(self, symbol: str, expected_category: AssetCategory):
        """Known commodity symbols should be detected as COMMODITY."""
        result = CorrelationMapper.detect_asset_category(symbol)
        assert result == expected_category

    def test_heuristic_forex_detection(self):
        """6-char currency pairs should be detected as FOREX via heuristic."""
        # Not in known list but follows forex naming convention
        result = CorrelationMapper.detect_asset_category("AUDCAD")
        assert result == AssetCategory.FOREX

    def test_unknown_symbol(self):
        """Unknown symbols should return UNKNOWN category."""
        result = CorrelationMapper.detect_asset_category("RANDOM123")
        assert result == AssetCategory.UNKNOWN


class TestCaseInsensitivity:
    """Tests for case-insensitive symbol handling."""

    def test_lowercase_forex(self):
        """Lowercase forex symbol should work."""
        result = CorrelationMapper.get_correlation_group("eurusd", AssetCategory.FOREX)
        assert result == "USD_MAJOR"

    def test_lowercase_equity(self):
        """Lowercase equity symbol should work."""
        result = CorrelationMapper.get_sector("aapl")
        assert result == "TECH"

    def test_mixed_case_crypto(self):
        """Mixed case crypto symbol should work."""
        result = CorrelationMapper.get_correlation_group("BtcUsd", AssetCategory.CRYPTO)
        assert result == "BTC_CORRELATED"

    def test_lowercase_detection(self):
        """Lowercase symbol detection should work."""
        result = CorrelationMapper.detect_asset_category("msft")
        assert result == AssetCategory.EQUITY


class TestCampaignCorrelationInfo:
    """Tests for get_campaign_correlation_info helper method."""

    def test_equity_full_info(self):
        """Equity symbol should return category, sector, and correlation group."""
        category, sector, group = CorrelationMapper.get_campaign_correlation_info("AAPL")
        assert category == AssetCategory.EQUITY
        assert sector == "TECH"
        assert group == "EQUITY_TECH"

    def test_forex_full_info(self):
        """Forex symbol should return category, None sector, and correlation group."""
        category, sector, group = CorrelationMapper.get_campaign_correlation_info("EURUSD")
        assert category == AssetCategory.FOREX
        assert sector is None
        assert group == "USD_MAJOR"

    def test_crypto_full_info(self):
        """Crypto symbol should return category, None sector, and correlation group."""
        category, sector, group = CorrelationMapper.get_campaign_correlation_info("BTCUSD")
        assert category == AssetCategory.CRYPTO
        assert sector is None
        assert group == "BTC_CORRELATED"

    def test_with_explicit_category(self):
        """Explicit category should override auto-detection."""
        category, sector, group = CorrelationMapper.get_campaign_correlation_info(
            "AAPL", category=AssetCategory.FOREX
        )
        # Category is used as-is
        assert category == AssetCategory.FOREX
        # Sector is None for forex
        assert sector is None
        # Group is FOREX_OTHER since AAPL not in forex mappings
        assert group == "FOREX_OTHER"

    def test_unknown_equity_no_sector(self):
        """Unknown equity should return None sector."""
        # Force equity category but use unknown symbol
        category, sector, group = CorrelationMapper.get_campaign_correlation_info(
            "UNKNOWN_TICKER", category=AssetCategory.EQUITY
        )
        assert category == AssetCategory.EQUITY
        assert sector is None  # Unknown sector returns None
        assert group == "EQUITY_UNKNOWN"


class TestDefaultGroupHandling:
    """Tests for default/fallback group handling."""

    def test_unknown_category_returns_default(self):
        """UNKNOWN category should return DEFAULT group."""
        result = CorrelationMapper.get_correlation_group("ANYTHING", AssetCategory.UNKNOWN)
        assert result == "DEFAULT"

    def test_all_categories_have_fallback(self):
        """All categories should have a fallback group for unknown symbols."""
        unknown_symbol = "COMPLETELY_UNKNOWN_SYMBOL_12345"

        # Each category should return a valid fallback
        assert (
            CorrelationMapper.get_correlation_group(unknown_symbol, AssetCategory.FOREX)
            == "FOREX_OTHER"
        )
        assert (
            CorrelationMapper.get_correlation_group(unknown_symbol, AssetCategory.CRYPTO)
            == "CRYPTO_OTHER"
        )
        assert "EQUITY_" in CorrelationMapper.get_correlation_group(
            unknown_symbol, AssetCategory.EQUITY
        )
        assert (
            CorrelationMapper.get_correlation_group(unknown_symbol, AssetCategory.COMMODITY)
            == "COMMODITY_OTHER"
        )
        assert (
            CorrelationMapper.get_correlation_group(unknown_symbol, AssetCategory.INDEX)
            == "INDEX_OTHER"
        )
        assert (
            CorrelationMapper.get_correlation_group(unknown_symbol, AssetCategory.UNKNOWN)
            == "DEFAULT"
        )
