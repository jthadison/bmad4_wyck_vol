"""
Order Management API Routes (Issue P4-I16).

Provides REST endpoints for viewing, modifying, and cancelling pending orders
across all connected broker adapters (Alpaca, MetaTrader).

Endpoints:
- GET    /api/v1/orders              - List all pending orders across brokers
- GET    /api/v1/orders/{order_id}   - Get specific order status
- DELETE /api/v1/orders/{order_id}   - Cancel an order
- PATCH  /api/v1/orders/{order_id}   - Modify order price/quantity
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user_id
from src.brokers.broker_router import BrokerRouter
from src.models.order import OrderStatus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class PendingOrder(BaseModel):
    """A pending order aggregated from a connected broker."""

    order_id: str = Field(description="Platform order ID")
    internal_order_id: Optional[UUID] = Field(
        default=None, description="Our system order ID if tracked"
    )
    broker: str = Field(description="Broker name (alpaca or mt5)")
    symbol: str = Field(default="", description="Trading symbol")
    side: str = Field(default="", description="buy or sell")
    order_type: str = Field(default="", description="market, limit, stop, stop_limit")
    quantity: Decimal = Field(default=Decimal("0"), description="Total order quantity")
    filled_quantity: Decimal = Field(default=Decimal("0"), description="Filled quantity")
    remaining_quantity: Decimal = Field(default=Decimal("0"), description="Remaining quantity")
    limit_price: Optional[Decimal] = Field(default=None, description="Limit price")
    stop_price: Optional[Decimal] = Field(default=None, description="Stop price")
    status: str = Field(default="pending", description="pending, partial, rejected")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Order creation time"
    )
    campaign_id: Optional[UUID] = Field(default=None, description="Linked campaign ID")
    is_oco: bool = Field(default=False, description="Part of OCO group")
    oco_group_id: Optional[str] = Field(default=None, description="OCO group identifier")


class PendingOrdersResponse(BaseModel):
    """Response for list pending orders endpoint."""

    orders: list[PendingOrder]
    total: int
    brokers_connected: dict[str, bool]


class OrderModifyRequest(BaseModel):
    """Request body for modifying a pending order."""

    limit_price: Optional[Decimal] = Field(default=None, description="New limit price")
    stop_price: Optional[Decimal] = Field(default=None, description="New stop price")
    quantity: Optional[Decimal] = Field(default=None, description="New quantity")


class OrderModifyResponse(BaseModel):
    """Response for order modification."""

    success: bool
    message: str
    order_id: str
    replacement_needed: bool = Field(
        default=True,
        description="Whether a replacement order must be placed manually",
    )


class OrderCancelResponse(BaseModel):
    """Response for order cancellation."""

    success: bool
    message: str
    order_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_broker_router(request: Request) -> BrokerRouter:
    """Get BrokerRouter from app state."""
    broker_router = getattr(request.app.state, "broker_router", None)
    if broker_router is None:
        raise HTTPException(
            status_code=503,
            detail="Broker infrastructure not initialized",
        )
    return broker_router


def _map_status(status: OrderStatus) -> str:
    """Map internal OrderStatus to simplified pending order status string."""
    if status in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
        return "pending"
    if status == OrderStatus.PARTIAL_FILL:
        return "partial"
    if status == OrderStatus.REJECTED:
        return "rejected"
    if status == OrderStatus.FILLED:
        return "filled"
    if status == OrderStatus.CANCELLED:
        return "cancelled"
    if status == OrderStatus.EXPIRED:
        return "expired"
    logger.warning("unknown_order_status", status=str(status))
    return "unknown"


async def _fetch_orders_from_adapter(
    adapter_name: str,
    adapter: object,
) -> list[PendingOrder]:
    """Fetch open orders from a single adapter and convert to PendingOrder list."""
    orders: list[PendingOrder] = []
    try:
        if not adapter.is_connected():  # type: ignore[union-attr]
            logger.debug("orders_adapter_not_connected", adapter=adapter_name)
            return orders

        reports = await adapter.get_open_orders()  # type: ignore[union-attr]
        for report in reports:
            pending = PendingOrder(
                order_id=report.platform_order_id,
                internal_order_id=None,
                broker=adapter_name,
                symbol="",  # ExecutionReport doesn't carry symbol
                side="",
                order_type="",
                quantity=report.filled_quantity + report.remaining_quantity,
                filled_quantity=report.filled_quantity,
                remaining_quantity=report.remaining_quantity,
                limit_price=None,
                stop_price=None,
                status=_map_status(report.status),
                created_at=report.timestamp,
                campaign_id=None,
                is_oco=False,
                oco_group_id=None,
            )
            orders.append(pending)
    except Exception as exc:
        logger.error("orders_fetch_failed", adapter=adapter_name, error=str(exc))
    return orders


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=PendingOrdersResponse)
async def list_pending_orders(
    request: Request,
    _user_id: UUID = Depends(get_current_user_id),
) -> PendingOrdersResponse:
    """
    List all pending orders across all connected brokers.

    Aggregates open orders from Alpaca and MetaTrader adapters.
    Brokers that are not connected return empty lists gracefully.
    """
    broker_router = _get_broker_router(request)

    all_orders: list[PendingOrder] = []
    brokers_connected: dict[str, bool] = {}

    # Build list of connected adapters to fetch concurrently
    fetch_tasks: list[tuple[str, object]] = []
    for name, adapter in [
        ("alpaca", broker_router._alpaca_adapter),
        ("mt5", broker_router._mt5_adapter),
    ]:
        if adapter is None:
            brokers_connected[name] = False
            continue
        brokers_connected[name] = adapter.is_connected()
        fetch_tasks.append((name, adapter))

    # Fetch from all connected adapters concurrently
    # _fetch_orders_from_adapter catches exceptions internally and returns empty list
    if fetch_tasks:
        results = await asyncio.gather(
            *(_fetch_orders_from_adapter(name, adapter) for name, adapter in fetch_tasks),
        )
        for result in results:
            all_orders.extend(result)

    logger.info("orders_list", total=len(all_orders), brokers=brokers_connected)

    return PendingOrdersResponse(
        orders=all_orders,
        total=len(all_orders),
        brokers_connected=brokers_connected,
    )


@router.get("/{order_id}", response_model=PendingOrder)
async def get_order(
    request: Request,
    order_id: str,
    _user_id: UUID = Depends(get_current_user_id),
) -> PendingOrder:
    """
    Get status of a specific order by platform order ID.

    Searches across all connected brokers.
    """
    broker_router = _get_broker_router(request)

    # Try each adapter
    for name, adapter in [
        ("alpaca", broker_router._alpaca_adapter),
        ("mt5", broker_router._mt5_adapter),
    ]:
        if adapter is None or not adapter.is_connected():
            continue
        try:
            report = await adapter.get_order_status(order_id)
            return PendingOrder(
                order_id=report.platform_order_id,
                broker=name,
                quantity=report.filled_quantity + report.remaining_quantity,
                filled_quantity=report.filled_quantity,
                remaining_quantity=report.remaining_quantity,
                status=_map_status(report.status),
                created_at=report.timestamp,
            )
        except ValueError:
            continue
        except Exception as exc:
            logger.warning("order_get_failed", adapter=name, error=str(exc))
            continue

    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@router.delete("/{order_id}", response_model=OrderCancelResponse)
async def cancel_order(
    request: Request,
    order_id: str,
    _user_id: UUID = Depends(get_current_user_id),
) -> OrderCancelResponse:
    """
    Cancel a pending order.

    Searches across all connected brokers and cancels on the broker where found.
    """
    broker_router = _get_broker_router(request)

    errors: list[str] = []
    for name, adapter in [
        ("alpaca", broker_router._alpaca_adapter),
        ("mt5", broker_router._mt5_adapter),
    ]:
        if adapter is None or not adapter.is_connected():
            continue
        try:
            await adapter.cancel_order(order_id)
            logger.info("order_cancelled", order_id=order_id, broker=name)
            return OrderCancelResponse(
                success=True,
                message=f"Order {order_id} cancelled on {name}",
                order_id=order_id,
            )
        except ValueError:
            continue
        except Exception as exc:
            logger.error("order_cancel_failed", adapter=name, error=str(exc))
            errors.append(name)

    if errors:
        raise HTTPException(
            status_code=500,
            detail=f"Cancel order operation failed for {', '.join(errors)}. Please try again.",
        )

    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@router.patch("/{order_id}", response_model=OrderModifyResponse)
async def modify_order(
    order_id: str,
    body: OrderModifyRequest,
    _user_id: UUID = Depends(get_current_user_id),
) -> OrderModifyResponse:
    """
    Modify a pending order's price or quantity.

    Not currently supported. Cancel the order and place a new one instead.
    """
    raise HTTPException(
        status_code=501,
        detail="Order modification is not supported. Cancel and place a new order.",
    )
