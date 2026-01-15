"""
Return Calculator for performance metrics (Story 18.7.2).

Provides return calculation methods:
- Total return percentage
- CAGR (Compound Annual Growth Rate)
- Monthly returns for heatmap visualization
- Annual returns breakdown

All methods use Decimal for financial precision.

Author: Story 18.7.2
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.backtesting.metrics_core.base import EquityPoint, MetricResult

# Constants
DAYS_PER_YEAR = Decimal("365.25")


@dataclass(frozen=True)
class MonthlyReturn:
    """Monthly return data for heatmap visualization.

    Attributes:
        year: Calendar year
        month: Month number (1-12)
        month_label: Human-readable label (e.g., "Jan 2024")
        return_pct: Return percentage for the month
        start_value: Portfolio value at month start
        end_value: Portfolio value at month end
    """

    year: int
    month: int
    month_label: str
    return_pct: Decimal
    start_value: Decimal
    end_value: Decimal


@dataclass(frozen=True)
class AnnualReturn:
    """Annual return data.

    Attributes:
        year: Calendar year
        return_pct: Return percentage for the year
        start_value: Portfolio value at year start
        end_value: Portfolio value at year end
        months_traded: Number of months with trading activity
    """

    year: int
    return_pct: Decimal
    start_value: Decimal
    end_value: Decimal
    months_traded: int


class ReturnCalculator:
    """Calculate return metrics with consistent Decimal precision.

    Stateless calculator - all methods are pure functions.

    Example:
        calculator = ReturnCalculator()
        equity = [EquityPoint(ts1, 100000), EquityPoint(ts2, 115000), ...]
        total = calculator.calculate_total_return(equity)
        cagr = calculator.calculate_cagr(equity)
        monthly = calculator.calculate_monthly_returns(equity)
    """

    __slots__ = ()

    # Month name labels for formatting
    _MONTH_NAMES = [
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

    def calculate_total_return(
        self,
        equity_curve: Sequence[EquityPoint],
    ) -> MetricResult:
        """Calculate total return percentage.

        Total Return = ((final - initial) / initial) * 100

        Time: O(1), Space: O(1)

        Args:
            equity_curve: Sequence of equity points

        Returns:
            MetricResult with total return percentage
        """
        if len(equity_curve) < 2:
            return MetricResult(
                name="total_return_pct",
                value=Decimal("0"),
                metadata={"error": "Insufficient data points"},
            )

        initial = equity_curve[0].value
        final = equity_curve[-1].value

        if initial <= 0:
            return MetricResult(
                name="total_return_pct",
                value=Decimal("0"),
                metadata={"error": "Invalid initial value"},
            )

        return_pct = ((final - initial) / initial) * Decimal("100")

        return MetricResult(
            name="total_return_pct",
            value=return_pct.quantize(Decimal("0.0001")),
            metadata={
                "initial_value": initial,
                "final_value": final,
            },
        )

    def calculate_cagr(
        self,
        equity_curve: Sequence[EquityPoint],
    ) -> MetricResult:
        """Calculate Compound Annual Growth Rate.

        CAGR = ((final / initial) ^ (1 / years)) - 1

        Time: O(1), Space: O(1)

        Args:
            equity_curve: Sequence of equity points

        Returns:
            MetricResult with CAGR as decimal (0.15 = 15%)
        """
        if len(equity_curve) < 2:
            return MetricResult(
                name="cagr",
                value=Decimal("0"),
                metadata={"error": "Insufficient data points"},
            )

        initial = equity_curve[0].value
        final = equity_curve[-1].value
        start_ts = equity_curve[0].timestamp
        end_ts = equity_curve[-1].timestamp

        if initial <= 0 or final <= 0:
            return MetricResult(
                name="cagr",
                value=Decimal("0"),
                metadata={"error": "Invalid equity values"},
            )

        # Calculate years
        days = (end_ts - start_ts).days
        if days <= 0:
            return MetricResult(
                name="cagr",
                value=Decimal("0"),
                metadata={"error": "Invalid time period"},
            )

        years = Decimal(days) / DAYS_PER_YEAR

        # CAGR calculation using float for exponentiation
        cagr = (float(final) / float(initial)) ** (1 / float(years)) - 1

        return MetricResult(
            name="cagr",
            value=Decimal(str(cagr)).quantize(Decimal("0.000001")),
            metadata={
                "initial_value": initial,
                "final_value": final,
                "years": years.quantize(Decimal("0.01")),
            },
        )

    def calculate_monthly_returns(
        self,
        equity_curve: Sequence[EquityPoint],
    ) -> list[MonthlyReturn]:
        """Calculate monthly returns for heatmap visualization.

        Groups equity points by year-month and calculates return for each month.

        Time: O(n), Space: O(m) where m = number of months

        Args:
            equity_curve: Sequence of equity points ordered by timestamp

        Returns:
            List of MonthlyReturn objects, one per month
        """
        if len(equity_curve) < 2:
            return []

        # Group equity points by year-month - O(n)
        monthly_data: dict[tuple[int, int], list[EquityPoint]] = {}

        for point in equity_curve:
            key = (point.timestamp.year, point.timestamp.month)
            if key not in monthly_data:
                monthly_data[key] = []
            monthly_data[key].append(point)

        # Calculate returns for each month - O(m)
        monthly_returns: list[MonthlyReturn] = []

        for (year, month), points in sorted(monthly_data.items()):
            if len(points) < 2:
                continue

            start_value = points[0].value
            end_value = points[-1].value

            if start_value > 0:
                return_pct = ((end_value - start_value) / start_value) * Decimal("100")
            else:
                return_pct = Decimal("0")

            month_label = f"{self._MONTH_NAMES[month - 1]} {year}"

            monthly_returns.append(
                MonthlyReturn(
                    year=year,
                    month=month,
                    month_label=month_label,
                    return_pct=return_pct.quantize(Decimal("0.0001")),
                    start_value=start_value,
                    end_value=end_value,
                )
            )

        return monthly_returns

    def calculate_annual_returns(
        self,
        equity_curve: Sequence[EquityPoint],
    ) -> list[AnnualReturn]:
        """Calculate annual returns breakdown.

        Groups equity points by year and calculates return for each year.

        Time: O(n), Space: O(y) where y = number of years

        Args:
            equity_curve: Sequence of equity points ordered by timestamp

        Returns:
            List of AnnualReturn objects, one per year
        """
        if len(equity_curve) < 2:
            return []

        # Group equity points by year - O(n)
        yearly_data: dict[int, list[EquityPoint]] = {}

        for point in equity_curve:
            year = point.timestamp.year
            if year not in yearly_data:
                yearly_data[year] = []
            yearly_data[year].append(point)

        # Also track months per year for activity metric
        monthly_activity: dict[int, set[int]] = {}
        for point in equity_curve:
            year = point.timestamp.year
            month = point.timestamp.month
            if year not in monthly_activity:
                monthly_activity[year] = set()
            monthly_activity[year].add(month)

        # Calculate returns for each year - O(y)
        annual_returns: list[AnnualReturn] = []

        for year, points in sorted(yearly_data.items()):
            if len(points) < 2:
                continue

            start_value = points[0].value
            end_value = points[-1].value

            if start_value > 0:
                return_pct = ((end_value - start_value) / start_value) * Decimal("100")
            else:
                return_pct = Decimal("0")

            months_traded = len(monthly_activity.get(year, set()))

            annual_returns.append(
                AnnualReturn(
                    year=year,
                    return_pct=return_pct.quantize(Decimal("0.0001")),
                    start_value=start_value,
                    end_value=end_value,
                    months_traded=months_traded,
                )
            )

        return annual_returns

    def calculate_period_return(
        self,
        start_value: Decimal,
        end_value: Decimal,
    ) -> Decimal:
        """Calculate simple period return percentage.

        Utility method for calculating return between two values.

        Args:
            start_value: Initial portfolio value
            end_value: Final portfolio value

        Returns:
            Return as percentage (e.g., 15.5 for 15.5%)
        """
        if start_value <= 0:
            return Decimal("0")

        return ((end_value - start_value) / start_value) * Decimal("100")

    def calculate_cumulative_returns(
        self,
        equity_curve: Sequence[EquityPoint],
    ) -> list[tuple[datetime, Decimal]]:
        """Calculate cumulative return at each point.

        Returns cumulative return percentage from initial value at each timestamp.

        Time: O(n), Space: O(n)

        Args:
            equity_curve: Sequence of equity points

        Returns:
            List of (timestamp, cumulative_return_pct) tuples
        """
        if not equity_curve:
            return []

        initial = equity_curve[0].value
        if initial <= 0:
            return []

        results: list[tuple[datetime, Decimal]] = []

        for point in equity_curve:
            cum_return = ((point.value - initial) / initial) * Decimal("100")
            results.append((point.timestamp, cum_return.quantize(Decimal("0.0001"))))

        return results
