"""
Unit tests for sos_detector module.

Tests SOS breakout pattern detection with synthetic data covering all acceptance criteria:
- AC 7: Valid SOS detection (2% breakout, 2.0x volume)
- AC 8: Low-volume rejection (1.4x volume)
- AC 9: Breakout percentage validation (<1% rejected)
- AC 10: Phase D validation (wrong phase rejected)
- FR12: Volume expansion validation (non-negotiable)
- FR15: Phase validation (Phase D only for Story 6.1A)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase, PhaseClassification
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange, RangeStatus
from src.models.price_cluster import PriceCluster
from src.models.ice_level import IceLevel
from src.models.pivot import Pivot, PivotType
from src.models.touch_detail import TouchDetail
from src.pattern_engine.detectors.sos_detector import detect_sos_breakout


def create_test_bar(
    timestamp: datetime,
    low: Decimal,
    high: Decimal,
    close: Decimal,
    volume: int,
    symbol: str = "AAPL",
) -> OHLCVBar:
    """
    Create test OHLCV bar with specified parameters.

    Args:
        timestamp: Bar timestamp
        low: Low price
        high: High price
        close: Close price
        volume: Volume
        symbol: Stock symbol (default: AAPL)

    Returns:
        OHLCVBar instance for testing
    """
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


def create_trading_range(
    ice_level: Decimal,
    symbol: str = "AAPL",
) -> TradingRange:
    """
    Create test trading range with Ice level.

    Args:
        ice_level: Ice price level (resistance)
        symbol: Stock symbol (default: AAPL)

    Returns:
        TradingRange instance for testing
    """
    # Create pivot bars for support cluster
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    support_pivots = []
    for i, idx in enumerate([10, 20, 30]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=ice_level - Decimal("12.00"),
            high=ice_level - Decimal("5.00"),
            close=ice_level - Decimal("7.00"),
            volume=100000,
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
        average_price=ice_level - Decimal("12.00"),
        min_price=ice_level - Decimal("13.00"),
        max_price=ice_level - Decimal("11.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create pivot bars for resistance cluster
    resistance_pivots = []
    for i, idx in enumerate([15, 25, 35]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=ice_level - Decimal("2.00"),
            high=ice_level + Decimal("1.00"),
            close=ice_level - Decimal("1.00"),
            volume=100000,
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
        average_price=ice_level + Decimal("1.00"),
        min_price=ice_level,
        max_price=ice_level + Decimal("2.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Ice with all required fields
    ice = IceLevel(
        price=ice_level,
        absolute_high=ice_level + Decimal("1.00"),
        touch_count=3,
        touch_details=[
            TouchDetail(
                index=i,
                price=ice_level,
                volume=100000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.3"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp + timedelta(days=idx),
            )
            for i, idx in enumerate([15, 25, 35])
        ],
        strength_score=75,
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp + timedelta(days=35),
        first_test_timestamp=base_timestamp + timedelta(days=15),
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
        support=ice_level - Decimal("12.00"),
        resistance=ice_level + Decimal("1.00"),
        midpoint=ice_level - Decimal("5.50"),
        range_width=Decimal("13.00"),
        range_width_pct=Decimal("0.13"),
        start_index=0,
        end_index=50,
        duration=51,
        ice=ice,
        status=RangeStatus.ACTIVE,
    )


def create_bars_with_sos_breakout(
    ice_level: Decimal,
    breakout_pct: Decimal,
    volume: int,
    symbol: str = "AAPL",
) -> list[OHLCVBar]:
    """
    Create synthetic bars with SOS breakout pattern.

    Args:
        ice_level: Ice price level (resistance)
        breakout_pct: Breakout percentage above Ice (e.g., 0.02 for 2%)
        volume: Volume for breakout bar
        symbol: Stock symbol (default: AAPL)

    Returns:
        List of 25 OHLCV bars (24 normal + 1 breakout)
    """
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    bars = []

    # Create 24 normal bars trading within range ($95-$100)
    for i in range(24):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=i),
            low=ice_level - Decimal("5.00"),
            high=ice_level - Decimal("0.50"),
            close=ice_level - Decimal("2.00"),
            volume=100000,
            symbol=symbol,
        )
        bars.append(bar)

    # Create breakout bar (bar 25)
    breakout_price = ice_level * (Decimal("1") + breakout_pct)
    breakout_bar = create_test_bar(
        timestamp=base_timestamp + timedelta(days=24),
        low=ice_level - Decimal("1.00"),
        high=breakout_price + Decimal("1.00"),
        close=breakout_price,
        volume=volume,
        symbol=symbol,
    )
    bars.append(breakout_bar)

    return bars


def create_phase_classification(
    phase: WyckoffPhase,
    confidence: int,
) -> PhaseClassification:
    """
    Create test phase classification.

    Args:
        phase: Wyckoff phase
        confidence: Phase confidence (0-100)

    Returns:
        PhaseClassification instance for testing
    """
    from src.models.phase_classification import PhaseEvents

    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    return PhaseClassification(
        phase=phase,
        confidence=confidence,
        duration=10,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=0,
        phase_start_timestamp=base_timestamp,
    )


# ============================================================
# TEST: Valid SOS Detection (AC 7)
# ============================================================


def test_detect_sos_breakout_valid():
    """
    AC 7: Test valid SOS detection (2% breakout, 2.0x volume).

    Scenario:
    - Ice at $100.00
    - Breakout bar closes at $102.00 (2% above Ice)
    - Volume: 200,000 (2.0x average per AC 7)
    - Phase: D (markup)

    Expected:
    - SOS detected
    - breakout_pct = 2%
    - volume_ratio = 2.0x
    - ice_reference = $100.00
    - breakout_price = $102.00
    """
    # Arrange
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),  # 2% breakout
        volume=200000,  # 2.0x volume
    )

    volume_analysis = {
        bars[24].timestamp: {
            "volume_ratio": Decimal("2.0"),  # AC 7: 2.0x volume
        }
    }

    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is not None, "SOS should be detected"
    assert sos.breakout_pct >= Decimal("0.01"), "Breakout >= 1% above Ice"
    assert abs(sos.breakout_pct - Decimal("0.02")) < Decimal("0.0001"), "Breakout should be ~2%"
    assert sos.volume_ratio == Decimal("2.0"), "2.0x volume ratio"
    assert sos.ice_reference == Decimal("100.00"), "Ice reference should be $100.00"
    assert sos.breakout_price == ice_level * Decimal("1.02"), "Breakout price should be $102.00"
    assert sos.trading_range_id == trading_range.id
    assert isinstance(sos.detection_timestamp, datetime)


# ============================================================
# TEST: Low-Volume Rejection (AC 4, 8, FR12)
# ============================================================


def test_detect_sos_low_volume_rejected():
    """
    AC 4, 8: Test low-volume breakout rejection (1.4x volume, below 1.5x threshold).

    FR12: Volume expansion < 1.5x = immediate rejection (false breakout).

    Scenario:
    - Ice at $100.00
    - Breakout bar closes at $102.00 (2% above Ice)
    - Volume: 140,000 (1.4x average - BELOW THRESHOLD)
    - Phase: D (markup)

    Expected:
    - SOS REJECTED (low volume = false breakout per FR12)
    - Return None
    """
    # Arrange
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),  # 2% breakout (good)
        volume=140000,  # LOW VOLUME (1.4x)
    )

    volume_analysis = {
        bars[24].timestamp: {
            "volume_ratio": Decimal("1.4"),  # LOW VOLUME (< 1.5x)
        }
    }

    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is None, "Low-volume breakout should be REJECTED (FR12)"


def test_volume_boundary_149_rejects_150_passes():
    """
    Test volume boundary conditions: 1.49x rejects, 1.50x passes.

    FR12: Volume threshold is EXACTLY 1.5x (binary rejection).
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)

    # Test 1.49x - should REJECT
    bars_reject = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),
        volume=149000,
    )
    volume_analysis_reject = {
        bars_reject[24].timestamp: {"volume_ratio": Decimal("1.49")}
    }
    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    sos_reject = detect_sos_breakout(
        trading_range, bars_reject, volume_analysis_reject, phase
    )
    assert sos_reject is None, "1.49x volume should reject (< 1.5x threshold)"

    # Test 1.50x - should PASS
    bars_pass = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),
        volume=150000,
    )
    volume_analysis_pass = {
        bars_pass[24].timestamp: {"volume_ratio": Decimal("1.50")}
    }

    sos_pass = detect_sos_breakout(
        trading_range, bars_pass, volume_analysis_pass, phase
    )
    assert sos_pass is not None, "1.50x volume should pass (>= 1.5x threshold, FR12)"
    assert sos_pass.volume_ratio == Decimal("1.50")


# ============================================================
# TEST: Breakout Percentage Validation (AC 3, 9)
# ============================================================


def test_breakout_1_percent_accepted():
    """
    AC 3: Test exact 1% breakout (minimum acceptable).

    Scenario:
    - Ice at $100.00
    - Breakout bar closes at $101.00 (exactly 1% above Ice)
    - Volume: 200,000 (2.0x - high volume)
    - Phase: D

    Expected:
    - SOS detected (1% is minimum acceptable per AC 3)
    - breakout_pct = 1% (0.01)
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.01"),  # Exactly 1% breakout
        volume=200000,  # 2.0x volume
    )

    volume_analysis = {
        bars[24].timestamp: {"volume_ratio": Decimal("2.0")}
    }

    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is not None, "1% breakout should be accepted (AC 3 minimum)"
    assert abs(sos.breakout_pct - Decimal("0.01")) < Decimal("0.0001"), "Breakout should be ~1%"


def test_breakout_below_1_percent_rejected():
    """
    AC 9: Test <1% breakout (rejected).

    Scenario:
    - Ice at $100.00
    - Breakout bar closes at $100.50 (0.5% above Ice - TOO SMALL)
    - Volume: 200,000 (2.0x - high volume)
    - Phase: D

    Expected:
    - SOS REJECTED (< 1% breakout per AC 3)
    - Return None
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.005"),  # 0.5% breakout (TOO SMALL)
        volume=200000,  # 2.0x volume (good)
    )

    volume_analysis = {
        bars[24].timestamp: {"volume_ratio": Decimal("2.0")}
    }

    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is None, "< 1% breakout should be rejected (AC 3)"


# ============================================================
# TEST: Phase D Validation (AC 6, 10, FR15)
# ============================================================


def test_sos_in_phase_d_accepted():
    """
    AC 6: Test SOS in Phase D (valid - markup phase).

    FR15: SOS valid in Phase D (Story 6.1A scope).

    Scenario:
    - Phase D (markup)
    - Valid breakout (2% above Ice)
    - High volume (2.0x)

    Expected:
    - SOS detected (Phase D is ideal for SOS per FR15)
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),
        volume=200000,
    )

    volume_analysis = {
        bars[24].timestamp: {"volume_ratio": Decimal("2.0")}
    }

    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is not None, "SOS valid in Phase D (FR15)"


@pytest.mark.parametrize(
    "phase_value",
    [
        WyckoffPhase.A,
        WyckoffPhase.B,
        WyckoffPhase.C,  # Phase C deferred to Story 6.1B
        WyckoffPhase.E,
    ],
)
def test_sos_wrong_phase_rejected(phase_value):
    """
    AC 10: Test SOS in wrong phases (rejected).

    FR15: Story 6.1A only supports Phase D.
    Phase C support deferred to Story 6.1B.

    Scenario:
    - Phase A, B, C, or E (not Phase D)
    - Valid breakout (2% above Ice)
    - High volume (2.0x)

    Expected:
    - SOS REJECTED (wrong phase per FR15)
    - Return None
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),
        volume=200000,
    )

    volume_analysis = {
        bars[24].timestamp: {"volume_ratio": Decimal("2.0")}
    }

    phase = create_phase_classification(phase=phase_value, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert (
        sos is None
    ), f"SOS should be rejected in Phase {phase_value.value} (FR15 - Story 6.1A only supports Phase D)"


# ============================================================
# TEST: Edge Cases (Task 12)
# ============================================================


def test_insufficient_bars_rejected():
    """
    Task 12: Test insufficient bars (<25 bars).

    Scenario:
    - Only 20 bars available (need 25 for volume calculation)

    Expected:
    - Return None (insufficient data)
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)

    # Create only 20 bars (insufficient)
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    bars = []
    for i in range(20):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=i),
            low=Decimal("95.00"),
            high=Decimal("99.00"),
            close=Decimal("97.00"),
            volume=100000,
        )
        bars.append(bar)

    volume_analysis = {}
    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is None, "Insufficient bars should return None"


def test_missing_trading_range_raises_error():
    """
    Task 12: Test missing trading range (None).

    Expected:
    - Raise ValueError
    """
    bars = create_bars_with_sos_breakout(
        ice_level=Decimal("100.00"),
        breakout_pct=Decimal("0.02"),
        volume=200000,
    )
    volume_analysis = {bars[24].timestamp: {"volume_ratio": Decimal("2.0")}}
    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act & Assert
    with pytest.raises(ValueError, match="Trading range required"):
        detect_sos_breakout(None, bars, volume_analysis, phase)


def test_invalid_ice_level_raises_error():
    """
    Task 12: Test invalid Ice level (None or <= 0).

    Expected:
    - Raise ValueError
    """
    trading_range = create_trading_range(ice_level=Decimal("100.00"))
    trading_range.ice = None  # Simulate missing Ice

    bars = create_bars_with_sos_breakout(
        ice_level=Decimal("100.00"),
        breakout_pct=Decimal("0.02"),
        volume=200000,
    )
    volume_analysis = {bars[24].timestamp: {"volume_ratio": Decimal("2.0")}}
    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act & Assert
    with pytest.raises(ValueError, match="Valid Ice level required"):
        detect_sos_breakout(trading_range, bars, volume_analysis, phase)


def test_missing_volume_analysis_skips_candidate():
    """
    Task 12: Test missing volume analysis for breakout bar.

    Scenario:
    - Valid breakout bar, but no volume_ratio in volume_analysis

    Expected:
    - Skip candidate, return None
    """
    ice_level = Decimal("100.00")
    trading_range = create_trading_range(ice_level=ice_level)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_level,
        breakout_pct=Decimal("0.02"),
        volume=200000,
    )

    # Volume analysis missing breakout bar timestamp
    volume_analysis = {}  # Empty (missing data)

    phase = create_phase_classification(phase=WyckoffPhase.D, confidence=85)

    # Act
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase)

    # Assert
    assert sos is None, "Missing volume analysis should skip candidate"
