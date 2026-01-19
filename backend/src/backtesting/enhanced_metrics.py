"""
Enhanced Metrics Calculator (Story 12.6A Task 2).

Calculates advanced performance metrics including:
- Pattern-level performance analysis
- Monthly return breakdowns
- Drawdown period tracking
- Portfolio risk metrics
- Wyckoff campaign performance

Author: Story 12.6A Task 2
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.models.backtest import (
    BacktestPosition,
    BacktestTrade,
    CampaignPerformance,
    DrawdownPeriod,
    EquityCurvePoint,
    MonthlyReturn,
    PatternPerformance,
    RiskMetrics,
)


class EnhancedMetricsCalculator:
    """Calculate enhanced backtest metrics for Story 12.6A.

    Provides advanced metrics calculation beyond basic performance stats,
    including pattern analysis, temporal breakdowns, risk tracking, and
    Wyckoff campaign lifecycle analysis.

    Example:
        calculator = EnhancedMetricsCalculator()
        pattern_perf = calculator.calculate_pattern_performance(trades)
        monthly_returns = calculator.calculate_monthly_returns(equity_curve, trades)
        drawdowns = calculator.calculate_drawdown_periods(equity_curve)
        risk = calculator.calculate_risk_metrics(position_snapshots, initial_capital)
    """

    def calculate_pattern_performance(
        self, trades: list[BacktestTrade]
    ) -> list[PatternPerformance]:
        """Calculate per-pattern performance statistics.

        Args:
            trades: List of completed trades with pattern_type field

        Returns:
            List of PatternPerformance metrics, one per unique pattern type

        Example:
            trades = [trade1_spring, trade2_spring, trade3_sos, ...]
            pattern_perf = calculator.calculate_pattern_performance(trades)
            # Returns: [PatternPerformance(pattern_type="SPRING", ...),
            #           PatternPerformance(pattern_type="SOS", ...)]
        """
        if not trades:
            return []

        # Group trades by pattern type
        pattern_groups: dict[str, list[BacktestTrade]] = defaultdict(list)
        for trade in trades:
            if trade.pattern_type:
                pattern_groups[trade.pattern_type].append(trade)

        results = []
        for pattern_type, pattern_trades in pattern_groups.items():
            # Calculate statistics for this pattern
            total_trades = len(pattern_trades)
            winning_trades = len([t for t in pattern_trades if t.realized_pnl > 0])
            losing_trades = len([t for t in pattern_trades if t.realized_pnl <= 0])

            win_rate = (
                (Decimal(str(winning_trades)) / Decimal(str(total_trades))).quantize(
                    Decimal("0.0001")
                )
                if total_trades > 0
                else Decimal("0")
            )

            # Average R-multiple
            r_multiples = [t.r_multiple for t in pattern_trades]
            avg_r = (
                (sum(r_multiples, Decimal("0")) / Decimal(str(len(r_multiples)))).quantize(
                    Decimal("0.0001")
                )
                if r_multiples
                else Decimal("0")
            )

            # Profit factor
            total_wins = sum(
                (t.realized_pnl for t in pattern_trades if t.realized_pnl > 0), Decimal("0")
            )
            total_losses = abs(
                sum((t.realized_pnl for t in pattern_trades if t.realized_pnl < 0), Decimal("0"))
            )
            profit_factor = (
                (total_wins / total_losses).quantize(Decimal("0.0001"))
                if total_losses > 0
                else Decimal("0")
            )

            # Total P&L
            total_pnl = sum((t.realized_pnl for t in pattern_trades), Decimal("0"))

            # Trade duration
            durations = [
                (t.exit_timestamp - t.entry_timestamp).total_seconds() / 3600
                for t in pattern_trades
            ]
            avg_duration = (
                Decimal(str(sum(durations) / len(durations))) if durations else Decimal("0")
            )

            # Best/worst trades (by P&L, not R-multiple)
            pnls = [t.realized_pnl for t in pattern_trades]
            best_pnl = max(pnls) if pnls else Decimal("0")
            worst_pnl = min(pnls) if pnls else Decimal("0")

            results.append(
                PatternPerformance(
                    pattern_type=pattern_type,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    win_rate=win_rate,
                    avg_r_multiple=avg_r,
                    profit_factor=profit_factor,
                    total_pnl=total_pnl,
                    avg_trade_duration_hours=avg_duration,
                    best_trade_pnl=best_pnl,
                    worst_trade_pnl=worst_pnl,
                )
            )

        return sorted(results, key=lambda x: x.total_trades, reverse=True)

    def calculate_monthly_returns(
        self, equity_curve: list[EquityCurvePoint], trades: list[BacktestTrade]
    ) -> list[MonthlyReturn]:
        """Calculate monthly return breakdown for heatmap visualization.

        Args:
            equity_curve: Portfolio value time series
            trades: Completed trades for trade count per month

        Returns:
            List of MonthlyReturn objects, one per calendar month

        Example:
            monthly = calculator.calculate_monthly_returns(equity_curve, trades)
            # Returns: [MonthlyReturn(year=2023, month=1, return_pct=12.5, ...), ...]
        """
        if not equity_curve:
            return []

        # Group equity points by month
        monthly_values: dict[tuple[int, int], list[EquityCurvePoint]] = defaultdict(list)
        for point in equity_curve:
            key = (point.timestamp.year, point.timestamp.month)
            monthly_values[key].append(point)

        # Group trades by exit month
        monthly_trades: dict[tuple[int, int], list[BacktestTrade]] = defaultdict(list)
        for trade in trades:
            key = (trade.exit_timestamp.year, trade.exit_timestamp.month)
            monthly_trades[key].append(trade)

        results = []
        for (year, month), points in sorted(monthly_values.items()):
            if len(points) < 2:
                continue  # Need at least 2 points to calculate return

            # Calculate monthly return
            month_start_value = points[0].portfolio_value
            month_end_value = points[-1].portfolio_value

            if month_start_value > 0:
                return_pct = (
                    ((month_end_value - month_start_value) / month_start_value) * Decimal("100")
                ).quantize(Decimal("0.0001"))
            else:
                return_pct = Decimal("0")

            # Get trade stats for this month
            month_trades = monthly_trades.get((year, month), [])
            trade_count = len(month_trades)
            winning = len([t for t in month_trades if t.realized_pnl > 0])
            losing = len([t for t in month_trades if t.realized_pnl <= 0])

            # Month label
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
            month_label = f"{month_names[month-1]} {year}"

            results.append(
                MonthlyReturn(
                    year=year,
                    month=month,
                    month_label=month_label,
                    return_pct=return_pct,
                    trade_count=trade_count,
                    winning_trades=winning,
                    losing_trades=losing,
                )
            )

        return results

    def calculate_drawdown_periods(
        self, equity_curve: list[EquityCurvePoint]
    ) -> list[DrawdownPeriod]:
        """Identify and track individual drawdown events.

        Args:
            equity_curve: Portfolio value time series

        Returns:
            List of DrawdownPeriod objects for each drawdown event

        Example:
            drawdowns = calculator.calculate_drawdown_periods(equity_curve)
            # Returns: [DrawdownPeriod(peak_value=115000, trough_value=103500, ...), ...]
        """
        if len(equity_curve) < 2:
            return []

        drawdowns = []
        peak_value = equity_curve[0].portfolio_value
        peak_date = equity_curve[0].timestamp
        in_drawdown = False
        trough_value = peak_value
        trough_date = peak_date

        for point in equity_curve[1:]:
            if point.portfolio_value > peak_value:
                # New high - end any active drawdown
                if in_drawdown:
                    # Calculate drawdown percentage
                    dd_pct = (((peak_value - trough_value) / peak_value) * Decimal("100")).quantize(
                        Decimal("0.0001")
                    )
                    duration = (trough_date - peak_date).days
                    recovery_duration = (point.timestamp - trough_date).days

                    drawdowns.append(
                        DrawdownPeriod(
                            peak_date=peak_date,
                            trough_date=trough_date,
                            recovery_date=point.timestamp,
                            peak_value=peak_value,
                            trough_value=trough_value,
                            drawdown_pct=dd_pct,
                            duration_days=duration,
                            recovery_duration_days=recovery_duration,
                        )
                    )
                    in_drawdown = False

                # Set new peak
                peak_value = point.portfolio_value
                peak_date = point.timestamp
                trough_value = peak_value
                trough_date = peak_date

            elif point.portfolio_value < trough_value:
                # Deeper into drawdown
                in_drawdown = True
                trough_value = point.portfolio_value
                trough_date = point.timestamp

        # Handle uncovered drawdown at end
        if in_drawdown and trough_value < peak_value:
            dd_pct = (((peak_value - trough_value) / peak_value) * Decimal("100")).quantize(
                Decimal("0.0001")
            )
            duration = (trough_date - peak_date).days

            drawdowns.append(
                DrawdownPeriod(
                    peak_date=peak_date,
                    trough_date=trough_date,
                    recovery_date=None,  # Not yet recovered
                    peak_value=peak_value,
                    trough_value=trough_value,
                    drawdown_pct=dd_pct,
                    duration_days=duration,
                    recovery_duration_days=None,
                )
            )

        return sorted(drawdowns, key=lambda x: x.drawdown_pct, reverse=True)

    def calculate_risk_metrics(
        self,
        position_snapshots: list[tuple[datetime, list[BacktestPosition]]],
        initial_capital: Decimal,
    ) -> Optional[RiskMetrics]:
        """Calculate portfolio risk statistics.

        Args:
            position_snapshots: List of (timestamp, open_positions) tuples
            initial_capital: Starting capital for percentage calculations

        Returns:
            RiskMetrics with portfolio risk statistics

        Example:
            snapshots = [(datetime1, [pos1, pos2]), (datetime2, [pos3]), ...]
            risk = calculator.calculate_risk_metrics(snapshots, Decimal("100000"))
        """
        if not position_snapshots or initial_capital <= 0:
            return None

        concurrent_counts = []
        portfolio_heats = []
        position_sizes = []
        capital_deployed = []

        for timestamp, positions in position_snapshots:
            # Concurrent positions
            concurrent_counts.append(len(positions))

            # Portfolio heat (total risk as % of capital)
            # Simplified: assume 2% risk per position (would need stop loss data for exact)
            total_heat = Decimal(str(len(positions))) * Decimal("2.0")  # 2% per position
            portfolio_heats.append(total_heat)

            # Position sizes and capital deployment
            for pos in positions:
                position_value = pos.quantity * pos.current_price
                size_pct = (position_value / initial_capital) * Decimal("100")
                position_sizes.append(size_pct)

            # Total capital deployed
            total_deployed = sum(
                (pos.quantity * pos.current_price for pos in positions), Decimal("0")
            )
            deployed_pct = (total_deployed / initial_capital) * Decimal("100")
            capital_deployed.append(deployed_pct)

        # Calculate statistics
        max_concurrent = max(concurrent_counts) if concurrent_counts else 0
        avg_concurrent = (
            Decimal(str(sum(concurrent_counts) / len(concurrent_counts)))
            if concurrent_counts
            else Decimal("0")
        )

        max_heat = max(portfolio_heats) if portfolio_heats else Decimal("0")
        avg_heat = (
            sum(portfolio_heats, Decimal("0")) / Decimal(str(len(portfolio_heats)))
            if portfolio_heats
            else Decimal("0")
        )

        max_pos_size = max(position_sizes) if position_sizes else Decimal("0")
        avg_pos_size = (
            sum(position_sizes, Decimal("0")) / Decimal(str(len(position_sizes)))
            if position_sizes
            else Decimal("0")
        )

        max_deployed = max(capital_deployed) if capital_deployed else Decimal("0")
        avg_deployed = (
            sum(capital_deployed, Decimal("0")) / Decimal(str(len(capital_deployed)))
            if capital_deployed
            else Decimal("0")
        )

        return RiskMetrics(
            max_concurrent_positions=max_concurrent,
            avg_concurrent_positions=avg_concurrent,
            max_portfolio_heat=max_heat,
            avg_portfolio_heat=avg_heat,
            max_position_size_pct=max_pos_size,
            avg_position_size_pct=avg_pos_size,
            max_capital_deployed_pct=max_deployed,
            avg_capital_deployed_pct=avg_deployed,
        )

    def calculate_campaign_performance(
        self,
        trades: list[BacktestTrade],
        timeframe: str = "1d",
    ) -> list[CampaignPerformance]:
        """Calculate Wyckoff campaign lifecycle performance (CRITICAL).

        Uses WyckoffCampaignDetector (or IntradayCampaignDetector for ≤1h timeframes)
        to identify campaigns, validate pattern sequences, track phase progression,
        and calculate campaign-level metrics.

        This method provides the critical business insight that individual pattern
        statistics cannot: complete campaign lifecycle analysis from PS→JUMP
        (Accumulation) or PSY→DECLINE (Distribution).

        Uses WyckoffCampaignDetector to identify campaigns from completed trades.

        Args:
            trades: Completed trades with pattern metadata
            timeframe: Chart timeframe (e.g., "1d", "1h", "15m") - currently unused

        Returns:
            List of CampaignPerformance objects

        Example:
            calculator = EnhancedMetricsCalculator()
            campaigns = calculator.calculate_campaign_performance(trades)
            for campaign in campaigns:
                print(f"{campaign.symbol}: {campaign.status} - {campaign.total_pnl}")
        """
        from src.backtesting.campaign_detector import WyckoffCampaignDetector

        # Use WyckoffCampaignDetector for batch campaign detection from trades
        detector = WyckoffCampaignDetector()
        campaigns = detector.detect_campaigns(trades)

        return campaigns

    def calculate_trade_streaks(self, trades: list[BacktestTrade]) -> tuple[int, int]:
        """Calculate longest winning and losing streaks.

        Args:
            trades: List of completed trades sorted chronologically

        Returns:
            Tuple of (longest_winning_streak, longest_losing_streak)

        Example:
            streaks = calculator.calculate_trade_streaks(trades)
            # Returns: (5, 3) - longest win streak 5, longest lose streak 3
        """
        if not trades:
            return (0, 0)

        # Sort by exit timestamp to ensure chronological order
        sorted_trades = sorted(trades, key=lambda t: t.exit_timestamp)

        longest_win_streak = 0
        longest_lose_streak = 0
        current_win_streak = 0
        current_lose_streak = 0

        for trade in sorted_trades:
            if trade.realized_pnl > 0:
                # Winning trade
                current_win_streak += 1
                current_lose_streak = 0
                longest_win_streak = max(longest_win_streak, current_win_streak)
            else:
                # Losing or break-even trade
                current_lose_streak += 1
                current_win_streak = 0
                longest_lose_streak = max(longest_lose_streak, current_lose_streak)

        return (longest_win_streak, longest_lose_streak)

    def identify_extreme_trades(
        self, trades: list[BacktestTrade]
    ) -> tuple[Optional[BacktestTrade], Optional[BacktestTrade]]:
        """Identify largest winner and loser by P&L.

        Args:
            trades: List of completed trades

        Returns:
            Tuple of (largest_winner, largest_loser)

        Example:
            winner, loser = calculator.identify_extreme_trades(trades)
            # winner.realized_pnl = Decimal("5000.00")
            # loser.realized_pnl = Decimal("-2500.00")
        """
        if not trades:
            return (None, None)

        # Find trade with max P&L (largest winner)
        largest_winner = max(trades, key=lambda t: t.realized_pnl)

        # Find trade with min P&L (largest loser)
        largest_loser = min(trades, key=lambda t: t.realized_pnl)

        return (largest_winner, largest_loser)
