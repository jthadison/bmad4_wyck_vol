"""
Unit tests for WyckoffCampaignDetector (Story 12.8).

Author: Story 12.8
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.campaign_detector import WyckoffCampaignDetector
from src.models.backtest import BacktestTrade


def make_trade(
    symbol="AAPL",
    pattern=None,
    entry_date=None,
    days_duration=3,
    pnl=Decimal("200.00"),
    side="LONG",
    **kwargs,
):
    """Helper to create BacktestTrade with defaults."""
    entry_date = entry_date or datetime(2024, 1, 1)
    exit_date = entry_date + timedelta(days=days_duration)

    return BacktestTrade(
        trade_id=uuid4(),
        position_id=uuid4(),
        symbol=symbol,
        pattern_type=pattern,
        entry_timestamp=entry_date,
        entry_price=Decimal("150.00"),
        exit_timestamp=exit_date,
        exit_price=Decimal("152.00"),
        quantity=100,
        side=side,
        realized_pnl=pnl,
        commission=Decimal("5.00"),
        slippage=Decimal("2.00"),
        r_multiple=Decimal("2.0"),
        **kwargs,
    )


@pytest.fixture
def detector():
    """Create campaign detector instance."""
    return WyckoffCampaignDetector(campaign_window_days=90)


class TestCampaignDetection:
    """Test campaign detection logic."""

    def test_detect_campaigns_empty_trades(self, detector):
        """Test with empty trades list."""
        campaigns = detector.detect_campaigns([])
        assert len(campaigns) == 0

    def test_detect_campaigns_no_patterns(self, detector):
        """Test with trades but no pattern_type."""
        trades = [make_trade(pattern=None)]
        campaigns = detector.detect_campaigns(trades)
        assert len(campaigns) == 0

    def test_detect_complete_accumulation_campaign(self, detector):
        """Test detection of complete Accumulation campaign PS→JUMP."""
        base_date = datetime(2024, 1, 1)
        patterns = ["PS", "SC", "AR", "SPRING", "TEST", "SOS", "LPS", "JUMP"]

        trades = [
            make_trade(
                symbol="AAPL",
                pattern=pattern,
                entry_date=base_date + timedelta(days=i * 7),
            )
            for i, pattern in enumerate(patterns)
        ]

        campaigns = detector.detect_campaigns(trades)

        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.symbol == "AAPL"
        assert campaign.patterns_traded == 8
        assert campaign.status == "COMPLETED"
        assert campaign.failure_reason is None  # COMPLETED campaigns have no failure_reason
        assert "PHASE_A" in campaign.phases_completed
        assert "PHASE_E" in campaign.phases_completed

    def test_detect_complete_distribution_campaign(self, detector):
        """Test detection of complete Distribution campaign BC→DECLINE."""
        base_date = datetime(2024, 1, 1)
        patterns = ["BC", "AR", "UTAD", "TEST", "SOW", "LPSY", "DECLINE"]

        trades = [
            make_trade(
                symbol="TSLA",
                pattern=pattern,
                entry_date=base_date + timedelta(days=i * 7),
                side="SHORT",
            )
            for i, pattern in enumerate(patterns)
        ]

        campaigns = detector.detect_campaigns(trades)

        assert len(campaigns) == 1
        campaign = campaigns[0]
        assert campaign.symbol == "TSLA"
        assert campaign.status == "COMPLETED"
        assert campaign.failure_reason is None  # COMPLETED campaigns have no failure_reason

    def test_time_gap_creates_separate_campaigns(self, detector):
        """Test that time gap > 90 days creates separate campaigns."""
        base_date = datetime(2024, 1, 1)

        # Campaign 1: PS, SC
        campaign1 = [
            make_trade(pattern="PS", entry_date=base_date),
            make_trade(pattern="SC", entry_date=base_date + timedelta(days=7)),
        ]

        # Campaign 2: PS, SC (100 days later - exceeds window)
        campaign2 = [
            make_trade(pattern="PS", entry_date=base_date + timedelta(days=100)),
            make_trade(pattern="SC", entry_date=base_date + timedelta(days=107)),
        ]

        all_trades = campaign1 + campaign2
        campaigns = detector.detect_campaigns(all_trades)

        assert len(campaigns) == 2


class TestPatternSequenceValidation:
    """Test pattern sequence validation."""

    def test_valid_first_patterns(self, detector):
        """Test that only PS, PSY, BC are valid campaign starters."""
        assert detector._is_valid_next_pattern([], "PS") is True
        assert detector._is_valid_next_pattern([], "PSY") is True
        assert detector._is_valid_next_pattern([], "BC") is True
        assert detector._is_valid_next_pattern([], "SPRING") is False
        assert detector._is_valid_next_pattern([], "SOS") is False

    def test_spring_requires_sc_and_ar(self, detector):
        """Test that SPRING requires both SC and AR."""
        # Valid: has both SC and AR
        assert detector._is_valid_next_pattern(["PS", "SC", "AR"], "SPRING") is True

        # Invalid: missing SC
        assert detector._is_valid_next_pattern(["PS", "AR"], "SPRING") is False

        # Invalid: missing AR
        assert detector._is_valid_next_pattern(["PS", "SC"], "SPRING") is False

    def test_sos_requires_spring_or_test(self, detector):
        """Test that SOS requires SPRING or TEST."""
        # Valid: has SPRING
        assert detector._is_valid_next_pattern(["PS", "SC", "AR", "SPRING"], "SOS") is True

        # Valid: has TEST
        assert detector._is_valid_next_pattern(["PS", "SC", "AR", "SPRING", "TEST"], "SOS") is True

        # Invalid: no SPRING or TEST
        assert detector._is_valid_next_pattern(["PS", "SC", "AR"], "SOS") is False

    def test_mixed_campaign_types_rejected(self, detector):
        """Test that Distribution patterns can't follow Accumulation."""
        # Accumulation started with PS, try to add UTAD (Distribution)
        assert detector._is_valid_next_pattern(["PS", "SC", "AR"], "UTAD") is False

    def test_broken_sequence_creates_new_campaign(self, detector):
        """Test that invalid sequence starts new campaign."""
        base_date = datetime(2024, 1, 1)

        # Valid partial campaign then invalid pattern
        trades = [
            make_trade(pattern="PS", entry_date=base_date),
            make_trade(pattern="SC", entry_date=base_date + timedelta(days=7)),
            make_trade(pattern="AR", entry_date=base_date + timedelta(days=14)),
            # SOS without SPRING - invalid, starts new campaign
            make_trade(pattern="SOS", entry_date=base_date + timedelta(days=21)),
        ]

        campaigns = detector.detect_campaigns(trades)

        # Should create 2 campaigns
        assert len(campaigns) == 2


class TestCampaignStatus:
    """Test campaign status determination."""

    def test_completed_accumulation_status(self, detector):
        """Test JUMP marks campaign as COMPLETED."""
        trades = [
            make_trade(pattern="PS"),
            make_trade(pattern="SC"),
            make_trade(pattern="AR"),
            make_trade(pattern="SPRING"),
            make_trade(pattern="SOS"),  # Required before JUMP
            make_trade(pattern="JUMP"),
        ]

        campaigns = detector.detect_campaigns(trades)
        assert campaigns[0].status == "COMPLETED"
        assert campaigns[0].failure_reason is None  # COMPLETED campaigns have no failure_reason

    def test_early_phase_campaign_marked_failed(self, detector):
        """Test campaign that ends in early phase (A/B) is marked FAILED.

        In backtest context, all campaigns have end dates (trades are completed).
        A campaign that doesn't reach Phase D (SOS) is marked FAILED with
        reason PHASE_D_NOT_REACHED.
        """
        trades = [
            make_trade(pattern="PS"),
            make_trade(pattern="SC"),
            make_trade(pattern="AR"),
            # Campaign stops here - only reached Phase B, never got to Phase D
        ]

        campaigns = detector.detect_campaigns(trades)
        assert len(campaigns) == 1
        assert campaigns[0].status == "FAILED"
        assert campaigns[0].failure_reason == "PHASE_D_NOT_REACHED"
        assert campaigns[0].end_date is not None  # Last trade exit date

    def test_failed_campaign_no_jump(self, detector):
        """Test ended campaign without JUMP is FAILED."""
        base_date = datetime(2024, 1, 1)
        patterns = ["PS", "SC", "AR", "SPRING", "SOS", "LPS"]

        # All trades closed (has exit_timestamp) but no JUMP
        trades = [
            make_trade(
                pattern=pattern,
                entry_date=base_date + timedelta(days=i * 7),
            )
            for i, pattern in enumerate(patterns)
        ]

        campaigns = detector.detect_campaigns(trades)
        campaign = campaigns[0]

        # Reached Phase D (SOS, LPS) but failed to JUMP
        assert campaign.status == "FAILED"
        assert campaign.failure_reason == "MARKUP_FAILED"


class TestCampaignMetrics:
    """Test campaign metrics calculation."""

    def test_campaign_pnl_calculation(self, detector):
        """Test campaign P&L is sum of trade P&L."""
        trades = [
            make_trade(pattern="PS", pnl=Decimal("100.00")),
            make_trade(pattern="SC", pnl=Decimal("200.00")),
            make_trade(pattern="AR", pnl=Decimal("150.00")),
        ]

        campaigns = detector.detect_campaigns(trades)
        assert campaigns[0].total_campaign_pnl == Decimal("450.00")

    def test_campaign_metadata(self, detector):
        """Test campaign metadata fields populated."""
        base_date = datetime(2024, 1, 1)
        trades = [
            make_trade(pattern="PS", entry_date=base_date, symbol="AAPL"),
            make_trade(pattern="SC", entry_date=base_date + timedelta(days=7)),
        ]

        campaigns = detector.detect_campaigns(trades)
        campaign = campaigns[0]

        assert campaign.campaign_id is not None
        assert campaign.symbol == "AAPL"
        # CampaignPerformance model enforces UTC timezone
        assert campaign.start_date.replace(tzinfo=None) == base_date
        assert campaign.end_date is not None
        assert campaign.patterns_traded == 2

    def test_multiple_symbols_separate_campaigns(self, detector):
        """Test different symbols create separate campaigns."""
        trades = [
            make_trade(pattern="PS", symbol="AAPL"),
            make_trade(pattern="BC", symbol="TSLA"),
        ]

        campaigns = detector.detect_campaigns(trades)
        assert len(campaigns) == 2
        symbols = {c.symbol for c in campaigns}
        assert symbols == {"AAPL", "TSLA"}
