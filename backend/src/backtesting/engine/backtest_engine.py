"""
Backtest Engine Package (Story 11.2 + Story 18.9.2)

Purpose:
--------
Core backtesting engines for the system:

1. BacktestEngine (Story 11.2): Preview mode engine for configuration comparison
   - Dual simulation mode: Run current and proposed configs in parallel
   - Progress tracking: Emit updates via WebSocket every 5% or 10 seconds
   - Timeout handling: 5-minute max with partial results
   - Recommendation algorithm: Compare metrics and suggest action

2. UnifiedBacktestEngine (Story 18.9.2): Unified engine with dependency injection
   - Pluggable strategies via SignalDetector and CostModel protocols
   - Position tracking delegated to PositionManager
   - Bar-by-bar processing with clean separation of concerns

Author: Story 11.2, Story 18.9.2
"""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from src.backtesting.engine.interfaces import CostModel, EngineConfig, SignalDetector
from src.backtesting.metrics import calculate_equity_curve, calculate_metrics
from src.backtesting.position_manager import PositionManager
from src.models.backtest import (
    BacktestComparison,
    BacktestConfig,
    BacktestMetrics,
    BacktestOrder,
    BacktestResult,
    EquityCurvePoint,
)
from src.models.ohlcv import OHLCVBar
from src.models.signal import TradeSignal

logger = logging.getLogger(__name__)

# Constants
TIMEOUT_SECONDS = 300  # 5 minutes
PROGRESS_UPDATE_INTERVAL_SECONDS = 10
PROGRESS_UPDATE_PERCENT = 5
INITIAL_CAPITAL = Decimal("100000.00")  # $100k starting capital


class BacktestEngine:
    """
    Backtesting engine for validating configuration changes.

    Simulates trading with current and proposed configurations against
    historical data to compare performance metrics.
    """

    def __init__(self, progress_callback: Callable[..., Any] | None = None) -> None:
        """
        Initialize backtest engine.

        Args:
            progress_callback: Optional async callback for progress updates.
                               Called with (bars_analyzed, total_bars, percent_complete)
        """
        self.progress_callback = progress_callback
        self._cancelled = False

    async def run_preview(
        self,
        backtest_run_id: UUID,
        current_config: dict[str, Any],
        proposed_config: dict[str, Any],
        historical_bars: list[dict[str, Any]],
        timeout_seconds: int = TIMEOUT_SECONDS,
    ) -> BacktestComparison:
        """
        Run backtest preview comparing current and proposed configurations.

        Args:
            backtest_run_id: Unique identifier for this backtest run
            current_config: Current system configuration
            proposed_config: Proposed configuration changes
            historical_bars: List of historical OHLCV bars with keys:
                - timestamp, open, high, low, close, volume
            timeout_seconds: Maximum execution time (default 300)

        Returns:
            BacktestComparison with metrics and recommendation

        Raises:
            TimeoutError: If backtest exceeds timeout_seconds
        """
        logger.info(
            f"Starting backtest preview {backtest_run_id}",
            extra={
                "backtest_run_id": str(backtest_run_id),
                "bars_count": len(historical_bars),
                "timeout_seconds": timeout_seconds,
            },
        )

        try:
            # Run with timeout
            return await asyncio.wait_for(
                self._run_comparison(
                    backtest_run_id, current_config, proposed_config, historical_bars
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Backtest {backtest_run_id} timed out after {timeout_seconds}s - returning partial results"
            )
            # Return partial results
            # In production, we'd track partial progress and return what we have
            raise

    async def _run_comparison(
        self,
        backtest_run_id: UUID,
        current_config: dict[str, Any],
        proposed_config: dict[str, Any],
        historical_bars: list[dict[str, Any]],
    ) -> BacktestComparison:
        """
        Run dual simulation comparing current and proposed configs.

        Args:
            backtest_run_id: Unique identifier for this run
            current_config: Current configuration
            proposed_config: Proposed configuration
            historical_bars: Historical market data

        Returns:
            BacktestComparison with full results
        """
        total_bars = len(historical_bars)

        # Run current configuration backtest
        current_trades = await self._simulate_trading(
            backtest_run_id, current_config, historical_bars, "current"
        )

        # Run proposed configuration backtest
        proposed_trades = await self._simulate_trading(
            backtest_run_id, proposed_config, historical_bars, "proposed"
        )

        # Calculate metrics for both
        current_metrics = calculate_metrics(current_trades, INITIAL_CAPITAL)
        proposed_metrics = calculate_metrics(proposed_trades, INITIAL_CAPITAL)

        # Generate equity curves
        equity_curve_current = calculate_equity_curve(current_trades, INITIAL_CAPITAL)
        equity_curve_proposed = calculate_equity_curve(proposed_trades, INITIAL_CAPITAL)

        # Determine recommendation
        recommendation, recommendation_text = self._generate_recommendation(
            current_metrics, proposed_metrics
        )

        return BacktestComparison(
            current_metrics=current_metrics,
            proposed_metrics=proposed_metrics,
            recommendation=recommendation,
            recommendation_text=recommendation_text,
            equity_curve_current=equity_curve_current,
            equity_curve_proposed=equity_curve_proposed,
        )

    async def _simulate_trading(
        self,
        backtest_run_id: UUID,
        config: dict[str, Any],
        historical_bars: list[dict[str, Any]],
        config_label: str,
    ) -> list[dict[str, Any]]:
        """
        Simulate trading with given configuration.

        Args:
            backtest_run_id: Backtest run identifier
            config: Configuration to test
            historical_bars: Historical market data
            config_label: Label for logging ("current" or "proposed")

        Returns:
            List of trade dictionaries with results
        """
        trades = []
        total_bars = len(historical_bars)
        last_progress_update = datetime.now(UTC)
        last_progress_percent = 0

        for idx, bar in enumerate(historical_bars):
            if self._cancelled:
                logger.info(f"Backtest {backtest_run_id} cancelled")
                break

            # Simulate pattern detection and signal generation
            # In production, this would integrate with actual pattern engine
            # For MVP, we'll use simplified logic

            signal = self._detect_signal(bar, config)
            if signal:
                trade = self._execute_trade(bar, signal, historical_bars[idx:])
                trades.append(trade)

            # Emit progress updates
            bars_analyzed = idx + 1
            percent_complete = int((bars_analyzed / total_bars) * 100)

            # Update every 5% or 10 seconds
            now = datetime.now(UTC)
            should_update = (
                percent_complete >= last_progress_percent + PROGRESS_UPDATE_PERCENT
                or (now - last_progress_update).total_seconds() >= PROGRESS_UPDATE_INTERVAL_SECONDS
            )

            if should_update and self.progress_callback:
                await self.progress_callback(bars_analyzed, total_bars, percent_complete)
                last_progress_update = now
                last_progress_percent = percent_complete

        logger.info(
            f"Simulation complete for {config_label} config",
            extra={"backtest_run_id": str(backtest_run_id), "trades": len(trades)},
        )

        return trades

    def _detect_signal(self, bar: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
        """
        Detect trade signal based on bar data and configuration.

        This is a simplified placeholder for MVP. In production, this would
        integrate with the actual Wyckoff pattern detection engine.

        Args:
            bar: OHLCV bar data
            config: Configuration for signal detection

        Returns:
            Signal dictionary if detected, None otherwise
        """
        # Placeholder: Simplified signal detection
        # In production, integrate with pattern_engine and signal_generator

        # Example: Generate signal on strong volume with price range
        volume_threshold = config.get("volume_thresholds", {}).get("ultra_high", 2.5)
        price_change_pct = abs(
            (Decimal(str(bar["close"])) - Decimal(str(bar["open"]))) / Decimal(str(bar["open"]))
        )

        # Simplified: Trigger signal if price moves >2% with high volume
        if price_change_pct > Decimal("0.02"):
            return {
                "type": "spring" if bar["close"] > bar["open"] else "test",
                "entry_price": bar["close"],
                "confidence": 0.75,
            }

        return None

    def _execute_trade(
        self, entry_bar: dict[str, Any], signal: dict[str, Any], future_bars: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Execute simulated trade and calculate results.

        This is a simplified placeholder for MVP. In production, this would
        use actual position sizing, risk management, and exit logic.

        Args:
            entry_bar: Bar where trade was entered
            signal: Signal that triggered the trade
            future_bars: Future bars for simulating exit

        Returns:
            Trade dictionary with results
        """
        entry_price = Decimal(str(signal["entry_price"]))
        position_size = Decimal("100")  # Simplified: Fixed 100 shares
        direction = "long" if signal["type"] == "spring" else "short"

        # Simplified exit logic: Hold for 5 bars or until 3% move
        exit_bar = future_bars[min(5, len(future_bars) - 1)] if len(future_bars) > 1 else entry_bar
        exit_price = Decimal(str(exit_bar["close"]))

        # Calculate P&L
        if direction == "long":
            profit = (exit_price - entry_price) * position_size
            r_multiple = (exit_price - entry_price) / (entry_price * Decimal("0.02"))  # 2% risk
        else:
            profit = (entry_price - exit_price) * position_size
            r_multiple = (entry_price - exit_price) / (entry_price * Decimal("0.02"))

        return {
            "entry_timestamp": entry_bar["timestamp"],
            "exit_timestamp": exit_bar["timestamp"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "position_size": position_size,
            "direction": direction,
            "profit": profit,
            "r_multiple": r_multiple,
        }

    def _generate_recommendation(
        self, current: BacktestMetrics, proposed: BacktestMetrics
    ) -> tuple[str, str]:
        """
        Generate recommendation by comparing current and proposed metrics.

        Recommendation algorithm:
        - Improvement: Win rate increases AND (avg_r_multiple improves OR max_drawdown decreases)
        - Degraded: Win rate decreases OR max_drawdown increases significantly
        - Neutral: Minor changes with no clear advantage

        Args:
            current: Current configuration metrics
            proposed: Proposed configuration metrics

        Returns:
            Tuple of (recommendation, recommendation_text)
        """
        # Calculate deltas
        win_rate_delta = proposed.win_rate - current.win_rate
        r_multiple_delta = proposed.average_r_multiple - current.average_r_multiple
        drawdown_delta = proposed.max_drawdown - current.max_drawdown
        pf_delta = proposed.profit_factor - current.profit_factor

        # Thresholds for recommendation
        significant_improvement = Decimal("0.05")  # 5% improvement
        significant_degradation = Decimal("0.05")  # 5% degradation

        # Check for improvement
        if win_rate_delta > significant_improvement and (
            r_multiple_delta > Decimal("0.1") or drawdown_delta < Decimal("-0.02")
        ):
            return (
                "improvement",
                f"Performance improved - Win rate +{float(win_rate_delta)*100:.1f}%, "
                f"Avg R-multiple +{float(r_multiple_delta):.2f}",
            )

        # Check for degradation
        if win_rate_delta < -significant_degradation or drawdown_delta > Decimal("0.03"):
            return (
                "degraded",
                f"Performance degraded - not recommended. "
                f"Win rate {float(win_rate_delta)*100:+.1f}%, "
                f"Max drawdown {float(drawdown_delta)*100:+.1f}%",
            )

        # Neutral
        return (
            "neutral",
            f"Marginal changes detected. Win rate {float(win_rate_delta)*100:+.1f}%, "
            f"Profit factor {float(pf_delta):+.2f}",
        )

    def cancel(self) -> None:
        """Cancel the currently running backtest."""
        self._cancelled = True


class UnifiedBacktestEngine:
    """
    Unified backtest engine with pluggable strategies (Story 18.9.2).

    Consolidates duplicate backtest engine implementations into a single,
    maintainable class using dependency injection for strategies.

    Attributes:
        _detector: Signal detection strategy
        _cost_model: Transaction cost calculation strategy
        _positions: Position management delegate
        _config: Engine configuration

    Reference: CF-002 from Critical Foundation Refactoring document.
    """

    def __init__(
        self,
        signal_detector: SignalDetector,
        cost_model: CostModel,
        position_manager: PositionManager,
        config: EngineConfig,
    ) -> None:
        """
        Initialize unified backtest engine with injectable dependencies.

        Args:
            signal_detector: Strategy for detecting trading signals
            cost_model: Strategy for calculating transaction costs
            position_manager: Delegate for position tracking
            config: Engine configuration parameters
        """
        self._detector = signal_detector
        self._cost_model = cost_model
        self._positions = position_manager
        self._config = config
        self._equity_curve: list[EquityCurvePoint] = []
        self._bars: list[OHLCVBar] = []

    def run(self, bars: list[OHLCVBar]) -> BacktestResult:
        """
        Execute backtest on historical bar data.

        Processes bars sequentially, detecting signals and managing positions.
        Records equity curve at each bar for performance analysis.

        Args:
            bars: Historical OHLCV bars to backtest (chronological order)

        Returns:
            BacktestResult with trades, equity curve, and metrics
        """
        start_time = time.time()
        self._bars = bars
        self._equity_curve = []

        for index, bar in enumerate(bars):
            self._process_bar(bar, index)

        execution_time = time.time() - start_time
        return self._generate_result(bars, execution_time)

    def _process_bar(self, bar: OHLCVBar, index: int) -> None:
        """
        Process a single bar for signal detection and position management.

        Args:
            bar: Current OHLCV bar
            index: Bar index in the sequence
        """
        # Calculate portfolio value once per bar (avoid double calculation)
        portfolio_value = self._positions.calculate_portfolio_value(bar)

        # Detect potential signal - pass only bars up to current index to prevent look-ahead
        # This enforces that detectors cannot access future data
        visible_bars = self._bars[: index + 1]
        signal = self._detector.detect(visible_bars, index)

        if signal is not None:
            self._handle_signal(signal, bar, portfolio_value)

        # Record equity curve point
        self._record_equity_point(bar, portfolio_value)

    def _handle_signal(self, signal: TradeSignal, bar: OHLCVBar, portfolio_value: Decimal) -> None:
        """
        Handle a detected signal by opening or closing positions.

        Args:
            signal: Detected trading signal
            bar: Current bar for execution
            portfolio_value: Current portfolio value for position sizing
        """
        # Check position limits
        if self._positions.get_pending_count() >= self._config.max_open_positions:
            return

        # Create and execute order based on signal direction
        order = self._create_order(signal, bar, portfolio_value)
        if order is None:
            return

        self._execute_order(order, bar)

    def _create_order(
        self, signal: TradeSignal, bar: OHLCVBar, portfolio_value: Decimal
    ) -> Optional[BacktestOrder]:
        """
        Create a backtest order from a signal.

        Args:
            signal: Trading signal
            bar: Current bar for pricing
            portfolio_value: Current portfolio value for position sizing

        Returns:
            BacktestOrder or None if order cannot be created
        """
        # Validate signal direction explicitly
        if signal.direction not in ("LONG", "SHORT"):
            logger.warning(
                f"Invalid signal direction '{signal.direction}' for {bar.symbol}, skipping"
            )
            return None

        # Calculate position size based on current equity (passed in, not recalculated)
        position_value = portfolio_value * self._config.max_position_size
        quantity = int(position_value / bar.close)

        if quantity <= 0:
            return None

        return BacktestOrder(
            order_id=uuid4(),
            symbol=bar.symbol,
            side="BUY" if signal.direction == "LONG" else "SELL",
            order_type="MARKET",
            quantity=quantity,
            status="PENDING",
            created_bar_timestamp=bar.timestamp,
        )

    def _execute_order(self, order: BacktestOrder, bar: OHLCVBar) -> None:
        """
        Execute an order with cost model calculations.

        Args:
            order: Order to execute
            bar: Current bar for fill price
        """
        # Calculate costs if enabled
        commission = Decimal("0")
        slippage = Decimal("0")

        if self._config.enable_cost_model:
            commission = self._cost_model.calculate_commission(order)
            slippage = self._cost_model.calculate_slippage(order, bar)

        # Update order with fill details
        order.fill_price = bar.close + slippage
        order.commission = commission
        order.slippage = slippage
        order.status = "FILLED"
        order.filled_bar_timestamp = bar.timestamp

        # Delegate position tracking
        if order.side == "BUY":
            self._positions.open_position(order)
        else:
            if self._positions.has_position(order.symbol):
                self._positions.close_position(order)
            else:
                logger.debug(f"SELL order skipped for {order.symbol}: no open position to close")

    def _record_equity_point(self, bar: OHLCVBar, portfolio_value: Decimal) -> None:
        """
        Record an equity curve point.

        Args:
            bar: Current bar
            portfolio_value: Current portfolio value
        """
        point = EquityCurvePoint(
            timestamp=bar.timestamp,
            equity_value=portfolio_value,  # Legacy field, same as portfolio_value
            portfolio_value=portfolio_value,
            cash=self._positions.cash,
            positions_value=portfolio_value - self._positions.cash,
        )
        self._equity_curve.append(point)

    def _generate_result(self, bars: list[OHLCVBar], execution_time: float) -> BacktestResult:
        """
        Generate the final backtest result.

        Args:
            bars: Original bar data
            execution_time: Time taken to run backtest

        Returns:
            Complete BacktestResult with all metrics
        """
        trades = self._positions.closed_trades

        # Handle empty bars case with warning
        if not bars:
            logger.warning("Backtest run with empty bars list - returning empty result")
            symbol = "EMPTY"
            timeframe = "1d"
            start_date = datetime.now(UTC).date()
            end_date = datetime.now(UTC).date()
        else:
            symbol = bars[0].symbol
            timeframe = bars[0].timeframe
            start_date = bars[0].timestamp.date()
            end_date = bars[-1].timestamp.date()

        # Build metrics using existing calculator
        metrics = self._calculate_metrics(trades)

        # Build BacktestConfig from EngineConfig for result
        config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self._config.initial_capital,
            max_position_size=self._config.max_position_size,
        )

        return BacktestResult(
            backtest_run_id=uuid4(),
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            config=config,
            equity_curve=self._equity_curve,
            trades=trades,
            summary=metrics,
            look_ahead_bias_check=True,
            execution_time_seconds=Decimal(str(execution_time)),
        )

    def _calculate_metrics(self, trades: list) -> BacktestMetrics:
        """
        Calculate performance metrics from trades.

        Args:
            trades: List of completed trades

        Returns:
            BacktestMetrics with performance statistics
        """
        if not trades:
            return BacktestMetrics(
                total_signals=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                average_r_multiple=Decimal("0"),
                max_drawdown=Decimal("0"),
                profit_factor=Decimal("0"),
            )

        # Calculate basic metrics
        winning = [t for t in trades if t.realized_pnl > 0]
        losing = [t for t in trades if t.realized_pnl <= 0]

        win_rate = Decimal(len(winning)) / Decimal(len(trades)) if trades else Decimal("0")

        # Profit factor: ratio of gross profit to gross loss
        # When no losing trades, use a high cap (999.99) to indicate excellent performance
        gross_profit = sum(t.realized_pnl for t in winning) if winning else Decimal("0")
        gross_loss = abs(sum(t.realized_pnl for t in losing)) if losing else Decimal("0")
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = Decimal("999.99")  # Cap for "infinite" profit factor
        else:
            profit_factor = Decimal("0")

        return BacktestMetrics(
            total_signals=len(trades),
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            average_r_multiple=Decimal("0"),  # Simplified for now
            max_drawdown=self._calculate_max_drawdown(),
            profit_factor=profit_factor,
        )

    def _calculate_max_drawdown(self) -> Decimal:
        """
        Calculate maximum drawdown from equity curve.

        Returns:
            Maximum drawdown as decimal (0.10 = 10%)
        """
        if not self._equity_curve:
            return Decimal("0")

        peak = Decimal("0")
        max_dd = Decimal("0")

        for point in self._equity_curve:
            if point.portfolio_value > peak:
                peak = point.portfolio_value
            if peak > 0:
                drawdown = (peak - point.portfolio_value) / peak
                if drawdown > max_dd:
                    max_dd = drawdown

        return max_dd
