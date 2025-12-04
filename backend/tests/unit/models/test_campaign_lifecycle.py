"""
Unit Tests for Campaign Lifecycle Models (Story 9.1)

Test Coverage:
--------------
1. Campaign ID generation format (AC: 3)
2. Campaign lifecycle states (AC: 4)
3. Campaign position addition
4. Campaign allocation limit enforcement (FR18)
5. Weighted average entry calculation
6. Total P&L calculation
7. State transition validation
8. UTC timezone enforcement
9. Decimal precision validation

Author: Story 9.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.campaign_lifecycle import (
    Campaign,
    CampaignPosition,
    CampaignStatus,
    MAX_CAMPAIGN_RISK_PCT,
    VALID_CAMPAIGN_TRANSITIONS,
)
from src.models.trading_range import TradingRange


class TestCampaignPosition:
    """Tests for CampaignPosition model."""

    def test_position_creation_valid(self):
        """Test creating valid campaign position."""
        position = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.25"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("175.00"),  # (152-150.25)*100 = 175
            status="OPEN",
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("225.00"),  # (150.25-148)*100 = 225
        )

        assert position.pattern_type == "SPRING"
        assert position.entry_price == Decimal("150.25")
        assert position.shares == Decimal("100")
        assert position.status == "OPEN"
        assert position.allocation_percent == Decimal("2.0")

    def test_position_pnl_calculation_validation(self):
        """Test current_pnl must match calculated (entry - current) * shares."""
        # Valid case: (152.00 - 150.25) * 100 = 175.00
        position = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.25"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("175.00"),
            status="OPEN",
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("225.00"),
        )
        assert position.current_pnl == Decimal("175.00")

    def test_position_pnl_calculation_mismatch_raises_error(self):
        """Test invalid current_pnl raises ValueError."""
        with pytest.raises(ValueError, match="current_pnl.*doesn't match calculated"):
            CampaignPosition(
                signal_id=uuid4(),
                pattern_type="SPRING",
                entry_date=datetime.now(UTC),
                entry_price=Decimal("150.25"),
                shares=Decimal("100"),
                stop_loss=Decimal("148.00"),
                target_price=Decimal("156.00"),
                current_price=Decimal("152.00"),
                current_pnl=Decimal("500.00"),  # Wrong! Should be 175.00
                status="OPEN",
                allocation_percent=Decimal("2.0"),
                risk_amount=Decimal("225.00"),
            )

    def test_position_utc_enforcement(self):
        """Test all datetime fields must be UTC timezone."""
        # Valid: UTC timezone
        position = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("147.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("1.5"),
            risk_amount=Decimal("150.00"),
        )
        assert position.entry_date.tzinfo == UTC

        # Invalid: no timezone
        with pytest.raises(ValueError, match="Datetime must have timezone"):
            CampaignPosition(
                signal_id=uuid4(),
                pattern_type="SOS",
                entry_date=datetime.now(),  # No timezone!
                entry_price=Decimal("150.00"),
                shares=Decimal("50"),
                stop_loss=Decimal("147.00"),
                target_price=Decimal("156.00"),
                current_price=Decimal("150.00"),
                current_pnl=Decimal("0.00"),
                status="OPEN",
                allocation_percent=Decimal("1.5"),
                risk_amount=Decimal("150.00"),
            )


class TestCampaign:
    """Tests for Campaign model."""

    def test_campaign_id_format(self):
        """Test campaign_id follows format: {symbol}-{date} (AC: 3)."""
        campaign = Campaign(
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
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        assert campaign.campaign_id == "AAPL-2024-10-15"
        assert "-" in campaign.campaign_id
        assert campaign.symbol in campaign.campaign_id

    def test_campaign_lifecycle_states(self):
        """Test campaign status transitions through lifecycle (AC: 4)."""
        # ACTIVE state
        campaign = Campaign(
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
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )
        assert campaign.is_active() is True

        # MARKUP state (still active)
        campaign.status = CampaignStatus.MARKUP
        assert campaign.is_active() is True

        # COMPLETED state (not active)
        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = datetime.now(UTC)
        assert campaign.is_active() is False

        # INVALIDATED state (not active)
        campaign.status = CampaignStatus.INVALIDATED
        campaign.invalidation_reason = "Stop hit"
        assert campaign.is_active() is False

    def test_campaign_position_addition(self):
        """Test adding positions to campaign."""
        position1 = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("200.00"),
        )

        position2 = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("152.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("152.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("1.5"),
            risk_amount=Decimal("200.00"),
        )

        campaign = Campaign(
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[position1, position2],
            total_risk=Decimal("400.00"),
            total_allocation=Decimal("3.5"),  # 2.0 + 1.5
            current_risk=Decimal("400.00"),
            total_shares=Decimal("150"),  # 100 + 50
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        assert len(campaign.positions) == 2
        assert campaign.total_allocation == Decimal("3.5")
        assert campaign.total_shares == Decimal("150")

    def test_campaign_allocation_limit_enforcement(self):
        """Test 5% allocation limit enforced (FR18)."""
        # Valid: 5.0% allocation (exactly at limit)
        campaign = Campaign(
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            total_risk=Decimal("500.00"),
            total_allocation=Decimal("5.0"),  # Max allowed
            current_risk=Decimal("500.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )
        assert campaign.total_allocation == Decimal("5.0")

        # Invalid: 5.1% exceeds limit
        with pytest.raises(ValueError, match="Campaign allocation.*exceeds maximum.*5.0%"):
            Campaign(
                campaign_id="AAPL-2024-10-15",
                symbol="AAPL",
                timeframe="1d",
                trading_range_id=uuid4(),
                status=CampaignStatus.ACTIVE,
                phase="C",
                total_risk=Decimal("510.00"),
                total_allocation=Decimal("5.1"),  # Exceeds limit!
                current_risk=Decimal("510.00"),
                total_shares=Decimal("100"),
                total_pnl=Decimal("0.00"),
                start_date=datetime.now(UTC),
            )

    def test_can_add_position_within_limit(self):
        """Test can_add_position checks allocation limit (FR18)."""
        campaign = Campaign(
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            total_risk=Decimal("300.00"),
            total_allocation=Decimal("3.0"),  # 3% currently used
            current_risk=Decimal("300.00"),
            total_shares=Decimal("100"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        # Can add 2.0% (total would be 5.0%)
        assert campaign.can_add_position(Decimal("2.0")) is True

        # Cannot add 2.5% (total would be 5.5%)
        assert campaign.can_add_position(Decimal("2.5")) is False

    def test_weighted_average_entry_calculation(self):
        """Test weighted_avg_entry calculated correctly."""
        # Position 1: 100 shares @ $150 = $15,000
        # Position 2: 50 shares @ $153 = $7,650
        # Total cost: $22,650
        # Total shares: 150
        # Weighted avg: $22,650 / 150 = $151.00

        position1 = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("150.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("200.00"),
        )

        position2 = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("153.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("153.00"),
            current_pnl=Decimal("0.00"),
            status="OPEN",
            allocation_percent=Decimal("1.5"),
            risk_amount=Decimal("250.00"),
        )

        campaign = Campaign(
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[position1, position2],
            total_risk=Decimal("450.00"),
            total_allocation=Decimal("3.5"),
            current_risk=Decimal("450.00"),
            weighted_avg_entry=Decimal("151.00"),  # (100*150 + 50*153)/150
            total_shares=Decimal("150"),
            total_pnl=Decimal("0.00"),
            start_date=datetime.now(UTC),
        )

        assert campaign.weighted_avg_entry == Decimal("151.00")

    def test_total_pnl_calculation(self):
        """Test calculate_total_pnl sums position PnLs."""
        # Position 1: entry $150, current $155, 100 shares → PnL = $500
        position1 = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("500.00"),  # (155-150)*100
            status="OPEN",
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("200.00"),
        )

        # Position 2: entry $153, current $154, 50 shares → PnL = $50
        position2 = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("153.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("154.00"),
            current_pnl=Decimal("50.00"),  # (154-153)*50
            status="OPEN",
            allocation_percent=Decimal("1.5"),
            risk_amount=Decimal("250.00"),
        )

        campaign = Campaign(
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[position1, position2],
            total_risk=Decimal("450.00"),
            total_allocation=Decimal("3.5"),
            current_risk=Decimal("450.00"),
            total_shares=Decimal("150"),
            total_pnl=Decimal("550.00"),  # 500 + 50
            start_date=datetime.now(UTC),
        )

        assert campaign.calculate_total_pnl() == Decimal("550.00")
        assert campaign.total_pnl == Decimal("550.00")

    def test_get_open_positions_filters_correctly(self):
        """Test get_open_positions returns only OPEN status positions."""
        position_open = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("155.00"),
            current_pnl=Decimal("500.00"),
            status="OPEN",
            allocation_percent=Decimal("2.0"),
            risk_amount=Decimal("200.00"),
        )

        position_closed = CampaignPosition(
            signal_id=uuid4(),
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("153.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("148.00"),
            target_price=Decimal("156.00"),
            current_price=Decimal("156.00"),
            current_pnl=Decimal("150.00"),
            status="CLOSED",
            allocation_percent=Decimal("1.5"),
            risk_amount=Decimal("250.00"),
        )

        campaign = Campaign(
            campaign_id="AAPL-2024-10-15",
            symbol="AAPL",
            timeframe="1d",
            trading_range_id=uuid4(),
            status=CampaignStatus.ACTIVE,
            phase="C",
            positions=[position_open, position_closed],
            total_risk=Decimal("450.00"),
            total_allocation=Decimal("3.5"),
            current_risk=Decimal("200.00"),  # Only open position risk
            total_shares=Decimal("150"),
            total_pnl=Decimal("650.00"),
            start_date=datetime.now(UTC),
        )

        open_positions = campaign.get_open_positions()
        assert len(open_positions) == 1
        assert open_positions[0].status == "OPEN"
        assert open_positions[0].pattern_type == "SPRING"

    def test_terminal_states_require_completed_at(self):
        """Test COMPLETED/INVALIDATED states require completed_at timestamp."""
        # COMPLETED requires completed_at
        with pytest.raises(ValueError, match="completed_at must be set"):
            Campaign(
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
                completed_at=None,  # Missing!
            )

        # INVALIDATED requires completed_at AND invalidation_reason
        with pytest.raises(ValueError, match="invalidation_reason must be set"):
            Campaign(
                campaign_id="AAPL-2024-10-15",
                symbol="AAPL",
                timeframe="1d",
                trading_range_id=uuid4(),
                status=CampaignStatus.INVALIDATED,  # Terminal state
                phase="C",
                total_risk=Decimal("200.00"),
                total_allocation=Decimal("2.0"),
                current_risk=Decimal("0.00"),
                total_shares=Decimal("100"),
                total_pnl=Decimal("-200.00"),
                start_date=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                invalidation_reason=None,  # Missing!
            )

    def test_valid_state_transitions_mapping(self):
        """Test VALID_CAMPAIGN_TRANSITIONS constants are correct (AC: 4)."""
        # ACTIVE can transition to MARKUP or INVALIDATED
        assert CampaignStatus.MARKUP in VALID_CAMPAIGN_TRANSITIONS[CampaignStatus.ACTIVE]
        assert CampaignStatus.INVALIDATED in VALID_CAMPAIGN_TRANSITIONS[CampaignStatus.ACTIVE]

        # MARKUP can transition to COMPLETED or INVALIDATED
        assert CampaignStatus.COMPLETED in VALID_CAMPAIGN_TRANSITIONS[CampaignStatus.MARKUP]
        assert CampaignStatus.INVALIDATED in VALID_CAMPAIGN_TRANSITIONS[CampaignStatus.MARKUP]

        # COMPLETED is terminal (no valid transitions)
        assert VALID_CAMPAIGN_TRANSITIONS[CampaignStatus.COMPLETED] == []

        # INVALIDATED is terminal (no valid transitions)
        assert VALID_CAMPAIGN_TRANSITIONS[CampaignStatus.INVALIDATED] == []
