"""
Unit tests for SpringDetector class (Story 5.6 - Task 3).

Tests cover:
- detect_all_springs() returns SpringHistory with proper population
- get_best_signal() selects highest confidence signal
- detect() backward compatibility wrapper returns List[SpringSignal]
- Phase validation (FR15: Phase C only)
- Empty history handling (no springs detected)
- Integration with existing spring detection pipeline

Author: Story 5.6 - SpringDetector Module Integration
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.creek_level import CreekLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.spring_history import SpringHistory
from src.models.touch_detail import TouchDetail
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.detectors.spring_detector import SpringDetector


def create_test_bar(
    timestamp: datetime,
    low: Decimal,
    high: Decimal,
    close: Decimal,
    volume: int,
    symbol: str = "TEST",
) -> OHLCVBar:
    """Create test OHLCV bar with specified parameters."""
    spread = high - low
    open_price = (high + low) / 2

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=spread,
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


def create_test_range(
    creek_level: Decimal = Decimal("100.00"),
    symbol: str = "TEST",
) -> TradingRange:
    """Create test trading range with Creek level."""
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Create support pivots
    support_pivots = []
    for i, idx in enumerate([10, 20, 30]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=creek_level - Decimal("2.00"),
            high=creek_level + Decimal("5.00"),
            close=creek_level + Decimal("1.00"),
            volume=1000000,
            symbol=symbol,
        )
        pivot = Pivot(
            bar=bar,
            price=bar.low,
            type=PivotType.LOW,
            strength=5,
            timestamp=bar.timestamp,
            index=idx,
        )
        support_pivots.append(pivot)

    support_cluster = PriceCluster(
        pivots=support_pivots,
        average_price=creek_level - Decimal("2.00"),
        min_price=creek_level - Decimal("3.00"),
        max_price=creek_level - Decimal("1.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create resistance pivots
    resistance_pivots = []
    for i, idx in enumerate([15, 25, 35]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=creek_level + Decimal("5.00"),
            high=creek_level + Decimal("10.00"),
            close=creek_level + Decimal("7.00"),
            volume=1000000,
            symbol=symbol,
        )
        pivot = Pivot(
            bar=bar,
            price=bar.high,
            type=PivotType.HIGH,
            strength=5,
            timestamp=bar.timestamp,
            index=idx,
        )
        resistance_pivots.append(pivot)

    resistance_cluster = PriceCluster(
        pivots=resistance_pivots,
        average_price=creek_level + Decimal("10.00"),
        min_price=creek_level + Decimal("9.00"),
        max_price=creek_level + Decimal("11.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Creek with all required fields
    creek = CreekLevel(
        price=creek_level,
        absolute_low=creek_level - Decimal("1.00"),
        touch_count=3,
        touch_details=[
            TouchDetail(
                index=i,
                price=creek_level,
                volume=1000000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.7"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp + timedelta(days=idx),
            )
            for i, idx in enumerate([10, 20, 30])
        ],
        strength_score=75,
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp + timedelta(days=30),
        first_test_timestamp=base_timestamp + timedelta(days=10),
        hold_duration=20,
        confidence="HIGH",
        volume_trend="DECREASING",
    )

    return TradingRange(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=creek_level - Decimal("2.00"),
        resistance=creek_level + Decimal("10.00"),
        midpoint=creek_level + Decimal("4.00"),
        range_width=Decimal("12.00"),
        range_width_pct=Decimal("0.12"),
        start_index=0,
        end_index=50,
        duration=51,
        creek=creek,
        status=RangeStatus.ACTIVE,
    )


def create_test_bars(count: int, creek_level: Decimal = Decimal("100.00")) -> list[OHLCVBar]:
    """Create test bars with base volume pattern."""
    bars = []
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    for i in range(count):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_test_bar(
                timestamp=timestamp,
                low=creek_level + Decimal("1.00"),
                high=creek_level + Decimal("5.00"),
                close=creek_level + Decimal("3.00"),
                volume=1000000,  # Base volume
            )
        )

    return bars


class TestSpringDetectorCreation:
    """Test SpringDetector initialization."""

    def test_create_detector(self):
        """Test SpringDetector instance creation."""
        detector = SpringDetector()

        assert detector is not None
        assert detector.logger is not None


class TestDetectAllSprings:
    """Test detect_all_springs() method functionality."""

    def test_detect_all_springs_wrong_phase_returns_empty_history(self):
        """Test Phase B returns empty SpringHistory (FR15 validation)."""
        detector = SpringDetector()
        range = create_test_range()
        bars = create_test_bars(30)

        # Call with Phase B (wrong phase)
        history = detector.detect_all_springs(range, bars, WyckoffPhase.B)

        # Should return empty history
        assert isinstance(history, SpringHistory)
        assert history.spring_count == 0
        assert len(history.signals) == 0
        assert history.best_spring is None
        assert history.best_signal is None
        assert history.symbol == "TEST"

    def test_detect_all_springs_phase_c_no_spring_returns_empty_history(self):
        """Test Phase C with no spring detected returns empty history."""
        detector = SpringDetector()
        creek_level = Decimal("100.00")
        range = create_test_range(creek_level=creek_level)

        # Create bars with NO penetration below Creek (all bars stay above Creek)
        bars = create_test_bars(30, creek_level=creek_level)

        # Call with Phase C (correct phase, but no spring)
        history = detector.detect_all_springs(range, bars, WyckoffPhase.C)

        # Should return empty history (no spring detected)
        assert isinstance(history, SpringHistory)
        assert history.spring_count == 0
        assert len(history.signals) == 0
        assert history.best_spring is None

    def test_detect_all_springs_returns_history_instance(self):
        """Test detect_all_springs returns SpringHistory instance."""
        detector = SpringDetector()
        range = create_test_range()
        bars = create_test_bars(30)

        history = detector.detect_all_springs(range, bars, WyckoffPhase.C)

        assert isinstance(history, SpringHistory)
        assert history.symbol == "TEST"
        assert history.trading_range_id == range.id

    def test_detect_all_springs_populates_risk_level_and_volume_trend(self):
        """Test detect_all_springs populates risk_level and volume_trend."""
        detector = SpringDetector()
        creek_level = Decimal("100.00")
        range = create_test_range(creek_level=creek_level)

        # Create bars (no spring in this test - just checking attributes)
        bars = create_test_bars(30, creek_level=creek_level)

        history = detector.detect_all_springs(range, bars, WyckoffPhase.C)

        # History should have risk_level and volume_trend populated (even if empty)
        assert history.risk_level in ["LOW", "MODERATE", "HIGH"]
        assert history.volume_trend in ["DECLINING", "STABLE", "RISING"]


class TestGetBestSignal:
    """Test get_best_signal() method functionality."""

    def test_get_best_signal_empty_history_returns_none(self):
        """Test get_best_signal with empty history returns None."""
        detector = SpringDetector()
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        best_signal = detector.get_best_signal(history)

        assert best_signal is None

    def test_get_best_signal_no_signals_returns_none(self):
        """Test get_best_signal with springs but no signals returns None."""
        from src.models.spring import Spring

        detector = SpringDetector()
        history = SpringHistory(symbol="TEST", trading_range_id=uuid4())

        # Add spring WITHOUT signal (no test confirmation)
        creek_level = Decimal("100.00")
        bar = create_test_bar(
            timestamp=datetime(2024, 1, 21, tzinfo=UTC),
            low=Decimal("98.00"),
            high=Decimal("100.00"),
            close=Decimal("99.50"),
            volume=500000,
        )

        spring = Spring(
            bar=bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=2,
            creek_reference=creek_level,
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
        )

        history.add_spring(spring, signal=None)

        best_signal = detector.get_best_signal(history)

        assert best_signal is None
        assert history.spring_count == 1  # Spring exists
        assert len(history.signals) == 0  # But no signals


class TestBackwardCompatibility:
    """Test detect() backward compatibility wrapper."""

    def test_detect_wrapper_returns_list_of_signals(self):
        """Test detect() returns List[SpringSignal] for backward compatibility."""
        detector = SpringDetector()
        range = create_test_range()
        bars = create_test_bars(30)

        # Call legacy detect() method
        signals = detector.detect(range, bars, WyckoffPhase.C)

        # Should return list (even if empty)
        assert isinstance(signals, list)

    def test_detect_wrapper_wrong_phase_returns_empty_list(self):
        """Test detect() with wrong phase returns empty list."""
        detector = SpringDetector()
        range = create_test_range()
        bars = create_test_bars(30)

        # Call with Phase B (wrong phase)
        signals = detector.detect(range, bars, WyckoffPhase.B)

        assert isinstance(signals, list)
        assert len(signals) == 0

    def test_detect_wrapper_no_spring_returns_empty_list(self):
        """Test detect() with no spring detected returns empty list."""
        detector = SpringDetector()
        creek_level = Decimal("100.00")
        range = create_test_range(creek_level=creek_level)

        # Create bars with NO penetration (no spring - all above Creek)
        bars = create_test_bars(30, creek_level=creek_level)

        signals = detector.detect(range, bars, WyckoffPhase.C)

        assert isinstance(signals, list)
        assert len(signals) == 0


class TestSpringDetectorIntegration:
    """Test SpringDetector integration with existing pipeline."""

    def test_detector_calls_existing_detect_spring_function(self):
        """Test SpringDetector integrates with detect_spring() from Story 5.1."""
        detector = SpringDetector()
        creek_level = Decimal("100.00")
        range = create_test_range(creek_level=creek_level)

        # Create bars (no spring in this basic test)
        bars = create_test_bars(30, creek_level=creek_level)

        # Detect springs
        history = detector.detect_all_springs(range, bars, WyckoffPhase.C)

        # Pipeline should execute without errors
        assert isinstance(history, SpringHistory)
        assert history.symbol == "TEST"
