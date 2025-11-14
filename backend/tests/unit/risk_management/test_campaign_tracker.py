"""
Unit Tests for Campaign Risk Tracking - Story 7.4

Test Coverage:
--------------
1. calculate_campaign_risk (AC 8):
   - Empty campaign (no positions)
   - Single position
   - Multiple positions (Spring + SOS + LPS)
   - Closed positions don't contribute
   - Different campaign_ids don't accumulate

2. BMAD allocation validation (AC 4, 11, 12):
   - Spring 40% allocation (2.0% max) - HIGHEST
   - SOS 35% allocation (1.75% max)
   - LPS 25% allocation (1.25% max)
   - ST pattern rejection (confirmation event, not entry)
   - Full campaign scenario
   - Campaign variants (SOS-only, Spring+SOS)

3. Campaign risk validation (AC 6):
   - Validation passes
   - Validation fails (exceeds 5% limit)
   - Boundary conditions (exactly 5.0%, 5.0001%)
   - campaign_id is None (no constraint)

4. Proximity warnings (AC 10):
   - Below threshold (no warning)
   - At threshold (warning triggered)
   - Above threshold (warning triggered)

5. Campaign completion (AC 7):
   - All positions closed
   - Mixed open/closed positions
   - Empty campaign

Author: Story 7.4
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.models.portfolio import Position
from src.risk_management.campaign_tracker import (
    build_campaign_risk_report,
    calculate_campaign_risk,
    check_campaign_completion,
    check_campaign_proximity_warning,
    validate_bmad_allocation,
    validate_campaign_risk_capacity,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def campaign_id() -> UUID:
    """Generate consistent campaign ID for tests."""
    return uuid4()


@pytest.fixture
def other_campaign_id() -> UUID:
    """Generate different campaign ID for isolation tests."""
    return uuid4()


@pytest.fixture
def spring_position(campaign_id: UUID) -> Position:
    """Create Spring position (40% allocation, 2.0% risk)."""
    pos = Position(
        symbol="AAPL",
        position_risk_pct=Decimal("2.0"),
        status="OPEN",
        wyckoff_phase="C",
        volume_confirmation_score=Decimal("35.0"),
        sector="Technology",
    )
    pos.campaign_id = campaign_id
    pos.pattern_type = "SPRING"
    return pos


@pytest.fixture
def sos_position(campaign_id: UUID) -> Position:
    """Create SOS position (35% allocation, 1.75% risk)."""
    pos = Position(
        symbol="MSFT",
        position_risk_pct=Decimal("1.75"),
        status="OPEN",
        wyckoff_phase="D",
        volume_confirmation_score=Decimal("30.0"),
        sector="Technology",
    )
    pos.campaign_id = campaign_id
    pos.pattern_type = "SOS"
    return pos


@pytest.fixture
def lps_position(campaign_id: UUID) -> Position:
    """Create LPS position (25% allocation, 1.25% risk)."""
    pos = Position(
        symbol="GOOGL",
        position_risk_pct=Decimal("1.25"),
        status="OPEN",
        wyckoff_phase="D",
        volume_confirmation_score=Decimal("28.0"),
        sector="Technology",
    )
    pos.campaign_id = campaign_id
    pos.pattern_type = "LPS"
    return pos


# ============================================================================
# Test calculate_campaign_risk (AC 1, 5, 8)
# ============================================================================


def test_calculate_campaign_risk_empty_campaign(campaign_id: UUID):
    """Test empty campaign (no positions) returns 0% risk."""
    positions = []
    risk = calculate_campaign_risk(campaign_id, positions)

    assert risk == Decimal("0")
    assert isinstance(risk, Decimal)


def test_calculate_campaign_risk_single_spring(campaign_id: UUID, spring_position: Position):
    """Test single Spring position returns correct risk."""
    positions = [spring_position]
    risk = calculate_campaign_risk(campaign_id, positions)

    assert risk == Decimal("2.0")
    assert isinstance(risk, Decimal)


def test_calculate_campaign_risk_spring_sos_lps(
    campaign_id: UUID,
    spring_position: Position,
    sos_position: Position,
    lps_position: Position,
):
    """Test Spring + SOS + LPS in same campaign accumulates correctly (AC 8)."""
    positions = [spring_position, sos_position, lps_position]
    risk = calculate_campaign_risk(campaign_id, positions)

    # 2.0 + 1.75 + 1.25 = 5.0
    assert risk == Decimal("5.0")
    assert isinstance(risk, Decimal)


def test_calculate_campaign_risk_closed_positions_ignored(
    campaign_id: UUID, spring_position: Position
):
    """Test closed positions don't contribute to campaign risk."""
    spring_position.status = "CLOSED"
    positions = [spring_position]
    risk = calculate_campaign_risk(campaign_id, positions)

    assert risk == Decimal("0")


def test_calculate_campaign_risk_different_campaigns_isolated(
    campaign_id: UUID, other_campaign_id: UUID, spring_position: Position
):
    """Test positions with different campaign_ids don't accumulate together."""
    # Position in different campaign
    other_pos = Position(
        symbol="TSLA",
        position_risk_pct=Decimal("1.5"),
        status="OPEN",
    )
    other_pos.campaign_id = other_campaign_id
    other_pos.pattern_type = "SOS"

    positions = [spring_position, other_pos]
    risk = calculate_campaign_risk(campaign_id, positions)

    # Should only count spring_position (2.0), not other_pos
    assert risk == Decimal("2.0")


def test_calculate_campaign_risk_none_campaign_id():
    """Test campaign_id=None returns 0% (no campaign constraint)."""
    risk = calculate_campaign_risk(None, [])
    assert risk == Decimal("0")


def test_calculate_campaign_risk_decimal_precision(campaign_id: UUID):
    """Test Decimal precision maintained (no floating point drift)."""
    pos1 = Position(
        symbol="AAPL",
        position_risk_pct=Decimal("0.333333"),
        status="OPEN",
    )
    pos1.campaign_id = campaign_id

    pos2 = Position(
        symbol="MSFT",
        position_risk_pct=Decimal("0.333333"),
        status="OPEN",
    )
    pos2.campaign_id = campaign_id

    pos3 = Position(
        symbol="GOOGL",
        position_risk_pct=Decimal("0.333334"),
        status="OPEN",
    )
    pos3.campaign_id = campaign_id

    positions = [pos1, pos2, pos3]
    risk = calculate_campaign_risk(campaign_id, positions)

    # Exact Decimal addition: 0.333333 + 0.333333 + 0.333334 = 1.0
    assert risk == Decimal("1.0")
    assert isinstance(risk, Decimal)


# ============================================================================
# Test BMAD Allocation Validation (AC 4, 11, 12)
# ============================================================================


def test_bmad_allocation_spring_40_percent():
    """Test Spring 40% allocation = max 2.0% of 5% limit (HIGHEST)."""
    # Spring with 1.5% existing
    existing = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
        )
    ]
    existing[0].pattern_type = "SPRING"

    # Try to add 0.5% more Spring (total 2.0% = exactly at limit)
    valid, msg = validate_bmad_allocation(existing, "SPRING", Decimal("0.5"))
    assert valid is True
    assert msg is None

    # Try to add 0.6% more Spring (total 2.1% > 2.0% limit)
    valid, msg = validate_bmad_allocation(existing, "SPRING", Decimal("0.6"))
    assert valid is False
    assert "SPRING allocation exceeded" in msg
    assert "2.00%" in msg or "2.0%" in msg  # Max allocation mentioned


def test_bmad_allocation_sos_35_percent():
    """Test SOS 35% allocation = max 1.75% of 5% limit."""
    # SOS with 1.0% existing
    existing = [
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("1.0"),
            status="OPEN",
        )
    ]
    existing[0].pattern_type = "SOS"

    # Try to add 0.75% more SOS (total 1.75% = exactly at limit)
    valid, msg = validate_bmad_allocation(existing, "SOS", Decimal("0.75"))
    assert valid is True
    assert msg is None

    # Try to add 0.76% more SOS (total 1.76% > 1.75% limit)
    valid, msg = validate_bmad_allocation(existing, "SOS", Decimal("0.76"))
    assert valid is False
    assert "SOS allocation exceeded" in msg
    assert "1.75%" in msg


def test_bmad_allocation_lps_25_percent():
    """Test LPS 25% allocation = max 1.25% of 5% limit."""
    # LPS with 1.0% existing
    existing = [
        Position(
            symbol="GOOGL",
            position_risk_pct=Decimal("1.0"),
            status="OPEN",
        )
    ]
    existing[0].pattern_type = "LPS"

    # Try to add 0.25% more LPS (total 1.25% = exactly at limit)
    valid, msg = validate_bmad_allocation(existing, "LPS", Decimal("0.25"))
    assert valid is True
    assert msg is None

    # Try to add 0.26% more LPS (total 1.26% > 1.25% limit)
    valid, msg = validate_bmad_allocation(existing, "LPS", Decimal("0.26"))
    assert valid is False
    assert "LPS allocation exceeded" in msg
    assert "1.25%" in msg


def test_bmad_allocation_st_rejected():
    """Test ST pattern rejected (confirmation event, not entry) (AC 4)."""
    existing = []

    # Try to create ST entry
    valid, msg = validate_bmad_allocation(existing, "ST", Decimal("1.0"))

    assert valid is False
    assert "ST (Secondary Test) is a confirmation event" in msg
    assert "not an entry pattern" in msg
    assert "SPRING, SOS, LPS" in msg


def test_bmad_allocation_full_campaign():
    """Test full campaign (Spring + SOS + LPS) = 5.0% total."""
    existing = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
    ]
    existing[0].pattern_type = "SPRING"
    existing[1].pattern_type = "SOS"

    # Try to add LPS with 1.25% (total 5.0%)
    valid, msg = validate_bmad_allocation(existing, "LPS", Decimal("1.25"))
    assert valid is True
    assert msg is None


def test_bmad_allocation_sos_only_campaign():
    """Test SOS-only campaign (no Spring) = valid."""
    # Campaign with only SOS (no Spring taken)
    existing = [
        Position(symbol="MSFT", position_risk_pct=Decimal("2.9"), status="OPEN"),
    ]
    existing[0].pattern_type = "SOS"

    # SOS can use more than 1.75% if Spring not taken (proportional redistribution)
    # However, per pattern allocation is still enforced
    # This test validates that SOS > 1.75% is rejected per current allocation
    valid, msg = validate_bmad_allocation(existing, "SOS", Decimal("0.1"))
    assert valid is False  # 2.9 + 0.1 = 3.0 > 1.75 limit


def test_bmad_allocation_spring_sos_only():
    """Test Spring + SOS campaign (no LPS) = valid."""
    existing = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
    ]
    existing[0].pattern_type = "SPRING"
    existing[1].pattern_type = "SOS"

    # Try to add more SOS (should fail - already at limit)
    valid, msg = validate_bmad_allocation(existing, "SOS", Decimal("0.1"))
    assert valid is False


def test_bmad_allocation_invalid_pattern():
    """Test invalid pattern type rejected."""
    existing = []

    valid, msg = validate_bmad_allocation(existing, "INVALID", Decimal("1.0"))

    assert valid is False
    assert "Invalid pattern type" in msg


def test_bmad_allocation_closed_positions_ignored():
    """Test closed positions don't count toward allocation."""
    existing = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="CLOSED"),
    ]
    existing[0].pattern_type = "SPRING"

    # Try to add 2.0% Spring (should pass - closed position ignored)
    valid, msg = validate_bmad_allocation(existing, "SPRING", Decimal("2.0"))
    assert valid is True
    assert msg is None


# ============================================================================
# Test Campaign Risk Validation (AC 2, 6)
# ============================================================================


def test_validate_campaign_risk_capacity_passes():
    """Test validation passes when within 5% limit."""
    campaign_id = uuid4()
    valid, msg = validate_campaign_risk_capacity(campaign_id, Decimal("4.0"), Decimal("0.5"))

    assert valid is True
    assert msg is None


def test_validate_campaign_risk_capacity_fails():
    """Test validation fails when exceeds 5% limit."""
    campaign_id = uuid4()
    valid, msg = validate_campaign_risk_capacity(campaign_id, Decimal("4.8"), Decimal("0.3"))

    assert valid is False
    assert "Campaign risk limit exceeded" in msg
    assert "5%" in msg


def test_validate_campaign_risk_capacity_exactly_5_percent():
    """Test exactly 5.0% campaign risk passes (boundary condition)."""
    campaign_id = uuid4()
    valid, msg = validate_campaign_risk_capacity(campaign_id, Decimal("4.5"), Decimal("0.5"))

    assert valid is True
    assert msg is None


def test_validate_campaign_risk_capacity_5_0001_percent():
    """Test 5.0001% campaign risk fails (boundary condition)."""
    campaign_id = uuid4()
    valid, msg = validate_campaign_risk_capacity(campaign_id, Decimal("5.0"), Decimal("0.0001"))

    assert valid is False
    assert "Campaign risk limit exceeded" in msg


def test_validate_campaign_risk_capacity_none_campaign_id():
    """Test campaign_id=None passes validation (no campaign constraint)."""
    valid, msg = validate_campaign_risk_capacity(None, Decimal("10.0"), Decimal("5.0"))

    assert valid is True
    assert msg is None


# ============================================================================
# Test Proximity Warnings (AC 10)
# ============================================================================


def test_proximity_warning_below_threshold():
    """Test 3.9% risk returns no warning."""
    warning = check_campaign_proximity_warning(Decimal("3.9"))
    assert warning is None


def test_proximity_warning_at_threshold():
    """Test 4.0% risk triggers warning (80% of 5% limit)."""
    warning = check_campaign_proximity_warning(Decimal("4.0"))

    assert warning is not None
    assert "4.0%" in warning
    assert "80%" in warning


def test_proximity_warning_above_threshold():
    """Test 4.8% risk triggers warning."""
    warning = check_campaign_proximity_warning(Decimal("4.8"))

    assert warning is not None
    assert "4.8%" in warning


def test_proximity_warning_message_format():
    """Test warning message includes actual risk percentage."""
    warning = check_campaign_proximity_warning(Decimal("4.2"))

    assert warning is not None
    assert "Campaign risk at 4.2%" in warning
    assert "80% of 5% limit" in warning


# ============================================================================
# Test Campaign Completion (AC 7)
# ============================================================================


def test_campaign_completion_all_closed(campaign_id: UUID):
    """Test all positions closed returns True (campaign complete)."""
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="CLOSED"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.5"), status="STOPPED"),
    ]
    positions[0].campaign_id = campaign_id
    positions[1].campaign_id = campaign_id

    complete = check_campaign_completion(campaign_id, positions)
    assert complete is True


def test_campaign_completion_mixed_open_closed(campaign_id: UUID):
    """Test 2 closed + 1 open returns False (campaign incomplete)."""
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="CLOSED"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.5"), status="STOPPED"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.0"), status="OPEN"),
    ]
    for pos in positions:
        pos.campaign_id = campaign_id

    complete = check_campaign_completion(campaign_id, positions)
    assert complete is False


def test_campaign_completion_mixed_statuses(campaign_id: UUID):
    """Test positions with STOPPED, TARGET_HIT, EXPIRED count as closed."""
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="STOPPED"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.5"), status="TARGET_HIT"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.0"), status="EXPIRED"),
    ]
    for pos in positions:
        pos.campaign_id = campaign_id

    complete = check_campaign_completion(campaign_id, positions)
    assert complete is True


def test_campaign_completion_empty_campaign(campaign_id: UUID):
    """Test empty campaign (no positions) returns True (complete)."""
    positions = []
    complete = check_campaign_completion(campaign_id, positions)
    assert complete is True


# ============================================================================
# Test build_campaign_risk_report (AC 1, 4, 7)
# ============================================================================


def test_build_campaign_risk_report_full_campaign(
    campaign_id: UUID,
    spring_position: Position,
    sos_position: Position,
    lps_position: Position,
):
    """Test comprehensive report with Spring + SOS + LPS."""
    positions = [spring_position, sos_position, lps_position]
    report = build_campaign_risk_report(campaign_id, positions)

    # Verify core fields
    assert report.campaign_id == campaign_id
    assert report.total_risk == Decimal("5.0")  # 2.0 + 1.75 + 1.25
    assert report.available_capacity == Decimal("0.0")  # 5.0 - 5.0
    assert report.position_count == 3

    # Verify entry_breakdown
    assert len(report.entry_breakdown) == 3
    assert "AAPL" in report.entry_breakdown
    assert "MSFT" in report.entry_breakdown
    assert "GOOGL" in report.entry_breakdown

    # Verify BMAD allocation percentages
    spring_entry = report.entry_breakdown["AAPL"]
    assert spring_entry.pattern_type == "SPRING"
    assert spring_entry.allocation_percentage == Decimal("40.0")
    assert spring_entry.position_risk_pct == Decimal("2.0")

    sos_entry = report.entry_breakdown["MSFT"]
    assert sos_entry.pattern_type == "SOS"
    assert sos_entry.allocation_percentage == Decimal("35.0")
    assert sos_entry.position_risk_pct == Decimal("1.75")

    lps_entry = report.entry_breakdown["GOOGL"]
    assert lps_entry.pattern_type == "LPS"
    assert lps_entry.allocation_percentage == Decimal("25.0")
    assert lps_entry.position_risk_pct == Decimal("1.25")


def test_build_campaign_risk_report_empty_campaign(campaign_id: UUID):
    """Test report with empty campaign."""
    positions = []
    report = build_campaign_risk_report(campaign_id, positions)

    assert report.campaign_id == campaign_id
    assert report.total_risk == Decimal("0")
    assert report.available_capacity == Decimal("5.0")
    assert report.position_count == 0
    assert len(report.entry_breakdown) == 0


def test_build_campaign_risk_report_spring_allocation_highest(
    campaign_id: UUID, spring_position: Position
):
    """Test Spring receives HIGHEST allocation (40%) in report."""
    positions = [spring_position]
    report = build_campaign_risk_report(campaign_id, positions)

    spring_entry = report.entry_breakdown["AAPL"]
    assert spring_entry.allocation_percentage == Decimal("40.0")  # HIGHEST


def test_build_campaign_risk_report_decimal_serialization(
    campaign_id: UUID, spring_position: Position
):
    """Test Decimal values preserved in report (no float conversion)."""
    positions = [spring_position]
    report = build_campaign_risk_report(campaign_id, positions)

    assert isinstance(report.total_risk, Decimal)
    assert isinstance(report.available_capacity, Decimal)
    assert isinstance(report.entry_breakdown["AAPL"].position_risk_pct, Decimal)
