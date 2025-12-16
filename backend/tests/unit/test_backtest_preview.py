"""
Unit tests for Backtest Preview functionality (Story 11.2)

Tests:
------
- BacktestEngine: Core backtest execution logic
- Metrics calculation: Win rate, R-multiples, profit factor, drawdown
- Recommendation algorithm: Compare configs and generate suggestions
- Progress tracking: Callback invocation

Author: Story 11.2 Task 1
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.engine import BacktestEngine
from src.backtesting.metrics import (
    calculate_equity_curve,
    calculate_max_drawdown,
    calculate_metrics,
)
from src.models.backtest import BacktestMetrics


class TestMetricsCalculation:
    """Test suite for backtest metrics calculation."""

    def test_calculate_metrics_empty_trades(self):
        """Test metrics calculation with no trades."""
        metrics = calculate_metrics([], Decimal("100000.00"))

        assert metrics.total_signals == 0
        assert metrics.win_rate == Decimal("0.0")
        assert metrics.average_r_multiple == Decimal("0.0")
        assert metrics.profit_factor == Decimal("0.0")
        assert metrics.max_drawdown == Decimal("0.0")

    def test_calculate_metrics_winning_trades(self):
        """Test metrics with all winning trades."""
        trades = [
            {
                "entry_timestamp": datetime.now(UTC),
                "exit_timestamp": datetime.now(UTC) + timedelta(hours=1),
                "entry_price": Decimal("100.00"),
                "exit_price": Decimal("105.00"),
                "profit": Decimal("500.00"),
                "r_multiple": Decimal("2.5"),
            },
            {
                "entry_timestamp": datetime.now(UTC) + timedelta(hours=2),
                "exit_timestamp": datetime.now(UTC) + timedelta(hours=3),
                "entry_price": Decimal("105.00"),
                "exit_price": Decimal("110.00"),
                "profit": Decimal("500.00"),
                "r_multiple": Decimal("2.5"),
            },
        ]

        metrics = calculate_metrics(trades, Decimal("100000.00"))

        assert metrics.total_signals == 2
        assert metrics.win_rate == Decimal("1.0")  # 100% win rate
        assert metrics.average_r_multiple == Decimal("2.5")
        assert metrics.profit_factor > Decimal("100.0")  # Very high (no losses)

    def test_calculate_metrics_mixed_trades(self):
        """Test metrics with mixed winning and losing trades."""
        trades = [
            {
                "entry_timestamp": datetime.now(UTC),
                "exit_timestamp": datetime.now(UTC) + timedelta(hours=1),
                "profit": Decimal("1000.00"),
                "r_multiple": Decimal("2.0"),
            },
            {
                "entry_timestamp": datetime.now(UTC) + timedelta(hours=2),
                "exit_timestamp": datetime.now(UTC) + timedelta(hours=3),
                "profit": Decimal("-500.00"),
                "r_multiple": Decimal("-1.0"),
            },
            {
                "entry_timestamp": datetime.now(UTC) + timedelta(hours=4),
                "exit_timestamp": datetime.now(UTC) + timedelta(hours=5),
                "profit": Decimal("750.00"),
                "r_multiple": Decimal("1.5"),
            },
        ]

        metrics = calculate_metrics(trades, Decimal("100000.00"))

        assert metrics.total_signals == 3
        # Win rate: 2 wins out of 3 = 0.6667
        assert abs(metrics.win_rate - Decimal("0.6667")) < Decimal("0.01")
        # Average R: (2.0 - 1.0 + 1.5) / 3 = 0.8333
        assert abs(metrics.average_r_multiple - Decimal("0.8333")) < Decimal("0.01")
        # Profit factor: 1750 / 500 = 3.5
        assert metrics.profit_factor == Decimal("3.5")

    def test_calculate_max_drawdown(self):
        """Test maximum drawdown calculation."""
        # Equity goes up, then drops, then recovers
        equity_values = [
            Decimal("100000.00"),
            Decimal("105000.00"),
            Decimal("110000.00"),  # Peak
            Decimal("100000.00"),  # -9.09% drawdown
            Decimal("95000.00"),  # -13.64% drawdown from peak
            Decimal("105000.00"),  # Recovered
        ]

        max_dd = calculate_max_drawdown(equity_values)

        # Max drawdown: (110000 - 95000) / 110000 = 0.1364 (~13.64%)
        expected_dd = (Decimal("110000.00") - Decimal("95000.00")) / Decimal("110000.00")
        assert abs(max_dd - expected_dd) < Decimal("0.001")

    def test_calculate_max_drawdown_always_up(self):
        """Test max drawdown when equity always increases."""
        equity_values = [
            Decimal("100000.00"),
            Decimal("105000.00"),
            Decimal("110000.00"),
            Decimal("115000.00"),
        ]

        max_dd = calculate_max_drawdown(equity_values)
        assert max_dd == Decimal("0.0")

    def test_calculate_equity_curve(self):
        """Test equity curve generation."""
        base_time = datetime.now(UTC)
        trades = [
            {
                "entry_timestamp": base_time,
                "exit_timestamp": base_time + timedelta(hours=1),
                "profit": Decimal("1000.00"),
            },
            {
                "entry_timestamp": base_time + timedelta(hours=2),
                "exit_timestamp": base_time + timedelta(hours=3),
                "profit": Decimal("-500.00"),
            },
            {
                "entry_timestamp": base_time + timedelta(hours=4),
                "exit_timestamp": base_time + timedelta(hours=5),
                "profit": Decimal("750.00"),
            },
        ]

        initial_capital = Decimal("100000.00")
        equity_curve = calculate_equity_curve(trades, initial_capital)

        # Should have 4 points: initial + 3 trades
        assert len(equity_curve) == 4
        assert equity_curve[0].equity_value == initial_capital
        assert equity_curve[1].equity_value == Decimal("101000.00")
        assert equity_curve[2].equity_value == Decimal("100500.00")
        assert equity_curve[3].equity_value == Decimal("101250.00")


class TestBacktestEngine:
    """Test suite for BacktestEngine."""

    @pytest.mark.asyncio
    async def test_progress_callback_invoked(self):
        """Test that progress callback is invoked during backtest."""
        progress_updates = []

        async def progress_callback(bars_analyzed: int, total_bars: int, percent_complete: int):
            progress_updates.append(
                {
                    "bars_analyzed": bars_analyzed,
                    "total_bars": total_bars,
                    "percent_complete": percent_complete,
                }
            )

        engine = BacktestEngine(progress_callback=progress_callback)

        # Create sample historical data (50 bars to ensure multiple progress updates)
        historical_bars = []
        base_time = datetime.now(UTC) - timedelta(days=50)
        for i in range(50):
            historical_bars.append(
                {
                    "timestamp": base_time + timedelta(days=i),
                    "open": 150.0 + i * 0.5,
                    "high": 155.0 + i * 0.5,
                    "low": 145.0 + i * 0.5,
                    "close": 152.0 + i * 0.5,
                    "volume": 1000000,
                }
            )

        current_config = {"volume_thresholds": {"ultra_high": 2.5}}
        proposed_config = {"volume_thresholds": {"ultra_high": 2.0}}

        comparison = await engine._run_comparison(
            backtest_run_id=uuid4(),
            current_config=current_config,
            proposed_config=proposed_config,
            historical_bars=historical_bars,
        )

        # Verify progress callbacks were made
        assert len(progress_updates) > 0
        # Last update should be at or near 100%
        assert progress_updates[-1]["percent_complete"] >= 95

    @pytest.mark.asyncio
    async def test_recommendation_improvement(self):
        """Test recommendation algorithm detects improvement."""
        engine = BacktestEngine()

        current_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.60"),
            average_r_multiple=Decimal("1.5"),
            profit_factor=Decimal("2.0"),
            max_drawdown=Decimal("0.15"),
        )

        proposed_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.70"),  # +10% win rate
            average_r_multiple=Decimal("1.8"),  # +0.3 R-multiple
            profit_factor=Decimal("2.5"),
            max_drawdown=Decimal("0.12"),  # -3% drawdown
        )

        recommendation, text = engine._generate_recommendation(current_metrics, proposed_metrics)

        assert recommendation == "improvement"
        assert "improved" in text.lower() or "win rate" in text.lower()

    @pytest.mark.asyncio
    async def test_recommendation_degraded(self):
        """Test recommendation algorithm detects degradation."""
        engine = BacktestEngine()

        current_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.70"),
            average_r_multiple=Decimal("2.0"),
            profit_factor=Decimal("3.0"),
            max_drawdown=Decimal("0.10"),
        )

        proposed_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.55"),  # -15% win rate (significant degradation)
            average_r_multiple=Decimal("1.5"),
            profit_factor=Decimal("2.0"),
            max_drawdown=Decimal("0.20"),  # +10% drawdown (bad)
        )

        recommendation, text = engine._generate_recommendation(current_metrics, proposed_metrics)

        assert recommendation == "degraded"
        assert "degraded" in text.lower() or "not recommended" in text.lower()

    @pytest.mark.asyncio
    async def test_recommendation_neutral(self):
        """Test recommendation algorithm detects neutral changes."""
        engine = BacktestEngine()

        current_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.65"),
            average_r_multiple=Decimal("1.5"),
            profit_factor=Decimal("2.5"),
            max_drawdown=Decimal("0.12"),
        )

        proposed_metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.67"),  # +2% (marginal)
            average_r_multiple=Decimal("1.55"),  # +0.05 (marginal)
            profit_factor=Decimal("2.6"),
            max_drawdown=Decimal("0.11"),  # -1% (marginal)
        )

        recommendation, text = engine._generate_recommendation(current_metrics, proposed_metrics)

        assert recommendation == "neutral"
        assert "marginal" in text.lower() or "neutral" in text.lower()

    @pytest.mark.asyncio
    async def test_engine_cancel(self):
        """Test backtest cancellation."""
        engine = BacktestEngine()

        # Create large dataset
        historical_bars = []
        base_time = datetime.now(UTC) - timedelta(days=100)
        for i in range(100):
            historical_bars.append(
                {
                    "timestamp": base_time + timedelta(days=i),
                    "open": 150.0,
                    "high": 155.0,
                    "low": 145.0,
                    "close": 152.0,
                    "volume": 1000000,
                }
            )

        # Cancel immediately
        engine.cancel()

        # Run should complete but with cancelled flag
        current_config = {"volume_thresholds": {"ultra_high": 2.5}}
        trades = await engine._simulate_trading(
            backtest_run_id=uuid4(),
            config=current_config,
            historical_bars=historical_bars,
            config_label="current",
        )

        # Should return empty or very few trades due to cancellation
        assert len(trades) < 10  # Not all bars were processed


class TestBacktestModels:
    """Test suite for Pydantic models."""

    def test_backtest_preview_request_validation(self):
        """Test BacktestPreviewRequest validation."""
        from src.models.backtest import BacktestPreviewRequest

        # Valid request
        request = BacktestPreviewRequest(proposed_config={"test": "config"}, days=90)
        assert request.days == 90
        assert request.timeframe == "1d"

        # Invalid days (too low)
        with pytest.raises(Exception):  # Pydantic ValidationError
            BacktestPreviewRequest(proposed_config={}, days=5)

        # Invalid days (too high)
        with pytest.raises(Exception):  # Pydantic ValidationError
            BacktestPreviewRequest(proposed_config={}, days=400)

    def test_backtest_metrics_validation(self):
        """Test BacktestMetrics validation."""
        # Valid metrics
        metrics = BacktestMetrics(
            total_signals=10,
            win_rate=Decimal("0.75"),
            average_r_multiple=Decimal("1.5"),
            profit_factor=Decimal("2.5"),
            max_drawdown=Decimal("0.12"),
        )
        assert metrics.total_signals == 10
        assert metrics.win_rate == Decimal("0.75")

        # Invalid win rate (>1.0)
        with pytest.raises(Exception):  # Pydantic ValidationError
            BacktestMetrics(
                total_signals=10,
                win_rate=Decimal("1.5"),  # Invalid
                average_r_multiple=Decimal("1.0"),
                profit_factor=Decimal("2.0"),
                max_drawdown=Decimal("0.1"),
            )
