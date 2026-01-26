"""
Unit tests for Campaign Tracker Service (Story 11.4)

Tests progression logic, health status calculation, P&L calculations,
and quality scoring for campaign visualization.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from src.models.campaign_tracker import (
    CampaignHealthStatus,
    CampaignQualityScore,
    PreliminaryEvent,
)
from src.repositories.models import CampaignModel, PositionModel
from src.services.campaign_tracker_service import (
    calculate_entry_pnl,
    calculate_health,
    calculate_progression,
    calculate_quality_score,
)


class TestCampaignProgression:
    """Test campaign progression calculation logic."""

    def test_progression_no_entries(self):
        """Test progression with no entries returns Phase C with Spring pending."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="ACTIVE",
            phase="C",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("0.00"),
            created_at=datetime.now(UTC),
        )

        progression = calculate_progression(campaign)

        assert progression.current_phase == "C"
        assert progression.completed_phases == []
        assert progression.pending_phases == ["SPRING", "SOS", "LPS"]
        assert progression.next_expected == "Phase C watch - monitoring for Spring"

    def test_progression_spring_completed(self):
        """Test progression with Spring entry shows Phase D pending SOS."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="ACTIVE",
            phase="D",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )

        # Mock position for Spring entry using SQLAlchemy PositionModel
        spring_position = PositionModel(
            id=uuid4(),
            campaign_id=campaign.id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("20"),
            stop_loss=Decimal("148.50"),
            status="FILLED",
        )
        campaign.positions = [spring_position]

        progression = calculate_progression(campaign)

        assert progression.current_phase == "D"
        assert "SPRING" in progression.completed_phases
        assert "SOS" not in progression.completed_phases
        assert progression.next_expected == "Phase D watch - monitoring for SOS"

    def test_progression_all_phases_completed(self):
        """Test progression with all entries shows Phase E markup."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="MARKUP",
            phase="E",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("10000.00"),
            created_at=datetime.now(UTC),
        )

        # Mock positions for all entries using SQLAlchemy PositionModel
        positions = [
            PositionModel(
                id=uuid4(),
                campaign_id=campaign.id,
                signal_id=uuid4(),
                symbol="AAPL",
                timeframe="1D",
                pattern_type="SPRING",
                entry_date=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                shares=Decimal("20"),
                stop_loss=Decimal("148.50"),
                status="FILLED",
            ),
            PositionModel(
                id=uuid4(),
                campaign_id=campaign.id,
                signal_id=uuid4(),
                symbol="AAPL",
                timeframe="1D",
                pattern_type="SOS",
                entry_date=datetime.now(UTC),
                entry_price=Decimal("155.00"),
                shares=Decimal("19"),
                stop_loss=Decimal("152.00"),
                status="FILLED",
            ),
            PositionModel(
                id=uuid4(),
                campaign_id=campaign.id,
                signal_id=uuid4(),
                symbol="AAPL",
                timeframe="1D",
                pattern_type="LPS",
                entry_date=datetime.now(UTC),
                entry_price=Decimal("152.00"),
                shares=Decimal("26"),
                stop_loss=Decimal("150.00"),
                status="FILLED",
            ),
        ]
        campaign.positions = positions

        progression = calculate_progression(campaign)

        assert progression.current_phase == "E"
        assert len(progression.completed_phases) == 3
        assert "SPRING" in progression.completed_phases
        assert "SOS" in progression.completed_phases
        assert "LPS" in progression.completed_phases
        assert progression.next_expected == "Campaign complete - all entries filled"


class TestCampaignHealth:
    """Test campaign health status calculation logic."""

    def test_health_green_low_allocation(self):
        """Test health is GREEN when allocation < 4%."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="ACTIVE",
            phase="C",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )

        health = calculate_health(
            campaign=campaign,
            total_allocation=Decimal("3.0"),
            any_stop_hit=False,
        )

        assert health == CampaignHealthStatus.GREEN

    def test_health_yellow_medium_allocation(self):
        """Test health is YELLOW when allocation 4-5%."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="ACTIVE",
            phase="C",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("4500.00"),
            created_at=datetime.now(UTC),
        )

        health = calculate_health(
            campaign=campaign,
            total_allocation=Decimal("4.5"),
            any_stop_hit=False,
        )

        assert health == CampaignHealthStatus.YELLOW

    def test_health_red_stop_hit(self):
        """Test health is RED when stop is hit."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="ACTIVE",
            phase="C",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )

        health = calculate_health(
            campaign=campaign,
            total_allocation=Decimal("3.0"),
            any_stop_hit=True,
        )

        assert health == CampaignHealthStatus.RED

    def test_health_red_invalidated(self):
        """Test health is RED when campaign is invalidated."""
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),
            status="INVALIDATED",
            phase="C",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )

        health = calculate_health(
            campaign=campaign,
            total_allocation=Decimal("3.0"),
            any_stop_hit=False,
        )

        assert health == CampaignHealthStatus.RED


class TestEntryPnL:
    """Test entry P&L calculation logic."""

    def test_pnl_positive(self):
        """Test P&L calculation for profitable position."""
        position = PositionModel(
            id=uuid4(),
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=Decimal("20"),
            stop_loss=Decimal("148.50"),
            status="FILLED",
        )

        current_price = Decimal("155.00")
        pnl, pnl_percent = calculate_entry_pnl(position, current_price)

        # 20 shares * ($155 - $150) = $100 profit
        assert pnl == Decimal("100.00")
        # ($155 - $150) / $150 * 100 = 3.333...%
        expected_pct = ((current_price - position.entry_price) / position.entry_price) * Decimal(
            "100"
        )
        assert pnl_percent == expected_pct

    def test_pnl_negative(self):
        """Test P&L calculation for losing position."""
        position = PositionModel(
            id=uuid4(),
            campaign_id=uuid4(),
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            pattern_type="SOS",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("155.00"),
            shares=Decimal("20"),
            stop_loss=Decimal("152.00"),
            status="FILLED",
        )

        current_price = Decimal("152.00")
        pnl, pnl_percent = calculate_entry_pnl(position, current_price)

        # 20 shares * ($152 - $155) = -$60 loss
        assert pnl == Decimal("-60.00")
        # ($152 - $155) / $155 * 100 = -1.935...%
        expected_pct = ((current_price - position.entry_price) / position.entry_price) * Decimal(
            "100"
        )
        assert pnl_percent == expected_pct


class TestQualityScore:
    """Test campaign quality score calculation logic."""

    def test_quality_complete_all_events(self):
        """Test COMPLETE quality when all 4 preliminary events present."""
        events = [
            PreliminaryEvent(
                event_type="PS",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("150.00"),
                bar_index=1,
            ),
            PreliminaryEvent(
                event_type="SC",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("148.00"),
                bar_index=5,
            ),
            PreliminaryEvent(
                event_type="AR",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("153.00"),
                bar_index=7,
            ),
            PreliminaryEvent(
                event_type="ST",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("149.00"),
                bar_index=12,
            ),
        ]

        quality = calculate_quality_score(events)

        assert quality == CampaignQualityScore.COMPLETE

    def test_quality_partial_2_events(self):
        """Test PARTIAL quality when 2-3 preliminary events present."""
        events = [
            PreliminaryEvent(
                event_type="SC",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("148.00"),
                bar_index=5,
            ),
            PreliminaryEvent(
                event_type="AR",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("153.00"),
                bar_index=7,
            ),
        ]

        quality = calculate_quality_score(events)

        assert quality == CampaignQualityScore.PARTIAL

    def test_quality_minimal_no_events(self):
        """Test MINIMAL quality when 0-1 preliminary events."""
        events: list[PreliminaryEvent] = []

        quality = calculate_quality_score(events)

        assert quality == CampaignQualityScore.MINIMAL

    def test_quality_minimal_one_event(self):
        """Test MINIMAL quality when only 1 preliminary event."""
        events = [
            PreliminaryEvent(
                event_type="SC",
                timestamp=datetime.now(UTC).isoformat(),
                price=Decimal("148.00"),
                bar_index=5,
            ),
        ]

        quality = calculate_quality_score(events)

        assert quality == CampaignQualityScore.MINIMAL
