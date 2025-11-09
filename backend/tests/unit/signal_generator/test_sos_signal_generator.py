"""
Unit tests for SOS/LPS signal generation.

Tests cover:
- LPS signal generation with correct entry/stop/target (AC 1)
- SOS direct signal generation (AC 2)
- R-multiple calculation (AC 3)
- Minimum 2.0R validation (AC 4, FR19)
- Pattern data inclusion (AC 6)
- Campaign linkage (AC 7)
- LPS tighter stop than SOS direct (AC 8)
- JSON serialization (AC 10)
- Edge cases (invalid risk, missing Jump, boundary R-multiples)
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.sos_breakout import SOSBreakout
from src.models.sos_signal import SOSSignal
from src.signal_generator.sos_signal_generator import (
    check_spring_campaign_linkage,
    generate_lps_signal,
    generate_sos_direct_signal,
)


# Test AC 1: LPS signal generation
def test_generate_lps_signal_valid(lps_pattern, sos_breakout, trading_range):
    """Test AC 1: LPS signal generation with correct entry/stop/target."""
    confidence = 85

    # Act
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence)

    # Assert
    assert signal is not None, "LPS signal should be generated"
    assert signal.entry_type == "LPS_ENTRY"

    # AC 1: Entry above Ice (Ice + 1%)
    expected_entry = Decimal("100.00") * Decimal("1.01")  # $101.00
    assert signal.entry_price == expected_entry, f"Entry should be Ice + 1% = {expected_entry}"

    # AC 1: Stop 3% below Ice
    expected_stop = Decimal("100.00") * Decimal("0.97")  # $97.00
    assert signal.stop_loss == expected_stop, f"Stop should be Ice - 3% = {expected_stop}"

    # AC 1: Target = Jump level
    assert signal.target == Decimal("120.00"), "Target should be Jump level"

    # Verify confidence
    assert signal.confidence == 85

    # Verify phase
    assert signal.phase == "D"

    # Verify timestamps
    assert signal.sos_bar_timestamp == sos_breakout.bar.timestamp
    assert signal.lps_bar_timestamp == lps_pattern.bar.timestamp


# Test AC 8: LPS tighter stop than SOS direct
def test_lps_tighter_stop_than_sos_direct(lps_pattern, sos_breakout, trading_range):
    """Test AC 8: LPS should have tighter stop than SOS direct."""
    # Act
    lps_signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)
    sos_direct_signal = generate_sos_direct_signal(sos_breakout, trading_range, confidence=80)

    # Assert
    assert lps_signal is not None
    assert sos_direct_signal is not None

    # LPS stop: Ice - 3% = $97.00
    # SOS stop: Ice - 5% = $95.00
    lps_risk = lps_signal.entry_price - lps_signal.stop_loss
    sos_risk = sos_direct_signal.entry_price - sos_direct_signal.stop_loss

    assert lps_risk < sos_risk, "LPS should have tighter stop (lower risk) than SOS direct"

    # LPS: $101 - $97 = $4 risk
    # SOS: $102 - $95 = $7 risk
    assert lps_risk == Decimal("4.00")
    assert sos_risk == Decimal("7.00")


# Test AC 2: SOS direct signal generation
def test_generate_sos_direct_signal_valid(sos_breakout, trading_range):
    """Test AC 2: SOS direct signal generation with correct entry/stop/target."""
    confidence = 80

    # Act
    signal = generate_sos_direct_signal(sos_breakout, trading_range, confidence)

    # Assert
    assert signal is not None, "SOS direct signal should be generated"
    assert signal.entry_type == "SOS_DIRECT_ENTRY"

    # AC 2: Entry at breakout price
    assert signal.entry_price == Decimal("102.00"), "Entry should be SOS breakout price"

    # AC 2: Stop 5% below Ice
    expected_stop = Decimal("100.00") * Decimal("0.95")  # $95.00
    assert signal.stop_loss == expected_stop, f"Stop should be Ice - 5% = {expected_stop}"

    # AC 2: Target = Jump level
    assert signal.target == Decimal("120.00"), "Target should be Jump level"

    # Verify confidence
    assert signal.confidence == 80

    # Verify no LPS timestamp
    assert signal.lps_bar_timestamp is None
    assert signal.lps_volume_ratio is None


# Test AC 3: R-multiple calculation
def test_r_multiple_calculation(lps_pattern, sos_breakout, trading_range):
    """Test AC 3: R-multiple calculation formula."""
    # Arrange: LPS with known entry/stop/target
    # Entry: $101, Stop: $97, Target: $120
    # Risk: $101 - $97 = $4
    # Reward: $120 - $101 = $19
    # R-multiple: $19 / $4 = 4.75R

    # Act
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    # Assert (AC 3)
    assert signal is not None
    expected_r_multiple = Decimal("19.00") / Decimal("4.00")  # 4.75R
    assert signal.r_multiple == expected_r_multiple, f"R-multiple should be {expected_r_multiple}R"

    # Verify calculation method
    risk = signal.entry_price - signal.stop_loss
    reward = signal.target - signal.entry_price
    calculated_r = reward / risk
    assert calculated_r == signal.r_multiple

    # Verify helper methods
    assert signal.get_risk_distance() == Decimal("4.00")
    assert signal.get_reward_distance() == Decimal("19.00")


# Test AC 4, FR19: Minimum 2.0R requirement
def test_minimum_r_multiple_rejection(lps_pattern, sos_breakout, trading_range):
    """Test AC 4, FR19: Minimum 2.0R requirement."""
    # Arrange: Setup with low Jump level (poor R-multiple)
    # Ice: $100, Jump: $103 (only $3 target above Ice)
    # Entry: $101 (LPS), Stop: $97, Target: $103
    # Risk: $4, Reward: $2
    # R-multiple: $2 / $4 = 0.5R (below 2.0R minimum)

    # Update jump price to create poor R-multiple
    trading_range.jump.price = Decimal("103.00")

    # Act
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    # Assert (AC 4, FR19)
    assert signal is None, "Signal should be rejected - R-multiple < 2.0R (FR19)"


# Test AC 6: Pattern data inclusion
def test_lps_signal_pattern_data(lps_pattern, sos_breakout, trading_range):
    """Test AC 6: Signal includes SOS bar, LPS bar, volume ratios, phase."""
    # Act
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    # Assert (AC 6)
    assert signal is not None
    assert signal.sos_bar_timestamp == sos_breakout.bar.timestamp, "SOS bar timestamp included"
    assert signal.lps_bar_timestamp == lps_pattern.bar.timestamp, "LPS bar timestamp included"
    assert signal.sos_volume_ratio == Decimal("2.5"), "SOS volume ratio included"
    assert signal.lps_volume_ratio == Decimal("0.6"), "LPS volume ratio included"
    assert signal.phase == "D", "Phase context included"

    # Verify pattern_data structure
    pattern_data = signal.pattern_data
    assert "sos" in pattern_data
    assert "lps" in pattern_data
    assert pattern_data["sos"]["volume_ratio"] == "2.5"
    assert pattern_data["lps"]["volume_ratio"] == "0.6"
    assert pattern_data["entry_type"] == "LPS_ENTRY"
    assert "entry_rationale" in pattern_data


# Test AC 7: Campaign linkage
def test_campaign_linkage_spring_sos_progression(lps_pattern, sos_breakout, trading_range):
    """Test AC 7: Spring→SOS campaign linkage."""
    # Arrange
    spring_campaign_id = uuid4()

    # Act
    signal = generate_lps_signal(
        lps_pattern, sos_breakout, trading_range, confidence=85, campaign_id=spring_campaign_id
    )

    # Assert (AC 7)
    assert signal is not None
    assert signal.campaign_id == spring_campaign_id, "Should link to Spring campaign"
    assert signal.has_campaign, "Campaign linkage should be set"


# Test boundary R-multiple (exactly 2.0R)
def test_boundary_r_multiple_2_0(lps_pattern, sos_breakout, trading_range):
    """Test boundary R-multiple (exactly 2.0R should pass)."""
    # Arrange: Setup to produce exactly 2.0R
    # Entry: $101, Stop: $97 (risk $4)
    # Target: $109 (reward $8)
    # R-multiple: $8 / $4 = 2.0R (exactly at boundary)

    # Update jump price to create exactly 2.0R
    trading_range.jump.price = Decimal("109.00")

    # Act
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    # Assert
    assert signal is not None, "2.0R exactly should pass (minimum requirement)"
    assert signal.r_multiple == Decimal("2.0"), "R-multiple should be exactly 2.0R"
    assert signal.validate_r_multiple(), "Should pass R-multiple validation"


# Test invalid risk (stop >= entry)
def test_invalid_risk_stop_above_entry(sos_breakout, trading_range):
    """Test invalid risk scenario where stop >= entry."""
    # Arrange: Create invalid SOS where breakout is below Ice
    invalid_sos = SOSBreakout(
        bar=sos_breakout.bar,
        breakout_pct=Decimal("0.01"),
        volume_ratio=Decimal("2.0"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("95.00"),  # Below Ice (invalid)
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.3"),
        close_position=Decimal("0.6"),
        spread=Decimal("2.00"),
    )

    # Act
    signal = generate_sos_direct_signal(invalid_sos, trading_range, confidence=80)

    # Assert
    assert signal is None, "Should reject when risk <= 0 (stop >= entry)"


# Test missing Jump level
def test_missing_jump_level(lps_pattern, sos_breakout, trading_range):
    """Test error when Jump level is missing."""
    # Arrange: Remove Jump level
    trading_range.jump = None

    # Act / Assert
    with pytest.raises(ValueError, match="Jump level required"):
        generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)


# Test missing Ice level
def test_missing_ice_level(lps_pattern, sos_breakout, trading_range):
    """Test error when Ice level is missing."""
    # Arrange: Remove Ice level
    trading_range.ice = None

    # Act / Assert
    with pytest.raises(ValueError, match="Ice level required"):
        generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)


# Test AC 10: JSON serialization
def test_sos_signal_json_serialization(lps_pattern, sos_breakout, trading_range):
    """Test AC 10: Signals serializable to JSON."""
    import json

    # Arrange
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    # Act: Serialize to JSON
    signal_dict = signal.model_dump()
    json_string = json.dumps(signal_dict, default=str)

    # Assert (AC 10)
    assert json_string is not None, "Signal should serialize to JSON"

    # Deserialize and verify
    deserialized = json.loads(json_string)

    assert deserialized["symbol"] == signal.symbol
    assert deserialized["entry_type"] == "LPS_ENTRY"
    assert Decimal(deserialized["entry_price"]) == signal.entry_price
    assert Decimal(deserialized["r_multiple"]) == signal.r_multiple

    # Verify Pydantic can reconstruct from dict
    reconstructed_signal = SOSSignal(**signal.model_dump())
    assert reconstructed_signal.entry_price == signal.entry_price


# Test helper methods
def test_helper_methods(lps_pattern, sos_breakout, trading_range):
    """Test helper methods on SOSSignal."""
    # Arrange
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    # Assert
    assert signal.is_lps_entry is True
    assert signal.is_sos_direct_entry is False
    assert signal.get_risk_distance() == Decimal("4.00")
    assert signal.get_reward_distance() == Decimal("19.00")
    assert signal.validate_r_multiple() is True
    assert signal.stop_distance_pct > Decimal("0")


# Test SOS direct entry helper methods
def test_sos_direct_helper_methods(sos_breakout, trading_range):
    """Test helper methods for SOS direct entry."""
    # Arrange
    signal = generate_sos_direct_signal(sos_breakout, trading_range, confidence=80)

    # Assert
    assert signal.is_lps_entry is False
    assert signal.is_sos_direct_entry is True
    assert signal.has_campaign is False


# Test campaign linkage helper
def test_check_spring_campaign_linkage_no_repository(trading_range):
    """Test campaign linkage with no repository."""
    # Act
    campaign_id = check_spring_campaign_linkage(trading_range, None)

    # Assert
    assert campaign_id is None


# Test SOS direct signal R-multiple calculation
def test_sos_direct_r_multiple_realistic(sos_breakout, trading_range):
    """Test SOS direct R-multiple is realistic but lower than LPS."""
    # Act
    signal = generate_sos_direct_signal(sos_breakout, trading_range, confidence=80)

    # Assert
    assert signal is not None
    # SOS: Entry $102, Stop $95, Target $120
    # Risk: $7, Reward: $18
    # R-multiple: $18 / $7 = 2.5714R
    assert signal.r_multiple >= Decimal("2.0")  # Meets minimum
    assert signal.r_multiple < Decimal("4.75")  # Below LPS R-multiple (4.75R)


# Test confidence bounds
def test_confidence_validation(lps_pattern, sos_breakout, trading_range):
    """Test confidence score validation."""
    # Valid confidence
    signal = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)
    assert signal.confidence == 85

    # Boundary cases
    signal_low = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=0)
    assert signal_low.confidence == 0

    signal_high = generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=100)
    assert signal_high.confidence == 100
