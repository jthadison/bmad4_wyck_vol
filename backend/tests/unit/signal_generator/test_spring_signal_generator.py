"""
Unit tests for Spring Signal Generator (Story 5.5) - Core Helper Functions.

These tests validate the core business logic functions that power signal generation:
- Adaptive stop loss calculation (3 tiers based on penetration depth)
- Position sizing calculation (risk-based with whole shares)
- Urgency determination (recovery speed mapping)
- Error handling for invalid inputs

Full integration testing is deferred - these core functions are the critical path.
"""

from decimal import Decimal, ROUND_DOWN

import pytest

from src.signal_generator.spring_signal_generator import (
    calculate_adaptive_stop_buffer,
    calculate_position_size,
    determine_urgency,
)


# ============================================================================
# Task 18A: Test adaptive stop loss tiers (AC 3)
# ============================================================================


def test_calculate_adaptive_stop_buffer():
    """Test AC 3: Adaptive stop buffer tiers based on penetration depth."""
    # Shallow spring (1-2%): 2% stop buffer (more room)
    assert calculate_adaptive_stop_buffer(Decimal("0.010")) == Decimal("0.02")
    assert calculate_adaptive_stop_buffer(Decimal("0.015")) == Decimal("0.02")
    assert calculate_adaptive_stop_buffer(Decimal("0.019")) == Decimal("0.02")

    # Medium spring (2-3%): 1.5% stop buffer (balanced)
    assert calculate_adaptive_stop_buffer(Decimal("0.020")) == Decimal("0.015")
    assert calculate_adaptive_stop_buffer(Decimal("0.025")) == Decimal("0.015")
    assert calculate_adaptive_stop_buffer(Decimal("0.029")) == Decimal("0.015")

    # Deep spring (3-5%): 1% stop buffer (tighter, near breakdown)
    assert calculate_adaptive_stop_buffer(Decimal("0.030")) == Decimal("0.01")
    assert calculate_adaptive_stop_buffer(Decimal("0.040")) == Decimal("0.01")
    assert calculate_adaptive_stop_buffer(Decimal("0.050")) == Decimal("0.01")


# ============================================================================
# Task 18B: Test position size calculation (AC 11)
# ============================================================================


def test_calculate_position_size_direct():
    """Test AC 11: Position size calculation scales correctly with risk."""
    # Test 1: $100k account, 1% risk, $5 risk per share
    # Dollar risk: $100k × 1% = $1,000
    # Position: $1,000 / $5 = 200 shares
    position = calculate_position_size(
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("145.00"),  # $5 risk per share
        account_size=Decimal("100000"),
        risk_per_trade_pct=Decimal("0.01"),  # 1%
    )
    assert position == Decimal("200"), "Should calculate 200 shares"

    # Test 2: $50k account, 2% risk, $10 risk per share
    # Dollar risk: $50k × 2% = $1,000
    # Position: $1,000 / $10 = 100 shares
    position = calculate_position_size(
        entry_price=Decimal("110.00"),
        stop_loss=Decimal("100.00"),  # $10 risk per share
        account_size=Decimal("50000"),
        risk_per_trade_pct=Decimal("0.02"),  # 2%
    )
    assert position == Decimal("100"), "Should calculate 100 shares"

    # Test 3: Fractional shares round down (never risk more than planned)
    # Dollar risk: $100k × 1% = $1,000
    # Risk per share: $3.33
    # Position raw: $1,000 / $3.33 = 300.3 shares
    # Position final: 300 shares (ROUND_DOWN)
    position = calculate_position_size(
        entry_price=Decimal("153.33"),
        stop_loss=Decimal("150.00"),  # $3.33 risk per share
        account_size=Decimal("100000"),
        risk_per_trade_pct=Decimal("0.01"),
    )
    assert position == Decimal("300"), "Should round down to 300 shares (not 301)"


def test_calculate_position_size_invalid_stop():
    """Test AC 11: Position size raises error if stop >= entry (invalid long setup)."""
    with pytest.raises(ValueError, match="Stop must be below entry"):
        calculate_position_size(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("105.00"),  # INVALID: stop above entry
            account_size=Decimal("100000"),
            risk_per_trade_pct=Decimal("0.01"),
        )

    with pytest.raises(ValueError, match="Stop must be below entry"):
        calculate_position_size(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("100.00"),  # INVALID: stop equal to entry
            account_size=Decimal("100000"),
            risk_per_trade_pct=Decimal("0.01"),
        )


# ============================================================================
# Task 18C: Test urgency determination (AC 12)
# ============================================================================


def test_determine_urgency_direct():
    """Test AC 12: Urgency classification based on recovery speed."""
    # IMMEDIATE: 1-bar recovery (strongest demand, fastest absorption)
    assert determine_urgency(1) == "IMMEDIATE"

    # MODERATE: 2-3 bar recovery (normal spring behavior)
    assert determine_urgency(2) == "MODERATE"
    assert determine_urgency(3) == "MODERATE"

    # LOW: 4-5 bar recovery (slower absorption, weaker demand)
    assert determine_urgency(4) == "LOW"
    assert determine_urgency(5) == "LOW"

    # Edge case: 6+ bars should still return LOW
    assert determine_urgency(6) == "LOW"
    assert determine_urgency(10) == "LOW"
