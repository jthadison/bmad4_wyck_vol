"""
Unit Tests for CampaignService (Story 9.1)

Test Coverage:
--------------
1. create_campaign from Spring signal (AC: 5)
2. get_or_create_campaign creates new (AC: 6)
3. get_or_create_campaign links existing (AC: 6)
4. add_signal_to_campaign adds SOS and triggers MARKUP (AC: 4, 6)
5. add_signal_to_campaign enforces 5% limit (FR18)
6. complete_campaign requires all positions closed
7. invalidate_campaign sets reason
8. update_campaign_status validates transitions (AC: 4)

Author: Story 9.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.campaign_management.service import (
    CampaignAllocationExceededError,
    CampaignNotReadyForCompletionError,
    CampaignService,
    InvalidStatusTransitionError,
)
from src.models.campaign_lifecycle import Campaign, CampaignPosition, CampaignStatus
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.trading_range import TradingRange
from src.repositories.campaign_lifecycle_repository import CampaignLifecycleRepository


@pytest.fixture
def mock_repository():
    """Mock CampaignLifecycleRepository."""
    return AsyncMock(spec=CampaignLifecycleRepository)


@pytest.fixture
def campaign_service(mock_repository):
    """Campaign service with mocked repository."""
    return CampaignService(campaign_repository=mock_repository)


@pytest.fixture
def mock_trading_range():
    """Mock TradingRange for testing."""
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
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_spring_signal(mock_trading_range):
    """Mock Spring TradeSignal."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("150.25"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("225.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=85,
            overall_confidence=85,
        ),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_sos_signal(mock_trading_range):
    """Mock SOS TradeSignal."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("152.50"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("50"),
        risk_amount=Decimal("225.00"),
        r_multiple=Decimal("2.5"),
        confidence_score=82,
        confidence_components=ConfidenceComponents(
            pattern_confidence=85,
            phase_confidence=80,
            volume_confidence=80,
            overall_confidence=82,
        ),
        timestamp=datetime.now(UTC),
    )


class TestCreateCampaign:
    """Tests for create_campaign method (AC: 5)."""

    @pytest.mark.asyncio
    async def test_create_campaign_from_spring_signal(
        self, campaign_service, mock_repository, mock_spring_signal, mock_trading_range
    ):
        """Test campaign created from Spring signal with ACTIVE status (AC: 5)."""
        # Mock repository to return created campaign
        mock_repository.create_campaign.return_value = AsyncMock()

        campaign = await campaign_service.create_campaign(mock_spring_signal, mock_trading_range)

        # Verify campaign created
        assert mock_repository.create_campaign.called
        created_campaign_arg = mock_repository.create_campaign.call_args[0][0]

        # Verify campaign fields (AC: 2, 3, 4, 5)
        assert created_campaign_arg.symbol == "AAPL"
        assert created_campaign_arg.status == CampaignStatus.ACTIVE  # Initial status
        assert len(created_campaign_arg.positions) == 1  # First position (Spring)
        assert created_campaign_arg.positions[0].pattern_type == "SPRING"
        assert created_campaign_arg.total_allocation == Decimal("2.0")  # Spring allocation

        # Verify campaign_id format: {symbol}-{date} (AC: 3)
        assert "AAPL-" in created_campaign_arg.campaign_id
        assert len(created_campaign_arg.campaign_id.split("-")) >= 4  # AAPL-YYYY-MM-DD

    @pytest.mark.asyncio
    async def test_create_campaign_initializes_correct_metrics(
        self, campaign_service, mock_repository, mock_spring_signal, mock_trading_range
    ):
        """Test campaign metrics initialized correctly."""
        mock_repository.create_campaign.return_value = AsyncMock()

        await campaign_service.create_campaign(mock_spring_signal, mock_trading_range)

        created_campaign = mock_repository.create_campaign.call_args[0][0]

        # Verify initial metrics
        assert created_campaign.total_risk == mock_spring_signal.risk_amount
        assert created_campaign.current_risk == mock_spring_signal.risk_amount
        assert created_campaign.total_shares == mock_spring_signal.position_size
        assert created_campaign.total_pnl == Decimal("0.00")  # Not yet filled
        assert created_campaign.weighted_avg_entry == mock_spring_signal.entry_price


class TestGetOrCreateCampaign:
    """Tests for get_or_create_campaign method (AC: 6)."""

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_when_none_exists(
        self, campaign_service, mock_repository, mock_spring_signal, mock_trading_range
    ):
        """Test creates new campaign when none exists for range (AC: 6)."""
        # Mock: no existing campaign
        mock_repository.get_campaign_by_trading_range.return_value = None
        mock_repository.create_campaign.return_value = AsyncMock()

        campaign = await campaign_service.get_or_create_campaign(
            mock_spring_signal, mock_trading_range
        )

        # Verify checked for existing campaign
        mock_repository.get_campaign_by_trading_range.assert_called_once_with(mock_trading_range.id)

        # Verify created new campaign
        assert mock_repository.create_campaign.called

    @pytest.mark.asyncio
    async def test_get_or_create_links_existing_when_found(
        self, campaign_service, mock_repository, mock_spring_signal, mock_trading_range
    ):
        """Test returns existing campaign when active campaign found (AC: 6)."""
        # Mock: existing campaign found
        existing_campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=mock_trading_range.id,
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[],
            total_risk=Decimal("200.00"),
            total_allocation=Decimal("2.0"),
            current_risk=Decimal("200.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )
        mock_repository.get_campaign_by_trading_range.return_value = existing_campaign

        campaign = await campaign_service.get_or_create_campaign(
            mock_spring_signal, mock_trading_range
        )

        # Verify returned existing campaign
        assert campaign.id == existing_campaign.id
        assert campaign.campaign_id == "AAPL-2024-10-15"

        # Verify did NOT create new campaign
        assert not mock_repository.create_campaign.called


class TestAddSignalToCampaign:
    """Tests for add_signal_to_campaign method (AC: 6)."""

    @pytest.mark.asyncio
    async def test_add_signal_to_campaign_adds_position(
        self, campaign_service, mock_repository, mock_sos_signal
    ):
        """Test adds new position to campaign."""
        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[],
            total_risk=Decimal("225.00"),
            total_allocation=Decimal("2.0"),
            current_risk=Decimal("225.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        # Mock repository methods
        mock_repository.add_position_to_campaign.return_value = campaign
        mock_repository.get_campaign_by_id.return_value = campaign

        updated_campaign = await campaign_service.add_signal_to_campaign(campaign, mock_sos_signal)

        # Verify position added
        assert mock_repository.add_position_to_campaign.called

    @pytest.mark.asyncio
    async def test_add_sos_triggers_markup_transition(
        self, campaign_service, mock_repository, mock_sos_signal
    ):
        """Test adding SOS transitions ACTIVE → MARKUP (AC: 4)."""
        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,  # Before SOS
            phase="C",
            positions=[],
            total_risk=Decimal("225.00"),
            total_allocation=Decimal("2.0"),
            current_risk=Decimal("225.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        # Mock repository
        mock_repository.add_position_to_campaign.return_value = campaign
        campaign_markup = Campaign(**campaign.model_dump())
        campaign_markup.status = CampaignStatus.MARKUP
        mock_repository.get_campaign_by_id.return_value = campaign_markup
        mock_repository.update_campaign.return_value = campaign_markup

        updated_campaign = await campaign_service.add_signal_to_campaign(campaign, mock_sos_signal)

        # Verify status updated to MARKUP
        assert mock_repository.update_campaign.called

    @pytest.mark.asyncio
    async def test_add_signal_enforces_allocation_limit(
        self, campaign_service, mock_repository, mock_sos_signal
    ):
        """Test adding position exceeding 5% limit raises error (FR18)."""
        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[],
            total_risk=Decimal("480.00"),
            total_allocation=Decimal("4.8"),  # Already at 4.8%
            current_risk=Decimal("480.00"),
            total_shares=Decimal("200"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        # SOS signal would add 1.5%, exceeding 5% limit
        with pytest.raises(CampaignAllocationExceededError, match="exceed.*5%.*campaign limit"):
            await campaign_service.add_signal_to_campaign(campaign, mock_sos_signal)

        # Verify position NOT added
        assert not mock_repository.add_position_to_campaign.called


class TestCampaignStatusTransitions:
    """Tests for status transition methods (AC: 4)."""

    @pytest.mark.asyncio
    async def test_update_campaign_status_valid_transition(self, campaign_service, mock_repository):
        """Test valid status transition updates campaign."""
        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            total_risk=Decimal("225.00"),
            total_allocation=Decimal("2.0"),
            current_risk=Decimal("225.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        mock_repository.get_campaign_by_id.return_value = campaign
        updated_campaign = Campaign(**campaign.model_dump())
        updated_campaign.status = CampaignStatus.MARKUP
        mock_repository.update_campaign.return_value = updated_campaign

        result = await campaign_service.update_campaign_status(campaign.id, CampaignStatus.MARKUP)

        assert mock_repository.update_campaign.called
        assert result.status == CampaignStatus.MARKUP

    @pytest.mark.asyncio
    async def test_update_campaign_status_invalid_transition_raises_error(
        self, campaign_service, mock_repository
    ):
        """Test invalid transition raises InvalidStatusTransitionError (AC: 4)."""
        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.COMPLETED,  # Terminal state
            phase="D",
            total_risk=Decimal("500.00"),
            total_allocation=Decimal("5.0"),
            current_risk=Decimal("0.00"),
            total_shares=Decimal("150"),
            total_pnl=Decimal("1200.00"),
            start_date=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        mock_repository.get_campaign_by_id.return_value = campaign

        # Cannot transition from COMPLETED (terminal state)
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            await campaign_service.update_campaign_status(campaign.id, CampaignStatus.ACTIVE)

    @pytest.mark.asyncio
    async def test_complete_campaign_requires_all_positions_closed(
        self, campaign_service, mock_repository
    ):
        """Test complete_campaign raises error if open positions exist."""
        # Campaign with 1 OPEN position
        open_position = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("500.00"),
            status="OPEN",  # Still open!
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("200.00"),
        )

        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.MARKUP,
            phase="D",
            positions=[open_position],
            total_risk=Decimal("200.00"),
            total_allocation=Decimal("2.0"),
            current_risk=Decimal("200.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("500.00"),
            start_date=datetime.now(UTC),
        )

        mock_repository.get_campaign_by_id.return_value = campaign

        with pytest.raises(CampaignNotReadyForCompletionError, match="open positions"):
            await campaign_service.complete_campaign(campaign.id)

    @pytest.mark.asyncio
    async def test_invalidate_campaign_sets_reason(self, campaign_service, mock_repository):
        """Test invalidate_campaign sets invalidation_reason."""
        campaign = Campaign(
            id=uuid4(),
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            total_risk=Decimal("200.00"),
            total_allocation=Decimal("2.0"),
            current_risk=Decimal("200.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("-200.00"),
            start_date=datetime.now(UTC),
        )

        invalidated_campaign = Campaign(**campaign.model_dump())
        invalidated_campaign.status = CampaignStatus.INVALIDATED
        invalidated_campaign.invalidation_reason = "Spring low break"
        invalidated_campaign.completed_at = datetime.now(UTC)

        mock_repository.get_campaign_by_id.return_value = campaign
        mock_repository.update_campaign.return_value = invalidated_campaign

        result = await campaign_service.invalidate_campaign(campaign.id, "Spring low break")

        # Verify status and reason set
        assert mock_repository.update_campaign.called
        updated_campaign_arg = mock_repository.update_campaign.call_args[0][0]
        assert updated_campaign_arg.status == CampaignStatus.INVALIDATED
        assert updated_campaign_arg.invalidation_reason == "Spring low break"
        assert updated_campaign_arg.completed_at is not None
