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
from src.pattern_engine.phase_detector import detect_selling_climax


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
