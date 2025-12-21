"""
Commission Calculator for Backtesting (Story 12.5 Task 5).

Calculates commission costs for backtest orders with support for multiple
commission models: per-share, percentage-based, and fixed.

AC1: Commission $0.005/share (configurable per broker)
AC10: Ensure realistic cost impact on R-multiples

Author: Story 12.5 Task 5
"""

from decimal import ROUND_UP, Decimal

import structlog

from src.models.backtest import (
    BacktestOrder,
    CommissionBreakdown,
    CommissionConfig,
)

logger = structlog.get_logger(__name__)


class CommissionCalculator:
    """
    Calculate commission costs for backtest orders.

    Supports three commission models:
    1. PER_SHARE: Fixed cost per share (e.g., IB: $0.005/share)
    2. PERCENTAGE: Percentage of trade value (e.g., 0.1% of trade)
    3. FIXED: Fixed cost per trade (e.g., Robinhood: $0)

    Min/max caps prevent edge cases (very small/large trades).

    Methods:
        calculate_commission: Main entry point for commission calculation
        _calculate_per_share: Per-share commission model
        _calculate_percentage: Percentage-based commission model
        _calculate_fixed: Fixed commission model
        _apply_min_max_caps: Apply min/max commission limits

    Example:
        calculator = CommissionCalculator()
        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            min_commission=Decimal("1.00")
        )
        order = BacktestOrder(quantity=1000, ...)
        commission = calculator.calculate_commission(order, config)
        # commission = Decimal("5.00") (1000 * $0.005)

    Author: Story 12.5 Task 5
    """

    def calculate_commission(
        self, order: BacktestOrder, config: CommissionConfig
    ) -> tuple[Decimal, CommissionBreakdown]:
        """
        Calculate commission for an order.

        Subtask 5.2: Route to appropriate calculation method based on config.commission_type
        Subtask 5.2: Apply min/max commission caps
        Subtask 5.2: Return final commission as Decimal with breakdown

        Args:
            order: Backtest order (must have quantity and fill_price)
            config: Commission configuration

        Returns:
            Tuple of (final_commission, commission_breakdown)

        Example:
            Per-share (IB retail):
                1,000 shares * $0.005 = $5.00

            Percentage (0.1%):
                $10,000 trade * 0.001 = $10.00

            Fixed (Robinhood):
                $0 per trade

        Author: Story 12.5 Subtask 5.2
        """
        # Route to appropriate calculation method
        if config.commission_type == "PER_SHARE":
            base_commission = self._calculate_per_share(order.quantity, config.commission_per_share)
        elif config.commission_type == "PERCENTAGE":
            # Calculate order value for percentage-based commission
            order_value = Decimal(str(order.fill_price or 0)) * Decimal(order.quantity)
            base_commission = self._calculate_percentage(order_value, config.commission_percentage)
        elif config.commission_type == "FIXED":
            base_commission = self._calculate_fixed(config.fixed_commission_per_trade)
        else:
            logger.error("Unknown commission type", commission_type=config.commission_type)
            base_commission = Decimal("0")

        # Apply min/max caps
        final_commission = self._apply_min_max_caps(base_commission, config)

        # Create breakdown (quantize to 2 decimal places for Pydantic validation, using ROUND_UP)
        breakdown = CommissionBreakdown(
            order_id=order.order_id,
            shares=order.quantity,
            base_commission=base_commission.quantize(Decimal("0.01"), rounding=ROUND_UP),
            applied_commission=final_commission.quantize(Decimal("0.01"), rounding=ROUND_UP),
            commission_type=config.commission_type,
            broker_name=config.broker_name,
        )

        logger.info(
            "Commission calculated",
            order_id=str(order.order_id),
            commission_type=config.commission_type,
            quantity=order.quantity,
            base_commission=float(base_commission),
            final_commission=float(final_commission),
            broker=config.broker_name,
        )

        return final_commission, breakdown

    def _calculate_per_share(self, quantity: int, commission_per_share: Decimal) -> Decimal:
        """
        Calculate per-share commission.

        Subtask 5.3: Base commission = quantity * commission_per_share
        Subtask 5.3: Example: 1,000 shares * $0.005 = $5.00

        Args:
            quantity: Number of shares
            commission_per_share: Commission rate per share

        Returns:
            Base commission (before min/max caps)

        Example:
            commission = _calculate_per_share(1000, Decimal("0.005"))
            # commission = Decimal("5.00")

        Author: Story 12.5 Subtask 5.3
        """
        base_commission = Decimal(quantity) * commission_per_share

        logger.debug(
            "Per-share commission calculated",
            quantity=quantity,
            commission_per_share=float(commission_per_share),
            base_commission=float(base_commission),
        )

        return base_commission

    def _calculate_percentage(
        self, order_value: Decimal, commission_percentage: Decimal
    ) -> Decimal:
        """
        Calculate percentage-based commission.

        Subtask 5.4: Base commission = order_value * commission_percentage
        Subtask 5.4: Example: $10,000 order * 0.001 (0.1%) = $10.00

        Args:
            order_value: Dollar value of order (quantity * fill_price)
            commission_percentage: Commission percentage (e.g., Decimal("0.001") = 0.1%)

        Returns:
            Base commission (before min/max caps)

        Example:
            commission = _calculate_percentage(
                Decimal("10000"),
                Decimal("0.001")
            )
            # commission = Decimal("10.00")

        Author: Story 12.5 Subtask 5.4
        """
        base_commission = order_value * commission_percentage

        logger.debug(
            "Percentage commission calculated",
            order_value=float(order_value),
            commission_percentage=float(commission_percentage * 100),
            base_commission=float(base_commission),
        )

        return base_commission

    def _calculate_fixed(self, fixed_commission: Decimal) -> Decimal:
        """
        Calculate fixed commission.

        Subtask 5.5: Return fixed commission regardless of order size
        Subtask 5.5: Example: $1.00 per trade (Robinhood-style) or $0

        Args:
            fixed_commission: Fixed commission amount

        Returns:
            Fixed commission

        Example:
            commission = _calculate_fixed(Decimal("1.00"))
            # commission = Decimal("1.00")

            commission = _calculate_fixed(Decimal("0"))
            # commission = Decimal("0") (commission-free broker)

        Author: Story 12.5 Subtask 5.5
        """
        logger.debug("Fixed commission calculated", fixed_commission=float(fixed_commission))

        return fixed_commission

    def _apply_min_max_caps(self, base_commission: Decimal, config: CommissionConfig) -> Decimal:
        """
        Apply minimum and maximum commission caps.

        Subtask 5.6: If base_commission < min_commission: return min_commission
        Subtask 5.6: If max_commission exists and base_commission > max_commission: return max_commission
        Subtask 5.6: Else: return base_commission

        Args:
            base_commission: Commission before caps
            config: Commission configuration with min/max settings

        Returns:
            Commission after applying caps

        Example:
            Min cap:
                base = Decimal("0.50"), min = Decimal("1.00")
                result = Decimal("1.00")  # capped to minimum

            Max cap:
                base = Decimal("500.00"), max = Decimal("100.00")
                result = Decimal("100.00")  # capped to maximum

            No cap:
                base = Decimal("5.00"), min = Decimal("1.00"), max = None
                result = Decimal("5.00")  # no adjustment needed

        Author: Story 12.5 Subtask 5.6
        """
        final_commission = base_commission

        # Apply minimum cap
        if final_commission < config.min_commission:
            logger.debug(
                "Commission capped to minimum",
                base_commission=float(base_commission),
                min_commission=float(config.min_commission),
            )
            final_commission = config.min_commission

        # Apply maximum cap (if set)
        if config.max_commission is not None and final_commission > config.max_commission:
            logger.debug(
                "Commission capped to maximum",
                base_commission=float(base_commission),
                max_commission=float(config.max_commission),
            )
            final_commission = config.max_commission

        return final_commission
