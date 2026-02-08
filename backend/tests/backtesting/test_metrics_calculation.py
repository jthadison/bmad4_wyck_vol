"""
Unit tests for _calculate_metrics() in UnifiedBacktestEngine.

Tests verify that total_return_pct, cagr, sharpe_ratio, total_pnl,
and final_equity are computed correctly from the equity curve and trades.

Author: fix/compute-missing-metrics (PR #419 follow-up)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.backtesting.engine.backtest_engine import UnifiedBacktestEngine
from src.backtesting.engine.interfaces import EngineConfig
from src.backtesting.position_manager import PositionManager
from src.models.backtest import BacktestOrder, BacktestTrade, EquityCurvePoint
from src.models.ohlcv import OHLCVBar

_BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _NullDetector:
    """Signal detector that never fires."""

    def detect(self, bars: list[OHLCVBar], index: int):
        return None


class _NullCostModel:
    """Cost model with zero costs."""

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        return Decimal("0")

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        return Decimal("0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(initial_capital: Decimal = Decimal("100000")) -> UnifiedBacktestEngine:
    """Create a UnifiedBacktestEngine with null detector and cost model."""
    config = EngineConfig(initial_capital=initial_capital)
    pm = PositionManager(initial_capital=initial_capital)
    return UnifiedBacktestEngine(
        signal_detector=_NullDetector(),
        cost_model=_NullCostModel(),
        position_manager=pm,
        config=config,
    )


def _make_equity_point(portfolio_value: Decimal, day_offset: int = 0) -> EquityCurvePoint:
    """Create a single EquityCurvePoint."""
    return EquityCurvePoint(
        timestamp=_BASE_DATE + timedelta(days=day_offset),
        equity_value=portfolio_value,
        portfolio_value=portfolio_value,
        cash=portfolio_value,
        positions_value=Decimal("0"),
    )


def _make_trade(
    realized_pnl: Decimal, day_offset_entry: int = 0, day_offset_exit: int = 1
) -> BacktestTrade:
    """Create a minimal BacktestTrade with the given P&L."""
    return BacktestTrade(
        trade_id=uuid4(),
        position_id=uuid4(),
        symbol="TEST",
        side="LONG",
        quantity=100,
        entry_price=Decimal("100"),
        exit_price=Decimal("100") + realized_pnl / Decimal("100"),
        entry_timestamp=_BASE_DATE + timedelta(days=day_offset_entry),
        exit_timestamp=_BASE_DATE + timedelta(days=day_offset_exit),
        realized_pnl=realized_pnl,
        commission=Decimal("0"),
        slippage=Decimal("0"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTotalReturnPct:
    """Tests for total_return_pct computation."""

    def test_total_return_pct_computed(self):
        """total_return_pct = (final - initial) / initial * 100."""
        engine = _make_engine(Decimal("100000"))
        # Equity curve: 100k -> 115k (15% return)
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
            _make_equity_point(Decimal("105000"), day_offset=1),
            _make_equity_point(Decimal("115000"), day_offset=2),
        ]
        trades = [_make_trade(Decimal("15000"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.total_return_pct == Decimal("15")

    def test_total_return_pct_negative(self):
        """Negative returns should produce negative total_return_pct."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
            _make_equity_point(Decimal("90000"), day_offset=1),
        ]
        trades = [_make_trade(Decimal("-10000"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.total_return_pct == Decimal("-10")


class TestCAGR:
    """Tests for CAGR computation."""

    def test_cagr_computed(self):
        """CAGR over a known period should be calculable and non-zero."""
        engine = _make_engine(Decimal("100000"))
        # 100k -> 121k over exactly 2 years (730 days)
        # CAGR = (121000/100000)^(365/730) - 1 = 1.21^0.5 - 1 = 0.1 (10%)
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
            _make_equity_point(Decimal("121000"), day_offset=730),
        ]
        trades = [_make_trade(Decimal("21000"), day_offset_entry=0, day_offset_exit=730)]

        metrics = engine._calculate_metrics(trades)

        # CAGR should be approximately 0.1 (10%)
        cagr_float = float(metrics.cagr)
        assert abs(cagr_float - 0.1) < 0.001, f"Expected ~0.1, got {cagr_float}"

    def test_cagr_zero_when_single_point(self):
        """CAGR should be 0 with only one equity curve point (no time range)."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("110000"), day_offset=0),
        ]
        trades = [_make_trade(Decimal("10000"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.cagr == Decimal("0")


class TestSharpeRatio:
    """Tests for Sharpe ratio computation."""

    def test_sharpe_ratio_computed(self):
        """Sharpe ratio should be non-zero for a trending equity curve."""
        engine = _make_engine(Decimal("100000"))
        # Steadily increasing equity -> positive Sharpe
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=i) for i in range(30)
        ]
        # Add small increments to create positive returns with some variance
        for i, pt in enumerate(engine._equity_curve):
            # Equity goes 100k, 100.5k, 101k, ... with slight noise
            value = Decimal("100000") + Decimal(str(i * 500 + (i % 3) * 100))
            pt.portfolio_value = value
            pt.equity_value = value

        trades = [_make_trade(Decimal("15000"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.sharpe_ratio != Decimal("0")
        assert (
            float(metrics.sharpe_ratio) > 0
        ), "Positive trending equity should have positive Sharpe"

    def test_sharpe_ratio_zero_when_insufficient_data(self):
        """Sharpe ratio should be 0 with fewer than 2 equity points."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("110000"), day_offset=0),
        ]
        trades = [_make_trade(Decimal("10000"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.sharpe_ratio == Decimal("0")

    def test_sharpe_ratio_zero_when_flat(self):
        """Sharpe ratio should be 0 when equity is flat (std=0)."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=i) for i in range(10)
        ]
        trades = [_make_trade(Decimal("0"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.sharpe_ratio == Decimal("0")


class TestMetricsWithNoTrades:
    """Tests for metrics when no trades are present."""

    def test_metrics_with_no_trades(self):
        """All financial metrics should be 0 when there are no trades."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
        ]

        metrics = engine._calculate_metrics([])

        assert metrics.total_return_pct == Decimal("0")
        assert metrics.cagr == Decimal("0")
        assert metrics.sharpe_ratio == Decimal("0")
        assert metrics.total_pnl == Decimal("0")
        assert metrics.final_equity == Decimal("100000")
        assert metrics.total_trades == 0
        assert metrics.win_rate == Decimal("0")


class TestMetricsWithSingleTrade:
    """Tests for metrics with exactly one trade."""

    def test_metrics_with_single_trade(self):
        """Metrics should work with just one trade."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
            _make_equity_point(Decimal("102000"), day_offset=30),
        ]
        trades = [_make_trade(Decimal("2000"), day_offset_entry=0, day_offset_exit=30)]

        metrics = engine._calculate_metrics(trades)

        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.total_pnl == Decimal("2000")
        assert metrics.final_equity == Decimal("102000")
        assert metrics.total_return_pct == Decimal("2")
        # CAGR should be positive for a gain over 30 days
        assert float(metrics.cagr) > 0
        # Sharpe should be 0 with only 1 daily return (need >= 2 for std)
        # Actually we have 2 points so 1 return -> still not enough for std
        # The code requires len(daily_returns) >= 2, so Sharpe is 0 here
        assert metrics.sharpe_ratio == Decimal("0")


class TestTotalPnlAndFinalEquity:
    """Tests for total_pnl and final_equity fields."""

    def test_total_pnl_sum(self):
        """total_pnl should be the sum of all trade realized_pnl."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
            _make_equity_point(Decimal("103000"), day_offset=30),
        ]
        trades = [
            _make_trade(Decimal("5000"), day_offset_entry=0, day_offset_exit=10),
            _make_trade(Decimal("-2000"), day_offset_entry=10, day_offset_exit=20),
        ]

        metrics = engine._calculate_metrics(trades)

        assert metrics.total_pnl == Decimal("3000")

    def test_final_equity_from_curve(self):
        """final_equity should come from the last equity curve point."""
        engine = _make_engine(Decimal("100000"))
        engine._equity_curve = [
            _make_equity_point(Decimal("100000"), day_offset=0),
            _make_equity_point(Decimal("108500"), day_offset=90),
        ]
        trades = [_make_trade(Decimal("8500"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.final_equity == Decimal("108500")

    def test_final_equity_defaults_to_initial_when_no_curve(self):
        """final_equity should default to initial_capital when equity curve is empty."""
        engine = _make_engine(Decimal("50000"))
        engine._equity_curve = []
        trades = [_make_trade(Decimal("1000"))]

        metrics = engine._calculate_metrics(trades)

        assert metrics.final_equity == Decimal("50000")
