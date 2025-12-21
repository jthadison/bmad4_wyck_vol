"""
Market Impact Calculator for Backtesting (Story 12.5 Task 4).

Calculates additional slippage from market impact when order size
is large relative to bar volume.

AC4: Orders > 10% of bar volume incur additional 0.01% slippage per 10% increment

Author: Story 12.5 Task 4
"""

from decimal import ROUND_UP, Decimal

import structlog

from src.models.backtest import SlippageConfig

logger = structlog.get_logger(__name__)


class MarketImpactCalculator:
    """
    Calculate market impact slippage for large orders.

    When an order consumes significant bar volume, it "moves the market"
    and incurs additional slippage beyond base liquidity slippage.

    AC4: Threshold = 10% of bar volume
         Impact = 0.01% per 10% increment above threshold

    Methods:
        calculate_volume_participation: Calculate order size as % of bar volume
        calculate_market_impact_slippage: Calculate additional slippage from impact

    Example:
        Order: 30,000 shares
        Bar volume: 100,000 shares
        Volume participation: 30%
        Threshold: 10%
        Excess: 20% = 2 increments
        Market impact: 2 * 0.01% = 0.02% additional slippage

    Author: Story 12.5 Task 4
    """

    def calculate_volume_participation(self, order_quantity: int, bar_volume: int) -> Decimal:
        """
        Calculate order quantity as percentage of bar volume.

        Subtask 4.2: Calculate order_quantity / bar_volume
        Subtask 4.2: Return as Decimal percentage (e.g., Decimal("0.15") = 15%)
        Subtask 4.2: Handle edge case: bar_volume = 0 → return Decimal("0")

        Args:
            order_quantity: Number of shares in order
            bar_volume: Total volume of the bar

        Returns:
            Volume participation as Decimal (e.g., Decimal("0.15") = 15%)

        Edge cases:
            - bar_volume = 0: Return Decimal("0") (cannot calculate participation)
            - order_quantity = 0: Return Decimal("0") (no participation)
            - order_quantity > bar_volume: Return > 1.0 (100%+ participation)

        Example:
            participation = calculate_volume_participation(10000, 50000)
            # participation = Decimal("0.20") = 20%

            participation = calculate_volume_participation(5000, 0)
            # participation = Decimal("0") (edge case: no volume)

        Author: Story 12.5 Subtask 4.2
        """
        # Edge case: zero bar volume
        if bar_volume == 0:
            logger.warning(
                "Zero bar volume encountered in market impact calculation",
                order_quantity=order_quantity,
            )
            return Decimal("0")

        # Edge case: zero order quantity
        if order_quantity == 0:
            return Decimal("0")

        # Calculate participation percentage
        participation = Decimal(order_quantity) / Decimal(bar_volume)

        logger.debug(
            "Volume participation calculated",
            order_quantity=order_quantity,
            bar_volume=bar_volume,
            participation_pct=float(participation * 100),
        )

        return participation

    def calculate_market_impact_slippage(
        self, volume_participation_pct: Decimal, config: SlippageConfig
    ) -> Decimal:
        """
        Calculate additional slippage from market impact.

        Subtask 4.3: If not config.market_impact_enabled: return Decimal("0")
        Subtask 4.3: If volume_participation_pct <= threshold: return Decimal("0")
        Subtask 4.3: Calculate excess: volume_participation_pct - threshold_pct
        Subtask 4.3: Calculate increments: excess_pct / 0.10 (number of 10% increments)
        Subtask 4.3: Calculate impact: increments * config.market_impact_per_increment_pct
        Subtask 4.3: Return market impact slippage as Decimal

        Args:
            volume_participation_pct: Order as % of bar volume (from calculate_volume_participation)
            config: Slippage configuration with market impact settings

        Returns:
            Market impact slippage percentage (Decimal)

        Logic:
            - If disabled OR below threshold: return 0
            - Calculate excess participation above threshold
            - Calculate number of 10% increments (round up)
            - Each increment adds market_impact_per_increment_pct (default 0.01%)

        Example (Subtask 4.4):
            Order: 10,000 shares
            Bar volume: 50,000 shares
            Volume participation: 20%
            Threshold: 10%
            Excess: 20% - 10% = 10% = 1 increment
            Market impact: 1 * 0.01% = 0.01% additional slippage

        Example 2:
            Volume participation: 35%
            Threshold: 10%
            Excess: 25% = 2.5 increments → round up to 3
            Market impact: 3 * 0.01% = 0.03% additional slippage

        Author: Story 12.5 Subtask 4.3
        """
        # If market impact disabled, return zero
        if not config.market_impact_enabled:
            logger.debug("Market impact disabled")
            return Decimal("0")

        # If below threshold, no market impact
        if volume_participation_pct <= config.market_impact_threshold_pct:
            logger.debug(
                "Volume participation below threshold, no market impact",
                participation_pct=float(volume_participation_pct * 100),
                threshold_pct=float(config.market_impact_threshold_pct * 100),
            )
            return Decimal("0")

        # Calculate excess participation above threshold
        excess_pct = volume_participation_pct - config.market_impact_threshold_pct

        # Calculate number of 10% increments (round up)
        # Each 10% above threshold adds one increment
        num_increments = (excess_pct / config.market_impact_threshold_pct).quantize(
            Decimal("1"), rounding=ROUND_UP
        )

        # Calculate market impact slippage
        market_impact = num_increments * config.market_impact_per_increment_pct

        logger.info(
            "Market impact slippage calculated",
            participation_pct=float(volume_participation_pct * 100),
            threshold_pct=float(config.market_impact_threshold_pct * 100),
            excess_pct=float(excess_pct * 100),
            num_increments=int(num_increments),
            market_impact_pct=float(market_impact * 100),
        )

        return market_impact
