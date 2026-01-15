"""
Unit tests for SpringRiskAnalyzer

Tests all calculation methods individually to ensure testability and correctness.
Each method is tested with boundary values and representative cases.

Story 18.8.3: Spring Risk Analyzer
AC6: 95%+ test coverage
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.detectors.spring.models import SpringCandidate, SpringRiskProfile
from src.pattern_engine.detectors.spring.risk_analyzer import (
    DEFAULT_RISK_CONFIG,
    RiskConfig,
    SpringRiskAnalyzer,
)

# ================================================================
# Shared Fixtures
# ================================================================


@pytest.fixture
def analyzer():
    """Create analyzer instance for all tests."""
    return SpringRiskAnalyzer()


@pytest.fixture
def sample_bar():
    """Create a sample OHLCV bar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=150000,
        spread=Decimal("3.00"),
        timeframe="1d",
    )


@pytest.fixture
def sample_candidate(sample_bar):
    """Create a sample SpringCandidate for testing."""
    return SpringCandidate(
        bar_index=25,
        bar=sample_bar,
        penetration_pct=Decimal("0.02"),
        recovery_pct=Decimal("0.015"),
        creek_level=Decimal("100.00"),
    )


@pytest.fixture
def mock_trading_range():
    """Create mock TradingRange with Ice level."""
    trading_range = MagicMock()
    type(trading_range).ice_level = PropertyMock(return_value=Decimal("110.00"))
    return trading_range


# ================================================================
# RiskConfig Tests
# ================================================================


class TestRiskConfig:
    """Tests for RiskConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = RiskConfig()

        assert config.stop_buffer_pct == Decimal("0.02")
        assert config.min_rr_ratio == Decimal("1.5")
        assert config.max_stop_distance_pct == Decimal("0.10")

    def test_custom_config_values(self):
        """Test custom configuration."""
        config = RiskConfig(
            stop_buffer_pct=Decimal("0.03"),
            min_rr_ratio=Decimal("2.0"),
            max_stop_distance_pct=Decimal("0.08"),
        )

        assert config.stop_buffer_pct == Decimal("0.03")
        assert config.min_rr_ratio == Decimal("2.0")
        assert config.max_stop_distance_pct == Decimal("0.08")

    def test_default_risk_config_is_correct(self):
        """Test DEFAULT_RISK_CONFIG module-level constant."""
        assert DEFAULT_RISK_CONFIG.stop_buffer_pct == Decimal("0.02")
        assert DEFAULT_RISK_CONFIG.min_rr_ratio == Decimal("1.5")
        assert DEFAULT_RISK_CONFIG.max_stop_distance_pct == Decimal("0.10")


# ================================================================
# SpringRiskAnalyzer Tests
# ================================================================


class TestSpringRiskAnalyzer:
    """Tests for SpringRiskAnalyzer class."""

    # ================================================================
    # Initialization Tests
    # ================================================================

    class TestInit:
        """Tests for __init__ method."""

        def test_init_with_default_config(self):
            """Test initialization with default config."""
            analyzer = SpringRiskAnalyzer()
            assert analyzer.config == DEFAULT_RISK_CONFIG

        def test_init_with_custom_config(self):
            """Test initialization with custom config."""
            custom_config = RiskConfig(stop_buffer_pct=Decimal("0.03"))
            analyzer = SpringRiskAnalyzer(config=custom_config)
            assert analyzer.config.stop_buffer_pct == Decimal("0.03")

    # ================================================================
    # Stop Loss Calculation Tests (_calculate_stop_loss)
    # ================================================================

    class TestCalculateStopLoss:
        """Tests for _calculate_stop_loss method."""

        def test_stop_loss_with_default_buffer(self, analyzer):
            """Stop loss is spring_low - 2% buffer."""
            stop_loss, is_valid = analyzer._calculate_stop_loss(
                spring_low=Decimal("100.00"),
                entry_price=Decimal("102.00"),
            )

            # Expected: 100 * (1 - 0.02) = 98.00
            assert stop_loss == Decimal("98.00")
            assert is_valid is True

        def test_stop_loss_with_custom_buffer(self):
            """Stop loss respects custom buffer percentage."""
            config = RiskConfig(stop_buffer_pct=Decimal("0.03"))
            analyzer = SpringRiskAnalyzer(config=config)

            stop_loss, is_valid = analyzer._calculate_stop_loss(
                spring_low=Decimal("100.00"),
                entry_price=Decimal("102.00"),
            )

            # Expected: 100 * (1 - 0.03) = 97.00
            assert stop_loss == Decimal("97.00")
            assert is_valid is True

        def test_stop_loss_exceeds_max_distance(self, analyzer):
            """Stop loss marked invalid if exceeds max distance."""
            # Entry at 100, spring low at 85
            # Stop = 85 * 0.98 = 83.30
            # Distance = (100 - 83.30) / 100 = 16.7% (> 10% max)
            stop_loss, is_valid = analyzer._calculate_stop_loss(
                spring_low=Decimal("85.00"),
                entry_price=Decimal("100.00"),
            )

            assert is_valid is False

        def test_stop_loss_at_max_distance_boundary(self, analyzer):
            """Stop loss valid when exactly at max distance."""
            # Calculate spring_low that results in exactly 10% stop distance
            # Entry = 100, stop_distance = 10%, stop_price = 90
            # stop_price = spring_low * 0.98 = 90 → spring_low = 91.84
            stop_loss, is_valid = analyzer._calculate_stop_loss(
                spring_low=Decimal("91.84"),
                entry_price=Decimal("100.00"),
            )

            # Stop = 91.84 * 0.98 ≈ 90.00
            assert is_valid is True

        def test_stop_loss_with_decimal_precision(self, analyzer):
            """Stop loss calculation maintains decimal precision."""
            stop_loss, _ = analyzer._calculate_stop_loss(
                spring_low=Decimal("123.456789"),
                entry_price=Decimal("125.00"),
            )

            # Expected: 123.456789 * 0.98 = 120.98765322
            expected = Decimal("123.456789") * Decimal("0.98")
            assert stop_loss == expected

    # ================================================================
    # Target Calculation Tests (_calculate_target)
    # ================================================================

    class TestCalculateTarget:
        """Tests for _calculate_target method."""

        def test_target_from_ice_level(self, analyzer, mock_trading_range):
            """Target is Ice level from trading range."""
            target = analyzer._calculate_target(mock_trading_range)
            assert target == Decimal("110.00")

        def test_target_raises_if_no_ice_level(self, analyzer):
            """Target calculation raises if Ice level is None."""
            trading_range = MagicMock()
            type(trading_range).ice_level = PropertyMock(return_value=None)

            with pytest.raises(ValueError, match="Ice level"):
                analyzer._calculate_target(trading_range)

    # ================================================================
    # Entry Price Calculation Tests (_calculate_entry_price)
    # ================================================================

    class TestCalculateEntryPrice:
        """Tests for _calculate_entry_price method."""

        def test_entry_is_bar_close(self, analyzer, sample_candidate):
            """Entry price is the close of the Spring bar."""
            entry = analyzer._calculate_entry_price(sample_candidate)
            assert entry == Decimal("100.50")

    # ================================================================
    # Risk/Reward Ratio Tests (_calculate_rr_ratio)
    # ================================================================

    class TestCalculateRRRatio:
        """Tests for _calculate_rr_ratio method."""

        def test_rr_ratio_calculation(self, analyzer):
            """R:R ratio correctly calculated."""
            # Entry: 100, Stop: 96, Target: 110
            # Risk: 100 - 96 = 4
            # Reward: 110 - 100 = 10
            # R:R: 10 / 4 = 2.5
            rr = analyzer._calculate_rr_ratio(
                entry_price=Decimal("100.00"),
                stop_loss=Decimal("96.00"),
                target=Decimal("110.00"),
            )

            assert rr == Decimal("2.50")

        def test_rr_ratio_1_to_1(self, analyzer):
            """R:R ratio of 1:1 calculated correctly."""
            # Risk = Reward
            rr = analyzer._calculate_rr_ratio(
                entry_price=Decimal("100.00"),
                stop_loss=Decimal("95.00"),
                target=Decimal("105.00"),
            )

            assert rr == Decimal("1.00")

        def test_rr_ratio_with_zero_reward(self, analyzer):
            """R:R ratio returns 0 if target below entry."""
            rr = analyzer._calculate_rr_ratio(
                entry_price=Decimal("100.00"),
                stop_loss=Decimal("96.00"),
                target=Decimal("99.00"),
            )

            assert rr == Decimal("0")

        def test_rr_ratio_raises_if_stop_at_entry(self, analyzer):
            """R:R calculation raises if stop equals entry."""
            with pytest.raises(ValueError, match="below entry"):
                analyzer._calculate_rr_ratio(
                    entry_price=Decimal("100.00"),
                    stop_loss=Decimal("100.00"),
                    target=Decimal("110.00"),
                )

        def test_rr_ratio_raises_if_stop_above_entry(self, analyzer):
            """R:R calculation raises if stop above entry."""
            with pytest.raises(ValueError, match="below entry"):
                analyzer._calculate_rr_ratio(
                    entry_price=Decimal("100.00"),
                    stop_loss=Decimal("102.00"),
                    target=Decimal("110.00"),
                )

        def test_rr_ratio_decimal_precision(self, analyzer):
            """R:R ratio rounds to 2 decimal places."""
            # 10 / 3 = 3.333... → 3.33
            rr = analyzer._calculate_rr_ratio(
                entry_price=Decimal("100.00"),
                stop_loss=Decimal("97.00"),
                target=Decimal("110.00"),
            )

            assert rr == Decimal("3.33")

    # ================================================================
    # Position Recommendation Tests (_calculate_position_recommendation)
    # ================================================================

    class TestCalculatePositionRecommendation:
        """Tests for _calculate_position_recommendation method."""

        def test_full_position_rr_2_plus(self, analyzer):
            """R:R >= 2.0 with valid stop recommends FULL position."""
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("2.5"),
                stop_valid=True,
            )
            assert rec == "FULL"

        def test_full_position_boundary_rr_2(self, analyzer):
            """R:R exactly 2.0 recommends FULL position."""
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("2.0"),
                stop_valid=True,
            )
            assert rec == "FULL"

        def test_reduced_position_rr_1_5_to_2(self, analyzer):
            """R:R 1.5-2.0 with valid stop recommends REDUCED position."""
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("1.75"),
                stop_valid=True,
            )
            assert rec == "REDUCED"

        def test_reduced_position_boundary_rr_1_5(self, analyzer):
            """R:R exactly 1.5 recommends REDUCED position."""
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("1.5"),
                stop_valid=True,
            )
            assert rec == "REDUCED"

        def test_skip_position_rr_below_1_5(self, analyzer):
            """R:R < 1.5 recommends SKIP."""
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("1.4"),
                stop_valid=True,
            )
            assert rec == "SKIP"

        def test_skip_position_invalid_stop(self, analyzer):
            """Invalid stop always recommends SKIP regardless of R:R."""
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("3.0"),
                stop_valid=False,
            )
            assert rec == "SKIP"

        def test_skip_position_custom_min_rr(self):
            """Custom min_rr_ratio affects REDUCED threshold."""
            config = RiskConfig(min_rr_ratio=Decimal("2.0"))
            analyzer = SpringRiskAnalyzer(config=config)

            # 1.5 is now below custom min of 2.0
            rec = analyzer._calculate_position_recommendation(
                rr_ratio=Decimal("1.5"),
                stop_valid=True,
            )
            assert rec == "SKIP"

    # ================================================================
    # Analyze Method Tests (Integration)
    # ================================================================

    class TestAnalyze:
        """Tests for analyze method (integration of all calculations)."""

        def test_analyze_returns_spring_risk_profile(
            self, analyzer, sample_candidate, mock_trading_range
        ):
            """Analyze returns SpringRiskProfile instance."""
            profile = analyzer.analyze(sample_candidate, mock_trading_range)
            assert isinstance(profile, SpringRiskProfile)

        def test_analyze_calculates_correct_stop_loss(
            self, analyzer, sample_candidate, mock_trading_range
        ):
            """Analyze calculates stop loss from Spring low."""
            # Sample bar low = 98.00
            # Stop = 98.00 * 0.98 = 96.04
            profile = analyzer.analyze(sample_candidate, mock_trading_range)
            assert profile.stop_loss == Decimal("96.04")

        def test_analyze_calculates_correct_target(
            self, analyzer, sample_candidate, mock_trading_range
        ):
            """Analyze uses Ice level as target."""
            profile = analyzer.analyze(sample_candidate, mock_trading_range)
            assert profile.initial_target == Decimal("110.00")

        def test_analyze_calculates_correct_rr_ratio(
            self, analyzer, sample_candidate, mock_trading_range
        ):
            """Analyze calculates correct R:R ratio."""
            # Entry: 100.50 (bar close)
            # Stop: 96.04 (98 * 0.98)
            # Target: 110.00 (Ice level)
            # Risk: 100.50 - 96.04 = 4.46
            # Reward: 110.00 - 100.50 = 9.50
            # R:R: 9.50 / 4.46 ≈ 2.13
            profile = analyzer.analyze(sample_candidate, mock_trading_range)
            assert profile.risk_reward_ratio == Decimal("2.13")

        def test_analyze_raises_for_none_candidate(self, analyzer, mock_trading_range):
            """Analyze raises ValueError if candidate is None."""
            with pytest.raises(ValueError, match="SpringCandidate required"):
                analyzer.analyze(None, mock_trading_range)

        def test_analyze_raises_for_none_trading_range(self, analyzer, sample_candidate):
            """Analyze raises ValueError if trading_range is None."""
            with pytest.raises(ValueError, match="TradingRange required"):
                analyzer.analyze(sample_candidate, None)

        def test_analyze_with_favorable_profile(
            self, analyzer, sample_candidate, mock_trading_range
        ):
            """Analyze creates profile that passes is_favorable check."""
            profile = analyzer.analyze(sample_candidate, mock_trading_range)
            # R:R ≈ 2.13 >= 1.5 threshold
            assert profile.is_favorable is True

        def test_analyze_with_unfavorable_profile(self, analyzer, sample_bar):
            """Analyze creates unfavorable profile when R:R is low."""
            # Create candidate with high entry (close near target)
            bar = OHLCVBar(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
                open=Decimal("108.00"),
                high=Decimal("109.00"),
                low=Decimal("98.00"),
                close=Decimal("108.50"),  # High entry near target
                volume=150000,
                spread=Decimal("3.00"),
                timeframe="1d",
            )
            candidate = SpringCandidate(
                bar_index=25,
                bar=bar,
                penetration_pct=Decimal("0.02"),
                recovery_pct=Decimal("0.015"),
                creek_level=Decimal("100.00"),
            )

            trading_range = MagicMock()
            type(trading_range).ice_level = PropertyMock(return_value=Decimal("110.00"))

            # Entry: 108.50, Stop: 96.04, Target: 110.00
            # Risk: 108.50 - 96.04 = 12.46
            # Reward: 110.00 - 108.50 = 1.50
            # R:R: 1.50 / 12.46 ≈ 0.12

            profile = analyzer.analyze(candidate, trading_range)
            assert profile.is_favorable is False


# ================================================================
# Edge Cases and Boundary Tests
# ================================================================


class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_very_small_price_values(self, analyzer):
        """Handle very small price values (penny stocks)."""
        stop_loss, is_valid = analyzer._calculate_stop_loss(
            spring_low=Decimal("0.50"),
            entry_price=Decimal("0.52"),
        )

        assert stop_loss == Decimal("0.49")
        assert is_valid is True

    def test_very_large_price_values(self, analyzer):
        """Handle very large price values."""
        stop_loss, is_valid = analyzer._calculate_stop_loss(
            spring_low=Decimal("50000.00"),
            entry_price=Decimal("51000.00"),
        )

        assert stop_loss == Decimal("49000.00")
        assert is_valid is True

    def test_high_precision_decimals(self, analyzer):
        """Handle high precision decimal values."""
        rr = analyzer._calculate_rr_ratio(
            entry_price=Decimal("100.123456789"),
            stop_loss=Decimal("96.987654321"),
            target=Decimal("110.111111111"),
        )

        # Should round to 2 decimal places
        assert len(str(rr).split(".")[-1]) <= 2
