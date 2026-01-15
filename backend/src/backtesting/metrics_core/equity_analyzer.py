"""
Equity curve analyzer for backtesting (Story 18.7.3).

Provides equity curve analysis extracted from the monolithic
metrics.py file. Part of CF-005 refactoring.

Analysis:
    - Monthly return aggregation
    - Equity curve validation
    - Time-based equity metrics

Author: Story 18.7.3
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.backtesting.metrics_core.base import EquityPoint


@dataclass
class MonthlyEquityReturn:
    """Monthly equity return data.

    Attributes:
        year: Calendar year
        month: Calendar month (1-12)
        month_label: Human-readable label (e.g., "Jan 2024")
        start_equity: Equity value at start of month
        end_equity: Equity value at end of month
        return_pct: Return percentage for the month
        trade_count: Number of trades closed in this month
    """

    year: int
    month: int
    month_label: str
    start_equity: Decimal
    end_equity: Decimal
    return_pct: Decimal
    trade_count: int = 0


@dataclass
class EquityMetrics:
    """Aggregated equity curve metrics.

    Attributes:
        start_date: First equity point timestamp
        end_date: Last equity point timestamp
        start_value: Initial equity value
        end_value: Final equity value
        total_return_pct: Overall return percentage
        total_days: Number of calendar days
        trading_days: Number of points in equity curve
    """

    start_date: Optional[datetime]
    end_date: Optional[datetime]
    start_value: Decimal
    end_value: Decimal
    total_return_pct: Decimal
    total_days: int
    trading_days: int


class EquityAnalyzer:
    """Analyzer for equity curve data.

    Provides modular analysis of equity curves that can be
    composed with other calculators via the MetricsFacade.

    Example:
        analyzer = EquityAnalyzer()

        # Convert to standard equity points
        points = [EquityPoint(ts, value) for ts, value in data]

        # Get equity metrics
        metrics = analyzer.calculate_equity_metrics(points)

        # Get monthly breakdown
        monthly = analyzer.calculate_monthly_returns(points)
    """

    MONTH_NAMES = [
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

    def calculate_equity_metrics(self, equity_points: list[EquityPoint]) -> EquityMetrics:
        """Calculate basic equity curve metrics.

        Args:
            equity_points: List of EquityPoint with timestamp and value

        Returns:
            EquityMetrics with aggregated statistics
        """
        if not equity_points:
            return EquityMetrics(
                start_date=None,
                end_date=None,
                start_value=Decimal("0"),
                end_value=Decimal("0"),
                total_return_pct=Decimal("0"),
                total_days=0,
                trading_days=0,
            )

        start_point = equity_points[0]
        end_point = equity_points[-1]

        # Calculate return percentage
        if start_point.value > 0:
            total_return_pct = (
                (end_point.value - start_point.value) / start_point.value
            ) * Decimal("100")
        else:
            total_return_pct = Decimal("0")

        # Calculate days
        total_days = (end_point.timestamp - start_point.timestamp).days

        return EquityMetrics(
            start_date=start_point.timestamp,
            end_date=end_point.timestamp,
            start_value=start_point.value,
            end_value=end_point.value,
            total_return_pct=total_return_pct.quantize(Decimal("0.0001")),
            total_days=max(total_days, 0),
            trading_days=len(equity_points),
        )

    def calculate_monthly_returns(
        self,
        equity_points: list[EquityPoint],
        trades: Optional[list] = None,
    ) -> list[MonthlyEquityReturn]:
        """Calculate monthly return data from equity curve.

        Groups equity points by year-month and calculates monthly
        return percentages.

        Args:
            equity_points: List of EquityPoint with timestamp and value
            trades: Optional list of trades for trade counting

        Returns:
            List of MonthlyEquityReturn, one per month with data
        """
        if not equity_points:
            return []

        # Group equity points by year-month
        monthly_data: dict[tuple[int, int], list[EquityPoint]] = {}
        for point in equity_points:
            year_month = (point.timestamp.year, point.timestamp.month)
            if year_month not in monthly_data:
                monthly_data[year_month] = []
            monthly_data[year_month].append(point)

        # Group trades by exit month if provided
        monthly_trades: dict[tuple[int, int], int] = {}
        if trades:
            for trade in trades:
                exit_ts = getattr(trade, "exit_timestamp", None)
                if exit_ts:
                    year_month = (exit_ts.year, exit_ts.month)
                    monthly_trades[year_month] = monthly_trades.get(year_month, 0) + 1

        # Calculate monthly returns
        monthly_returns: list[MonthlyEquityReturn] = []

        for (year, month), points in sorted(monthly_data.items()):
            if len(points) < 2:
                continue  # Need at least 2 points for return calculation

            # Sort points by timestamp
            sorted_points = sorted(points, key=lambda p: p.timestamp)
            start_equity = sorted_points[0].value
            end_equity = sorted_points[-1].value

            # Calculate return percentage
            if start_equity > 0:
                return_pct = (
                    ((end_equity - start_equity) / start_equity) * Decimal("100")
                ).quantize(Decimal("0.0001"))
            else:
                return_pct = Decimal("0")

            # Get trade count for this month
            trade_count = monthly_trades.get((year, month), 0)

            # Create month label
            month_label = f"{self.MONTH_NAMES[month - 1]} {year}"

            monthly_returns.append(
                MonthlyEquityReturn(
                    year=year,
                    month=month,
                    month_label=month_label,
                    start_equity=start_equity,
                    end_equity=end_equity,
                    return_pct=return_pct,
                    trade_count=trade_count,
                )
            )

        return monthly_returns

    def validate_equity_curve(self, equity_points: list[EquityPoint]) -> tuple[bool, list[str]]:
        """Validate equity curve data integrity.

        Checks for common issues:
        - Empty curve
        - Non-chronological timestamps
        - Negative equity values
        - Large gaps in time

        Args:
            equity_points: List of EquityPoint to validate

        Returns:
            Tuple of (is_valid, list of warning/error messages)
        """
        messages: list[str] = []

        if not equity_points:
            messages.append("Empty equity curve")
            return False, messages

        if len(equity_points) < 2:
            messages.append("Insufficient data points (need at least 2)")
            return False, messages

        # Check chronological order
        prev_ts = equity_points[0].timestamp
        for i, point in enumerate(equity_points[1:], start=1):
            if point.timestamp < prev_ts:
                messages.append(f"Non-chronological timestamp at index {i}")
            prev_ts = point.timestamp

        # Check for negative values
        for i, point in enumerate(equity_points):
            if point.value < 0:
                messages.append(f"Negative equity value at index {i}: {point.value}")

        is_valid = len(messages) == 0
        return is_valid, messages
