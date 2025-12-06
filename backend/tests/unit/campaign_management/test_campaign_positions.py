"""
Unit Tests for Campaign Position Tracking (Story 9.4)

Purpose:
--------
Comprehensive unit tests for Position model, CampaignPositions aggregation,
and CampaignRepository position tracking methods.

Test Coverage:
--------------
1. Position model validation (AC 7)
2. CampaignPositions aggregation calculations (AC 3, 7)
3. Repository methods with in-memory database (AC 4, 5, 6, 7)

Author: Story 9.4
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.campaign import CampaignPositions
from src.models.position import Position, PositionStatus
from src.repositories.campaign_repository import (
    CampaignNotFoundError,
    CampaignRepository,
    PositionNotFoundError,
)
from src.repositories.models import CampaignModel, PositionModel


# Fixtures
@pytest.fixture
async def in_memory_session():
    """Create in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def sample_campaign(in_memory_session):
    """Create sample campaign for testing."""
    campaign = CampaignModel(
        id=uuid4(),
        symbol="AAPL",
        trading_range_id=uuid4(),
        current_risk=Decimal("0.0"),
        total_allocation=Decimal("0.0"),
        status="ACTIVE",
        version=1,
    )
    in_memory_session.add(campaign)
    await in_memory_session.commit()
    await in_memory_session.refresh(campaign)
    return campaign


# Position Model Tests
class TestPositionModel:
    """Test Position Pydantic model validation."""

    def test_valid_position_creation(self):
        """Test creating valid position with all required fields (AC 7)."""
        position = Position(
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("200.00"),
            status=PositionStatus.OPEN,
            pattern_type="SPRING",
        )

        assert position.symbol == "AAPL"
        assert position.entry_price == Decimal("150.00")
        assert position.shares == Decimal("100")
        assert position.stop_loss == Decimal("148.00")
        assert position.status == PositionStatus.OPEN

    def test_decimal_precision_enforcement(self):
        """Test Decimal type enforces 18,8 precision (AC 7)."""
        position = Position(
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.12345678"),  # 8 decimal places
            shares=Decimal("100.12345678"),
            stop_loss=Decimal("148.12345678"),
            pattern_type="SPRING",
        )

        assert position.entry_price == Decimal("150.12345678")
        assert position.shares == Decimal("100.12345678")

    def test_utc_timezone_enforcement(self):
        """Test UTC timezone enforcement on datetime fields (AC 7)."""
        now = datetime.now(UTC)
        position = Position(
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=now,
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            pattern_type="SPRING",
        )

        assert position.entry_date.tzinfo == UTC

    def test_status_enum_validation(self):
        """Test status enum validation (AC 7)."""
        position = Position(
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            status=PositionStatus.OPEN,
            pattern_type="SPRING",
        )

        assert position.status == PositionStatus.OPEN
        assert position.status.value == "OPEN"

    def test_invalid_negative_shares(self):
        """Test validation rejects negative shares (AC 7)."""
        with pytest.raises(Exception):  # Pydantic validation error
            Position(
                campaign_id=uuid4(),
                signal_id=uuid4(),
                symbol="AAPL",
                timeframe="1h",
                entry_date=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                shares=Decimal("-100"),  # Invalid
                stop_loss=Decimal("148.00"),
                pattern_type="SPRING",
            )

    def test_invalid_stop_above_entry(self):
        """Test validation rejects stop loss >= entry price (AC 7)."""
        with pytest.raises(ValueError, match="Stop loss.*must be below entry price"):
            Position(
                campaign_id=uuid4(),
                signal_id=uuid4(),
                symbol="AAPL",
                timeframe="1h",
                entry_date=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                shares=Decimal("100"),
                stop_loss=Decimal("151.00"),  # Invalid: above entry
                pattern_type="SPRING",
            )

    def test_calculate_current_pnl(self):
        """Test current P&L calculation method (AC 5)."""
        position = Position(
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            pattern_type="SPRING",
        )

        current_pnl = position.calculate_current_pnl(Decimal("152.00"))
        assert current_pnl == Decimal("200.00")  # (152 - 150) * 100

    def test_calculate_realized_pnl(self):
        """Test realized P&L calculation method (AC 6)."""
        position = Position(
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            pattern_type="SPRING",
        )

        realized_pnl = position.calculate_realized_pnl(Decimal("158.00"))
        assert realized_pnl == Decimal("800.00")  # (158 - 150) * 100


# CampaignPositions Aggregation Tests
class TestCampaignPositionsAggregation:
    """Test CampaignPositions aggregation calculations (AC 3, 7)."""

    def test_weighted_avg_entry_with_multiple_positions(self):
        """Test weighted average entry calculation (AC 3, 7)."""
        campaign_id = uuid4()

        # Create 2 open positions
        pos1 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("200.00"),
            status=PositionStatus.OPEN,
            pattern_type="SPRING",
        )

        pos2 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("152.00"),
            shares=Decimal("75"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("225.00"),
            status=PositionStatus.OPEN,
            pattern_type="SOS",
        )

        campaign_positions = CampaignPositions.from_positions(
            campaign_id=campaign_id, positions=[pos1, pos2]
        )

        # Weighted avg = (150*100 + 152*75) / (100 + 75) = 26400 / 175 = 150.85714286 (rounded to 8 decimals)
        expected_weighted_avg = (
            (Decimal("150.00") * Decimal("100") + Decimal("152.00") * Decimal("75"))
            / (Decimal("100") + Decimal("75"))
        ).quantize(Decimal("0.00000001"))
        assert campaign_positions.weighted_avg_entry == expected_weighted_avg
        assert campaign_positions.total_shares == Decimal("175")

    def test_total_risk_calculation(self):
        """Test total risk calculation (AC 3)."""
        campaign_id = uuid4()

        pos1 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),  # Risk: (150-148)*100 = 200
            status=PositionStatus.OPEN,
            pattern_type="SPRING",
        )

        pos2 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("152.00"),
            shares=Decimal("75"),
            stop_loss=Decimal("148.00"),  # Risk: (152-148)*75 = 300
            status=PositionStatus.OPEN,
            pattern_type="SOS",
        )

        campaign_positions = CampaignPositions.from_positions(
            campaign_id=campaign_id, positions=[pos1, pos2]
        )

        # Total risk = 200 + 300 = 500
        assert campaign_positions.total_risk == Decimal("500.00")

    def test_total_pnl_open_and_closed(self):
        """Test total P&L combining open + closed positions (AC 3)."""
        campaign_id = uuid4()

        # Open position with current_pnl
        pos1 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("200.00"),
            status=PositionStatus.OPEN,
            pattern_type="SPRING",
        )

        # Closed position with realized_pnl
        pos2 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("145.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("143.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("158.00"),
            realized_pnl=Decimal("1300.00"),
            pattern_type="SPRING",
        )

        campaign_positions = CampaignPositions.from_positions(
            campaign_id=campaign_id, positions=[pos1, pos2]
        )

        # Total P&L = 200 (unrealized) + 1300 (realized) = 1500
        assert campaign_positions.total_pnl == Decimal("1500.00")
        assert campaign_positions.open_positions_count == 1
        assert campaign_positions.closed_positions_count == 1

    def test_empty_positions_list(self):
        """Test aggregation with empty positions list (AC 3)."""
        campaign_id = uuid4()

        campaign_positions = CampaignPositions.from_positions(campaign_id=campaign_id, positions=[])

        assert campaign_positions.total_shares == Decimal("0")
        assert campaign_positions.weighted_avg_entry == Decimal("0")
        assert campaign_positions.total_risk == Decimal("0")
        assert campaign_positions.total_pnl == Decimal("0")
        assert campaign_positions.open_positions_count == 0
        assert campaign_positions.closed_positions_count == 0

    def test_closed_positions_excluded_from_totals(self):
        """Test closed positions excluded from weighted avg and total risk (AC 3, 6)."""
        campaign_id = uuid4()

        # Open position
        pos1 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("200.00"),
            status=PositionStatus.OPEN,
            pattern_type="SPRING",
        )

        # Closed position (should be excluded from weighted_avg_entry and total_risk)
        pos2 = Position(
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("200.00"),  # Much higher price
            shares=Decimal("100"),
            stop_loss=Decimal("198.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("210.00"),
            realized_pnl=Decimal("1000.00"),
            pattern_type="SOS",
        )

        campaign_positions = CampaignPositions.from_positions(
            campaign_id=campaign_id, positions=[pos1, pos2]
        )

        # Weighted avg should only include pos1
        assert campaign_positions.weighted_avg_entry == Decimal("150.00")
        assert campaign_positions.total_shares == Decimal("100")  # Only pos1

        # Total risk should only include pos1
        assert campaign_positions.total_risk == Decimal("200.00")  # (150-148)*100

        # Total P&L should include both
        assert campaign_positions.total_pnl == Decimal("1200.00")  # 200 + 1000


# Repository Tests
class TestCampaignRepository:
    """Test CampaignRepository position tracking methods (AC 4, 5, 6, 7)."""

    @pytest.mark.asyncio
    async def test_get_campaign_positions(self, in_memory_session, sample_campaign):
        """Test fetching campaign positions with aggregations (AC 4)."""
        # Add positions to campaign
        pos1 = PositionModel(
            campaign_id=sample_campaign.id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("200.00"),
            status="OPEN",
        )
        in_memory_session.add(pos1)
        await in_memory_session.commit()

        # Fetch positions
        repo = CampaignRepository(in_memory_session)
        campaign_positions = await repo.get_campaign_positions(sample_campaign.id)

        assert len(campaign_positions.positions) == 1
        assert campaign_positions.positions[0].symbol == "AAPL"
        assert campaign_positions.total_shares == Decimal("100")
        assert campaign_positions.weighted_avg_entry == Decimal("150.00")

    @pytest.mark.asyncio
    async def test_add_position_updates_campaign_totals(self, in_memory_session, sample_campaign):
        """Test adding position updates campaign totals atomically (AC 7)."""
        repo = CampaignRepository(in_memory_session)

        position = Position(
            campaign_id=sample_campaign.id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            pattern_type="SPRING",
        )

        created_position = await repo.add_position_to_campaign(sample_campaign.id, position)

        assert created_position.id is not None
        assert created_position.symbol == "AAPL"

        # Verify campaign version incremented (optimistic locking)
        await in_memory_session.refresh(sample_campaign)
        assert sample_campaign.version == 2

    @pytest.mark.asyncio
    async def test_update_position_recalculates_pnl(self, in_memory_session, sample_campaign):
        """Test updating position recalculates current P&L (AC 5)."""
        # Create position
        pos_model = PositionModel(
            campaign_id=sample_campaign.id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
        )
        in_memory_session.add(pos_model)
        await in_memory_session.commit()
        await in_memory_session.refresh(pos_model)

        # Update position
        repo = CampaignRepository(in_memory_session)
        updated_position = await repo.update_position(pos_model.id, Decimal("152.00"))

        assert updated_position.current_price == Decimal("152.00")
        assert updated_position.current_pnl == Decimal("200.00")  # (152 - 150) * 100

    @pytest.mark.asyncio
    async def test_close_position_maintains_record(self, in_memory_session, sample_campaign):
        """Test closing position maintains record in database (AC 6)."""
        # Create position
        pos_model = PositionModel(
            campaign_id=sample_campaign.id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("200.00"),
            status="OPEN",
        )
        in_memory_session.add(pos_model)
        await in_memory_session.commit()
        await in_memory_session.refresh(pos_model)

        # Close position
        repo = CampaignRepository(in_memory_session)
        closed_position = await repo.close_position(
            pos_model.id, Decimal("158.00"), datetime.now(UTC)
        )

        assert closed_position.status == PositionStatus.CLOSED
        assert closed_position.exit_price == Decimal("158.00")
        assert closed_position.realized_pnl == Decimal("800.00")  # (158 - 150) * 100
        assert closed_position.current_price is None  # Cleared

        # Verify record still exists
        campaign_positions = await repo.get_campaign_positions(
            sample_campaign.id, include_closed=True
        )
        assert len(campaign_positions.positions) == 1
        assert campaign_positions.positions[0].status == PositionStatus.CLOSED

    @pytest.mark.asyncio
    async def test_campaign_not_found_error(self, in_memory_session):
        """Test CampaignNotFoundError raised when campaign doesn't exist (AC 4)."""
        repo = CampaignRepository(in_memory_session)

        with pytest.raises(CampaignNotFoundError, match="Campaign .* not found"):
            await repo.get_campaign_positions(uuid4())

    @pytest.mark.asyncio
    async def test_position_not_found_error(self, in_memory_session):
        """Test PositionNotFoundError raised when position doesn't exist (AC 5)."""
        repo = CampaignRepository(in_memory_session)

        with pytest.raises(PositionNotFoundError, match="Position .* not found"):
            await repo.update_position(uuid4(), Decimal("152.00"))
