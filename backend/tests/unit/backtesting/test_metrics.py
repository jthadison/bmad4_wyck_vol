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
from src.models.backtest import BacktestTrade, EquityCurvePoint


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
            daily_return=Decimal("0.01") if i > 0 else Decimal("0"),
            cumulative_return=Decimal(str(i * 0.01)),
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
                    daily_return=daily_return,
                    cumulative_return=(portfolio_value - base_value) / base_value,
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
                daily_return=Decimal("0"),
                cumulative_return=Decimal("0"),
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
                daily_return=Decimal("0"),
                cumulative_return=Decimal("0"),
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
                daily_return=Decimal("0"),
                cumulative_return=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                portfolio_value=Decimal("115000"),  # Peak
                equity_value=Decimal("115000"),
                cash=Decimal("100000"),
                positions_value=Decimal("15000"),
                daily_return=Decimal("0.15"),
                cumulative_return=Decimal("0.15"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 3, tzinfo=UTC),
                portfolio_value=Decimal("110000"),  # Decline
                equity_value=Decimal("110000"),
                cash=Decimal("100000"),
                positions_value=Decimal("10000"),
                daily_return=Decimal("-0.043"),
                cumulative_return=Decimal("0.10"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 4, tzinfo=UTC),
                portfolio_value=Decimal("103500"),  # Trough (10% from peak)
                equity_value=Decimal("103500"),
                cash=Decimal("100000"),
                positions_value=Decimal("3500"),
                daily_return=Decimal("-0.059"),
                cumulative_return=Decimal("0.035"),
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
                daily_return=Decimal("0.01") if i > 0 else Decimal("0"),
                cumulative_return=Decimal(str(i * 0.01)),
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
        # No losses = undefined, return 0
        assert profit_factor == Decimal("0")


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
        assert metrics.average_r_multiple == Decimal("4.0") / Decimal("3")
        assert metrics.total_return_pct == Decimal("9")  # $100k -> $109k
        assert metrics.max_drawdown >= Decimal("0")
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
        # Win rate, avg_r, profit_factor should be None for no trades
        assert metrics.win_rate is None or metrics.win_rate == Decimal("0")
        assert metrics.average_r_multiple is None or metrics.average_r_multiple == Decimal("0")
        assert metrics.profit_factor is None or metrics.profit_factor == Decimal("0")

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
                daily_return=Decimal("0"),
                cumulative_return=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                portfolio_value=Decimal("100500"),
                equity_value=Decimal("100500"),
                cash=Decimal("100500"),
                positions_value=Decimal("0"),
                daily_return=Decimal("0.005"),
                cumulative_return=Decimal("0.005"),
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
