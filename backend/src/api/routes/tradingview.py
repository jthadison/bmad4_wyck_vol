"""
TradingView Webhook API Routes (Story 16.4a)

API endpoints for receiving TradingView alert webhooks.
Handles webhook signature verification and order creation from alerts.

Author: Story 16.4a
"""

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from src.brokers.order_builder import OrderBuilder
from src.brokers.tradingview_adapter import TradingViewAdapter
from src.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/tradingview", tags=["TradingView"])


# Initialize TradingView adapter
# Webhook secret should be configured in settings
tradingview_adapter = TradingViewAdapter(
    webhook_secret=getattr(settings, "TRADINGVIEW_WEBHOOK_SECRET", None)
)

order_builder = OrderBuilder(default_platform="TradingView")


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

        logger.info(
            "tradingview_webhook_received",
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=float(order.quantity),
        )

        # TODO: Store order in database
        # TODO: Execute order on broker if auto-execution enabled
        # TODO: Emit WebSocket event for frontend

        return {
            "status": "success",
            "message": "Webhook received and order created",
            "order": {
                "id": str(order.id),
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "quantity": float(order.quantity),
                "status": order.status,
            },
        }

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
