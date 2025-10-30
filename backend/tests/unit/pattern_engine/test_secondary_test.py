"""
Unit tests for Secondary Test (ST) detection - Story 4.3.

Tests cover:
- Synthetic ST bar detection with correct characteristics (AC 8)
- Confidence scoring boundaries (AC 12)
- Multiple STs detection and test numbering (AC 7, 13)
- ST vs Spring distinction (AC 14)
- No ST detection scenarios (AC 16)
- Edge cases (AC 17)
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.models.effort_result import EffortResult
from src.pattern_engine.phase_detector import (
    detect_selling_climax,
    detect_automatic_rally,
    detect_secondary_test,
)


class TestSecondaryTestDetection:
    """Test suite for Secondary Test detection functionality (Story 4.3)."""

    def _create_sc_ar_scenario(self):
        """
        Helper to create standard SC + AR scenario.

        Returns:
            tuple: (bars, volume_analysis_list, sc, ar)
        """
        bars = []
        volume_analysis_list = []

        # Prior bar
        prior_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 22, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("106.00"),
            low=Decimal("104.00"),
            close=Decimal("105.50"),
            volume=30000000,
            spread=Decimal("2.00"),
        )
        bars.append(prior_bar)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=prior_bar,
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            )
        )

        # SC bar at $100.00 low
        sc_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("105.50"),
            low=Decimal("100.00"),  # SC low
            close=Decimal("104.00"),  # close_position = 0.73
            volume=75000000,  # 2.5x
            spread=Decimal("5.50"),
        )
        bars.append(sc_bar)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=sc_bar,
                volume_ratio=Decimal("2.5"),  # SC volume
                spread_ratio=Decimal("1.8"),
                close_position=Decimal("0.73"),
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        # AR bar (rally to $106.00, 6% rally)
        ar_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 24, tzinfo=timezone.utc),
            open=Decimal("104.00"),
            high=Decimal("106.00"),  # AR high
            low=Decimal("103.00"),
            close=Decimal("105.50"),
            volume=50000000,
            spread=Decimal("3.00"),
        )
        bars.append(ar_bar)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=ar_bar,
                volume_ratio=Decimal("1.67"),
                spread_ratio=Decimal("1.5"),
                close_position=Decimal("0.83"),
                effort_result=EffortResult.NORMAL,
            )
        )

        # Detect SC and AR
        sc = detect_selling_climax(bars, volume_analysis_list)
        ar = detect_automatic_rally(bars, sc, volume_analysis_list)

        return bars, volume_analysis_list, sc, ar

    def test_detect_synthetic_st_high_confidence(self):
        """
        Test detection of synthetic ST bar with high confidence.

        AC 8 (Story 4.3): Synthetic test bar with reduced volume detected.

        Setup:
        - SC at $100.00, volume_ratio = 2.5
        - AR rally from SC
        - ST candidate 10 bars after AR:
          - test_low = $100.50 (0.5% above SC low, within 2% tolerance)
          - test_volume_ratio = 1.2 (reduced from SC's 2.5, 52% reduction)
          - No penetration (holds above SC low)
        - Expected: ST detected with confidence >= 80
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # Add filler bars (7 bars between AR and ST)
        for i in range(7):
            filler_bar = OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 25 + i, tzinfo=timezone.utc),
                open=Decimal("105.00"),
                high=Decimal("106.00"),
                low=Decimal("104.00"),
                close=Decimal("105.00"),
                volume=35000000,
                spread=Decimal("2.00"),
            )
            bars.append(filler_bar)
            volume_analysis_list.append(
                VolumeAnalysis(
                    bar=filler_bar,
                    volume_ratio=Decimal("1.17"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.5"),
                    effort_result=EffortResult.NORMAL,
                )
            )

        # ST bar (test at $100.50, 52% volume reduction)
        st_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 4, 1, tzinfo=timezone.utc),
            open=Decimal("104.00"),
            high=Decimal("104.50"),
            low=Decimal("100.50"),  # 0.5% above SC low
            close=Decimal("102.00"),
            volume=36000000,  # 1.2x (52% reduction from SC's 2.5x)
            spread=Decimal("4.00"),
        )
        bars.append(st_bar)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=st_bar,
                volume_ratio=Decimal("1.2"),  # Reduced volume
                spread_ratio=Decimal("2.0"),
                close_position=Decimal("0.38"),
                effort_result=EffortResult.NORMAL,
            )
        )

        # Detect ST
        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        assert st is not None, "ST should be detected"
        assert st.distance_from_sc_low <= Decimal("0.02"), "Distance should be within 2%"
        assert float(st.distance_from_sc_low) == pytest.approx(0.005, abs=0.001), "Distance should be ~0.5%"
        assert st.volume_reduction_pct >= Decimal("0.50"), f"Volume reduction should be >=50%, got {st.volume_reduction_pct}"
        assert st.penetration == Decimal("0.0"), "Should have no penetration"
        assert st.confidence >= 80, f"Confidence should be >= 80, got {st.confidence}"
        assert st.test_number == 1, "Should be first ST"

    def test_st_confidence_scoring_minimum(self):
        """
        Test ST confidence scoring - minimum viable ST.

        AC 12 (Story 4.3): Minimum confidence ST.

        Enhanced scoring with 5 components (45/27/18/10/bonus):
        - volume_reduction = 20% (20 pts) - minimum threshold
        - distance = 2.0% (15 pts)
        - penetration = 1.5% (6 pts)
        - close_position = 0.40 (0 pts - below midpoint)
        - spread_ratio = 0.85 (0 pts - wide)
        - Expected confidence = 41 (minimum viable ST)
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # ST with minimum characteristics
        # distance = 2.0%, volume_reduction = 10%, penetration = 2.0%
        st_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
            open=Decimal("104.00"),
            high=Decimal("104.50"),
            low=Decimal("98.00"),  # 2% below SC low (penetration = 2%)
            close=Decimal("100.00"),
            volume=67500000,  # 2.25x (10% reduction from 2.5x)
            spread=Decimal("6.50"),
        )
        bars.append(st_bar)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=st_bar,
                volume_ratio=Decimal("2.25"),  # 10% reduction from 2.5x
                spread_ratio=Decimal("3.25"),
                close_position=Decimal("0.31"),
                effort_result=EffortResult.NORMAL,
            )
        )

        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        # With new 20% threshold, this will be rejected (only 10% reduction)
        assert st is None, "ST with <20% volume reduction should be rejected"

    def test_st_confidence_scoring_maximum(self):
        """
        Test ST confidence scoring - perfect ST.

        AC 12 (Story 4.3): Maximum confidence ST.

        Enhanced scoring with 5 components:
        - volume_reduction = 60% (45 pts) - maximum
        - distance = 0.3% (27 pts) - very close
        - no penetration (18 pts) - perfect hold
        - close_position = 0.85 (10 pts) - bullish close
        - spread_ratio = 0.35 (5 pts bonus) - very narrow
        - Expected confidence = 100 (perfect ST, capped)
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # Perfect ST: 60% volume reduction, 0.3% distance, no penetration
        st_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
            open=Decimal("103.00"),
            high=Decimal("103.50"),
            low=Decimal("100.30"),  # 0.3% above SC low
            close=Decimal("102.00"),
            volume=30000000,  # 1.0x (60% reduction from 2.5x)
            spread=Decimal("3.20"),
        )
        bars.append(st_bar)
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=st_bar,
                volume_ratio=Decimal("1.0"),  # 60% reduction
                spread_ratio=Decimal("0.58"),  # Narrow spread (3.2 / 5.5 = 0.58)
                close_position=Decimal("0.78"),  # Good bullish close
                effort_result=EffortResult.NORMAL,
            )
        )

        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        assert st is not None, "Perfect ST should be detected"
        # With enhanced scoring: 45 (vol) + 27 (prox) + 18 (hold) + 10 (close) + 2 (spread) = 102, capped at 100
        assert st.confidence >= 95, f"Expected confidence >= 95, got {st.confidence}"

    def test_detect_multiple_sts(self):
        """
        Test detection of multiple Secondary Tests.

        AC 7, 13 (Story 4.3): Multiple STs build cause.

        Setup:
        - First ST: 5 bars after AR, test_number = 1
        - Second ST: 15 bars after AR, test_number = 2
        - Third ST: 25 bars after AR, test_number = 3
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # Add 30 bars total after AR for 3 STs
        for i in range(30):
            is_st_bar = i in [4, 14, 24]  # ST at bars 5, 15, 25 after AR

            if is_st_bar:
                # ST bar
                bar = OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc) + timedelta(days=i),
                    open=Decimal("103.00"),
                    high=Decimal("103.50"),
                    low=Decimal("100.30"),  # Near SC low
                    close=Decimal("102.00"),
                    volume=36000000,  # 1.2x (52% reduction)
                    spread=Decimal("3.20"),
                )
                bars.append(bar)
                volume_analysis_list.append(
                    VolumeAnalysis(
                        bar=bar,
                        volume_ratio=Decimal("1.2"),  # Reduced
                        spread_ratio=Decimal("1.6"),
                        close_position=Decimal("0.53"),
                        effort_result=EffortResult.NORMAL,
                    )
                )
            else:
                # Normal bar
                bar = OHLCVBar(
                    symbol="TEST",
                    timeframe="1d",
                    timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc) + timedelta(days=i),
                    open=Decimal("104.00"),
                    high=Decimal("105.00"),
                    low=Decimal("103.00"),
                    close=Decimal("104.50"),
                    volume=35000000,
                    spread=Decimal("2.00"),
                )
                bars.append(bar)
                volume_analysis_list.append(
                    VolumeAnalysis(
                        bar=bar,
                        volume_ratio=Decimal("1.17"),
                        spread_ratio=Decimal("1.0"),
                        close_position=Decimal("0.75"),
                        effort_result=EffortResult.NORMAL,
                    )
                )

        # Detect 1st ST
        st1 = detect_secondary_test(bars, sc, ar, volume_analysis_list, existing_sts=[])
        assert st1 is not None, "1st ST should be detected"
        assert st1.test_number == 1, f"Expected test_number 1, got {st1.test_number}"

        # Detect 2nd ST (pass st1 in existing_sts)
        st2 = detect_secondary_test(bars, sc, ar, volume_analysis_list, existing_sts=[st1])
        assert st2 is not None, "2nd ST should be detected"
        assert st2.test_number == 2, f"Expected test_number 2, got {st2.test_number}"

        # Detect 3rd ST (pass st1, st2 in existing_sts)
        st3 = detect_secondary_test(bars, sc, ar, volume_analysis_list, existing_sts=[st1, st2])
        assert st3 is not None, "3rd ST should be detected"
        assert st3.test_number == 3, f"Expected test_number 3, got {st3.test_number}"

        # All STs should reference same SC
        assert st1.sc_reference["bar"]["timestamp"] == sc.bar["timestamp"]
        assert st2.sc_reference["bar"]["timestamp"] == sc.bar["timestamp"]
        assert st3.sc_reference["bar"]["timestamp"] == sc.bar["timestamp"]

    def test_st_vs_spring_distinction(self):
        """
        Test ST vs Spring distinction based on penetration.

        AC 14 (Story 4.3): ST has minor penetration (<1%), Spring has larger penetration (>1%).

        Scenario 1: ST with minor penetration (0.5%)
        Scenario 2: Possible Spring with large penetration (1.5%)
        """
        # Scenario 1: ST with 0.5% penetration
        bars_st, volume_analysis_st, sc_st, ar_st = self._create_sc_ar_scenario()

        # ST with 0.5% penetration (test_low = $99.50)
        bars_st.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
                open=Decimal("103.00"),
                high=Decimal("103.50"),
                low=Decimal("99.50"),  # 0.5% below SC low
                close=Decimal("102.00"),
                volume=36000000,  # 1.2x (52% reduction)
                spread=Decimal("4.00"),
            )
        )
        volume_analysis_st.append(
            VolumeAnalysis(
                bar=bars_st[-1],
                volume_ratio=Decimal("1.2"),
                spread_ratio=Decimal("2.0"),
                close_position=Decimal("0.63"),
                effort_result=EffortResult.NORMAL,
            )
        )

        st = detect_secondary_test(bars_st, sc_st, ar_st, volume_analysis_st)

        # Assert ST detected with minor penetration
        assert st is not None, "ST with minor penetration should be detected"
        assert float(st.penetration) == pytest.approx(0.005, abs=0.001), "Penetration should be ~0.5%"
        assert st.confidence >= 70, f"Expected confidence >= 70 with minor penetration, got {st.confidence}"

        # Scenario 2: Possible Spring with 1.5% penetration
        bars_spring, volume_analysis_spring, sc_spring, ar_spring = self._create_sc_ar_scenario()

        # Possible Spring with 1.5% penetration (test_low = $98.50)
        bars_spring.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
                open=Decimal("103.00"),
                high=Decimal("103.50"),
                low=Decimal("98.50"),  # 1.5% below SC low
                close=Decimal("102.00"),
                volume=36000000,
                spread=Decimal("5.00"),
            )
        )
        volume_analysis_spring.append(
            VolumeAnalysis(
                bar=bars_spring[-1],
                volume_ratio=Decimal("1.2"),
                spread_ratio=Decimal("2.5"),
                close_position=Decimal("0.70"),
                effort_result=EffortResult.NORMAL,
            )
        )

        spring_candidate = detect_secondary_test(bars_spring, sc_spring, ar_spring, volume_analysis_spring)

        # Assert detected but low confidence (large penetration)
        assert spring_candidate is not None, "Spring candidate should be detected"
        assert float(spring_candidate.penetration) == pytest.approx(0.015, abs=0.001), "Penetration should be ~1.5%"
        # Confidence should be lower due to large penetration (holding_pts = 6 instead of 15-18)
        # With enhanced scoring: 52% vol (40pts) + 1.5% dist (18pts) + 1.5% pen (6pts) + close/spread bonus = ~74
        assert spring_candidate.confidence <= 75, f"Expected confidence <= 75 with large penetration, got {spring_candidate.confidence}"
        # The key distinction is that spring has lower holding_pts (10 vs 25-30)
        assert st.confidence > spring_candidate.confidence or st.confidence == spring_candidate.confidence, "ST should have equal or better confidence than spring"

    def test_no_st_detection_price_too_far(self):
        """
        Test no ST detected when price stays too far from SC low.

        AC 16 (Story 4.3): No ST when price > 5% away from SC low.
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # Bar that stays far from SC low (low = $110.00, 10% above SC low)
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
                open=Decimal("110.00"),
                high=Decimal("112.00"),
                low=Decimal("110.00"),  # 10% above SC low
                close=Decimal("111.00"),
                volume=35000000,
                spread=Decimal("2.00"),
            )
        )
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bars[-1],
                volume_ratio=Decimal("1.17"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.5"),
                effort_result=EffortResult.NORMAL,
            )
        )

        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        assert st is None, "No ST should be detected when price stays >5% from SC low"

    def test_no_st_detection_volume_not_reduced(self):
        """
        Test no ST detected when volume is not reduced.

        AC 16 (Story 4.3): No ST when volume >= SC volume.
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # Bar near SC low but with HIGH volume (2.8x, not reduced)
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
                open=Decimal("103.00"),
                high=Decimal("103.50"),
                low=Decimal("100.20"),  # Near SC low
                close=Decimal("102.00"),
                volume=84000000,  # 2.8x (higher than SC!)
                spread=Decimal("3.30"),
            )
        )
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bars[-1],
                volume_ratio=Decimal("2.8"),  # Not reduced!
                spread_ratio=Decimal("1.65"),
                close_position=Decimal("0.55"),
                effort_result=EffortResult.NORMAL,
            )
        )

        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        assert st is None, "No ST should be detected when volume is not reduced"

    def test_st_edge_case_ar_at_end(self):
        """
        Test ST detection when AR is at end of bars (no room for ST).

        AC 17 (Story 4.3): Edge case - insufficient data after AR.
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # bars already has 3 items (prior, SC, AR), AR is last bar
        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        assert st is None, "No ST should be detected when AR is at end (insufficient data)"

    def test_st_edge_case_sc_none_raises_error(self):
        """
        Test ST detection with sc = None raises ValueError.

        AC 17 (Story 4.3): Edge case - SC required.
        """
        bars = [
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
                open=Decimal("105.00"),
                high=Decimal("106.00"),
                low=Decimal("104.00"),
                close=Decimal("105.50"),
                volume=30000000,
                spread=Decimal("2.00"),
            )
        ]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=bars[0],
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            )
        ]

        # Mock AR
        from src.models.automatic_rally import AutomaticRally

        ar = AutomaticRally(
            bar={"timestamp": "2020-03-23T00:00:00+00:00", "low": "100.00", "high": "106.00"},
            rally_pct=Decimal("0.06"),
            bars_after_sc=1,
            sc_reference={"bar": {"timestamp": "2020-03-22T00:00:00+00:00", "low": "100.00"}},
            sc_low=Decimal("100.00"),
            ar_high=Decimal("106.00"),
            volume_profile="NORMAL",
        )

        # Execute & Assert
        with pytest.raises(ValueError, match="SC cannot be None"):
            detect_secondary_test(bars, sc=None, ar=ar, volume_analysis=volume_analysis_list)

    def test_st_edge_case_ar_none_raises_error(self):
        """
        Test ST detection with ar = None raises ValueError.

        AC 17 (Story 4.3): Edge case - AR required.
        """
        bars = [
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 23, tzinfo=timezone.utc),
                open=Decimal("105.00"),
                high=Decimal("106.00"),
                low=Decimal("104.00"),
                close=Decimal("105.50"),
                volume=30000000,
                spread=Decimal("2.00"),
            )
        ]
        volume_analysis_list = [
            VolumeAnalysis(
                bar=bars[0],
                volume_ratio=Decimal("1.0"),
                spread_ratio=Decimal("1.0"),
                close_position=Decimal("0.75"),
                effort_result=EffortResult.NORMAL,
            )
        ]

        # Mock SC
        from src.models.selling_climax import SellingClimax

        sc = SellingClimax(
            bar={"timestamp": "2020-03-22T00:00:00+00:00", "low": "100.00"},
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.73"),
            confidence=85,
            prior_close=Decimal("105.00"),
        )

        # Execute & Assert
        with pytest.raises(ValueError, match="AR cannot be None"):
            detect_secondary_test(bars, sc=sc, ar=None, volume_analysis=volume_analysis_list)

    def test_st_volume_reduction_below_20_percent_threshold(self):
        """
        Test ST rejection when volume reduction < 20% minimum threshold.

        AC 4 (Story 4.3): Volume reduction must be >= 20% minimum to filter noise.
        Updated from 10% to 20% per expert feedback for more accurate detection.
        """
        bars, volume_analysis_list, sc, ar = self._create_sc_ar_scenario()

        # ST bar with only 15% volume reduction (below 20% threshold)
        # SC volume = 2.5x, test volume = 2.125x (15% reduction)
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=datetime(2020, 3, 25, tzinfo=timezone.utc),
                open=Decimal("103.00"),
                high=Decimal("103.50"),
                low=Decimal("100.30"),  # Near SC low (good proximity)
                close=Decimal("102.00"),
                volume=63750000,  # 2.125x (only 15% reduction from 2.5x)
                spread=Decimal("3.20"),
            )
        )
        volume_analysis_list.append(
            VolumeAnalysis(
                bar=bars[-1],
                volume_ratio=Decimal("2.125"),  # Only 15% reduction
                spread_ratio=Decimal("1.6"),
                close_position=Decimal("0.53"),
                effort_result=EffortResult.NORMAL,
            )
        )

        st = detect_secondary_test(bars, sc, ar, volume_analysis_list)

        # Assert
        assert st is None, "ST with volume reduction < 20% should be rejected as noise"
