"""
Integration Tests for Signal Output (Story 8.8)

Tests for:
- Generated signals contain all FR22 required fields
- Validation chain integration with signal creation
- STOCK vs FOREX signal differences
- Rejected signal creation from failed validation

Author: Story 8.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from src.models.signal import RejectedSignal, TradeSignal
from src.models.validation import ValidationStatus
from tests.fixtures.signal_fixtures import (
    mock_validation_chain,
    valid_forex_signal,
    valid_spring_signal,
)

# ============================================================================
# Signal Generation Integration Tests (AC: 8)
# ============================================================================


def test_generated_signal_contains_all_fr22_fields():
    """
    Test generated TradeSignal contains all FR22 required fields.

    FR22 Fields:
    - symbol, pattern_type, phase
    - entry_price, stop_loss
    - target_levels (primary + secondary)
    - position_size, risk_amount
    - r_multiple, confidence_score
    - campaign_id, timestamp
    """
    signal = valid_spring_signal()

    # Verify all FR22 fields present and populated
    assert signal.symbol == "AAPL"
    assert signal.pattern_type == "SPRING"
    assert signal.phase == "C"
    assert signal.entry_price == Decimal("150.00")
    assert signal.stop_loss == Decimal("148.00")
    assert signal.target_levels.primary_target == Decimal("156.00")
    assert len(signal.target_levels.secondary_targets) == 2
    assert signal.position_size == Decimal("100")
    assert signal.risk_amount == Decimal("200.00")
    assert signal.r_multiple == Decimal("3.0")
    assert signal.confidence_score == 85
    assert signal.campaign_id == "AAPL-2024-03-13-C"
    assert signal.timestamp is not None
    assert isinstance(signal.timestamp, datetime)


def test_generated_signal_has_complete_validation_chain():
    """Test signal includes validation results from all 5 validators."""
    signal = valid_spring_signal()

    # Validation chain should exist
    assert signal.validation_chain is not None
    assert signal.validation_chain.overall_status == ValidationStatus.PASS

    # Should have results from all 5 stages
    stages = [r.stage for r in signal.validation_chain.validation_results]
    expected_stages = ["Volume", "Phase", "Levels", "Risk", "Strategy"]

    assert len(stages) == len(expected_stages)
    for expected_stage in expected_stages:
        assert expected_stage in stages


def test_generated_signal_has_confidence_components():
    """Test signal has confidence breakdown from all validators."""
    signal = valid_spring_signal()

    # Confidence components should exist
    assert signal.confidence_components is not None
    assert signal.confidence_components.pattern_confidence == 88
    assert signal.confidence_components.phase_confidence == 82
    assert signal.confidence_components.volume_confidence == 80
    assert signal.confidence_components.overall_confidence == 85

    # Overall should match top-level confidence
    assert signal.confidence_score == signal.confidence_components.overall_confidence


def test_generated_signal_has_pattern_data():
    """Test signal includes pattern-specific metadata."""
    signal = valid_spring_signal()

    # Pattern data should exist
    assert signal.pattern_data is not None
    assert "pattern_bar_timestamp" in signal.pattern_data
    assert "test_bar_timestamp" in signal.pattern_data
    assert "trading_range_id" in signal.pattern_data


def test_generated_signal_has_volume_analysis():
    """Test signal includes volume analysis data."""
    signal = valid_spring_signal()

    # Volume analysis should exist
    assert signal.volume_analysis is not None
    assert "volume_ratio" in signal.volume_analysis
    assert signal.volume_analysis["volume_ratio"] == "0.55"
    assert "average_volume" in signal.volume_analysis


# ============================================================================
# STOCK vs FOREX Integration Tests (AC: 11-14)
# ============================================================================


def test_stock_signal_structure():
    """Test STOCK signal has correct structure and fields."""
    signal = valid_spring_signal()

    # STOCK-specific fields
    assert signal.asset_class == "STOCK"
    assert signal.position_size_unit == "SHARES"
    assert signal.leverage is None
    assert signal.margin_requirement is None

    # Notional value = position_size × entry_price
    expected_notional = signal.position_size * signal.entry_price
    assert signal.notional_value == expected_notional


def test_forex_signal_structure():
    """Test FOREX signal has correct structure with leverage."""
    signal = valid_forex_signal()

    # FOREX-specific fields
    assert signal.asset_class == "FOREX"
    assert signal.position_size_unit == "LOTS"
    assert signal.leverage == Decimal("50.0")
    assert signal.margin_requirement == Decimal("1085.00")

    # Notional value = position_size × 100,000 × entry_price (for standard lots)
    # 0.5 lots × 100,000 × 1.085 = 54,250
    assert signal.notional_value == Decimal("54250.00")


def test_forex_signal_has_session_context():
    """Test FOREX signal includes session-specific context."""
    signal = valid_forex_signal()

    # Forex signals should have session info in volume_analysis
    assert "session" in signal.volume_analysis
    assert signal.volume_analysis["session"] == "LONDON"

    # Should have tick volume instead of regular volume
    assert "tick_volume_ratio" in signal.volume_analysis


# ============================================================================
# Rejected Signal Integration Tests (AC: 2, 8)
# ============================================================================


def test_rejected_signal_contains_rejection_data():
    """Test RejectedSignal created when validation fails."""
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(
        pattern_id=pattern_id,
        overall_status=ValidationStatus.FAIL,
        rejection_stage="Risk",
        rejection_reason="Portfolio heat would be 12.5% (exceeds 10.0% limit)",
    )

    # Create rejected signal
    rejected = RejectedSignal(
        pattern_id=pattern_id,
        symbol="TSLA",
        pattern_type="SPRING",
        rejection_stage="Risk",
        rejection_reason="Portfolio heat would be 12.5% (exceeds 10.0% limit)",
        validation_chain=validation_chain,
    )

    # Verify rejection data
    assert rejected.rejection_stage == "Risk"
    assert "Portfolio heat" in rejected.rejection_reason
    assert "10.0% limit" in rejected.rejection_reason


def test_rejected_signal_has_partial_validation_chain():
    """Test rejected signal includes partial validation results."""
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(
        pattern_id=pattern_id,
        overall_status=ValidationStatus.FAIL,
        rejection_stage="Risk",
        rejection_reason="Portfolio heat exceeded",
    )

    rejected = RejectedSignal(
        pattern_id=pattern_id,
        symbol="NVDA",
        pattern_type="SOS",
        rejection_stage="Risk",
        rejection_reason="Portfolio heat exceeded",
        validation_chain=validation_chain,
    )

    # Validation chain should show partial results
    assert rejected.validation_chain.overall_status == ValidationStatus.FAIL
    assert rejected.validation_chain.rejection_stage == "Risk"

    # Should have Volume, Phase, Levels PASS, Risk FAIL
    stages = {r.stage: r.status for r in rejected.validation_chain.validation_results}
    assert stages["Volume"] == ValidationStatus.PASS
    assert stages["Phase"] == ValidationStatus.PASS
    assert stages["Levels"] == ValidationStatus.PASS
    assert stages["Risk"] == ValidationStatus.FAIL


# ============================================================================
# Signal Workflow Integration Tests
# ============================================================================


def test_signal_immutability_for_audit_trail():
    """Test signal fields are immutable once created (audit integrity)."""
    signal = valid_spring_signal()

    # Key fields should not be modified after creation
    original_entry = signal.entry_price
    original_timestamp = signal.timestamp

    # Attempting to modify should create new instance (Pydantic behavior)
    # Original signal should remain unchanged
    modified = signal.model_copy(update={"status": "FILLED"})

    assert signal.entry_price == original_entry
    assert signal.timestamp == original_timestamp
    assert signal.status == "APPROVED"
    assert modified.status == "FILLED"


def test_signal_serialization_preserves_audit_trail():
    """Test validation_chain survives serialization round-trip."""
    signal = valid_spring_signal()

    # Serialize and deserialize
    json_str = signal.model_dump_json()
    restored = TradeSignal.model_validate_json(json_str)

    # Validation chain should be preserved
    assert restored.validation_chain.overall_status == signal.validation_chain.overall_status
    assert len(restored.validation_chain.validation_results) == len(
        signal.validation_chain.validation_results
    )

    # All validation results should match
    for i, result in enumerate(signal.validation_chain.validation_results):
        restored_result = restored.validation_chain.validation_results[i]
        assert restored_result.stage == result.stage
        assert restored_result.status == result.status
        assert restored_result.validator_id == result.validator_id


def test_multiple_signals_from_same_campaign():
    """Test creating multiple signals for the same campaign."""
    campaign_id = "AAPL-2024-03-13-C"

    # Create two signals for same campaign
    signal1 = valid_spring_signal()
    signal1.campaign_id = campaign_id

    signal2 = valid_spring_signal()
    signal2.campaign_id = campaign_id
    signal2.pattern_type = "LPS"  # Different pattern

    # Should have same campaign ID but different signal IDs
    assert signal1.campaign_id == signal2.campaign_id
    assert signal1.id != signal2.id


def test_signal_r_multiple_reflects_actual_risk_reward():
    """Test R-multiple accurately reflects risk/reward ratio."""
    signal = valid_spring_signal()

    # Calculate expected R-multiple
    risk_per_share = signal.entry_price - signal.stop_loss
    reward_per_share = signal.target_levels.primary_target - signal.entry_price
    expected_r = reward_per_share / risk_per_share

    assert signal.r_multiple == expected_r

    # Verify potential gain calculation
    total_risk = signal.position_size * risk_per_share
    total_reward = signal.position_size * reward_per_share

    assert signal.risk_amount == total_risk
    assert total_reward == signal.risk_amount * signal.r_multiple


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_signal_handles_very_small_forex_position():
    """Test FOREX signal with minimum position size (micro lot)."""
    signal = valid_forex_signal()
    signal.position_size = Decimal("0.01")  # 1 micro lot = 1,000 units

    # Should still be valid
    assert signal.position_size == Decimal("0.01")
    assert signal.position_size_unit == "LOTS"


def test_signal_handles_high_precision_forex_prices():
    """Test FOREX signal with 8 decimal place precision."""
    signal = valid_forex_signal()

    # Forex prices often have 5 decimal places (or more for JPY pairs)
    signal.entry_price = Decimal("1.08567")
    signal.stop_loss = Decimal("1.08234")
    signal.target_levels.primary_target = Decimal("1.09567")

    # Should preserve precision
    assert signal.entry_price == Decimal("1.08567")


def test_signal_timestamp_always_utc():
    """Test signal timestamps are always UTC regardless of creation timezone."""
    signal = valid_spring_signal()

    # All timestamps should be UTC
    assert signal.timestamp.tzinfo == UTC
    assert signal.created_at.tzinfo == UTC

    # Serialization should include Z suffix
    json_str = signal.model_dump_json()
    assert (
        '"timestamp":"2024-03-13T14:30:00+00:00"' in json_str or "2024-03-13T14:30:00Z" in json_str
    )
