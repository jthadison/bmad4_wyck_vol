"""
Unit tests for MetricsCalculator (Story 12.1 Task 7).

Tests:
- Total return percentage calculation
- CAGR calculation
- Sharpe ratio calculation
- Max drawdown calculation
- Win rate, R-multiple, profit factor
- Edge cases (no trades, no equity curve)

Author: Story 12.1 Task 7
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.metrics import MetricsCalculator
from src.models.backtest import (
    BacktestTrade,
    EquityCurvePoint,
)


@pytest.fixture
def calculator():
    """Fixture for MetricsCalculator."""
    return MetricsCalculator()


@pytest.fixture
def sample_equity_curve():
    """Fixture for sample equity curve."""
    start_date = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        EquityCurvePoint(
            timestamp=start_date + timedelta(days=i),
            equity_value=Decimal("100000") + Decimal(str(i * 1000)),
            portfolio_value=Decimal("100000") + Decimal(str(i * 1000)),
            cash=Decimal("50000"),
            positions_value=Decimal("50000") + Decimal(str(i * 1000)),
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_trades():
    """Fixture for sample trades."""
    return [
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("155.00"),
            entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
            realized_pnl=Decimal("500.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("155.00"),
            exit_price=Decimal("150.00"),
            entry_timestamp=datetime(2024, 1, 6, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 10, tzinfo=UTC),
            realized_pnl=Decimal("-500.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("160.00"),
            entry_timestamp=datetime(2024, 1, 11, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 15, tzinfo=UTC),
            realized_pnl=Decimal("1000.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
        ),
    ]


class TestMetricsCalculatorInitialization:
    """Test MetricsCalculator initialization."""

    def test_initialization_with_defaults(self):
        """Test calculator initialization with default risk-free rate."""
        calculator = MetricsCalculator()
        assert calculator.risk_free_rate == Decimal("0.02")  # 2% default

    def test_initialization_with_custom_risk_free_rate(self):
        """Test calculator initialization with custom risk-free rate."""
        calculator = MetricsCalculator(risk_free_rate=Decimal("0.05"))
        assert calculator.risk_free_rate == Decimal("0.05")


class TestTotalReturnCalculation:
    """Test total return percentage calculation."""

    def test_calculate_total_return_pct_positive(self, calculator):
        """Test total return calculation with profit."""
        # $100,000 -> $115,000 = 15% return
        total_return = calculator._calculate_total_return_pct(
            final_value=Decimal("115000"),
            initial_capital=Decimal("100000"),
        )
        assert total_return == Decimal("15")

    def test_calculate_total_return_pct_negative(self, calculator):
        """Test total return calculation with loss."""
        # $100,000 -> $85,000 = -15% return
        total_return = calculator._calculate_total_return_pct(
            final_value=Decimal("85000"),
            initial_capital=Decimal("100000"),
        )
        assert total_return == Decimal("-15")

    def test_calculate_total_return_pct_zero_initial_capital(self, calculator):
        """Test total return with zero initial capital (edge case)."""
        total_return = calculator._calculate_total_return_pct(
            final_value=Decimal("100000"),
            initial_capital=Decimal("0"),
        )
        assert total_return == Decimal("0")


class TestCAGRCalculation:
    """Test CAGR calculation."""

    def test_calculate_cagr_one_year(self, calculator):
        """Test CAGR over one year."""
        # $100,000 -> $115,000 over 1 year = 15% CAGR
        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2025, 1, 1, tzinfo=UTC)

        cagr = calculator._calculate_cagr(
            final_value=Decimal("115000"),
            initial_capital=Decimal("100000"),
            start_date=start_date,
            end_date=end_date,
        )

        # CAGR should be approximately 0.15 (15%)
        assert abs(cagr - Decimal("0.15")) < Decimal("0.001")

    def test_calculate_cagr_two_years(self, calculator):
        """Test CAGR over two years."""
        # $100,000 -> $121,000 over 2 years = 10% CAGR
        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2026, 1, 1, tzinfo=UTC)

        cagr = calculator._calculate_cagr(
            final_value=Decimal("121000"),
            initial_capital=Decimal("100000"),
            start_date=start_date,
            end_date=end_date,
        )

        # CAGR should be approximately 0.10 (10%)
        assert abs(cagr - Decimal("0.10")) < Decimal("0.001")

    def test_calculate_cagr_zero_years(self, calculator):
        """Test CAGR with same start and end date."""
        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2024, 1, 1, tzinfo=UTC)

        cagr = calculator._calculate_cagr(
            final_value=Decimal("115000"),
            initial_capital=Decimal("100000"),
            start_date=start_date,
            end_date=end_date,
        )

        assert cagr == Decimal("0")


class TestSharpeRatioCalculation:
    """Test Sharpe ratio calculation."""

    def test_calculate_sharpe_ratio_positive_returns(self, calculator):
        """Test Sharpe ratio with positive returns (with some volatility)."""
        # Create equity curve with varying positive returns (realistic volatility)
        # Returns: [0, 0.01, 0.02, 0.008, 0.015, 0.012, 0.018...]
        returns = [
            Decimal("0"),
            Decimal("0.01"),
            Decimal("0.02"),
            Decimal("0.008"),
            Decimal("0.015"),
            Decimal("0.012"),
            Decimal("0.018"),
            Decimal("0.009"),
            Decimal("0.014"),
            Decimal("0.011"),
            Decimal("0.016"),
            Decimal("0.013"),
            Decimal("0.010"),
            Decimal("0.017"),
            Decimal("0.012"),
            Decimal("0.015"),
            Decimal("0.011"),
            Decimal("0.014"),
            Decimal("0.013"),
            Decimal("0.016"),
        ]

        base_value = Decimal("100000")
        equity_curve = []
        portfolio_value = base_value

        for i, daily_return in enumerate(returns):
            if i > 0:
                portfolio_value = portfolio_value * (Decimal("1") + daily_return)

            equity_curve.append(
                EquityCurvePoint(
                    timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                    equity_value=portfolio_value,
                    portfolio_value=portfolio_value,
                    cash=Decimal("50000"),
                    positions_value=portfolio_value - Decimal("50000"),
                )
            )

        sharpe = calculator._calculate_sharpe_ratio(equity_curve)

        # Sharpe should be positive with positive returns and volatility
        assert sharpe > Decimal("0")

    def test_calculate_sharpe_ratio_zero_std_dev(self, calculator):
        """Test Sharpe ratio with zero std deviation (no volatility)."""
        # All returns are exactly 0
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            )
            for i in range(10)
        ]

        sharpe = calculator._calculate_sharpe_ratio(equity_curve)
        assert sharpe == Decimal("0")

    def test_calculate_sharpe_ratio_insufficient_data(self, calculator):
        """Test Sharpe ratio with insufficient data points."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            )
        ]

        sharpe = calculator._calculate_sharpe_ratio(equity_curve)
        assert sharpe == Decimal("0")


class TestDrawdownCalculation:
    """Test drawdown calculation."""

    def test_calculate_drawdown_with_decline(self, calculator):
        """Test drawdown calculation with peak-to-trough decline."""
        # Peak at $115,000, trough at $103,500 = 10% drawdown
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                portfolio_value=Decimal("115000"),  # Peak
                equity_value=Decimal("115000"),
                cash=Decimal("100000"),
                positions_value=Decimal("15000"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 3, tzinfo=UTC),
                portfolio_value=Decimal("110000"),  # Decline
                equity_value=Decimal("110000"),
                cash=Decimal("100000"),
                positions_value=Decimal("10000"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 4, tzinfo=UTC),
                portfolio_value=Decimal("103500"),  # Trough (10% from peak)
                equity_value=Decimal("103500"),
                cash=Decimal("100000"),
                positions_value=Decimal("3500"),
            ),
        ]

        max_drawdown, max_duration = calculator._calculate_drawdown(equity_curve)

        # Max drawdown should be 10%
        expected_drawdown = Decimal("11500") / Decimal("115000")
        assert abs(max_drawdown - expected_drawdown) < Decimal("0.0001")
        assert max_duration == 2  # 2 days from peak to trough

    def test_calculate_drawdown_no_decline(self, calculator):
        """Test drawdown with only upward movement."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                portfolio_value=Decimal("100000") + Decimal(str(i * 1000)),
                equity_value=Decimal("100000") + Decimal(str(i * 1000)),
                cash=Decimal("50000"),
                positions_value=Decimal("50000") + Decimal(str(i * 1000)),
            )
            for i in range(10)
        ]

        max_drawdown, max_duration = calculator._calculate_drawdown(equity_curve)
        assert max_drawdown == Decimal("0")
        assert max_duration == 0


class TestWinRateCalculation:
    """Test win rate calculation."""

    def test_calculate_win_rate_60_percent(self, calculator):
        """Test win rate calculation with 60% wins."""
        win_rate = calculator._calculate_win_rate(winning_trades=60, total_trades=100)
        assert win_rate == Decimal("0.60")

    def test_calculate_win_rate_100_percent(self, calculator):
        """Test win rate with all wins."""
        win_rate = calculator._calculate_win_rate(winning_trades=10, total_trades=10)
        assert win_rate == Decimal("1.0")

    def test_calculate_win_rate_zero_trades(self, calculator):
        """Test win rate with zero trades."""
        win_rate = calculator._calculate_win_rate(winning_trades=0, total_trades=0)
        assert win_rate == Decimal("0")


class TestAvgRMultipleCalculation:
    """Test average R-multiple calculation."""

    def test_calculate_avg_r_multiple_positive(self, calculator, sample_trades):
        """Test average R-multiple calculation."""
        # Set R-multiples: 2.0, -1.0, 3.0
        sample_trades[0].r_multiple = Decimal("2.0")
        sample_trades[1].r_multiple = Decimal("-1.0")
        sample_trades[2].r_multiple = Decimal("3.0")

        avg_r = calculator._calculate_avg_r_multiple(sample_trades)
        assert avg_r == Decimal("4.0") / Decimal("3")  # (2 - 1 + 3) / 3

    def test_calculate_avg_r_multiple_no_trades(self, calculator):
        """Test average R-multiple with no trades."""
        avg_r = calculator._calculate_avg_r_multiple([])
        assert avg_r == Decimal("0")


class TestProfitFactorCalculation:
    """Test profit factor calculation."""

    def test_calculate_profit_factor_2_to_1(self, calculator, sample_trades):
        """Test profit factor with 2:1 win/loss ratio."""
        # Wins: $500 + $1000 = $1500
        # Losses: $500
        # Profit factor: 1500 / 500 = 3.0
        profit_factor = calculator._calculate_profit_factor(sample_trades)
        assert profit_factor == Decimal("3.0")

    def test_calculate_profit_factor_no_losses(self, calculator):
        """Test profit factor with no losing trades."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]

        profit_factor = calculator._calculate_profit_factor(trades)
        # No losses but has wins - return 999.99 (capped infinity)
        assert profit_factor == Decimal("999.99")


class TestFullMetricsCalculation:
    """Test full metrics calculation."""

    def test_calculate_metrics_comprehensive(self, calculator, sample_equity_curve, sample_trades):
        """Test full metrics calculation with all fields."""
        # Set R-multiples
        sample_trades[0].r_multiple = Decimal("2.0")
        sample_trades[1].r_multiple = Decimal("-1.0")
        sample_trades[2].r_multiple = Decimal("3.0")

        metrics = calculator.calculate_metrics(
            equity_curve=sample_equity_curve,
            trades=sample_trades,
            initial_capital=Decimal("100000"),
        )

        # Verify all fields are set
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("2") / Decimal("3")
        assert metrics.profit_factor == Decimal("3.0")
        # avg_r_multiple is rounded to 4 decimal places
        expected_avg_r = Decimal("4.0") / Decimal("3")
        assert abs(metrics.avg_r_multiple - expected_avg_r) < Decimal("0.0001")
        assert metrics.total_return_pct == Decimal("9")  # $100k -> $109k
        assert metrics.max_drawdown <= Decimal("0")  # Drawdown should be negative or zero
        assert metrics.cagr >= Decimal("0")
        assert metrics.sharpe_ratio >= Decimal("0")

    def test_calculate_metrics_no_trades(self, calculator, sample_equity_curve):
        """Test metrics calculation with no trades."""
        metrics = calculator.calculate_metrics(
            equity_curve=sample_equity_curve,
            trades=[],
            initial_capital=Decimal("100000"),
        )

        # Should have return metrics but zero trade stats
        assert metrics.total_return_pct == Decimal("9")
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        # Win rate, avg_r, profit_factor should be zero for no trades
        assert metrics.win_rate == Decimal("0")
        assert metrics.avg_r_multiple == Decimal("0")
        assert metrics.profit_factor == Decimal("0")

    def test_calculate_metrics_no_equity_curve(self, calculator, sample_trades):
        """Test metrics calculation with no equity curve."""
        metrics = calculator.calculate_metrics(
            equity_curve=[],
            trades=sample_trades,
            initial_capital=Decimal("100000"),
        )

        # Should return default/empty metrics (all zeros or None)
        assert metrics.total_return_pct is None or metrics.total_return_pct == Decimal("0.0")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_metrics_with_single_trade(self, calculator):
        """Test metrics with only one trade."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                portfolio_value=Decimal("100500"),
                equity_value=Decimal("100500"),
                cash=Decimal("100500"),
                positions_value=Decimal("0"),
            ),
        ]

        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            )
        ]
        trades[0].r_multiple = Decimal("2.0")

        metrics = calculator.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )

        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 0
        assert metrics.win_rate == Decimal("1.0")


# ===========================================================================================
# Enhanced Metrics Tests (Story 12.6A IMPL-004)
# ===========================================================================================


class TestMonthlyReturnsCalculation:
    """Test monthly returns calculation (Story 12.6A AC2)."""

    def test_calculate_monthly_returns_single_month(self, calculator):
        """Test monthly returns for a single month."""
        # January 2024: $100,000 -> $105,000
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                equity_value=Decimal("102500"),
                portfolio_value=Decimal("102500"),
                cash=Decimal("100000"),
                positions_value=Decimal("2500"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 31, tzinfo=UTC),
                equity_value=Decimal("105000"),
                portfolio_value=Decimal("105000"),
                cash=Decimal("100000"),
                positions_value=Decimal("5000"),
            ),
        ]

        monthly_returns = calculator.calculate_monthly_returns(equity_curve=equity_curve, trades=[])

        assert len(monthly_returns) == 1
        assert monthly_returns[0].year == 2024
        assert monthly_returns[0].month == 1
        assert monthly_returns[0].return_pct == Decimal("5")  # 5% return
        assert monthly_returns[0].trade_count == 0  # No trades passed
        assert monthly_returns[0].winning_trades == 0
        assert monthly_returns[0].losing_trades == 0

    def test_calculate_monthly_returns_multiple_months(self, calculator):
        """Test monthly returns across multiple months."""
        # Jan-Feb-Mar 2024
        equity_curve = [
            # January
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 31, tzinfo=UTC),
                equity_value=Decimal("105000"),
                portfolio_value=Decimal("105000"),
                cash=Decimal("105000"),
                positions_value=Decimal("0"),
            ),
            # February
            EquityCurvePoint(
                timestamp=datetime(2024, 2, 1, tzinfo=UTC),
                equity_value=Decimal("105000"),
                portfolio_value=Decimal("105000"),
                cash=Decimal("105000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 2, 29, tzinfo=UTC),
                equity_value=Decimal("103000"),  # Loss
                portfolio_value=Decimal("103000"),
                cash=Decimal("103000"),
                positions_value=Decimal("0"),
            ),
            # March
            EquityCurvePoint(
                timestamp=datetime(2024, 3, 1, tzinfo=UTC),
                equity_value=Decimal("103000"),
                portfolio_value=Decimal("103000"),
                cash=Decimal("103000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 3, 31, tzinfo=UTC),
                equity_value=Decimal("108000"),
                portfolio_value=Decimal("108000"),
                cash=Decimal("108000"),
                positions_value=Decimal("0"),
            ),
        ]

        monthly_returns = calculator.calculate_monthly_returns(equity_curve=equity_curve, trades=[])

        assert len(monthly_returns) == 3

        # January: +5%
        assert monthly_returns[0].year == 2024
        assert monthly_returns[0].month == 1
        assert monthly_returns[0].return_pct == Decimal("5")

        # February: -1.9047...% (from 105000 to 103000)
        assert monthly_returns[1].year == 2024
        assert monthly_returns[1].month == 2
        assert monthly_returns[1].return_pct < Decimal("0")  # Negative return

        # March: +4.8543...% (from 103000 to 108000)
        assert monthly_returns[2].year == 2024
        assert monthly_returns[2].month == 3
        assert monthly_returns[2].return_pct > Decimal("0")  # Positive return

    def test_calculate_monthly_returns_empty_equity_curve(self, calculator):
        """Test monthly returns with empty equity curve."""
        monthly_returns = calculator.calculate_monthly_returns(equity_curve=[], trades=[])

        assert monthly_returns == []


class TestDrawdownPeriodsCalculation:
    """Test drawdown periods calculation (Story 12.6A AC3)."""

    def test_calculate_drawdown_periods_with_recovery(self, calculator):
        """Test drawdown period tracking with recovery."""
        # Peak -> Trough -> Recovery cycle
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                portfolio_value=Decimal("115000"),  # Peak
                equity_value=Decimal("115000"),
                cash=Decimal("115000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 2, 1, tzinfo=UTC),
                portfolio_value=Decimal("103500"),  # Trough (-10%)
                equity_value=Decimal("103500"),
                cash=Decimal("103500"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 3, 1, tzinfo=UTC),
                portfolio_value=Decimal("115500"),  # Recovery
                equity_value=Decimal("115500"),
                cash=Decimal("115500"),
                positions_value=Decimal("0"),
            ),
        ]

        drawdown_periods = calculator.calculate_drawdown_periods(equity_curve, top_n=5)

        assert len(drawdown_periods) == 1
        dd = drawdown_periods[0]

        assert dd.peak_date == datetime(2024, 1, 15, tzinfo=UTC)
        assert dd.trough_date == datetime(2024, 2, 1, tzinfo=UTC)
        assert dd.recovery_date == datetime(2024, 3, 1, tzinfo=UTC)
        assert dd.peak_value == Decimal("115000")
        assert dd.trough_value == Decimal("103500")
        assert dd.recovery_value == Decimal("115500")
        assert dd.drawdown_pct == Decimal("-10")  # -10%
        assert dd.duration_days == 17  # Jan 15 to Feb 1
        assert dd.recovery_duration_days == 29  # Feb 1 to Mar 1 (2024 is leap year)

    def test_calculate_drawdown_periods_ongoing_drawdown(self, calculator):
        """Test drawdown period without recovery (ongoing)."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                portfolio_value=Decimal("110000"),  # Peak
                equity_value=Decimal("110000"),
                cash=Decimal("110000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 2, 1, tzinfo=UTC),
                portfolio_value=Decimal("95000"),  # Trough (not recovered)
                equity_value=Decimal("95000"),
                cash=Decimal("95000"),
                positions_value=Decimal("0"),
            ),
        ]

        drawdown_periods = calculator.calculate_drawdown_periods(equity_curve, top_n=5)

        assert len(drawdown_periods) == 1
        dd = drawdown_periods[0]

        assert dd.recovery_date is None
        assert dd.recovery_value is None
        assert dd.recovery_duration_days is None

    def test_calculate_drawdown_periods_top_n_limit(self, calculator):
        """Test top N drawdown periods sorting."""
        # Create multiple drawdown periods
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            # First drawdown: -5%
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 10, tzinfo=UTC),
                portfolio_value=Decimal("105000"),
                equity_value=Decimal("105000"),
                cash=Decimal("105000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 20, tzinfo=UTC),
                portfolio_value=Decimal("99750"),
                equity_value=Decimal("99750"),
                cash=Decimal("99750"),
                positions_value=Decimal("0"),
            ),
            # Second drawdown: -10% (larger)
            EquityCurvePoint(
                timestamp=datetime(2024, 2, 1, tzinfo=UTC),
                portfolio_value=Decimal("110000"),
                equity_value=Decimal("110000"),
                cash=Decimal("110000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 2, 15, tzinfo=UTC),
                portfolio_value=Decimal("99000"),
                equity_value=Decimal("99000"),
                cash=Decimal("99000"),
                positions_value=Decimal("0"),
            ),
            # Recovery
            EquityCurvePoint(
                timestamp=datetime(2024, 3, 1, tzinfo=UTC),
                portfolio_value=Decimal("115000"),
                equity_value=Decimal("115000"),
                cash=Decimal("115000"),
                positions_value=Decimal("0"),
            ),
        ]

        drawdown_periods = calculator.calculate_drawdown_periods(equity_curve, top_n=1)

        # Should return only the largest drawdown (second one at -10%)
        assert len(drawdown_periods) == 1
        assert drawdown_periods[0].peak_value == Decimal("110000")
        assert drawdown_periods[0].trough_value == Decimal("99000")

    def test_calculate_drawdown_periods_no_drawdown(self, calculator):
        """Test with only upward equity curve (no drawdowns)."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                portfolio_value=Decimal("100000") + Decimal(str(i * 1000)),
                equity_value=Decimal("100000") + Decimal(str(i * 1000)),
                cash=Decimal("100000"),
                positions_value=Decimal(str(i * 1000)),
            )
            for i in range(10)
        ]

        drawdown_periods = calculator.calculate_drawdown_periods(equity_curve, top_n=5)

        assert len(drawdown_periods) == 0


class TestRiskMetricsCalculation:
    """Test risk metrics calculation (Story 12.6A AC4)."""

    def test_calculate_risk_metrics_with_positions(self, calculator):
        """Test risk metrics with concurrent positions."""
        # Create equity curve spanning 10 days
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("50000"),
                positions_value=Decimal("50000"),
            )
            for i in range(10)
        ]

        # Create 3 trades with overlapping periods
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 8, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            ),
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="MSFT",
                side="LONG",
                quantity=50,
                entry_price=Decimal("300.00"),
                exit_price=Decimal("310.00"),
                entry_timestamp=datetime(2024, 1, 3, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 7, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            ),
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="GOOGL",
                side="LONG",
                quantity=25,
                entry_price=Decimal("120.00"),
                exit_price=Decimal("125.00"),
                entry_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 10, tzinfo=UTC),
                realized_pnl=Decimal("125.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
            ),
        ]

        risk_metrics = calculator.calculate_risk_metrics(
            equity_curve=equity_curve, trades=trades, initial_capital=Decimal("100000")
        )

        # Should have up to 3 concurrent positions
        assert risk_metrics.max_concurrent_positions == 3
        assert risk_metrics.avg_concurrent_positions > Decimal("0")

        # Portfolio heat (assuming 2% risk per position)
        assert risk_metrics.max_portfolio_heat == Decimal("6")  # 3 positions × 2%
        assert risk_metrics.avg_portfolio_heat > Decimal("0")

        # Capital deployed
        assert risk_metrics.max_capital_deployed_pct > Decimal("0")
        assert risk_metrics.avg_capital_deployed_pct > Decimal("0")

        # Exposure time (all 10 days had positions)
        assert risk_metrics.total_exposure_days == 10
        assert risk_metrics.exposure_time_pct == Decimal("100")

    def test_calculate_risk_metrics_no_trades(self, calculator):
        """Test risk metrics with no trades."""
        equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                portfolio_value=Decimal("100000"),
                equity_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            )
            for i in range(10)
        ]

        risk_metrics = calculator.calculate_risk_metrics(
            equity_curve=equity_curve, trades=[], initial_capital=Decimal("100000")
        )

        # All metrics should be zero
        assert risk_metrics.max_concurrent_positions == 0
        assert risk_metrics.avg_concurrent_positions == Decimal("0")
        assert risk_metrics.max_portfolio_heat == Decimal("0")
        assert risk_metrics.avg_portfolio_heat == Decimal("0")
        assert risk_metrics.total_exposure_days == 0
        assert risk_metrics.exposure_time_pct == Decimal("0")


class TestCampaignPerformanceCalculation:
    """Test campaign performance calculation (Story 12.6A AC5)."""

    def test_calculate_campaign_performance_single_trade(self, calculator):
        """Test campaign performance with single SPRING trade."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                pattern_type="SPRING",
            ),
        ]

        campaign_performance = calculator.calculate_campaign_performance(trades)

        # Should return one campaign
        assert len(campaign_performance) == 1
        assert isinstance(campaign_performance, list)

        campaign = campaign_performance[0]
        assert campaign.symbol == "AAPL"
        assert campaign.campaign_type == "ACCUMULATION"
        assert campaign.patterns_traded == 1
        assert campaign.total_campaign_pnl == Decimal("500.00")
        # Status determined by WyckoffCampaignDetector logic
        assert campaign.status in ["COMPLETED", "FAILED", "IN_PROGRESS"]
        assert "PHASE_C" in campaign.phases_completed

    def test_calculate_campaign_performance_multiple_trades_same_campaign(self, calculator):
        """Test campaign grouping with multiple trades in same campaign."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                pattern_type="SPRING",
            ),
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("155.00"),
                exit_price=Decimal("160.00"),
                entry_timestamp=datetime(2024, 1, 10, tzinfo=UTC),  # Within 30-day window
                exit_timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                pattern_type="SOS",  # Different phase - MARKUP
            ),
        ]

        campaign_performance = calculator.calculate_campaign_performance(trades)

        # Should group into one campaign (same symbol, within 30 days)
        assert len(campaign_performance) == 1
        campaign = campaign_performance[0]
        assert campaign.patterns_traded == 2
        assert campaign.total_campaign_pnl == Decimal("1000.00")
        assert campaign.campaign_type == "ACCUMULATION"  # First pattern
        assert "PHASE_C" in campaign.phases_completed or "PHASE_D" in campaign.phases_completed

    def test_calculate_campaign_performance_separate_campaigns(self, calculator):
        """Test campaign separation by symbol and time gap."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                pattern_type="SPRING",
            ),
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("160.00"),
                exit_price=Decimal("158.00"),
                entry_timestamp=datetime(2024, 3, 1, tzinfo=UTC),  # >30 days later
                exit_timestamp=datetime(2024, 3, 5, tzinfo=UTC),
                realized_pnl=Decimal("-200.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                pattern_type="UTAD",  # DISTRIBUTION pattern
            ),
        ]

        campaign_performance = calculator.calculate_campaign_performance(trades)

        # Should create two separate campaigns (time gap >30 days)
        assert len(campaign_performance) == 2
        assert campaign_performance[0].patterns_traded == 1
        assert campaign_performance[1].patterns_traded == 1
        # Status can be COMPLETED, FAILED, or IN_PROGRESS - just verify we got 2 campaigns
        assert campaign_performance[0].status in ["COMPLETED", "FAILED", "IN_PROGRESS"]
        assert campaign_performance[1].status in ["COMPLETED", "FAILED", "IN_PROGRESS"]

    def test_calculate_campaign_performance_no_pattern_trades(self, calculator):
        """Test campaign performance with no pattern trades."""
        trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("150.00"),
                exit_price=Decimal("155.00"),
                entry_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 5, tzinfo=UTC),
                realized_pnl=Decimal("500.00"),
                commission=Decimal("1.00"),
                slippage=Decimal("0.50"),
                pattern_type=None,  # No pattern
            ),
        ]

        campaign_performance = calculator.calculate_campaign_performance(trades)

        # Should return empty list (no pattern trades)
        assert campaign_performance == []

    def test_calculate_campaign_performance_empty_trades(self, calculator):
        """Test campaign performance with empty trades list."""
        campaign_performance = calculator.calculate_campaign_performance([])

        assert campaign_performance == []
