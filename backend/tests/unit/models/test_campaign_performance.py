"""
Unit tests for CampaignPerformanceMetrics model - Story 22.10

Tests the performance tracking functionality including P&L,
R-multiples, excursion tracking, and win/loss status.
"""

from datetime import UTC, datetime
from decimal import Decimal

from src.models.campaign_performance import (
    CampaignPerformanceMetrics,
    ExitReason,
    WinLossStatus,
)


class TestExitReasonEnum:
    """Test ExitReason enum."""

    def test_all_exit_reasons_exist(self):
        """Test all expected exit reasons are defined."""
        assert ExitReason.TARGET_HIT.value == "TARGET_HIT"
        assert ExitReason.STOP_OUT.value == "STOP_OUT"
        assert ExitReason.TIME_EXIT.value == "TIME_EXIT"
        assert ExitReason.PHASE_E.value == "PHASE_E"
        assert ExitReason.MANUAL_EXIT.value == "MANUAL_EXIT"
        assert ExitReason.UNKNOWN.value == "UNKNOWN"


class TestWinLossStatusEnum:
    """Test WinLossStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        assert WinLossStatus.OPEN.value == "open"
        assert WinLossStatus.WIN.value == "win"
        assert WinLossStatus.LOSS.value == "loss"
        assert WinLossStatus.BREAKEVEN.value == "breakeven"


class TestCampaignPerformanceMetricsCreation:
    """Test CampaignPerformanceMetrics instantiation."""

    def test_default_creation(self):
        """Test creating with defaults."""
        perf = CampaignPerformanceMetrics()

        assert perf.profit_loss == Decimal("0")
        assert perf.unrealized_pnl == Decimal("0")
        assert perf.realized_pnl == Decimal("0")
        assert perf.r_multiple is None
        assert perf.target_r_multiple == Decimal("2.0")
        assert perf.points_gained is None
        assert perf.percent_gain == 0.0
        assert perf.max_favorable_excursion == Decimal("0")
        assert perf.max_adverse_excursion == Decimal("0")
        assert perf.win_loss_status == WinLossStatus.OPEN
        assert perf.exit_reason == ExitReason.UNKNOWN
        assert perf.exit_price is None
        assert perf.exit_timestamp is None
        assert perf.duration_bars == 0

    def test_custom_creation(self):
        """Test creating with custom values."""
        perf = CampaignPerformanceMetrics(
            profit_loss=Decimal("500.00"),
            r_multiple=Decimal("2.5"),
            win_loss_status=WinLossStatus.WIN,
            exit_reason=ExitReason.TARGET_HIT,
        )

        assert perf.profit_loss == Decimal("500.00")
        assert perf.r_multiple == Decimal("2.5")
        assert perf.win_loss_status == WinLossStatus.WIN
        assert perf.exit_reason == ExitReason.TARGET_HIT


class TestExcursionTracking:
    """Test update_excursions method."""

    def test_update_excursions_positive_pnl(self):
        """Test MFE updates with positive P&L."""
        perf = CampaignPerformanceMetrics()

        perf.update_excursions(Decimal("100"))

        assert perf.max_favorable_excursion == Decimal("100")
        assert perf.max_adverse_excursion == Decimal("0")

    def test_update_excursions_negative_pnl(self):
        """Test MAE updates with negative P&L."""
        perf = CampaignPerformanceMetrics()

        perf.update_excursions(Decimal("-50"))

        assert perf.max_favorable_excursion == Decimal("0")
        assert perf.max_adverse_excursion == Decimal("-50")

    def test_update_excursions_sequence(self):
        """Test excursion tracking through a sequence."""
        perf = CampaignPerformanceMetrics()

        # Trade goes up
        perf.update_excursions(Decimal("100"))
        assert perf.max_favorable_excursion == Decimal("100")

        # Trade pulls back
        perf.update_excursions(Decimal("-20"))
        assert perf.max_favorable_excursion == Decimal("100")  # Unchanged
        assert perf.max_adverse_excursion == Decimal("-20")

        # Trade makes new high
        perf.update_excursions(Decimal("150"))
        assert perf.max_favorable_excursion == Decimal("150")  # Updated
        assert perf.max_adverse_excursion == Decimal("-20")  # Unchanged

        # Trade falls further
        perf.update_excursions(Decimal("-30"))
        assert perf.max_favorable_excursion == Decimal("150")  # Unchanged
        assert perf.max_adverse_excursion == Decimal("-30")  # Updated


class TestEfficiencyCalculation:
    """Test calculate_efficiency method."""

    def test_efficiency_calculation(self):
        """Test basic efficiency calculation."""
        perf = CampaignPerformanceMetrics(
            profit_loss=Decimal("400"),
            max_favorable_excursion=Decimal("500"),
        )

        efficiency = perf.calculate_efficiency()

        assert efficiency == 0.8  # Captured 80% of max profit

    def test_efficiency_full_capture(self):
        """Test efficiency when capturing 100% of MFE."""
        perf = CampaignPerformanceMetrics(
            profit_loss=Decimal("500"),
            max_favorable_excursion=Decimal("500"),
        )

        efficiency = perf.calculate_efficiency()

        assert efficiency == 1.0

    def test_efficiency_zero_mfe(self):
        """Test efficiency with zero MFE."""
        perf = CampaignPerformanceMetrics(
            profit_loss=Decimal("100"),
            max_favorable_excursion=Decimal("0"),
        )

        assert perf.calculate_efficiency() is None


class TestMAERatioCalculation:
    """Test calculate_mae_ratio method."""

    def test_mae_ratio_calculation(self):
        """Test basic MAE ratio calculation."""
        perf = CampaignPerformanceMetrics(
            profit_loss=Decimal("200"),
            max_adverse_excursion=Decimal("-100"),
        )

        ratio = perf.calculate_mae_ratio()

        assert ratio == -0.5  # Drawdown was half the final profit

    def test_mae_ratio_zero_profit(self):
        """Test MAE ratio with zero profit."""
        perf = CampaignPerformanceMetrics(
            profit_loss=Decimal("0"),
            max_adverse_excursion=Decimal("-100"),
        )

        assert perf.calculate_mae_ratio() is None


class TestFinalizePerformance:
    """Test finalize method."""

    def test_finalize_winning_trade(self):
        """Test finalizing a winning trade."""
        perf = CampaignPerformanceMetrics()
        exit_time = datetime.now(UTC)

        perf.finalize(
            exit_price=Decimal("155.00"),
            entry_price=Decimal("150.00"),
            risk_per_share=Decimal("2.00"),
            exit_reason=ExitReason.TARGET_HIT,
            exit_timestamp=exit_time,
        )

        assert perf.points_gained == Decimal("5.00")
        assert perf.r_multiple == Decimal("2.5")
        assert perf.win_loss_status == WinLossStatus.WIN
        assert perf.exit_price == Decimal("155.00")
        assert perf.exit_reason == ExitReason.TARGET_HIT
        assert perf.exit_timestamp == exit_time
        assert perf.percent_gain > 0

    def test_finalize_losing_trade(self):
        """Test finalizing a losing trade."""
        perf = CampaignPerformanceMetrics()

        perf.finalize(
            exit_price=Decimal("145.00"),
            entry_price=Decimal("150.00"),
            risk_per_share=Decimal("2.00"),
            exit_reason=ExitReason.STOP_OUT,
            exit_timestamp=datetime.now(UTC),
        )

        assert perf.points_gained == Decimal("-5.00")
        assert perf.r_multiple == Decimal("-2.5")
        assert perf.win_loss_status == WinLossStatus.LOSS
        assert perf.exit_reason == ExitReason.STOP_OUT
        assert perf.percent_gain < 0

    def test_finalize_breakeven_trade(self):
        """Test finalizing a breakeven trade."""
        perf = CampaignPerformanceMetrics()

        perf.finalize(
            exit_price=Decimal("150.00"),
            entry_price=Decimal("150.00"),
            risk_per_share=Decimal("2.00"),
            exit_reason=ExitReason.TIME_EXIT,
            exit_timestamp=datetime.now(UTC),
        )

        assert perf.points_gained == Decimal("0.00")
        assert perf.r_multiple == Decimal("0")
        assert perf.win_loss_status == WinLossStatus.BREAKEVEN

    def test_finalize_no_risk_per_share(self):
        """Test finalizing with no risk_per_share."""
        perf = CampaignPerformanceMetrics()

        perf.finalize(
            exit_price=Decimal("155.00"),
            entry_price=Decimal("150.00"),
            risk_per_share=None,
            exit_reason=ExitReason.MANUAL_EXIT,
            exit_timestamp=datetime.now(UTC),
        )

        assert perf.points_gained == Decimal("5.00")
        assert perf.r_multiple is None
        assert perf.win_loss_status == WinLossStatus.WIN

    def test_finalize_zero_risk_per_share(self):
        """Test finalizing with zero risk_per_share."""
        perf = CampaignPerformanceMetrics()

        perf.finalize(
            exit_price=Decimal("155.00"),
            entry_price=Decimal("150.00"),
            risk_per_share=Decimal("0"),
            exit_reason=ExitReason.PHASE_E,
            exit_timestamp=datetime.now(UTC),
        )

        assert perf.r_multiple is None


class TestStatusMethods:
    """Test status checking methods."""

    def test_is_winner_true(self):
        """Test is_winner returns True for wins."""
        perf = CampaignPerformanceMetrics(win_loss_status=WinLossStatus.WIN)
        assert perf.is_winner() is True

    def test_is_winner_false(self):
        """Test is_winner returns False for non-wins."""
        perf = CampaignPerformanceMetrics(win_loss_status=WinLossStatus.LOSS)
        assert perf.is_winner() is False

        perf.win_loss_status = WinLossStatus.BREAKEVEN
        assert perf.is_winner() is False

        perf.win_loss_status = WinLossStatus.OPEN
        assert perf.is_winner() is False

    def test_is_closed_true(self):
        """Test is_closed returns True for closed trades."""
        for status in [WinLossStatus.WIN, WinLossStatus.LOSS, WinLossStatus.BREAKEVEN]:
            perf = CampaignPerformanceMetrics(win_loss_status=status)
            assert perf.is_closed() is True

    def test_is_closed_false(self):
        """Test is_closed returns False for open trades."""
        perf = CampaignPerformanceMetrics(win_loss_status=WinLossStatus.OPEN)
        assert perf.is_closed() is False

    def test_target_reached_true(self):
        """Test target_reached when R-multiple meets target."""
        perf = CampaignPerformanceMetrics(
            r_multiple=Decimal("3.0"),
            target_r_multiple=Decimal("2.0"),
        )
        assert perf.target_reached() is True

    def test_target_reached_exactly(self):
        """Test target_reached when R-multiple equals target."""
        perf = CampaignPerformanceMetrics(
            r_multiple=Decimal("2.0"),
            target_r_multiple=Decimal("2.0"),
        )
        assert perf.target_reached() is True

    def test_target_reached_false(self):
        """Test target_reached when R-multiple below target."""
        perf = CampaignPerformanceMetrics(
            r_multiple=Decimal("1.5"),
            target_r_multiple=Decimal("2.0"),
        )
        assert perf.target_reached() is False

    def test_target_reached_no_r_multiple(self):
        """Test target_reached with no R-multiple."""
        perf = CampaignPerformanceMetrics(r_multiple=None)
        assert perf.target_reached() is False
