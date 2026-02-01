"""
Transaction cost models.

This module contains models for tracking commission and slippage costs.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "CommissionBreakdown",
    "SlippageBreakdown",
    "TransactionCostReport",
    "BacktestCostSummary",
]


class CommissionBreakdown(BaseModel):
    """
    Detailed commission breakdown for a single order (Story 12.5 Task 1).

    Provides transparency into commission calculations, showing base commission
    before caps and final applied commission after min/max adjustments.

    Attributes:
        order_id: Reference to BacktestOrder
        shares: Quantity traded
        base_commission: Commission before min/max caps
        applied_commission: Actual commission charged after caps
        commission_type: Calculation method used
        broker_name: Broker profile used

    Author: Story 12.5 Task 1
    """

    order_id: UUID = Field(description="BacktestOrder ID")
    shares: int = Field(gt=0, description="Share quantity")
    base_commission: Decimal = Field(decimal_places=2, description="Commission before caps")
    applied_commission: Decimal = Field(decimal_places=2, description="Actual commission charged")
    commission_type: str = Field(description="Calculation method (PER_SHARE, PERCENTAGE, FIXED)")
    broker_name: str = Field(description="Broker name")

    @field_validator("base_commission", "applied_commission", mode="before")
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class SlippageBreakdown(BaseModel):
    """
    Detailed slippage breakdown for a single order (Story 12.5 Task 2).

    Provides complete transparency into slippage calculations, showing
    liquidity assessment, base slippage, market impact, and total costs.

    Attributes:
        order_id: Reference to BacktestOrder
        bar_volume: Volume of the fill bar
        bar_avg_dollar_volume: 20-bar average dollar volume for liquidity calc
        order_quantity: Number of shares in order
        order_value: Dollar value of order (quantity * fill_price)
        volume_participation_pct: Order quantity as % of bar volume
        base_slippage_pct: Liquidity-based slippage percentage
        market_impact_slippage_pct: Additional slippage from market impact
        total_slippage_pct: Combined slippage percentage
        slippage_dollar_amount: Total slippage cost in dollars
        slippage_model_used: Model used for calculation

    Author: Story 12.5 Task 2
    """

    order_id: UUID = Field(description="BacktestOrder ID")
    bar_volume: int = Field(ge=0, description="Fill bar volume")
    bar_avg_dollar_volume: Decimal = Field(decimal_places=2, description="20-bar avg dollar volume")
    order_quantity: int = Field(gt=0, description="Order quantity")
    order_value: Decimal = Field(decimal_places=2, description="Order dollar value")
    volume_participation_pct: Decimal = Field(
        decimal_places=4, description="Order as % of bar volume"
    )
    base_slippage_pct: Decimal = Field(decimal_places=8, description="Base slippage %")
    market_impact_slippage_pct: Decimal = Field(
        decimal_places=8, description="Market impact slippage %"
    )
    total_slippage_pct: Decimal = Field(decimal_places=8, description="Total slippage %")
    slippage_dollar_amount: Decimal = Field(decimal_places=2, description="Slippage in dollars")
    slippage_model_used: str = Field(description="Slippage model used")

    @field_validator(
        "bar_avg_dollar_volume",
        "order_value",
        "volume_participation_pct",
        "base_slippage_pct",
        "market_impact_slippage_pct",
        "total_slippage_pct",
        "slippage_dollar_amount",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class TransactionCostReport(BaseModel):
    """
    Transaction cost report for a single completed trade (Story 12.5 Task 8).

    Analyzes all costs (commission + slippage) for a round-trip trade,
    showing impact on P&L and R-multiples.

    Attributes:
        trade_id: Reference to BacktestTrade
        entry_commission: Commission for entry order
        exit_commission: Commission for exit order
        total_commission: Total commission (entry + exit)
        entry_slippage: Slippage cost for entry
        exit_slippage: Slippage cost for exit
        total_slippage: Total slippage (entry + exit)
        total_transaction_costs: Total costs (commission + slippage)
        transaction_cost_pct: Costs as % of trade value
        transaction_cost_r_multiple: Costs expressed in R-multiples
        gross_pnl: P&L before costs
        net_pnl: P&L after costs
        gross_r_multiple: R-multiple before costs
        net_r_multiple: R-multiple after costs

    Author: Story 12.5 Task 8
    """

    trade_id: UUID = Field(description="BacktestTrade ID")
    entry_commission: Decimal = Field(decimal_places=2, description="Entry commission")
    exit_commission: Decimal = Field(decimal_places=2, description="Exit commission")
    total_commission: Decimal = Field(decimal_places=2, description="Total commission")
    entry_slippage: Decimal = Field(decimal_places=2, description="Entry slippage cost")
    exit_slippage: Decimal = Field(decimal_places=2, description="Exit slippage cost")
    total_slippage: Decimal = Field(decimal_places=2, description="Total slippage")
    total_transaction_costs: Decimal = Field(decimal_places=2, description="Total costs")
    transaction_cost_pct: Decimal = Field(decimal_places=4, description="Costs as % of trade value")
    transaction_cost_r_multiple: Decimal = Field(
        decimal_places=4, description="Costs in R-multiples"
    )
    gross_pnl: Decimal = Field(decimal_places=2, description="P&L before costs")
    net_pnl: Decimal = Field(decimal_places=2, description="P&L after costs")
    gross_r_multiple: Decimal = Field(decimal_places=2, description="R-multiple before costs")
    net_r_multiple: Decimal = Field(decimal_places=2, description="R-multiple after costs")

    @field_validator(
        "entry_commission",
        "exit_commission",
        "total_commission",
        "entry_slippage",
        "exit_slippage",
        "total_slippage",
        "total_transaction_costs",
        "transaction_cost_pct",
        "transaction_cost_r_multiple",
        "gross_pnl",
        "net_pnl",
        "gross_r_multiple",
        "net_r_multiple",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class BacktestCostSummary(BaseModel):
    """
    Aggregate cost summary for entire backtest (Story 12.5 Task 8).

    Summarizes all transaction costs across all trades in a backtest,
    showing total costs, averages, and impact on performance metrics.

    Attributes:
        total_trades: Number of trades
        total_commission_paid: Sum of all commissions
        total_slippage_cost: Sum of all slippage
        total_transaction_costs: Total costs (commission + slippage)
        avg_commission_per_trade: Average commission per trade
        avg_slippage_per_trade: Average slippage per trade
        avg_transaction_cost_per_trade: Average total cost per trade
        cost_as_pct_of_total_pnl: Costs as % of total P&L
        gross_avg_r_multiple: Avg R-multiple before costs
        net_avg_r_multiple: Avg R-multiple after costs
        r_multiple_degradation: Difference (gross - net)

    Author: Story 12.5 Task 8
    """

    total_trades: int = Field(ge=0, description="Number of trades")
    total_commission_paid: Decimal = Field(decimal_places=2, description="Total commissions")
    total_slippage_cost: Decimal = Field(decimal_places=2, description="Total slippage")
    total_transaction_costs: Decimal = Field(decimal_places=2, description="Total costs")
    avg_commission_per_trade: Decimal = Field(
        decimal_places=2, description="Avg commission per trade"
    )
    avg_slippage_per_trade: Decimal = Field(decimal_places=2, description="Avg slippage per trade")
    avg_transaction_cost_per_trade: Decimal = Field(
        decimal_places=2, description="Avg cost per trade"
    )
    cost_as_pct_of_total_pnl: Decimal = Field(
        decimal_places=4, description="Costs as % of total P&L"
    )
    gross_avg_r_multiple: Decimal = Field(decimal_places=2, description="Avg R before costs")
    net_avg_r_multiple: Decimal = Field(decimal_places=2, description="Avg R after costs")
    r_multiple_degradation: Decimal = Field(
        decimal_places=2, description="R degradation (gross - net)"
    )

    @field_validator(
        "total_commission_paid",
        "total_slippage_cost",
        "total_transaction_costs",
        "avg_commission_per_trade",
        "avg_slippage_per_trade",
        "avg_transaction_cost_per_trade",
        "cost_as_pct_of_total_pnl",
        "gross_avg_r_multiple",
        "net_avg_r_multiple",
        "r_multiple_degradation",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))
