"""
Integration tests for BMAD Position Allocation (Story 9.2).

Tests the full allocation flow from signal generation through campaign creation,
verifying:
- CampaignService integration with CampaignAllocator
- AllocationPlan persistence to database
- Correct BMAD 40/30/30 allocation percentages
- Rebalancing scenarios when entries are skipped
- 75% confidence threshold for 100% LPS allocation
- Campaign budget enforcement (5% maximum)

Author: Story 9.2 Integration Tests
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.campaign_management.allocator import CampaignAllocator
from src.campaign_management.service import CampaignService
from src.models.campaign_lifecycle import CampaignStatus
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal, ValidationChain
from src.models.trading_range import TradingRange
from src.repositories.allocation_repository import AllocationRepository
from src.repositories.campaign_lifecycle_repository import CampaignLifecycleRepository


@pytest.fixture
def portfolio_value():
    """Portfolio value for testing: $100,000."""
    return Decimal("100000.00")


@pytest.fixture
def allocator(portfolio_value):
    """CampaignAllocator instance."""
    return CampaignAllocator(portfolio_value=portfolio_value)


@pytest.fixture
async def campaign_repository(db_session: AsyncSession):
    """Campaign repository with real database session."""
    return CampaignLifecycleRepository(db_session)


@pytest.fixture
async def allocation_repository(db_session: AsyncSession):
    """Allocation repository with real database session."""
    return AllocationRepository(db_session)


@pytest.fixture
async def campaign_service(campaign_repository, allocation_repository, allocator):
    """CampaignService with all dependencies."""
    return CampaignService(
        campaign_repository=campaign_repository,
        allocation_repository=allocation_repository,
        allocator=allocator,
    )


@pytest.fixture
def trading_range():
    """Sample trading range for campaigns."""
    return TradingRange(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        range_low=Decimal("145.00"),
        range_high=Decimal("155.00"),
        creek=Decimal("150.00"),
        phase="C",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def spring_signal(portfolio_value):
    """Spring signal with 0.5% risk ($500 on $100k portfolio)."""
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("148.00"),
        stop_loss=Decimal("145.00"),
        target_levels=TargetLevels(primary_target=Decimal("157.00")),
        position_size=Decimal("166"),
        position_size_unit="SHARES",
        risk_amount=Decimal("500.00"),
        notional_value=Decimal("24568.00"),
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
    """SOS signal with 1.0% risk ($1,000 on $100k portfolio)."""
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("151.00"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("160.00")),
        position_size=Decimal("333"),
        position_size_unit="SHARES",
        risk_amount=Decimal("1000.00"),
        notional_value=Decimal("50283.00"),
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
    """LPS signal with 0.6% risk ($600 on $100k portfolio)."""
    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("153.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("162.00")),
        position_size=Decimal("200"),
        position_size_unit="SHARES",
        risk_amount=Decimal("600.00"),
        notional_value=Decimal("30600.00"),
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
# Integration Test: Full BMAD Allocation Flow (Spring → SOS → LPS)
# =============================================================================


@pytest.mark.asyncio
async def test_full_bmad_allocation_flow_spring_sos_lps(
    campaign_service,
    allocation_repository,
    trading_range,
    spring_signal,
    sos_signal,
    lps_signal,
):
    """
    Test complete BMAD allocation flow: Spring → SOS → LPS.

    Verifies:
    - Campaign creation with Spring (40% allocation = 2% of 5%)
    - SOS addition with 30% allocation (1.5% of 5%)
    - LPS addition with 30% allocation (1.5% of 5%)
    - Total allocation: 5% of portfolio
    - AllocationPlan persistence for each entry
    - Campaign status transitions (ACTIVE → MARKUP)
    """
    # Step 1: Create campaign with Spring (first signal)
    campaign, spring_plan = await campaign_service.create_campaign(spring_signal, trading_range)

    assert campaign is not None
    assert campaign.status == CampaignStatus.ACTIVE
    assert len(campaign.positions) == 1
    assert campaign.positions[0].pattern_type == "SPRING"

    # Verify Spring allocation plan
    assert spring_plan.approved is True
    assert spring_plan.bmad_allocation_pct == Decimal("0.40")  # 40%
    assert spring_plan.is_rebalanced is False

    # Step 2: Add SOS to campaign
    campaign, sos_plan = await campaign_service.add_signal_to_campaign(campaign, sos_signal)

    assert campaign.status == CampaignStatus.MARKUP  # Transitioned after SOS
    assert len(campaign.positions) == 2
    assert campaign.positions[1].pattern_type == "SOS"

    # Verify SOS allocation plan
    assert sos_plan.approved is True
    assert sos_plan.bmad_allocation_pct == Decimal("0.30")  # 30%
    assert sos_plan.is_rebalanced is False

    # Step 3: Add LPS to campaign
    campaign, lps_plan = await campaign_service.add_signal_to_campaign(campaign, lps_signal)

    assert campaign.status == CampaignStatus.MARKUP  # Stays MARKUP
    assert len(campaign.positions) == 3
    assert campaign.positions[2].pattern_type == "LPS"

    # Verify LPS allocation plan
    assert lps_plan.approved is True
    assert lps_plan.bmad_allocation_pct == Decimal("0.30")  # 30%
    assert lps_plan.is_rebalanced is False

    # Verify total allocation is 5% (sum of all positions)
    # Spring: 0.5%, SOS: 1.0%, LPS: 0.6% = 2.1% (actual risk)
    # But allocation percentages should sum close to 5%
    total_allocation = campaign.total_allocation
    assert total_allocation <= Decimal("5.0")  # Within 5% limit

    # Verify all allocation plans persisted
    saved_plans = await allocation_repository.get_allocation_plans_by_campaign(campaign.id)
    assert len(saved_plans) == 3
    assert saved_plans[0].pattern_type == "SPRING"
    assert saved_plans[1].pattern_type == "SOS"
    assert saved_plans[2].pattern_type == "LPS"


# =============================================================================
# Integration Test: Rebalancing Scenario (Spring Skipped → SOS 70%)
# =============================================================================


@pytest.mark.asyncio
async def test_rebalancing_spring_skipped_sos_gets_70_percent(
    campaign_service,
    allocation_repository,
    trading_range,
    sos_signal,
):
    """
    Test rebalancing when Spring is skipped.

    Scenario:
    - No Spring entry (skipped)
    - SOS is first entry → should get 70% allocation (40% + 30%)

    Verifies:
    - SOS gets rebalanced 70% allocation
    - is_rebalanced = True
    - rebalance_reason mentions "Spring skipped"
    """
    # Create campaign with SOS (no Spring)
    campaign, sos_plan = await campaign_service.create_campaign(sos_signal, trading_range)

    # Verify SOS got rebalanced 70%
    assert sos_plan.approved is True
    assert sos_plan.bmad_allocation_pct == Decimal("0.70")  # 70% rebalanced
    assert sos_plan.is_rebalanced is True
    assert "Spring skipped" in sos_plan.rebalance_reason

    # Verify campaign created successfully
    assert campaign.status == CampaignStatus.ACTIVE  # Not MARKUP yet (no SOS entry)
    assert len(campaign.positions) == 1
    assert campaign.positions[0].pattern_type == "SOS"


# =============================================================================
# Integration Test: 100% LPS Allocation with Confidence Threshold
# =============================================================================


@pytest.mark.asyncio
async def test_100_percent_lps_sole_entry_75_percent_confidence_required(
    campaign_service,
    allocation_repository,
    trading_range,
):
    """
    Test 100% LPS allocation requires 75% confidence.

    Scenario:
    - Spring AND SOS both skipped
    - LPS is sole entry → requires 75% minimum confidence

    Verifies:
    - LPS with 75% confidence: APPROVED with 100% allocation
    - LPS with 72% confidence: REJECTED
    """
    # Test 1: LPS with 75% confidence (approved)
    lps_high_confidence = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("153.00"),
        stop_loss=Decimal("150.00"),
        target_levels=TargetLevels(primary_target=Decimal("162.00")),
        position_size=Decimal("200"),
        position_size_unit="SHARES",
        risk_amount=Decimal("600.00"),
        notional_value=Decimal("30600.00"),
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

    campaign, lps_plan = await campaign_service.create_campaign(lps_high_confidence, trading_range)

    assert lps_plan.approved is True
    assert lps_plan.bmad_allocation_pct == Decimal("1.00")  # 100%
    assert lps_plan.is_rebalanced is True
    assert "LPS sole entry" in lps_plan.rebalance_reason
    assert len(campaign.positions) == 1

    # Test 2: LPS with 72% confidence (rejected)
    lps_low_confidence = TradeSignal(
        id=uuid4(),
        symbol="TSLA",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("250.00"),
        stop_loss=Decimal("245.00"),
        target_levels=TargetLevels(primary_target=Decimal("265.00")),
        position_size=Decimal("20"),
        position_size_unit="SHARES",
        risk_amount=Decimal("100.00"),
        notional_value=Decimal("5000.00"),
        r_multiple=Decimal("3.0"),
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

    # Create new trading range for second test
    trading_range_2 = TradingRange(
        id=uuid4(),
        symbol="TSLA",
        timeframe="1d",
        range_low=Decimal("240.00"),
        range_high=Decimal("260.00"),
        creek=Decimal("250.00"),
        phase="D",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    campaign_rejected, lps_plan_rejected = await campaign_service.create_campaign(
        lps_low_confidence, trading_range_2
    )

    # Campaign creation should still succeed, but allocation plan rejected
    assert lps_plan_rejected.approved is False
    assert "75% minimum confidence" in lps_plan_rejected.rejection_reason
    assert "signal has 72%" in lps_plan_rejected.rejection_reason


# =============================================================================
# Integration Test: Campaign Budget Enforcement (5% Maximum)
# =============================================================================


@pytest.mark.asyncio
async def test_campaign_budget_enforcement_5_percent_maximum(
    campaign_service,
    allocation_repository,
    trading_range,
    spring_signal,
    sos_signal,
):
    """
    Test campaign 5% budget enforcement.

    Verifies:
    - Multiple positions don't exceed 5% campaign limit
    - allocation_used tracked correctly
    - remaining_budget calculated correctly
    """
    # Create campaign with Spring
    campaign, spring_plan = await campaign_service.create_campaign(spring_signal, trading_range)

    assert spring_plan.allocation_used <= Decimal("5.0")
    assert spring_plan.remaining_budget >= Decimal("0.0")

    # Add SOS
    campaign, sos_plan = await campaign_service.add_signal_to_campaign(campaign, sos_signal)

    assert sos_plan.allocation_used <= Decimal("5.0")
    assert sos_plan.remaining_budget >= Decimal("0.0")

    # Verify allocation plans show budget consumption
    all_plans = await allocation_repository.get_allocation_plans_by_campaign(campaign.id)
    assert len(all_plans) == 2

    # Remaining budget should decrease with each entry
    assert all_plans[1].remaining_budget < all_plans[0].remaining_budget
