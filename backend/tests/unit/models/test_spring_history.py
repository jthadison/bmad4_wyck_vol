"""
Unit tests for SpringHistory dataclass.

Tests cover:
- Spring addition with chronological ordering
- Best spring selection using Wyckoff quality hierarchy
- Best signal selection (highest confidence)
- Empty history edge cases
- Volume quality comparison (primary criterion)
- Penetration depth tiebreaker (secondary criterion)
- Recovery speed tiebreaker (tertiary criterion)

Author: Story 5.6 - SpringDetector Module Integration
"""

from datetime import datetime, UTC, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.spring_history import SpringHistory
from src.models.spring import Spring
from src.models.spring_signal import SpringSignal
from src.models.ohlcv import OHLCVBar


def create_test_spring(
    symbol: str = "TEST",
    volume_ratio: Decimal = Decimal("0.5"),
    penetration_pct: Decimal = Decimal("0.02"),
    recovery_bars: int = 2,
    timestamp: datetime = None,
    bar_index: int = 20,
) -> Spring:
    """Create test spring with specified characteristics."""
    if timestamp is None:
        timestamp = datetime.now(UTC)

    bar = OHLCVBar(
        symbol=symbol,
        timestamp=timestamp,
        open=Decimal("99.00"),
        high=Decimal("100.00"),
        low=Decimal("98.00"),
        close=Decimal("99.50"),
        volume=500000,
        spread=Decimal("2.00"),  # high - low
        timeframe="1d",
    )

    return Spring(
        bar=bar,
        bar_index=bar_index,
        penetration_pct=penetration_pct,
        volume_ratio=volume_ratio,
        recovery_bars=recovery_bars,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=timestamp,
        trading_range_id=uuid4(),
    )


def create_test_signal(
    symbol: str = "TEST",
    confidence: int = 75,
    spring_timestamp: datetime = None,
) -> SpringSignal:
    """Create test signal with specified confidence."""
    if spring_timestamp is None:
        spring_timestamp = datetime.now(UTC)

    return SpringSignal(
        symbol=symbol,
        timeframe="1d",
        entry_price=Decimal("100.50"),
        stop_loss=Decimal("96.53"),
        target_price=Decimal("110.00"),
        confidence=confidence,
        r_multiple=Decimal("2.39"),
        spring_bar_timestamp=spring_timestamp,
        test_bar_timestamp=spring_timestamp + timedelta(days=5),
        spring_volume_ratio=Decimal("0.45"),
        test_volume_ratio=Decimal("0.30"),
        volume_decrease_pct=Decimal("0.33"),
        penetration_pct=Decimal("0.02"),
        recovery_bars=2,
        creek_level=Decimal("100.00"),
        jump_level=Decimal("110.00"),
        phase="C",
        trading_range_id=uuid4(),
        range_start_timestamp=spring_timestamp - timedelta(days=30),
        range_bar_count=45,
        stop_distance_pct=Decimal("0.0395"),
        target_distance_pct=Decimal("0.0945"),
        recommended_position_size=Decimal("252"),
        risk_per_trade_pct=Decimal("0.01"),
        urgency="MODERATE",
    )


class TestSpringHistoryCreation:
    """Test SpringHistory initialization and basic properties."""

    def test_create_empty_history(self):
        """Test creating empty SpringHistory."""
        history = SpringHistory(
            symbol="AAPL",
            trading_range_id=uuid4(),
        )

        assert history.symbol == "AAPL"
        assert len(history.springs) == 0
        assert len(history.signals) == 0
        assert history.best_spring is None
        assert history.best_signal is None
        assert history.spring_count == 0
        assert history.volume_trend == "STABLE"
        assert history.risk_level == "MODERATE"
        assert history.detection_timestamp is not None

    def test_create_history_with_defaults(self):
        """Test default field values."""
        history = SpringHistory(
            symbol="TEST",
            trading_range_id=uuid4(),
        )

        assert isinstance(history.springs, list)
        assert isinstance(history.signals, list)
        assert history.volume_trend == "STABLE"
        assert history.risk_level == "MODERATE"
        assert isinstance(history.detection_timestamp, datetime)


class TestAddSpring:
    """Test add_spring() method functionality."""

    def test_add_single_spring_no_signal(self):
        """Test adding single spring without signal."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())
        spring = create_test_spring()

        history.add_spring(spring)

        assert history.spring_count == 1
        assert len(history.springs) == 1
        assert history.springs[0] == spring
        assert history.best_spring == spring
        assert len(history.signals) == 0
        assert history.best_signal is None

    def test_add_single_spring_with_signal(self):
        """Test adding single spring with signal."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())
        spring = create_test_spring()
        signal = create_test_signal(confidence=85)

        history.add_spring(spring, signal)

        assert history.spring_count == 1
        assert history.best_spring == spring
        assert history.best_signal == signal
        assert len(history.signals) == 1
        assert history.signals[0] == signal

    def test_add_multiple_springs_chronological_order(self):
        """Test that springs are maintained in chronological order."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        # Add springs out of chronological order
        timestamp1 = datetime.now(UTC)
        timestamp2 = timestamp1 + timedelta(days=5)
        timestamp3 = timestamp1 + timedelta(days=10)

        spring2 = create_test_spring(timestamp=timestamp2)
        spring1 = create_test_spring(timestamp=timestamp1)
        spring3 = create_test_spring(timestamp=timestamp3)

        # Add in wrong order
        history.add_spring(spring2)
        history.add_spring(spring1)
        history.add_spring(spring3)

        # Should be sorted chronologically
        assert history.spring_count == 3
        assert history.springs[0] == spring1
        assert history.springs[1] == spring2
        assert history.springs[2] == spring3


class TestBestSpringSelection:
    """Test best spring selection using Wyckoff quality hierarchy."""

    def test_best_spring_volume_quality_primary(self):
        """Test volume quality as primary criterion (lower volume wins)."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        # Spring 1: 0.5x volume
        spring1 = create_test_spring(
            volume_ratio=Decimal("0.5"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=2,
        )

        # Spring 2: 0.3x volume (LOWER = BETTER)
        spring2 = create_test_spring(
            volume_ratio=Decimal("0.3"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=2,
        )

        history.add_spring(spring1)
        history.add_spring(spring2)

        # Spring 2 should be best (lower volume)
        assert history.best_spring == spring2
        assert history.best_spring.volume_ratio == Decimal("0.3")

    def test_best_spring_penetration_tiebreaker(self):
        """Test penetration depth as secondary criterion (deeper wins)."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        # Spring 1: 0.4x volume, 1% penetration
        spring1 = create_test_spring(
            volume_ratio=Decimal("0.4"),
            penetration_pct=Decimal("0.01"),
            recovery_bars=2,
        )

        # Spring 2: 0.4x volume, 2% penetration (DEEPER = BETTER)
        spring2 = create_test_spring(
            volume_ratio=Decimal("0.4"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=2,
        )

        history.add_spring(spring1)
        history.add_spring(spring2)

        # Spring 2 should be best (deeper penetration when volume equal)
        assert history.best_spring == spring2
        assert history.best_spring.penetration_pct == Decimal("0.02")

    def test_best_spring_recovery_speed_tiebreaker(self):
        """Test recovery speed as tertiary criterion (faster wins)."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        # Spring 1: 0.4x volume, 2% penetration, 3 bars recovery
        spring1 = create_test_spring(
            volume_ratio=Decimal("0.4"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=3,
        )

        # Spring 2: 0.4x volume, 2% penetration, 1 bar recovery (FASTER = BETTER)
        spring2 = create_test_spring(
            volume_ratio=Decimal("0.4"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=1,
        )

        history.add_spring(spring1)
        history.add_spring(spring2)

        # Spring 2 should be best (faster recovery when volume and penetration equal)
        assert history.best_spring == spring2
        assert history.best_spring.recovery_bars == 1

    def test_volume_comparison_0_3_vs_0_5(self):
        """Test specific volume comparison: 0.3x beats 0.5x."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        spring1 = create_test_spring(volume_ratio=Decimal("0.5"))
        spring2 = create_test_spring(volume_ratio=Decimal("0.3"))

        history.add_spring(spring1)
        history.add_spring(spring2)

        assert history.best_spring == spring2
        assert history.best_spring.volume_ratio == Decimal("0.3")


class TestBestSignalSelection:
    """Test best signal selection (highest confidence)."""

    def test_best_signal_highest_confidence(self):
        """Test that signal with highest confidence is selected."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        spring1 = create_test_spring()
        spring2 = create_test_spring()
        signal1 = create_test_signal(confidence=75)
        signal2 = create_test_signal(confidence=90)

        history.add_spring(spring1, signal1)
        history.add_spring(spring2, signal2)

        assert history.best_signal == signal2
        assert history.best_signal.confidence == 90

    def test_best_signal_with_no_signals(self):
        """Test best_signal remains None when no signals added."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        spring1 = create_test_spring()
        spring2 = create_test_spring()

        history.add_spring(spring1)
        history.add_spring(spring2)

        assert history.best_signal is None

    def test_best_signal_partial_signals(self):
        """Test best signal selection when only some springs have signals."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        spring1 = create_test_spring()
        spring2 = create_test_spring()
        spring3 = create_test_spring()
        signal2 = create_test_signal(confidence=80)
        signal3 = create_test_signal(confidence=85)

        history.add_spring(spring1)  # No signal
        history.add_spring(spring2, signal2)
        history.add_spring(spring3, signal3)

        assert history.best_signal == signal3
        assert history.best_signal.confidence == 85


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_equal_quality_springs(self):
        """Test handling of springs with identical quality."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        # Two springs with identical characteristics
        spring1 = create_test_spring(
            volume_ratio=Decimal("0.4"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=2,
        )
        spring2 = create_test_spring(
            volume_ratio=Decimal("0.4"),
            penetration_pct=Decimal("0.02"),
            recovery_bars=2,
        )

        history.add_spring(spring1)
        history.add_spring(spring2)

        # First spring should remain best (no reason to change)
        assert history.best_spring == spring1

    def test_single_spring_vs_multiple_springs(self):
        """Test behavior with single spring vs multiple springs."""
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        spring1 = create_test_spring()
        history.add_spring(spring1)

        # Single spring
        assert history.spring_count == 1
        assert history.best_spring == spring1

        # Add more springs
        spring2 = create_test_spring(volume_ratio=Decimal("0.3"))
        history.add_spring(spring2)

        assert history.spring_count == 2
        assert history.best_spring == spring2  # Better volume
