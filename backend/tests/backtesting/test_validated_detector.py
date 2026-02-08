"""
Unit tests for ValidatedSignalDetector (Critical Backtest Fix).

Tests cover the validation wrapper that enforces volume and phase rules
on signals produced by an inner detector:
- Passes valid signals through unchanged
- Rejects SPRING signals with high volume (>= 0.7x)
- Rejects signals in wrong Wyckoff phase
- Returns None when inner detector returns None

Author: Critical Backtest Fix tests
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from src.backtesting.engine.validated_detector import ValidatedSignalDetector

_BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC)
from src.models.ohlcv import OHLCVBar
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import ValidationChain

# ---------------------------------------------------------------------------
# Mock inner detector
# ---------------------------------------------------------------------------


class MockDetector:
    """Simple mock that returns a predetermined signal from detect()."""

    def __init__(self, signal: Optional[TradeSignal] = None) -> None:
        self._signal = signal

    def detect(self, bars: list[OHLCVBar], index: int) -> Optional[TradeSignal]:
        return self._signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_bar(
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: int,
    day_offset: int = 0,
    symbol: str = "TEST",
) -> OHLCVBar:
    """Create an OHLCVBar with the given values."""
    return OHLCVBar(
        symbol=symbol,
        timeframe="1d",
        open=Decimal(str(open_price)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=volume,
        spread=Decimal(str(high - low)),
        timestamp=_BASE_DATE + timedelta(days=day_offset),
    )


def make_signal(
    pattern_type: str = "SPRING",
    phase: str = "C",
    entry: Decimal = Decimal("100"),
    stop: Decimal = Decimal("98"),
    target: Decimal = Decimal("106"),
    symbol: str = "TEST",
) -> TradeSignal:
    """Create a valid TradeSignal for testing.

    Constructs a signal with all required fields. For SHORT (UTAD) patterns,
    the caller must provide entry > target and stop > entry.
    """
    risk = abs(entry - stop)
    reward = abs(target - entry)
    r_multiple = (reward / risk).quantize(Decimal("0.01"))

    # Confidence components: pattern 50%, phase 30%, volume 20%
    pattern_conf = 85
    phase_conf = 80
    volume_conf = 82
    overall_conf = int(pattern_conf * 0.5 + phase_conf * 0.3 + volume_conf * 0.2)
    # Clamp to valid range [70, 95]
    overall_conf = max(70, min(95, overall_conf))

    chain = ValidationChain(pattern_id=uuid4())

    return TradeSignal(
        symbol=symbol,
        asset_class="STOCK",
        pattern_type=pattern_type,
        phase=phase,
        timeframe="1d",
        entry_price=entry,
        stop_loss=stop,
        target_levels=TargetLevels(primary_target=target),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        notional_value=entry * Decimal("100"),
        risk_amount=risk * Decimal("100"),
        r_multiple=r_multiple,
        confidence_score=overall_conf,
        confidence_components=ConfidenceComponents(
            pattern_confidence=pattern_conf,
            phase_confidence=phase_conf,
            volume_confidence=volume_conf,
            overall_confidence=overall_conf,
        ),
        validation_chain=chain,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        status="APPROVED",
    )


def make_bars_with_volume(
    count: int,
    base_volume: int,
    current_volume: int,
) -> list[OHLCVBar]:
    """Create a list of bars where all use base_volume except the last uses current_volume."""
    bars: list[OHLCVBar] = []
    for i in range(count - 1):
        bars.append(
            make_bar(
                open_price=105.0,
                high=106.0,
                low=104.0,
                close=105.0,
                volume=base_volume,
                day_offset=i,
            )
        )
    # Last bar (the one at the detection index) uses current_volume
    bars.append(
        make_bar(
            open_price=105.0,
            high=106.0,
            low=104.0,
            close=105.0,
            volume=current_volume,
            day_offset=count - 1,
        )
    )
    return bars


# ===========================================================================
# Tests
# ===========================================================================


class TestValidatedSignalDetectorPassThrough:
    """Tests for signals that should pass through validation."""

    def test_passes_valid_signal_through(self) -> None:
        """A SPRING signal with low volume in phase C passes validation."""
        signal = make_signal(pattern_type="SPRING", phase="C")
        inner = MockDetector(signal=signal)

        # Bars with low volume at current index: 400/1000 = 0.4x < 0.7x
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=400)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is not None
        assert result.pattern_type == "SPRING"
        assert result.symbol == "TEST"

    def test_passes_sos_signal_with_high_volume(self) -> None:
        """An SOS signal with high volume in phase D passes validation."""
        signal = make_signal(pattern_type="SOS", phase="D")
        inner = MockDetector(signal=signal)

        # Bars with high volume at current index: 1800/1000 = 1.8x > 1.5x
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=1800)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is not None
        assert result.pattern_type == "SOS"


class TestValidatedSignalDetectorVolumeRejection:
    """Tests for volume-based rejection."""

    def test_rejects_spring_with_high_volume(self) -> None:
        """SPRING signal with volume >= 0.7x average must be rejected."""
        signal = make_signal(pattern_type="SPRING", phase="C")
        inner = MockDetector(signal=signal)

        # Volume at current bar: 800/1000 = 0.8x >= 0.7x -> should reject
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=800)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is None, "SPRING with volume >= 0.7x should be rejected"

    def test_rejects_sos_with_low_volume(self) -> None:
        """SOS signal with volume < 1.5x average must be rejected."""
        signal = make_signal(pattern_type="SOS", phase="D")
        inner = MockDetector(signal=signal)

        # Volume at current bar: 1200/1000 = 1.2x < 1.5x -> should reject
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=1200)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is None, "SOS with volume < 1.5x should be rejected"


class TestValidatedSignalDetectorPhaseRejection:
    """Tests for phase-based rejection."""

    def test_rejects_spring_in_wrong_phase(self) -> None:
        """SPRING signal in phase B must be rejected (only valid in C)."""
        signal = make_signal(pattern_type="SPRING", phase="B")
        inner = MockDetector(signal=signal)

        # Low volume so volume check passes -- phase should catch it
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=400)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is None, "SPRING in Phase B should be rejected"

    def test_rejects_sos_in_wrong_phase(self) -> None:
        """SOS signal in phase C must be rejected (only valid in D/E)."""
        signal = make_signal(pattern_type="SOS", phase="C")
        inner = MockDetector(signal=signal)

        # High volume so volume check passes -- phase should catch it
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=1800)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is None, "SOS in Phase C should be rejected"

    def test_rejects_utad_in_wrong_phase(self) -> None:
        """UTAD signal in phase E must be rejected (only valid in D)."""
        signal = make_signal(
            pattern_type="UTAD",
            phase="E",
            entry=Decimal("110"),
            stop=Decimal("112"),
            target=Decimal("100"),
        )
        inner = MockDetector(signal=signal)

        # High volume so volume check passes (UTAD needs > 1.2x)
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=1400)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is None, "UTAD in Phase E should be rejected"


class TestValidatedSignalDetectorNonePassthrough:
    """Tests for None passthrough from inner detector."""

    def test_returns_none_when_inner_returns_none(self) -> None:
        """When inner detector returns None, validator returns None."""
        inner = MockDetector(signal=None)
        bars = make_bars_with_volume(count=25, base_volume=1000, current_volume=1000)

        validated = ValidatedSignalDetector(inner=inner, volume_lookback=20)
        result = validated.detect(bars, index=24)

        assert result is None
