"""
Event-Driven Backtest Engine Core (Story 12.1 Task 5).

Implements the main backtesting engine that orchestrates bar-by-bar execution,
order fills, position management, and result generation.

Author: Story 12.1 Task 5
"""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from src.backtesting.bias_detector import LookAheadBiasDetector
from src.backtesting.order_simulator import OrderSimulator
from src.backtesting.position_manager import PositionManager
from src.backtesting.slippage_calculator import CommissionCalculator, SlippageCalculator
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    EquityCurvePoint,
)
from src.models.ohlcv import OHLCVBar


class BacktestEngine:
    """Event-driven backtesting engine.

    Processes bars sequentially to prevent look-ahead bias, simulates
    realistic order fills, tracks positions, and generates comprehensive results.

    AC1: Event-driven architecture - process one bar at a time
    AC2: Orders filled at next bar open with realistic slippage
    AC3: No look-ahead bias - only use historical data
    AC4: Generate equity curve, trades, and metrics

    Example:
        config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        engine = BacktestEngine(config)

        # Define strategy logic
        def strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            # Return "BUY" or "SELL" signal
            if bar.close > context.get("prev_close", 0):
                return "BUY"
            return None

        result = engine.run(bars, strategy_func=strategy)
    """

    def __init__(
        self,
        config: BacktestConfig,
        slippage_calculator: Optional[SlippageCalculator] = None,
        commission_calculator: Optional[CommissionCalculator] = None,
        bias_detector: Optional[LookAheadBiasDetector] = None,
    ):
        """Initialize backtest engine.

        Args:
            config: Backtest configuration
            slippage_calculator: Custom slippage calculator (optional)
            commission_calculator: Custom commission calculator (optional)
            bias_detector: Custom bias detector (optional)
        """
        self.config = config
        self.slippage_calc = slippage_calculator or SlippageCalculator()
        self.commission_calc = commission_calculator or CommissionCalculator()
        self.bias_detector = bias_detector or LookAheadBiasDetector()

        # Initialize components
        self.order_simulator = OrderSimulator(self.slippage_calc, self.commission_calc)
        self.position_manager = PositionManager(config.initial_capital)

        # Tracking
        self.equity_curve: list[EquityCurvePoint] = []
        self.current_bar_index = 0
        self.bars_processed = 0

        # Strategy context (accessible to strategy functions)
        self.strategy_context: dict = {}

    def run(
        self,
        bars: list[OHLCVBar],
        strategy_func: Callable[[OHLCVBar, dict], Optional[str]],
        avg_volume: Decimal = Decimal("2000000"),
    ) -> BacktestResult:
        """Run backtest on historical bars.

        AC1: Event-driven - process bars sequentially
        AC2: Call strategy function on each bar
        AC3: Fill pending orders at next bar open
        AC4: Track equity curve and generate results

        Args:
            bars: List of historical OHLCV bars (chronological order)
            strategy_func: Strategy function that returns "BUY", "SELL", or None
            avg_volume: Average dollar volume for liquidity calculation

        Returns:
            BacktestResult with trades, equity curve, and metrics

        Example:
            def my_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
                # Simple momentum strategy
                if len(context.get("prices", [])) >= 20:
                    sma_20 = sum(context["prices"][-20:]) / 20
                    if bar.close > sma_20 * Decimal("1.02"):
                        return "BUY"
                    elif bar.close < sma_20 * Decimal("0.98"):
                        return "SELL"
                return None

            result = engine.run(bars, my_strategy)
        """
        start_time = datetime.utcnow()

        # Validate bars
        if not bars:
            raise ValueError("Cannot run backtest with empty bar list")

        # Initialize bar count (1-indexed: bars seen so far including current)
        bar_count = 0

        # Main event loop: process each bar sequentially
        for i, bar in enumerate(bars):
            self.current_bar_index = i
            self.bars_processed = i + 1
            bar_count += 1

            # Step 1: Fill pending orders from previous bar (AC2: next bar fill)
            if i > 0:
                self._fill_pending_orders(bar, avg_volume)

            # Step 2: Update position prices and calculate unrealized P&L
            if self.position_manager.positions:
                self.position_manager.calculate_unrealized_pnl(bar)

            # Step 3: Record equity curve point
            is_first = i == 0
            self._record_equity_point(bar, is_first=is_first)

            # Step 4: Update context with current bar count and prices from PREVIOUS bars
            # bar_count represents "bars seen so far" (1-indexed)
            self.strategy_context["bar_count"] = bar_count

            # Step 5: Execute strategy logic (AC1: only current/past data available)
            # Strategy sees bar_count (1-indexed) and prices from previous bars
            signal = strategy_func(bar, self.strategy_context)

            # Step 6: Process strategy signals
            if signal:
                self._process_signal(signal, bar)

            # Step 7: Update strategy context with current bar data AFTER strategy execution
            # This ensures strategy sees prices from PREVIOUS bars (no look-ahead bias)
            self._update_context_with_bar_data(bar)

        # Fill any final pending orders at a virtual next bar
        if bars and self.order_simulator.pending_orders:
            # Use last bar for final fills
            final_bar = bars[-1]
            self._fill_pending_orders(final_bar, avg_volume)
            # Record final equity point after fills
            self._record_equity_point(final_bar)

        # Cancel any remaining pending orders
        self._cancel_pending_orders()

        # Calculate final metrics
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        metrics = self._calculate_metrics()

        # Run bias detection validation (AC8)
        bias_check_passed = self.bias_detector.detect_look_ahead_bias(
            trades=self.position_manager.closed_trades,
            bars=bars,
        )

        # Story 12.6: Calculate enhanced metrics
        from src.backtesting.metrics import MetricsCalculator

        metrics_calculator = MetricsCalculator()

        # Calculate extended reporting metrics
        monthly_returns = metrics_calculator.calculate_monthly_returns(
            equity_curve=self.equity_curve,
            initial_capital=self.config.initial_capital,
        )
        drawdown_periods = metrics_calculator.calculate_drawdown_periods(
            equity_curve=self.equity_curve,
            top_n=5,
        )
        risk_metrics = metrics_calculator.calculate_risk_metrics(
            equity_curve=self.equity_curve,
            trades=self.position_manager.closed_trades,
            initial_capital=self.config.initial_capital,
        )
        campaign_performance = metrics_calculator.calculate_campaign_performance(
            trades=self.position_manager.closed_trades
        )

        # Build result
        result = BacktestResult(
            backtest_run_id=uuid4(),
            symbol=self.config.symbol,
            timeframe="1d",
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            config=self.config,
            equity_curve=self.equity_curve,
            trades=self.position_manager.closed_trades,
            metrics=metrics,
            look_ahead_bias_check=bias_check_passed,
            execution_time_seconds=execution_time,
            created_at=end_time,
            # Story 12.6 enhanced metrics
            monthly_returns=monthly_returns,
            drawdown_periods=drawdown_periods,
            risk_metrics=risk_metrics,
            campaign_performance=campaign_performance,
        )

        return result

    def _fill_pending_orders(self, bar: OHLCVBar, avg_volume: Decimal) -> None:
        """Fill pending orders at current bar open.

        AC2: Market orders filled at next bar open + slippage.

        Args:
            bar: Current bar for fills
            avg_volume: Average volume for slippage calculation
        """
        filled_orders = self.order_simulator.fill_pending_orders(
            next_bar=bar,
            avg_volume=avg_volume,
            commission_per_share=self.config.commission_per_share,
        )

        # Update positions from filled orders
        for order in filled_orders:
            if order.side == "BUY":
                self.position_manager.open_position(order)
            elif order.side == "SELL":
                # Only close if we have a position
                if self.position_manager.has_position(order.symbol):
                    self.position_manager.close_position(order)

    def _process_signal(self, signal: str, bar: OHLCVBar) -> None:
        """Process strategy signal (BUY or SELL).

        Args:
            signal: "BUY" or "SELL"
            bar: Current bar when signal generated
        """
        signal = signal.upper()

        if signal == "BUY":
            # Check if we already have a position
            if not self.position_manager.has_position(self.config.symbol):
                # Calculate position size
                quantity = self._calculate_position_size(bar)
                if quantity > 0:
                    # Submit buy order (filled on next bar)
                    self.order_simulator.submit_order(
                        symbol=self.config.symbol,
                        order_type="MARKET",
                        side="BUY",
                        quantity=quantity,
                        current_bar=bar,
                    )

        elif signal == "SELL":
            # Close position if we have one
            if self.position_manager.has_position(self.config.symbol):
                position = self.position_manager.get_position(self.config.symbol)
                if position:
                    # Submit sell order for entire position
                    self.order_simulator.submit_order(
                        symbol=self.config.symbol,
                        order_type="MARKET",
                        side="SELL",
                        quantity=position.quantity,
                        current_bar=bar,
                    )

    def _calculate_position_size(self, bar: OHLCVBar) -> int:
        """Calculate position size based on risk limits.

        AC: max_position_size as fraction of portfolio (e.g., 0.02 = 2%).

        Args:
            bar: Current bar with price

        Returns:
            Number of shares to buy
        """
        # Portfolio value for sizing
        portfolio_value = self.position_manager.calculate_portfolio_value(bar)

        # Maximum position value
        max_position_value = portfolio_value * self.config.max_position_size

        # Shares we can afford
        price = bar.close  # Use close for estimation
        quantity = int(max_position_value / price)

        # Ensure we have cash available
        estimated_cost = (quantity * price) + (quantity * self.config.commission_per_share)
        if estimated_cost > self.position_manager.cash:
            # Reduce quantity to fit cash
            quantity = int(self.position_manager.cash / (price + self.config.commission_per_share))

        return max(0, quantity)

    def _record_equity_point(self, bar: OHLCVBar, is_first: bool = False) -> None:
        """Record portfolio equity at current bar.

        Args:
            bar: Current bar
            is_first: Whether this is the first equity point
        """
        portfolio_value = self.position_manager.calculate_portfolio_value(bar)
        cash = self.position_manager.cash
        positions_value = portfolio_value - cash

        # Calculate returns
        if is_first or not self.equity_curve:
            daily_return = Decimal("0")
            cumulative_return = Decimal("0")
        else:
            prev_value = self.equity_curve[-1].portfolio_value
            if prev_value > 0:
                daily_return = (portfolio_value - prev_value) / prev_value
                cumulative_return = (
                    portfolio_value - self.config.initial_capital
                ) / self.config.initial_capital
            else:
                daily_return = Decimal("0")
                cumulative_return = Decimal("0")

        point = EquityCurvePoint(
            timestamp=bar.timestamp,
            equity_value=portfolio_value,  # Legacy compatibility
            portfolio_value=portfolio_value,
            cash=cash,
            positions_value=positions_value,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
        )

        self.equity_curve.append(point)

    def _update_context_with_bar_data(self, bar: OHLCVBar) -> None:
        """Update strategy context with current bar data AFTER strategy execution.

        This ensures strategy sees prices from PREVIOUS bars only (no look-ahead bias).
        bar_count is updated separately before strategy execution.

        Args:
            bar: Current bar
        """
        # Track price history
        if "prices" not in self.strategy_context:
            self.strategy_context["prices"] = []
        self.strategy_context["prices"].append(bar.close)

        # Track previous close
        self.strategy_context["prev_close"] = bar.close

    def _cancel_pending_orders(self) -> None:
        """Cancel any remaining pending orders at end of backtest."""
        self.order_simulator.cancel_pending_orders()

    def _calculate_metrics(self) -> BacktestMetrics:
        """Calculate performance metrics from backtest results.

        Returns:
            BacktestMetrics with all performance statistics
        """
        trades = self.position_manager.closed_trades

        # Always calculate drawdown and returns from equity curve
        final_value = (
            self.equity_curve[-1].portfolio_value
            if self.equity_curve
            else self.config.initial_capital
        )
        total_return_pct = (
            (final_value - self.config.initial_capital) / self.config.initial_capital
        ) * Decimal("100")
        max_drawdown, max_dd_duration = self._calculate_drawdown()

        if not trades:
            # No trades - return metrics with drawdown but no trade stats
            return BacktestMetrics(
                total_return_pct=total_return_pct,
                max_drawdown=max_drawdown,
                max_drawdown_duration_days=max_dd_duration,
            )

        # Basic trade statistics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.realized_pnl > 0])
        losing_trades = len([t for t in trades if t.realized_pnl < 0])

        # Win rate
        win_rate = (
            Decimal(winning_trades) / Decimal(total_trades) if total_trades > 0 else Decimal("0")
        )

        # Profit factor
        total_wins = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        total_losses = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else Decimal("0")

        # Average R-multiple
        avg_r_multiple = (
            sum(t.r_multiple for t in trades) / Decimal(total_trades)
            if total_trades > 0
            else Decimal("0")
        )

        # CAGR and Sharpe (simplified for now)
        cagr = total_return_pct  # Simplified - should annualize
        sharpe_ratio = Decimal("0")  # TODO: Implement in Task 7

        return BacktestMetrics(
            total_signals=total_trades,
            win_rate=win_rate,
            average_r_multiple=avg_r_multiple,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            total_return_pct=total_return_pct,
            cagr=cagr,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_duration_days=max_dd_duration,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )

    def _calculate_drawdown(self) -> tuple[Decimal, int]:
        """Calculate maximum drawdown and duration.

        Returns:
            Tuple of (max_drawdown_pct, max_duration_days)
        """
        if not self.equity_curve:
            return Decimal("0"), 0

        max_drawdown = Decimal("0")
        max_duration = 0

        peak = self.equity_curve[0].portfolio_value
        current_duration = 0

        for point in self.equity_curve:
            if point.portfolio_value >= peak:
                # New peak or at peak - reset drawdown
                peak = point.portfolio_value
                current_duration = 0
            else:
                # In drawdown
                drawdown = (peak - point.portfolio_value) / peak if peak > 0 else Decimal("0")
                max_drawdown = max(max_drawdown, drawdown)
                current_duration += 1
                max_duration = max(max_duration, current_duration)

        return max_drawdown, max_duration
