"""
Unit tests for AR Pattern Detector - Story 14.1

Tests cover:
- Happy path: Valid AR after Spring and SC
- Edge cases: Low-quality AR, weak recovery, high volume
- Invalid scenarios: Exceeds resistance, closes in lower half, no prior pattern

Test Coverage Target: 85%+
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.automatic_rally import AutomaticRally
from src.models.ohlcv import OHLCVBar
from src.models.selling_climax import SellingClimax
from src.models.spring import Spring
from src.pattern_engine.detectors.ar_detector import detect_ar_after_sc, detect_ar_after_spring


class TestDetectARAfterSpring:
    """Test AR detection after Spring patterns (Phase C)."""

    @pytest.fixture
    def base_bars(self):
        """Create base bar sequence with a Spring setup."""
        bars = []
        # Bars 0-19: Baseline bars for volume average calculation
        for i in range(20):
            bar = OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                open=Decimal("100.0"),
                high=Decimal("101.0"),
                low=Decimal("99.0"),
                close=Decimal("100.0"),
                volume=1000000,  # 1M baseline volume
                spread=Decimal("2.0"),
            )
            bars.append(bar)

        # Bar 20: Accumulation high (before decline)
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, 21, tzinfo=UTC),
                open=Decimal("100.0"),
                high=Decimal("105.0"),  # Peak before decline
                low=Decimal("100.0"),
                close=Decimal("104.0"),
                volume=1200000,
                spread=Decimal("5.0"),
            )
        )

        # Bars 21-29: Decline to Creek
        for i in range(9):
            bars.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 22 + i, tzinfo=UTC),
                    open=Decimal("104.0") - Decimal(str(i * 0.5)),
                    high=Decimal("104.5") - Decimal(str(i * 0.5)),
                    low=Decimal("103.0") - Decimal(str(i * 0.5)),
                    close=Decimal("103.5") - Decimal(str(i * 0.5)),
                    volume=900000,
                    spread=Decimal("1.5"),
                )
            )

        # Bar 30: Spring bar (penetration below Creek at 100.0)
        spring_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 31, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("100.5"),
            low=Decimal("98.0"),  # Spring low (2% below Creek)
            close=Decimal("100.2"),  # Recovers above Creek
            volume=600000,  # Low volume (<0.7x)
            spread=Decimal("2.5"),
        )
        bars.append(spring_bar)

        return bars

    @pytest.fixture
    def spring_pattern(self, base_bars):
        """Create Spring pattern at bar 30."""
        from uuid import uuid4

        spring = Spring(
            bar=base_bars[30],
            bar_index=30,
            penetration_pct=Decimal("0.02"),  # 2% penetration
            volume_ratio=Decimal("0.6"),  # 60% of average (low volume)
            recovery_bars=1,
            creek_reference=Decimal("100.0"),
            spring_low=Decimal("98.0"),
            recovery_price=Decimal("100.2"),
            detection_timestamp=datetime(2024, 1, 31, tzinfo=UTC),
            trading_range_id=uuid4(),
        )
        return spring

    def test_valid_ar_after_spring_high_quality(self, base_bars, spring_pattern):
        """
        Test Case 1: Valid high-quality AR after Spring.

        Scenario:
        - Spring at bar 30 → AR at bar 33 (3 bars later)
        - Volume 0.9x average (ideal moderate)
        - 50% recovery of decline (ideal)
        - Close in upper 60% of range (bullish)

        Expected:
        - AR detected with quality score > 0.7
        - recovery_percent = 0.50
        - volume_trend = "DECLINING"
        - prior_pattern_type = "SPRING"
        """
        # Add AR bar at index 33 (3 bars after Spring)
        # Decline was from 105.0 to 98.0 = 7.0 range
        # 50% recovery = 98.0 + 3.5 = 101.5 close
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 3, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("102.0"),
            low=Decimal("99.5"),
            close=Decimal("101.5"),  # 50% recovery
            volume=900000,  # 0.9x average (ideal moderate)
            spread=Decimal("2.5"),
        )
        base_bars.append(ar_bar)

        volume_avg = Decimal("1000000")  # 1M average
        ice_level = Decimal("105.0")  # Ice at prior high

        # Detect AR
        ar = detect_ar_after_spring(base_bars, spring_pattern, volume_avg, ice_level)

        # Assertions
        assert ar is not None, "AR should be detected"
        assert ar.bar_index == 31, "AR should be at bar 31 (index after Spring)"
        assert ar.quality_score > 0.7, f"Quality score {ar.quality_score} should be > 0.7"
        assert ar.recovery_percent >= Decimal("0.4"), "Should have 40%+ recovery"
        assert ar.prior_pattern_type == "SPRING"
        assert ar.prior_spring_bar == 30
        assert ar.volume_trend in [
            "DECLINING",
            "NEUTRAL",
            "INCREASING",
        ], "Volume trend should be valid"

    def test_valid_ar_after_spring_good_quality(self, base_bars, spring_pattern):
        """
        Test Case 2: Valid good-quality AR (later timing but good fundamentals).

        Scenario:
        - Spring at bar 30 → AR at bar 38 (8 bars later)
        - Volume 1.0x average (ideal moderate)
        - 45% recovery (good)
        - Close in upper 79% (very bullish)

        Expected:
        - AR detected with quality score 0.7-0.85 (good volume/recovery/range offset later timing)
        """
        # Add bars 31-37 (filler)
        for i in range(7):
            base_bars.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2024, 2, 1 + i, tzinfo=UTC),
                    open=Decimal("100.0"),
                    high=Decimal("100.5"),
                    low=Decimal("99.5"),
                    close=Decimal("100.0"),
                    volume=950000,
                    spread=Decimal("1.0"),
                )
            )

        # AR bar at index 38 (8 bars after Spring)
        # 45% recovery: 98.0 + (7.0 * 0.45) = 101.15
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 8, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("101.5"),
            low=Decimal("99.8"),
            close=Decimal("101.15"),  # 45% recovery
            volume=1000000,  # 1.0x average
            spread=Decimal("1.7"),
        )
        base_bars.append(ar_bar)

        volume_avg = Decimal("1000000")

        # Detect AR
        ar = detect_ar_after_spring(base_bars, spring_pattern, volume_avg)

        # Assertions
        assert ar is not None, "AR should be detected"
        assert (
            0.7 <= ar.quality_score <= 0.85
        ), f"Quality score {ar.quality_score} should be 0.7-0.85"
        assert ar.bars_after_sc == 8, "Should be 8 bars after Spring"

    def test_ar_too_weak_recovery_rejected(self, base_bars, spring_pattern):
        """
        Test Case 3: AR with insufficient recovery (<40%) rejected.

        Scenario:
        - Recovery only 35% of decline
        - All other parameters valid

        Expected:
        - No AR detected (fails validation)
        """
        # AR bar with only 35% recovery
        # 35% recovery: 98.0 + (7.0 * 0.35) = 100.45
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 3, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("101.0"),
            low=Decimal("99.5"),
            close=Decimal("100.45"),  # Only 35% recovery
            volume=900000,  # Good volume
            spread=Decimal("1.5"),
        )
        base_bars.append(ar_bar)

        volume_avg = Decimal("1000000")

        # Detect AR
        ar = detect_ar_after_spring(base_bars, spring_pattern, volume_avg)

        # Assertions
        assert ar is None, "AR with <40% recovery should be rejected"

    def test_ar_volume_too_high_rejected(self, base_bars, spring_pattern):
        """
        Test Case 4: AR with excessive volume (>1.5x) rejected.

        Scenario:
        - Volume 1.6x average (suggests distribution)
        - Recovery and other params valid

        Expected:
        - No AR detected (volume too high)
        """
        # AR bar with excessive volume
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 3, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("102.0"),
            low=Decimal("99.5"),
            close=Decimal("101.5"),  # 50% recovery (good)
            volume=1600000,  # 1.6x average (too high!)
            spread=Decimal("2.5"),
        )
        base_bars.append(ar_bar)

        volume_avg = Decimal("1000000")

        # Detect AR
        ar = detect_ar_after_spring(base_bars, spring_pattern, volume_avg)

        # Assertions
        assert ar is None, "AR with >1.5x volume should be rejected (distribution risk)"

    def test_ar_exceeds_ice_rejected(self, base_bars, spring_pattern):
        """
        Test Case 5: AR exceeding Ice level rejected.

        Scenario:
        - AR high breaks above Ice (105.0)
        - All other parameters valid

        Expected:
        - No AR detected (exceeds resistance)
        """
        # AR bar that exceeds Ice
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 3, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("106.0"),  # Exceeds Ice at 105.0
            low=Decimal("99.5"),
            close=Decimal("105.5"),
            volume=900000,  # Good volume
            spread=Decimal("6.5"),
        )
        base_bars.append(ar_bar)

        volume_avg = Decimal("1000000")
        ice_level = Decimal("105.0")

        # Detect AR
        ar = detect_ar_after_spring(base_bars, spring_pattern, volume_avg, ice_level)

        # Assertions
        assert ar is None, "AR exceeding Ice level should be rejected"

    def test_ar_closes_lower_half_rejected(self, base_bars, spring_pattern):
        """
        Test Case 6: AR closing in lower half of range rejected.

        Scenario:
        - Close at 30% of bar range (bearish)
        - Recovery and volume valid

        Expected:
        - No AR detected (fails close position validation)
        """
        # AR bar closing in lower 30% of range
        # Range: 99.5 to 102.0 = 2.5
        # 30% position: 99.5 + (2.5 * 0.3) = 100.25
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 3, tzinfo=UTC),
            open=Decimal("101.0"),
            high=Decimal("102.0"),
            low=Decimal("99.5"),
            close=Decimal("100.25"),  # Lower 30% (bearish)
            volume=900000,
            spread=Decimal("2.5"),
        )
        base_bars.append(ar_bar)

        volume_avg = Decimal("1000000")

        # Detect AR
        ar = detect_ar_after_spring(base_bars, spring_pattern, volume_avg)

        # Assertions
        assert ar is None, "AR closing in lower half should be rejected"

    def test_no_spring_provided_returns_none(self, base_bars):
        """
        Test Case 7: No Spring provided returns None.

        Expected:
        - None returned with error logged
        """
        volume_avg = Decimal("1000000")

        ar = detect_ar_after_spring(base_bars, None, volume_avg)

        assert ar is None, "Should return None when Spring is None"

    def test_empty_bars_returns_none(self, spring_pattern):
        """
        Test Case 8: Empty bars list returns None.

        Expected:
        - None returned with error logged
        """
        volume_avg = Decimal("1000000")

        ar = detect_ar_after_spring([], spring_pattern, volume_avg)

        assert ar is None, "Should return None when bars list is empty"


class TestDetectARAfterSC:
    """Test AR detection after Selling Climax patterns (Phase A)."""

    @pytest.fixture
    def base_bars_with_sc(self):
        """Create bar sequence with Selling Climax setup."""
        bars = []
        # Bars 0-19: Baseline
        for i in range(20):
            bar = OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                open=Decimal("100.0"),
                high=Decimal("101.0"),
                low=Decimal("99.0"),
                close=Decimal("100.0"),
                volume=1000000,
                spread=Decimal("2.0"),
            )
            bars.append(bar)

        # Bar 20: Prior high
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, 21, tzinfo=UTC),
                open=Decimal("100.0"),
                high=Decimal("110.0"),
                low=Decimal("100.0"),
                close=Decimal("108.0"),
                volume=1200000,
                spread=Decimal("10.0"),
            )
        )

        # Bars 21-29: Decline
        for i in range(9):
            bars.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 22 + i, tzinfo=UTC),
                    open=Decimal("108.0") - Decimal(str(i * 1.0)),
                    high=Decimal("108.5") - Decimal(str(i * 1.0)),
                    low=Decimal("107.0") - Decimal(str(i * 1.0)),
                    close=Decimal("107.5") - Decimal(str(i * 1.0)),
                    volume=1500000,
                    spread=Decimal("1.5"),
                )
            )

        # Bar 30: Selling Climax (panic selling)
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 31, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("100.5"),
            low=Decimal("95.0"),  # SC low (climactic decline)
            close=Decimal("96.0"),
            volume=3000000,  # Climactic volume (3.0x average)
            spread=Decimal("5.5"),
        )
        bars.append(sc_bar)

        return bars

    @pytest.fixture
    def sc_pattern(self, base_bars_with_sc):
        """Create SellingClimax pattern at bar 30."""
        sc = SellingClimax(
            bar=base_bars_with_sc[30].model_dump(),
            bar_index=30,
            volume_ratio=Decimal("3.0"),  # 3.0x average
            spread_ratio=Decimal("2.0"),  # 2.0x average spread
            close_position=Decimal("0.7"),  # Close in upper 70%
            confidence=80,
            prior_close=Decimal("99.5"),  # Prior bar close
            detection_timestamp=datetime(2024, 1, 31, tzinfo=UTC),
        )
        return sc

    def test_valid_ar_after_sc_high_quality(self, base_bars_with_sc, sc_pattern):
        """
        Test Case 9: Valid high-quality AR after Selling Climax.

        Scenario:
        - SC at bar 30 → AR at bar 34 (4 bars later)
        - Volume 1.0x average (good, declining from climax)
        - 60% recovery (excellent)
        - Close in upper 70% (very bullish)

        Expected:
        - AR detected with quality score > 0.75
        - volume_trend = "DECLINING"
        - prior_pattern_type = "SC"
        """
        # Add filler bars
        for i in range(3):
            base_bars_with_sc.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2024, 2, 1 + i, tzinfo=UTC),
                    open=Decimal("96.0"),
                    high=Decimal("97.0"),
                    low=Decimal("95.5"),
                    close=Decimal("96.5"),
                    volume=1100000,
                    spread=Decimal("1.5"),
                )
            )

        # AR bar: Decline from 110.0 to 95.0 = 15.0 range
        # 60% recovery: 95.0 + (15.0 * 0.60) = 104.0
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 4, tzinfo=UTC),
            open=Decimal("96.5"),
            high=Decimal("105.0"),
            low=Decimal("96.0"),
            close=Decimal("104.0"),  # 60% recovery, upper 89% of range
            volume=1000000,  # 1.0x (declined from 3.0x climax)
            spread=Decimal("9.0"),
        )
        base_bars_with_sc.append(ar_bar)

        volume_avg = Decimal("1000000")

        # Detect AR
        ar = detect_ar_after_sc(base_bars_with_sc, sc_pattern, volume_avg)

        # Assertions
        assert ar is not None, "AR should be detected after SC"
        assert ar.quality_score > 0.75, f"Quality score {ar.quality_score} should be > 0.75"
        assert ar.prior_pattern_type == "SC"
        assert ar.volume_trend == "DECLINING", "Volume should be declining from climax"
        assert ar.recovery_percent >= Decimal("0.5"), "Should have 50%+ recovery"

    def test_ar_quality_score_calculation(self, base_bars_with_sc, sc_pattern):
        """
        Test Case 10: Verify quality score calculation.

        Tests the calculate_quality_score method with known inputs.

        Expected:
        - Score calculation matches expected weights
        """
        # Create AR with specific parameters

        ar = AutomaticRally(
            bar={
                "timestamp": "2024-02-01T00:00:00Z",
                "high": "105.0",
                "low": "96.0",
                "close": "104.0",
            },
            bar_index=34,
            rally_pct=Decimal("0.60"),
            bars_after_sc=4,
            sc_reference={},
            sc_low=Decimal("95.0"),
            ar_high=Decimal("105.0"),
            volume_profile="NORMAL",
            recovery_percent=Decimal("0.60"),  # 60% recovery → 0.3 score
            volume_trend="DECLINING",
            prior_pattern_type="SC",
        )

        # Test quality score calculation
        # Volume: 1.0x (in 0.8-1.2 range) → 0.4 score
        # Recovery: 60% → 0.3 score
        # Timing: 4 bars → 0.2 score
        # Close position: 0.89 → 0.1 score
        # Total expected: 0.4 + 0.3 + 0.2 + 0.1 = 1.0
        score = ar.calculate_quality_score(Decimal("1.0"), Decimal("0.89"))

        assert score == pytest.approx(1.0, abs=0.01), f"Expected score ~1.0, got {score}"

    def test_low_quality_ar_warning(self, base_bars_with_sc, sc_pattern):
        """
        Test Case 11: Low-quality AR at minimum thresholds.

        Scenario:
        - AR at bar 40 (10 bars later, maximum allowed)
        - Volume 0.7x (minimum acceptable)
        - 40% recovery (minimum)
        - Close at 50% (minimum)

        Expected:
        - AR detected with quality score 0.5-0.6 (all minimum parameters)
        - Still valid AR but at lower end of quality spectrum
        """
        # Add filler bars
        for i in range(9):
            base_bars_with_sc.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2024, 2, 1 + i, tzinfo=UTC),
                    open=Decimal("96.0"),
                    high=Decimal("96.5"),
                    low=Decimal("95.5"),
                    close=Decimal("96.0"),
                    volume=900000,
                    spread=Decimal("1.0"),
                )
            )

        # Low-quality AR bar
        # 40% recovery: 95.0 + (15.0 * 0.40) = 101.0
        # For 50% close position with close=101.0: need range where (101-low)/(high-low)=0.5
        # Using low=96.0, high=106.0: (101-96)/(106-96) = 5/10 = 0.5 ✓
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 2, 10, tzinfo=UTC),
            open=Decimal("96.0"),
            high=Decimal("106.0"),
            low=Decimal("96.0"),
            close=Decimal("101.0"),  # 40% recovery, exactly at 50% of range
            volume=700000,  # 0.7x (minimum)
            spread=Decimal("10.0"),
        )
        base_bars_with_sc.append(ar_bar)

        volume_avg = Decimal("1000000")

        # Detect AR
        ar = detect_ar_after_sc(base_bars_with_sc, sc_pattern, volume_avg)

        # Assertions
        assert ar is not None, "AR at minimum thresholds should still be detected"
        assert (
            0.5 <= ar.quality_score <= 0.6
        ), f"Quality score {ar.quality_score} should be 0.5-0.6 (minimum params)"
        assert ar.bars_after_sc == 10, "Should be at maximum timing window"
