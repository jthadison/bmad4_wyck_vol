"""
TradingView Webhook Adapter (Story 16.4a)

Adapter for TradingView platform using webhook-based alert integration.
Receives alerts from TradingView and translates them into Order objects.

TradingView sends webhooks when chart alerts trigger. This adapter:
1. Validates webhook signatures
2. Parses alert payloads
3. Creates Order objects for execution

Author: Story 16.4a
"""

import hashlib
import hmac
from typing import Any, Optional

import structlog

from src.brokers.base_adapter import TradingPlatformAdapter
from src.config import settings
from src.models.order import (
    ExecutionReport,
    OCOOrder,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

logger = structlog.get_logger(__name__)


class TradingViewAdapter(TradingPlatformAdapter):
    """
    TradingView platform adapter using webhook integration.

    TradingView doesn't provide a direct API for order placement.
    Instead, it sends webhook alerts that we receive and process.

    Typical flow:
    1. User creates alert in TradingView with webhook URL
    2. Alert triggers and sends POST request to our webhook endpoint
    3. Adapter validates signature and parses payload
    4. Order created from alert data
    """

    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Initialize TradingView adapter.

        Args:
            webhook_secret: Secret key for webhook signature verification (optional but recommended)
        """
        super().__init__(platform_name="TradingView")
        self.webhook_secret = webhook_secret
        self._set_connected(True)  # Always "connected" since webhook-based
        logger.info(
            "tradingview_adapter_initialized", has_webhook_secret=webhook_secret is not None
        )

    async def connect(self) -> bool:
        """
        TradingView uses webhooks, no connection needed.

        Returns:
            True (always connected)
        """
        self._set_connected(True)
        return True

    async def disconnect(self) -> bool:
        """
        TradingView uses webhooks, no disconnection needed.

        Returns:
            True
        """
        return True

    async def place_order(self, order: Order) -> ExecutionReport:
        """
        TradingView doesn't support direct order placement via API.

        Orders are created from incoming webhooks, not placed programmatically.

        Raises:
            NotImplementedError: Direct order placement not supported
        """
        raise NotImplementedError(
            "TradingView adapter receives orders via webhooks, "
            "direct order placement not supported. Use parse_webhook() instead."
        )

    async def place_oco_order(self, oco_order: OCOOrder) -> list[ExecutionReport]:
        """
        TradingView doesn't support OCO orders via webhooks.

        Raises:
            NotImplementedError: OCO orders not supported
        """
        raise NotImplementedError("TradingView webhook adapter does not support OCO orders")

    async def cancel_order(self, order_id: str) -> ExecutionReport:
        """
        TradingView doesn't support order cancellation via API.

        Raises:
            NotImplementedError: Order cancellation not supported
        """
        raise NotImplementedError("TradingView webhook adapter does not support order cancellation")

    async def get_order_status(self, order_id: str) -> ExecutionReport:
        """
        TradingView doesn't provide order status via API.

        Raises:
            NotImplementedError: Order status not supported
        """
        raise NotImplementedError(
            "TradingView webhook adapter does not support order status queries"
        )

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExecutionReport]:
        """
        TradingView doesn't provide open orders via API.

        Raises:
            NotImplementedError: Open orders not supported
        """
        raise NotImplementedError(
            "TradingView webhook adapter does not support open orders queries"
        )

    async def get_account_info(self) -> dict[str, Any]:
        """
        TradingView doesn't provide account information.

        Returns:
            Dict with all None values.
        """
        return {
            "account_id": None,
            "balance": None,
            "buying_power": None,
            "cash": None,
            "margin_used": None,
            "margin_available": None,
            "margin_level_pct": None,
        }

    async def close_all_positions(self) -> list[ExecutionReport]:
        """
        TradingView doesn't support position management via API.

        Returns:
            Empty list (no positions to close)
        """
        logger.warning("tradingview_close_all_not_supported")
        return []

    def validate_order(self, order: Order) -> bool:
        """
        Validate order from TradingView webhook.

        Args:
            order: Order to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        if not order.symbol:
            raise ValueError("Symbol is required")

        if order.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {order.quantity}")

        if order.order_type == OrderType.LIMIT and order.limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")

        if order.order_type == OrderType.STOP and order.stop_price is None:
            raise ValueError("Stop price required for STOP orders")

        logger.debug(
            "tradingview_order_validated", symbol=order.symbol, order_type=order.order_type
        )
        return True

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature for security.

        Validates that webhook came from TradingView by checking HMAC signature.

        Args:
            payload: Raw webhook payload (JSON string)
            signature: Signature from webhook headers

        Returns:
            True if signature valid

        Raises:
            ValueError: If webhook_secret not configured in production
        """
        if not self.webhook_secret:
            # Security: Require webhook secret in production
            if settings.environment == "production":
                logger.error(
                    "tradingview_webhook_secret_not_configured_in_production",
                    message="Webhook secret required in production",
                )
                return False
            # Allow skipping verification in non-production environments
            logger.warning(
                "tradingview_webhook_secret_not_configured",
                message="Webhook verification skipped - development mode only",
            )
            return True

        # Calculate expected signature
        expected_signature = hmac.new(
            self.webhook_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant-time comparison to prevent timing attacks)
        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            logger.warning("tradingview_webhook_signature_invalid", signature_provided=signature)

        return is_valid

    def parse_webhook(self, payload: dict) -> Order:
        """
        Parse TradingView webhook payload into Order object.

        Expected webhook format:
        {
            "symbol": "AAPL",
            "action": "buy",
            "order_type": "limit",
            "quantity": 100,
            "limit_price": 150.50,
            "stop_loss": 145.00,
            "take_profit": 160.00,
            "signal_id": "uuid-string" (optional)
        }

        Args:
            payload: Webhook JSON payload

        Returns:
            Order object

        Raises:
            ValueError: If payload invalid or missing required fields
        """
        try:
            # Extract required fields
            symbol = payload.get("symbol")
            action = payload.get("action", "").upper()
            order_type = payload.get("order_type", "MARKET").upper()
            quantity = payload.get("quantity")

            # Validate required fields
            if not symbol:
                raise ValueError("Missing required field: symbol")
            if action not in ["BUY", "SELL"]:
                raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'")
            if not quantity or float(quantity) <= 0:
                raise ValueError(f"Invalid quantity: {quantity}")

            # Parse optional fields
            limit_price = payload.get("limit_price")
            stop_price = payload.get("stop_price")
            stop_loss = payload.get("stop_loss")
            take_profit = payload.get("take_profit")
            signal_id = payload.get("signal_id")

            # Create Order (using Decimal for precision)
            from decimal import Decimal

            order = Order(
                platform="TradingView",
                symbol=symbol,
                side=OrderSide(action),
                order_type=OrderType(order_type),
                quantity=Decimal(str(quantity)),
                limit_price=Decimal(str(limit_price)) if limit_price else None,
                stop_price=Decimal(str(stop_price)) if stop_price else None,
                stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
                take_profit=Decimal(str(take_profit)) if take_profit else None,
                signal_id=signal_id,
                status=OrderStatus.PENDING,
            )

            # Validate the order
            self.validate_order(order)

            logger.info(
                "tradingview_webhook_parsed",
                symbol=symbol,
                action=action,
                order_type=order_type,
                quantity=quantity,
            )

            return order

        except (KeyError, ValueError, TypeError) as e:
            # Log error without full payload to avoid exposing sensitive data
            logger.error(
                "tradingview_webhook_parse_error",
                error=str(e),
                symbol=payload.get("symbol", "unknown"),
                action=payload.get("action", "unknown"),
            )
            raise ValueError(f"Failed to parse TradingView webhook: {e}") from e
