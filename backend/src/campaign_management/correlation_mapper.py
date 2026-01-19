"""
Correlation Mapper for Asset Categorization (Story 16.1a)

Purpose:
--------
Maps trading symbols to correlation groups and sectors for risk management
diversification. Enables correlation-aware position limits by grouping
assets that tend to move together.

Key Features:
-------------
- Symbol-to-correlation-group mapping
- Asset category detection (FOREX, EQUITY, CRYPTO, COMMODITY, INDEX)
- Sector mapping for equities (TECH, FINANCE, ENERGY, etc.)
- Auto-assignment for campaign creation
- Manual override capability

Correlation Groups:
-------------------
- FOREX: USD_MAJOR, EUR_CROSS, JPY_CROSS, FOREX_OTHER
- CRYPTO: BTC_CORRELATED, ETH_CORRELATED, ALT_CORRELATED, CRYPTO_OTHER
- EQUITY: EQUITY_{SECTOR} (e.g., EQUITY_TECH, EQUITY_FINANCE)
- COMMODITY: COMMODITY_METALS, COMMODITY_ENERGY, COMMODITY_OTHER
- INDEX: INDEX_US, INDEX_EU, INDEX_ASIA, INDEX_OTHER

Author: Story 16.1a
"""

from src.models.campaign import AssetCategory


class CorrelationMapper:
    """
    Maps asset symbols to correlation groups for risk management.

    Provides static mappings for:
    - Forex pairs to correlation groups (USD_MAJOR, EUR_CROSS, JPY_CROSS)
    - Crypto assets to correlation groups (BTC_CORRELATED, ETH_CORRELATED, ALT_CORRELATED)
    - Equity symbols to sectors (TECH, FINANCE, ENERGY, HEALTHCARE, etc.)
    - Commodity symbols to commodity groups
    - Index symbols to regional groups

    Example:
    --------
    >>> from src.campaign_management.correlation_mapper import CorrelationMapper
    >>> from src.models.campaign import AssetCategory
    >>>
    >>> # Get correlation group for forex
    >>> group = CorrelationMapper.get_correlation_group("EURUSD", AssetCategory.FOREX)
    >>> print(group)  # "USD_MAJOR"
    >>>
    >>> # Get sector for equity
    >>> sector = CorrelationMapper.get_sector("AAPL")
    >>> print(sector)  # "TECH"
    """

    # Forex correlation groups - pairs that move together
    FOREX_GROUPS: dict[str, str] = {
        # USD Major pairs (move inversely to USD)
        "EURUSD": "USD_MAJOR",
        "GBPUSD": "USD_MAJOR",
        "AUDUSD": "USD_MAJOR",
        "NZDUSD": "USD_MAJOR",
        "USDCAD": "USD_MAJOR",
        "USDCHF": "USD_MAJOR",
        # EUR crosses (correlated with EUR strength)
        "EURGBP": "EUR_CROSS",
        "EURJPY": "EUR_CROSS",
        "EURAUD": "EUR_CROSS",
        "EURNZD": "EUR_CROSS",
        "EURCHF": "EUR_CROSS",
        # JPY crosses (correlated with JPY/risk sentiment)
        "USDJPY": "JPY_CROSS",
        "GBPJPY": "JPY_CROSS",
        "AUDJPY": "JPY_CROSS",
        "NZDJPY": "JPY_CROSS",
        "CADJPY": "JPY_CROSS",
        "CHFJPY": "JPY_CROSS",
    }

    # Crypto correlation groups - assets that move together
    CRYPTO_GROUPS: dict[str, str] = {
        # BTC-correlated (high beta to BTC)
        "BTCUSD": "BTC_CORRELATED",
        "BTCUSDT": "BTC_CORRELATED",
        "XBTUSD": "BTC_CORRELATED",
        # ETH-correlated (DeFi/smart contract platforms)
        "ETHUSD": "ETH_CORRELATED",
        "ETHUSDT": "ETH_CORRELATED",
        "SOLUSD": "ETH_CORRELATED",
        "AVAXUSD": "ETH_CORRELATED",
        # Altcoin-correlated (smaller caps, higher volatility)
        "ADAUSD": "ALT_CORRELATED",
        "DOTUSD": "ALT_CORRELATED",
        "LINKUSD": "ALT_CORRELATED",
        "MATICUSD": "ALT_CORRELATED",
        "XRPUSD": "ALT_CORRELATED",
        "DOGEUSD": "ALT_CORRELATED",
    }

    # Equity sector mappings
    SECTOR_GROUPS: dict[str, str] = {
        # Technology
        "AAPL": "TECH",
        "MSFT": "TECH",
        "GOOGL": "TECH",
        "GOOG": "TECH",
        "META": "TECH",
        "NVDA": "TECH",
        "AMD": "TECH",
        "INTC": "TECH",
        "TSLA": "TECH",
        "AMZN": "TECH",
        "CRM": "TECH",
        "ORCL": "TECH",
        "ADBE": "TECH",
        "NFLX": "TECH",
        # Finance
        "JPM": "FINANCE",
        "BAC": "FINANCE",
        "WFC": "FINANCE",
        "C": "FINANCE",
        "GS": "FINANCE",
        "MS": "FINANCE",
        "AXP": "FINANCE",
        "V": "FINANCE",
        "MA": "FINANCE",
        "BLK": "FINANCE",
        # Energy
        "XOM": "ENERGY",
        "CVX": "ENERGY",
        "COP": "ENERGY",
        "SLB": "ENERGY",
        "EOG": "ENERGY",
        "OXY": "ENERGY",
        "PSX": "ENERGY",
        "VLO": "ENERGY",
        # Healthcare
        "JNJ": "HEALTHCARE",
        "UNH": "HEALTHCARE",
        "PFE": "HEALTHCARE",
        "MRK": "HEALTHCARE",
        "ABBV": "HEALTHCARE",
        "LLY": "HEALTHCARE",
        "TMO": "HEALTHCARE",
        "ABT": "HEALTHCARE",
        # Consumer
        "WMT": "CONSUMER",
        "PG": "CONSUMER",
        "KO": "CONSUMER",
        "PEP": "CONSUMER",
        "COST": "CONSUMER",
        "HD": "CONSUMER",
        "MCD": "CONSUMER",
        "NKE": "CONSUMER",
        # Industrial
        "CAT": "INDUSTRIAL",
        "BA": "INDUSTRIAL",
        "HON": "INDUSTRIAL",
        "UPS": "INDUSTRIAL",
        "RTX": "INDUSTRIAL",
        "GE": "INDUSTRIAL",
        "MMM": "INDUSTRIAL",
        "DE": "INDUSTRIAL",
        # Utilities
        "NEE": "UTILITIES",
        "DUK": "UTILITIES",
        "SO": "UTILITIES",
        "D": "UTILITIES",
        "AEP": "UTILITIES",
    }

    # Commodity groups
    COMMODITY_GROUPS: dict[str, str] = {
        # Metals
        "XAUUSD": "COMMODITY_METALS",
        "GOLD": "COMMODITY_METALS",
        "GC": "COMMODITY_METALS",
        "XAGUSD": "COMMODITY_METALS",
        "SILVER": "COMMODITY_METALS",
        "SI": "COMMODITY_METALS",
        "COPPER": "COMMODITY_METALS",
        "HG": "COMMODITY_METALS",
        # Energy commodities
        "USOIL": "COMMODITY_ENERGY",
        "CL": "COMMODITY_ENERGY",
        "WTI": "COMMODITY_ENERGY",
        "BRENT": "COMMODITY_ENERGY",
        "NG": "COMMODITY_ENERGY",
        "NATGAS": "COMMODITY_ENERGY",
        # Agricultural
        "WHEAT": "COMMODITY_AGRI",
        "CORN": "COMMODITY_AGRI",
        "SOYBEAN": "COMMODITY_AGRI",
    }

    # Index groups
    INDEX_GROUPS: dict[str, str] = {
        # US indices
        "SPX": "INDEX_US",
        "SPX500": "INDEX_US",
        "SPY": "INDEX_US",
        "ES": "INDEX_US",
        "NDX": "INDEX_US",
        "NAS100": "INDEX_US",
        "QQQ": "INDEX_US",
        "NQ": "INDEX_US",
        "DJI": "INDEX_US",
        "US30": "INDEX_US",
        "YM": "INDEX_US",
        "RUT": "INDEX_US",
        "IWM": "INDEX_US",
        # EU indices
        "DAX": "INDEX_EU",
        "FTSE": "INDEX_EU",
        "UK100": "INDEX_EU",
        "CAC40": "INDEX_EU",
        "STOXX50": "INDEX_EU",
        # Asia indices
        "NIKKEI": "INDEX_ASIA",
        "JP225": "INDEX_ASIA",
        "HSI": "INDEX_ASIA",
        "HK50": "INDEX_ASIA",
        "CHINA50": "INDEX_ASIA",
        "ASX200": "INDEX_ASIA",
    }

    @staticmethod
    def get_correlation_group(symbol: str, category: AssetCategory) -> str:
        """
        Determine correlation group for a symbol based on its asset category.

        Parameters:
        -----------
        symbol : str
            Trading symbol (e.g., "EURUSD", "AAPL", "BTCUSD")
        category : AssetCategory
            Asset category enum value

        Returns:
        --------
        str
            Correlation group identifier (e.g., "USD_MAJOR", "EQUITY_TECH")

        Example:
        --------
        >>> CorrelationMapper.get_correlation_group("EURUSD", AssetCategory.FOREX)
        "USD_MAJOR"
        >>> CorrelationMapper.get_correlation_group("AAPL", AssetCategory.EQUITY)
        "EQUITY_TECH"
        """
        symbol_upper = symbol.upper()

        if category == AssetCategory.FOREX:
            return CorrelationMapper.FOREX_GROUPS.get(symbol_upper, "FOREX_OTHER")

        elif category == AssetCategory.CRYPTO:
            return CorrelationMapper.CRYPTO_GROUPS.get(symbol_upper, "CRYPTO_OTHER")

        elif category == AssetCategory.EQUITY:
            sector = CorrelationMapper.get_sector(symbol_upper)
            return f"EQUITY_{sector}"

        elif category == AssetCategory.COMMODITY:
            return CorrelationMapper.COMMODITY_GROUPS.get(symbol_upper, "COMMODITY_OTHER")

        elif category == AssetCategory.INDEX:
            return CorrelationMapper.INDEX_GROUPS.get(symbol_upper, "INDEX_OTHER")

        return "DEFAULT"

    @staticmethod
    def get_sector(symbol: str) -> str:
        """
        Get sector for an equity symbol.

        Parameters:
        -----------
        symbol : str
            Equity ticker symbol (e.g., "AAPL", "JPM")

        Returns:
        --------
        str
            Sector name (e.g., "TECH", "FINANCE", "UNKNOWN")

        Example:
        --------
        >>> CorrelationMapper.get_sector("AAPL")
        "TECH"
        >>> CorrelationMapper.get_sector("JPM")
        "FINANCE"
        >>> CorrelationMapper.get_sector("UNKNOWN_SYMBOL")
        "UNKNOWN"
        """
        return CorrelationMapper.SECTOR_GROUPS.get(symbol.upper(), "UNKNOWN")

    @staticmethod
    def detect_asset_category(symbol: str) -> AssetCategory:
        """
        Auto-detect asset category from symbol pattern.

        Heuristic detection based on symbol naming conventions:
        - Forex: 6 chars, ends with major currency (USD, EUR, GBP, JPY, etc.)
        - Crypto: Ends with USD/USDT and matches known crypto symbols
        - Index: Matches known index symbols
        - Commodity: Matches known commodity symbols
        - Equity: Default fallback for unknown symbols

        Parameters:
        -----------
        symbol : str
            Trading symbol

        Returns:
        --------
        AssetCategory
            Detected asset category

        Example:
        --------
        >>> CorrelationMapper.detect_asset_category("EURUSD")
        AssetCategory.FOREX
        >>> CorrelationMapper.detect_asset_category("BTCUSD")
        AssetCategory.CRYPTO
        """
        symbol_upper = symbol.upper()

        # Check known forex pairs
        if symbol_upper in CorrelationMapper.FOREX_GROUPS:
            return AssetCategory.FOREX

        # Check known crypto symbols
        if symbol_upper in CorrelationMapper.CRYPTO_GROUPS:
            return AssetCategory.CRYPTO

        # Check known indices
        if symbol_upper in CorrelationMapper.INDEX_GROUPS:
            return AssetCategory.INDEX

        # Check known commodities
        if symbol_upper in CorrelationMapper.COMMODITY_GROUPS:
            return AssetCategory.COMMODITY

        # Check known equities (by sector mapping)
        if symbol_upper in CorrelationMapper.SECTOR_GROUPS:
            return AssetCategory.EQUITY

        # Heuristic detection for forex (6-char pairs)
        currencies = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"}
        if len(symbol_upper) == 6:
            base = symbol_upper[:3]
            quote = symbol_upper[3:]
            if base in currencies and quote in currencies:
                return AssetCategory.FOREX

        # Default to UNKNOWN
        return AssetCategory.UNKNOWN

    @staticmethod
    def get_campaign_correlation_info(
        symbol: str, category: AssetCategory | None = None
    ) -> tuple[AssetCategory, str | None, str]:
        """
        Get complete correlation information for campaign creation.

        Convenience method that returns all correlation-related fields
        needed when creating a new campaign. Auto-detects category if not provided.

        Parameters:
        -----------
        symbol : str
            Trading symbol
        category : AssetCategory | None
            Optional pre-determined category. If None, auto-detects.

        Returns:
        --------
        tuple[AssetCategory, str | None, str]
            (asset_category, sector, correlation_group)

        Example:
        --------
        >>> cat, sector, group = CorrelationMapper.get_campaign_correlation_info("AAPL")
        >>> print(cat, sector, group)
        AssetCategory.EQUITY TECH EQUITY_TECH
        """
        # Auto-detect category if not provided
        if category is None:
            category = CorrelationMapper.detect_asset_category(symbol)

        # Get sector (only meaningful for equities)
        sector = None
        if category == AssetCategory.EQUITY:
            sector = CorrelationMapper.get_sector(symbol)
            if sector == "UNKNOWN":
                sector = None

        # Get correlation group
        correlation_group = CorrelationMapper.get_correlation_group(symbol, category)

        return category, sector, correlation_group
