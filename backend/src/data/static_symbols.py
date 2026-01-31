"""
Static Symbol Fallback Lists (Story 21.2)

Provides static lists of known symbols for fallback validation when
TwelveData API is unavailable. Used for graceful degradation.

Lists include:
- STATIC_FOREX_PAIRS: 50+ forex pairs (majors, minors, exotics)
- STATIC_INDICES: 20+ major world indices
- STATIC_CRYPTO: 20+ major cryptocurrencies
"""

from typing import Any

# ============================================================================
# Forex Pairs (50+ pairs)
# ============================================================================

STATIC_FOREX_PAIRS: list[dict[str, Any]] = [
    # Major Pairs (7)
    {"symbol": "EURUSD", "name": "Euro / US Dollar", "exchange": "FOREX", "type": "forex"},
    {"symbol": "GBPUSD", "name": "British Pound / US Dollar", "exchange": "FOREX", "type": "forex"},
    {"symbol": "USDJPY", "name": "US Dollar / Japanese Yen", "exchange": "FOREX", "type": "forex"},
    {
        "symbol": "AUDUSD",
        "name": "Australian Dollar / US Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "USDCAD",
        "name": "US Dollar / Canadian Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {"symbol": "USDCHF", "name": "US Dollar / Swiss Franc", "exchange": "FOREX", "type": "forex"},
    {
        "symbol": "NZDUSD",
        "name": "New Zealand Dollar / US Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    # Euro Crosses (8)
    {"symbol": "EURGBP", "name": "Euro / British Pound", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURJPY", "name": "Euro / Japanese Yen", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURAUD", "name": "Euro / Australian Dollar", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURCAD", "name": "Euro / Canadian Dollar", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURCHF", "name": "Euro / Swiss Franc", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURNZD", "name": "Euro / New Zealand Dollar", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURSGD", "name": "Euro / Singapore Dollar", "exchange": "FOREX", "type": "forex"},
    {"symbol": "EURHKD", "name": "Euro / Hong Kong Dollar", "exchange": "FOREX", "type": "forex"},
    # GBP Crosses (7)
    {
        "symbol": "GBPJPY",
        "name": "British Pound / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "GBPAUD",
        "name": "British Pound / Australian Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "GBPCAD",
        "name": "British Pound / Canadian Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "GBPCHF",
        "name": "British Pound / Swiss Franc",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "GBPNZD",
        "name": "British Pound / New Zealand Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "GBPSGD",
        "name": "British Pound / Singapore Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "GBPHKD",
        "name": "British Pound / Hong Kong Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    # JPY Crosses (6)
    {
        "symbol": "AUDJPY",
        "name": "Australian Dollar / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "CADJPY",
        "name": "Canadian Dollar / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "CHFJPY",
        "name": "Swiss Franc / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "NZDJPY",
        "name": "New Zealand Dollar / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "SGDJPY",
        "name": "Singapore Dollar / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "HKDJPY",
        "name": "Hong Kong Dollar / Japanese Yen",
        "exchange": "FOREX",
        "type": "forex",
    },
    # AUD Crosses (5)
    {
        "symbol": "AUDCAD",
        "name": "Australian Dollar / Canadian Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "AUDCHF",
        "name": "Australian Dollar / Swiss Franc",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "AUDNZD",
        "name": "Australian Dollar / New Zealand Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "AUDSGD",
        "name": "Australian Dollar / Singapore Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "AUDHKD",
        "name": "Australian Dollar / Hong Kong Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    # CAD Crosses (4)
    {
        "symbol": "CADCHF",
        "name": "Canadian Dollar / Swiss Franc",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "CADSGD",
        "name": "Canadian Dollar / Singapore Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "CADHKD",
        "name": "Canadian Dollar / Hong Kong Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "NZDCAD",
        "name": "New Zealand Dollar / Canadian Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    # CHF Crosses (3)
    {
        "symbol": "NZDCHF",
        "name": "New Zealand Dollar / Swiss Franc",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "SGDCHF",
        "name": "Singapore Dollar / Swiss Franc",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "HKDCHF",
        "name": "Hong Kong Dollar / Swiss Franc",
        "exchange": "FOREX",
        "type": "forex",
    },
    # Exotic Pairs (10)
    {"symbol": "USDMXN", "name": "US Dollar / Mexican Peso", "exchange": "FOREX", "type": "forex"},
    {
        "symbol": "USDZAR",
        "name": "US Dollar / South African Rand",
        "exchange": "FOREX",
        "type": "forex",
    },
    {"symbol": "USDTRY", "name": "US Dollar / Turkish Lira", "exchange": "FOREX", "type": "forex"},
    {"symbol": "USDSEK", "name": "US Dollar / Swedish Krona", "exchange": "FOREX", "type": "forex"},
    {
        "symbol": "USDNOK",
        "name": "US Dollar / Norwegian Krone",
        "exchange": "FOREX",
        "type": "forex",
    },
    {"symbol": "USDDKK", "name": "US Dollar / Danish Krone", "exchange": "FOREX", "type": "forex"},
    {
        "symbol": "USDSGD",
        "name": "US Dollar / Singapore Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {
        "symbol": "USDHKD",
        "name": "US Dollar / Hong Kong Dollar",
        "exchange": "FOREX",
        "type": "forex",
    },
    {"symbol": "USDPLN", "name": "US Dollar / Polish Zloty", "exchange": "FOREX", "type": "forex"},
    {
        "symbol": "USDCNH",
        "name": "US Dollar / Chinese Yuan Offshore",
        "exchange": "FOREX",
        "type": "forex",
    },
]

# ============================================================================
# Indices (20+ indices)
# ============================================================================

STATIC_INDICES: list[dict[str, Any]] = [
    # US Indices
    {"symbol": "SPX", "name": "S&P 500", "exchange": "INDEX", "type": "index"},
    {"symbol": "NDX", "name": "NASDAQ 100", "exchange": "INDEX", "type": "index"},
    {"symbol": "DJI", "name": "Dow Jones Industrial Average", "exchange": "INDEX", "type": "index"},
    {"symbol": "RUT", "name": "Russell 2000", "exchange": "INDEX", "type": "index"},
    {"symbol": "VIX", "name": "CBOE Volatility Index", "exchange": "INDEX", "type": "index"},
    # European Indices
    {"symbol": "FTSE", "name": "FTSE 100", "exchange": "INDEX", "type": "index"},
    {"symbol": "DAX", "name": "DAX 40", "exchange": "INDEX", "type": "index"},
    {"symbol": "CAC", "name": "CAC 40", "exchange": "INDEX", "type": "index"},
    {"symbol": "IBEX", "name": "IBEX 35", "exchange": "INDEX", "type": "index"},
    {"symbol": "SMI", "name": "Swiss Market Index", "exchange": "INDEX", "type": "index"},
    {"symbol": "AEX", "name": "AEX Amsterdam", "exchange": "INDEX", "type": "index"},
    {"symbol": "STOXX50", "name": "Euro Stoxx 50", "exchange": "INDEX", "type": "index"},
    # Asian Indices
    {"symbol": "NIKKEI", "name": "Nikkei 225", "exchange": "INDEX", "type": "index"},
    {"symbol": "HSI", "name": "Hang Seng Index", "exchange": "INDEX", "type": "index"},
    {"symbol": "SSEC", "name": "Shanghai Composite", "exchange": "INDEX", "type": "index"},
    {"symbol": "KOSPI", "name": "KOSPI Composite", "exchange": "INDEX", "type": "index"},
    {"symbol": "TWSE", "name": "Taiwan Weighted", "exchange": "INDEX", "type": "index"},
    {"symbol": "SENSEX", "name": "BSE SENSEX", "exchange": "INDEX", "type": "index"},
    {"symbol": "NIFTY", "name": "NIFTY 50", "exchange": "INDEX", "type": "index"},
    # Other Indices
    {"symbol": "ASX", "name": "S&P/ASX 200", "exchange": "INDEX", "type": "index"},
    {"symbol": "TSX", "name": "S&P/TSX Composite", "exchange": "INDEX", "type": "index"},
    {"symbol": "BOVESPA", "name": "Bovespa Index", "exchange": "INDEX", "type": "index"},
]

# ============================================================================
# Cryptocurrencies (20+ crypto)
# ============================================================================

STATIC_CRYPTO: list[dict[str, Any]] = [
    # Major Cryptocurrencies
    {"symbol": "BTC/USD", "name": "Bitcoin / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "ETH/USD", "name": "Ethereum / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "SOL/USD", "name": "Solana / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "XRP/USD", "name": "Ripple / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "ADA/USD", "name": "Cardano / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "DOGE/USD", "name": "Dogecoin / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "DOT/USD", "name": "Polkadot / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "AVAX/USD", "name": "Avalanche / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "MATIC/USD", "name": "Polygon / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "LINK/USD", "name": "Chainlink / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "LTC/USD", "name": "Litecoin / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {
        "symbol": "BCH/USD",
        "name": "Bitcoin Cash / US Dollar",
        "exchange": "CRYPTO",
        "type": "crypto",
    },
    {"symbol": "XLM/USD", "name": "Stellar / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "ATOM/USD", "name": "Cosmos / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "UNI/USD", "name": "Uniswap / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {
        "symbol": "ETC/USD",
        "name": "Ethereum Classic / US Dollar",
        "exchange": "CRYPTO",
        "type": "crypto",
    },
    {"symbol": "ALGO/USD", "name": "Algorand / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "FIL/USD", "name": "Filecoin / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "APT/USD", "name": "Aptos / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "ARB/USD", "name": "Arbitrum / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
    {"symbol": "OP/USD", "name": "Optimism / US Dollar", "exchange": "CRYPTO", "type": "crypto"},
]


def get_static_symbols(asset_class: str) -> list[dict[str, Any]]:
    """
    Get static symbols for an asset class.

    Args:
        asset_class: Asset class (forex, index, crypto)

    Returns:
        List of symbol dictionaries with symbol, name, exchange, type
    """
    asset_class_lower = asset_class.lower()
    if asset_class_lower == "forex":
        return STATIC_FOREX_PAIRS
    elif asset_class_lower == "index":
        return STATIC_INDICES
    elif asset_class_lower == "crypto":
        return STATIC_CRYPTO
    return []


def is_known_symbol(symbol: str, asset_class: str) -> bool:
    """
    Check if symbol exists in static list.

    Args:
        symbol: Symbol to check (e.g., EURUSD, BTC/USD)
        asset_class: Asset class (forex, index, crypto)

    Returns:
        True if symbol is in the static list
    """
    symbols = get_static_symbols(asset_class)
    symbol_upper = symbol.upper()
    # Also check without slash for crypto
    symbol_no_slash = symbol_upper.replace("/", "")
    return any(
        s["symbol"].upper() == symbol_upper
        or s["symbol"].upper().replace("/", "") == symbol_no_slash
        for s in symbols
    )


def get_symbol_info_from_static(symbol: str, asset_class: str) -> dict[str, Any] | None:
    """
    Get symbol info from static list.

    Args:
        symbol: Symbol to look up
        asset_class: Asset class (forex, index, crypto)

    Returns:
        Symbol dictionary if found, None otherwise
    """
    symbols = get_static_symbols(asset_class)
    symbol_upper = symbol.upper()
    symbol_no_slash = symbol_upper.replace("/", "")

    for s in symbols:
        s_symbol = s["symbol"].upper()
        if s_symbol == symbol_upper or s_symbol.replace("/", "") == symbol_no_slash:
            return s

    return None
