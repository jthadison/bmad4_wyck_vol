"""
Live Position Management endpoints (Issue P4-I15).

Action-oriented endpoints for managing open positions:
- GET /api/v1/live-positions - List all open positions with enriched data
- PATCH /api/v1/live-positions/{position_id}/stop-loss - Adjust stop loss
- POST /api/v1/live-positions/{position_id}/partial-exit - Partial exit

Note: Currently long-only. PositionModel has no `side` field and pattern_type
is constrained to SPRING/SOS/LPS (all long entries). UTAD short support
requires adding a `side` column to the positions table first.

Note: Single-tenant system. PositionModel and CampaignModel have no user_id
field, so positions are not filtered by user. All authenticated users see
all positions. Multi-tenant filtering requires schema changes.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id, get_db_session
from src.models.order import Order, OrderSide, OrderType

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/live-positions", tags=["live-positions"])

# Default account equity used when broker is not connected.
# TODO: Replace with real account equity from broker adapter once
# broker connectivity is guaranteed in all partial-exit paths.
_DEFAULT_ACCOUNT_EQUITY = Decimal("100000")


# ---------------------------------------------------------------------------
# Response / Request schemas
# ---------------------------------------------------------------------------


class EnrichedPosition(BaseModel):
    """Position with computed risk/PnL fields for live management."""

    id: str
    campaign_id: str
    signal_id: str
    symbol: str
    timeframe: str
    pattern_type: str
    entry_price: str
    current_price: Optional[str]
    stop_loss: str
    shares: str
    current_pnl: Optional[str]
    status: str
    entry_date: str

    # Enriched fields
    stop_distance_pct: Optional[str] = None
    r_multiple: Optional[str] = None
    dollars_at_risk: Optional[str] = None
    pnl_pct: Optional[str] = None


class StopLossUpdate(BaseModel):
    """Request body for stop-loss adjustment."""

    new_stop: str = Field(..., description="New stop loss price as decimal string")


class PartialExitRequest(BaseModel):
    """Request body for partial exit."""

    exit_pct: float = Field(..., gt=0, le=100, description="Percentage of position to exit (1-100)")
    limit_price: Optional[str] = Field(None, description="Limit price (None = market order)")


class PartialExitResponse(BaseModel):
    """Response for partial exit request."""

    order_id: str
    shares_to_exit: str
    order_type: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enrich_position(pos_model: object) -> EnrichedPosition:
    """Build an EnrichedPosition from a DB model row."""
    entry_price = Decimal(str(pos_model.entry_price))  # type: ignore[union-attr]
    stop_loss = Decimal(str(pos_model.stop_loss))  # type: ignore[union-attr]
    shares = Decimal(str(pos_model.shares))  # type: ignore[union-attr]
    current_price_raw = pos_model.current_price  # type: ignore[union-attr]
    current_pnl_raw = pos_model.current_pnl  # type: ignore[union-attr]

    current_price = Decimal(str(current_price_raw)) if current_price_raw is not None else None
    current_pnl = Decimal(str(current_pnl_raw)) if current_pnl_raw is not None else None

    # Computed fields
    stop_distance_pct: Optional[str] = None
    r_multiple: Optional[str] = None
    pnl_pct: Optional[str] = None

    # Use current price for dollars_at_risk (current exposure),
    # falling back to entry price when current price is unavailable.
    risk_reference_price = current_price if current_price is not None else entry_price
    risk_per_share = risk_reference_price - stop_loss
    dollars_at_risk = risk_per_share * shares

    # Initial risk per share for R-multiple calculation
    initial_risk_per_share = entry_price - stop_loss

    if current_price is not None and current_price > 0:
        stop_distance_pct = str(
            ((current_price - stop_loss) / current_price * Decimal("100")).quantize(Decimal("0.01"))
        )

    if current_pnl is not None and initial_risk_per_share > 0 and shares > 0:
        r_multiple = str(
            (current_pnl / (initial_risk_per_share * shares)).quantize(Decimal("0.01"))
        )

    if current_pnl is not None and entry_price > 0 and shares > 0:
        pnl_pct = str(
            (current_pnl / (entry_price * shares) * Decimal("100")).quantize(Decimal("0.01"))
        )

    return EnrichedPosition(
        id=str(pos_model.id),  # type: ignore[union-attr]
        campaign_id=str(pos_model.campaign_id),  # type: ignore[union-attr]
        signal_id=str(pos_model.signal_id),  # type: ignore[union-attr]
        symbol=pos_model.symbol,  # type: ignore[union-attr]
        timeframe=pos_model.timeframe,  # type: ignore[union-attr]
        pattern_type=pos_model.pattern_type,  # type: ignore[union-attr]
        entry_price=str(entry_price),
        current_price=str(current_price) if current_price is not None else None,
        stop_loss=str(stop_loss),
        shares=str(shares),
        current_pnl=str(current_pnl) if current_pnl is not None else None,
        status=pos_model.status,  # type: ignore[union-attr]
        entry_date=pos_model.entry_date.isoformat() if pos_model.entry_date else "",  # type: ignore[union-attr]
        stop_distance_pct=stop_distance_pct,
        r_multiple=r_multiple,
        dollars_at_risk=str(dollars_at_risk.quantize(Decimal("0.01"))),
        pnl_pct=pnl_pct,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[EnrichedPosition])
async def get_live_positions(
    db_session: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> list[EnrichedPosition]:
    """
    List all open positions across campaigns with enriched risk data.

    Returns positions with computed fields:
    - stop_distance_pct: distance from current price to stop
    - r_multiple: unrealised R-multiple
    - dollars_at_risk: absolute dollar risk (based on current price)
    - pnl_pct: unrealized P&L as percentage

    Note: Single-tenant - returns all open positions regardless of user.
    See module docstring for multi-tenant considerations.
    """
    try:
        from src.repositories.models import PositionModel

        result = await db_session.execute(
            select(PositionModel).where(PositionModel.status == "OPEN")
        )
        rows = result.scalars().all()

        positions = [_enrich_position(row) for row in rows]

        logger.info(
            "live_positions_retrieved",
            count=len(positions),
        )

        return positions

    except Exception as e:
        logger.error("live_positions_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


@router.patch("/{position_id}/stop-loss", response_model=EnrichedPosition)
async def update_stop_loss(
    position_id: UUID,
    body: StopLossUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> EnrichedPosition:
    """
    Adjust stop loss for an open position.

    Wyckoff rules enforced (long positions only):
    - Stop must be above zero
    - Stop must be below entry price
    - Stop can only move up (never move stop down)
    """
    try:
        new_stop = Decimal(body.new_stop)
    except (InvalidOperation, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stop price: {body.new_stop}",
        ) from e

    if new_stop <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stop loss must be greater than zero.",
        )

    try:
        from src.repositories.models import PositionModel

        # Row-level lock to prevent concurrent stop-loss updates
        result = await db_session.execute(
            select(PositionModel).where(PositionModel.id == position_id).with_for_update()
        )
        pos = result.scalar_one_or_none()

        if pos is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Position not found: {position_id}",
            )

        if pos.status != "OPEN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot adjust stop on a closed position.",
            )

        entry_price = Decimal(str(pos.entry_price))
        current_stop = Decimal(str(pos.stop_loss))

        # Wyckoff rule: stop must be below entry price for longs
        if new_stop >= entry_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stop loss ({new_stop}) must be below entry price ({entry_price}).",
            )

        # Wyckoff rule: never move stop down for long positions
        if new_stop < current_stop:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot move stop down from {current_stop} to {new_stop}. "
                "Stops can only trail up for long positions.",
            )

        pos.stop_loss = new_stop
        await db_session.commit()
        await db_session.refresh(pos)

        logger.info(
            "stop_loss_updated",
            position_id=str(position_id),
            old_stop=str(current_stop),
            new_stop=str(new_stop),
        )

        return _enrich_position(pos)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "stop_loss_update_error",
            position_id=str(position_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e


@router.post("/{position_id}/partial-exit", response_model=PartialExitResponse)
async def partial_exit(
    position_id: UUID,
    body: PartialExitRequest,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    _user_id: UUID = Depends(get_current_user_id),
) -> PartialExitResponse:
    """
    Execute a partial exit on an open position.

    Calculates shares to exit based on exit_pct, creates a sell order,
    and persists the updated share count to the database.
    """
    try:
        from src.repositories.models import PositionModel

        # Row-level lock to prevent concurrent partial exits from over-exiting
        result = await db_session.execute(
            select(PositionModel).where(PositionModel.id == position_id).with_for_update()
        )
        pos = result.scalar_one_or_none()

        if pos is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Position not found: {position_id}",
            )

        if pos.status != "OPEN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot exit a closed position.",
            )

        shares = Decimal(str(pos.shares))
        exit_pct = Decimal(str(body.exit_pct))
        shares_to_exit = (shares * exit_pct / Decimal("100")).quantize(Decimal("1"))

        if shares_to_exit <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Calculated shares to exit is zero. Position too small for this percentage.",
            )

        if shares_to_exit > shares:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot exit {shares_to_exit} shares; only {shares} remaining.",
            )

        # Determine order type
        limit_price: Optional[Decimal] = None
        order_type = OrderType.MARKET
        if body.limit_price is not None:
            try:
                limit_price = Decimal(body.limit_price)
                order_type = OrderType.LIMIT
            except (InvalidOperation, ValueError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid limit price: {body.limit_price}",
                ) from e

        # Build the sell order
        order = Order(
            symbol=pos.symbol,
            side=OrderSide.SELL,
            order_type=order_type,
            quantity=shares_to_exit,
            limit_price=limit_price,
            platform="system",
            campaign_id=str(pos.campaign_id),
        )

        logger.info(
            "partial_exit_order_created",
            position_id=str(position_id),
            exit_pct=str(exit_pct),
            shares_to_exit=str(shares_to_exit),
            order_type=order_type.value,
            order_id=str(order.id),
        )

        # Route order through broker if available
        broker_router = getattr(request.app.state, "broker_router", None)
        if broker_router is not None:
            from src.risk_management.execution_risk_gate import PortfolioState

            # Try to fetch real account equity from broker
            account_equity = _DEFAULT_ACCOUNT_EQUITY
            try:
                for adapter in [
                    getattr(broker_router, "_alpaca_adapter", None),
                    getattr(broker_router, "_mt5_adapter", None),
                ]:
                    if adapter is not None and adapter.is_connected():
                        account_info = await adapter.get_account_info()
                        balance = account_info.get("balance")
                        if balance is not None:
                            account_equity = Decimal(str(balance))
                            break
            except Exception:
                logger.warning(
                    "partial_exit_equity_fetch_failed",
                    position_id=str(position_id),
                    fallback_equity=str(_DEFAULT_ACCOUNT_EQUITY),
                )

            # Partial exits are risk-reducing; use minimal placeholder risk values
            portfolio_state = PortfolioState(account_equity=account_equity)
            trade_risk_pct = Decimal("0.01")

            execution_report = await broker_router.route_order(
                order, portfolio_state, trade_risk_pct
            )

            logger.info(
                "partial_exit_order_routed",
                position_id=str(position_id),
                order_id=str(order.id),
                broker_status=str(execution_report.status),
            )

            # Persist updated share count after successful broker routing
            remaining = shares - shares_to_exit
            pos.shares = remaining
            if remaining <= 0:
                pos.status = "CLOSED"
            await db_session.commit()

            return PartialExitResponse(
                order_id=str(order.id),
                shares_to_exit=str(shares_to_exit),
                order_type=order_type.value,
                status=str(execution_report.status.value),
                message=f"Partial exit order routed for {shares_to_exit} shares ({exit_pct}%) of {pos.symbol}",
            )

        # No broker configured - still persist the share decrement
        remaining = shares - shares_to_exit
        pos.shares = remaining
        if remaining <= 0:
            pos.status = "CLOSED"
        await db_session.commit()

        logger.warning(
            "partial_exit_order_not_routed",
            position_id=str(position_id),
            order_id=str(order.id),
            reason="broker_router_not_configured",
        )

        return PartialExitResponse(
            order_id=str(order.id),
            shares_to_exit=str(shares_to_exit),
            order_type=order_type.value,
            status="PENDING",
            message=f"Partial exit order created for {shares_to_exit} shares ({exit_pct}%) of {pos.symbol} - awaiting broker configuration",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "partial_exit_error",
            position_id=str(position_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        ) from e
