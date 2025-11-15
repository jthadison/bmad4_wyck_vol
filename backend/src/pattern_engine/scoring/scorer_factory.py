"""
Confidence Scorer Factory.

This module implements the factory pattern for creating asset-class-specific
confidence scorers. It provides centralized asset class detection and automatic
scorer selection, enabling detectors to work seamlessly across stocks and forex
without knowing scorer implementation details.

Factory Pattern Benefits:
- Centralized asset class detection (no scattered if/else in detectors)
- Easy to add new asset classes (futures, crypto) without touching existing code
- Singleton pattern for performance (one scorer instance per asset class, cached)
- Clear separation of concerns (detection logic vs scoring logic)

Singleton Pattern Benefits:
- Performance: Create scorer once, reuse for all symbols of same asset class
- Memory: One scorer instance for all symbols of same asset class
- Consistency: Same scoring logic applied to all symbols of same asset class

Example Usage:
    >>> # Automatic asset class detection and scorer selection
    >>> scorer = get_scorer(detect_asset_class("EUR/USD"))
    >>> # Returns ForexConfidenceScorer (max_confidence=85)

    >>> scorer = get_scorer(detect_asset_class("AAPL"))
    >>> # Returns StockConfidenceScorer (max_confidence=100)

    >>> scorer = get_scorer(detect_asset_class("US30"))
    >>> # Returns ForexConfidenceScorer (CFD uses tick volume like forex)
"""

import structlog

from src.pattern_engine.base.confidence_scorer import ConfidenceScorer
from src.pattern_engine.scoring.forex_scorer import ForexConfidenceScorer
from src.pattern_engine.scoring.stock_scorer import StockConfidenceScorer

logger = structlog.get_logger()

# Singleton cache: One scorer instance per asset class
_scorer_cache: dict[str, ConfidenceScorer] = {}


def detect_asset_class(symbol: str) -> str:
    """
    Detect asset class from trading symbol.

    Asset Class Detection Logic (evaluated in priority order):
        1. Forex pairs (contains "/"): "EUR/USD", "GBP/JPY" → "forex"
        2. CFD indices (specific symbols): "US30", "NAS100" → "forex"
           (CFDs use tick volume, treat like forex for scoring)
        3. Stocks (default): "AAPL", "SPY", "MSFT" → "stock"
        4. Future support (commented out):
           - Futures: "ES", "NQ", "YM" → "futures"
           - Crypto: "BTC/USD", "ETH/USD" → "crypto"

    Args:
        symbol: Trading symbol to analyze

    Returns:
        Asset class: "stock", "forex", "futures", or "crypto"

    Examples:
        >>> detect_asset_class("EUR/USD")
        "forex"
        >>> detect_asset_class("US30")
        "forex"  # CFD index uses tick volume
        >>> detect_asset_class("AAPL")
        "stock"
    """
    # 1. Forex pairs (contains "/")
    if "/" in symbol:
        logger.debug(
            "asset_class_detected",
            symbol=symbol,
            asset_class="forex",
            reason="contains_slash",
        )
        return "forex"

    # 2. CFD indices (treat like forex - use tick volume)
    cfd_indices = ["US30", "NAS100", "SPX500", "GER40", "UK100", "JPN225"]
    if symbol in cfd_indices:
        logger.debug(
            "asset_class_detected",
            symbol=symbol,
            asset_class="forex",
            reason="cfd_index",
        )
        return "forex"  # CFDs use tick volume, treat like forex

    # Future support - uncomment when futures implemented
    # futures_symbols = ["ES", "NQ", "YM", "CL", "GC", "ZB"]
    # if symbol in futures_symbols:
    #     logger.debug(
    #         "asset_class_detected",
    #         symbol=symbol,
    #         asset_class="futures",
    #         reason="futures_symbol"
    #     )
    #     return "futures"

    # Future support - uncomment when crypto implemented
    # crypto_keywords = ["BTC", "ETH", "SOL", "USDT"]
    # if any(keyword in symbol for keyword in crypto_keywords):
    #     logger.debug(
    #         "asset_class_detected",
    #         symbol=symbol,
    #         asset_class="crypto",
    #         reason="crypto_keyword"
    #     )
    #     return "crypto"

    # 3. Default to stock
    logger.debug("asset_class_detected", symbol=symbol, asset_class="stock", reason="default")
    return "stock"


def get_scorer(asset_class: str) -> ConfidenceScorer:
    """
    Get confidence scorer for asset class (singleton pattern).

    Returns cached scorer instance if available, otherwise creates new instance
    and caches it for future use. This ensures one scorer instance per asset class.

    Args:
        asset_class: Asset class ("stock", "forex", "futures", "crypto")

    Returns:
        ConfidenceScorer instance for the specified asset class

    Raises:
        ValueError: If asset class is not supported

    Examples:
        >>> scorer = get_scorer("stock")
        >>> isinstance(scorer, StockConfidenceScorer)
        True
        >>> scorer.max_confidence
        100

        >>> scorer = get_scorer("forex")
        >>> isinstance(scorer, ForexConfidenceScorer)
        True
        >>> scorer.max_confidence
        85

        >>> scorer1 = get_scorer("stock")
        >>> scorer2 = get_scorer("stock")
        >>> scorer1 is scorer2  # Same instance (cached)
        True
    """
    # Check cache first (singleton pattern)
    if asset_class in _scorer_cache:
        logger.debug("scorer_cache_hit", asset_class=asset_class)
        return _scorer_cache[asset_class]

    # Create new scorer and cache it
    logger.info("creating_scorer", asset_class=asset_class)
    scorer = _create_scorer(asset_class)
    _scorer_cache[asset_class] = scorer

    # Log scorer details
    logger.info(
        "creating_confidence_scorer",
        asset_class=asset_class,
        scorer_type=scorer.__class__.__name__,
        volume_reliability=scorer.volume_reliability,
        max_confidence=scorer.max_confidence,
    )

    return scorer


def _create_scorer(asset_class: str) -> ConfidenceScorer:
    """
    Create confidence scorer for asset class (internal helper).

    Args:
        asset_class: Asset class ("stock", "forex", "futures", "crypto")

    Returns:
        ConfidenceScorer instance for the specified asset class

    Raises:
        ValueError: If asset class is not supported
    """
    supported_asset_classes = ["stock", "forex"]

    if asset_class == "stock":
        return StockConfidenceScorer()
    elif asset_class == "forex":
        return ForexConfidenceScorer()
    else:
        logger.error(
            "unsupported_asset_class",
            asset_class=asset_class,
            supported=supported_asset_classes,
        )
        raise ValueError(
            f"Unsupported asset class: {asset_class}. "
            f"Supported: {', '.join(supported_asset_classes)}"
        )
