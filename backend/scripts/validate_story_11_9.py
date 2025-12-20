#!/usr/bin/env python3
"""
Story 11.9 Validation Script

Validates that all 7 subtasks from Story 11.9 are working correctly:
- PivotDetector
- RangeQualityScorer
- LevelCalculator
- ZoneMapper
- UTAD Detector
- Quality Position Sizer
- Campaign State Machine

Usage:
    python backend/scripts/validate_story_11_9.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add backend to path (parent.parent for scripts/validate_story_11_9.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.container import OrchestratorContainer
from src.pattern_engine.campaign_manager import CampaignState, CampaignStateMachine
from src.pattern_engine.detectors.utad_detector import UTADDetector
from src.pattern_engine.level_calculator import LevelCalculator
from src.pattern_engine.pivot_detector import PivotDetector
from src.pattern_engine.position_sizer import QualityPositionSizer
from src.pattern_engine.range_quality import RangeQualityScorer
from src.pattern_engine.zone_mapper import ZoneMapper

logger = structlog.get_logger(__name__)


def create_sample_bars(count: int = 100) -> list[OHLCVBar]:
    """Create sample OHLCV bars for testing."""
    bars = []
    base_price = Decimal("100.0")
    base_time = datetime.now() - timedelta(days=count)

    for i in range(count):
        # Create price movement with pivots
        offset = Decimal(str(i % 10 - 5))  # Creates wave pattern
        price = base_price + offset

        bar = OHLCVBar(
            symbol="TEST",
            timestamp=base_time + timedelta(days=i),
            open=price,
            high=price + Decimal("1.0"),
            low=price - Decimal("1.0"),
            close=price + Decimal("0.5"),
            volume=1000000 + (i * 10000),
            timeframe="1d",
        )
        bars.append(bar)

    return bars


def create_sample_volume_analysis(bars: list[OHLCVBar]) -> list[VolumeAnalysis]:
    """Create sample volume analysis for testing."""
    analyses = []
    for i, bar in enumerate(bars):
        analysis = VolumeAnalysis(
            bar_index=i,
            timestamp=bar.timestamp,
            volume=bar.volume,
            volume_ma=1000000,
            volume_ratio=1.0,
            effort=50,
            result=50,
            classification="NEUTRAL",
            spread_pct=2.0,
            close_position=0.5,
        )
        analyses.append(analysis)
    return analyses


def create_sample_trading_range(bars: list[OHLCVBar]) -> TradingRange:
    """Create sample trading range for testing."""
    return TradingRange(
        range_id="test_range_1",
        symbol="TEST",
        timeframe="1d",
        start_index=20,
        end_index=80,
        duration=60,
        resistance=Decimal("105.0"),
        support=Decimal("95.0"),
        range_pct=Decimal("10.0"),
        resistance_touches=5,
        support_touches=5,
        quality_score=75,
    )


def validate_pivot_detector() -> bool:
    """Validate PivotDetector (11.9a)."""
    print("\n" + "=" * 60)
    print("11.9a: Validating PivotDetector")
    print("=" * 60)

    try:
        # Create detector
        detector = PivotDetector(left_bars=5, right_bars=5)
        print("[OK] PivotDetector initialized")

        # Create test data
        bars = create_sample_bars(100)
        print(f"[OK] Created {len(bars)} sample bars")

        # Detect pivots
        pivot_highs, pivot_lows = detector.detect_pivots(bars)
        print(f"[OK] Detected {len(pivot_highs)} pivot highs")
        print(f"[OK] Detected {len(pivot_lows)} pivot lows")

        # Validate results
        assert len(pivot_highs) > 0, "Should detect at least one pivot high"
        assert len(pivot_lows) > 0, "Should detect at least one pivot low"
        print("[OK] PivotDetector validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] PivotDetector validation FAILED: {e}")
        return False


def validate_range_quality_scorer() -> bool:
    """Validate RangeQualityScorer (11.9b)."""
    print("\n" + "=" * 60)
    print("11.9b: Validating RangeQualityScorer")
    print("=" * 60)

    try:
        # Create scorer
        scorer = RangeQualityScorer(min_touches=3, min_bars=10)
        print("[OK] RangeQualityScorer initialized")

        # Create test data
        bars = create_sample_bars(100)
        volume_analysis = create_sample_volume_analysis(bars)
        trading_range = create_sample_trading_range(bars)
        print("[OK] Created sample trading range")

        # Score range
        score = scorer.score_range(trading_range, bars, volume_analysis)
        print(f"[OK] Range scored: {score.quality_grade} ({score.total_score}/100)")
        print(f"  - Tightness: {score.tightness_score}/20")
        print(f"  - Volume: {score.volume_score}/20")
        print(f"  - Duration: {score.duration_score}/30")
        print(f"  - Touches: {score.touch_score}/30")

        # Validate results
        assert score.total_score >= 0, "Score should be non-negative"
        assert score.total_score <= 100, "Score should not exceed 100"
        assert score.quality_grade in [
            "EXCELLENT",
            "GOOD",
            "FAIR",
            "POOR",
        ], f"Invalid grade: {score.quality_grade}"
        print("[OK] RangeQualityScorer validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] RangeQualityScorer validation FAILED: {e}")
        return False


def validate_level_calculator() -> bool:
    """Validate LevelCalculator (11.9c)."""
    print("\n" + "=" * 60)
    print("11.9c: Validating LevelCalculator")
    print("=" * 60)

    try:
        # Create calculator
        calculator = LevelCalculator()
        print("[OK] LevelCalculator initialized")

        # Create test data
        bars = create_sample_bars(100)
        volume_analysis = create_sample_volume_analysis(bars)
        trading_range = create_sample_trading_range(bars)
        print("[OK] Created test data")

        # Calculate levels
        creek_levels = calculator.calculate_creek_levels(trading_range, bars, volume_analysis)
        print(f"[OK] Calculated {len(creek_levels)} Creek levels")

        ice_levels = calculator.calculate_ice_levels(trading_range, bars, volume_analysis)
        print(f"[OK] Calculated {len(ice_levels)} Ice levels")

        jump_levels = calculator.calculate_jump_levels(
            trading_range, "bullish", bars=bars, volume_analysis=volume_analysis
        )
        print(f"[OK] Calculated {len(jump_levels)} Jump levels")

        # Validate results
        assert isinstance(creek_levels, list), "Creek levels should be a list"
        assert isinstance(ice_levels, list), "Ice levels should be a list"
        assert isinstance(jump_levels, list), "Jump levels should be a list"
        print("[OK] LevelCalculator validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] LevelCalculator validation FAILED: {e}")
        return False


def validate_zone_mapper() -> bool:
    """Validate ZoneMapper (11.9d)."""
    print("\n" + "=" * 60)
    print("11.9d: Validating ZoneMapper")
    print("=" * 60)

    try:
        # Create mapper
        mapper = ZoneMapper(zone_thickness_pct=0.02)
        print("[OK] ZoneMapper initialized")

        # Create test data
        bars = create_sample_bars(100)
        volume_analysis = create_sample_volume_analysis(bars)
        trading_range = create_sample_trading_range(bars)
        print("[OK] Created test data")

        # Map zones
        supply_zones = mapper.map_supply_zones(
            bars, lookback=100, volume_analysis=volume_analysis, trading_range=trading_range
        )
        print(f"[OK] Mapped {len(supply_zones)} supply zones")

        demand_zones = mapper.map_demand_zones(
            bars, lookback=100, volume_analysis=volume_analysis, trading_range=trading_range
        )
        print(f"[OK] Mapped {len(demand_zones)} demand zones")

        # Validate results
        assert isinstance(supply_zones, list), "Supply zones should be a list"
        assert isinstance(demand_zones, list), "Demand zones should be a list"
        print("[OK] ZoneMapper validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] ZoneMapper validation FAILED: {e}")
        return False


def validate_utad_detector() -> bool:
    """Validate UTAD Detector (11.9e)."""
    print("\n" + "=" * 60)
    print("11.9e: Validating UTAD Detector")
    print("=" * 60)

    try:
        # Create detector
        detector = UTADDetector(max_penetration_pct=Decimal("5.0"))
        print("[OK] UTADDetector initialized")

        # Create test data with UTAD pattern
        bars = create_sample_bars(100)
        trading_range = create_sample_trading_range(bars)
        ice_level = Decimal("105.0")
        print("[OK] Created test data")

        # Detect UTAD (may return None if pattern not present)
        utad = detector.detect_utad(trading_range, bars, ice_level)
        if utad:
            print(f"[OK] UTAD detected at bar {utad.utad_bar_index}")
            print(f"  - Volume ratio: {utad.volume_ratio:.2f}x")
            print(f"  - Penetration: {utad.penetration_pct:.2f}%")
            print(f"  - Confidence: {utad.confidence}/100")
        else:
            print("[OK] No UTAD detected (expected with random data)")

        print("[OK] UTAD Detector validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] UTAD Detector validation FAILED: {e}")
        return False


def validate_quality_position_sizer() -> bool:
    """Validate Quality Position Sizer (11.9f)."""
    print("\n" + "=" * 60)
    print("11.9f: Validating Quality Position Sizer")
    print("=" * 60)

    try:
        # Create sizer
        sizer = QualityPositionSizer()
        print("[OK] QualityPositionSizer initialized")

        # Test different quality grades
        base_size = Decimal("100")
        test_cases = [
            ("EXCELLENT", False, False, Decimal("100.0")),  # 1.0x
            ("GOOD", False, False, Decimal("75.0")),  # 0.75x
            ("FAIR", False, False, Decimal("50.0")),  # 0.5x
            ("POOR", False, False, Decimal("25.0")),  # 0.25x
            ("EXCELLENT", True, False, Decimal("120.0")),  # 1.0 * 1.2 = 1.2x
            ("EXCELLENT", False, True, Decimal("110.0")),  # 1.0 * 1.1 = 1.1x
        ]

        for quality, sector_leader, market_leader, expected in test_cases:
            size = sizer.calculate_position_size(
                base_size=base_size,
                quality_grade=quality,
                is_sector_leader=sector_leader,
                is_market_leader=market_leader,
            )
            leader_str = ""
            if sector_leader:
                leader_str = " (sector leader)"
            elif market_leader:
                leader_str = " (market leader)"
            print(f"[OK] {quality}{leader_str}: {size} shares (expected ~{expected})")

            # Validate within 1% tolerance
            assert abs(size - expected) < Decimal("1.0"), f"Unexpected size: {size}"

        # Validate capping at 1.5x
        size = sizer.calculate_position_size(
            base_size=Decimal("100"),
            quality_grade="EXCELLENT",
            rs_score=Decimal("0.9"),
            is_sector_leader=True,  # Would be 1.0 * 1.2 = 1.2, capped at 1.5
        )
        print(f"[OK] Multiplier capping: {size} shares (should be ≤ 150)")
        assert size <= Decimal("150"), "Should cap at 1.5x"

        print("[OK] Quality Position Sizer validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] Quality Position Sizer validation FAILED: {e}")
        return False


def validate_campaign_state_machine() -> bool:
    """Validate Campaign State Machine (11.9g)."""
    print("\n" + "=" * 60)
    print("11.9g: Validating Campaign State Machine")
    print("=" * 60)

    try:
        # Create state machine
        machine = CampaignStateMachine()
        print("[OK] CampaignStateMachine initialized")

        # Test state transitions
        state = CampaignState.BUILDING_CAUSE
        print(f"[OK] Initial state: {state.value}")

        state = machine.transition_state(state, "SPRING_DETECTED")
        assert state == CampaignState.TESTING, f"Expected TESTING, got {state}"
        print(f"[OK] SPRING_DETECTED → {state.value}")

        state = machine.transition_state(state, "SOS_DETECTED")
        assert state == CampaignState.BREAKOUT, f"Expected BREAKOUT, got {state}"
        print(f"[OK] SOS_DETECTED → {state.value}")

        state = machine.transition_state(state, "LPS_DETECTED")
        assert state == CampaignState.MARKUP, f"Expected MARKUP, got {state}"
        print(f"[OK] LPS_DETECTED → {state.value}")

        # Test position sizing
        breakout_position = machine.calculate_campaign_position(CampaignState.BREAKOUT, "EXCELLENT")
        assert breakout_position == Decimal("33"), f"Expected 33%, got {breakout_position}"
        print(f"[OK] BREAKOUT position: {breakout_position}% (expected 33%)")

        markup_position = machine.calculate_campaign_position(CampaignState.MARKUP, "EXCELLENT")
        assert markup_position == Decimal("50"), f"Expected 50%, got {markup_position}"
        print(f"[OK] MARKUP position: {markup_position}% (expected 50%)")

        # Test quality adjustment
        poor_quality_position = machine.calculate_campaign_position(CampaignState.BREAKOUT, "POOR")
        assert poor_quality_position < breakout_position, "POOR quality should reduce position"
        print(f"[OK] POOR quality adjustment: {poor_quality_position}% (reduced from 33%)")

        # Test valid transitions
        valid_events = machine.get_valid_transitions(CampaignState.TESTING)
        print(f"[OK] Valid transitions from TESTING: {valid_events}")
        assert "SOS_DETECTED" in valid_events, "Should include SOS_DETECTED"

        print("[OK] Campaign State Machine validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] Campaign State Machine validation FAILED: {e}")
        return False


def validate_orchestrator_health() -> bool:
    """Validate Orchestrator Health (AC8)."""
    print("\n" + "=" * 60)
    print("AC8: Validating Orchestrator Health")
    print("=" * 60)

    try:
        # Create container
        container = OrchestratorContainer()
        print("[OK] OrchestratorContainer initialized")

        # Check health
        health = container.health_check()
        print(f"[OK] Status: {health['status']}")
        print(f"[OK] Loaded: {health['loaded_count']} detectors")

        # Validate healthy status
        assert health["status"] == "healthy", f"Expected healthy, got {health['status']}"
        assert health["loaded_count"] >= 9, f"Expected 9+ detectors, got {health['loaded_count']}"

        print("[OK] Orchestrator Health validation PASSED")
        return True

    except Exception as e:
        print(f"[FAIL] Orchestrator Health validation FAILED: {e}")
        return False


def main():
    """Run all validations."""
    print("\n" + "=" * 60)
    print("Story 11.9 Validation Suite")
    print("=" * 60)
    print("\nValidating all 7 subtasks + orchestrator health...\n")

    results = {
        "11.9a PivotDetector": validate_pivot_detector(),
        "11.9b RangeQualityScorer": validate_range_quality_scorer(),
        "11.9c LevelCalculator": validate_level_calculator(),
        "11.9d ZoneMapper": validate_zone_mapper(),
        "11.9e UTAD Detector": validate_utad_detector(),
        "11.9f Quality Position Sizer": validate_quality_position_sizer(),
        "11.9g Campaign State Machine": validate_campaign_state_machine(),
        "AC8 Orchestrator Health": validate_orchestrator_health(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for name, result in results.items():
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status} - {name}")

    print("\n" + "-" * 60)
    print(f"Results: {passed}/{total} validations passed")
    print("=" * 60)

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
