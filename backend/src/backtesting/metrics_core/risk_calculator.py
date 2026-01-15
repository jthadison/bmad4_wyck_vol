"""
Risk Calculator with O(n) algorithms (Story 18.7.2).

Provides efficient single-pass algorithms for risk-adjusted return metrics:
- Sharpe ratio (risk-adjusted return vs total volatility)
- Sortino ratio (risk-adjusted return vs downside volatility)
- Calmar ratio (return vs maximum drawdown)

All algorithms are O(n) time complexity with O(1) additional space.

Author: Story 18.7.2
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Optional

from src.backtesting.metrics_core.base import EquityPoint, MetricResult
from src.backtesting.metrics_core.drawdown_calculator import DrawdownCalculator

# Constants
TRADING_DAYS_PER_YEAR = Decimal("252")
SQRT_252 = Decimal("15.874507866387544")  # sqrt(252) pre-calculated


class RiskCalculator:
    """Calculate risk-adjusted return metrics using O(n) algorithms.

    Stateless calculator - all methods are pure functions.

    Example:
        calculator = RiskCalculator(risk_free_rate=Decimal("0.02"))
        returns = [Decimal("0.01"), Decimal("-0.005"), Decimal("0.02"), ...]
        sharpe = calculator.calculate_sharpe_ratio(returns)
        sortino = calculator.calculate_sortino_ratio(returns)
    """

    __slots__ = ("_risk_free_rate", "_drawdown_calculator")

    def __init__(
        self,
        risk_free_rate: Decimal = Decimal("0.02"),
        drawdown_calculator: Optional[DrawdownCalculator] = None,
    ):
        """Initialize risk calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 2% = 0.02)
            drawdown_calculator: Optional DrawdownCalculator instance for Calmar ratio
        """
        self._risk_free_rate = risk_free_rate
        self._drawdown_calculator = drawdown_calculator or DrawdownCalculator()

    @property
    def risk_free_rate(self) -> Decimal:
        """Annual risk-free rate used in calculations."""
        return self._risk_free_rate

    def calculate_sharpe_ratio(
        self,
        returns: Sequence[Decimal],
        annualize: bool = True,
    ) -> MetricResult:
        """Calculate Sharpe ratio in a single O(n) pass.

        Sharpe = (mean_return - risk_free_rate) / std_dev

        Algorithm computes mean and variance in two sequential O(n) passes
        (mathematically equivalent to single-pass Welford but clearer).

        Time: O(n), Space: O(1)

        Args:
            returns: Sequence of period returns (e.g., daily returns as decimals)
            annualize: If True, annualize the ratio assuming daily returns

        Returns:
            MetricResult with Sharpe ratio value
        """
        if len(returns) < 2:
            return MetricResult(
                name="sharpe_ratio",
                value=Decimal("0"),
                metadata={"error": "Insufficient data points"},
            )

        n = Decimal(len(returns))

        # Pass 1: Calculate mean return - O(n)
        total = sum(returns, Decimal("0"))
        mean_return = total / n

        # Pass 2: Calculate variance - O(n)
        variance = sum((r - mean_return) ** 2 for r in returns) / n

        # Standard deviation
        if variance <= 0:
            return MetricResult(
                name="sharpe_ratio",
                value=Decimal("0"),
                metadata={"error": "Zero variance"},
            )

        std_dev = Decimal(str(float(variance) ** 0.5))

        if std_dev == 0:
            return MetricResult(
                name="sharpe_ratio",
                value=Decimal("0"),
                metadata={"error": "Zero standard deviation"},
            )

        # Daily risk-free rate
        daily_rf = self._risk_free_rate / TRADING_DAYS_PER_YEAR

        # Calculate Sharpe ratio
        sharpe = (mean_return - daily_rf) / std_dev

        # Annualize if requested
        if annualize:
            sharpe = sharpe * SQRT_252

        return MetricResult(
            name="sharpe_ratio",
            value=sharpe.quantize(Decimal("0.0001")),
            metadata={
                "mean_return": mean_return.quantize(Decimal("0.000001")),
                "std_dev": std_dev.quantize(Decimal("0.000001")),
                "annualized": annualize,
            },
        )

    def calculate_sortino_ratio(
        self,
        returns: Sequence[Decimal],
        target_return: Decimal = Decimal("0"),
        annualize: bool = True,
    ) -> MetricResult:
        """Calculate Sortino ratio in a single O(n) pass.

        Sortino = (mean_return - target_return) / downside_deviation

        Unlike Sharpe, Sortino only penalizes downside volatility (returns below target).

        Time: O(n), Space: O(1)

        Args:
            returns: Sequence of period returns (e.g., daily returns as decimals)
            target_return: Minimum acceptable return (default 0)
            annualize: If True, annualize the ratio assuming daily returns

        Returns:
            MetricResult with Sortino ratio value
        """
        if len(returns) < 2:
            return MetricResult(
                name="sortino_ratio",
                value=Decimal("0"),
                metadata={"error": "Insufficient data points"},
            )

        n = Decimal(len(returns))

        # Pass 1: Calculate mean return - O(n)
        total = sum(returns, Decimal("0"))
        mean_return = total / n

        # Pass 2: Calculate downside variance - O(n)
        # Only consider returns below target
        downside_sum = Decimal("0")
        downside_count = 0

        for r in returns:
            if r < target_return:
                downside_sum += (r - target_return) ** 2
                downside_count += 1

        if downside_count == 0:
            # No downside returns - infinite Sortino (return large positive)
            return MetricResult(
                name="sortino_ratio",
                value=Decimal("999.9999"),
                metadata={
                    "mean_return": mean_return.quantize(Decimal("0.000001")),
                    "downside_deviation": Decimal("0"),
                    "note": "No downside returns",
                },
            )

        # Downside deviation (use n for denominator, not downside_count)
        downside_variance = downside_sum / n
        downside_dev = Decimal(str(float(downside_variance) ** 0.5))

        if downside_dev == 0:
            return MetricResult(
                name="sortino_ratio",
                value=Decimal("999.9999"),
                metadata={"error": "Zero downside deviation"},
            )

        # Calculate Sortino ratio
        sortino = (mean_return - target_return) / downside_dev

        # Annualize if requested
        if annualize:
            sortino = sortino * SQRT_252

        return MetricResult(
            name="sortino_ratio",
            value=sortino.quantize(Decimal("0.0001")),
            metadata={
                "mean_return": mean_return.quantize(Decimal("0.000001")),
                "downside_deviation": downside_dev.quantize(Decimal("0.000001")),
                "target_return": target_return,
                "annualized": annualize,
            },
        )

    def calculate_calmar_ratio(
        self,
        equity_curve: Sequence[EquityPoint],
        annualized_return: Optional[Decimal] = None,
    ) -> MetricResult:
        """Calculate Calmar ratio using O(n) max drawdown.

        Calmar = Annualized Return / Max Drawdown

        Uses DrawdownCalculator for O(n) max drawdown calculation.

        Time: O(n), Space: O(1)

        Args:
            equity_curve: Sequence of equity points ordered by timestamp
            annualized_return: Pre-calculated CAGR. If None, calculated from equity curve.

        Returns:
            MetricResult with Calmar ratio value
        """
        if len(equity_curve) < 2:
            return MetricResult(
                name="calmar_ratio",
                value=Decimal("0"),
                metadata={"error": "Insufficient data points"},
            )

        # Calculate max drawdown using O(n) algorithm
        dd_result = self._drawdown_calculator.calculate_max_drawdown(equity_curve)
        max_dd = dd_result.value

        if max_dd <= 0:
            return MetricResult(
                name="calmar_ratio",
                value=Decimal("999.9999"),
                metadata={
                    "max_drawdown_pct": Decimal("0"),
                    "note": "No drawdown",
                },
            )

        # Calculate annualized return if not provided
        if annualized_return is None:
            annualized_return = self._calculate_cagr(equity_curve)

        # Calmar = CAGR / Max Drawdown (both as percentages)
        # Convert CAGR from decimal to percentage for consistency
        cagr_pct = annualized_return * Decimal("100")
        calmar = cagr_pct / max_dd

        return MetricResult(
            name="calmar_ratio",
            value=calmar.quantize(Decimal("0.0001")),
            metadata={
                "annualized_return_pct": cagr_pct.quantize(Decimal("0.0001")),
                "max_drawdown_pct": max_dd.quantize(Decimal("0.0001")),
            },
        )

    def _calculate_cagr(self, equity_curve: Sequence[EquityPoint]) -> Decimal:
        """Calculate CAGR from equity curve.

        CAGR = (final / initial) ^ (1 / years) - 1

        Args:
            equity_curve: Sequence of equity points

        Returns:
            CAGR as decimal (e.g., 0.15 = 15%)
        """
        if len(equity_curve) < 2:
            return Decimal("0")

        initial = equity_curve[0].value
        final = equity_curve[-1].value

        if initial <= 0 or final <= 0:
            return Decimal("0")

        # Calculate years
        start_ts = equity_curve[0].timestamp
        end_ts = equity_curve[-1].timestamp
        days = (end_ts - start_ts).days

        if days <= 0:
            return Decimal("0")

        years = Decimal(days) / Decimal("365.25")

        # CAGR calculation using float for exponentiation
        cagr = (float(final) / float(initial)) ** (1 / float(years)) - 1

        return Decimal(str(cagr))

    def calculate_returns_from_equity(
        self,
        equity_curve: Sequence[EquityPoint],
    ) -> list[Decimal]:
        """Convert equity curve to period returns.

        Utility method to generate returns sequence from equity points.

        Time: O(n), Space: O(n) for output

        Args:
            equity_curve: Sequence of equity points

        Returns:
            List of period returns (percentage change between consecutive points)
        """
        if len(equity_curve) < 2:
            return []

        returns = []
        for i in range(1, len(equity_curve)):
            prev_val = equity_curve[i - 1].value
            curr_val = equity_curve[i].value

            if prev_val > 0:
                ret = (curr_val - prev_val) / prev_val
                returns.append(ret)

        return returns
