"""
Backtest configuration models.

This module contains models for backtest configuration including
parameters, commission settings, and slippage settings.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class BacktestPreviewRequest(BaseModel):
    """Request payload for backtest preview.

    Attributes:
        proposed_config: Configuration changes to test
        days: Backtest duration in days (7-365, default 90)
        symbol: Optional symbol filter for specific instrument
        timeframe: Data timeframe (default "1d")
    """

    proposed_config: dict[str, Any]  # Configuration changes to test
    days: int = Field(default=90, ge=7, le=365, description="Backtest duration in days")
    symbol: str | None = Field(default=None, description="Optional symbol filter")
    timeframe: str = Field(default="1d", description="Data timeframe")


class CommissionConfig(BaseModel):
    """
    Commission configuration for backtesting (Story 12.5 Task 1).

    Supports multiple commission models to match different brokers:
    - PER_SHARE: Fixed cost per share (e.g., Interactive Brokers: $0.005/share)
    - PERCENTAGE: Percentage of trade value (e.g., 0.1% of trade value)
    - FIXED: Fixed cost per trade regardless of size (e.g., Robinhood: $0)

    Min/max caps prevent edge cases (very small/large trades).

    Attributes:
        commission_type: Type of commission calculation
        commission_per_share: Cost per share for PER_SHARE model (default $0.005 IB retail)
        commission_percentage: Percentage for PERCENTAGE model (e.g., Decimal("0.001") = 0.1%)
        fixed_commission_per_trade: Fixed cost for FIXED model
        min_commission: Minimum commission per trade (default $1.00)
        max_commission: Optional maximum commission cap
        broker_name: Broker name for reference (e.g., "Interactive Brokers")

    Author: Story 12.5 Task 1
    """

    commission_type: Literal["PER_SHARE", "PERCENTAGE", "FIXED"] = Field(
        default="PER_SHARE", description="Commission calculation method"
    )
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"),
        ge=Decimal("0"),
        decimal_places=8,
        description="Commission per share (default $0.005 for IB retail)",
    )
    commission_percentage: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Commission as percentage of trade value",
    )
    fixed_commission_per_trade: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        decimal_places=2,
        description="Fixed commission per trade",
    )
    min_commission: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("0"),
        decimal_places=2,
        description="Minimum commission per trade",
    )
    max_commission: Optional[Decimal] = Field(
        default=None, ge=Decimal("0"), decimal_places=2, description="Maximum commission cap"
    )
    broker_name: str = Field(
        default="Interactive Brokers Retail", max_length=100, description="Broker name"
    )

    @field_validator(
        "commission_per_share",
        "commission_percentage",
        "fixed_commission_per_trade",
        "min_commission",
        "max_commission",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Optional[Decimal]:
        """Convert numeric values to Decimal for financial precision."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class SlippageConfig(BaseModel):
    """
    Slippage configuration for backtesting (Story 12.5 Task 2).

    Implements multiple slippage models:
    - LIQUIDITY_BASED: Slippage based on average dollar volume (default)
    - FIXED_PERCENTAGE: Fixed slippage percentage for all trades
    - VOLUME_WEIGHTED: Slippage scales with order size vs bar volume

    Attributes:
        slippage_model: Type of slippage calculation
        high_liquidity_threshold: Dollar volume threshold for high liquidity (default $1M)
        high_liquidity_slippage_pct: Slippage for high liquidity stocks (default 0.02%)
        low_liquidity_slippage_pct: Slippage for low liquidity stocks (default 0.05%)
        market_impact_enabled: Enable market impact calculations
        market_impact_threshold_pct: Volume participation threshold (default 10%)
        market_impact_per_increment_pct: Additional slippage per 10% increment (default 0.01%)
        fixed_slippage_pct: Fixed slippage for FIXED_PERCENTAGE model

    Author: Story 12.5 Task 2
    """

    slippage_model: Literal["LIQUIDITY_BASED", "FIXED_PERCENTAGE", "VOLUME_WEIGHTED"] = Field(
        default="LIQUIDITY_BASED", description="Slippage calculation model"
    )
    high_liquidity_threshold: Decimal = Field(
        default=Decimal("1000000"),
        gt=Decimal("0"),
        decimal_places=2,
        description="Avg dollar volume threshold for high liquidity ($1M default)",
    )
    high_liquidity_slippage_pct: Decimal = Field(
        default=Decimal("0.0002"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Slippage for high liquidity (0.02% default)",
    )
    low_liquidity_slippage_pct: Decimal = Field(
        default=Decimal("0.0005"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Slippage for low liquidity (0.05% default)",
    )
    market_impact_enabled: bool = Field(default=True, description="Enable market impact")
    market_impact_threshold_pct: Decimal = Field(
        default=Decimal("0.10"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Volume participation threshold (10% default)",
    )
    market_impact_per_increment_pct: Decimal = Field(
        default=Decimal("0.0001"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Additional slippage per 10% increment (0.01% default)",
    )
    fixed_slippage_pct: Decimal = Field(
        default=Decimal("0.0002"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=8,
        description="Fixed slippage for FIXED_PERCENTAGE model",
    )

    @field_validator(
        "high_liquidity_threshold",
        "high_liquidity_slippage_pct",
        "low_liquidity_slippage_pct",
        "market_impact_threshold_pct",
        "market_impact_per_increment_pct",
        "fixed_slippage_pct",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class BacktestConfig(BaseModel):
    """Configuration for backtesting engine.

    Defines all parameters needed to run a backtest including symbol,
    date range, capital, risk limits, and cost models.

    Extended in Story 12.5 to include comprehensive commission and slippage configs.

    Attributes:
        symbol: Trading symbol to backtest
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital amount
        max_position_size: Maximum position size as fraction of capital (e.g., 0.02 = 2%)
        commission_per_share: Commission cost per share (default $0.005 for IB) - DEPRECATED
        slippage_model: Type of slippage model to use - DEPRECATED
        slippage_percentage: Base slippage percentage (default 0.02% = 0.0002) - DEPRECATED
        commission_config: Commission configuration (Story 12.5)
        slippage_config: Slippage configuration (Story 12.5)
        risk_limits: Risk limit configuration dict
    """

    symbol: str = Field(description="Trading symbol")
    timeframe: str = Field(default="1d", description="Data timeframe")
    start_date: date = Field(description="Backtest start date")
    end_date: date = Field(description="Backtest end date")
    initial_capital: Decimal = Field(
        default=Decimal("100000"), gt=Decimal("0"), description="Starting capital"
    )
    max_position_size: Decimal = Field(
        default=Decimal("0.02"),
        gt=Decimal("0"),
        le=Decimal("1.0"),
        description="Max position size as fraction",
    )
    # Legacy fields (maintain for backward compatibility)
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"), ge=Decimal("0"), description="Commission per share (deprecated)"
    )
    slippage_model: Literal["PERCENTAGE", "FIXED"] = Field(
        default="PERCENTAGE", description="Slippage model type (deprecated)"
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.0002"),
        ge=Decimal("0"),
        description="Base slippage percentage (deprecated)",
    )
    # Story 12.5: New comprehensive configs
    commission_config: Optional[CommissionConfig] = Field(
        default=None, description="Commission configuration (Story 12.5)"
    )
    slippage_config: Optional[SlippageConfig] = Field(
        default=None, description="Slippage configuration (Story 12.5)"
    )
    risk_limits: dict[str, Any] = Field(
        default_factory=lambda: {"max_portfolio_heat": 0.10, "max_campaign_risk": 0.05},
        description="Risk limit configuration",
    )
