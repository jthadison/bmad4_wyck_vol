"""
Integration Tests for Campaign Lifecycle (Story 9.1)

Test Coverage (AC: 8):
-----------------------
1. Full Spring → SOS → LPS campaign sequence
2. Campaign creation from first signal
3. Signal linkage to existing campaign
4. Status transitions (ACTIVE → MARKUP → COMPLETED)
5. Position tracking across campaign lifecycle
6. Campaign completion workflow
7. Database persistence (when implemented)

This is a comprehensive end-to-end test demonstrating the complete
multi-phase position building workflow for a single trading range.

Author: Story 9.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.campaign_management.service import CampaignService
from src.models.campaign_lifecycle import CampaignStatus
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.trading_range import TradingRange
from src.repositories.campaign_lifecycle_repository import CampaignLifecycleRepository


@pytest.fixture
def mock_repository():
    """Mock repository for integration testing."""
    repo = AsyncMock(spec=CampaignLifecycleRepository)

    # Mock storage for campaigns
    repo._campaigns = {}

    # Mock create_campaign
    async def mock_create_campaign(campaign):
        repo._campaigns[campaign.id] = campaign
        return campaign

    repo.create_campaign.side_effect = mock_create_campaign

    # Mock get_campaign_by_id
    async def mock_get_campaign_by_id(campaign_id):
        return repo._campaigns.get(campaign_id)

    repo.get_campaign_by_id.side_effect = mock_get_campaign_by_id

    # Mock get_campaign_by_trading_range
    async def mock_get_campaign_by_trading_range(trading_range_id):
        # Find active campaign for this range
        for campaign in repo._campaigns.values():
            if (
                campaign.trading_range_id == trading_range_id
                and campaign.status
                in [CampaignStatus.ACTIVE, CampaignStatus.MARKUP]
            ):
                return campaign
        return None

    repo.get_campaign_by_trading_range.side_effect = mock_get_campaign_by_trading_range

    # Mock add_position_to_campaign
    async def mock_add_position(campaign_id, position):
        campaign = repo._campaigns.get(campaign_id)
        if campaign:
            campaign.positions.append(position)
            # Update totals
            campaign.total_allocation += position.allocation_percent
            campaign.total_risk += position.risk_amount
            campaign.total_shares += position.shares
            campaign.version += 1
        return campaign

    repo.add_position_to_campaign.side_effect = mock_add_position

    # Mock update_campaign
    async def mock_update_campaign(campaign):
        repo._campaigns[campaign.id] = campaign
        return campaign

    repo.update_campaign.side_effect = mock_update_campaign

    return repo


@pytest.fixture
def campaign_service(mock_repository):
    """Campaign service for integration testing."""
    return CampaignService(campaign_repository=mock_repository)


@pytest.fixture
def trading_range():
    """Trading range for AAPL accumulation."""
    return TradingRange(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        support=Decimal("148.00"),
        resistance=Decimal("156.00"),
        midpoint=Decimal("152.00"),
        range_width=Decimal("8.00"),
        range_width_pct=Decimal("5.41"),
        start_index=0,
        end_index=20,
        duration=21,
        created_at=datetime(2024, 10, 15, tzinfo=UTC),
    )


@pytest.fixture
def spring_signal():
    """Spring signal for AAPL at $150.25."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("150.25"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("225.00"),  # (150.25-148)*100
        r_multiple=Decimal("3.0"),
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=85,
            overall_confidence=85,
        ),
        timestamp=datetime(2024, 10, 15, 10, 30, tzinfo=UTC),
    )


@pytest.fixture
def sos_signal():
    """SOS signal for AAPL at $152.50."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("152.50"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("50"),
        risk_amount=Decimal("225.00"),  # (152.50-148)*50
        r_multiple=Decimal("2.5"),
        confidence_score=82,
        confidence_components=ConfidenceComponents(
            pattern_confidence=85,
            phase_confidence=80,
            volume_confidence=80,
            overall_confidence=82,
        ),
        timestamp=datetime(2024, 10, 18, 14, 0, tzinfo=UTC),
    )


@pytest.fixture
def lps_signal():
    """LPS signal for AAPL at $151.00."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="LPS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("151.00"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("50"),
        risk_amount=Decimal("150.00"),  # (151-148)*50
        r_multiple=Decimal("3.3"),
        confidence_score=80,
        confidence_components=ConfidenceComponents(
            pattern_confidence=82,
            phase_confidence=78,
            volume_confidence=80,
            overall_confidence=80,
        ),
        timestamp=datetime(2024, 10, 20, 11, 15, tzinfo=UTC),
    )


@pytest.mark.asyncio
class TestFullCampaignLifecycle:
    """
    Integration test for full Spring → SOS → LPS campaign (AC: 8).

    This test demonstrates the complete multi-phase position building
    workflow within a single trading range.
    """

    async def test_full_campaign_lifecycle_spring_sos_lps(
        self,
        campaign_service,
        trading_range,
        spring_signal,
        sos_signal,
        lps_signal,
    ):
        """
        Test complete campaign lifecycle: Spring → SOS → LPS → COMPLETED (AC: 8).

        Workflow:
        ---------
        1. Spring signal creates campaign (status=ACTIVE, 1 position, 2% allocation)
        2. SOS signal links to campaign (status=MARKUP, 2 positions, 3.5% allocation)
        3. LPS signal adds to campaign (status=MARKUP, 3 positions, ~5% allocation)
        4. Close all positions (status=COMPLETED)

        This is the canonical BMAD multi-phase entry sequence.
        """

        # =====================================================================
        # Step 1: Create Spring signal (First signal creates campaign)
        # =====================================================================
        print("\n=== Step 1: Spring Signal (First Entry) ===")

        campaign = await campaign_service.get_or_create_campaign(spring_signal, trading_range)

        # Verify campaign created (AC: 1, 5)
        assert campaign is not None
        assert campaign.campaign_id == "AAPL-2024-10-15"  # AC: 3 format
        assert campaign.symbol == "AAPL"
        assert campaign.status == CampaignStatus.ACTIVE  # AC: 4 initial state
        assert len(campaign.positions) == 1  # Spring position
        assert campaign.positions[0].pattern_type == "SPRING"
        assert campaign.total_allocation == Decimal("2.0")  # Spring: 2%
        assert campaign.total_risk == Decimal("225.00")

        print(f"✓ Campaign created: {campaign.campaign_id}")
        print(f"  Status: {campaign.status.value}")
        print(f"  Positions: {len(campaign.positions)} (Spring)")
        print(f"  Allocation: {campaign.total_allocation}%")

        # =====================================================================
        # Step 2: Create SOS signal (Links to existing campaign)
        # =====================================================================
        print("\n=== Step 2: SOS Signal (Second Entry) ===")

        campaign2 = await campaign_service.get_or_create_campaign(sos_signal, trading_range)

        # Verify same campaign returned (AC: 6)
        assert campaign2.id == campaign.id  # Same campaign instance
        assert campaign2.campaign_id == campaign.campaign_id

        # Add SOS position to campaign
        campaign = await campaign_service.add_signal_to_campaign(campaign2, sos_signal)

        # Verify SOS added and status transitioned (AC: 4, 6)
        assert len(campaign.positions) == 2  # Spring + SOS
        assert campaign.positions[1].pattern_type == "SOS"
        assert campaign.status == CampaignStatus.MARKUP  # ACTIVE → MARKUP after SOS
        assert campaign.total_allocation == Decimal("3.5")  # 2.0 + 1.5

        print(f"✓ SOS position added to campaign: {campaign.campaign_id}")
        print(f"  Status: {campaign.status.value} (transitioned from ACTIVE)")
        print(f"  Positions: {len(campaign.positions)} (Spring + SOS)")
        print(f"  Allocation: {campaign.total_allocation}%")

        # =====================================================================
        # Step 3: Create LPS signal (Adds third position)
        # =====================================================================
        print("\n=== Step 3: LPS Signal (Third Entry) ===")

        campaign3 = await campaign_service.get_or_create_campaign(lps_signal, trading_range)

        # Verify same campaign returned
        assert campaign3.id == campaign.id

        # Add LPS position to campaign
        campaign = await campaign_service.add_signal_to_campaign(campaign3, lps_signal)

        # Verify LPS added (AC: 6, 8)
        assert len(campaign.positions) == 3  # Spring + SOS + LPS
        assert campaign.positions[2].pattern_type == "LPS"
        assert campaign.status == CampaignStatus.MARKUP  # Still MARKUP
        assert campaign.total_allocation == Decimal("5.0")  # 2.0 + 1.5 + 1.5 = 5%
        assert campaign.total_risk == Decimal("600.00")  # 225 + 225 + 150

        print(f"✓ LPS position added to campaign: {campaign.campaign_id}")
        print(f"  Status: {campaign.status.value}")
        print(f"  Positions: {len(campaign.positions)} (Spring + SOS + LPS)")
        print(f"  Allocation: {campaign.total_allocation}% (at 5% limit)")

        # =====================================================================
        # Step 4: Close all positions and complete campaign
        # =====================================================================
        print("\n=== Step 4: Close Positions and Complete Campaign ===")

        # Simulate closing all positions
        for position in campaign.positions:
            position.status = "CLOSED"

        # Update campaign in repository
        await campaign_service.campaign_repository.update_campaign(campaign)

        # Complete campaign
        campaign = await campaign_service.complete_campaign(campaign.id)

        # Verify campaign completed (AC: 4, 8)
        assert campaign.status == CampaignStatus.COMPLETED  # MARKUP → COMPLETED
        assert campaign.completed_at is not None
        assert all(p.status == "CLOSED" for p in campaign.positions)

        print(f"✓ Campaign completed: {campaign.campaign_id}")
        print(f"  Status: {campaign.status.value}")
        print(f"  Completed at: {campaign.completed_at}")
        print(f"  All positions closed: {len(campaign.positions)}")

        # =====================================================================
        # Final Assertions: Verify complete campaign state
        # =====================================================================
        print("\n=== Final Campaign State ===")

        assert campaign.campaign_id == "AAPL-2024-10-15"
        assert campaign.symbol == "AAPL"
        assert campaign.status == CampaignStatus.COMPLETED
        assert len(campaign.positions) == 3  # Spring, SOS, LPS
        assert campaign.total_allocation == Decimal("5.0")  # Full 5% allocated
        assert campaign.total_shares == Decimal("200")  # 100 + 50 + 50
        assert campaign.completed_at is not None

        # Verify position sequence
        assert campaign.positions[0].pattern_type == "SPRING"
        assert campaign.positions[1].pattern_type == "SOS"
        assert campaign.positions[2].pattern_type == "LPS"

        print(f"✓ Campaign lifecycle completed successfully")
        print(f"  Campaign ID: {campaign.campaign_id}")
        print(f"  Status: {campaign.status.value}")
        print(f"  Total Allocation: {campaign.total_allocation}%")
        print(f"  Total Shares: {campaign.total_shares}")
        print(f"  Position Sequence: Spring → SOS → LPS")

    async def test_campaign_invalidation_workflow(
        self,
        campaign_service,
        trading_range,
        spring_signal,
    ):
        """Test campaign invalidation when stop hit."""

        # Create campaign with Spring
        campaign = await campaign_service.get_or_create_campaign(spring_signal, trading_range)
        assert campaign.status == CampaignStatus.ACTIVE

        # Invalidate campaign (e.g., Spring low break)
        campaign = await campaign_service.invalidate_campaign(
            campaign.id, reason="Spring low break"
        )

        # Verify invalidated
        assert campaign.status == CampaignStatus.INVALIDATED
        assert campaign.invalidation_reason == "Spring low break"
        assert campaign.completed_at is not None

        print(f"✓ Campaign invalidated: {campaign.invalidation_reason}")

    async def test_campaign_prevents_duplicate_for_same_range(
        self,
        campaign_service,
        trading_range,
        spring_signal,
    ):
        """Test only one active campaign exists per trading range (AC: 6)."""

        # Create first campaign
        campaign1 = await campaign_service.get_or_create_campaign(spring_signal, trading_range)
        assert campaign1.status == CampaignStatus.ACTIVE

        # Try to get campaign again (should return same one)
        campaign2 = await campaign_service.get_or_create_campaign(spring_signal, trading_range)

        # Verify same campaign instance
        assert campaign1.id == campaign2.id
        assert campaign1.campaign_id == campaign2.campaign_id

        print(f"✓ Same campaign returned for duplicate range: {campaign1.campaign_id}")
