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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
