"""
Unit tests for backtesting models (Story 12.1 Task 1).

Tests all Pydantic models for validation, defaults, and serialization.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestOrder,
    BacktestPosition,
    BacktestResult,
    BacktestTrade,
    EquityCurvePoint,
)


class TestBacktestConfig:
    """Test BacktestConfig model."""

    def test_backtest_config_defaults(self):
        """Test default values for BacktestConfig."""
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert config.symbol == "AAPL"
        assert config.initial_capital == Decimal("100000")
        assert config.max_position_size == Decimal("0.02")
        assert config.commission_per_share == Decimal("0.005")
        assert config.slippage_model == "PERCENTAGE"
        assert config.slippage_percentage == Decimal("0.0002")
        assert config.risk_limits == {"max_portfolio_heat": 0.10, "max_campaign_risk": 0.05}

    def test_backtest_config_custom_values(self):
        """Test custom values for BacktestConfig."""
        config = BacktestConfig(
            symbol="TSLA",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            initial_capital=Decimal("50000"),
            max_position_size=Decimal("0.05"),
            commission_per_share=Decimal("0.01"),
            slippage_model="FIXED",
            slippage_percentage=Decimal("0.001"),
            risk_limits={"max_portfolio_heat": 0.15},
        )

        assert config.symbol == "TSLA"
        assert config.initial_capital == Decimal("50000")
        assert config.max_position_size == Decimal("0.05")
        assert config.commission_per_share == Decimal("0.01")
        assert config.slippage_model == "FIXED"
        assert config.slippage_percentage == Decimal("0.001")
        assert config.risk_limits == {"max_portfolio_heat": 0.15}

    def test_backtest_config_validation_negative_capital(self):
        """Test validation rejects negative initial capital."""
        with pytest.raises(ValueError):
            BacktestConfig(
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                initial_capital=Decimal("-1000"),
            )

    def test_backtest_config_validation_position_size_too_large(self):
        """Test validation rejects position size > 1.0."""
        with pytest.raises(ValueError):
            BacktestConfig(
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                max_position_size=Decimal("1.5"),
            )

    def test_backtest_config_serialization(self):
        """Test BacktestConfig can be serialized to dict."""
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        data = config.model_dump()
        assert data["symbol"] == "AAPL"
        assert data["start_date"] == date(2024, 1, 1)
        assert data["initial_capital"] == Decimal("100000")


class TestBacktestOrder:
    """Test BacktestOrder model."""

    def test_backtest_order_creation(self):
        """Test creating a BacktestOrder."""
        order_id = uuid4()
        timestamp = datetime.utcnow()

        order = BacktestOrder(
            order_id=order_id,
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            created_bar_timestamp=timestamp,
            status="PENDING",
        )

        assert order.order_id == order_id
        assert order.symbol == "AAPL"
        assert order.order_type == "MARKET"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.status == "PENDING"
        assert order.commission == Decimal("0")
        assert order.slippage == Decimal("0")
        assert order.fill_price is None
        assert order.filled_bar_timestamp is None

    def test_backtest_order_filled(self):
        """Test filled BacktestOrder with price and costs."""
        order_id = uuid4()
        created_ts = datetime.utcnow()
        filled_ts = datetime.utcnow()

        order = BacktestOrder(
            order_id=order_id,
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            created_bar_timestamp=created_ts,
            filled_bar_timestamp=filled_ts,
            fill_price=Decimal("150.25"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.03"),
            status="FILLED",
        )

        assert order.status == "FILLED"
        assert order.fill_price == Decimal("150.25")
        assert order.commission == Decimal("0.50")
        assert order.slippage == Decimal("0.03")

    def test_backtest_order_limit_order(self):
        """Test LIMIT order with limit price."""
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="LIMIT",
            side="BUY",
            quantity=100,
            limit_price=Decimal("149.50"),
            created_bar_timestamp=datetime.utcnow(),
            status="PENDING",
        )

        assert order.order_type == "LIMIT"
        assert order.limit_price == Decimal("149.50")

    def test_backtest_order_validation_zero_quantity(self):
        """Test validation rejects zero quantity."""
        with pytest.raises(ValueError):
            BacktestOrder(
                order_id=uuid4(),
                symbol="AAPL",
                order_type="MARKET",
                side="BUY",
                quantity=0,
                created_bar_timestamp=datetime.utcnow(),
                status="PENDING",
            )


class TestBacktestPosition:
    """Test BacktestPosition model."""

    def test_backtest_position_creation(self):
        """Test creating a BacktestPosition."""
        position_id = uuid4()
        entry_ts = datetime(2024, 1, 10, 9, 30)

        position = BacktestPosition(
            position_id=position_id,
            symbol="AAPL",
            side="LONG",
            quantity=100,
            average_entry_price=Decimal("150.00"),
            current_price=Decimal("155.00"),
            entry_timestamp=entry_ts,
            last_updated=entry_ts,
        )

        assert position.position_id == position_id
        assert position.symbol == "AAPL"
        assert position.side == "LONG"
        assert position.quantity == 100
        assert position.average_entry_price == Decimal("150.00")
        assert position.entry_price == Decimal("150.00")  # Test alias
        assert position.current_price == Decimal("155.00")
        assert position.unrealized_pnl == Decimal("0")
        assert position.total_commission == Decimal("0")

    def test_backtest_position_with_pnl(self):
        """Test BacktestPosition with P&L values."""
        entry_ts = datetime(2024, 1, 10, 9, 30)

        position = BacktestPosition(
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            average_entry_price=Decimal("150.00"),
            current_price=Decimal("155.00"),
            entry_timestamp=entry_ts,
            last_updated=entry_ts,
            unrealized_pnl=Decimal("500.00"),
            total_commission=Decimal("1.00"),
        )

        assert position.unrealized_pnl == Decimal("500.00")
        assert position.total_commission == Decimal("1.00")


class TestBacktestTrade:
    """Test BacktestTrade model."""

    def test_backtest_trade_creation(self):
        """Test creating a BacktestTrade."""
        trade_id = uuid4()
        position_id = uuid4()
        entry_ts = datetime(2024, 1, 10, 9, 30)
        exit_ts = datetime(2024, 1, 15, 16, 0)

        trade = BacktestTrade(
            trade_id=trade_id,
            position_id=position_id,
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("155.00"),
            entry_timestamp=entry_ts,
            exit_timestamp=exit_ts,
            realized_pnl=Decimal("498.50"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
            r_multiple=Decimal("2.5"),
            pattern_type="SPRING",
        )

        assert trade.trade_id == trade_id
        assert trade.position_id == position_id
        assert trade.symbol == "AAPL"
        assert trade.side == "LONG"
        assert trade.entry_timestamp == entry_ts
        assert trade.exit_timestamp == exit_ts
        assert trade.entry_price == Decimal("150.00")
        assert trade.exit_price == Decimal("155.00")
        assert trade.quantity == 100
        assert trade.realized_pnl == Decimal("498.50")
        assert trade.pnl == Decimal("498.50")  # Test alias
        assert trade.commission == Decimal("1.00")
        assert trade.commission_total == Decimal("1.00")  # Test alias
        assert trade.slippage == Decimal("0.50")
        assert trade.slippage_total == Decimal("0.50")  # Test alias
        assert trade.r_multiple == Decimal("2.5")
        assert trade.pattern_type == "SPRING"

    def test_backtest_trade_losing_trade(self):
        """Test losing trade with negative P&L."""
        trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("148.00"),
            entry_timestamp=datetime(2024, 1, 10, 9, 30),
            exit_timestamp=datetime(2024, 1, 12, 16, 0),
            realized_pnl=Decimal("-201.50"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
            r_multiple=Decimal("-1.0"),
            pattern_type="SOS",
        )

        assert trade.pnl == Decimal("-201.50")
        assert trade.r_multiple == Decimal("-1.0")


class TestEquityCurvePoint:
    """Test EquityCurvePoint model."""

    def test_equity_curve_point_creation(self):
        """Test creating an EquityCurvePoint."""
        timestamp = datetime.utcnow()

        point = EquityCurvePoint(
            timestamp=timestamp,
            equity_value=Decimal("105000"),
            portfolio_value=Decimal("105000"),
            cash=Decimal("95000"),
            positions_value=Decimal("10000"),
            daily_return=Decimal("0.02"),
            cumulative_return=Decimal("0.05"),
        )

        assert point.timestamp == timestamp
        assert point.equity_value == Decimal("105000")
        assert point.portfolio_value == Decimal("105000")
        assert point.cash == Decimal("95000")
        assert point.positions_value == Decimal("10000")
        assert point.daily_return == Decimal("0.02")
        assert point.cumulative_return == Decimal("0.05")

    def test_equity_curve_point_defaults(self):
        """Test EquityCurvePoint with default values."""
        point = EquityCurvePoint(
            timestamp=datetime.utcnow(),
            equity_value=Decimal("100000"),
            portfolio_value=Decimal("100000"),
            cash=Decimal("100000"),
        )

        assert point.positions_value == Decimal("0")
        assert point.daily_return == Decimal("0")
        assert point.cumulative_return == Decimal("0")


class TestBacktestMetrics:
    """Test BacktestMetrics model."""

    def test_backtest_metrics_defaults(self):
        """Test default values for BacktestMetrics."""
        metrics = BacktestMetrics()

        assert metrics.total_signals == 0
        assert metrics.win_rate == Decimal("0.0")
        assert metrics.average_r_multiple == Decimal("0.0")
        assert metrics.profit_factor == Decimal("0.0")
        assert metrics.max_drawdown == Decimal("0.0")
        assert metrics.total_return_pct == Decimal("0.0")
        assert metrics.cagr == Decimal("0.0")
        assert metrics.sharpe_ratio == Decimal("0.0")
        assert metrics.max_drawdown_duration_days == 0
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0

    def test_backtest_metrics_custom_values(self):
        """Test custom values for BacktestMetrics."""
        metrics = BacktestMetrics(
            total_signals=25,
            win_rate=Decimal("0.65"),
            average_r_multiple=Decimal("2.3"),
            profit_factor=Decimal("2.8"),
            max_drawdown=Decimal("0.12"),
            total_return_pct=Decimal("45.5"),
            cagr=Decimal("15.2"),
            sharpe_ratio=Decimal("1.8"),
            max_drawdown_duration_days=45,
            total_trades=20,
            winning_trades=13,
            losing_trades=7,
        )

        assert metrics.total_signals == 25
        assert metrics.win_rate == Decimal("0.65")
        assert metrics.average_r_multiple == Decimal("2.3")
        assert metrics.profit_factor == Decimal("2.8")
        assert metrics.max_drawdown == Decimal("0.12")
        assert metrics.total_return_pct == Decimal("45.5")
        assert metrics.cagr == Decimal("15.2")
        assert metrics.sharpe_ratio == Decimal("1.8")
        assert metrics.max_drawdown_duration_days == 45
        assert metrics.total_trades == 20
        assert metrics.winning_trades == 13
        assert metrics.losing_trades == 7

    def test_backtest_metrics_avg_r_multiple_alias(self):
        """Test avg_r_multiple property alias."""
        metrics = BacktestMetrics(average_r_multiple=Decimal("2.5"))
        assert metrics.avg_r_multiple == Decimal("2.5")

    def test_backtest_metrics_validation_win_rate_bounds(self):
        """Test win_rate must be between 0 and 1."""
        with pytest.raises(ValueError):
            BacktestMetrics(win_rate=Decimal("1.5"))

        with pytest.raises(ValueError):
            BacktestMetrics(win_rate=Decimal("-0.1"))


class TestBacktestResult:
    """Test BacktestResult model."""

    def test_backtest_result_creation(self):
        """Test creating a BacktestResult."""
        run_id = uuid4()
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        metrics = BacktestMetrics(
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            win_rate=Decimal("0.70"),
        )

        result = BacktestResult(
            backtest_run_id=run_id,
            symbol="AAPL",
            timeframe="1d",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            config=config,
            metrics=metrics,
        )

        assert result.backtest_run_id == run_id
        assert result.symbol == "AAPL"
        assert result.timeframe == "1d"
        assert result.start_date == date(2024, 1, 1)
        assert result.end_date == date(2024, 12, 31)
        assert result.config == config
        assert result.metrics == metrics
        assert result.equity_curve == []
        assert result.trades == []
        assert result.look_ahead_bias_check is False
        assert result.execution_time_seconds == 0.0

    def test_backtest_result_with_trades_and_equity_curve(self):
        """Test BacktestResult with trades and equity curve."""
        run_id = uuid4()
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("155.00"),
            entry_timestamp=datetime(2024, 1, 10, 9, 30),
            exit_timestamp=datetime(2024, 1, 15, 16, 0),
            realized_pnl=Decimal("498.50"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.50"),
            r_multiple=Decimal("2.5"),
            pattern_type="SPRING",
        )

        point = EquityCurvePoint(
            timestamp=datetime(2024, 1, 1, 9, 30),
            equity_value=Decimal("100000"),
            portfolio_value=Decimal("100000"),
            cash=Decimal("100000"),
        )

        metrics = BacktestMetrics(total_trades=1, winning_trades=1)

        result = BacktestResult(
            backtest_run_id=run_id,
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            config=config,
            equity_curve=[point],
            trades=[trade],
            metrics=metrics,
            look_ahead_bias_check=True,
            execution_time_seconds=3.5,
        )

        assert len(result.equity_curve) == 1
        assert len(result.trades) == 1
        assert result.look_ahead_bias_check is True
        assert result.execution_time_seconds == 3.5

    def test_backtest_result_serialization(self):
        """Test BacktestResult can be serialized."""
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        metrics = BacktestMetrics()

        result = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            config=config,
            metrics=metrics,
        )

        data = result.model_dump()
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1d"
        assert "config" in data
        assert "metrics" in data
        assert "equity_curve" in data
        assert "trades" in data
