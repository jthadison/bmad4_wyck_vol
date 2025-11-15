"""
Unit tests for Confidence Scorer Factory.

Tests cover:
1. Asset class detection (forex pairs, CFD indices, stocks)
2. Scorer factory (correct scorer instances returned)
3. Singleton caching (same instance returned on multiple calls)
4. Error handling (unsupported asset classes)
5. Scorer properties (max_confidence, volume_reliability, asset_class)
"""

import pytest

from src.pattern_engine.scoring.forex_scorer import ForexConfidenceScorer
from src.pattern_engine.scoring.scorer_factory import (
    _create_scorer,
    _scorer_cache,
    detect_asset_class,
    get_scorer,
)
from src.pattern_engine.scoring.stock_scorer import StockConfidenceScorer


class TestDetectAssetClass:
    """Test asset class detection from symbols."""

    def test_detect_asset_class_forex_pairs(self) -> None:
        """Forex pairs (contains '/') should be detected as 'forex'."""
        assert detect_asset_class("EUR/USD") == "forex"
        assert detect_asset_class("GBP/JPY") == "forex"
        assert detect_asset_class("AUD/CAD") == "forex"
        assert detect_asset_class("USD/CHF") == "forex"
        assert detect_asset_class("NZD/USD") == "forex"

    def test_detect_asset_class_cfd_indices(self) -> None:
        """CFD indices should be detected as 'forex' (use tick volume)."""
        # CFD indices use tick volume (no real institutional volume)
        # Treat like forex for scoring purposes
        assert detect_asset_class("US30") == "forex"  # Dow Jones CFD
        assert detect_asset_class("NAS100") == "forex"  # NASDAQ 100 CFD
        assert detect_asset_class("SPX500") == "forex"  # S&P 500 CFD
        assert detect_asset_class("GER40") == "forex"  # DAX CFD
        assert detect_asset_class("UK100") == "forex"  # FTSE 100 CFD
        assert detect_asset_class("JPN225") == "forex"  # Nikkei 225 CFD

    def test_detect_asset_class_stocks(self) -> None:
        """Stocks should be detected as 'stock' (default)."""
        assert detect_asset_class("AAPL") == "stock"
        assert detect_asset_class("SPY") == "stock"
        assert detect_asset_class("MSFT") == "stock"
        assert detect_asset_class("TSLA") == "stock"
        assert detect_asset_class("GOOGL") == "stock"

    def test_detect_asset_class_edge_cases(self) -> None:
        """Edge cases should default to 'stock'."""
        # Unknown symbols default to stock
        assert detect_asset_class("XYZ123") == "stock"
        assert detect_asset_class("") == "stock"
        assert detect_asset_class("A") == "stock"

    def test_detect_asset_class_case_sensitivity(self) -> None:
        """Asset class detection should be case-sensitive for exact matching."""
        # Forex pairs work regardless of case (contains "/" check)
        assert detect_asset_class("eur/usd") == "forex"
        assert detect_asset_class("EUR/USD") == "forex"

        # CFD indices require exact match (case-sensitive)
        assert detect_asset_class("US30") == "forex"
        assert detect_asset_class("us30") == "stock"  # Different case = not in CFD list


class TestGetScorer:
    """Test scorer factory with singleton pattern."""

    def setup_method(self) -> None:
        """Clear scorer cache before each test."""
        _scorer_cache.clear()

    def test_get_scorer_stock(self) -> None:
        """Should return StockConfidenceScorer for 'stock' asset class."""
        scorer = get_scorer("stock")

        # Verify correct scorer type
        assert isinstance(scorer, StockConfidenceScorer)

        # Verify scorer properties
        assert scorer.asset_class == "stock"
        assert scorer.max_confidence == 100
        assert scorer.volume_reliability == "HIGH"

    def test_get_scorer_forex(self) -> None:
        """Should return ForexConfidenceScorer for 'forex' asset class."""
        scorer = get_scorer("forex")

        # Verify correct scorer type
        assert isinstance(scorer, ForexConfidenceScorer)

        # Verify scorer properties
        assert scorer.asset_class == "forex"
        assert scorer.max_confidence == 85
        assert scorer.volume_reliability == "LOW"

    def test_get_scorer_unsupported_asset_class_futures(self) -> None:
        """Should raise ValueError for unsupported 'futures' asset class."""
        with pytest.raises(
            ValueError, match="Unsupported asset class: futures. Supported: stock, forex"
        ):
            get_scorer("futures")

    def test_get_scorer_unsupported_asset_class_crypto(self) -> None:
        """Should raise ValueError for unsupported 'crypto' asset class."""
        with pytest.raises(
            ValueError, match="Unsupported asset class: crypto. Supported: stock, forex"
        ):
            get_scorer("crypto")

    def test_get_scorer_unsupported_asset_class_invalid(self) -> None:
        """Should raise ValueError for invalid asset class."""
        with pytest.raises(
            ValueError,
            match="Unsupported asset class: invalid_class. Supported: stock, forex",
        ):
            get_scorer("invalid_class")


class TestSingletonPattern:
    """Test singleton caching behavior."""

    def setup_method(self) -> None:
        """Clear scorer cache before each test."""
        _scorer_cache.clear()

    def test_scorer_singleton_pattern_stock(self) -> None:
        """Should return same StockConfidenceScorer instance on multiple calls."""
        scorer1 = get_scorer("stock")
        scorer2 = get_scorer("stock")
        scorer3 = get_scorer("stock")

        # All calls should return the exact same instance
        assert scorer1 is scorer2
        assert scorer2 is scorer3
        assert scorer1 is scorer3

    def test_scorer_singleton_pattern_forex(self) -> None:
        """Should return same ForexConfidenceScorer instance on multiple calls."""
        scorer1 = get_scorer("forex")
        scorer2 = get_scorer("forex")
        scorer3 = get_scorer("forex")

        # All calls should return the exact same instance
        assert scorer1 is scorer2
        assert scorer2 is scorer3
        assert scorer1 is scorer3

    def test_scorer_singleton_pattern_different_asset_classes(self) -> None:
        """Different asset classes should have separate cached instances."""
        stock_scorer = get_scorer("stock")
        forex_scorer = get_scorer("forex")

        # Different asset classes = different instances
        assert stock_scorer is not forex_scorer

        # Verify they're different types
        assert isinstance(stock_scorer, StockConfidenceScorer)
        assert isinstance(forex_scorer, ForexConfidenceScorer)

        # But repeated calls should return same instances
        assert stock_scorer is get_scorer("stock")
        assert forex_scorer is get_scorer("forex")

    def test_scorer_cache_populated(self) -> None:
        """Cache should be populated after creating scorers."""
        assert len(_scorer_cache) == 0

        get_scorer("stock")
        assert len(_scorer_cache) == 1
        assert "stock" in _scorer_cache

        get_scorer("forex")
        assert len(_scorer_cache) == 2
        assert "forex" in _scorer_cache

        # Repeated calls should not increase cache size
        get_scorer("stock")
        get_scorer("forex")
        assert len(_scorer_cache) == 2


class TestCreateScorer:
    """Test internal _create_scorer helper."""

    def test_create_scorer_stock(self) -> None:
        """Should create StockConfidenceScorer for 'stock' asset class."""
        scorer = _create_scorer("stock")
        assert isinstance(scorer, StockConfidenceScorer)
        assert scorer.asset_class == "stock"

    def test_create_scorer_forex(self) -> None:
        """Should create ForexConfidenceScorer for 'forex' asset class."""
        scorer = _create_scorer("forex")
        assert isinstance(scorer, ForexConfidenceScorer)
        assert scorer.asset_class == "forex"

    def test_create_scorer_unsupported(self) -> None:
        """Should raise ValueError for unsupported asset class."""
        with pytest.raises(ValueError, match="Unsupported asset class: futures"):
            _create_scorer("futures")


class TestIntegrationWithScorers:
    """Integration tests: Factory → Scorers."""

    def setup_method(self) -> None:
        """Clear scorer cache before each test."""
        _scorer_cache.clear()

    def test_factory_stock_scorer_properties(self) -> None:
        """Factory should return stock scorer with correct properties."""
        scorer = get_scorer("stock")

        # StockConfidenceScorer properties (from Story 0.2)
        assert scorer.asset_class == "stock"
        assert scorer.max_confidence == 100
        assert scorer.volume_reliability == "HIGH"

    def test_factory_forex_scorer_properties(self) -> None:
        """Factory should return forex scorer with correct properties."""
        scorer = get_scorer("forex")

        # ForexConfidenceScorer properties (from Story 0.3)
        assert scorer.asset_class == "forex"
        assert scorer.max_confidence == 85
        assert scorer.volume_reliability == "LOW"

    def test_end_to_end_symbol_to_scorer_stock(self) -> None:
        """End-to-end: Symbol → Asset class → Scorer (stock)."""
        # 1. Detect asset class
        asset_class = detect_asset_class("AAPL")
        assert asset_class == "stock"

        # 2. Get scorer
        scorer = get_scorer(asset_class)
        assert isinstance(scorer, StockConfidenceScorer)
        assert scorer.max_confidence == 100

    def test_end_to_end_symbol_to_scorer_forex(self) -> None:
        """End-to-end: Symbol → Asset class → Scorer (forex)."""
        # 1. Detect asset class
        asset_class = detect_asset_class("EUR/USD")
        assert asset_class == "forex"

        # 2. Get scorer
        scorer = get_scorer(asset_class)
        assert isinstance(scorer, ForexConfidenceScorer)
        assert scorer.max_confidence == 85

    def test_end_to_end_symbol_to_scorer_cfd(self) -> None:
        """End-to-end: Symbol → Asset class → Scorer (CFD treated as forex)."""
        # 1. Detect asset class (CFD indices use tick volume)
        asset_class = detect_asset_class("US30")
        assert asset_class == "forex"  # CFDs treated as forex

        # 2. Get scorer
        scorer = get_scorer(asset_class)
        assert isinstance(scorer, ForexConfidenceScorer)
        assert scorer.max_confidence == 85
        assert scorer.volume_reliability == "LOW"  # Low reliability for tick volume
