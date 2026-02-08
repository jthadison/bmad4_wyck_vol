"""
Unit tests for WyckoffSignalDetector (Critical Backtest Fix).

Tests cover Wyckoff pattern detection from OHLCV bars including:
- Insufficient data handling
- Spring detection with low-volume validation
- Spring rejection on high volume (NON-NEGOTIABLE)
- SOS detection with high-volume validation
- SOS rejection on low volume (NON-NEGOTIABLE)
- UTAD detection with failure-back-below pattern
- Cooldown enforcement between signals
- R-multiple filter (minimum 2.0R)

Author: Critical Backtest Fix tests
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.backtesting.engine.wyckoff_detector import WyckoffSignalDetector
from src.models.ohlcv import OHLCVBar

_BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helper: create an OHLCVBar
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
        spread=Decimal(str(round(high - low, 4))),
        timestamp=_BASE_DATE + timedelta(days=day_offset),
    )


def make_range_bars(
    count: int = 35,
    support: float = 100.0,
    resistance: float = 110.0,
    base_volume: int = 1000,
    symbol: str = "TEST",
) -> list[OHLCVBar]:
    """Create bars oscillating within a trading range.

    Bars alternate around the midpoint of the range to establish clear
    support and resistance levels for the detector.
    """
    bars: list[OHLCVBar] = []
    mid = (support + resistance) / 2.0
    half_range = (resistance - support) / 2.0

    for i in range(count):
        # Alternate between upper and lower portions of range
        if i % 2 == 0:
            o = mid - half_range * 0.3
            h = mid + half_range * 0.2
            lo = support + half_range * 0.05
            c = mid - half_range * 0.1
        else:
            o = mid + half_range * 0.1
            h = resistance - half_range * 0.05
            lo = mid - half_range * 0.2
            c = mid + half_range * 0.3

        bars.append(
            make_bar(
                open_price=round(o, 2),
                high=round(h, 2),
                low=round(lo, 2),
                close=round(c, 2),
                volume=base_volume,
                day_offset=i,
                symbol=symbol,
            )
        )
    return bars


# ===========================================================================
# Tests
# ===========================================================================


class TestWyckoffSignalDetectorInsufficientBars:
    """Tests for returning None when there is insufficient data."""

    def test_returns_none_when_insufficient_bars(self) -> None:
        """Detector returns None when index < min_range_bars."""
        detector = WyckoffSignalDetector(min_range_bars=30)
        bars = make_range_bars(count=35)
        # Index 10 is well below min_range_bars=30
        result = detector.detect(bars, index=10)
        assert result is None

    def test_returns_none_at_exact_boundary(self) -> None:
        """Detector returns None when index == min_range_bars - 1."""
        detector = WyckoffSignalDetector(min_range_bars=30)
        bars = make_range_bars(count=35)
        result = detector.detect(bars, index=29)
        assert result is None


class TestSpringDetection:
    """Tests for Spring pattern detection."""

    def test_detects_spring_pattern(self) -> None:
        """Spring: dip below support on LOW volume that recovers -> SPRING LONG."""
        base_volume = 1000
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)

        # Add a spring bar: dips below support (100) on low volume, closes back near support
        # Volume must be < 0.7x average = < 700
        spring_bar = make_bar(
            open_price=100.5,
            high=101.0,
            low=98.5,  # Penetrates below 100 support
            close=100.2,  # Recovers back above support
            volume=400,  # Low volume: 400/1000 = 0.4x < 0.7x
            day_offset=35,
        )
        bars.append(spring_bar)

        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)
        signal = detector.detect(bars, index=35)

        assert signal is not None
        assert signal.pattern_type == "SPRING"
        assert signal.direction == "LONG"
        assert signal.phase == "C"

    def test_spring_rejected_on_high_volume(self) -> None:
        """Spring with volume >= 0.7x average must be rejected (NON-NEGOTIABLE)."""
        base_volume = 1000
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)

        # Same spring shape but with HIGH volume (>= 0.7x)
        spring_bar = make_bar(
            open_price=100.5,
            high=101.0,
            low=98.5,
            close=100.2,
            volume=800,  # 800/1000 = 0.8x >= 0.7x -> REJECT
            day_offset=35,
        )
        bars.append(spring_bar)

        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)
        signal = detector.detect(bars, index=35)

        assert signal is None, "Spring must be rejected when volume >= 0.7x average"


class TestSOSDetection:
    """Tests for Sign of Strength (SOS) pattern detection."""

    def test_detects_sos_pattern(self) -> None:
        """SOS: close above resistance on HIGH volume (>1.5x) -> SOS LONG."""
        base_volume = 1000
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)

        # SOS bar: closes decisively above resistance on high volume
        # Detected resistance will be ~109.75 (90th percentile of highs)
        # Need close > resistance * 1.01 for the meaningful break check
        # Close in upper half of bar range for strong bar check
        # Low must be high enough so R-multiple >= 2.0
        # (stop = low * 0.99, risk = entry - stop, reward = target - entry)
        sos_bar = make_bar(
            open_price=110.5,
            high=112.5,
            low=111.0,  # Tight low -> small risk for good R-multiple
            close=112.0,  # Above 109.75 * 1.01 = 110.85
            volume=1800,  # 1800/1000 = 1.8x > 1.5x
            day_offset=35,
        )
        bars.append(sos_bar)

        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)
        signal = detector.detect(bars, index=35)

        assert signal is not None
        assert signal.pattern_type == "SOS"
        assert signal.direction == "LONG"

    def test_sos_rejected_on_low_volume(self) -> None:
        """SOS with volume < 1.5x average must be rejected (NON-NEGOTIABLE)."""
        base_volume = 1000
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)

        # SOS bar shape but with LOW volume
        sos_bar = make_bar(
            open_price=109.5,
            high=112.5,
            low=109.0,
            close=112.0,
            volume=1200,  # 1200/1000 = 1.2x < 1.5x -> REJECT
            day_offset=35,
        )
        bars.append(sos_bar)

        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)
        signal = detector.detect(bars, index=35)

        assert signal is None, "SOS must be rejected when volume < 1.5x average"


class TestUTADDetection:
    """Tests for Upthrust After Distribution (UTAD) pattern detection."""

    def test_detects_utad_pattern(self) -> None:
        """UTAD: prev bar pushes above resistance, current fails back below on elevated volume."""
        base_volume = 1000
        bars = make_range_bars(count=34, support=100.0, resistance=110.0, base_volume=base_volume)

        # Previous bar: pushed above resistance (upthrust)
        # Detected resistance ~109.75, so prev high just above it
        prev_bar = make_bar(
            open_price=109.0,
            high=110.5,  # Above resistance ~109.75 (upthrust)
            low=108.5,
            close=110.0,  # Closed above resistance
            volume=1300,
            day_offset=34,
        )
        bars.append(prev_bar)

        # Current bar: fails back below resistance on elevated volume
        # Entry ~109.0, Stop = 110.5 * 1.02 = ~112.71
        # Target = support ~100.25, R = (109-100.25)/(112.71-109) = 2.36
        utad_bar = make_bar(
            open_price=110.0,
            high=110.2,
            low=108.0,
            close=109.0,  # Below resistance ~109.75 -> failure
            volume=1400,  # 1400/1000 = 1.4x > 1.2x UTAD threshold
            day_offset=35,
        )
        bars.append(utad_bar)

        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)
        signal = detector.detect(bars, index=35)

        assert signal is not None
        assert signal.pattern_type == "UTAD"
        assert signal.direction == "SHORT"


class TestCooldownEnforcement:
    """Tests for cooldown between signals."""

    def test_cooldown_prevents_rapid_signals(self) -> None:
        """After a signal fires, another should not fire within cooldown_bars."""
        base_volume = 1000
        cooldown = 10

        # Build bars for first spring
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)
        spring_bar = make_bar(
            open_price=100.5,
            high=101.0,
            low=98.5,
            close=100.2,
            volume=400,
            day_offset=35,
        )
        bars.append(spring_bar)

        detector = WyckoffSignalDetector(
            min_range_bars=30, volume_lookback=20, cooldown_bars=cooldown
        )

        # First detection should succeed
        first_signal = detector.detect(bars, index=35)
        assert first_signal is not None, "First spring signal should fire"

        # Add more range bars, then another spring within cooldown
        for i in range(5):
            bars.append(
                make_bar(
                    open_price=104.0,
                    high=106.0,
                    low=103.0,
                    close=105.0,
                    volume=base_volume,
                    day_offset=36 + i,
                )
            )

        # Add another spring-like bar within cooldown window
        second_spring = make_bar(
            open_price=100.5,
            high=101.0,
            low=98.5,
            close=100.2,
            volume=400,
            day_offset=41,
        )
        bars.append(second_spring)

        # Index 41 is only 6 bars after index 35, within cooldown of 10
        second_signal = detector.detect(bars, index=41)
        assert second_signal is None, "Signal within cooldown window should be suppressed"


class TestRMultipleFilter:
    """Tests for R-multiple minimum filter."""

    def test_r_multiple_filter_rejects_low_r(self) -> None:
        """Signal with R-multiple < 2.0 should be filtered out.

        We create a spring with a very deep dip so the stop is far below entry,
        making the risk large relative to the reward (target = resistance).
        This should produce R < 2.0 and be filtered.

        Detected resistance ~109.75, support ~100.25, range_width ~9.5.
        Spring bar: low=95.0 (deep penetration ~5%), close=100.3 (recovers).
        Entry = 100.3, Stop = 95.0 * 0.98 = 93.1, Target = 109.75.
        Risk = 100.3 - 93.1 = 7.2, Reward = 109.75 - 100.3 = 9.45.
        R = 9.45 / 7.2 = 1.31 < 2.0 -> should be filtered.
        """
        base_volume = 1000
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)

        # Deep spring dip (just under 5% penetration limit) with low volume
        spring_bar = make_bar(
            open_price=100.5,
            high=101.0,
            low=95.5,
            close=100.3,
            volume=400,
            day_offset=35,
        )
        bars.append(spring_bar)

        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)
        signal = detector.detect(bars, index=35)

        # The deep spring causes high risk -> low R-multiple -> should be rejected
        # (may also be rejected by max_penetration_pct > 5%, either way None is correct)
        if signal is not None:
            assert signal.r_multiple >= Decimal(
                "2.0"
            ), f"Signal with R={signal.r_multiple} should have been filtered (min 2.0R)"
        # If None, the R-multiple filter (or range filter) correctly rejected it


class TestPhaseProgressionTracking:
    """Tests for the phase progression state machine."""

    def test_phase_no_backward_regression(self) -> None:
        """Once a symbol reaches Phase D, it must not regress to Phase C.

        Build bars that progress through B -> C -> D, then add bars that
        would normally classify as Phase C (close within range after having
        been in the upper half). The detector should still report D.
        """
        base_volume = 1000
        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)

        # Phase B: initial range bars
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=base_volume)

        # Phase C: bar with low penetrating below support (spring zone)
        spring_bar = make_bar(
            open_price=100.5,
            high=101.0,
            low=98.5,  # Low penetrates below support=100
            close=100.2,  # Recovers above support
            volume=400,
            day_offset=35,
        )
        bars.append(spring_bar)

        # Detect at spring bar to advance state to C
        sig = detector.detect(bars, index=35)
        # Verify we got Phase C (the spring should fire here)
        assert sig is not None
        assert sig.phase == "C"

        # Phase D: add bars in upper half of range with a break above resistance
        for i in range(11):
            bars.append(
                make_bar(
                    open_price=108.0,
                    high=111.0,  # Above resistance ~109.75 -> triggers "had_break_above"
                    low=107.0,
                    close=109.0,
                    volume=base_volume,
                    day_offset=36 + i,
                )
            )

        # Detect in the upper range -- should be Phase D (break above resistance)
        detector.detect(bars, index=46)
        # Signal may or may not fire, but phase state should be D now.
        # We verify by adding a bar that would raw-classify as C.

        # Now add bars that would normally classify as lower phases:
        # bar close within range, no break above resistance recently, lower half
        for i in range(12):
            bars.append(
                make_bar(
                    open_price=102.0,
                    high=103.0,
                    low=101.0,
                    close=102.0,  # Lower half of range
                    volume=base_volume,
                    day_offset=47 + i,
                )
            )

        # The raw classification would be C (10+ bars in range, lower half).
        # But the state machine should keep it at D.
        range_slice = bars[max(0, len(bars) - 61) :]
        tr = detector._identify_trading_range(range_slice)  # noqa: SLF001
        phase = detector._classify_phase(bars, len(bars) - 1, tr)  # noqa: SLF001
        assert phase in {"D", "E"}, f"Phase regressed to {phase}, expected D or E"

    def test_phase_d_requires_prior_c(self) -> None:
        """Upper-half-of-range heuristic should NOT produce Phase D without prior Phase C.

        Build bars that stay in the upper half of the range but never penetrate
        below support. The position-in-range > 0.5 heuristic should be blocked
        because the symbol has never visited Phase C.
        """
        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)

        # Build range bars that stay in the upper half (no low penetration)
        bars: list[OHLCVBar] = []
        for i in range(35):
            bars.append(
                make_bar(
                    open_price=106.0,
                    high=108.0,
                    low=104.0,
                    close=107.0,  # Upper half of 100-110 range
                    volume=1000,
                    day_offset=i,
                )
            )

        # Manually identify the trading range to check the phase
        tr = detector._identify_trading_range(bars)  # noqa: SLF001
        assert tr is not None

        # Classify phase -- should NOT be D because no prior Phase C
        # (No break above resistance either, and close is in upper half)
        # The position_in_range > 0.5 path should be blocked.
        phase = detector._classify_phase(bars, len(bars) - 1, tr)  # noqa: SLF001

        # Without Phase C visit, position-in-range heuristic should not yield D.
        # Phase should be B or C (C if 10+ bars in range criterion is met).
        assert (
            phase != "D"
        ), f"Phase was {phase}; position-in-range should not produce D without prior C visit"

    def test_phase_c_on_low_penetration(self) -> None:
        """Phase C should be classified when bar.low penetrates support even if close is above.

        This is important for Spring detection where the bar dips below support
        but closes back above it.
        """
        detector = WyckoffSignalDetector(min_range_bars=30, volume_lookback=20, cooldown_bars=5)

        # Build range bars
        bars = make_range_bars(count=35, support=100.0, resistance=110.0, base_volume=1000)

        # Add a bar where low penetrates support but close is above
        penetration_bar = make_bar(
            open_price=101.0,
            high=102.0,
            low=99.0,  # Below support of ~100.25
            close=101.5,  # Above support
            volume=1000,
            day_offset=35,
        )
        bars.append(penetration_bar)

        tr = detector._identify_trading_range(bars[max(0, len(bars) - 61) :])  # noqa: SLF001
        assert tr is not None

        phase = detector._classify_phase(bars, len(bars) - 1, tr)  # noqa: SLF001
        assert (
            phase == "C"
        ), f"Phase was {phase}; low penetration below support should yield Phase C"
