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
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from src.backtesting.engine.bar_processor import calculate_stop_fill_price
from src.backtesting.engine.interfaces import CostModel, EngineConfig, SignalDetector
from src.backtesting.metrics import calculate_equity_curve, calculate_metrics
from src.backtesting.position_manager import PositionManager
from src.backtesting.risk_integration import BacktestRiskManager
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
                trade = self._execute_trade(bar, signal, config)
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
        self, entry_bar: dict[str, Any], signal: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute simulated trade and calculate results using only current bar data.

        Uses a fixed percentage-based exit to avoid look-ahead bias.
        No future bars are accessed -- exit price is estimated from the entry
        price using a configurable take-profit/stop-loss percentage.

        Args:
            entry_bar: Bar where trade was entered
            signal: Signal that triggered the trade
            config: Configuration dict (may contain exit_pct override)

        Returns:
            Trade dictionary with results
        """
        entry_price = Decimal(str(signal["entry_price"]))
        position_size = Decimal("100")  # Simplified: Fixed 100 shares
        direction = "long" if signal["type"] == "spring" else "short"

        # Use a configurable exit percentage (default 2%) to estimate exit.
        # Positive for take-profit assumption based on signal confidence.
        exit_pct = Decimal(str(config.get("preview_exit_pct", "0.02")))
        confidence = Decimal(str(signal.get("confidence", "0.5")))

        # Scale the exit move by confidence: higher confidence -> closer to
        # full take-profit; lower confidence -> smaller estimated move.
        estimated_move = entry_price * exit_pct * confidence

        if direction == "long":
            exit_price = entry_price + estimated_move
        else:
            exit_price = entry_price - estimated_move

        # Calculate P&L
        risk_amount = entry_price * Decimal("0.02")  # 2% risk
        if direction == "long":
            profit = (exit_price - entry_price) * position_size
            r_multiple = (exit_price - entry_price) / risk_amount if risk_amount else Decimal("0")
        else:
            profit = (entry_price - exit_price) * position_size
            r_multiple = (entry_price - exit_price) / risk_amount if risk_amount else Decimal("0")

        return {
            "entry_timestamp": entry_bar["timestamp"],
            "exit_timestamp": entry_bar["timestamp"],  # Same bar (no future data)
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
                f"Performance improved - Win rate +{float(win_rate_delta) * 100:.1f}%, "
                f"Avg R-multiple +{float(r_multiple_delta):.2f}",
            )

        # Check for degradation
        if win_rate_delta < -significant_degradation or drawdown_delta > Decimal("0.03"):
            return (
                "degraded",
                f"Performance degraded - not recommended. "
                f"Win rate {float(win_rate_delta) * 100:+.1f}%, "
                f"Max drawdown {float(drawdown_delta) * 100:+.1f}%",
            )

        # Neutral
        return (
            "neutral",
            f"Marginal changes detected. Win rate {float(win_rate_delta) * 100:+.1f}%, "
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

    # Conservative gap buffer for risk sizing (0.5% = accounts for overnight/session gaps).
    # Applied when estimating entry price at order creation time so that position size
    # is conservative relative to the actual next-bar fill price.
    GAP_BUFFER = Decimal("0.005")

    # Hard per-trade risk limit (non-negotiable, see CLAUDE.md)
    MAX_RISK_PER_TRADE_PCT = Decimal("0.02")

    def __init__(
        self,
        signal_detector: SignalDetector,
        cost_model: CostModel,
        position_manager: PositionManager,
        config: EngineConfig,
        risk_manager: BacktestRiskManager | None = None,
    ) -> None:
        """
        Initialize unified backtest engine with injectable dependencies.

        Args:
            signal_detector: Strategy for detecting trading signals
            cost_model: Strategy for calculating transaction costs
            position_manager: Delegate for position tracking
            config: Engine configuration parameters
            risk_manager: Optional risk manager for position sizing and risk limits.
                          When None, falls back to flat percentage sizing.
        """
        self._detector = signal_detector
        self._cost_model = cost_model
        self._positions = position_manager
        self._config = config
        self._risk_manager = risk_manager
        self._equity_curve: list[EquityCurvePoint] = []
        self._bars: list[OHLCVBar] = []
        self._pending_orders: list[BacktestOrder] = []
        # Maps symbol -> (stop_price, target_price, risk_manager_position_id)
        self._position_stops: dict[str, tuple[Decimal, Decimal, str | None]] = {}
        # Temporary storage for signal stop/target keyed by order_id
        self._pending_order_stops: dict[UUID, tuple[Decimal, Decimal | None]] = {}
        # Peak prices for trailing stop (symbol -> highest high for LONG / lowest low for SHORT)
        self._position_peaks: dict[str, Decimal] = {}
        # Original risk distance for trailing stop (symbol -> abs(entry - initial_stop))
        self._position_initial_risk: dict[str, Decimal] = {}

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
        self._pending_orders = []

        for index, bar in enumerate(bars):
            self._process_bar(bar, index)

        # Cancel any pending orders that were never filled (no next bar available)
        if self._pending_orders:
            for order in self._pending_orders:
                order.status = "REJECTED"
                self._pending_order_stops.pop(order.order_id, None)
            self._pending_orders.clear()

        execution_time = time.time() - start_time
        return self._generate_result(bars, execution_time)

    def _process_bar(self, bar: OHLCVBar, index: int) -> None:
        """
        Process a single bar for signal detection and position management.

        Order of operations per bar:
        1. Fill any pending orders from previous bar at this bar's open price
        2. Detect signals on this bar
        3. Create new orders as PENDING (filled on the next bar)
        4. Record equity curve point

        Args:
            bar: Current OHLCV bar
            index: Bar index in the sequence
        """
        # Step 1: Fill pending orders from previous bar at current bar's open
        self._fill_pending_orders(bar)

        # Step 1b: Check stop-loss / take-profit exits for open positions
        self._check_position_exits(bar)

        # Calculate portfolio value once per bar (after fills and exits, before signal detection)
        portfolio_value = self._positions.calculate_portfolio_value(bar)

        # Step 2: Detect potential signal - pass only bars up to current index
        # to prevent look-ahead. This enforces that detectors cannot access future data.
        visible_bars = self._bars[: index + 1]
        signal = self._detector.detect(visible_bars, index)

        # Step 3: Create order as PENDING (will be filled on next bar)
        if signal is not None:
            self._handle_signal(signal, bar, portfolio_value)

        # Step 4: Record equity curve point
        self._record_equity_point(bar, portfolio_value)

    def _check_position_exits(self, bar: OHLCVBar) -> None:
        """
        Check open positions for stop-loss and take-profit exits.

        For each open position matching the bar's symbol, checks if the bar's
        high/low triggers the stop or target price. Uses stored signal-based
        stop/target levels when available (Wyckoff level-based stops), falling
        back to percentage-based stops from engine config.

        If both stop and target are hit in the same bar, the stop is assumed
        to have been hit first (conservative approach).

        Args:
            bar: Current OHLCV bar with high/low for exit checking
        """
        positions_to_close = []

        for symbol, position in self._positions.positions.items():
            if symbol != bar.symbol:
                continue

            entry_price = position.average_entry_price

            # Use stored signal-based stops if available, otherwise fall back to percentage
            if symbol in self._position_stops:
                stop_price, target_price, _pos_id = self._position_stops[symbol]
            else:
                stop_pct = self._config.risk_per_trade
                target_pct = stop_pct * Decimal("3")  # 3:1 reward-to-risk
                if position.side == "LONG":
                    stop_price = entry_price * (Decimal("1") - stop_pct)
                    target_price = entry_price * (Decimal("1") + target_pct)
                else:
                    stop_price = entry_price * (Decimal("1") + stop_pct)
                    target_price = entry_price * (Decimal("1") - target_pct)

            # Trailing stop: ratchet stop using initial risk distance (stored at entry)
            if self._config.enable_trailing_stop and symbol in self._position_initial_risk:
                original_risk = self._position_initial_risk[symbol]
                if position.side == "LONG":
                    peak = self._position_peaks.get(symbol, entry_price)
                    peak = max(peak, bar.high)
                    self._position_peaks[symbol] = peak
                    new_stop = peak - original_risk
                    if new_stop > stop_price:
                        stop_price = new_stop
                        if symbol in self._position_stops:
                            _, tp, pid = self._position_stops[symbol]
                            self._position_stops[symbol] = (stop_price, tp, pid)
                else:  # SHORT
                    trough = self._position_peaks.get(symbol, entry_price)
                    trough = min(trough, bar.low)
                    self._position_peaks[symbol] = trough
                    new_stop = trough + original_risk
                    if new_stop < stop_price:
                        stop_price = new_stop
                        if symbol in self._position_stops:
                            _, tp, pid = self._position_stops[symbol]
                            self._position_stops[symbol] = (stop_price, tp, pid)

            if position.side == "LONG":
                stop_hit = bar.low <= stop_price
                target_hit = bar.high >= target_price
            elif position.side == "SHORT":
                stop_hit = bar.high >= stop_price
                target_hit = bar.low <= target_price
            else:
                logger.warning(
                    f"Unknown position side '{position.side}' for {symbol}, skipping exit check"
                )
                continue

            if stop_hit:
                fill_price = calculate_stop_fill_price(position.side, bar.open, stop_price)
                positions_to_close.append(
                    (symbol, fill_price, position.quantity, position.side, "stop_loss")
                )
            elif target_hit:
                # Target fills remain at target price (conservative).
                positions_to_close.append(
                    (symbol, target_price, position.quantity, position.side, "take_profit")
                )

        # Execute exits: SELL closes LONG, BUY closes SHORT
        for symbol, exit_price, quantity, pos_side, reason in positions_to_close:
            exit_order_side = "SELL" if pos_side == "LONG" else "BUY"
            exit_order = BacktestOrder(
                order_id=uuid4(),
                symbol=symbol,
                side=exit_order_side,
                order_type="MARKET",
                quantity=quantity,
                status="FILLED",
                created_bar_timestamp=bar.timestamp,
                filled_bar_timestamp=bar.timestamp,
                fill_price=exit_price,
                commission=Decimal("0"),
                slippage=Decimal("0"),
            )
            if self._config.enable_cost_model:
                exit_order.commission = self._cost_model.calculate_commission(exit_order)
                exit_order.slippage = self._cost_model.calculate_slippage(exit_order, bar)

            if self._positions.has_position(symbol):
                stored = self._position_stops.get(symbol)
                stop_for_trade = stored[0] if stored else None
                trade = self._positions.close_position(exit_order, stop_price=stop_for_trade)
                self._compute_r_multiple(trade)

                # Update risk manager if present (close_position handles capital tracking)
                if self._risk_manager is not None:
                    # Use stored position_id if available, fall back to symbol
                    risk_position_id = symbol
                    if symbol in self._position_stops:
                        _, _, stored_pos_id = self._position_stops[symbol]
                        if stored_pos_id is not None:
                            risk_position_id = stored_pos_id
                    self._risk_manager.close_position(risk_position_id, exit_price)
                    # Sync capital between risk manager and position manager
                    self._risk_manager.current_capital = self._positions.cash

                # Clean up stored stops, peaks, and initial risk
                self._position_stops.pop(symbol, None)
                self._position_peaks.pop(symbol, None)
                self._position_initial_risk.pop(symbol, None)

                logger.debug(f"Position exit for {symbol}: {reason} at {exit_price}")

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
    ) -> BacktestOrder | None:
        """
        Create a backtest order from a signal.

        When a risk manager is provided and the signal has stop_loss info,
        uses risk-based position sizing (risk_amount / stop_distance).
        Otherwise falls back to flat percentage sizing.

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

        # Risk-based sizing when risk manager is present and signal has stop_loss
        signal_stop_loss = getattr(signal, "stop_loss", None)
        if self._risk_manager is not None and signal_stop_loss is not None:
            entry_price = bar.close
            stop_loss = Decimal(str(signal_stop_loss))
            campaign_id = getattr(signal, "campaign_id", None) or bar.symbol

            # Apply gap buffer: assume fill will be worse than bar.close by GAP_BUFFER %.
            # This makes position sizing conservative, building in a cushion for the
            # signal-bar-close to next-bar-open gap.
            if signal.direction == "LONG":
                adjusted_entry = entry_price * (Decimal("1") + self.GAP_BUFFER)
            else:
                adjusted_entry = entry_price * (Decimal("1") - self.GAP_BUFFER)

            # Validate through risk manager (checks all 4 risk limits + sizes position)
            (
                can_trade,
                risk_position_size,
                rejection_reason,
            ) = self._risk_manager.validate_and_size_position(
                symbol=bar.symbol,
                entry_price=adjusted_entry,
                stop_loss=stop_loss,
                campaign_id=campaign_id,
                side=signal.direction,
                pattern_type=getattr(signal, "pattern_type", None),
            )

            if not can_trade:
                logger.info(f"Risk manager rejected order for {bar.symbol}: {rejection_reason}")
                return None

            # risk_position_size is already in tradeable units (shares/lots)
            quantity = int(risk_position_size)
        else:
            # Fallback: flat percentage sizing (original behavior)
            position_value = portfolio_value * self._config.max_position_size
            quantity = int(position_value / bar.close)

        if quantity <= 0:
            return None

        order = BacktestOrder(
            order_id=uuid4(),
            symbol=bar.symbol,
            side="BUY" if signal.direction == "LONG" else "SELL",
            order_type="MARKET",
            quantity=quantity,
            status="PENDING",
            created_bar_timestamp=bar.timestamp,
        )

        # Store signal stop/target for use when filling the order
        signal_stop = getattr(signal, "stop_loss", None)
        signal_target = getattr(signal, "target_levels", None)
        if signal_stop is not None:
            stop_dec = Decimal(str(signal_stop))
            target_dec: Decimal | None = None
            if signal_target is not None:
                primary = getattr(signal_target, "primary_target", None)
                if primary is not None:
                    target_dec = Decimal(str(primary))
            self._pending_order_stops[order.order_id] = (stop_dec, target_dec)

        return order

    def _execute_order(self, order: BacktestOrder, bar: OHLCVBar) -> None:
        """
        Queue an order as PENDING for next-bar fill.

        Orders are NOT filled on the signal bar. They are added to the
        pending queue and will be filled at the next bar's open price,
        mirroring realistic execution (signal at bar close -> fill at next open).

        Args:
            order: Order to queue (already has status=PENDING)
            bar: Current bar when signal was generated (used for timestamp only)
        """
        # Order is already created with status="PENDING" in _create_order
        self._pending_orders.append(order)

    def _fill_pending_orders(self, bar: OHLCVBar) -> None:
        """
        Fill all pending orders at the current bar's open price.

        Called at the START of each bar's processing, before signal detection.
        This ensures orders from the previous bar are filled at the next bar's
        open price, preventing same-bar fill bias.

        Args:
            bar: Current bar whose open price is used for fills
        """
        if not self._pending_orders:
            return

        filled_orders: list[BacktestOrder] = []
        for order in self._pending_orders:
            # Calculate costs if enabled
            commission = Decimal("0")
            slippage = Decimal("0")

            if self._config.enable_cost_model:
                commission = self._cost_model.calculate_commission(order)
                slippage = self._cost_model.calculate_slippage(order, bar)

            # Fill at next bar's OPEN price with directional slippage:
            # BUY orders pay more (add slippage), SELL orders receive less (subtract slippage)
            abs_slippage = abs(slippage)
            if order.side == "BUY":
                order.fill_price = bar.open + abs_slippage
            else:
                order.fill_price = bar.open - abs_slippage
            order.commission = commission
            order.slippage = abs_slippage
            order.status = "FILLED"
            order.filled_bar_timestamp = bar.timestamp

            # Post-fill risk validation: check if actual risk exceeds the 2% hard limit.
            # The gap buffer in _create_order should handle most cases, but this catches
            # extreme gaps (e.g. overnight gaps larger than the buffer).
            is_opening = not self._positions.has_position(order.symbol)
            if is_opening and order.order_id in self._pending_order_stops:
                stop_loss_price = self._pending_order_stops[order.order_id][0]
                actual_risk_per_share = abs(order.fill_price - stop_loss_price)
                actual_risk = actual_risk_per_share * Decimal(str(order.quantity))
                portfolio_value = self._positions.calculate_portfolio_value(bar)
                if portfolio_value > Decimal("0"):
                    actual_risk_pct = actual_risk / portfolio_value
                    if actual_risk_pct > self.MAX_RISK_PER_TRADE_PCT:
                        safe_quantity = int(
                            order.quantity * (self.MAX_RISK_PER_TRADE_PCT / actual_risk_pct)
                        )
                        if safe_quantity <= 0:
                            # Risk too high even for 1 share -- cancel the order
                            order.status = "REJECTED"
                            self._pending_order_stops.pop(order.order_id, None)
                            logger.info(
                                f"Order cancelled for {order.symbol}: fill gap "
                                f"caused risk {float(actual_risk_pct) * 100:.2f}% > 2% limit, "
                                f"quantity reduced to 0"
                            )
                            filled_orders.append(order)
                            continue
                        logger.info(
                            f"Reducing quantity for {order.symbol} from {order.quantity} "
                            f"to {safe_quantity}: fill gap caused risk "
                            f"{float(actual_risk_pct) * 100:.2f}% > 2% limit"
                        )
                        order.quantity = safe_quantity

            # Delegate position tracking
            if order.status == "REJECTED":
                # Order was cancelled during risk check above
                self._pending_order_stops.pop(order.order_id, None)

            elif order.side == "BUY" and not self._positions.has_position(order.symbol):
                # BUY with no position: open LONG
                self._positions.open_position(order, side="LONG")
                self._setup_position_stops(order, bar, side="LONG")

            elif order.side == "SELL" and not self._positions.has_position(order.symbol):
                # SELL with no position: open SHORT
                self._positions.open_position(order, side="SHORT")
                self._setup_position_stops(order, bar, side="SHORT")

            elif self._positions.has_position(order.symbol):
                position = self._positions.get_position(order.symbol)
                assert position is not None  # guaranteed by has_position

                # Check if this is an ADD (same direction) or CLOSE (opposite direction)
                is_add = (order.side == "BUY" and position.side == "LONG") or (
                    order.side == "SELL" and position.side == "SHORT"
                )

                if is_add:
                    # BMAD Add workflow: add to existing position (average entry)
                    self._positions.open_position(order, side=position.side)

                    # Register with risk manager if present
                    if self._risk_manager is not None and order.fill_price is not None:
                        self._risk_manager.register_position(
                            symbol=order.symbol,
                            campaign_id=order.symbol,
                            entry_price=order.fill_price,
                            stop_loss=self._position_stops.get(order.symbol, (order.fill_price,))[
                                0
                            ],
                            position_size=Decimal(str(order.quantity)),
                            timestamp=bar.timestamp,
                            side=position.side,
                        )

                    # Update stop if new signal has a tighter (more protective) stop
                    new_stop_info = self._pending_order_stops.pop(order.order_id, None)
                    if new_stop_info is not None and order.symbol in self._position_stops:
                        new_stop = new_stop_info[0]
                        old_stop, old_target, old_pos_id = self._position_stops[order.symbol]
                        # Tighter = higher stop for LONG, lower stop for SHORT
                        if position.side == "LONG" and new_stop > old_stop:
                            self._position_stops[order.symbol] = (new_stop, old_target, old_pos_id)
                        elif position.side == "SHORT" and new_stop < old_stop:
                            self._position_stops[order.symbol] = (new_stop, old_target, old_pos_id)

                    logger.info(
                        f"Added to {position.side} position for {order.symbol}: "
                        f"+{order.quantity} shares at {order.fill_price}, "
                        f"new total {position.quantity} shares"
                    )
                else:
                    # Close existing position (opposite direction)
                    stored = self._position_stops.get(order.symbol)
                    stop_for_trade = stored[0] if stored else None
                    trade = self._positions.close_position(order, stop_price=stop_for_trade)
                    self._compute_r_multiple(trade)

                    # Close position in risk manager using stored position_id
                    if self._risk_manager is not None and order.fill_price is not None:
                        risk_position_id: str = order.symbol
                        if order.symbol in self._position_stops:
                            _, _, stored_pos_id = self._position_stops[order.symbol]
                            if stored_pos_id is not None:
                                risk_position_id = stored_pos_id
                        self._risk_manager.close_position(risk_position_id, order.fill_price)
                        # Sync capital between risk manager and position manager
                        self._risk_manager.current_capital = self._positions.cash
                    self._position_stops.pop(order.symbol, None)
                    self._position_peaks.pop(order.symbol, None)
                    self._position_initial_risk.pop(order.symbol, None)
            else:
                self._pending_order_stops.pop(order.order_id, None)
                logger.debug(f"Order skipped for {order.symbol}: cannot process")

            filled_orders.append(order)

        # Clear the pending queue
        self._pending_orders.clear()

    def _setup_position_stops(self, order: BacktestOrder, bar: OHLCVBar, side: str) -> None:
        """
        Set up stop-loss, take-profit, and risk manager tracking for a newly opened position.

        Args:
            order: The filled order that opened the position
            bar: The current bar when the order was filled
            side: Position side ("LONG" or "SHORT")
        """
        # Determine stop/target from signal or fall back to percentage
        stored = self._pending_order_stops.pop(order.order_id, None)
        if stored is not None:
            stop_loss_price = stored[0]
            signal_target = stored[1]
        else:
            stop_pct = self._config.risk_per_trade
            if side == "LONG":
                stop_loss_price = order.fill_price * (Decimal("1") - stop_pct)
            else:
                stop_loss_price = order.fill_price * (Decimal("1") + stop_pct)
            signal_target = None

        # Compute target price: use signal target, or default 3:1 R:R
        if signal_target is not None:
            target_price = signal_target
        elif order.fill_price is not None:
            stop_dist = abs(order.fill_price - stop_loss_price)
            if side == "LONG":
                target_price = order.fill_price + stop_dist * Decimal("3")
            else:
                target_price = order.fill_price - stop_dist * Decimal("3")
        else:
            target_price = stop_loss_price  # Degenerate fallback

        # Register position with risk manager for tracking
        risk_pos_id: str | None = None
        if self._risk_manager is not None and order.fill_price is not None:
            risk_pos_id = self._risk_manager.register_position(
                symbol=order.symbol,
                campaign_id=order.symbol,
                entry_price=order.fill_price,
                stop_loss=stop_loss_price,
                position_size=Decimal(str(order.quantity)),
                timestamp=bar.timestamp,
                side=side,
            )

        # Store stop/target/position_id for exit checking
        self._position_stops[order.symbol] = (
            stop_loss_price,
            target_price,
            risk_pos_id,
        )

        # Store initial risk distance for trailing stop (never changes)
        if order.fill_price is not None:
            self._position_initial_risk[order.symbol] = abs(order.fill_price - stop_loss_price)

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
        initial_capital = self._config.initial_capital
        final_equity = (
            self._equity_curve[-1].portfolio_value if self._equity_curve else initial_capital
        )

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
                total_pnl=Decimal("0"),
                final_equity=final_equity,
                total_return_pct=Decimal("0"),
                cagr=Decimal("0"),
                sharpe_ratio=Decimal("0"),
            )

        # Calculate basic metrics
        winning = [t for t in trades if t.realized_pnl > 0]
        losing = [t for t in trades if t.realized_pnl < 0]

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

        # Total P&L: sum of realized P&L from all trades
        total_pnl = sum(t.realized_pnl for t in trades)

        # Total return percentage: (final - initial) / initial * 100
        if initial_capital > 0:
            total_return_pct = (final_equity - initial_capital) / initial_capital * Decimal("100")
        else:
            total_return_pct = Decimal("0")

        # CAGR: ((final / initial) ^ (365 / total_days)) - 1
        cagr = Decimal("0")
        if initial_capital > 0 and final_equity > 0 and len(self._equity_curve) >= 2:
            first_ts = self._equity_curve[0].timestamp
            last_ts = self._equity_curve[-1].timestamp
            total_days = (last_ts - first_ts).total_seconds() / 86400.0
            if total_days > 0:
                ratio = float(final_equity) / float(initial_capital)
                exponent = 365.25 / total_days
                cagr = Decimal(str(ratio**exponent - 1.0))

        # Sharpe ratio: (mean(daily_returns) - daily_rf) / std(daily_returns) * sqrt(252)
        sharpe_ratio = Decimal("0")
        if len(self._equity_curve) >= 2:
            daily_returns: list[float] = []
            for i in range(1, len(self._equity_curve)):
                prev_val = float(self._equity_curve[i - 1].portfolio_value)
                curr_val = float(self._equity_curve[i].portfolio_value)
                if prev_val > 0:
                    daily_returns.append((curr_val - prev_val) / prev_val)
            if len(daily_returns) >= 2:
                mean_ret = sum(daily_returns) / len(daily_returns)
                daily_rf = 0.02 / 252  # Annual risk-free rate (2%) / trading days
                variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (
                    len(daily_returns) - 1
                )
                std_ret = math.sqrt(variance)
                if std_ret > 0:
                    sharpe_ratio = Decimal(str((mean_ret - daily_rf) / std_ret * math.sqrt(252)))

        return BacktestMetrics(
            total_signals=len(trades),
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            average_r_multiple=self._calculate_avg_r_multiple(trades),
            max_drawdown=self._calculate_max_drawdown(),
            profit_factor=profit_factor,
            total_pnl=total_pnl,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            cagr=cagr,
            sharpe_ratio=sharpe_ratio,
        )

    def _calculate_avg_r_multiple(self, trades: list) -> Decimal:
        """
        Calculate average R-multiple from completed trades.

        Uses actual stop distance (entry - stop_price) when available,
        falling back to percentage-based risk for trades without stop_price.

        Args:
            trades: List of completed BacktestTrade objects

        Returns:
            Average R-multiple across all trades, Decimal("0") if no trades
        """
        if not trades:
            return Decimal("0")

        # Prefer pre-computed r_multiple on each trade (set at close time)
        r_multiples = [t.r_multiple for t in trades if t.r_multiple != Decimal("0")]

        if not r_multiples:
            return Decimal("0")

        return sum(r_multiples) / Decimal(len(r_multiples))

    @staticmethod
    def _compute_r_multiple(trade) -> None:
        """Compute and set r_multiple on a trade using actual stop distance.

        If stop_price is available, R = pnl_per_share / stop_distance.
        Otherwise leaves r_multiple at its default (0).
        """
        if not isinstance(getattr(trade, "stop_price", None), Decimal):
            return
        stop_distance = abs(trade.entry_price - trade.stop_price)
        if stop_distance <= Decimal("0"):
            return
        if trade.side == "LONG":
            pnl_per_share = trade.exit_price - trade.entry_price
        else:
            pnl_per_share = trade.entry_price - trade.exit_price
        trade.r_multiple = pnl_per_share / stop_distance

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
