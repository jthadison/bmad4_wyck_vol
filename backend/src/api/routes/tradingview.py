"""
TradingView Webhook API Routes (Story 16.4a, 23.7)

API endpoints for receiving TradingView alert webhooks.
Handles webhook signature verification, order creation, broker routing,
and WebSocket broadcast of order events.

Author: Story 16.4a, Story 23.7
"""

import asyncio
import json
import time
from collections import deque
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from src.api.websocket import manager as ws_manager
from src.brokers.broker_router import BrokerRouter
from src.brokers.order_builder import OrderBuilder
from src.brokers.tradingview_adapter import TradingViewAdapter
from src.config import settings
from src.models.order import OrderStatus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/tradingview", tags=["TradingView"])


# Initialize TradingView adapter
# Webhook secret should be configured in settings
tradingview_adapter = TradingViewAdapter(
    webhook_secret=getattr(settings, "TRADINGVIEW_WEBHOOK_SECRET", None)
)

order_builder = OrderBuilder(default_platform="TradingView")

# In-memory order audit log with bounded size (Story 23.7)
# Uses deque(maxlen=10000) to prevent unbounded memory growth.
# TODO(Story 23.8+): Replace with database persistence using the Order ORM model
# before enabling auto_execute_orders in production. In-memory buffer is acceptable
# only for development/testing. Orders will be lost on restart.
order_audit_log: deque[dict[str, Any]] = deque(maxlen=10000)

# Broker router instance (adapters are None by default; set via configure_broker_router)
broker_router = BrokerRouter()

# Async-safe per-symbol rate limiter: tracks (symbol -> list of timestamps)
# Uses asyncio.Lock to prevent race conditions under concurrent async requests.
# Max 10 orders per minute per symbol
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_tracker: dict[str, list[float]] = {}
_rate_limit_lock = asyncio.Lock()


async def _check_rate_limit(symbol: str) -> bool:
    """
    Check if a symbol has exceeded the per-symbol rate limit.

    Thread-safe for async contexts using asyncio.Lock.

    Args:
        symbol: Trading symbol

    Returns:
        True if within limit, False if rate limit exceeded
    """
    async with _rate_limit_lock:
        now = time.monotonic()
        timestamps = _rate_limit_tracker.get(symbol, [])

        # Remove timestamps outside the window
        cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
        timestamps = [t for t in timestamps if t > cutoff]

        # Prune empty symbol keys to prevent slow memory leak
        if not timestamps and symbol in _rate_limit_tracker:
            del _rate_limit_tracker[symbol]

        if len(timestamps) >= _RATE_LIMIT_MAX:
            _rate_limit_tracker[symbol] = timestamps
            return False

        timestamps.append(now)
        _rate_limit_tracker[symbol] = timestamps
        return True


def configure_broker_router(router_instance: BrokerRouter) -> None:
    """
    Configure the module-level broker router with live adapters.

    Called during application startup to inject configured broker adapters.

    Args:
        router_instance: Configured BrokerRouter with adapters
    """
    global broker_router
    broker_router = router_instance
    logger.info("tradingview_broker_router_configured")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    x_tradingview_signature: Optional[str] = Header(None, alias="X-TradingView-Signature"),
) -> dict:
    """
    Receive TradingView alert webhook.

    TradingView sends POST requests to this endpoint when alerts trigger.
    Webhook payload should contain order details.

    Expected webhook format:
    ```json
    {
        "symbol": "AAPL",
        "action": "buy",
        "order_type": "limit",
        "quantity": 100,
        "limit_price": 150.50,
        "stop_loss": 145.00,
        "take_profit": 160.00
    }
    ```

    Args:
        request: FastAPI request object
        x_tradingview_signature: Webhook signature header (optional)

    Returns:
        Dict with order creation status

    Raises:
        HTTPException: If webhook verification fails or payload invalid
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        body_str = body.decode("utf-8")

        # Security (C-3): When auto-execution is enabled, ALWAYS require signature
        # and verify that a webhook secret is actually configured
        if settings.auto_execute_orders:
            if not tradingview_adapter.webhook_secret:
                logger.error(
                    "tradingview_webhook_secret_not_configured",
                    message="Cannot auto-execute without webhook secret configured",
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Auto-execution requires TRADINGVIEW_WEBHOOK_SECRET to be configured",
                )
            if not x_tradingview_signature:
                logger.warning(
                    "tradingview_webhook_signature_required",
                    message="Signature required when auto-execution is enabled",
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Webhook signature required when auto-execution is enabled",
                )

        # Verify webhook signature if provided
        if x_tradingview_signature:
            is_valid = tradingview_adapter.verify_webhook_signature(
                payload=body_str, signature=x_tradingview_signature
            )
            if not is_valid:
                logger.warning("tradingview_webhook_signature_invalid")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature",
                )

        # Parse JSON payload from already-read body (avoid double parsing)
        payload = json.loads(body_str)

        # Parse webhook into Order
        order = tradingview_adapter.parse_webhook(payload)

        # Rate limit check (M-1): max 10 orders per minute per symbol
        if not await _check_rate_limit(order.symbol):
            logger.warning(
                "tradingview_webhook_rate_limited",
                symbol=order.symbol,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for symbol {order.symbol}: "
                f"max {_RATE_LIMIT_MAX} orders per {_RATE_LIMIT_WINDOW_SECONDS}s",
            )

        logger.info(
            "tradingview_webhook_received",
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=float(order.quantity),
        )

        # Store order in audit trail
        order_record: dict[str, Any] = {
            "id": str(order.id),
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "quantity": float(order.quantity),
            "limit_price": float(order.limit_price) if order.limit_price else None,
            "stop_loss": float(order.stop_loss) if order.stop_loss else None,
            "take_profit": float(order.take_profit) if order.take_profit else None,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "source": "tradingview_webhook",
        }
        order_audit_log.append(order_record)

        logger.info(
            "tradingview_order_persisted",
            order_id=str(order.id),
            audit_log_size=len(order_audit_log),
        )

        # Execute order on broker if auto-execution is enabled
        execution_report = None
        execution_failed = False
        if settings.auto_execute_orders:
            try:
                execution_report = await broker_router.route_order(order)
                order_record["status"] = execution_report.status
                order_record["platform_order_id"] = execution_report.platform_order_id
                order_record["platform"] = execution_report.platform

                if execution_report.error_message:
                    order_record["error_message"] = execution_report.error_message

                logger.info(
                    "tradingview_order_executed",
                    order_id=str(order.id),
                    platform=execution_report.platform,
                    status=execution_report.status,
                )
            except Exception as exec_err:
                execution_failed = True
                logger.error(
                    "tradingview_order_execution_failed",
                    order_id=str(order.id),
                    error=str(exec_err),
                )
                order_record["status"] = OrderStatus.REJECTED
                order_record["error_message"] = str(exec_err)

        # Determine WebSocket event type
        ws_event_type = "order:submitted"
        if execution_failed:
            ws_event_type = "order:rejected"
        elif execution_report is not None:
            if execution_report.status in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILL):
                ws_event_type = "order:filled"
            elif execution_report.status == OrderStatus.REJECTED:
                ws_event_type = "order:rejected"

        await ws_manager.emit_order_event(ws_event_type, order_record)

        return {
            "status": "success",
            "message": "Webhook received and order created",
            "order": {
                "id": str(order.id),
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": float(order.quantity),
                "status": order_record["status"],
            },
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("tradingview_webhook_parse_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook payload: {e}"
        ) from e
    except Exception as e:
        logger.error("tradingview_webhook_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        ) from e


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict:
    """
    Health check endpoint for TradingView webhook service.

    Returns:
        Dict with service status
    """
    return {
        "status": "healthy",
        "service": "TradingView Webhook",
        "adapter_connected": tradingview_adapter.is_connected(),
    }


@router.post("/test", status_code=status.HTTP_200_OK)
async def test_webhook(payload: dict) -> dict:
    """
    Test endpoint for webhook integration.

    Allows testing webhook parsing without signature verification.
    Disabled in production for security.

    Args:
        payload: Test webhook payload

    Returns:
        Dict with parsed order details

    Raises:
        HTTPException: 403 if called in production environment
    """
    # Security: Disable test endpoint in production
    if settings.environment == "production":
        logger.warning("test_endpoint_blocked_in_production")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoint disabled in production environment",
        )

    try:
        order = tradingview_adapter.parse_webhook(payload)

        return {
            "status": "success",
            "message": "Test webhook parsed successfully",
            "order": {
                "id": str(order.id),
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": float(order.quantity),
                "limit_price": float(order.limit_price) if order.limit_price else None,
                "stop_loss": float(order.stop_loss) if order.stop_loss else None,
                "take_profit": float(order.take_profit) if order.take_profit else None,
            },
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid payload: {e}"
        ) from e
