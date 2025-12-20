"""
Unit tests for Look-Ahead Bias Detector (Story 12.1 Task 6).

Tests:
- Chronological order validation
- Realistic entry price validation
- Edge cases (empty trades, no matching bars)
- Intentional bias detection

Author: Story 12.1 Task 6
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.bias_detector import LookAheadBiasDetector
from src.models.backtest import BacktestTrade
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def detector():
    """Fixture for LookAheadBiasDetector."""
    return LookAheadBiasDetector()


@pytest.fixture
def sample_bars():
    """Fixture for sample OHLCV bars."""
    return [
        OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=50000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        ),
        OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("151.00"),
            high=Decimal("153.00"),
            low=Decimal("150.00"),
            close=Decimal("152.50"),
            volume=50000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, 11, 9, 30, tzinfo=UTC),
        ),
        OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("152.50"),
            high=Decimal("155.00"),
            low=Decimal("152.00"),
            close=Decimal("154.00"),
            volume=50000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, 12, 9, 30, tzinfo=UTC),
        ),
    ]


class TestLookAheadBiasDetectorInitialization:
    """Test LookAheadBiasDetector initialization."""

    def test_initialization_with_defaults(self):
        """Test detector initialization with default tolerance."""
        detector = LookAheadBiasDetector()
        assert detector.tolerance == Decimal("0.01")  # 1% default

    def test_initialization_with_custom_tolerance(self):
        """Test detector initialization with custom tolerance."""
        detector = LookAheadBiasDetector(tolerance=Decimal("0.05"))
        assert detector.tolerance == Decimal("0.05")


class TestChronologicalOrderValidation:
    """Test chronological order validation."""

    def test_valid_chronological_order(self, detector):
        """Test trades with valid chronological order (entry < exit)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            ),
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("155.00"),
                exit_price=Decimal("160.00"),
                entry_timestamp=datetime(2024, 1, 16, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 20, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            ),
        ]

        result = detector._verify_chronological_order(trades)
        assert result is True

    def test_invalid_chronological_order(self, detector):
        """Test trades with invalid chronological order (entry >= exit)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                # Exit before entry - BIAS!
                entry_timestamp=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector._verify_chronological_order(trades)
        assert result is False

    def test_same_entry_exit_timestamp(self, detector):
        """Test trade with same entry and exit timestamp (invalid)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector._verify_chronological_order(trades)
        assert result is False


class TestRealisticEntryPriceValidation:
    """Test realistic entry price validation."""

    def test_valid_entry_at_bar_open(self, detector, sample_bars):
        """Test trade with entry at bar open (realistic)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),  # Matches bar.open
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector._verify_realistic_entry_prices(trades, sample_bars)
        assert result is True

    def test_valid_entry_with_slippage(self, detector, sample_bars):
        """Test trade with realistic slippage from bar open."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.03"),  # Open + small slippage
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector._verify_realistic_entry_prices(trades, sample_bars)
        assert result is True

    def test_invalid_entry_at_bar_low(self, detector, sample_bars):
        """Test BUY trade with entry at bar low (look-ahead bias)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("149.00"),  # Perfect entry at bar.low - BIAS!
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector._verify_realistic_entry_prices(trades, sample_bars)
        assert result is False

    def test_invalid_entry_at_bar_high(self, detector, sample_bars):
        """Test SELL trade with entry at bar high (look-ahead bias)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="SHORT",
                quantity=100,
                entry_price=Decimal("152.00"),  # Perfect entry at bar.high - BIAS!
                exit_price=Decimal("145.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("700.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector._verify_realistic_entry_prices(trades, sample_bars)
        assert result is False

    def test_no_matching_bar(self, detector, sample_bars):
        """Test trade with no matching bar (assumes valid)."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                # Timestamp doesn't match any bar
                entry_timestamp=datetime(2024, 2, 1, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 2, 5, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        # Should return True (assume valid if can't validate)
        result = detector._verify_realistic_entry_prices(trades, sample_bars)
        assert result is True


class TestIsAtExtremeDetection:
    """Test extreme price detection."""

    def test_price_at_low_extreme(self, detector):
        """Test price exactly at bar low."""
        is_extreme = detector._is_price_at_extreme(
            price=Decimal("149.00"),
            bar_low=Decimal("149.00"),
            bar_high=Decimal("152.00"),
        )
        assert is_extreme is True

    def test_price_at_high_extreme(self, detector):
        """Test price exactly at bar high."""
        is_extreme = detector._is_price_at_extreme(
            price=Decimal("152.00"),
            bar_low=Decimal("149.00"),
            bar_high=Decimal("152.00"),
        )
        assert is_extreme is True

    def test_price_in_middle(self, detector):
        """Test price in middle of bar range (not extreme)."""
        is_extreme = detector._is_price_at_extreme(
            price=Decimal("150.50"),
            bar_low=Decimal("149.00"),
            bar_high=Decimal("152.00"),
        )
        assert is_extreme is False

    def test_price_near_low_within_tolerance(self, detector):
        """Test price near low but within tolerance SHOULD be flagged.

        With tolerance 0.01 (1%), price at 149.02 is 0.67% from low.
        Since 0.67% < 1%, it SHOULD be flagged as extreme (within tolerance).
        """
        # Bar range: 149-152 (3 points)
        # 1% tolerance = 0.01 = 1% of range = 0.03 points
        # Price at 149.02 is 0.02 from low = 0.67% of range
        # 0.67% < 1%, so should be flagged (within tolerance)
        is_extreme = detector._is_price_at_extreme(
            price=Decimal("149.02"),
            bar_low=Decimal("149.00"),
            bar_high=Decimal("152.00"),
        )
        assert is_extreme is True

    def test_price_near_low_outside_tolerance(self, detector):
        """Test price near low but outside tolerance."""
        # Bar range: 149-152 (3 points)
        # 1% tolerance = 0.03 points
        # Price at 149.10 is outside tolerance of low (3.3% of range)
        is_extreme = detector._is_price_at_extreme(
            price=Decimal("149.10"),
            bar_low=Decimal("149.00"),
            bar_high=Decimal("152.00"),
        )
        assert is_extreme is False

    def test_zero_range_bar(self, detector):
        """Test bar with zero range (high == low)."""
        is_extreme = detector._is_price_at_extreme(
            price=Decimal("150.00"),
            bar_low=Decimal("150.00"),
            bar_high=Decimal("150.00"),
        )
        # Should return False (can't determine extremes with zero range)
        assert is_extreme is False


class TestFullBiasDetection:
    """Test full bias detection workflow."""

    def test_no_trades_no_bias(self, detector, sample_bars):
        """Test empty trades list (no bias possible)."""
        result = detector.detect_look_ahead_bias([], sample_bars)
        assert result is True

    def test_valid_backtest_no_bias(self, detector, sample_bars):
        """Test valid backtest with realistic trades."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.03"),  # Open + slippage
                exit_price=Decimal("154.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 12, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("397.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector.detect_look_ahead_bias(trades, sample_bars)
        assert result is True

    def test_chronological_bias_detected(self, detector, sample_bars):
        """Test backtest with chronological order bias."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.03"),
                exit_price=Decimal("154.00"),
                # Exit before entry - BIAS!
                entry_timestamp=datetime(2024, 1, 12, 16, 0, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                realized_pnl=Decimal("397.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector.detect_look_ahead_bias(trades, sample_bars)
        assert result is False

    def test_perfect_entry_bias_detected(self, detector, sample_bars):
        """Test backtest with perfect entry at bar low bias."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("149.00"),  # Perfect entry at bar.low - BIAS!
                exit_price=Decimal("154.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 12, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        result = detector.detect_look_ahead_bias(trades, sample_bars)
        assert result is False

    def test_custom_tolerance(self, sample_bars):
        """Test detector with custom tolerance."""
        # Use 5% tolerance (more lenient)
        detector = LookAheadBiasDetector(tolerance=Decimal("0.05"))

        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                # Entry close to low but within 5% tolerance
                entry_price=Decimal("149.10"),
                exit_price=Decimal("154.00"),
                entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 12, 16, 0, tzinfo=UTC),
                realized_pnl=Decimal("490.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        # With 5% tolerance, this should still pass
        result = detector.detect_look_ahead_bias(trades, sample_bars)
        # Bar range: 149-152 = 3 points
        # Distance from low: 0.10 / 3 = 3.33%, which is < 5%
        assert result is False  # Still flagged as extreme
