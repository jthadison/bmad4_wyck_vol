"""
Backtest Metrics Calculator (Story 12.1 Task 7).

Calculates comprehensive performance metrics from backtest results including:
- Return metrics (total return, CAGR)
- Risk metrics (Sharpe ratio, max drawdown)
- Trade statistics (win rate, profit factor, R-multiple)

Author: Story 12.1 Task 7
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.models.backtest import (
    BacktestMetrics,
    BacktestTrade,
    CampaignPerformance,
    DrawdownPeriod,
    EquityCurvePoint,
    MonthlyReturn,
    RiskMetrics,
)


class MetricsCalculator:
    """Calculate backtest performance metrics.

    Provides comprehensive metrics calculation for backtesting results,
    including return metrics, risk-adjusted metrics, and trade statistics.

    AC10: Calculate all performance metrics:
    - total_return_pct
    - CAGR (annualized)
    - Sharpe ratio
    - max_drawdown
    - max_drawdown_duration_days
    - win_rate
    - avg_r_multiple
    - profit_factor
    - trade counts

    Example:
        # Daily backtest (default)
        calculator = MetricsCalculator(timeframe="1d")
        metrics = calculator.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )

        # Intraday backtest (Story 13.5)
        calculator = MetricsCalculator(timeframe="1h")
        metrics = calculator.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=Decimal("100000"),
        )
    """

    def __init__(self, risk_free_rate: Decimal = Decimal("0.02"), timeframe: str = "1d"):
        """Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default 2% = 0.02)
            timeframe: Data timeframe for annualization (e.g., "1d", "1h", "15m")
        """
        self.risk_free_rate = risk_free_rate
        self.timeframe = timeframe

    def calculate_metrics(
        self,
        equity_curve: list[EquityCurvePoint],
        trades: list[BacktestTrade],
        initial_capital: Decimal,
    ) -> BacktestMetrics:
        """Calculate all performance metrics from backtest results.

        AC10: Calculate comprehensive metrics.

        Args:
            equity_curve: List of equity curve points
            trades: List of completed trades
            initial_capital: Starting capital

        Returns:
            BacktestMetrics with all performance statistics

        Example:
            metrics = calculator.calculate_metrics(
                equity_curve=[point1, point2, ...],
                trades=[trade1, trade2, ...],
                initial_capital=Decimal("100000"),
            )
        """
        if not equity_curve:
            # No equity curve - return empty metrics with trade stats if trades exist
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.realized_pnl > 0]) if trades else 0
            losing_trades = len([t for t in trades if t.realized_pnl < 0]) if trades else 0
            total_pnl = sum(t.realized_pnl for t in trades) if trades else Decimal("0")

            return BacktestMetrics(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=self._calculate_win_rate(winning_trades, total_trades),
                total_pnl=total_pnl,
                total_return_pct=Decimal("0"),
                final_equity=initial_capital,
                max_drawdown=Decimal("0"),
                sharpe_ratio=Decimal("0"),
                cagr=Decimal("0"),
                average_r_multiple=self._calculate_avg_r_multiple(trades)
                if trades
                else Decimal("0"),
                profit_factor=self._calculate_profit_factor(trades) if trades else Decimal("0"),
            )

        # Calculate return metrics
        final_value = equity_curve[-1].portfolio_value
        total_return_pct = self._calculate_total_return_pct(final_value, initial_capital)
        cagr = self._calculate_cagr(
            final_value, initial_capital, equity_curve[0].timestamp, equity_curve[-1].timestamp
        )

        # Calculate risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
        max_drawdown, max_dd_duration = self._calculate_drawdown(equity_curve)

        # Calculate trade statistics
        if not trades:
            # No trades - return metrics with returns/drawdown but no trade stats
            return BacktestMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=Decimal("0"),
                total_pnl=Decimal("0"),
                total_return_pct=total_return_pct,
                final_equity=final_value,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio if sharpe_ratio is not None else Decimal("0"),
                cagr=cagr if cagr is not None else Decimal("0"),
                average_r_multiple=Decimal("0"),
                profit_factor=Decimal("0"),
            )

        # Trade counts
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.realized_pnl > 0])
        losing_trades = len([t for t in trades if t.realized_pnl < 0])

        # Win rate
        win_rate = self._calculate_win_rate(winning_trades, total_trades)

        # Average R-multiple
        avg_r_multiple = self._calculate_avg_r_multiple(trades)

        # Profit factor
        profit_factor = self._calculate_profit_factor(trades)

        # Calculate total P&L
        total_pnl = sum(t.realized_pnl for t in trades)

        # Calculate final equity
        final_equity = final_value

        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            final_equity=final_equity,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio if sharpe_ratio is not None else Decimal("0"),
            cagr=cagr if cagr is not None else Decimal("0"),
            average_r_multiple=avg_r_multiple,
            profit_factor=profit_factor,
        )

    def _calculate_total_return_pct(
        self, final_value: Decimal, initial_capital: Decimal
    ) -> Decimal:
        """Calculate total return percentage.

        AC10 Subtask 7.3: total_return_pct = ((final - initial) / initial) * 100

        Args:
            final_value: Final portfolio value
            initial_capital: Starting capital

        Returns:
            Total return as percentage

        Example:
            $100,000 -> $115,000 = 15% return
        """
        if initial_capital <= 0:
            return Decimal("0")

        return ((final_value - initial_capital) / initial_capital) * Decimal("100")

    def _calculate_cagr(
        self,
        final_value: Decimal,
        initial_capital: Decimal,
        start_date: datetime,
        end_date: datetime,
    ) -> Decimal:
        """Calculate Compound Annual Growth Rate (CAGR).

        AC10 Subtask 7.4: CAGR = ((final / initial) ^ (1 / years)) - 1

        **Compounding Assumptions**:
        - Assumes continuous compounding for total return annualization
        - Formula is mathematically correct for annualizing any holding period return
        - Error magnitude is negligible (< 1%) for realistic scenarios
        - Does not adjust for intraday bar frequencies (1h, 15m, 5m)

        Args:
            final_value: Final portfolio value
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            CAGR as decimal (e.g., 0.15 = 15% annual return)

        Example:
            $100,000 -> $115,000 over 1 year = 15% CAGR
            $100,000 -> $121,000 over 2 years = 10% CAGR

        Note:
            For intraday backtests, CAGR remains accurate because it measures
            total return over total time period, regardless of bar frequency.
        """
        if initial_capital <= 0 or final_value <= 0:
            return Decimal("0")

        # Calculate time period in years
        time_delta = end_date - start_date
        years = Decimal(time_delta.days) / Decimal("365.25")

        if years <= 0:
            return Decimal("0")

        # CAGR = (final / initial) ^ (1 / years) - 1
        # Using float for exponentiation, then convert back to Decimal
        final_float = float(final_value)
        initial_float = float(initial_capital)
        years_float = float(years)

        cagr_float = (final_float / initial_float) ** (1 / years_float) - 1
        return Decimal(str(cagr_float))

    def _get_bars_per_year(self, timeframe: str) -> int:
        """Calculate number of bars per year based on timeframe.

        Story 13.5 C-2 Fix: Dynamic calculation for intraday timeframes.

        **IMPORTANT - Asset Class Assumptions (CR-3)**:
        - Assumes 24/5 trading (forex/crypto market hours)
        - 252 trading days per year baseline
        - For equities with 6.5h/day market hours, bars_per_year would differ
        - Future enhancement needed for asset-class-specific trading hours

        Args:
            timeframe: Timeframe string (e.g., "1d", "1h", "15m", "5m")

        Returns:
            Number of bars per trading year

        Examples:
            "1d" -> 252 (252 trading days)
            "1h" -> 6,048 (252 days * 24 hours, assuming 24/5 forex)
            "15m" -> 24,192 (252 days * 24 hours * 4 quarters)
            "5m" -> 72,576 (252 days * 24 hours * 12 periods)
            "1m" -> 362,880 (252 days * 24 hours * 60 minutes)

        Warning:
            For equity backtests (US30, SPY, etc.), intraday Sharpe ratios
            will be slightly overstated due to 24h assumption vs 6.5h reality.
            Error magnitude: ~3.7x (24/6.5) on annualization factor.
        """
        # Parse timeframe string
        timeframe_lower = timeframe.lower()

        if timeframe_lower == "1d" or timeframe_lower == "daily":
            return 252
        elif timeframe_lower == "1h" or timeframe_lower == "hourly":
            return 252 * 24  # 6,048
        elif timeframe_lower == "4h":
            return 252 * 6  # 1,512 (24/4 = 6 bars per day)
        elif timeframe_lower == "15m":
            return 252 * 24 * 4  # 24,192 (4 fifteen-minute periods per hour)
        elif timeframe_lower == "30m":
            return 252 * 24 * 2  # 12,096 (2 thirty-minute periods per hour)
        elif timeframe_lower == "5m":
            return 252 * 24 * 12  # 72,576 (12 five-minute periods per hour)
        elif timeframe_lower == "1m":
            return 252 * 24 * 60  # 362,880 (60 one-minute periods per hour)
        elif timeframe_lower == "1w" or timeframe_lower == "weekly":
            return 52  # 52 weeks per year
        else:
            # Default to daily if unknown
            return 252

    def _calculate_sharpe_ratio(self, equity_curve: list[EquityCurvePoint]) -> Decimal:
        """Calculate Sharpe ratio with timeframe-aware annualization.

        AC10 Subtask 7.5: Sharpe = (avg_return - risk_free_rate) / std_dev * sqrt(bars_per_year)

        Story 13.5 C-2 Fix: Now uses timeframe-specific annualization factor.

        **IMPORTANT - Asset Class Assumptions (CR-3)**:
        See _get_bars_per_year() docstring for 24/5 forex/crypto assumption details.

        Args:
            equity_curve: List of equity curve points

        Returns:
            Sharpe ratio (annualized)

        Example Usage (Story 13.5):
            # Daily backtest
            calculator = MetricsCalculator(timeframe="1d")
            sharpe = calculator._calculate_sharpe_ratio(equity_curve)

            # Hourly backtest (intraday)
            calculator = MetricsCalculator(timeframe="1h")
            sharpe = calculator._calculate_sharpe_ratio(equity_curve)

        Example (Daily):
            Avg daily return = 0.1%, std dev = 0.5%
            Risk-free rate = 2% annual = 0.008% daily
            Sharpe = (0.1% - 0.008%) / 0.5% * sqrt(252) = 2.92

        Example (Hourly):
            Avg hourly return = 0.004%, std dev = 0.032%
            Risk-free rate = 2% annual = 0.00033% hourly
            Sharpe = (0.004% - 0.00033%) / 0.032% * sqrt(6048) = 2.92
        """
        if len(equity_curve) < 2:
            return Decimal("0")

        # Calculate bar-to-bar returns from equity values
        bar_returns = []
        for i in range(1, len(equity_curve)):
            prev_value = equity_curve[i - 1].equity_value
            curr_value = equity_curve[i].equity_value
            if prev_value > 0:
                bar_return = (curr_value - prev_value) / prev_value
                bar_returns.append(bar_return)

        if len(bar_returns) < 2:
            return Decimal("0")

        # Calculate average bar return
        avg_bar_return = sum(bar_returns, Decimal("0")) / Decimal(len(bar_returns))

        # Calculate standard deviation of bar returns
        # Use Bessel's correction (n-1) for sample variance
        variance = sum((r - avg_bar_return) ** 2 for r in bar_returns) / Decimal(
            len(bar_returns) - 1
        )

        # Convert to float for sqrt calculation
        variance_float = float(variance)
        if variance_float <= 0:
            return Decimal("0")

        std_dev = Decimal(str(variance_float**0.5))

        if std_dev == 0:
            return Decimal("0")

        # Get bars per year for this timeframe (Story 13.5 C-2 Fix)
        bars_per_year = self._get_bars_per_year(self.timeframe)

        # Per-bar risk-free rate (annualized rate / bars per year)
        bar_risk_free = self.risk_free_rate / Decimal(str(bars_per_year))

        # Sharpe ratio (annualized)
        # Sharpe = (avg_bar_return - bar_risk_free) / std_dev * sqrt(bars_per_year)
        sharpe = (avg_bar_return - bar_risk_free) / std_dev * Decimal(str(bars_per_year**0.5))

        return sharpe

    def _calculate_drawdown(self, equity_curve: list[EquityCurvePoint]) -> tuple[Decimal, int]:
        """Calculate maximum drawdown and duration.

        AC10 Subtasks 7.6-7.7: Track peak, calculate max % drop from peak and duration.

        Args:
            equity_curve: List of equity curve points

        Returns:
            Tuple of (max_drawdown_pct, max_duration_days)

        Example:
            Peak: $115,000
            Trough: $103,500
            Drawdown: (115,000 - 103,500) / 115,000 = 10%
            Duration: 45 days from peak to recovery
        """
        if not equity_curve:
            return Decimal("0"), 0

        max_drawdown = Decimal("0")
        max_duration = 0

        peak = equity_curve[0].portfolio_value
        current_duration = 0

        for point in equity_curve:
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

    def _calculate_win_rate(self, winning_trades: int, total_trades: int) -> Decimal:
        """Calculate win rate.

        AC10 Subtask 7.8: win_rate = winning_trades / total_trades

        Args:
            winning_trades: Number of winning trades
            total_trades: Total number of trades

        Returns:
            Win rate as decimal (e.g., 0.60 = 60% win rate)

        Example:
            60 wins out of 100 trades = 0.60 (60%)
        """
        if total_trades == 0:
            return Decimal("0")

        return Decimal(winning_trades) / Decimal(total_trades)

    def _calculate_avg_r_multiple(self, trades: list[BacktestTrade]) -> Decimal:
        """Calculate average R-multiple.

        AC10 Subtask 7.9: avg_r_multiple = sum(r_multiple) / total_trades

        Args:
            trades: List of trades

        Returns:
            Average R-multiple

        Example:
            R-multiples: [2.0, -1.0, 3.0, -0.5]
            Average: (2.0 - 1.0 + 3.0 - 0.5) / 4 = 0.875
        """
        if not trades:
            return Decimal("0")

        # Filter trades with r_multiple set
        trades_with_r = [t for t in trades if t.r_multiple is not None]
        if not trades_with_r:
            return Decimal("0")

        total_r = sum(t.r_multiple for t in trades_with_r)
        return total_r / Decimal(len(trades_with_r))

    def _calculate_profit_factor(self, trades: list[BacktestTrade]) -> Decimal:
        """Calculate profit factor.

        AC10 Subtask 7.10: profit_factor = sum(winning_pnl) / abs(sum(losing_pnl))

        Args:
            trades: List of trades

        Returns:
            Profit factor (e.g., 2.5 means $2.50 won per $1.00 lost)

        Example:
            Total wins: $15,000
            Total losses: $6,000
            Profit factor: 15,000 / 6,000 = 2.5
        """
        total_wins = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        total_losses = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))

        if total_losses == 0:
            if total_wins > 0:
                return Decimal("999.99")
            return Decimal("0")

        return total_wins / total_losses

    # ===========================================================================================
    # Enhanced Metrics Methods (Story 12.6A IMPL-004)
    # ===========================================================================================

    def calculate_monthly_returns(
        self, equity_curve: list[EquityCurvePoint], trades: list[BacktestTrade]
    ) -> list[MonthlyReturn]:
        """Calculate monthly return data for heatmap visualization (Story 12.6A AC2).

        Groups equity curve points by year-month and calculates monthly return percentages.

        Args:
            equity_curve: List of equity curve points
            trades: List of backtest trades for trade counting

        Returns:
            List of MonthlyReturn objects, one per month with trading activity

        Example:
            Jan 2024: $100,000 -> $105,000 = 5% return (3 trades, 2 wins, 1 loss)
            Feb 2024: $105,000 -> $103,000 = -1.9% return (1 trade, 0 wins, 1 loss)
        """
        if not equity_curve:
            return []

        # Group equity points by year-month
        monthly_data: dict[tuple[int, int], list[EquityCurvePoint]] = {}
        for point in equity_curve:
            year_month = (point.timestamp.year, point.timestamp.month)
            if year_month not in monthly_data:
                monthly_data[year_month] = []
            monthly_data[year_month].append(point)

        # Group trades by exit month
        monthly_trades: dict[tuple[int, int], list[BacktestTrade]] = {}
        for trade in trades:
            year_month = (trade.exit_timestamp.year, trade.exit_timestamp.month)
            if year_month not in monthly_trades:
                monthly_trades[year_month] = []
            monthly_trades[year_month].append(trade)

        # Calculate monthly returns
        monthly_returns: list[MonthlyReturn] = []

        # Month name labels
        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        for (year, month), points in sorted(monthly_data.items()):
            if len(points) < 2:
                continue  # Need at least 2 points to calculate return

            # Get first and last equity values for the month
            start_equity = points[0].equity_value
            end_equity = points[-1].equity_value

            # Calculate return percentage
            if start_equity > 0:
                return_pct = (
                    ((end_equity - start_equity) / start_equity) * Decimal("100")
                ).quantize(Decimal("0.0001"))
            else:
                return_pct = Decimal("0")

            # Get trade stats for this month
            month_trades = monthly_trades.get((year, month), [])
            trade_count = len(month_trades)
            winning_trades = len([t for t in month_trades if t.realized_pnl > 0])
            losing_trades = len([t for t in month_trades if t.realized_pnl <= 0])

            # Create month label
            month_label = f"{month_names[month-1]} {year}"

            monthly_return = MonthlyReturn(
                year=year,
                month=month,
                month_label=month_label,
                return_pct=return_pct,
                trade_count=trade_count,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
            )
            monthly_returns.append(monthly_return)

        return monthly_returns

    def calculate_drawdown_periods(
        self, equity_curve: list[EquityCurvePoint], top_n: int = 5
    ) -> list[DrawdownPeriod]:
        """Calculate top N drawdown periods (Story 12.6A AC3).

        Tracks equity peaks, troughs, and recovery points to identify significant
        drawdown events.

        Args:
            equity_curve: List of equity curve points
            top_n: Number of top drawdown periods to return (default 5)

        Returns:
            List of DrawdownPeriod objects sorted by drawdown magnitude (largest first)

        Example:
            Peak: $115,000 on 2024-03-01
            Trough: $103,500 on 2024-03-15 (-10%)
            Recovery: $115,500 on 2024-04-10 (26 days to recover)
        """
        if len(equity_curve) < 2:
            return []

        drawdown_periods: list[DrawdownPeriod] = []
        peak_value = equity_curve[0].portfolio_value
        peak_date = equity_curve[0].timestamp
        trough_value = peak_value
        trough_date = peak_date
        in_drawdown = False

        for i, point in enumerate(equity_curve[1:], start=1):
            current_value = point.portfolio_value
            current_date = point.timestamp

            if current_value >= peak_value:
                # End of drawdown period (if we were in one)
                if in_drawdown and trough_value < peak_value:
                    drawdown_pct = ((trough_value - peak_value) / peak_value) * Decimal("100")
                    duration_days = (trough_date - peak_date).days
                    recovery_duration_days = (current_date - trough_date).days

                    drawdown_period = DrawdownPeriod(
                        peak_date=peak_date,
                        trough_date=trough_date,
                        recovery_date=current_date,
                        peak_value=peak_value.quantize(Decimal("0.01")),
                        trough_value=trough_value.quantize(Decimal("0.01")),
                        recovery_value=current_value.quantize(Decimal("0.01")),
                        drawdown_pct=drawdown_pct.quantize(Decimal("0.0001")),
                        duration_days=duration_days,
                        recovery_duration_days=recovery_duration_days,
                    )
                    drawdown_periods.append(drawdown_period)

                # New peak
                peak_value = current_value
                peak_date = current_date
                trough_value = current_value
                trough_date = current_date
                in_drawdown = False
            else:
                # In drawdown
                in_drawdown = True
                if current_value < trough_value:
                    trough_value = current_value
                    trough_date = current_date

        # Handle ongoing drawdown at end of period
        if in_drawdown and trough_value < peak_value:
            drawdown_pct = ((trough_value - peak_value) / peak_value) * Decimal("100")
            duration_days = (trough_date - peak_date).days

            drawdown_period = DrawdownPeriod(
                peak_date=peak_date,
                trough_date=trough_date,
                recovery_date=None,  # Not yet recovered
                peak_value=peak_value.quantize(Decimal("0.01")),
                trough_value=trough_value.quantize(Decimal("0.01")),
                recovery_value=None,
                drawdown_pct=drawdown_pct.quantize(Decimal("0.0001")),
                duration_days=duration_days,
                recovery_duration_days=None,
            )
            drawdown_periods.append(drawdown_period)

        # Sort by drawdown magnitude (largest first) and return top N
        # Since drawdown_pct is negative, sort ascending to get most negative first
        drawdown_periods.sort(key=lambda d: d.drawdown_pct)
        return drawdown_periods[:top_n]

    def calculate_risk_metrics(
        self,
        equity_curve: list[EquityCurvePoint],
        trades: list[BacktestTrade],
        initial_capital: Decimal,
    ) -> RiskMetrics:
        """Calculate portfolio heat and capital deployment metrics (Story 12.6A AC4).

        Analyzes concurrent positions, portfolio heat (capital at risk), and
        capital deployment over time.

        Args:
            equity_curve: List of equity curve points
            trades: List of completed trades
            initial_capital: Starting capital

        Returns:
            RiskMetrics with portfolio heat and deployment statistics

        Example:
            Max concurrent positions: 3
            Max portfolio heat: 6% (3 positions × 2% risk each)
            Avg capital deployed: 28.5%
            Exposure time: 75% (3 months out of 4 with open positions)
        """
        if not equity_curve or not trades:
            return RiskMetrics(
                max_concurrent_positions=0,
                avg_concurrent_positions=Decimal("0"),
                max_portfolio_heat=Decimal("0"),
                avg_portfolio_heat=Decimal("0"),
                max_position_size_pct=Decimal("0"),
                avg_position_size_pct=Decimal("0"),
                max_capital_deployed_pct=Decimal("0"),
                avg_capital_deployed_pct=Decimal("0"),
                total_exposure_days=0,
                exposure_time_pct=Decimal("0"),
            )

        # Calculate backtest duration in days
        start_date = equity_curve[0].timestamp
        end_date = equity_curve[-1].timestamp
        total_days = max((end_date - start_date).days, 1)

        # Track concurrent positions over time
        position_counts: list[int] = []
        capital_deployed: list[Decimal] = []
        position_sizes: list[Decimal] = []
        days_with_positions = 0

        for point in equity_curve:
            # Count how many trades were open at this timestamp
            concurrent = 0
            deployed = Decimal("0")

            for trade in trades:
                if (
                    trade.entry_timestamp
                    <= point.timestamp
                    <= (trade.exit_timestamp or point.timestamp)
                ):
                    concurrent += 1
                    # Calculate position value and size
                    position_value = trade.entry_price * Decimal(str(trade.quantity))
                    deployed += position_value
                    # Position size as % of portfolio at entry
                    size_pct = (position_value / point.portfolio_value) * Decimal("100")
                    position_sizes.append(size_pct)

            position_counts.append(concurrent)
            capital_deployed.append(deployed)
            if concurrent > 0:
                days_with_positions += 1

        # Calculate statistics
        max_concurrent = max(position_counts) if position_counts else 0
        avg_concurrent_raw = (
            Decimal(str(sum(position_counts))) / Decimal(len(position_counts))
            if position_counts
            else Decimal("0")
        )
        # Round to 2 decimal places for avg_concurrent_positions field
        avg_concurrent = avg_concurrent_raw.quantize(Decimal("0.01"))

        # Calculate capital deployment percentages
        current_capital = initial_capital
        deployed_pcts: list[Decimal] = []
        for i, point in enumerate(equity_curve):
            current_capital = point.portfolio_value
            if current_capital > 0:
                deployed_pct = (capital_deployed[i] / current_capital) * Decimal("100")
                deployed_pcts.append(deployed_pct)

        max_deployed_pct_raw = max(deployed_pcts) if deployed_pcts else Decimal("0")
        avg_deployed_pct_raw = (
            sum(deployed_pcts, Decimal("0")) / Decimal(len(deployed_pcts))
            if deployed_pcts
            else Decimal("0")
        )
        # Round to 4 decimal places for percentage fields
        max_deployed_pct = max_deployed_pct_raw.quantize(Decimal("0.0001"))
        avg_deployed_pct = avg_deployed_pct_raw.quantize(Decimal("0.0001"))

        # Calculate position size statistics
        max_position_size_raw = max(position_sizes) if position_sizes else Decimal("0")
        avg_position_size_raw = (
            sum(position_sizes, Decimal("0")) / Decimal(len(position_sizes))
            if position_sizes
            else Decimal("0")
        )
        # Round to 4 decimal places for percentage fields
        max_position_size = max_position_size_raw.quantize(Decimal("0.0001"))
        avg_position_size = avg_position_size_raw.quantize(Decimal("0.0001"))

        # Estimate portfolio heat (assume 2% risk per position as default)
        # In real implementation, this would come from position sizing
        assumed_risk_per_position = Decimal("2")  # 2% per position
        max_heat_raw = Decimal(str(max_concurrent)) * assumed_risk_per_position
        avg_heat_raw = avg_concurrent * assumed_risk_per_position
        # Round to 4 decimal places for percentage fields
        max_heat = max_heat_raw.quantize(Decimal("0.0001"))
        avg_heat = avg_heat_raw.quantize(Decimal("0.0001"))

        # Exposure time percentage (cap at 100%)
        exposure_pct = (Decimal(str(days_with_positions)) / Decimal(str(total_days))) * Decimal(
            "100"
        )
        exposure_pct = min(exposure_pct, Decimal("100")).quantize(
            Decimal("0.01")
        )  # Cap at 100% and round to 2 decimal places

        return RiskMetrics(
            max_concurrent_positions=max_concurrent,
            avg_concurrent_positions=avg_concurrent,
            max_portfolio_heat=max_heat,
            avg_portfolio_heat=avg_heat,
            max_position_size_pct=max_position_size,
            avg_position_size_pct=avg_position_size,
            max_capital_deployed_pct=max_deployed_pct,
            avg_capital_deployed_pct=avg_deployed_pct,
            total_exposure_days=days_with_positions,
            exposure_time_pct=exposure_pct,
        )

    def calculate_campaign_performance(
        self, trades: list[BacktestTrade], timeframe: str = "1d"
    ) -> list[CampaignPerformance]:
        """Calculate Wyckoff campaign lifecycle tracking (Story 12.6A AC5 - CRITICAL).

        Tracks Wyckoff campaign lifecycles and aggregates trades within campaigns.

        Uses WyckoffCampaignDetector to identify campaigns from completed trades,
        validate pattern sequences, and track phase progression.

        Args:
            trades: List of completed trades
            timeframe: Chart timeframe (e.g., "1d", "1h", "15m") - currently unused

        Returns:
            List of CampaignPerformance objects

        Example (Future Implementation):
            Campaign 1: ACCUMULATION -> MARKUP (3 trades, +15% return, COMPLETED)
            Campaign 2: DISTRIBUTION -> MARKDOWN (2 trades, -5% return, FAILED)
        """

        from src.backtesting.campaign_detector import WyckoffCampaignDetector

        if not trades:
            return []

        # Use WyckoffCampaignDetector for batch campaign detection from trades
        detector = WyckoffCampaignDetector()
        campaigns = detector.detect_campaigns(trades)

        return campaigns

    def _create_campaign_from_trades(
        self, trades: list[BacktestTrade], pattern_to_phase_map: dict[str, str]
    ) -> CampaignPerformance:
        """Create a CampaignPerformance object from a group of trades.

        Args:
            trades: List of trades in this campaign
            pattern_to_phase_map: Mapping from pattern types to Wyckoff phases

        Returns:
            CampaignPerformance object with aggregated campaign data
        """
        from uuid import uuid4

        # Get campaign metadata
        first_trade = trades[0]
        last_trade = trades[-1]

        symbol = first_trade.symbol
        start_date = first_trade.entry_timestamp
        end_date = last_trade.exit_timestamp if last_trade.exit_timestamp else None

        # Determine detected phase from first pattern
        detected_phase = pattern_to_phase_map.get(
            first_trade.pattern_type.upper() if first_trade.pattern_type else "", "UNKNOWN"
        )

        # Collect all phases observed
        phases_observed = []
        for trade in trades:
            if trade.pattern_type:
                phase = pattern_to_phase_map.get(trade.pattern_type.upper(), "UNKNOWN")
                if phase not in phases_observed:
                    phases_observed.append(phase)

        # Calculate campaign P&L
        total_pnl = sum(t.realized_pnl for t in trades)
        trades_count = len(trades)

        # Determine campaign status
        if end_date is None:
            status = "IN_PROGRESS"
            completion_reason = None
        elif total_pnl >= Decimal("0"):
            status = "COMPLETED"
            completion_reason = "PROFITABLE_EXIT"
        else:
            status = "FAILED"
            completion_reason = "LOSS_REALIZED"

        # Calculate campaign return percentage
        first_trade_value = first_trade.entry_price * Decimal(str(first_trade.quantity))
        if first_trade_value > 0:
            campaign_return_pct = (total_pnl / first_trade_value) * Decimal("100")
        else:
            campaign_return_pct = Decimal("0")

        return CampaignPerformance(
            campaign_id=uuid4(),
            symbol=symbol,
            detected_phase=detected_phase,
            start_date=start_date,
            end_date=end_date,
            status=status,
            completion_reason=completion_reason,
            trades_count=trades_count,
            total_pnl=total_pnl,
            campaign_return_pct=campaign_return_pct,
            phases_observed=phases_observed,
        )


# Legacy function-based API for backward compatibility
# (Used by src/backtesting/engine.py from Story 11.2)


def calculate_metrics(trades: list[dict[str, Any]], initial_capital: Decimal) -> BacktestMetrics:
    """
    Calculate performance metrics from trade results (legacy function).

    DEPRECATED: Use MetricsCalculator class instead for Story 12.1+.
    This function is kept for backward compatibility with Story 11.2 code.

    Args:
        trades: List of trade dictionaries with keys:
            - entry_price: Entry price
            - exit_price: Exit price
            - position_size: Number of shares/contracts
            - direction: "long" or "short"
            - r_multiple: R-multiple of trade (profit/initial_risk)
        initial_capital: Starting capital for the backtest

    Returns:
        BacktestMetrics with all calculated metrics
    """
    if not trades:
        return BacktestMetrics(
            total_signals=0,
            win_rate=Decimal("0.0"),
            average_r_multiple=Decimal("0.0"),
            profit_factor=Decimal("0.0"),
            max_drawdown=Decimal("0.0"),
        )

    total_signals = len(trades)
    winning_trades = [t for t in trades if Decimal(str(t.get("r_multiple", 0))) > 0]
    win_rate = Decimal(str(len(winning_trades))) / Decimal(str(total_signals))

    # Calculate average R-multiple
    r_multiples = [Decimal(str(t.get("r_multiple", 0))) for t in trades]
    average_r_multiple = sum(r_multiples, Decimal("0.0")) / Decimal(str(total_signals))

    # Calculate profit factor (total wins / total losses)
    total_wins = sum(
        (Decimal(str(t.get("profit", 0))) for t in trades if Decimal(str(t.get("profit", 0))) > 0),
        Decimal("0.0"),
    )
    total_losses = abs(
        sum(
            (
                Decimal(str(t.get("profit", 0)))
                for t in trades
                if Decimal(str(t.get("profit", 0))) < 0
            ),
            Decimal("0.0"),
        )
    )

    if total_losses == Decimal("0.0"):
        profit_factor = Decimal("999.99") if total_wins > 0 else Decimal("0.0")
    else:
        profit_factor = total_wins / total_losses

    # Calculate maximum drawdown
    equity_values = [initial_capital]
    running_equity = initial_capital

    for trade in trades:
        profit = Decimal(str(trade.get("profit", 0)))
        running_equity += profit
        equity_values.append(running_equity)

    max_drawdown = calculate_max_drawdown(equity_values)

    return BacktestMetrics(
        total_signals=total_signals,
        win_rate=win_rate,
        average_r_multiple=average_r_multiple,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
    )


def calculate_max_drawdown(equity_values: list[Decimal]) -> Decimal:
    """
    Calculate maximum drawdown from equity curve (legacy function).

    DEPRECATED: Use MetricsCalculator._calculate_drawdown() instead.

    Args:
        equity_values: List of equity values over time

    Returns:
        Maximum drawdown as decimal (0.0-1.0)
    """
    if not equity_values or len(equity_values) < 2:
        return Decimal("0.0")

    max_dd = Decimal("0.0")
    peak = equity_values[0]

    for value in equity_values:
        if value > peak:
            peak = value
        if peak > Decimal("0.0"):
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown

    return max_dd


def calculate_equity_curve(
    trades: list[dict[str, Any]], initial_capital: Decimal
) -> list[EquityCurvePoint]:
    """
    Generate equity curve time series from trade results (legacy function).

    DEPRECATED: Equity curve is now generated by BacktestEngine.
    This function is kept for backward compatibility.

    Args:
        trades: List of trade dictionaries with keys:
            - exit_timestamp: Timestamp when trade was closed
            - profit: Profit/loss of the trade
        initial_capital: Starting capital

    Returns:
        List of EquityCurvePoint representing equity over time
    """
    from datetime import datetime

    # If no trades, return a single point at current time with initial capital
    if not trades:
        return [
            EquityCurvePoint(
                timestamp=datetime.now(UTC),
                equity_value=initial_capital,
                portfolio_value=initial_capital,
                cash=initial_capital,
                positions_value=Decimal("0"),
            )
        ]

    equity_curve = [
        EquityCurvePoint(
            timestamp=trades[0]["entry_timestamp"],
            equity_value=initial_capital,
            portfolio_value=initial_capital,
            cash=initial_capital,
            positions_value=Decimal("0"),
        )
    ]

    running_equity = initial_capital

    for trade in trades:
        profit = Decimal(str(trade.get("profit", 0)))
        running_equity += profit

        equity_curve.append(
            EquityCurvePoint(
                timestamp=trade["exit_timestamp"],
                equity_value=running_equity,
                portfolio_value=running_equity,
                cash=running_equity,  # Simplified: assume all cash after trade exit
                positions_value=Decimal("0"),
            )
        )

    return equity_curve
