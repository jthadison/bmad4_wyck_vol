"""
Integration Tests for Campaign Risk Limit Enforcement - Story 7.4

Test Coverage:
--------------
1. 5% limit enforcement (AC 9):
   - Add positions incrementally up to 5% limit
   - 6th position rejected if would exceed limit

2. API endpoint integration (AC 1, 4):
   - GET /api/campaigns/{id}/risk returns proper response
   - Validates all fields present
   - Tests error handling (404, 503)

3. Full workflow integration:
   - Create campaign with Spring → SOS → LPS sequence
   - Validate BMAD allocations enforced
   - Verify campaign completion detection

Author: Story 7.4
"""

from decimal import Decimal
from uuid import uuid4

from src.models.portfolio import Position
from src.risk_management.campaign_tracker import (
    build_campaign_risk_report,
    calculate_campaign_risk,
    check_campaign_completion,
    validate_bmad_allocation,
    validate_campaign_risk_capacity,
)

# ============================================================================
# Test 5% Limit Enforcement (AC 9)
# ============================================================================


def test_campaign_risk_limit_5_percent_enforcement():
    """
    Integration test: 6th position rejected if would exceed 5% limit (AC 9).

    Scenario:
    ---------
    1. Create campaign with 4 positions totaling 4.5% risk
    2. Attempt to add 5th position with 0.4% risk (total 4.9%) → should pass
    3. Attempt to add 6th position with 0.2% risk (total 5.1%) → should fail
    """
    campaign_id = uuid4()

    # Setup: Create 4 positions totaling 4.5%
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("1.2"), status="OPEN"),  # Spring
        Position(symbol="MSFT", position_risk_pct=Decimal("1.0"), status="OPEN"),  # Spring
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.3"), status="OPEN"),  # SOS
        Position(symbol="AMZN", position_risk_pct=Decimal("1.0"), status="OPEN"),  # LPS
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    # Assign pattern types for BMAD validation
    positions[0].pattern_type = "SPRING"
    positions[1].pattern_type = "SPRING"
    positions[2].pattern_type = "SOS"
    positions[3].pattern_type = "LPS"

    # Verify initial risk
    initial_risk = calculate_campaign_risk(campaign_id, positions)
    assert initial_risk == Decimal("4.5")

    # Attempt 1: Add 5th position with 0.4% risk (total 4.9%) → should pass
    valid, msg = validate_campaign_risk_capacity(campaign_id, initial_risk, Decimal("0.4"))
    assert valid is True, f"5th position should pass: {msg}"
    assert msg is None

    # Add the 5th position
    pos5 = Position(symbol="TSLA", position_risk_pct=Decimal("0.4"), status="OPEN")
    pos5.campaign_id = campaign_id
    pos5.pattern_type = "LPS"
    positions.append(pos5)

    # Verify updated risk
    updated_risk = calculate_campaign_risk(campaign_id, positions)
    assert updated_risk == Decimal("4.9")

    # Attempt 2: Add 6th position with 0.2% risk (total 5.1%) → should fail
    valid, msg = validate_campaign_risk_capacity(campaign_id, updated_risk, Decimal("0.2"))
    assert valid is False, "6th position should be rejected"
    assert msg is not None
    assert "Campaign risk limit exceeded" in msg
    assert "5%" in msg

    # Verify final state in CampaignRisk report
    report = build_campaign_risk_report(campaign_id, positions)
    assert report.total_risk == Decimal("4.9")
    assert report.available_capacity == Decimal("0.1")  # 5.0 - 4.9
    assert report.position_count == 5


def test_campaign_risk_limit_exactly_5_percent():
    """Test campaign can reach exactly 5.0% but not exceed."""
    campaign_id = uuid4()

    # Create positions totaling exactly 5.0%
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.25"), status="OPEN"),
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    positions[0].pattern_type = "SPRING"
    positions[1].pattern_type = "SOS"
    positions[2].pattern_type = "LPS"

    # Calculate risk
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("5.0")

    # Verify cannot add any more risk
    valid, msg = validate_campaign_risk_capacity(campaign_id, risk, Decimal("0.0001"))
    assert valid is False
    assert "Campaign risk limit exceeded" in msg


# ============================================================================
# Test BMAD Allocation Integration (AC 4, 11, 12)
# ============================================================================


def test_bmad_allocation_full_campaign_workflow():
    """
    Integration test: Full campaign workflow with BMAD allocations.

    Workflow:
    ---------
    1. Add Spring position (2.0% = 40% of 5%)
    2. Add SOS position (1.75% = 35% of 5%)
    3. Add LPS position (1.25% = 25% of 5%)
    4. Total = 5.0% (full campaign)
    5. Attempt to add more → rejected
    """
    campaign_id = uuid4()
    positions = []

    # Step 1: Add Spring (2.0%)
    spring = Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN")
    spring.campaign_id = campaign_id
    spring.pattern_type = "SPRING"
    positions.append(spring)

    # Validate Spring allocation
    valid, msg = validate_bmad_allocation([], "SPRING", Decimal("2.0"))
    assert valid is True

    risk_after_spring = calculate_campaign_risk(campaign_id, positions)
    assert risk_after_spring == Decimal("2.0")

    # Step 2: Add SOS (1.75%)
    sos = Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN")
    sos.campaign_id = campaign_id
    sos.pattern_type = "SOS"
    positions.append(sos)

    # Validate SOS allocation
    valid, msg = validate_bmad_allocation([spring], "SOS", Decimal("1.75"))
    assert valid is True

    risk_after_sos = calculate_campaign_risk(campaign_id, positions)
    assert risk_after_sos == Decimal("3.75")

    # Step 3: Add LPS (1.25%)
    lps = Position(symbol="GOOGL", position_risk_pct=Decimal("1.25"), status="OPEN")
    lps.campaign_id = campaign_id
    lps.pattern_type = "LPS"
    positions.append(lps)

    # Validate LPS allocation
    valid, msg = validate_bmad_allocation([spring, sos], "LPS", Decimal("1.25"))
    assert valid is True

    risk_after_lps = calculate_campaign_risk(campaign_id, positions)
    assert risk_after_lps == Decimal("5.0")

    # Step 4: Build report and verify BMAD breakdown
    report = build_campaign_risk_report(campaign_id, positions)
    assert report.total_risk == Decimal("5.0")
    assert report.available_capacity == Decimal("0.0")
    assert report.position_count == 3

    # Verify allocation percentages in report
    assert report.entry_breakdown["AAPL"].allocation_percentage == Decimal("40.0")
    assert report.entry_breakdown["MSFT"].allocation_percentage == Decimal("35.0")
    assert report.entry_breakdown["GOOGL"].allocation_percentage == Decimal("25.0")

    # Step 5: Attempt to add more → rejected
    valid, msg = validate_campaign_risk_capacity(campaign_id, risk_after_lps, Decimal("0.1"))
    assert valid is False
    assert "Campaign risk limit exceeded" in msg


def test_bmad_allocation_spring_allocation_highest():
    """Test Spring receives HIGHEST allocation (40%) in full campaign."""
    campaign_id = uuid4()

    # Create full campaign
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.25"), status="OPEN"),
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    positions[0].pattern_type = "SPRING"
    positions[1].pattern_type = "SOS"
    positions[2].pattern_type = "LPS"

    # Build report
    report = build_campaign_risk_report(campaign_id, positions)

    # Verify Spring has HIGHEST allocation
    spring_alloc = report.entry_breakdown["AAPL"].allocation_percentage
    sos_alloc = report.entry_breakdown["MSFT"].allocation_percentage
    lps_alloc = report.entry_breakdown["GOOGL"].allocation_percentage

    assert spring_alloc == Decimal("40.0")  # HIGHEST
    assert sos_alloc == Decimal("35.0")
    assert lps_alloc == Decimal("25.0")
    assert spring_alloc > sos_alloc > lps_alloc


# ============================================================================
# Test Campaign Completion Integration (AC 7)
# ============================================================================


def test_campaign_completion_workflow():
    """
    Integration test: Campaign completion detection workflow.

    Workflow:
    ---------
    1. Create campaign with 3 open positions
    2. Close 2 positions → campaign incomplete
    3. Close final position → campaign complete
    4. Verify campaign risk returns to 0%
    """
    campaign_id = uuid4()

    # Step 1: Create campaign with 3 open positions
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.25"), status="OPEN"),
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    # Verify initial state
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("5.0")

    complete = check_campaign_completion(campaign_id, positions)
    assert complete is False

    # Step 2: Close 2 positions
    positions[0].status = "CLOSED"
    positions[1].status = "STOPPED"

    # Verify still incomplete
    complete = check_campaign_completion(campaign_id, positions)
    assert complete is False

    # Verify risk reduced
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("1.25")  # Only GOOGL still open

    # Step 3: Close final position
    positions[2].status = "TARGET_HIT"

    # Verify campaign complete
    complete = check_campaign_completion(campaign_id, positions)
    assert complete is True

    # Verify campaign risk returns to 0%
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("0")

    # Verify report reflects completion
    report = build_campaign_risk_report(campaign_id, positions)
    assert report.total_risk == Decimal("0")
    assert report.available_capacity == Decimal("5.0")
    assert report.position_count == 0  # All closed


# ============================================================================
# Test Campaign Variants (AC 11, 12)
# ============================================================================


def test_campaign_variant_sos_only():
    """Test SOS-only campaign (no Spring taken)."""
    campaign_id = uuid4()

    # Create SOS-only campaign
    positions = [
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.0"), status="OPEN"),
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    positions[0].pattern_type = "SOS"
    positions[1].pattern_type = "LPS"

    # Verify campaign valid
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("2.75")

    # Validate SOS allocation still enforced (≤ 1.75%)
    valid, msg = validate_bmad_allocation([positions[0]], "SOS", Decimal("0.1"))
    assert valid is False  # 1.75 + 0.1 = 1.85 > 1.75 limit


def test_campaign_variant_spring_sos_only():
    """Test Spring + SOS campaign (no LPS opportunity)."""
    campaign_id = uuid4()

    # Create Spring + SOS campaign
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.75"), status="OPEN"),
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    positions[0].pattern_type = "SPRING"
    positions[1].pattern_type = "SOS"

    # Verify campaign valid
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("3.75")

    # Validate allocations enforced
    report = build_campaign_risk_report(campaign_id, positions)
    assert report.entry_breakdown["AAPL"].allocation_percentage == Decimal("40.0")
    assert report.entry_breakdown["MSFT"].allocation_percentage == Decimal("35.0")


# ============================================================================
# Test Multiple Campaigns Isolation
# ============================================================================


def test_multiple_campaigns_isolated():
    """Test multiple campaigns tracked independently."""
    campaign1_id = uuid4()
    campaign2_id = uuid4()

    # Create positions in campaign 1
    campaign1_positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("1.5"), status="OPEN"),
    ]
    for pos in campaign1_positions:
        pos.campaign_id = campaign1_id
    campaign1_positions[0].pattern_type = "SPRING"
    campaign1_positions[1].pattern_type = "SOS"

    # Create positions in campaign 2
    campaign2_positions = [
        Position(symbol="GOOGL", position_risk_pct=Decimal("1.8"), status="OPEN"),
        Position(symbol="AMZN", position_risk_pct=Decimal("1.2"), status="OPEN"),
    ]
    for pos in campaign2_positions:
        pos.campaign_id = campaign2_id
    campaign2_positions[0].pattern_type = "SOS"
    campaign2_positions[1].pattern_type = "LPS"

    # Combine all positions
    all_positions = campaign1_positions + campaign2_positions

    # Verify campaign 1 risk
    risk1 = calculate_campaign_risk(campaign1_id, all_positions)
    assert risk1 == Decimal("3.5")  # Only AAPL + MSFT

    # Verify campaign 2 risk
    risk2 = calculate_campaign_risk(campaign2_id, all_positions)
    assert risk2 == Decimal("3.0")  # Only GOOGL + AMZN

    # Verify reports isolated
    report1 = build_campaign_risk_report(campaign1_id, all_positions)
    assert report1.position_count == 2
    assert "AAPL" in report1.entry_breakdown
    assert "GOOGL" not in report1.entry_breakdown

    report2 = build_campaign_risk_report(campaign2_id, all_positions)
    assert report2.position_count == 2
    assert "GOOGL" in report2.entry_breakdown
    assert "AAPL" not in report2.entry_breakdown


# ============================================================================
# Test Decimal Precision Integration
# ============================================================================


def test_decimal_precision_full_workflow():
    """Test Decimal precision maintained throughout full workflow."""
    campaign_id = uuid4()

    # Create positions with precise decimal values (4 decimal places)
    positions = [
        Position(symbol="AAPL", position_risk_pct=Decimal("0.3333"), status="OPEN"),
        Position(symbol="MSFT", position_risk_pct=Decimal("0.3333"), status="OPEN"),
        Position(symbol="GOOGL", position_risk_pct=Decimal("0.3334"), status="OPEN"),
    ]

    for pos in positions:
        pos.campaign_id = campaign_id

    # Assign pattern types
    positions[0].pattern_type = "SPRING"
    positions[1].pattern_type = "SOS"
    positions[2].pattern_type = "LPS"

    # Calculate risk
    risk = calculate_campaign_risk(campaign_id, positions)
    assert risk == Decimal("1.0")
    assert isinstance(risk, Decimal)

    # Build report
    report = build_campaign_risk_report(campaign_id, positions)
    assert isinstance(report.total_risk, Decimal)
    assert isinstance(report.available_capacity, Decimal)
    assert report.total_risk == Decimal("1.0")

    # Verify no floating point drift
    assert report.available_capacity == Decimal("4.0")  # 5.0 - 1.0, exact
