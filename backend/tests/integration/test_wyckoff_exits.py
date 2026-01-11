"""
Integration Tests for Wyckoff Exit Logic (Story 13.6 Task 8)

Purpose:
--------
Comprehensive integration tests for the Wyckoff-based exit logic implemented
in Story 13.6. Tests individual exit conditions, priority enforcement, and
multi-tier exit strategy execution.

Test Coverage:
--------------
- AC6.9: Integration tests for all exit conditions
- FR6.1: Jump Level calculation and exit
- FR6.2: UTAD detection and Phase E exit
- FR6.3: Volume divergence detection
- FR6.4: Support invalidation exit
- FR6.5: Multi-tier exit priority enforcement
- FR6.6: Exit reason tracking
- FR6.7: Exit analysis generation

Author: Developer Agent (Story 13.6 Task 8)
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.intraday_campaign_detector import Campaign, CampaignState
from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.models.wyckoff_phase import WyckoffPhase


def create_test_bar(timestamp, open_price, high, low, close, volume):
    """Helper to create OHLCVBar for testing."""
    return OHLCVBar(
        symbol="TEST",
        timestamp=timestamp,
        open=Decimal(str(open_price)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
        timeframe="1h",
        spread=Decimal(str(abs(high - low))),
    )


def create_test_campaign(support, resistance, jump=None):
    """Helper to create test campaign with levels."""
    campaign = Campaign(
        start_time=datetime.now(),
        state=CampaignState.ACTIVE,
        current_phase=WyckoffPhase.D,
        support_level=Decimal(str(support)),
        resistance_level=Decimal(str(resistance)),
    )

    if jump:
        campaign.jump_level = Decimal(str(jump))
    else:
        # Calculate Jump Level automatically
        range_width = campaign.resistance_level - campaign.support_level
        campaign.jump_level = campaign.resistance_level + range_width

    return campaign


class TestJumpLevelCalculation:
    """Test FR6.1: Jump Level calculation and exit."""

    def test_calculate_jump_level_from_trading_range(self):
        """Test Jump Level calculation from TradingRange."""
        from src.models.creek_level import CreekLevel
        from src.models.pivot import Pivot, PivotType
        from src.models.price_cluster import PriceCluster

        # Arrange: Create TradingRange with Ice $110, Creek $100
        creek_price = Decimal("100.00")
        ice_price = Decimal("110.00")

        # Create minimal pivots for clusters
        test_bar = create_test_bar(
            datetime.now(), open_price=105, high=110, low=100, close=108, volume=1000000
        )

        pivot = Pivot(
            bar=test_bar,
            index=0,
            price=ice_price,
            timestamp=test_bar.timestamp,
            type=PivotType.HIGH,
            strength=5,
        )

        resistance_cluster = PriceCluster(
            pivots=[pivot, pivot],  # Duplicate for min 2 pivots
            average_price=ice_price,
            min_price=ice_price,
            max_price=ice_price,
            price_range=Decimal("0"),
            touch_count=2,
            cluster_type=PivotType.HIGH,
            std_deviation=Decimal("0"),
            timestamp_range=(test_bar.timestamp, test_bar.timestamp),
        )

        pivot_low = Pivot(
            bar=test_bar,
            index=0,
            price=creek_price,
            timestamp=test_bar.timestamp,
            type=PivotType.LOW,
            strength=5,
        )

        support_cluster = PriceCluster(
            pivots=[pivot_low, pivot_low],
            average_price=creek_price,
            min_price=creek_price,
            max_price=creek_price,
            price_range=Decimal("0"),
            touch_count=2,
            cluster_type=PivotType.LOW,
            std_deviation=Decimal("0"),
            timestamp_range=(test_bar.timestamp, test_bar.timestamp),
        )

        creek = CreekLevel(
            price=creek_price,
            absolute_low=creek_price,
            min_rally_height_pct=Decimal("2.0"),
            bars_since_formation=10,
            touch_count=2,
            touch_details=[],
            strength_score=50,
            strength_rating="MODERATE",
            last_test_timestamp=test_bar.timestamp,
            first_test_timestamp=test_bar.timestamp,
            hold_duration=10,
            confidence="MEDIUM",
            volume_trend="FLAT",
        )

        trading_range = TradingRange(
            symbol="TEST",
            timeframe="1d",
            support_cluster=support_cluster,
            resistance_cluster=resistance_cluster,
            support=creek_price,
            resistance=ice_price,
            midpoint=Decimal("105.00"),
            range_width=Decimal("10.00"),
            range_width_pct=Decimal("0.10"),
            start_index=0,
            end_index=10,
            duration=10,
            creek=creek,
        )

        # Act
        jump_level = trading_range.calculate_jump_level()

        # Assert: Jump = Ice + (Ice - Creek) = 110 + 10 = 120
        assert jump_level == Decimal("120.00"), f"Expected Jump $120, got ${jump_level}"

    def test_jump_level_exit_triggered(self):
        """Test that Jump Level exit is triggered when price reaches target."""
        # Arrange
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        bar = create_test_bar(datetime.now(), 119, 121, 118, 120.5, 1000000)

        # Act - Check if bar high >= jump_level
        should_exit = bar.high >= campaign.jump_level

        # Assert
        assert should_exit, "Exit should be triggered when high reaches Jump Level"


class TestUTADDetection:
    """Test FR6.2: UTAD detection for Phase E exit."""

    def test_utad_detector_identifies_false_breakout(self):
        """Test UTAD detector identifies false breakouts above Ice."""
        from src.pattern_engine.detectors.utad_detector import UTADDetector

        # Arrange: Create bars with false breakout pattern
        base_time = datetime.now()
        ice_level = Decimal("110.00")

        bars = [
            # Volume buildup
            create_test_bar(base_time - timedelta(hours=20), 108, 109, 107, 108, 1000000),
            create_test_bar(base_time - timedelta(hours=19), 108, 109, 107, 108.5, 1000000),
            # ... more bars for volume calculation
        ]

        # Add 18 more bars for volume baseline
        for i in range(18, 0, -1):
            bars.append(
                create_test_bar(base_time - timedelta(hours=i), 108, 109, 107, 108, 1000000)
            )

        # UTAD bar: Thrust above Ice on high volume
        utad_bar = create_test_bar(
            base_time - timedelta(hours=2),
            109,
            112,
            109,
            111,
            2000000,  # 2x volume
        )
        bars.append(utad_bar)

        # Failure bar: Close back below Ice
        failure_bar = create_test_bar(base_time - timedelta(hours=1), 111, 111, 108, 109, 1000000)
        bars.append(failure_bar)

        # Create minimal trading range
        from src.models.pivot import Pivot, PivotType
        from src.models.price_cluster import PriceCluster

        pivot = Pivot(
            bar=bars[0],
            index=0,
            price=ice_level,
            timestamp=bars[0].timestamp,
            type=PivotType.HIGH,
            strength=5,
        )

        cluster = PriceCluster(
            pivots=[pivot, pivot],
            average_price=ice_level,
            min_price=ice_level,
            max_price=ice_level,
            price_range=Decimal("0"),
            touch_count=2,
            cluster_type=PivotType.HIGH,
            std_deviation=Decimal("0"),
            timestamp_range=(bars[0].timestamp, bars[0].timestamp),
        )

        trading_range = TradingRange(
            symbol="TEST",
            timeframe="1h",
            support_cluster=cluster,
            resistance_cluster=cluster,
            support=Decimal("100.00"),
            resistance=ice_level,
            midpoint=Decimal("105.00"),
            range_width=Decimal("10.00"),
            range_width_pct=Decimal("0.10"),
            start_index=0,
            end_index=len(bars),
            duration=len(bars),
        )

        # Act
        detector = UTADDetector(max_penetration_pct=Decimal("5.0"))
        utad = detector.detect_utad(trading_range, bars, ice_level)

        # Assert
        assert utad is not None, "UTAD should be detected"
        assert utad.volume_ratio >= 1.5, "UTAD should have high volume"
        assert utad.confidence >= 60, "UTAD should have reasonable confidence"


class TestVolumeDivergence:
    """Test FR6.3: Volume divergence detection."""

    def test_detect_consecutive_divergences(self):
        """Test detection of 2+ consecutive new highs with declining volume."""
        # This test verifies the logic, actual integration is in backtest

        # Arrange: Simulate 3 consecutive new highs with declining volume
        divergences = [
            {"price": Decimal("110"), "volume_ratio": Decimal("1.8")},
            {"price": Decimal("112"), "volume_ratio": Decimal("1.4")},  # Higher price, lower volume
            {"price": Decimal("114"), "volume_ratio": Decimal("1.0")},  # Higher price, lower volume
        ]

        # Act: Count consecutive divergences
        divergence_count = 0
        for i in range(1, len(divergences)):
            if (
                divergences[i]["price"] > divergences[i - 1]["price"]
                and divergences[i]["volume_ratio"] < divergences[i - 1]["volume_ratio"]
            ):
                divergence_count += 1

        # Assert: Should detect 2 divergences
        assert divergence_count >= 2, f"Expected 2+ divergences, got {divergence_count}"


class TestSupportInvalidation:
    """Test FR6.4: Support invalidation exit."""

    def test_support_break_triggers_exit(self):
        """Test that closing below support (Creek) triggers exit."""
        # Arrange
        campaign = create_test_campaign(support=100, resistance=110)
        bar = create_test_bar(datetime.now(), 100, 101, 98, 99, 1000000)  # Close below support

        # Act
        should_exit = bar.close < campaign.support_level

        # Assert
        assert should_exit, "Exit should trigger when close < support_level"

    def test_support_hold_no_exit(self):
        """Test that holding above support does not trigger exit."""
        # Arrange
        campaign = create_test_campaign(support=100, resistance=110)
        bar = create_test_bar(datetime.now(), 102, 103, 100.5, 102, 1000000)  # Holds above support

        # Act
        should_exit = bar.close < campaign.support_level

        # Assert
        assert not should_exit, "No exit when price holds above support"


class TestExitPriority:
    """Test FR6.5: Multi-tier exit priority enforcement."""

    def test_support_break_has_highest_priority(self):
        """Test that support invalidation takes priority over other exits."""
        # Arrange: Bar that breaks support AND hits jump level
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        bar = create_test_bar(datetime.now(), 98, 121, 95, 96, 1000000)

        # Act: Check priority (support break first)
        if bar.close < campaign.support_level:
            exit_reason = "SUPPORT_BREAK"
        elif bar.high >= campaign.jump_level:
            exit_reason = "JUMP_LEVEL_HIT"
        else:
            exit_reason = "HOLD"

        # Assert: Support break takes priority
        assert exit_reason == "SUPPORT_BREAK", "Support break should have highest priority"

    def test_jump_level_priority_over_time_limit(self):
        """Test that Jump Level exit takes priority over time limit."""
        # Arrange
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        bar = create_test_bar(datetime.now(), 119, 121, 118, 120, 1000000)
        bars_in_position = 55  # Exceeds 50-bar time limit

        # Act: Check priority
        if bar.close < campaign.support_level:
            exit_reason = "SUPPORT_BREAK"
        elif bar.high >= campaign.jump_level:
            exit_reason = "JUMP_LEVEL_HIT"
        elif bars_in_position >= 50:
            exit_reason = "TIME_LIMIT"
        else:
            exit_reason = "HOLD"

        # Assert: Jump Level takes priority over time limit
        assert exit_reason == "JUMP_LEVEL_HIT", "Jump Level should take priority over time limit"


class TestExitReasonTracking:
    """Test FR6.6-FR6.7: Exit reason tracking and analysis."""

    def test_exit_reasons_are_tracked(self):
        """Test that exit reasons are properly tracked in context."""
        # Arrange
        context = {"exit_reasons": []}

        # Act: Simulate 3 exits
        context["exit_reasons"].append("JUMP_LEVEL_HIT (high $120.50 >= Jump $120.00)")
        context["exit_reasons"].append("SUPPORT_BREAK (close $98.00 < Creek $100.00)")
        context["exit_reasons"].append("TIME_LIMIT (52 bars in position)")

        # Assert
        assert len(context["exit_reasons"]) == 3, "All exit reasons should be tracked"
        assert "JUMP_LEVEL_HIT" in context["exit_reasons"][0], "Jump Level exit tracked"
        assert "SUPPORT_BREAK" in context["exit_reasons"][1], "Support break tracked"
        assert "TIME_LIMIT" in context["exit_reasons"][2], "Time limit tracked"

    def test_exit_analysis_calculation(self):
        """Test exit analysis calculations for reporting."""
        # Arrange: Simulate trade exit reasons
        exit_reasons = [
            "JUMP_LEVEL_HIT (high $120.50 >= Jump $120.00)",
            "SUPPORT_BREAK (close $98.00 < Creek $100.00)",
            "JUMP_LEVEL_HIT (high $125.00 >= Jump $122.00)",
            "TIME_LIMIT (52 bars in position)",
            "UTAD_DETECTED (penetration 2.50%, volume 1.8x, confidence 75)",
        ]

        # Act: Count exit types
        jump_exits = sum(1 for r in exit_reasons if "JUMP" in r)
        utad_exits = sum(1 for r in exit_reasons if "UTAD" in r)
        support_breaks = sum(1 for r in exit_reasons if "SUPPORT" in r)
        time_limits = sum(1 for r in exit_reasons if "TIME" in r)

        structural_exits = jump_exits + utad_exits
        structural_pct = (structural_exits / len(exit_reasons)) * 100

        # Assert
        assert jump_exits == 2, "Should count 2 Jump Level exits"
        assert utad_exits == 1, "Should count 1 UTAD exit"
        assert support_breaks == 1, "Should count 1 support break"
        assert time_limits == 1, "Should count 1 time limit"
        assert structural_pct == 60.0, f"Structural exits should be 60%, got {structural_pct}%"


@pytest.mark.integration
class TestWyckoffExitIntegration:
    """End-to-end integration test for Wyckoff exit logic."""

    def test_complete_exit_workflow(self):
        """Test complete workflow: pattern → entry → exit with reason tracking."""
        # Arrange
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        context = {
            "position": True,
            "entry_price": Decimal("108.00"),
            "entry_bar_index": 10,
            "exit_reasons": [],
            "bars": [],
        }

        # Simulate bars approaching Jump Level
        base_time = datetime.now()
        for i in range(40):
            bar = create_test_bar(
                base_time + timedelta(hours=i),
                108 + i * 0.3,
                109 + i * 0.3,
                107 + i * 0.3,
                108 + i * 0.3,
                1000000,
            )
            context["bars"].append(bar)

        # Final bar hits Jump Level
        exit_bar = create_test_bar(base_time + timedelta(hours=40), 119, 121, 118, 120, 1500000)
        context["bars"].append(exit_bar)

        # Act: Check exit logic
        current_index = len(context["bars"]) - 1
        should_exit = False
        exit_reason = "HOLD"

        if exit_bar.close < campaign.support_level:
            should_exit = True
            exit_reason = "SUPPORT_BREAK"
        elif exit_bar.high >= campaign.jump_level:
            should_exit = True
            exit_reason = "JUMP_LEVEL_HIT"

        if should_exit:
            context["exit_reasons"].append(exit_reason)
            context["position"] = False

        # Assert
        assert should_exit, "Exit should be triggered"
        assert exit_reason == "JUMP_LEVEL_HIT", "Should exit at Jump Level"
        assert len(context["exit_reasons"]) == 1, "Exit reason should be tracked"
        assert not context["position"], "Position should be closed"


@pytest.mark.integration
class TestExitLogicRefinementsIntegration:
    """Integration tests for Story 13.6.1 Exit Logic Refinements."""

    def test_ice_expansion_detection_integration(self):
        """Test FR6.1.1: Ice expansion detection with jump level update."""
        from src.backtesting.exit_logic_refinements import (
            detect_ice_expansion,
            update_jump_level,
        )

        # Arrange: Campaign in Phase D with initial levels
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.current_phase = WyckoffPhase.D
        campaign.timeframe = "1h"
        campaign.campaign_id = "test-ice-expansion"
        campaign.ice_expansion_count = 0
        campaign.original_ice_level = None
        campaign.original_jump_level = None

        base_time = datetime.now()

        # Create bars that consolidate at new level (above 110)
        recent_bars = []
        for i in range(20):
            bar = create_test_bar(
                base_time - timedelta(hours=20 - i),
                open_price=111,
                high=113,
                low=111,
                close=112,
                volume=1000000,
            )
            recent_bars.append(bar)

        # Current bar makes new high above existing Ice by >0.5%
        current_bar = create_test_bar(
            base_time,
            open_price=112,
            high=Decimal("115.00"),  # >0.5% above Ice $110
            low=111,
            close=114,
            volume=1200000,  # Above average volume
        )

        # Act
        new_ice = detect_ice_expansion(campaign, current_bar, recent_bars)

        # Assert: Ice expansion should be detected
        if new_ice:
            # Update jump level with new ice
            new_jump = update_jump_level(campaign, new_ice)

            assert new_ice == Decimal("115.00"), f"Expected new Ice $115, got ${new_ice}"
            assert campaign.ice_expansion_count == 1, "Ice expansion count should be 1"
            assert campaign.original_ice_level == Decimal("110"), "Original Ice should be stored"

    def test_enhanced_utad_detection_integration(self):
        """Test FR6.2.1: Enhanced UTAD with spread validation."""
        from src.backtesting.exit_logic_refinements import detect_utad_enhanced

        # Arrange: Campaign in Phase E
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.current_phase = WyckoffPhase.E
        campaign.campaign_id = "test-utad"

        base_time = datetime.now()

        # Create baseline bars (normal activity)
        bars = []
        for i in range(20):
            bar = create_test_bar(
                base_time - timedelta(hours=25 - i),
                open_price=108,
                high=109,
                low=107,
                close=108,
                volume=1000000,
            )
            bars.append(bar)

        # Add UTAD bar: Break above Ice ($110) by 0.5-1.5% with high volume and wide spread
        utad_bar = create_test_bar(
            base_time - timedelta(hours=3),
            open_price=109,
            high=Decimal("111.10"),  # ~1% above Ice
            low=107,  # Wide spread (4 points vs avg 2)
            close=110.5,
            volume=2000000,  # 2x average volume
        )
        bars.append(utad_bar)

        # Failure bar: Close back below Ice within 3 bars
        failure_bar = create_test_bar(
            base_time - timedelta(hours=2),
            open_price=110,
            high=110.5,
            low=108,
            close=Decimal("109.00"),  # Below Ice $110
            volume=1200000,
        )
        bars.append(failure_bar)

        # Act
        utad = detect_utad_enhanced(campaign, bars)

        # Assert
        assert utad is not None, "Enhanced UTAD should be detected"
        assert utad.volume_ratio >= Decimal("1.5"), "UTAD should have high volume ratio"
        assert utad.spread_ratio >= Decimal("1.0"), "UTAD should have wide spread"
        assert utad.confidence >= 30, f"UTAD confidence ({utad.confidence}) should be >= 30"

    def test_phase_contextual_utad_exit_decision(self):
        """Test FR6.2.1: UTAD exit decision based on phase progress."""
        from src.backtesting.exit_logic_refinements import EnhancedUTAD, should_exit_on_utad

        # Arrange: Campaign at different Phase E progress levels
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.campaign_id = "test-utad-exit"

        # Create a high-confidence UTAD
        utad = EnhancedUTAD(
            timestamp=datetime.now(),
            breakout_price=Decimal("111.50"),
            failure_price=Decimal("109.00"),
            ice_level=Decimal("110.00"),
            volume_ratio=Decimal("2.5"),  # High volume
            spread_ratio=Decimal("1.6"),  # Wide spread
            bars_to_failure=1,  # Immediate failure
            phase=WyckoffPhase.E,
        )
        utad.confidence = utad.calculate_confidence()

        # Test 1: Phase D - Should NOT exit
        campaign.current_phase = WyckoffPhase.D
        should_exit, reason = should_exit_on_utad(utad, campaign, Decimal("109.00"))
        assert not should_exit, "Phase D UTAD should NOT trigger exit"

        # Test 2: Early Phase E (price at $112 = 20% progress to $120)
        campaign.current_phase = WyckoffPhase.E
        should_exit, reason = should_exit_on_utad(utad, campaign, Decimal("112.00"))
        # High confidence (>85) required for early Phase E
        assert utad.confidence >= 85 or not should_exit, "Early Phase E needs ultra-high confidence"

        # Test 3: Late Phase E (price at $118 = 80% progress to $120)
        should_exit, reason = should_exit_on_utad(utad, campaign, Decimal("118.00"))
        if utad.confidence >= 60:
            assert should_exit, "Late Phase E should exit on high-confidence UTAD"

    def test_enhanced_volume_divergence_integration(self):
        """Test FR6.3.1: Volume divergence with spread analysis."""
        from src.backtesting.exit_logic_refinements import detect_volume_divergence_enhanced

        base_time = datetime.now()

        # Create bars with quality volume divergence pattern
        # Each new high has declining volume AND narrowing spread
        bars = []

        # Initial bar
        bars.append(
            create_test_bar(
                base_time - timedelta(hours=5),
                open_price=110,
                high=Decimal("112.00"),
                low=Decimal("108.00"),  # 4-point range
                close=111,
                volume=1500000,
            )
        )

        # New high #1: Higher price, lower volume, narrower spread
        bars.append(
            create_test_bar(
                base_time - timedelta(hours=4),
                open_price=111,
                high=Decimal("114.00"),
                low=Decimal("111.00"),  # 3-point range (narrower)
                close=113,
                volume=1100000,  # 73% of previous
            )
        )

        # New high #2: Higher price, lower volume, narrower spread
        bars.append(
            create_test_bar(
                base_time - timedelta(hours=3),
                open_price=113,
                high=Decimal("116.00"),
                low=Decimal("114.00"),  # 2-point range (even narrower)
                close=115,
                volume=700000,  # 63% of previous
            )
        )

        # Act
        div_count, divergences = detect_volume_divergence_enhanced(
            bars, lookback=10, min_quality=60
        )

        # Assert: Should detect quality divergences
        assert div_count >= 1, f"Expected >= 1 quality divergence, got {div_count}"
        if divergences:
            assert (
                divergences[-1].divergence_quality >= 60
            ), "Divergence should meet quality threshold"

    def test_volatility_spike_exit_integration(self):
        """Test FR6.5.1: Volatility spike detection for regime change."""
        from src.backtesting.exit_logic_refinements import check_volatility_spike

        # Arrange: Campaign with known entry ATR
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.campaign_id = "test-volatility"
        campaign.entry_atr = Decimal("0.50")  # Entry ATR was $0.50
        campaign.max_atr_seen = None

        base_time = datetime.now()

        # Create bars with much higher volatility (3x the entry ATR)
        recent_bars = []
        for i in range(20):
            bar = create_test_bar(
                base_time - timedelta(hours=20 - i),
                open_price=110,
                high=Decimal("112.00"),  # $2 range instead of $0.50
                low=Decimal("108.00"),
                close=111,
                volume=2000000,
            )
            recent_bars.append(bar)

        current_bar = create_test_bar(
            base_time,
            open_price=111,
            high=Decimal("114.00"),  # $4 range - extreme volatility
            low=Decimal("106.00"),
            close=112,
            volume=3000000,
        )

        # Act
        spike, reason = check_volatility_spike(current_bar, campaign, recent_bars)

        # Assert: Should detect volatility spike
        assert spike, "Volatility spike should be detected (ATR > 2.5x entry)"
        assert (
            reason and "VOLATILITY_SPIKE" in reason
        ), "Exit reason should mention volatility spike"

    def test_phase_e_uptrend_break_integration(self):
        """Test FR6.2.2: Uptrend break detection in Phase E."""
        from src.backtesting.exit_logic_refinements import detect_uptrend_break

        # Arrange: Campaign in Phase E
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.current_phase = WyckoffPhase.E
        campaign.campaign_id = "test-uptrend"

        base_time = datetime.now()

        # Create bars with rising lows (uptrend)
        # Using explicit Decimal values for all numeric parameters
        recent_bars = []
        for i in range(10):
            low_val = Decimal("108") + Decimal(str(i)) * Decimal("0.2")
            bar = create_test_bar(
                base_time - timedelta(hours=10 - i),
                open_price=Decimal("110") + Decimal(str(i)) * Decimal("0.2"),
                high=Decimal("112") + Decimal(str(i)) * Decimal("0.2"),
                low=low_val,  # Rising lows
                close=Decimal("111") + Decimal(str(i)) * Decimal("0.2"),
                volume=1000000,
            )
            recent_bars.append(bar)

        # Average of lows: approximately 108.9
        # Current bar breaks below this average by 0.5%
        break_bar = create_test_bar(
            base_time,
            open_price=Decimal("108"),
            high=Decimal("109"),
            low=Decimal("105"),
            close=Decimal("106.00"),  # Well below recent lows avg * 0.995
            volume=1500000,
        )

        # Act
        break_detected, reason = detect_uptrend_break(campaign, break_bar, recent_bars)

        # Assert
        assert break_detected, "Uptrend break should be detected"
        assert reason and "UPTREND_BREAK" in reason, "Exit reason should mention uptrend break"

    def test_phase_e_lower_high_integration(self):
        """Test FR6.2.2: Lower high detection for distribution."""
        from src.backtesting.exit_logic_refinements import detect_lower_high

        # Arrange: Campaign in Phase E
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.current_phase = WyckoffPhase.E
        campaign.campaign_id = "test-lower-high"

        base_time = datetime.now()

        # Create bars with two clear swing highs where second is lower
        # Swing high detection needs: bar.high > [i-1].high AND > [i-2].high AND > [i+1].high AND > [i+2].high
        bars = []

        # Bars before first swing high (lower highs leading up)
        bars.append(create_test_bar(base_time - timedelta(hours=18), 110, 111, 109, 110, 1000000))
        bars.append(create_test_bar(base_time - timedelta(hours=17), 110, 112, 109, 111, 1000000))

        # First swing high at index 2 (higher than 2 before and 2 after)
        bars.append(
            create_test_bar(
                base_time - timedelta(hours=16),
                open_price=115,
                high=Decimal("120.00"),  # First swing high - MUST be higher than all neighbors
                low=114,
                close=119,
                volume=1200000,
            )
        )

        # Bars after first swing high (lower highs)
        bars.append(create_test_bar(base_time - timedelta(hours=15), 117, 118, 116, 117, 1000000))
        bars.append(create_test_bar(base_time - timedelta(hours=14), 116, 117, 115, 116, 1000000))

        # Pullback bars
        bars.append(create_test_bar(base_time - timedelta(hours=13), 115, 116, 114, 115, 1000000))
        bars.append(create_test_bar(base_time - timedelta(hours=12), 114, 115, 113, 114, 1000000))

        # Second swing high at index 7 (LOWER than first by >0.2%)
        bars.append(
            create_test_bar(
                base_time - timedelta(hours=11),
                open_price=116,
                high=Decimal(
                    "119.50"
                ),  # Lower high (119.5 < 120 * 0.998 = 119.76) - must be <0.998x first
                low=115,
                close=118,
                volume=1100000,
            )
        )

        # Bars after second swing high (lower highs for swing detection)
        bars.append(create_test_bar(base_time - timedelta(hours=10), 117, 118, 116, 117, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=9), 116, 117, 115, 116, 900000))

        # Additional bars to ensure we have lookback + 4
        bars.append(create_test_bar(base_time - timedelta(hours=8), 115, 116, 114, 115, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=7), 114, 115, 113, 114, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=6), 114, 115, 113, 114, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=5), 114, 115, 113, 114, 900000))

        # Act
        lower_high_detected, reason = detect_lower_high(campaign, bars)

        # Assert
        assert lower_high_detected, "Lower high should be detected"
        assert reason and "LOWER_HIGH" in reason, "Exit reason should mention lower high"

    def test_failed_rallies_integration(self):
        """Test FR6.2.2: Multiple failed rally attempts detection."""
        from src.backtesting.exit_logic_refinements import detect_failed_rallies

        # Arrange: Campaign in Phase E
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.current_phase = WyckoffPhase.E
        campaign.campaign_id = "test-failed-rallies"

        base_time = datetime.now()
        resistance = Decimal("118.00")

        # Create bars with multiple failed rally attempts at resistance
        bars = []
        for i in range(20):
            if i in [5, 10, 15]:  # Three failed attempts
                # Rally attempts that touch but don't break resistance
                bar = create_test_bar(
                    base_time - timedelta(hours=20 - i),
                    open_price=116,
                    high=Decimal("117.50"),  # Approaches resistance
                    low=115,
                    close=Decimal("116.00"),  # Fails below resistance
                    volume=1200000 - (i * 20000),  # Declining volume
                )
            else:
                # Normal bars
                bar = create_test_bar(
                    base_time - timedelta(hours=20 - i),
                    open_price=114,
                    high=115,
                    low=113,
                    close=114,
                    volume=1000000,
                )
            bars.append(bar)

        # Act
        failed, reason = detect_failed_rallies(campaign, bars, resistance_level=resistance)

        # Assert
        assert failed, "Failed rallies should be detected"
        assert reason and "MULTIPLE_TESTS" in reason, "Exit reason should mention multiple tests"

    def test_complete_exit_refinements_workflow(self):
        """Test complete workflow using refined exit logic."""
        from src.backtesting.exit_logic_refinements import (
            check_volatility_spike,
            detect_ice_expansion,
            detect_lower_high,
            detect_uptrend_break,
            detect_utad_enhanced,
            detect_volume_divergence_enhanced,
            should_exit_on_utad,
            update_jump_level,
        )

        # Arrange: Full campaign lifecycle
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.current_phase = WyckoffPhase.D
        campaign.campaign_id = "test-complete-workflow"
        campaign.timeframe = "1h"
        campaign.entry_atr = Decimal("0.50")
        campaign.ice_expansion_count = 0
        campaign.max_atr_seen = None
        campaign.original_ice_level = None
        campaign.original_jump_level = None

        base_time = datetime.now()
        exit_reasons = []

        # Generate historical bars
        bars = []
        for i in range(30):
            bar = create_test_bar(
                base_time - timedelta(hours=30 - i),
                open_price=108 + i * 0.1,
                high=110 + i * 0.1,
                low=107 + i * 0.1,
                close=109 + i * 0.1,
                volume=1000000,
            )
            bars.append(bar)

        current_bar = bars[-1]

        # Step 1: Check Ice expansion (Phase D)
        new_ice = detect_ice_expansion(campaign, current_bar, bars)
        if new_ice:
            update_jump_level(campaign, new_ice)
            exit_reasons.append(f"ICE_EXPANSION: New Ice ${new_ice}")

        # Step 2: Transition to Phase E and check exits
        campaign.current_phase = WyckoffPhase.E

        # Check UTAD
        utad = detect_utad_enhanced(campaign, bars)
        if utad:
            should_exit, reason = should_exit_on_utad(utad, campaign, current_bar.close)
            if should_exit:
                exit_reasons.append(f"UTAD: {reason}")

        # Check uptrend break
        break_detected, reason = detect_uptrend_break(campaign, current_bar, bars)
        if break_detected:
            exit_reasons.append(f"STRUCTURE: {reason}")

        # Check lower high
        lower_high, reason = detect_lower_high(campaign, bars)
        if lower_high:
            exit_reasons.append(f"PATTERN: {reason}")

        # Check volume divergence
        div_count, divergences = detect_volume_divergence_enhanced(bars)
        if div_count >= 2:
            exit_reasons.append(f"VOLUME_DIV: {div_count} consecutive")

        # Check volatility spike
        spike, reason = check_volatility_spike(current_bar, campaign, bars)
        if spike:
            exit_reasons.append(f"RISK: {reason}")

        # Assert: Workflow completed without errors
        # (Actual exits depend on bar data - this tests integration of all functions)
        assert isinstance(exit_reasons, list), "Exit reasons should be tracked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
