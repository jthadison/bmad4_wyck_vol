"""
Unit Tests for Campaign Performance Calculator (Story 9.6 - Task 7)

Tests:
------
1. CampaignMetrics and PositionMetrics model validation
2. calculate_campaign_performance with synthetic data (AC #7)
3. Max drawdown calculation
4. Edge cases (no positions, all breakeven, single position)
5. Aggregated performance calculations
6. Phase-specific metrics (Phase C vs Phase D)

Test Data:
----------
- Synthetic campaigns with known inputs and expected outputs
- Decimal precision enforcement tests
- UTC timezone enforcement tests
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.campaign import (
    CampaignMetrics,
    PositionMetrics,
    WinLossStatus,
)
from src.models.position import Position, PositionStatus
from src.services.campaign_performance_calculator import (
    calculate_campaign_performance,
    calculate_max_drawdown_from_equity_curve,
    generate_pnl_curve,
    get_aggregated_performance,
)


class TestPositionMetricsValidation:
    """Test PositionMetrics model validation."""

    def test_valid_position_metrics(self):
        """Test creating PositionMetrics with valid data."""
        metrics = PositionMetrics(
            position_id=uuid4(),
            pattern_type="SPRING",
            individual_r=Decimal("2.5"),
            entry_price=Decimal("100.00"),
            exit_price=Decimal("105.00"),
            shares=Decimal("50"),
            realized_pnl=Decimal("250.00"),
            win_loss_status=WinLossStatus.WIN,
            duration_bars=120,
            entry_date=datetime.now(UTC),
            exit_date=datetime.now(UTC),
            entry_phase="Phase C",
        )

        assert metrics.pattern_type == "SPRING"
        assert metrics.individual_r == Decimal("2.5")
        assert metrics.win_loss_status == WinLossStatus.WIN
        assert metrics.entry_phase == "Phase C"

    def test_position_metrics_decimal_precision(self):
        """Test Decimal precision is enforced."""
        metrics = PositionMetrics(
            position_id=uuid4(),
            pattern_type="SOS",
            individual_r=Decimal("1.8765"),  # 4 decimal places
            entry_price=Decimal("100.12345678"),  # 8 decimal places
            exit_price=Decimal("103.87654321"),
            shares=Decimal("100"),
            realized_pnl=Decimal("375.30864300"),
            win_loss_status=WinLossStatus.WIN,
            duration_bars=50,
            entry_date=datetime.now(UTC),
            exit_date=datetime.now(UTC),
            entry_phase="Phase D",
        )

        # Decimal precision preserved
        assert metrics.individual_r == Decimal("1.8765")
        assert metrics.entry_price == Decimal("100.12345678")

    def test_position_metrics_serialization(self):
        """Test PositionMetrics serializes correctly with Decimals as strings."""
        metrics = PositionMetrics(
            position_id=uuid4(),
            pattern_type="LPS",
            individual_r=Decimal("3.25"),
            entry_price=Decimal("100.00"),
            exit_price=Decimal("106.50"),
            shares=Decimal("50"),
            realized_pnl=Decimal("325.00"),
            win_loss_status=WinLossStatus.WIN,
            duration_bars=80,
            entry_date=datetime.now(UTC),
            exit_date=datetime.now(UTC),
            entry_phase="Phase C",
        )

        serialized = metrics.serialize_model()

        # Decimals should be strings
        assert isinstance(serialized["individual_r"], str)
        assert serialized["individual_r"] == "3.25"
        assert isinstance(serialized["entry_price"], str)
        assert serialized["entry_price"] == "100.00"
        # Enum should be value
        assert serialized["win_loss_status"] == "WIN"


class TestCampaignMetricsValidation:
    """Test CampaignMetrics model validation."""

    def test_valid_campaign_metrics(self):
        """Test creating CampaignMetrics with all required fields."""
        metrics = CampaignMetrics(
            campaign_id=uuid4(),
            symbol="AAPL",
            total_return_pct=Decimal("15.50"),
            total_r_achieved=Decimal("8.2"),
            duration_days=45,
            max_drawdown=Decimal("5.25"),
            total_positions=3,
            winning_positions=2,
            losing_positions=1,
            win_rate=Decimal("66.67"),
            average_entry_price=Decimal("150.00"),
            average_exit_price=Decimal("173.25"),
            expected_jump_target=Decimal("175.00"),
            actual_high_reached=Decimal("178.50"),
            target_achievement_pct=Decimal("114.00"),
            expected_r=Decimal("10.0"),
            actual_r_achieved=Decimal("8.2"),
            phase_c_avg_r=Decimal("3.5"),
            phase_d_avg_r=Decimal("2.1"),
            phase_c_positions=2,
            phase_d_positions=1,
            phase_c_win_rate=Decimal("100.00"),
            phase_d_win_rate=Decimal("100.00"),
            position_details=[],
            calculation_timestamp=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        assert metrics.symbol == "AAPL"
        assert metrics.total_r_achieved == Decimal("8.2")
        assert metrics.win_rate == Decimal("66.67")
        assert metrics.phase_c_avg_r == Decimal("3.5")
        assert metrics.phase_d_avg_r == Decimal("2.1")

    def test_campaign_metrics_win_rate_bounds(self):
        """Test win_rate must be between 0 and 100."""
        # Valid win rate
        metrics = CampaignMetrics(
            campaign_id=uuid4(),
            symbol="AAPL",
            total_return_pct=Decimal("10.00"),
            total_r_achieved=Decimal("5.0"),
            duration_days=30,
            max_drawdown=Decimal("3.00"),
            total_positions=10,
            winning_positions=7,
            losing_positions=3,
            win_rate=Decimal("70.00"),  # Valid
            average_entry_price=Decimal("100.00"),
            average_exit_price=Decimal("110.00"),
            position_details=[],
            calculation_timestamp=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        assert metrics.win_rate == Decimal("70.00")

        # Invalid win rate > 100
        with pytest.raises(Exception):  # ValidationError
            CampaignMetrics(
                campaign_id=uuid4(),
                symbol="AAPL",
                total_return_pct=Decimal("10.00"),
                total_r_achieved=Decimal("5.0"),
                duration_days=30,
                max_drawdown=Decimal("3.00"),
                total_positions=10,
                winning_positions=7,
                losing_positions=3,
                win_rate=Decimal("150.00"),  # INVALID!
                average_entry_price=Decimal("100.00"),
                average_exit_price=Decimal("110.00"),
                position_details=[],
                calculation_timestamp=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )


class TestCalculateCampaignPerformance:
    """Test calculate_campaign_performance function (AC #7)."""

    def test_campaign_with_three_positions_two_wins_one_loss(self):
        """
        Test campaign with 3 positions: 2 wins (1.5R, 2.0R), 1 loss (-1.0R).

        Expected:
        - total_r_achieved = 2.5R
        - win_rate = 66.67%
        - total_return_pct calculated correctly
        """
        campaign_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=30)
        completed_at = datetime.now(UTC)

        # Position 1: SPRING - WIN (1.5R)
        # Entry $100, Stop $98, Exit $103 → R = (103-100)/(100-98) = 1.5R
        pos1 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=started_at,
            entry_price=Decimal("100.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at - timedelta(days=10),
            exit_price=Decimal("103.00"),
            realized_pnl=Decimal("150.00"),  # (103-100) * 50 = $150
        )

        # Position 2: SOS - WIN (2.0R)
        # Entry $102, Stop $100, Exit $106 → R = (106-102)/(102-100) = 2.0R
        pos2 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SOS",
            entry_date=started_at + timedelta(days=5),
            entry_price=Decimal("102.00"),
            shares=Decimal("40"),
            stop_loss=Decimal("100.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at - timedelta(days=5),
            exit_price=Decimal("106.00"),
            realized_pnl=Decimal("160.00"),  # (106-102) * 40 = $160
        )

        # Position 3: LPS - LOSS (-1.0R)
        # Entry $103, Stop $101, Exit $101 → R = (101-103)/(103-101) = -1.0R
        pos3 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="LPS",
            entry_date=started_at + timedelta(days=10),
            entry_price=Decimal("103.00"),
            shares=Decimal("30"),
            stop_loss=Decimal("101.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at,
            exit_price=Decimal("101.00"),
            realized_pnl=Decimal("-60.00"),  # (101-103) * 30 = -$60
        )

        positions = [pos1, pos2, pos3]
        initial_capital = Decimal("10000.00")

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=positions,
            started_at=started_at,
            completed_at=completed_at,
            initial_capital=initial_capital,
        )

        # Verify campaign-level metrics
        assert metrics.total_positions == 3
        assert metrics.winning_positions == 2
        assert metrics.losing_positions == 1
        assert metrics.win_rate == Decimal("66.67")  # 2/3 = 66.67%

        # Verify total R achieved = 1.5R + 2.0R + (-1.0R) = 2.5R
        assert metrics.total_r_achieved == Decimal("2.5000")

        # Verify total return %
        # Total P&L = $150 + $160 - $60 = $250
        # Return % = ($250 / $10000) * 100 = 2.5%
        expected_return = (Decimal("250.00") / initial_capital * Decimal("100")).quantize(
            Decimal("0.00000001")
        )
        assert metrics.total_return_pct == expected_return

        # Verify position details created
        assert len(metrics.position_details) == 3

        # Verify individual R calculations
        spring_metrics = next(p for p in metrics.position_details if p.pattern_type == "SPRING")
        assert spring_metrics.individual_r == Decimal("1.5000")
        assert spring_metrics.win_loss_status == WinLossStatus.WIN

        sos_metrics = next(p for p in metrics.position_details if p.pattern_type == "SOS")
        assert sos_metrics.individual_r == Decimal("2.0000")
        assert sos_metrics.win_loss_status == WinLossStatus.WIN

        lps_metrics = next(p for p in metrics.position_details if p.pattern_type == "LPS")
        assert lps_metrics.individual_r == Decimal("-1.0000")
        assert lps_metrics.win_loss_status == WinLossStatus.LOSS

    def test_campaign_target_achievement_reached(self):
        """Test target_achievement_pct when Jump target reached."""
        campaign_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=20)
        completed_at = datetime.now(UTC)

        # Single position reaching Jump target
        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=started_at,
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at,
            exit_price=Decimal("120.00"),  # Reached Jump target!
            realized_pnl=Decimal("2000.00"),
        )

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=[pos],
            started_at=started_at,
            completed_at=completed_at,
            initial_capital=Decimal("10000.00"),
            jump_target=Decimal("120.00"),  # Jump target
            actual_high_reached=Decimal("120.00"),  # Reached exactly
        )

        # Target achievement should be 100%
        # (120 - 100) / (120 - 100) * 100 = 100%
        assert metrics.target_achievement_pct == Decimal("100.00")

    def test_campaign_target_achievement_exceeded(self):
        """Test target_achievement_pct when Jump target exceeded."""
        campaign_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=20)
        completed_at = datetime.now(UTC)

        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=started_at,
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at,
            exit_price=Decimal("125.00"),  # Exceeded Jump!
            realized_pnl=Decimal("2500.00"),
        )

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=[pos],
            started_at=started_at,
            completed_at=completed_at,
            initial_capital=Decimal("10000.00"),
            jump_target=Decimal("120.00"),
            actual_high_reached=Decimal("125.00"),  # Exceeded by $5
        )

        # Target achievement > 100%
        # (125 - 100) / (120 - 100) * 100 = 125%
        assert metrics.target_achievement_pct == Decimal("125.00")

    def test_campaign_target_achievement_not_reached(self):
        """Test target_achievement_pct when Jump target NOT reached."""
        campaign_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=20)
        completed_at = datetime.now(UTC)

        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=started_at,
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at,
            exit_price=Decimal("110.00"),  # Stopped out before Jump
            realized_pnl=Decimal("1000.00"),
        )

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=[pos],
            started_at=started_at,
            completed_at=completed_at,
            initial_capital=Decimal("10000.00"),
            jump_target=Decimal("120.00"),
            actual_high_reached=Decimal("115.00"),  # Got to $115 (stopped before Jump)
        )

        # Target achievement < 100%
        # (115 - 100) / (120 - 100) * 100 = 75%
        assert metrics.target_achievement_pct == Decimal("75.00")


class TestMaxDrawdownCalculation:
    """Test calculate_max_drawdown_from_equity_curve."""

    def test_max_drawdown_with_single_drawdown(self):
        """
        Test max drawdown with equity curve: [10000, 11000, 10500, 12000, 11500].

        Expected max drawdown: (11000 - 10500) / 11000 = 4.55%
        """
        campaign_id = uuid4()
        initial_capital = Decimal("10000.00")

        # Position 1: +$1000 → Equity = $11000
        pos1 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC) - timedelta(days=5),
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC) - timedelta(days=4),
            exit_price=Decimal("110.00"),
            realized_pnl=Decimal("1000.00"),
        )

        # Position 2: -$500 → Equity = $10500
        pos2 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SOS",
            entry_date=datetime.now(UTC) - timedelta(days=3),
            entry_price=Decimal("110.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("108.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC) - timedelta(days=2),
            exit_price=Decimal("100.00"),
            realized_pnl=Decimal("-500.00"),
        )

        # Position 3: +$1500 → Equity = $12000
        pos3 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="LPS",
            entry_date=datetime.now(UTC) - timedelta(days=1),
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("115.00"),
            realized_pnl=Decimal("1500.00"),
        )

        positions = [pos1, pos2, pos3]

        max_dd = calculate_max_drawdown_from_equity_curve(positions, initial_capital)

        # Max DD = (11000 - 10500) / 11000 = 0.045454... = 4.5454...%
        expected_dd = (
            (Decimal("11000") - Decimal("10500")) / Decimal("11000") * Decimal("100")
        ).quantize(Decimal("0.00000001"))
        assert max_dd == expected_dd

    def test_max_drawdown_no_drawdown(self):
        """Test max drawdown with monotonically increasing equity (no drawdown)."""
        campaign_id = uuid4()
        initial_capital = Decimal("10000.00")

        # Position 1: +$500
        pos1 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC) - timedelta(days=2),
            entry_price=Decimal("100.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC) - timedelta(days=1),
            exit_price=Decimal("110.00"),
            realized_pnl=Decimal("500.00"),
        )

        # Position 2: +$1000
        pos2 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SOS",
            entry_date=datetime.now(UTC) - timedelta(days=1),
            entry_price=Decimal("110.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("108.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("120.00"),
            realized_pnl=Decimal("1000.00"),
        )

        positions = [pos1, pos2]

        max_dd = calculate_max_drawdown_from_equity_curve(positions, initial_capital)

        # No drawdown - should be 0
        assert max_dd == Decimal("0.00000000")

    def test_max_drawdown_empty_positions(self):
        """Test max drawdown with no positions."""
        max_dd = calculate_max_drawdown_from_equity_curve([], Decimal("10000.00"))
        assert max_dd == Decimal("0.00000000")


class TestEdgeCases:
    """Test edge cases for campaign performance calculation."""

    def test_campaign_with_no_closed_positions(self):
        """Test campaign with no closed positions raises ValueError."""
        campaign_id = uuid4()

        # Open position (not closed)
        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            current_price=Decimal("105.00"),
            current_pnl=Decimal("500.00"),
            status=PositionStatus.OPEN,  # Still OPEN!
        )

        with pytest.raises(ValueError, match="no closed positions"):
            calculate_campaign_performance(
                campaign_id=campaign_id,
                symbol="AAPL",
                positions=[pos],
                started_at=datetime.now(UTC) - timedelta(days=10),
                completed_at=datetime.now(UTC),
                initial_capital=Decimal("10000.00"),
            )

    def test_campaign_with_all_breakeven_positions(self):
        """Test campaign with all breakeven positions (realized_pnl = 0)."""
        campaign_id = uuid4()

        # Breakeven position
        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC) - timedelta(days=5),
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("100.00"),  # Breakeven!
            realized_pnl=Decimal("0.00"),
        )

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=[pos],
            started_at=datetime.now(UTC) - timedelta(days=5),
            completed_at=datetime.now(UTC),
            initial_capital=Decimal("10000.00"),
        )

        assert metrics.total_positions == 1
        assert metrics.winning_positions == 0
        assert metrics.losing_positions == 0
        assert metrics.win_rate == Decimal("0.00")
        assert metrics.total_r_achieved == Decimal("0.0000")
        assert metrics.total_return_pct == Decimal("0.00000000")

        # Verify position metrics
        assert len(metrics.position_details) == 1
        assert metrics.position_details[0].win_loss_status == WinLossStatus.BREAKEVEN
        assert metrics.position_details[0].individual_r == Decimal("0.0000")

    def test_campaign_with_single_position(self):
        """Test campaign with single position calculates all metrics correctly."""
        campaign_id = uuid4()

        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC) - timedelta(days=10),
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("106.00"),
            realized_pnl=Decimal("600.00"),
        )

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=[pos],
            started_at=datetime.now(UTC) - timedelta(days=10),
            completed_at=datetime.now(UTC),
            initial_capital=Decimal("10000.00"),
        )

        assert metrics.total_positions == 1
        assert metrics.winning_positions == 1
        assert metrics.losing_positions == 0
        assert metrics.win_rate == Decimal("100.00")
        # R = (106 - 100) / (100 - 98) = 3.0R
        assert metrics.total_r_achieved == Decimal("3.0000")


class TestAggregatedPerformance:
    """Test get_aggregated_performance function (AC #6)."""

    def test_aggregated_performance_with_10_campaigns(self):
        """Test aggregated metrics across 10 synthetic campaigns."""
        campaigns_metrics = []

        # Create 10 campaigns with varied results
        for i in range(10):
            campaign_id = uuid4()
            # Alternate between winning and losing campaigns
            if i % 2 == 0:
                # Winning campaign
                total_return = Decimal(f"{10 + i}.00")
                total_r = Decimal(f"{5 + i}.0")
                winning_pos = 3
                losing_pos = 1
            else:
                # Losing campaign
                total_return = Decimal(f"-{5 + i}.00")
                total_r = Decimal(f"-{2 + i}.0")
                winning_pos = 1
                losing_pos = 3

            metrics = CampaignMetrics(
                campaign_id=campaign_id,
                symbol="AAPL",
                total_return_pct=total_return,
                total_r_achieved=total_r,
                duration_days=30 + i,
                max_drawdown=Decimal(f"{3 + i}.00"),
                total_positions=4,
                winning_positions=winning_pos,
                losing_positions=losing_pos,
                win_rate=Decimal(f"{(winning_pos / 4) * 100}"),
                average_entry_price=Decimal("100.00"),
                average_exit_price=Decimal("110.00"),
                position_details=[],
                calculation_timestamp=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            campaigns_metrics.append(metrics)

        aggregated = get_aggregated_performance(campaigns_metrics)

        assert aggregated.total_campaigns_completed == 10

        # Overall win rate = 5 winning campaigns / 10 = 50%
        assert aggregated.overall_win_rate == Decimal("50.00")

        # Verify average_campaign_return_pct calculated
        # (10 + 11 + 12 + 13 + 14) - (6 + 7 + 8 + 9 + 10) = 60 - 40 = 20
        # Avg = 20 / 10 = 2.0%
        expected_avg_return = (
            sum([Decimal(f"{10 + i}.00") for i in range(0, 10, 2)])
            - sum([Decimal(f"{5 + i}.00") for i in range(1, 10, 2)])
        ) / Decimal("10")
        assert aggregated.average_campaign_return_pct == expected_avg_return.quantize(
            Decimal("0.00000001")
        )

        # Best campaign should be campaign with highest return (i=8, return = 18.00)
        assert aggregated.best_campaign is not None

        # Worst campaign should be campaign with lowest return (i=9, return = -14.00)
        assert aggregated.worst_campaign is not None

        # Median duration
        # Durations: 30, 31, 32, 33, 34, 35, 36, 37, 38, 39
        # Median = (34 + 35) / 2 = 34 (integer division)
        assert aggregated.median_duration_days == 34

    def test_aggregated_performance_with_empty_list(self):
        """Test aggregated metrics with no campaigns."""
        aggregated = get_aggregated_performance([])

        assert aggregated.total_campaigns_completed == 0
        assert aggregated.overall_win_rate == Decimal("0.00")
        assert aggregated.average_campaign_return_pct == Decimal("0.00000000")
        assert aggregated.average_r_achieved_per_campaign == Decimal("0.0000")
        assert aggregated.best_campaign is None
        assert aggregated.worst_campaign is None
        assert aggregated.median_duration_days is None


class TestPnLCurveGeneration:
    """Test generate_pnl_curve function (AC #9)."""

    def test_pnl_curve_with_multiple_positions(self):
        """Test P&L curve generation with chronological ordering."""
        campaign_id = uuid4()
        initial_capital = Decimal("10000.00")

        # Position 1: +$500
        pos1 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC) - timedelta(days=3),
            entry_price=Decimal("100.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC) - timedelta(days=2),
            exit_price=Decimal("110.00"),
            realized_pnl=Decimal("500.00"),
        )

        # Position 2: -$200
        pos2 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SOS",
            entry_date=datetime.now(UTC) - timedelta(days=2),
            entry_price=Decimal("110.00"),
            shares=Decimal("20"),
            stop_loss=Decimal("108.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC) - timedelta(days=1),
            exit_price=Decimal("100.00"),
            realized_pnl=Decimal("-200.00"),
        )

        # Position 3: +$1000
        pos3 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="LPS",
            entry_date=datetime.now(UTC) - timedelta(days=1),
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=datetime.now(UTC),
            exit_price=Decimal("110.00"),
            realized_pnl=Decimal("1000.00"),
        )

        positions = [pos1, pos2, pos3]

        pnl_curve = generate_pnl_curve(campaign_id, positions, initial_capital)

        # Verify curve has 3 data points
        assert len(pnl_curve.data_points) == 3

        # Verify chronological ordering
        assert pnl_curve.data_points[0].cumulative_pnl == Decimal("500.00000000")
        assert pnl_curve.data_points[1].cumulative_pnl == Decimal("300.00000000")  # 500 - 200
        assert pnl_curve.data_points[2].cumulative_pnl == Decimal("1300.00000000")  # 300 + 1000

        # Verify cumulative return %
        # Point 1: 500 / 10000 * 100 = 5.0%
        assert pnl_curve.data_points[0].cumulative_return_pct == Decimal("5.00000000")
        # Point 2: 300 / 10000 * 100 = 3.0%
        assert pnl_curve.data_points[1].cumulative_return_pct == Decimal("3.00000000")
        # Point 3: 1300 / 10000 * 100 = 13.0%
        assert pnl_curve.data_points[2].cumulative_return_pct == Decimal("13.00000000")

        # Verify max drawdown point identified
        # Running max equity: [10500, 10500, 11300]
        # Drawdowns: [0%, (10500-10300)/10500 = 1.9047...%, 0%]
        assert pnl_curve.max_drawdown_point is not None
        assert pnl_curve.max_drawdown_point.cumulative_pnl == Decimal("300.00000000")

    def test_pnl_curve_with_empty_positions(self):
        """Test P&L curve with no positions."""
        pnl_curve = generate_pnl_curve(uuid4(), [], Decimal("10000.00"))

        assert len(pnl_curve.data_points) == 0
        assert pnl_curve.max_drawdown_point is None


class TestPhaseSpecificMetrics:
    """Test phase-specific performance metrics (AC #11)."""

    def test_phase_c_and_phase_d_metrics(self):
        """Test Phase C (SPRING/LPS) vs Phase D (SOS) metrics calculated separately."""
        campaign_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=30)
        completed_at = datetime.now(UTC)

        # Phase C: SPRING (3.5R win)
        pos1 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=started_at,
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at - timedelta(days=10),
            exit_price=Decimal("107.00"),  # R = (107-100)/(100-98) = 3.5R
            realized_pnl=Decimal("700.00"),
        )

        # Phase C: LPS (2.8R win)
        pos2 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="LPS",
            entry_date=started_at + timedelta(days=10),
            entry_price=Decimal("105.00"),
            shares=Decimal("50"),
            stop_loss=Decimal("100.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at - timedelta(days=5),
            exit_price=Decimal("119.00"),  # R = (119-105)/(105-100) = 2.8R
            realized_pnl=Decimal("700.00"),
        )

        # Phase D: SOS (1.9R win)
        pos3 = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SOS",
            entry_date=started_at + timedelta(days=15),
            entry_price=Decimal("110.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("105.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at,
            exit_price=Decimal("119.50"),  # R = (119.5-110)/(110-105) = 1.9R
            realized_pnl=Decimal("950.00"),
        )

        positions = [pos1, pos2, pos3]

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=positions,
            started_at=started_at,
            completed_at=completed_at,
            initial_capital=Decimal("10000.00"),
        )

        # Verify phase counts
        assert metrics.phase_c_positions == 2  # SPRING + LPS
        assert metrics.phase_d_positions == 1  # SOS

        # Verify Phase C avg R = (3.5R + 2.8R) / 2 = 3.15R
        assert metrics.phase_c_avg_r == Decimal("3.1500")

        # Verify Phase D avg R = 1.9R
        assert metrics.phase_d_avg_r == Decimal("1.9000")

        # Verify Phase C outperforms Phase D (expected relationship)
        assert metrics.phase_c_avg_r > metrics.phase_d_avg_r  # type: ignore

        # Verify win rates
        assert metrics.phase_c_win_rate == Decimal("100.00")  # 2 wins / 2 = 100%
        assert metrics.phase_d_win_rate == Decimal("100.00")  # 1 win / 1 = 100%

    def test_phase_metrics_with_only_phase_c(self):
        """Test phase metrics when only Phase C entries exist."""
        campaign_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=20)
        completed_at = datetime.now(UTC)

        # Only Phase C: SPRING
        pos = Position(
            id=uuid4(),
            campaign_id=campaign_id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1h",
            pattern_type="SPRING",
            entry_date=started_at,
            entry_price=Decimal("100.00"),
            shares=Decimal("100"),
            stop_loss=Decimal("98.00"),
            status=PositionStatus.CLOSED,
            closed_date=completed_at,
            exit_price=Decimal("110.00"),
            realized_pnl=Decimal("1000.00"),
        )

        metrics = calculate_campaign_performance(
            campaign_id=campaign_id,
            symbol="AAPL",
            positions=[pos],
            started_at=started_at,
            completed_at=completed_at,
            initial_capital=Decimal("10000.00"),
        )

        # Phase C should have metrics
        assert metrics.phase_c_positions == 1
        assert metrics.phase_c_avg_r == Decimal("5.0000")  # R = (110-100)/(100-98) = 5.0R
        assert metrics.phase_c_win_rate == Decimal("100.00")

        # Phase D should be None (no positions)
        assert metrics.phase_d_positions == 0
        assert metrics.phase_d_avg_r is None
        assert metrics.phase_d_win_rate is None
