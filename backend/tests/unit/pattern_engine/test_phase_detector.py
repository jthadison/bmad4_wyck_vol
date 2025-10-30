"""
Unit tests for phase_detector module - Selling Climax detection.

Tests cover:
- Synthetic SC bar detection with correct characteristics
- False positive prevention (normal down bars)
- Confidence scoring boundaries
- Edge cases (insufficient data, mismatches)
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.models.effort_result import EffortResult
from src.pattern_engine.phase_detector import (
    detect_selling_climax,
    detect_sc_zone,
    detect_automatic_rally,
    detect_secondary_test,
    is_phase_a_confirmed,
)


class TestSellingClimaxDetection:
    """Test suite for Selling Climax detection functionality."""

    def test_detect_synthetic_sc_bar_high_confidence(self):
        """
        Test detection of synthetic SC bar with high confidence.

        AC 8: Synthetic climactic bar with correct characteristics detected.

        Setup:
        - Create prior bar (normal bar)
        - Create SC bar with:
          - volume_ratio = 2.5 (ultra-high volume, 35 pts)
          - spread_ratio = 1.8 (wide spread, 25 pts)
          - close_position = 0.8 (close in upper 20%, 25 pts)
          - effort_result = CLIMACTIC
          - current close < prior close (downward)
        - Expected confidence = 85
        """
        # Create prior bar (normal day)
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # Create SC bar (climactic selling)
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.28"),  # close_position = (225.28-212)/(228.5-212) = 0.8
            volume=75000000,  # 2.5x volume
            spread=Decimal("16.50"),  # 1.8x spread
        )

        sc_analysis = VolumeAnalysis(
            bar=sc_bar,
            volume_ratio=Decimal("2.5"),  # Ultra-high volume (35 pts)
            spread_ratio=Decimal("1.8"),  # Wide spread (25 pts)
            close_position=Decimal("0.8"),  # Close at high (25 pts) = 85 total
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [prior_bar, sc_bar]
        volume_analysis = [prior_analysis, sc_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is not None, "SC should be detected"
        assert result.confidence >= 80, f"Expected confidence >= 80, got {result.confidence}"
        assert result.volume_ratio == Decimal("2.5")
        assert result.spread_ratio == Decimal("1.8")
        assert result.close_position == Decimal("0.8")
        assert result.bar["symbol"] == "TEST"
        assert result.bar["timestamp"] == "2020-03-23T00:00:00+00:00"
        assert result.prior_close == Decimal("232.00")

    def test_reject_normal_down_bar_low_volume(self):
        """
        Test false positive prevention - normal down bar rejected.

        AC 10: Normal down bars rejected (volume/spread too low).

        Setup:
        - volume_ratio = 1.2 (normal volume, below 2.0 threshold)
        - spread_ratio = 1.0 (normal spread, below 1.5 threshold)
        - close_position = 0.5 (mid-range)
        - effort_result = NORMAL
        - current close < prior close (downward)

        Expected: None (rejected as false positive)
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # Normal down bar (NOT SC)
        down_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("232.00"),
            high=Decimal("233.00"),
            low=Decimal("228.00"),
            close=Decimal("230.50"),
            volume=36000000,  # Only 1.2x volume
            volume_ratio=Decimal("1.2"),
            spread=Decimal("5.00"),  # Only 1.0x spread
        )

        down_analysis = VolumeAnalysis(
            bar=down_bar,
            volume_ratio=Decimal("1.2"),  # Below 2.0 threshold
            spread_ratio=Decimal("1.0"),  # Below 1.5 threshold
            close_position=Decimal("0.5"),
            effort_result=EffortResult.NORMAL,  # Not CLIMACTIC
        )

        bars = [prior_bar, down_bar]
        volume_analysis = [prior_analysis, down_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "Normal down bar should be rejected"

    def test_reject_high_volume_but_narrow_spread(self):
        """
        Test rejection: high volume but narrow spread.

        AC 10: High volume but narrow spread rejected.
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # High volume but narrow spread
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("232.00"),
            high=Decimal("232.50"),
            low=Decimal("228.00"),
            close=Decimal("230.00"),
            volume=75000000,  # High volume (2.5x)
            spread=Decimal("4.50"),  # Narrow spread (only 1.0x)
        )

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),  # High
            spread_ratio=Decimal("1.0"),  # Too narrow (< 1.5)
            close_position=Decimal("0.44"),
            effort_result=EffortResult.CLIMACTIC,  # Would be CLIMACTIC by Path 1
        )

        bars = [prior_bar, bar]
        volume_analysis = [prior_analysis, analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "High volume with narrow spread should be rejected"

    def test_reject_climactic_but_close_too_low(self):
        """
        Test rejection: CLIMACTIC bar but close position too low.

        AC 10: CLIMACTIC bar with close < 0.5 rejected.
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # CLIMACTIC bar but close too low (might be Buying Climax)
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("232.00"),
            high=Decimal("235.00"),
            low=Decimal("212.00"),
            close=Decimal("215.00"),  # close_position = 0.13 (too low)
            volume=75000000,
            spread=Decimal("23.00"),
        )

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("2.0"),
            close_position=Decimal("0.13"),  # Too low for SC
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [prior_bar, bar]
        volume_analysis = [prior_analysis, analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "CLIMACTIC bar with close_position < 0.5 should be rejected"

    def test_reject_climactic_but_upward_movement(self):
        """
        Test rejection: CLIMACTIC bar but upward movement.

        AC 10: CLIMACTIC bar with close >= prior close rejected.
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # CLIMACTIC bar but upward movement (not selling pressure)
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("245.00"),
            low=Decimal("225.00"),
            close=Decimal("240.00"),  # close > prior close (upward)
            volume=75000000,
            spread=Decimal("20.00"),
        )

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("2.0"),
            close_position=Decimal("0.75"),
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [prior_bar, bar]
        volume_analysis = [prior_analysis, analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "Upward CLIMACTIC bar should be rejected (not SC)"

    def test_confidence_minimum_threshold(self):
        """
        Test minimum confidence SC.

        AC 7: Confidence scoring boundaries.

        Setup:
        - volume_ratio = 2.0 (30 pts)
        - spread_ratio = 1.5 (20 pts)
        - close_position = 0.7 (20 pts)
        - Expected confidence = 70 (minimum viable SC)
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # Minimum SC characteristics
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("223.55"),  # close_position = 0.7
            volume=60000000,
            spread=Decimal("16.50"),
        )

        sc_analysis = VolumeAnalysis(
            bar=sc_bar,
            volume_ratio=Decimal("2.0"),  # Minimum (30 pts)
            spread_ratio=Decimal("1.5"),  # Minimum (20 pts)
            close_position=Decimal("0.7"),  # Ideal threshold (20 pts)
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [prior_bar, sc_bar]
        volume_analysis = [prior_analysis, sc_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is not None, "Minimum SC should be detected"
        assert result.confidence == 70, f"Expected confidence 70, got {result.confidence}"

    def test_confidence_maximum_score(self):
        """
        Test maximum confidence SC.

        AC 7: Confidence scoring boundaries.

        Setup:
        - volume_ratio = 3.5 (40 pts)
        - spread_ratio = 2.5 (30 pts)
        - close_position = 0.95 (30 pts)
        - Expected confidence = 100 (perfect SC)
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        # Perfect SC characteristics
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("227.68"),  # close_position = 0.95
            volume=105000000,  # 3.5x
            spread=Decimal("16.50"),  # 2.5x (wait, need to adjust spread for ratio)
        )

        sc_analysis = VolumeAnalysis(
            bar=sc_bar,
            volume_ratio=Decimal("3.5"),  # Extreme (40 pts)
            spread_ratio=Decimal("2.5"),  # Very wide (30 pts)
            close_position=Decimal("0.95"),  # Excellent (30 pts)
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [prior_bar, sc_bar]
        volume_analysis = [prior_analysis, sc_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is not None, "Perfect SC should be detected"
        assert result.confidence == 100, f"Expected confidence 100, got {result.confidence}"

    def test_confidence_mid_range(self):
        """
        Test mid-range confidence SC.

        AC 7: Confidence scoring boundaries.

        Setup:
        - volume_ratio = 2.5 (35 pts)
        - spread_ratio = 1.8 (25 pts)
        - close_position = 0.8 (25 pts)
        - Expected confidence = 85
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.57"),
            effort_result=EffortResult.NORMAL,
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.28"),
            volume=75000000,
            spread=Decimal("16.50"),
        )

        sc_analysis = VolumeAnalysis(
            bar=sc_bar,
            volume_ratio=Decimal("2.5"),  # 35 pts
            spread_ratio=Decimal("1.8"),  # 25 pts
            close_position=Decimal("0.8"),  # 25 pts
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [prior_bar, sc_bar]
        volume_analysis = [prior_analysis, sc_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is not None, "Mid-range SC should be detected"
        assert result.confidence == 85, f"Expected confidence 85, got {result.confidence}"


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_only_one_bar_returns_none(self):
        """
        Test with only 1 bar (need prior close).

        AC: Edge case - insufficient data.
        Expected: None (need at least 2 bars)
        """
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.00"),
            volume=75000000,
            spread=Decimal("16.50"),
        )

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.78"),
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [bar]
        volume_analysis = [analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "Should return None with only 1 bar"

    def test_empty_bars_list_raises_error(self):
        """
        Test with empty bars list.

        AC: Edge case - empty input.
        Expected: ValueError
        """
        bars = []
        volume_analysis = []

        # Execute & Assert
        with pytest.raises(ValueError, match="Bars list cannot be empty"):
            detect_selling_climax(bars, volume_analysis)

    def test_bars_volume_mismatch_raises_error(self):
        """
        Test with bars/volume_analysis length mismatch.

        AC: Edge case - length mismatch.
        Expected: ValueError
        """
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.00"),
            volume=75000000,
            spread=Decimal("16.50"),
        )

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.78"),
            effort_result=EffortResult.CLIMACTIC,
        )

        bars = [bar, bar]  # 2 bars
        volume_analysis = [analysis]  # 1 analysis (mismatch)

        # Execute & Assert
        with pytest.raises(ValueError, match="length mismatch"):
            detect_selling_climax(bars, volume_analysis)

    def test_volume_ratio_none_skipped(self):
        """
        Test with volume_ratio = None (first 20 bars).

        AC: Edge case - insufficient volume data.
        Expected: None (skipped)
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        prior_analysis = VolumeAnalysis(
            bar=prior_bar,
            volume_ratio=None,  # No data yet
            spread_ratio=None,
            close_position=None,
            effort_result=None,
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.00"),
            volume=75000000,
            spread=Decimal("16.50"),
        )

        sc_analysis = VolumeAnalysis(
            bar=sc_bar,
            volume_ratio=None,  # No data yet (first 20 bars)
            spread_ratio=None,
            close_position=None,
            effort_result=EffortResult.CLIMACTIC,  # Would be CLIMACTIC if data available
        )

        bars = [prior_bar, sc_bar]
        volume_analysis = [prior_analysis, sc_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "Should return None when volume_ratio is None"

    def test_climactic_at_index_zero_skipped(self):
        """
        Test CLIMACTIC bar at index 0 (no prior bar).

        AC: Edge case - CLIMACTIC at first bar.
        Expected: None (can't validate downward movement)
        """
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.00"),
            volume=75000000,
            spread=Decimal("16.50"),
        )

        sc_analysis = VolumeAnalysis(
            bar=sc_bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.78"),
            effort_result=EffortResult.CLIMACTIC,
        )

        normal_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 24, tzinfo=timezone.utc),
            open=Decimal("225.00"),
            high=Decimal("230.00"),
            low=Decimal("223.00"),
            close=Decimal("228.00"),
            volume=40000000,
            spread=Decimal("7.00"),
        )

        normal_analysis = VolumeAnalysis(
            bar=normal_bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.71"),
            effort_result=EffortResult.NORMAL,
        )

        bars = [sc_bar, normal_bar]  # CLIMACTIC at index 0
        volume_analysis = [sc_analysis, normal_analysis]

        # Execute
        result = detect_selling_climax(bars, volume_analysis)

        # Assert
        assert result is None, "CLIMACTIC at index 0 should be skipped (no prior bar)"


class TestSCZoneDetection:
    """Test suite for Selling Climax Zone detection functionality."""

    def test_detect_multi_bar_sc_zone(self):
        """
        Test detection of SC zone with multiple climactic bars.

        Setup: 3 SC bars within 10 bars:
        - Bar 0: Normal (prior)
        - Bar 1: SC #1 (first SC)
        - Bar 2-3: Normal
        - Bar 4: SC #2 (3 bars after SC #1)
        - Bar 5-7: Normal
        - Bar 8: SC #3 (4 bars after SC #2)

        Expected: SC Zone with 3 bars, duration = 7 bars
        """
        bars = []
        volume_analysis_list = []

        # Bar 0: Normal (prior)
        bar0 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 20, tzinfo=timezone.utc),
            open=Decimal("300.00"),
            high=Decimal("305.00"),
            low=Decimal("298.00"),
            close=Decimal("302.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )
        bars.append(bar0)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bar0,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.57"),
                effort_result=EffortResult.NORMAL,
            )
        )

        # Bar 1: SC #1 (first SC)
        bar1 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 21, tzinfo=timezone.utc),
            open=Decimal("302.00"),
            high=Decimal("302.50"),
            low=Decimal("270.00"),
            close=Decimal("294.60"),  # close_position = 0.76
            volume=75000000,  # 2.5x
            spread=Decimal("32.50"),
        )
        bars.append(bar1)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bar1,
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.76"),
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        # Bars 2-3: Normal
        for i in range(2, 4):
            bar = OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 20 + i, tzinfo=timezone.utc),
                open=Decimal("290.00"),
                high=Decimal("295.00"),
                low=Decimal("288.00"),
                close=Decimal("292.00"),
                volume=35000000,
                spread=Decimal("7.00"),
            )
            bars.append(bar)
            volume_analysis_list.append(
                VolumeAnalysis(
                    bar=bar,
                    volume_ratio=Decimal("1.2"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.57"),
                    effort_result=EffortResult.NORMAL,
                )
            )

        # Bar 4: SC #2 (3 bars after SC #1)
        bar4 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 24, tzinfo=timezone.utc),
            open=Decimal("292.00"),
            high=Decimal("293.00"),
            low=Decimal("265.00"),
            close=Decimal("286.00"),  # close_position = 0.75
            volume=80000000,  # 2.67x
            spread=Decimal("28.00"),
        )
        bars.append(bar4)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bar4,
                volume_ratio=Decimal("2.67"),
                spread_ratio=Decimal("1.9"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        # Bars 5-7: Normal
        for i in range(5, 8):
            bar = OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 20 + i, tzinfo=timezone.utc),
                open=Decimal("286.00"),
                high=Decimal("290.00"),
                low=Decimal("283.00"),
                close=Decimal("287.00"),
                volume=38000000,
                spread=Decimal("7.00"),
            )
            bars.append(bar)
            volume_analysis_list.append(
                VolumeAnalysis(
                    bar=bar,
                    volume_ratio=Decimal("1.3"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.57"),
                    effort_result=EffortResult.NORMAL,
                )
            )

        # Bar 8: SC #3 (4 bars after SC #2)
        bar8 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 28, tzinfo=timezone.utc),
            open=Decimal("287.00"),
            high=Decimal("288.00"),
            low=Decimal("260.00"),
            close=Decimal("281.00"),  # close_position = 0.75
            volume=85000000,  # 2.83x
            spread=Decimal("28.00"),
        )
        bars.append(bar8)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bar8,
                volume_ratio=Decimal("2.83"),
                spread_ratio=Decimal("2.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        # Execute
        zone = detect_sc_zone(bars, volume_analysis_list, max_gap_bars=10)

        # Assert
        assert zone is not None, "SC Zone should be detected"
        assert zone.bar_count == 3, f"Expected 3 SC bars, got {zone.bar_count}"
        assert zone.duration_bars == 7, f"Expected duration 7 bars, got {zone.duration_bars}"
        assert zone.zone_start.bar["timestamp"] == "2020-03-21T00:00:00+00:00", "Zone start should be first SC"
        assert zone.zone_end.bar["timestamp"] == "2020-03-28T00:00:00+00:00", "Zone end should be last SC"
        assert zone.zone_low == Decimal("260.00"), f"Zone low should be $260, got ${zone.zone_low}"
        assert zone.avg_confidence >= 80, f"Average confidence should be >= 80, got {zone.avg_confidence}"

    def test_single_sc_returns_none(self):
        """
        Test that single SC (no additional bars) returns None.

        A zone requires 2+ climactic bars.
        """
        # Create single SC scenario
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("230.00"),
            high=Decimal("235.00"),
            low=Decimal("228.00"),
            close=Decimal("232.00"),
            volume=30000000,
            spread=Decimal("7.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("228.00"),
            high=Decimal("228.50"),
            low=Decimal("212.00"),
            close=Decimal("225.28"),
            volume=75000000,
            spread=Decimal("16.50"),
        )

        bars = [prior_bar, sc_bar]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=prior_bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.57"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=sc_bar,
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.8"),
                effort_result=EffortResult.CLIMACTIC,
            ),
        ]

        # Execute
        zone = detect_sc_zone(bars, volume_analysis_list)

        # Assert
        assert zone is None, "Single SC should not create a zone"

    def test_sc_zone_with_gap_exceeded(self):
        """
        Test that SC bars beyond max_gap_bars are not included in zone.

        Setup: 2 SC bars 15 bars apart (exceeds default max_gap=10)
        Expected: Zone not created (only 1 SC within gap window)
        """
        bars = []
        volume_analysis_list = []

        # Prior bar
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 20, tzinfo=timezone.utc),
                open=Decimal("300.00"),
                high=Decimal("305.00"),
                low=Decimal("298.00"),
                close=Decimal("302.00"),
                volume=30000000,
                spread=Decimal("7.00"),
            )
        )
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bars[-1],
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.57"),
                effort_result=EffortResult.NORMAL,
            )
        )

        # SC #1
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 21, tzinfo=timezone.utc),
                open=Decimal("302.00"),
                high=Decimal("302.50"),
                low=Decimal("270.00"),
                close=Decimal("294.60"),
                volume=75000000,
                spread=Decimal("32.50"),
            )
        )
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bars[-1],
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.76"),
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        # 15 normal bars (exceeds gap)
        from datetime import timedelta
        base_date = datetime(2020, 3, 22, tzinfo=timezone.utc)
        for i in range(15):
            bars.append(
                OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=base_date + timedelta(days=i),
                    open=Decimal("290.00"),
                    high=Decimal("295.00"),
                    low=Decimal("288.00"),
                    close=Decimal("292.00"),
                    volume=35000000,
                    spread=Decimal("7.00"),
                )
            )
            volume_analysis_list.append(
                VolumeAnalysis(
                    bar=bars[-1],
                    volume_ratio=Decimal("1.2"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.57"),
                    effort_result=EffortResult.NORMAL,
                )
            )

        # SC #2 (15 bars after SC #1, exceeds gap)
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 4, 6, tzinfo=timezone.utc),
                open=Decimal("292.00"),
                high=Decimal("293.00"),
                low=Decimal("265.00"),
                close=Decimal("286.00"),
                volume=80000000,
                spread=Decimal("28.00"),
            )
        )
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bars[-1],
                volume_ratio=Decimal("2.67"),
                spread_ratio=Decimal("1.9"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        # Execute
        zone = detect_sc_zone(bars, volume_analysis_list, max_gap_bars=10)

        # Assert
        assert zone is None, "SC bars beyond max_gap should not create zone"


class TestAutomaticRallyDetection:
    """Test suite for Automatic Rally (AR) detection functionality."""

    def test_detect_synthetic_ar_after_sc(self):
        """
        Test detection of synthetic AR after SC with 3.2% rally.

        AC 8: Synthetic AR sequence detected correctly.

        Setup:
        - SC bar at low $100.00
        - Bar 1 after SC: high $101.00 (1% rally, not enough)
        - Bar 2 after SC: high $102.50 (2.5% rally, not enough)
        - Bar 3 after SC: high $103.20 (3.2% rally, VALID AR)

        Expected:
        - AR detected at bar 3
        - rally_pct = 0.032 (3.2%)
        - bars_after_sc = 3
        - ar_high = 103.20
        - sc_low = 100.00
        """
        # Prior bar (normal)
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        # SC bar (climactic selling)
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),  # SC low
            close=Decimal("103.75"),  # close_position = 0.68 (upper region)
            volume=125000000,  # 2.5x volume
            spread=Decimal("5.50"),  # 1.8x spread
        )

        # Bar 1 after SC (1% rally, insufficient)
        bar1 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
            open=Decimal("104.00"),
            high=Decimal("101.00"),  # 1% from SC low
            low=Decimal("100.20"),
            close=Decimal("100.80"),
            volume=60000000,
            spread=Decimal("0.80"),
        )

        # Bar 2 after SC (2.5% rally, still insufficient)
        bar2 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 4, tzinfo=timezone.utc),
            open=Decimal("100.80"),
            high=Decimal("102.50"),  # 2.5% from SC low
            low=Decimal("100.50"),
            close=Decimal("102.00"),
            volume=55000000,
            spread=Decimal("2.00"),
        )

        # Bar 3 after SC (3.2% rally, VALID AR)
        bar3 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 5, tzinfo=timezone.utc),
            open=Decimal("102.00"),
            high=Decimal("103.20"),  # 3.2% from SC low
            low=Decimal("101.80"),
            close=Decimal("103.00"),
            volume=70000000,  # 1.4x volume (HIGH)
            spread=Decimal("1.40"),
        )

        bars = [prior_bar, sc_bar, bar1, bar2, bar3]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=prior_bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=sc_bar,
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.68"),
                effort_result=EffortResult.CLIMACTIC,
            ),
            VolumeAnalysis(
                bar=bar1,
                volume_ratio=Decimal("1.2"),
                spread_ratio=Decimal("0.8"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=bar2,
                volume_ratio=Decimal("1.1"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=bar3,
                volume_ratio=Decimal("1.4"),  # HIGH volume
                spread_ratio=Decimal("0.7"),
                close_position=Decimal("0.86"),
                effort_result=EffortResult.NORMAL,
            ),
        ]

        # Detect SC first
        sc = detect_selling_climax(bars, volume_analysis_list)
        assert sc is not None, "SC should be detected"

        # Execute AR detection
        result = detect_automatic_rally(bars, sc, volume_analysis_list)

        # Assert
        assert result is not None, "AR should be detected"
        assert result.rally_pct == Decimal("0.032"), f"Expected rally_pct 0.032, got {result.rally_pct}"
        assert result.bars_after_sc == 3, f"Expected bars_after_sc 3, got {result.bars_after_sc}"
        assert result.ar_high == Decimal("103.20"), f"Expected ar_high 103.20, got {result.ar_high}"
        assert result.sc_low == Decimal("100.00"), f"Expected sc_low 100.00, got {result.sc_low}"
        assert result.volume_profile == "HIGH", f"Expected HIGH volume, got {result.volume_profile}"
        assert result.bar["symbol"] == "TEST"

    def test_ar_timeout_no_demand(self):
        """
        Test AR timeout when no 3%+ rally occurs within 10 bars.

        AC 10: If no AR within 10 bars, SC invalidated (not enough demand).

        Setup:
        - SC at low $100
        - 10 bars oscillating between $100-$102 (max 2% rally)
        - Never reach 3% threshold

        Expected:
        - AR not detected (returns None)
        - Timeout message logged
        """
        # Prior bar
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        # SC bar
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        bars = [prior_bar, sc_bar]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=prior_bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=sc_bar,
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.55"),
                effort_result=EffortResult.CLIMACTIC,
            ),
        ]

        # Add 10 bars with weak rally (max 2%)
        from datetime import timedelta
        for i in range(10):
            bar = OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc) + timedelta(days=i),
                open=Decimal("100.50"),
                high=Decimal("102.00"),  # Only 2% rally
                low=Decimal("100.00"),
                close=Decimal("101.50"),
                volume=55000000,
                spread=Decimal("2.00"),
            )
            bars.append(bar)
            volume_analysis_list.append(
                VolumeAnalysis(
                    bar=bar,
                    volume_ratio=Decimal("1.1"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.75"),
                    effort_result=EffortResult.NORMAL,
                )
            )

        # Detect SC first
        sc = detect_selling_climax(bars, volume_analysis_list)
        assert sc is not None

        # Execute AR detection
        result = detect_automatic_rally(bars, sc, volume_analysis_list)

        # Assert
        assert result is None, "AR should not be detected (timeout)"

    def test_ar_volume_profile_high(self):
        """
        Test AR with HIGH volume profile (volume_ratio >= 1.2).

        AC 4: Volume on rally can be normal or high.

        Setup:
        - SC low $100
        - AR bar: high $103.50 (3.5% rally), volume_ratio 1.5 (high volume)

        Expected:
        - ar.volume_profile == "HIGH"
        - Interpretation: Strong demand absorption
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
            open=Decimal("103.00"),
            high=Decimal("103.50"),  # 3.5% rally
            low=Decimal("102.00"),
            close=Decimal("103.20"),
            volume=75000000,  # 1.5x volume (HIGH)
            spread=Decimal("1.50"),
        )

        bars = [prior_bar, sc_bar, ar_bar]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=prior_bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=sc_bar,
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.55"),
                effort_result=EffortResult.CLIMACTIC,
            ),
            VolumeAnalysis(
                bar=ar_bar,
                volume_ratio=Decimal("1.5"),  # HIGH volume
                spread_ratio=Decimal("0.75"),
                close_position=Decimal("0.80"),
                effort_result=EffortResult.NORMAL,
            ),
        ]

        sc = detect_selling_climax(bars, volume_analysis_list)
        result = detect_automatic_rally(bars, sc, volume_analysis_list)

        assert result is not None
        assert result.volume_profile == "HIGH"

    def test_ar_volume_profile_normal(self):
        """
        Test AR with NORMAL volume profile (volume_ratio < 1.2).

        AC 4: Volume on rally can be normal or high.

        Setup:
        - SC low $100
        - AR bar: high $103.50 (3.5% rally), volume_ratio 0.8 (normal volume)

        Expected:
        - ar.volume_profile == "NORMAL"
        - Interpretation: Weak relief rally
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
            open=Decimal("103.00"),
            high=Decimal("103.50"),
            low=Decimal("102.00"),
            close=Decimal("103.20"),
            volume=40000000,  # 0.8x volume (NORMAL)
            spread=Decimal("1.50"),
        )

        bars = [prior_bar, sc_bar, ar_bar]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=prior_bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            ),
            VolumeAnalysis(
                bar=sc_bar,
                volume_ratio=Decimal("2.5"),
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.55"),
                effort_result=EffortResult.CLIMACTIC,
            ),
            VolumeAnalysis(
                bar=ar_bar,
                volume_ratio=Decimal("0.8"),  # NORMAL volume
                spread_ratio=Decimal("0.75"),
                close_position=Decimal("0.80"),
                effort_result=EffortResult.NORMAL,
            ),
        ]

        sc = detect_selling_climax(bars, volume_analysis_list)
        result = detect_automatic_rally(bars, sc, volume_analysis_list)

        assert result is not None
        assert result.volume_profile == "NORMAL"

    def test_ar_within_ideal_window(self):
        """
        Test AR within ideal 5-bar window.

        AC 2: AR occurs within 5 bars after SC (ideal).

        Setup:
        - SC at index 1
        - AR at index 4 (3 bars after SC)

        Expected:
        - ar.bars_after_sc == 3
        - Log message: "AR within ideal 5-bar window"
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        # Bar 1 after SC
        bar1 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
            open=Decimal("103.00"),
            high=Decimal("102.00"),
            low=Decimal("101.00"),
            close=Decimal("101.50"),
            volume=55000000,
            spread=Decimal("1.00"),
        )

        # Bar 2 after SC
        bar2 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 4, tzinfo=timezone.utc),
            open=Decimal("101.50"),
            high=Decimal("102.50"),
            low=Decimal("101.00"),
            close=Decimal("102.00"),
            volume=60000000,
            spread=Decimal("1.50"),
        )

        # Bar 3 after SC (AR peak)
        bar3 = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 5, tzinfo=timezone.utc),
            open=Decimal("102.00"),
            high=Decimal("103.20"),  # 3.2% rally
            low=Decimal("101.80"),
            close=Decimal("103.00"),
            volume=65000000,
            spread=Decimal("1.40"),
        )

        bars = [prior_bar, sc_bar, bar1, bar2, bar3]
        volume_analysis_list = [
            VolumeAnalysis(bar=prior_bar, volume_ratio=Decimal("1.0"), spread_ratio=Decimal("1.0"), close_position=Decimal("0.75"), effort_result=EffortResult.NORMAL),
            VolumeAnalysis(bar=sc_bar, volume_ratio=Decimal("2.5"), spread_ratio=Decimal("1.8"), close_position=Decimal("0.55"), effort_result=EffortResult.CLIMACTIC),
            VolumeAnalysis(bar=bar1, volume_ratio=Decimal("1.1"), spread_ratio=Decimal("0.5"), close_position=Decimal("0.50"), effort_result=EffortResult.NORMAL),
            VolumeAnalysis(bar=bar2, volume_ratio=Decimal("1.2"), spread_ratio=Decimal("0.75"), close_position=Decimal("0.67"), effort_result=EffortResult.NORMAL),
            VolumeAnalysis(bar=bar3, volume_ratio=Decimal("1.3"), spread_ratio=Decimal("0.7"), close_position=Decimal("0.86"), effort_result=EffortResult.NORMAL),
        ]

        sc = detect_selling_climax(bars, volume_analysis_list)
        result = detect_automatic_rally(bars, sc, volume_analysis_list)

        assert result is not None
        assert result.bars_after_sc == 3

    def test_phase_a_confirmed(self):
        """
        Test Phase A confirmation when both SC and AR present.

        AC 7: Phase A confirmation requires SC + AR.

        Setup:
        - SC detected
        - AR detected (3.5% rally, 1 bar after SC)

        Expected:
        - is_phase_a_confirmed(sc, ar) returns True
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
            open=Decimal("103.00"),
            high=Decimal("103.50"),
            low=Decimal("102.00"),
            close=Decimal("103.20"),
            volume=65000000,
            spread=Decimal("1.50"),
        )

        bars = [prior_bar, sc_bar, ar_bar]
        volume_analysis_list = [
            VolumeAnalysis(bar=prior_bar, volume_ratio=Decimal("1.0"), spread_ratio=Decimal("1.0"), close_position=Decimal("0.75"), effort_result=EffortResult.NORMAL),
            VolumeAnalysis(bar=sc_bar, volume_ratio=Decimal("2.5"), spread_ratio=Decimal("1.8"), close_position=Decimal("0.55"), effort_result=EffortResult.CLIMACTIC),
            VolumeAnalysis(bar=ar_bar, volume_ratio=Decimal("1.3"), spread_ratio=Decimal("0.75"), close_position=Decimal("0.80"), effort_result=EffortResult.NORMAL),
        ]

        sc = detect_selling_climax(bars, volume_analysis_list)
        ar = detect_automatic_rally(bars, sc, volume_analysis_list)

        # Test Phase A confirmation
        assert is_phase_a_confirmed(sc, ar) == True

    def test_phase_a_not_confirmed_missing_ar(self):
        """
        Test Phase A not confirmed when AR missing.

        AC 7: Phase A requires both SC and AR.

        Setup:
        - SC detected
        - AR = None (no rally)

        Expected:
        - is_phase_a_confirmed(sc, None) returns False
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        bars = [prior_bar, sc_bar]
        volume_analysis_list = [
            VolumeAnalysis(bar=prior_bar, volume_ratio=Decimal("1.0"), spread_ratio=Decimal("1.0"), close_position=Decimal("0.75"), effort_result=EffortResult.NORMAL),
            VolumeAnalysis(bar=sc_bar, volume_ratio=Decimal("2.5"), spread_ratio=Decimal("1.8"), close_position=Decimal("0.55"), effort_result=EffortResult.CLIMACTIC),
        ]

        sc = detect_selling_climax(bars, volume_analysis_list)

        # Test Phase A not confirmed
        assert is_phase_a_confirmed(sc, None) == False

    def test_ar_sc_at_end_no_bars_after(self):
        """
        Test AR detection when SC is last bar (no bars after).

        AC: Edge case - SC as last bar should return None.

        Setup:
        - SC at last position in bars list

        Expected:
        - AR not detected (returns None)
        - Log: "SC is last bar, no bars for AR detection"
        """
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("2.00"),
        )

        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),
            close=Decimal("103.00"),
            volume=125000000,
            spread=Decimal("5.50"),
        )

        bars = [prior_bar, sc_bar]
        volume_analysis_list = [
            VolumeAnalysis(bar=prior_bar, volume_ratio=Decimal("1.0"), spread_ratio=Decimal("1.0"), close_position=Decimal("0.75"), effort_result=EffortResult.NORMAL),
            VolumeAnalysis(bar=sc_bar, volume_ratio=Decimal("2.5"), spread_ratio=Decimal("1.8"), close_position=Decimal("0.55"), effort_result=EffortResult.CLIMACTIC),
        ]

        sc = detect_selling_climax(bars, volume_analysis_list)
        result = detect_automatic_rally(bars, sc, volume_analysis_list)

        assert result is None
