"""
Unit Tests for CampaignAllocator - BMAD Position Allocation (Story 9.2)

Test Coverage:
--------------
AC: 2 - BMAD allocation percentages (40/30/30)
AC: 5 - Rebalancing when entries skipped
AC: 7 - Rejection when exceeding 5% campaign maximum
AC: 8 - Spring + SOS + LPS stay within 5% total
AC: 9 - Skipped Spring rebalances SOS to larger size
AC: 11, 12 - 100% LPS allocation requires 75% confidence

Test Categories:
----------------
1. Normal BMAD allocation (40/30/30)
2. Rebalancing scenarios (skipped entries)
3. Campaign budget validation (5% max)
4. 75% confidence threshold for 100% LPS
5. Edge cases and error handling
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.campaign_management.allocator import CampaignAllocator, InvalidPatternTypeError
from src.models.allocation import AllocationPlan
from src.models.campaign_lifecycle import Campaign, CampaignPosition, CampaignStatus
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal, ValidationChain

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def portfolio_value():
    """Portfolio value for testing: $100,000."""
    return Decimal("100000.00")


@pytest.fixture
def allocator(portfolio_value):
    """CampaignAllocator instance for testing."""
    return CampaignAllocator(portfolio_value=portfolio_value)


@pytest.fixture
def empty_campaign():
    """Empty campaign with no positions (total_allocation=0%)."""
    return Campaign(
        id=uuid4(),
        campaign_id="AAPL-2024-10-15",
        symbol="AAPL",
        timeframe="1d",
        trading_range_id=uuid4(),
        status=CampaignStatus.ACTIVE,
        phase="C",
        positions=[],
        total_risk=Decimal("0.00"),
        total_allocation=Decimal("0.00"),
        current_risk=Decimal("0.00"),
        weighted_avg_entry=Decimal("0.00"),
        total_shares=Decimal("0"),
        total_pnl=Decimal("0.00"),
        start_date=datetime.now(UTC),
        version=1,
    )


@pytest.fixture
def spring_signal(portfolio_value):
    """
    Spring signal with 0.5% risk ($500 on $100k portfolio).

    Uses FR16 pattern risk: Spring 0.5% of portfolio.
    """
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        risk_amount=Decimal("500.00"),  # 0.5% of $100k
        r_multiple=Decimal("3.0"),
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=80,
            overall_confidence=85,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def sos_signal(portfolio_value):
    """
    SOS signal with 1.0% risk ($1,000 on $100k portfolio).

    Uses FR16 pattern risk: SOS 1.0% of portfolio.
    """
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("155.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("165.00")),
        position_size=Decimal("50"),
        position_size_unit="SHARES",
        risk_amount=Decimal("1000.00"),  # 1.0% of $100k
        r_multiple=Decimal("2.0"),
        confidence_score=82,
        confidence_components=ConfidenceComponents(
            pattern_confidence=85,
            phase_confidence=80,
            volume_confidence=78,
            overall_confidence=82,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def lps_signal(portfolio_value):
    """
    LPS signal with 0.6% risk ($600 on $100k portfolio).

    Uses FR16 pattern risk: LPS 0.6% of portfolio.
    """
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("153.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("162.00")),
        position_size=Decimal("60"),
        position_size_unit="SHARES",
        risk_amount=Decimal("600.00"),  # 0.6% of $100k
        r_multiple=Decimal("2.5"),
        confidence_score=78,
        confidence_components=ConfidenceComponents(
            pattern_confidence=80,
            phase_confidence=77,
            volume_confidence=75,
            overall_confidence=78,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# Test Category 1: Normal BMAD Allocation (40/30/30) - AC: 2
# =============================================================================


def test_spring_gets_40_percent_allocation(allocator, empty_campaign, spring_signal):
    """Test Spring receives 40% BMAD allocation (AC: 2)."""
    plan = allocator.allocate_campaign_risk(empty_campaign, spring_signal)

    assert plan.approved is True
    assert plan.pattern_type == "SPRING"
    assert plan.bmad_allocation_pct == Decimal("0.40")  # 40%
    assert plan.target_risk_pct == Decimal("2.00")  # 40% of 5% = 2.0%
    assert plan.actual_risk_pct == Decimal("0.50")  # FR16: 0.5% of portfolio
    assert plan.allocation_used == Decimal("0.50")
    assert plan.remaining_budget == Decimal("4.50")  # 5.0% - 0.5% = 4.5%
    assert plan.is_rebalanced is False
    assert plan.rebalance_reason is None


def test_sos_gets_30_percent_allocation(allocator, empty_campaign, spring_signal, sos_signal):
    """Test SOS receives 30% BMAD allocation after Spring (AC: 2)."""
    # Add Spring position to campaign
    spring_position = CampaignPosition(
        signal_id=spring_signal.id,
        pattern_type="SPRING",
        entry_date=datetime.now(UTC),
        entry_price=Decimal("150.00"),
        shares=Decimal("100"),
        stop_loss=Decimal("148.00"),
        target_price=Decimal("156.00"),
        current_price=Decimal("150.00"),
        current_pnl=Decimal("0.00"),
        status="OPEN",
        allocation_percent=Decimal("0.50"),
        risk_amount=Decimal("500.00"),
    )
    campaign_with_spring = empty_campaign.model_copy(deep=True)
    campaign_with_spring.positions = [spring_position]
    campaign_with_spring.total_allocation = Decimal("0.50")

    plan = allocator.allocate_campaign_risk(campaign_with_spring, sos_signal)

    assert plan.approved is True
    assert plan.pattern_type == "SOS"
    assert plan.bmad_allocation_pct == Decimal("0.30")  # 30%
    assert plan.target_risk_pct == Decimal("1.50")  # 30% of 5% = 1.5%
    assert plan.actual_risk_pct == Decimal("1.00")  # FR16: 1.0% of portfolio
    assert plan.allocation_used == Decimal("1.00")
    assert plan.remaining_budget == Decimal("3.50")  # 5.0% - 0.5% - 1.0% = 3.5%
    assert plan.is_rebalanced is False


def test_lps_gets_30_percent_allocation(
    allocator, empty_campaign, spring_signal, sos_signal, lps_signal
):
    """Test LPS receives 30% BMAD allocation after Spring + SOS (AC: 2)."""
    # Add Spring and SOS positions to campaign
    campaign_with_spring_sos = empty_campaign.model_copy(deep=True)
    campaign_with_spring_sos.positions = [
        CampaignPosition(
            signal_id=spring_signal.id,
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("0.50"),
            risk_amount=Decimal("500.00"),
        ),
        CampaignPosition(
            signal_id=sos_signal.id,
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("155.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("150.00"),
            target_price=Decimal("165.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("1.00"),
            risk_amount=Decimal("1000.00"),
        ),
    ]
    campaign_with_spring_sos.total_allocation = Decimal("1.50")  # 0.5% + 1.0%

    plan = allocator.allocate_campaign_risk(campaign_with_spring_sos, lps_signal)

    assert plan.approved is True
    assert plan.pattern_type == "LPS"
    assert plan.bmad_allocation_pct == Decimal("0.30")  # 30%
    assert plan.target_risk_pct == Decimal("1.50")  # 30% of 5% = 1.5%
    assert plan.actual_risk_pct == Decimal("0.60")  # FR16: 0.6% of portfolio
    assert plan.allocation_used == Decimal("0.60")
    assert plan.remaining_budget == Decimal("2.90")  # 5.0% - 0.5% - 1.0% - 0.6% = 2.9%
    assert plan.is_rebalanced is False


# =============================================================================
# Test Category 2: Campaign Budget Validation (5% max) - AC: 7, 8
# =============================================================================


def test_spring_sos_lps_stay_within_5_percent(
    allocator, empty_campaign, spring_signal, sos_signal, lps_signal
):
    """
    Test full Spring → SOS → LPS sequence stays within 5% max (AC: 8).

    This validates the complete BMAD allocation:
    - Spring: 0.5% actual (from 40% × 5% = 2.0% target)
    - SOS: 1.0% actual (from 30% × 5% = 1.5% target)
    - LPS: 0.6% actual (from 30% × 5% = 1.5% target)
    - Total: 2.1% < 5.0% ✓
    """
    # Allocate Spring
    spring_plan = allocator.allocate_campaign_risk(empty_campaign, spring_signal)
    assert spring_plan.approved is True
    assert spring_plan.allocation_used == Decimal("0.50")

    # Add Spring to campaign
    campaign_after_spring = empty_campaign.model_copy(deep=True)
    campaign_after_spring.positions = [
        CampaignPosition(
            signal_id=spring_signal.id,
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("0.50"),
            risk_amount=Decimal("500.00"),
        )
    ]
    campaign_after_spring.total_allocation = Decimal("0.50")

    # Allocate SOS
    sos_plan = allocator.allocate_campaign_risk(campaign_after_spring, sos_signal)
    assert sos_plan.approved is True
    assert sos_plan.allocation_used == Decimal("1.00")

    # Add SOS to campaign
    campaign_after_sos = campaign_after_spring.model_copy(deep=True)
    campaign_after_sos.positions.append(
        CampaignPosition(
            signal_id=sos_signal.id,
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("155.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("150.00"),
            target_price=Decimal("165.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("1.00"),
            risk_amount=Decimal("1000.00"),
        )
    )
    campaign_after_sos.total_allocation = Decimal("1.50")  # 0.5% + 1.0%

    # Allocate LPS
    lps_plan = allocator.allocate_campaign_risk(campaign_after_sos, lps_signal)
    assert lps_plan.approved is True
    assert lps_plan.allocation_used == Decimal("0.60")

    # Verify total allocation within 5% maximum
    total_allocation = (
        spring_plan.allocation_used + sos_plan.allocation_used + lps_plan.allocation_used
    )
    assert total_allocation == Decimal("2.10")  # 0.5% + 1.0% + 0.6%
    assert total_allocation < Decimal("5.00")  # Within campaign max ✓


def test_allocation_exceeding_5_percent_rejected(allocator, empty_campaign):
    """Test allocation is rejected when it would exceed 5% campaign maximum (AC: 7)."""
    # Create campaign with 4.8% already allocated
    campaign_near_limit = empty_campaign.model_copy(deep=True)
    campaign_near_limit.total_allocation = Decimal("4.80")

    # Create signal with 1.0% risk (would exceed 5% limit)
    high_risk_signal = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("145.00"),
        target_levels=TargetLevels(primary_target=Decimal("160.00")),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        risk_amount=Decimal("1000.00"),  # 1.0% of $100k
        r_multiple=Decimal("2.0"),
        confidence_score=75,
        confidence_components=ConfidenceComponents(
            pattern_confidence=78,
            phase_confidence=74,
            volume_confidence=72,
            overall_confidence=75,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )

    plan = allocator.allocate_campaign_risk(campaign_near_limit, high_risk_signal)

    # Should be REJECTED
    assert plan.approved is False
    assert "exceeds remaining budget" in plan.rejection_reason
    assert plan.allocation_used == Decimal("1.00")
    assert plan.remaining_budget == Decimal("0.20")  # 5.0% - 4.8% = 0.2% remaining


# =============================================================================
# Test Category 3: Rebalancing Scenarios (Skipped Entries) - AC: 5, 9
# =============================================================================


def test_rebalance_sos_gets_70_percent_when_spring_skipped(allocator, empty_campaign, sos_signal):
    """
    Test SOS gets 70% allocation when Spring skipped (AC: 5, 9).

    Rebalancing logic:
    - Normal: SOS gets 30% (1.5% of 5%)
    - Spring skipped: SOS gets Spring's 40% + its own 30% = 70% (3.5% of 5%)
    """
    # Empty campaign (no Spring position) → Spring was skipped
    plan = allocator.allocate_campaign_risk(empty_campaign, sos_signal)

    assert plan.approved is True
    assert plan.pattern_type == "SOS"
    assert plan.is_rebalanced is True
    assert plan.bmad_allocation_pct == Decimal("0.70")  # 70% = 40% + 30%
    assert plan.target_risk_pct == Decimal("3.50")  # 70% of 5% = 3.5%
    assert "Spring not taken" in plan.rebalance_reason
    # Actual risk still FR16 (1.0% for SOS pattern)
    assert plan.actual_risk_pct == Decimal("1.00")


def test_rebalance_lps_gets_60_percent_when_spring_skipped_sos_taken(
    allocator, empty_campaign, sos_signal, lps_signal
):
    """
    Test LPS gets 60% allocation when Spring skipped but SOS taken (AC: 5, 9).

    Scenario: Campaign has SOS position, but NO Spring
    Rebalancing: LPS gets Spring's unclaimed 40% + LPS's 30% = 60% (but SOS took 30%)
    (Per story spec line 287-293: bmad_allocation_pct == 0.60)
    """
    # Campaign with SOS but NO Spring
    campaign_with_sos_only = empty_campaign.model_copy(deep=True)
    campaign_with_sos_only.positions = [
        CampaignPosition(
            signal_id=sos_signal.id,
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("155.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("150.00"),
            target_price=Decimal("165.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("1.00"),
            risk_amount=Decimal("1000.00"),
        )
    ]
    campaign_with_sos_only.total_allocation = Decimal("1.00")

    plan = allocator.allocate_campaign_risk(campaign_with_sos_only, lps_signal)

    assert plan.approved is True
    assert plan.pattern_type == "LPS"
    assert plan.is_rebalanced is True
    assert plan.bmad_allocation_pct == Decimal("0.60")  # 60% per story spec
    assert "Spring not taken" in plan.rebalance_reason


def test_rebalance_lps_gets_60_percent_when_sos_skipped_spring_taken(
    allocator, empty_campaign, spring_signal, lps_signal
):
    """
    Test LPS gets 60% allocation when SOS skipped but Spring taken (AC: 5).

    Scenario: Campaign has Spring position, but NO SOS
    Rebalancing: LPS gets SOS's unclaimed 30% + LPS's 30% = 60%
    """
    # Campaign with Spring but NO SOS
    campaign_with_spring_only = empty_campaign.model_copy(deep=True)
    campaign_with_spring_only.positions = [
        CampaignPosition(
            signal_id=spring_signal.id,
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("0.50"),
            risk_amount=Decimal("500.00"),
        )
    ]
    campaign_with_spring_only.total_allocation = Decimal("0.50")

    plan = allocator.allocate_campaign_risk(campaign_with_spring_only, lps_signal)

    assert plan.approved is True
    assert plan.pattern_type == "LPS"
    assert plan.is_rebalanced is True
    assert plan.bmad_allocation_pct == Decimal("0.60")  # 60%
    assert "SOS not taken" in plan.rebalance_reason


# =============================================================================
# Test Category 4: 100% LPS Allocation with 75% Confidence (AC: 11, 12)
# =============================================================================


def test_100_percent_lps_sole_entry_72_percent_confidence_rejected(allocator, empty_campaign):
    """
    Test 100% LPS allocation REJECTED with 72% confidence (AC: 12).

    Scenario: Spring AND SOS both skipped, LPS is sole entry
    Requirement: Requires 75% minimum confidence (vs normal 70%)
    Signal: 72% confidence (below threshold)
    Result: REJECTED
    """
    # LPS signal with 72% confidence (below 75% threshold)
    lps_low_confidence = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("153.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("162.00")),
        position_size=Decimal("60"),
        position_size_unit="SHARES",
        risk_amount=Decimal("600.00"),
        notional_value=Decimal("15000.00"),  # position_size * entry_price
        r_multiple=Decimal("2.5"),
        confidence_score=72,  # Below 75% threshold
        confidence_components=ConfidenceComponents(
            pattern_confidence=75,
            phase_confidence=70,
            volume_confidence=68,
            overall_confidence=72,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )

    # Empty campaign (no Spring, no SOS) → LPS would be sole entry
    plan = allocator.allocate_campaign_risk(empty_campaign, lps_low_confidence)

    # Should be REJECTED due to low confidence
    assert plan.approved is False
    assert plan.is_rebalanced is True
    assert plan.bmad_allocation_pct == Decimal("1.00")  # Would be 100%
    assert "100% LPS allocation requires 75% minimum confidence" in plan.rejection_reason
    assert "signal has 72%" in plan.rejection_reason


def test_100_percent_lps_sole_entry_75_percent_confidence_approved(allocator, empty_campaign):
    """
    Test 100% LPS allocation APPROVED with 75% confidence (AC: 12).

    Scenario: Spring AND SOS both skipped, LPS is sole entry
    Requirement: Requires 75% minimum confidence
    Signal: 75% confidence (meets threshold)
    Result: APPROVED with 100% allocation
    """
    # LPS signal with 75% confidence (meets threshold)
    lps_high_confidence = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("153.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("162.00")),
        position_size=Decimal("200"),  # Larger position for 100% allocation
        position_size_unit="SHARES",
        risk_amount=Decimal("2000.00"),  # ~2% of portfolio
        r_multiple=Decimal("2.5"),
        confidence_score=75,  # Meets 75% threshold
        confidence_components=ConfidenceComponents(
            pattern_confidence=78,
            phase_confidence=73,
            volume_confidence=72,
            overall_confidence=75,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )

    # Empty campaign (no Spring, no SOS) → LPS is sole entry
    plan = allocator.allocate_campaign_risk(empty_campaign, lps_high_confidence)

    # Should be APPROVED
    assert plan.approved is True
    assert plan.is_rebalanced is True
    assert plan.bmad_allocation_pct == Decimal("1.00")  # 100% allocation
    assert plan.target_risk_pct == Decimal("5.00")  # 100% of 5% campaign budget
    assert "elevated confidence threshold (75%)" in plan.rebalance_reason


def test_lps_with_spring_position_70_percent_confidence_approved(
    allocator, empty_campaign, spring_signal
):
    """
    Test LPS with Spring position APPROVED at 70% confidence (AC: 11).

    Scenario: Spring taken, LPS entry (not sole entry)
    Requirement: Normal 70% confidence threshold applies (NOT 75%)
    Signal: 70% confidence
    Result: APPROVED (75% threshold only for 100% LPS allocation)
    """
    # Campaign with Spring position
    campaign_with_spring = empty_campaign.model_copy(deep=True)
    campaign_with_spring.positions = [
        CampaignPosition(
            signal_id=spring_signal.id,
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("0.50"),
            risk_amount=Decimal("500.00"),
        )
    ]
    campaign_with_spring.total_allocation = Decimal("0.50")

    # LPS signal with 70% confidence (normal minimum)
    lps_normal_confidence = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("153.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("162.00")),
        position_size=Decimal("60"),
        position_size_unit="SHARES",
        risk_amount=Decimal("600.00"),
        notional_value=Decimal("15000.00"),  # position_size * entry_price
        r_multiple=Decimal("2.5"),
        confidence_score=70,  # Normal minimum (75% not required)
        confidence_components=ConfidenceComponents(
            pattern_confidence=72,
            phase_confidence=69,
            volume_confidence=67,
            overall_confidence=70,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )

    plan = allocator.allocate_campaign_risk(campaign_with_spring, lps_normal_confidence)

    # Should be APPROVED (70% OK when NOT sole entry)
    assert plan.approved is True
    assert plan.bmad_allocation_pct == Decimal("0.60")  # 60% rebalanced (SOS skipped)
    # 75% threshold only applies to 100% LPS allocation (sole entry)


# =============================================================================
# Test Category 5: Edge Cases and Error Handling
# =============================================================================


def test_invalid_pattern_type_raises_error(allocator, empty_campaign):
    """Test invalid pattern type raises InvalidPatternTypeError."""
    invalid_signal = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="UTAD",  # Not supported in BMAD allocation
        phase="E",
        timeframe="1d",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        risk_amount=Decimal("500.00"),
        notional_value=Decimal("15000.00"),  # position_size * entry_price
        r_multiple=Decimal("3.0"),
        confidence_score=80,
        confidence_components=ConfidenceComponents(
            pattern_confidence=82,
            phase_confidence=79,
            volume_confidence=77,
            overall_confidence=80,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        timestamp=datetime.now(UTC),
    )

    with pytest.raises(InvalidPatternTypeError, match="must be SPRING, SOS, or LPS"):
        allocator.allocate_campaign_risk(empty_campaign, invalid_signal)


def test_allocation_plan_validate_within_campaign_budget():
    """Test AllocationPlan.validate_within_campaign_budget() method."""
    # Valid allocation (within 5%)
    valid_plan = AllocationPlan(
        campaign_id=uuid4(),
        signal_id=uuid4(),
        pattern_type="SPRING",
        bmad_allocation_pct=Decimal("0.40"),
        target_risk_pct=Decimal("2.0"),
        actual_risk_pct=Decimal("0.5"),
        position_size_shares=Decimal("100"),
        allocation_used=Decimal("0.5"),  # Within 5%
        remaining_budget=Decimal("4.5"),
        approved=True,
    )
    assert valid_plan.validate_within_campaign_budget() is True

    # Invalid allocation (exceeds 5%)
    invalid_plan = AllocationPlan(
        campaign_id=uuid4(),
        signal_id=uuid4(),
        pattern_type="SPRING",
        bmad_allocation_pct=Decimal("0.40"),
        target_risk_pct=Decimal("2.0"),
        actual_risk_pct=Decimal("6.0"),
        position_size_shares=Decimal("100"),
        allocation_used=Decimal("6.0"),  # Exceeds 5%!
        remaining_budget=Decimal("0.0"),
        approved=False,
        rejection_reason="Test",
    )
    assert invalid_plan.validate_within_campaign_budget() is False
