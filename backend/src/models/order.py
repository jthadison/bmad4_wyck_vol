"""
Order Models (Story 16.4a)

Generic order and execution models for trading platform integration.
These models define the contract between the system and external trading platforms.

Author: Story 16.4a
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side (buy/sell)."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order execution status."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    """Order time in force."""

    GTC = "GTC"  # Good Till Cancelled
    DAY = "DAY"  # Day Order
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


class Order(BaseModel):
    """
    Generic order for trading platform execution.

    Represents an order to be placed on a trading platform.
    Platform adapters translate this to platform-specific formats.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique order identifier")
    signal_id: Optional[UUID] = Field(
        default=None, description="Reference to signal that generated this order"
    )
    campaign_id: Optional[str] = Field(
        default=None, description="Reference to campaign this order belongs to"
    )
    platform: str = Field(
        description="Target trading platform", examples=["TradingView", "MetaTrader", "Alpaca"]
    )
    symbol: str = Field(
        description="Ticker symbol",
        min_length=1,
        max_length=20,
        pattern=r"^[A-Z0-9\.\/\-]+$",
    )
    side: OrderSide = Field(description="Order side (BUY/SELL)")
    order_type: OrderType = Field(description="Order type")
    quantity: Decimal = Field(description="Order quantity", gt=Decimal("0"))
    limit_price: Optional[Decimal] = Field(
        default=None, description="Limit price (required for LIMIT/STOP_LIMIT orders)"
    )
    stop_price: Optional[Decimal] = Field(
        default=None, description="Stop price (required for STOP/STOP_LIMIT orders)"
    )
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC, description="Order time in force")
    stop_loss: Optional[Decimal] = Field(default=None, description="Attached stop loss price")
    take_profit: Optional[Decimal] = Field(default=None, description="Attached take profit price")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Order creation timestamp"
    )
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current order status")
    platform_order_id: Optional[str] = Field(
        default=None, description="Platform-specific order ID (set after submission)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "signal_id": "789e4567-e89b-12d3-a456-426614174000",
                "platform": "TradingView",
                "symbol": "AAPL",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": "100",
                "limit_price": "150.50",
                "time_in_force": "GTC",
                "stop_loss": "145.00",
                "take_profit": "160.00",
            }
        }
    }


class ExecutionReport(BaseModel):
    """
    Order execution report from trading platform.

    Reports order status updates and fill information from the platform.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique execution report identifier")
    order_id: UUID = Field(description="Reference to Order")
    platform_order_id: str = Field(description="Platform-specific order ID")
    platform: str = Field(description="Trading platform name")
    status: OrderStatus = Field(description="Order status after execution")
    filled_quantity: Decimal = Field(
        default=Decimal("0"), description="Quantity filled", ge=Decimal("0")
    )
    remaining_quantity: Decimal = Field(
        default=Decimal("0"), description="Quantity remaining", ge=Decimal("0")
    )
    average_fill_price: Optional[Decimal] = Field(
        default=None, description="Average fill price (if filled)"
    )
    commission: Optional[Decimal] = Field(default=None, description="Commission charged")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Execution timestamp"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if order rejected/failed"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "456e4567-e89b-12d3-a456-426614174000",
                "order_id": "123e4567-e89b-12d3-a456-426614174000",
                "platform_order_id": "TV-12345",
                "platform": "TradingView",
                "status": "FILLED",
                "filled_quantity": "100",
                "remaining_quantity": "0",
                "average_fill_price": "150.52",
                "commission": "0.50",
            }
        }
    }


class OCOOrder(BaseModel):
    """
    One-Cancels-Other (OCO) order pair.

    Typically used for stop-loss and take-profit orders where execution
    of one automatically cancels the other.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique OCO group identifier")
    primary_order: Order = Field(description="Primary order (typically entry)")
    stop_loss_order: Optional[Order] = Field(default=None, description="Stop loss order")
    take_profit_order: Optional[Order] = Field(default=None, description="Take profit order")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="OCO creation timestamp"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "789e4567-e89b-12d3-a456-426614174000",
                "primary_order": {"symbol": "AAPL", "side": "BUY", "quantity": "100"},
                "stop_loss_order": {
                    "symbol": "AAPL",
                    "side": "SELL",
                    "quantity": "100",
                    "stop_price": "145.00",
                },
                "take_profit_order": {
                    "symbol": "AAPL",
                    "side": "SELL",
                    "quantity": "100",
                    "limit_price": "160.00",
                },
            }
        }
    }
