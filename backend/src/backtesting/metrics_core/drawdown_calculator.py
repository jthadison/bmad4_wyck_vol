"""
Drawdown Calculator with O(n) algorithms (Story 18.7.1).

Provides efficient single-pass algorithms for:
- Maximum drawdown calculation
- Drawdown period identification

Both algorithms are O(n) time complexity with O(1) additional space
(excluding output storage for drawdown periods).

Author: Story 18.7.1
"""

import heapq
from collections.abc import Sequence
from decimal import Decimal

from src.backtesting.metrics_core.base import DrawdownPeriod, EquityPoint, MetricResult


class DrawdownCalculator:
    """Calculate drawdown metrics using O(n) algorithms.

    Stateless calculator - all methods are pure functions.

    Example:
        calculator = DrawdownCalculator()
        equity_curve = [EquityPoint(ts1, 100), EquityPoint(ts2, 95), ...]
        max_dd = calculator.calculate_max_drawdown(equity_curve)
        periods = calculator.find_drawdown_periods(equity_curve)
    """

    __slots__ = ()

    def calculate_max_drawdown(self, equity_curve: Sequence[EquityPoint]) -> MetricResult:
        """Calculate maximum drawdown in a single O(n) pass.

        Algorithm tracks running peak and computes drawdown at each point.
        Time: O(n), Space: O(1)

        Args:
            equity_curve: Sequence of equity points ordered by timestamp

        Returns:
            MetricResult with max drawdown as percentage (0-100 scale)
        """
        if not equity_curve:
            return MetricResult(name="max_drawdown", value=Decimal("0"))

        peak = equity_curve[0].value
        max_dd = Decimal("0")
        max_dd_peak = peak
        max_dd_trough = peak

        for point in equity_curve:
            if point.value > peak:
                peak = point.value
            elif peak > 0:
                dd = (peak - point.value) / peak * Decimal("100")
                if dd > max_dd:
                    max_dd = dd
                    max_dd_peak = peak
                    max_dd_trough = point.value

        return MetricResult(
            name="max_drawdown",
            value=max_dd.quantize(Decimal("0.0001")),
            metadata={
                "peak_value": max_dd_peak,
                "trough_value": max_dd_trough,
            },
        )

    def find_drawdown_periods(
        self,
        equity_curve: Sequence[EquityPoint],
        min_drawdown_pct: Decimal = Decimal("0"),
    ) -> list[DrawdownPeriod]:
        """Find all drawdown periods in a single O(n) pass.

        Algorithm tracks state transitions: PEAK -> DRAWDOWN -> RECOVERY.
        Time: O(n), Space: O(k) where k = number of drawdown periods

        Args:
            equity_curve: Sequence of equity points ordered by timestamp
            min_drawdown_pct: Minimum drawdown percentage to include (default 0)

        Returns:
            List of DrawdownPeriod objects, sorted by occurrence (chronological)
        """
        if len(equity_curve) < 2:
            return []

        periods: list[DrawdownPeriod] = []
        peak_value = equity_curve[0].value
        peak_date = equity_curve[0].timestamp
        trough_value = peak_value
        trough_date = peak_date
        in_drawdown = False

        for point in equity_curve[1:]:
            if point.value >= peak_value:
                # At or above peak - end any active drawdown
                if in_drawdown and trough_value < peak_value:
                    dd_pct = (peak_value - trough_value) / peak_value * Decimal("100")
                    if dd_pct >= min_drawdown_pct:
                        periods.append(
                            DrawdownPeriod(
                                peak_date=peak_date,
                                trough_date=trough_date,
                                recovery_date=point.timestamp,
                                peak_value=peak_value,
                                trough_value=trough_value,
                                drawdown_pct=dd_pct.quantize(Decimal("0.0001")),
                                duration_days=(trough_date - peak_date).days,
                                recovery_days=(point.timestamp - trough_date).days,
                            )
                        )
                # New peak
                peak_value = point.value
                peak_date = point.timestamp
                trough_value = point.value
                trough_date = point.timestamp
                in_drawdown = False
            else:
                # In drawdown
                in_drawdown = True
                if point.value < trough_value:
                    trough_value = point.value
                    trough_date = point.timestamp

        # Handle ongoing drawdown at end
        if in_drawdown and trough_value < peak_value:
            dd_pct = (peak_value - trough_value) / peak_value * Decimal("100")
            if dd_pct >= min_drawdown_pct:
                periods.append(
                    DrawdownPeriod(
                        peak_date=peak_date,
                        trough_date=trough_date,
                        recovery_date=None,
                        peak_value=peak_value,
                        trough_value=trough_value,
                        drawdown_pct=dd_pct.quantize(Decimal("0.0001")),
                        duration_days=(trough_date - peak_date).days,
                        recovery_days=None,
                    )
                )

        return periods

    def get_top_drawdowns(
        self,
        equity_curve: Sequence[EquityPoint],
        top_n: int = 5,
    ) -> list[DrawdownPeriod]:
        """Get top N drawdown periods by magnitude.

        Uses heapq.nlargest for O(n log k) complexity where k = top_n,
        more efficient than full sort O(n log n) when k << n.

        Args:
            equity_curve: Sequence of equity points ordered by timestamp
            top_n: Number of top drawdowns to return (default 5)

        Returns:
            List of DrawdownPeriod objects sorted by drawdown_pct (largest first)
        """
        periods = self.find_drawdown_periods(equity_curve)
        return heapq.nlargest(top_n, periods, key=lambda p: p.drawdown_pct)
