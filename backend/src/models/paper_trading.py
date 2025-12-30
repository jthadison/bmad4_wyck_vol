"""
Paper Trading Models (Story 12.8)

Pydantic models for paper trading mode that simulates live trading without real capital.
These models track virtual positions, trades, and account state.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class PaperTradingConfig(BaseModel):
    """
    Configuration for paper trading mode.

    Defines parameters for simulating realistic trade execution including
    slippage and commission costs.
    """

    enabled: bool = Field(default=False, description="Toggle paper trading mode on/off")
    starting_capital: Decimal = Field(
        default=Decimal("100000.00"), description="Virtual capital to start with", ge=Decimal("0")
    )
    commission_per_share: Decimal = Field(
        default=Decimal("0.005"),
        description="Commission cost per share (default: Interactive Brokers rate)",
        ge=Decimal("0"),
    )
    slippage_percentage: Decimal = Field(
        default=Decimal("0.02"),
        description="Slippage as percentage (default: 0.02% for liquid stocks)",
        ge=Decimal("0"),
    )
    use_realistic_fills: bool = Field(
        default=True, description="Apply slippage and commission to fills"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when config was created",
    )

    @field_validator("starting_capital", "commission_per_share", "slippage_percentage")
    @classmethod
    def validate_decimal_precision(cls, v: Decimal) -> Decimal:
        """Ensure Decimal values have proper precision (max 8 decimal places)."""
        if v is None:
            return v
        # Quantize to 8 decimal places
        return v.quantize(Decimal("0.00000001"))

    @field_validator("created_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware UTC."""
        if v is None:
            return v
        if v.tzinfo is None:
            # Assume UTC if naive
            import pytz

            return pytz.UTC.localize(v)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "enabled": True,
                "starting_capital": "100000.00",
                "commission_per_share": "0.005",
                "slippage_percentage": "0.02",
                "use_realistic_fills": True,
                "created_at": "2025-01-15T10:30:00Z",
            }
        }
    }


class PaperPosition(BaseModel):
    """
    Virtual open position in paper trading mode.

    Tracks entry details, targets, stops, and mark-to-market P&L.
    Updated in real-time as market prices change.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    signal_id: UUID = Field(description="Reference to Signal that generated this position")
    symbol: str = Field(description="Ticker symbol", min_length=1, max_length=10)
    entry_time: datetime = Field(description="UTC timestamp when position opened")
    entry_price: Decimal = Field(
        description="Virtual fill price (includes slippage)", gt=Decimal("0")
    )
    quantity: Decimal = Field(description="Number of shares", gt=Decimal("0"))
    stop_loss: Decimal = Field(description="Stop loss price level", gt=Decimal("0"))
    target_1: Decimal = Field(description="First profit target", gt=Decimal("0"))
    target_2: Decimal = Field(description="Second profit target", gt=Decimal("0"))
    current_price: Decimal = Field(description="Latest market price", gt=Decimal("0"))
    unrealized_pnl: Decimal = Field(description="Mark-to-market P&L (not yet realized)")
    status: Literal["OPEN", "STOPPED", "TARGET_1_HIT", "TARGET_2_HIT", "CLOSED"] = Field(
        default="OPEN", description="Position status"
    )
    commission_paid: Decimal = Field(description="Total commissions for entry", ge=Decimal("0"))
    slippage_cost: Decimal = Field(description="Total slippage cost for entry", ge=Decimal("0"))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp of last update"
    )

    @field_validator(
        "entry_price",
        "quantity",
        "stop_loss",
        "target_1",
        "target_2",
        "current_price",
        "unrealized_pnl",
        "commission_paid",
        "slippage_cost",
    )
    @classmethod
    def validate_decimal_precision(cls, v: Decimal) -> Decimal:
        """Ensure Decimal values have proper precision (max 8 decimal places)."""
        if v is None:
            return v
        return v.quantize(Decimal("0.00000001"))

    @field_validator("entry_time", "created_at", "updated_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware UTC."""
        if v is None:
            return v
        if v.tzinfo is None:
            import pytz

            return pytz.UTC.localize(v)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "signal_id": "660e8400-e29b-41d4-a716-446655440001",
                "symbol": "AAPL",
                "entry_time": "2025-01-15T14:30:00Z",
                "entry_price": "150.03",
                "quantity": "100",
                "stop_loss": "148.00",
                "target_1": "152.00",
                "target_2": "154.00",
                "current_price": "151.50",
                "unrealized_pnl": "147.00",
                "status": "OPEN",
                "commission_paid": "0.50",
                "slippage_cost": "3.00",
                "created_at": "2025-01-15T14:30:00Z",
                "updated_at": "2025-01-15T15:00:00Z",
            }
        }
    }


class PaperTrade(BaseModel):
    """
    Closed trade record from paper trading.

    Represents a completed position with realized P&L and exit details.
    Stored for performance analysis and comparison to backtests.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    position_id: UUID = Field(description="Reference to PaperPosition that was closed")
    signal_id: UUID = Field(description="Reference to originating Signal")
    symbol: str = Field(description="Ticker symbol", min_length=1, max_length=10)
    entry_time: datetime = Field(description="UTC timestamp of entry")
    entry_price: Decimal = Field(description="Entry fill price", gt=Decimal("0"))
    exit_time: datetime = Field(description="UTC timestamp of exit")
    exit_price: Decimal = Field(description="Exit fill price", gt=Decimal("0"))
    quantity: Decimal = Field(description="Number of shares", gt=Decimal("0"))
    realized_pnl: Decimal = Field(description="Actual P&L after all costs")
    r_multiple_achieved: Decimal = Field(description="Actual R-multiple vs planned R")
    commission_total: Decimal = Field(description="Entry + exit commissions", ge=Decimal("0"))
    slippage_total: Decimal = Field(description="Entry + exit slippage costs", ge=Decimal("0"))
    exit_reason: Literal["STOP_LOSS", "TARGET_1", "TARGET_2", "MANUAL", "EXPIRED"] = Field(
        description="Why position was closed"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp"
    )

    @field_validator(
        "entry_price",
        "exit_price",
        "quantity",
        "realized_pnl",
        "r_multiple_achieved",
        "commission_total",
        "slippage_total",
    )
    @classmethod
    def validate_decimal_precision(cls, v: Decimal) -> Decimal:
        """Ensure Decimal values have proper precision (max 8 decimal places)."""
        if v is None:
            return v
        return v.quantize(Decimal("0.00000001"))

    @field_validator("entry_time", "exit_time", "created_at")
    @classmethod
    def validate_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware UTC."""
        if v is None:
            return v
        if v.tzinfo is None:
            import pytz

            return pytz.UTC.localize(v)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "position_id": "550e8400-e29b-41d4-a716-446655440000",
                "signal_id": "660e8400-e29b-41d4-a716-446655440001",
                "symbol": "AAPL",
                "entry_time": "2025-01-15T14:30:00Z",
                "entry_price": "150.03",
                "exit_time": "2025-01-15T16:00:00Z",
                "exit_price": "152.05",
                "quantity": "100",
                "realized_pnl": "198.50",
                "r_multiple_achieved": "1.52",
                "commission_total": "1.00",
                "slippage_total": "5.00",
                "exit_reason": "TARGET_1",
                "created_at": "2025-01-15T16:00:00Z",
            }
        }
    }


class PaperAccount(BaseModel):
    """
    Virtual account for paper trading.

    Singleton account tracking capital, equity, performance metrics.
    Updated in real-time as positions are opened/closed and prices change.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier (singleton for system)")
    starting_capital: Decimal = Field(description="Initial virtual capital", gt=Decimal("0"))
    current_capital: Decimal = Field(description="Cash available for trading", ge=Decimal("0"))
    equity: Decimal = Field(description="Cash + unrealized P&L of open positions", ge=Decimal("0"))
    total_realized_pnl: Decimal = Field(
        default=Decimal("0"), description="Sum of all closed trades P&L"
    )
    total_unrealized_pnl: Decimal = Field(
        default=Decimal("0"), description="Sum of open position P&L"
    )
    total_commission_paid: Decimal = Field(
        default=Decimal("0"), description="Cumulative commissions", ge=Decimal("0")
    )
    total_slippage_cost: Decimal = Field(
        default=Decimal("0"), description="Cumulative slippage costs", ge=Decimal("0")
    )
    total_trades: int = Field(default=0, description="Number of closed trades", ge=0)
    winning_trades: int = Field(default=0, description="Number of profitable trades", ge=0)
    losing_trades: int = Field(default=0, description="Number of losing trades", ge=0)
    win_rate: Decimal = Field(
        default=Decimal("0"),
        description="Percentage of winning trades",
        ge=Decimal("0"),
        le=Decimal("100"),
    )
    average_r_multiple: Decimal = Field(
        default=Decimal("0"), description="Average R-multiple across all trades"
    )
    max_drawdown: Decimal = Field(
        default=Decimal("0"),
        description="Maximum peak-to-trough equity decline (%)",
        ge=Decimal("0"),
        le=Decimal("100"),
    )
    current_heat: Decimal = Field(
        default=Decimal("0"),
        description="Percentage of capital at risk in open positions",
        ge=Decimal("0"),
        le=Decimal("100"),
    )
    paper_trading_start_date: Optional[datetime] = Field(
        default=None, description="UTC timestamp when paper trading first enabled"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp of last update"
    )

    @field_validator(
        "starting_capital",
        "current_capital",
        "equity",
        "total_realized_pnl",
        "total_unrealized_pnl",
        "total_commission_paid",
        "total_slippage_cost",
        "win_rate",
        "average_r_multiple",
        "max_drawdown",
        "current_heat",
    )
    @classmethod
    def validate_decimal_precision(cls, v: Decimal) -> Decimal:
        """Ensure Decimal values have proper precision (max 8 decimal places)."""
        if v is None:
            return v
        return v.quantize(Decimal("0.00000001"))

    @field_validator("paper_trading_start_date", "created_at", "updated_at")
    @classmethod
    def validate_utc_timestamp(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure timestamp is timezone-aware UTC."""
        if v is None:
            return v
        if v.tzinfo is None:
            import pytz

            return pytz.UTC.localize(v)
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "880e8400-e29b-41d4-a716-446655440003",
                "starting_capital": "100000.00",
                "current_capital": "98500.00",
                "equity": "99200.00",
                "total_realized_pnl": "500.00",
                "total_unrealized_pnl": "700.00",
                "total_commission_paid": "25.50",
                "total_slippage_cost": "74.50",
                "total_trades": 15,
                "winning_trades": 9,
                "losing_trades": 6,
                "win_rate": "60.00",
                "average_r_multiple": "1.75",
                "max_drawdown": "3.25",
                "current_heat": "8.50",
                "paper_trading_start_date": "2025-01-01T00:00:00Z",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-15T16:00:00Z",
            }
        }
    }
