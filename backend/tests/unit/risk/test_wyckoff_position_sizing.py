"""
Unit tests for Wyckoff Position Sizing (Story 4.7).

Tests Rachel's position sizing calculator with Wyckoff-specific risk adjustments:
- Base position size calculation
- Phase B duration adjustment
- Phase E exhaustion adjustment
- Recent invalidation adjustment
- Helper functions (position value, risk amount, summary)

Risk Management Principle:
    Position size must adapt to Wyckoff phase context, not just account risk.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.models.phase_info import (
    PhaseInfo,
    PhaseInvalidation,
    PhaseESubState,
    PhaseBRiskProfile,
)
from src.models.phase_events import PhaseEvents
from src.models.wyckoff_phase import WyckoffPhase
from src.risk.wyckoff_position_sizing import (
    WyckoffPositionSize,
    calculate_wyckoff_position_size,
    get_position_value,
    get_risk_amount,
    get_position_summary,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def base_phase_info() -> PhaseInfo:
    """Create basic PhaseInfo without risk adjustments."""
    return PhaseInfo(
        phase=WyckoffPhase.C,
        confidence=78,
        events=PhaseEvents(),
        duration=10,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=0,
        current_bar_index=10,
        last_updated=datetime.now(timezone.utc),
    )


@pytest.fixture
def phase_info_short_phase_b() -> PhaseInfo:
    """Create PhaseInfo with short Phase B (requires position reduction)."""
    phase_b_risk = PhaseBRiskProfile(
        duration=7,
        context="base_accumulation",
        minimum_duration=10,
        has_exceptional_evidence=False,
        risk_adjustment_factor=0.75,  # Reduce to 75%
        risk_level="elevated",
        risk_rationale="Short Phase B - reduce to 75%",
    )

    return PhaseInfo(
        phase=WyckoffPhase.B,
        confidence=72,
        events=PhaseEvents(),
        duration=7,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=0,
        current_bar_index=7,
        last_updated=datetime.now(timezone.utc),
        phase_b_risk_profile=phase_b_risk,
    )


@pytest.fixture
def phase_info_exhaustion() -> PhaseInfo:
    """Create PhaseInfo with Phase E exhaustion (extreme risk reduction)."""
    return PhaseInfo(
        phase=WyckoffPhase.E,
        sub_phase=PhaseESubState.EXHAUSTION,
        confidence=65,
        events=PhaseEvents(),
        duration=50,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=0,
        current_bar_index=50,
        last_updated=datetime.now(timezone.utc),
    )


@pytest.fixture
def phase_info_recent_invalidation() -> PhaseInfo:
    """Create PhaseInfo with recent invalidation (caution required)."""
    invalidation = PhaseInvalidation(
        phase_invalidated=WyckoffPhase.C,
        invalidation_reason="Spring failed to hold",
        bar_index=45,
        timestamp=datetime.now(timezone.utc),
        invalidation_type="failed_event",
        reverted_to_phase=WyckoffPhase.B,
        risk_level="high",
        position_action="reduce",
        new_stop_level=49.00,
        risk_reason="Demand insufficient",
    )

    return PhaseInfo(
        phase=WyckoffPhase.B,
        confidence=68,
        events=PhaseEvents(),
        duration=10,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=40,
        current_bar_index=50,
        last_updated=datetime.now(timezone.utc),
        invalidations=[invalidation],
    )


# ============================================================================
# Base Position Size Calculation Tests
# ============================================================================


def test_base_position_size_calculation(base_phase_info):
    """Test basic position size calculation without adjustments."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,  # 2%
        entry_price=50.00,
        stop_price=48.00,  # $2 risk per share
        phase_info=base_phase_info,
    )

    # Base calculation: $2000 risk / $2 per share = 1000 shares
    assert position.base_position_size == pytest.approx(1000.0, abs=0.1)
    assert position.final_position_size == pytest.approx(1000.0, abs=0.1)
    assert position.risk_reduction_factors == {}


def test_position_size_with_larger_stop(base_phase_info):
    """Test position size calculation with wider stop (larger risk per share)."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=45.00,  # $5 risk per share
        phase_info=base_phase_info,
    )

    # Base calculation: $2000 risk / $5 per share = 400 shares
    assert position.base_position_size == pytest.approx(400.0, abs=0.1)
    assert position.final_position_size == pytest.approx(400.0, abs=0.1)


def test_position_size_with_higher_risk_tolerance(base_phase_info):
    """Test position size with higher risk per trade (3%)."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.03,  # 3%
        entry_price=50.00,
        stop_price=48.00,
        phase_info=base_phase_info,
    )

    # Base calculation: $3000 risk / $2 per share = 1500 shares
    assert position.base_position_size == pytest.approx(1500.0, abs=0.1)


def test_invalid_stop_above_entry_raises_error(base_phase_info):
    """Test that stop above entry raises ValueError."""
    with pytest.raises(ValueError, match="Stop price.*must be below entry price"):
        calculate_wyckoff_position_size(
            account_size=100000.0,
            risk_per_trade=0.02,
            entry_price=48.00,  # Entry below stop - INVALID
            stop_price=50.00,
            phase_info=base_phase_info,
        )


# ============================================================================
# Phase B Duration Adjustment Tests
# ============================================================================


def test_phase_b_short_duration_adjustment(phase_info_short_phase_b):
    """Test position size reduction for short Phase B (0.75x)."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info_short_phase_b,
    )

    # Base: 1000 shares
    # Adjustment: 0.75x (short Phase B)
    # Final: 750 shares
    assert position.base_position_size == pytest.approx(1000.0, abs=0.1)
    assert position.final_position_size == pytest.approx(750.0, abs=0.1)
    assert "phase_b_duration" in position.risk_reduction_factors
    assert position.risk_reduction_factors["phase_b_duration"] == 0.75


def test_normal_phase_b_no_adjustment(base_phase_info):
    """Test normal Phase B duration has no adjustment."""
    # Create Phase B with normal duration
    phase_b_risk = PhaseBRiskProfile(
        duration=12,
        context="base_accumulation",
        minimum_duration=10,
        has_exceptional_evidence=False,
        risk_adjustment_factor=1.0,  # Full position
        risk_level="normal",
        risk_rationale="Adequate duration",
    )

    phase_info = PhaseInfo(
        phase=WyckoffPhase.B,
        confidence=80,
        events=PhaseEvents(),
        duration=12,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=0,
        current_bar_index=12,
        last_updated=datetime.now(timezone.utc),
        phase_b_risk_profile=phase_b_risk,
    )

    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info,
    )

    # No adjustment (1.0x)
    assert position.final_position_size == pytest.approx(1000.0, abs=0.1)
    assert "phase_b_duration" in position.risk_reduction_factors
    assert position.risk_reduction_factors["phase_b_duration"] == 1.0


# ============================================================================
# Phase E Exhaustion Adjustment Tests
# ============================================================================


def test_phase_e_exhaustion_extreme_reduction(phase_info_exhaustion):
    """Test extreme position reduction for Phase E exhaustion (0.25x)."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info_exhaustion,
    )

    # Base: 1000 shares
    # Adjustment: 0.25x (EXHAUSTION - exit time, not entry)
    # Final: 250 shares
    assert position.base_position_size == pytest.approx(1000.0, abs=0.1)
    assert position.final_position_size == pytest.approx(250.0, abs=0.1)
    assert "phase_e_exhaustion" in position.risk_reduction_factors
    assert position.risk_reduction_factors["phase_e_exhaustion"] == 0.25


def test_phase_e_early_no_adjustment(base_phase_info):
    """Test early Phase E has no exhaustion adjustment."""
    phase_info = PhaseInfo(
        phase=WyckoffPhase.E,
        sub_phase=PhaseESubState.EARLY,  # Not exhaustion
        confidence=82,
        events=PhaseEvents(),
        duration=10,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=0,
        current_bar_index=10,
        last_updated=datetime.now(timezone.utc),
    )

    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info,
    )

    # No exhaustion adjustment
    assert position.final_position_size == pytest.approx(1000.0, abs=0.1)
    assert "phase_e_exhaustion" not in position.risk_reduction_factors


# ============================================================================
# Recent Invalidation Adjustment Tests
# ============================================================================


def test_recent_invalidation_reduction(phase_info_recent_invalidation):
    """Test position reduction for recent invalidation (0.75x)."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info_recent_invalidation,
    )

    # Base: 1000 shares
    # Adjustment: 0.75x (recent invalidation - caution)
    # Final: 750 shares
    assert position.base_position_size == pytest.approx(1000.0, abs=0.1)
    assert position.final_position_size == pytest.approx(750.0, abs=0.1)
    assert "recent_invalidation" in position.risk_reduction_factors
    assert position.risk_reduction_factors["recent_invalidation"] == 0.75


def test_old_invalidation_no_adjustment(base_phase_info):
    """Test old invalidation (>10 bars ago) has no adjustment."""
    # Add invalidation from 15 bars ago
    old_invalidation = PhaseInvalidation(
        phase_invalidated=WyckoffPhase.C,
        invalidation_reason="Old invalidation",
        bar_index=30,  # 20 bars ago (current bar = 50)
        timestamp=datetime.now(timezone.utc),
        invalidation_type="failed_event",
        reverted_to_phase=WyckoffPhase.B,
        risk_level="high",
        position_action="reduce",
        new_stop_level=49.00,
        risk_reason="Old event",
    )

    phase_info = PhaseInfo(
        phase=WyckoffPhase.C,
        confidence=76,
        events=PhaseEvents(),
        duration=20,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=30,
        current_bar_index=50,  # 20 bars after invalidation
        last_updated=datetime.now(timezone.utc),
        invalidations=[old_invalidation],
    )

    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info,
    )

    # No adjustment (invalidation too old)
    assert position.final_position_size == pytest.approx(1000.0, abs=0.1)
    assert "recent_invalidation" not in position.risk_reduction_factors


# ============================================================================
# Multiple Adjustments (Stacking) Tests
# ============================================================================


def test_multiple_adjustments_stack():
    """Test that multiple adjustments stack (multiply sequentially)."""
    # Create Phase B with short duration AND recent invalidation
    phase_b_risk = PhaseBRiskProfile(
        duration=7,
        context="base_accumulation",
        minimum_duration=10,
        has_exceptional_evidence=False,
        risk_adjustment_factor=0.75,
        risk_level="elevated",
        risk_rationale="Short Phase B",
    )

    invalidation = PhaseInvalidation(
        phase_invalidated=WyckoffPhase.C,
        invalidation_reason="Recent event",
        bar_index=45,
        timestamp=datetime.now(timezone.utc),
        invalidation_type="failed_event",
        reverted_to_phase=WyckoffPhase.B,
        risk_level="high",
        position_action="reduce",
        new_stop_level=49.00,
        risk_reason="Caution",
    )

    phase_info = PhaseInfo(
        phase=WyckoffPhase.B,
        confidence=70,
        events=PhaseEvents(),
        duration=7,
        progression_history=[],
        trading_range=None,
        phase_start_bar_index=43,
        current_bar_index=50,
        last_updated=datetime.now(timezone.utc),
        phase_b_risk_profile=phase_b_risk,
        invalidations=[invalidation],
    )

    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info,
    )

    # Base: 1000 shares
    # Adjustment 1: 0.75x (Phase B) = 750 shares
    # Adjustment 2: 0.75x (Invalidation) = 562.5 shares
    assert position.base_position_size == pytest.approx(1000.0, abs=0.1)
    assert position.final_position_size == pytest.approx(562.5, abs=0.1)
    assert len(position.risk_reduction_factors) == 2
    assert position.risk_reduction_factors["phase_b_duration"] == 0.75
    assert position.risk_reduction_factors["recent_invalidation"] == 0.75


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_get_position_value(base_phase_info):
    """Test position value calculation."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=base_phase_info,
    )

    position_value = get_position_value(position)

    # 1000 shares * $50 = $50,000
    assert position_value == pytest.approx(50000.0, abs=1.0)


def test_get_risk_amount(base_phase_info):
    """Test risk amount calculation."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=base_phase_info,
    )

    risk_amount = get_risk_amount(position)

    # 1000 shares * $2 risk = $2000
    assert risk_amount == pytest.approx(2000.0, abs=1.0)


def test_get_risk_amount_with_adjustments(phase_info_short_phase_b):
    """Test risk amount with position size adjustments (actual risk < target)."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,  # Target: 2%
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info_short_phase_b,
    )

    risk_amount = get_risk_amount(position)

    # 750 shares * $2 risk = $1500 (1.5% actual risk < 2% target)
    assert risk_amount == pytest.approx(1500.0, abs=1.0)
    # Actual risk % = 1500 / 100000 = 1.5%
    actual_risk_pct = risk_amount / position.account_size
    assert actual_risk_pct == pytest.approx(0.015, abs=0.001)


def test_get_position_summary(base_phase_info):
    """Test position summary generation."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=base_phase_info,
    )

    summary = get_position_summary(position)

    # Verify summary contains key information
    assert "Account: $100,000.00" in summary
    assert "Risk: 2.00%" in summary
    assert "Final Position: 1,000 shares" in summary
    assert "Final Risk: $2,000.00" in summary


def test_get_position_summary_with_adjustments(phase_info_short_phase_b):
    """Test position summary includes adjustment details."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=phase_info_short_phase_b,
    )

    summary = get_position_summary(position)

    # Verify summary includes adjustments
    assert "Adjustments:" in summary
    assert "Phase B Duration: 0.75x" in summary
    assert "Final Position: 750 shares" in summary


# ============================================================================
# Position Size Model Tests
# ============================================================================


def test_position_size_model_structure(base_phase_info):
    """Test WyckoffPositionSize model contains all required fields."""
    position = calculate_wyckoff_position_size(
        account_size=100000.0,
        risk_per_trade=0.02,
        entry_price=50.00,
        stop_price=48.00,
        phase_info=base_phase_info,
    )

    # Verify all fields present
    assert hasattr(position, 'account_size')
    assert hasattr(position, 'risk_per_trade')
    assert hasattr(position, 'entry_price')
    assert hasattr(position, 'stop_price')
    assert hasattr(position, 'phase')
    assert hasattr(position, 'sub_phase')
    assert hasattr(position, 'base_position_size')
    assert hasattr(position, 'risk_adjusted_size')
    assert hasattr(position, 'final_position_size')
    assert hasattr(position, 'risk_reduction_factors')

    # Verify types
    assert position.phase == WyckoffPhase.C
    assert isinstance(position.risk_reduction_factors, dict)
