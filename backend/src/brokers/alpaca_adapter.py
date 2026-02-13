"""
Alpaca Trading Platform Adapter (Story 23.5)

Adapter for Alpaca Trading API v2 using REST endpoints.
Supports order placement, cancellation, bracket (OCO) orders, and status queries.

Requires:
- Alpaca account with API keys
- httpx package for async HTTP

Author: Story 23.5
"""

import asyncio
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx
import structlog

from src.brokers.base_adapter import TradingPlatformAdapter
from src.models.order import (
    ExecutionReport,
    OCOOrder,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)

logger = structlog.get_logger(__name__)

# Alpaca status -> our OrderStatus mapping
_ALPACA_STATUS_MAP: dict[str, OrderStatus] = {
    "new": OrderStatus.SUBMITTED,
    "accepted": OrderStatus.SUBMITTED,
    "pending_new": OrderStatus.PENDING,
    "accepted_for_bidding": OrderStatus.SUBMITTED,
    "partially_filled": OrderStatus.PARTIAL_FILL,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
    "pending_cancel": OrderStatus.SUBMITTED,
    "pending_replace": OrderStatus.SUBMITTED,
    "stopped": OrderStatus.FILLED,
    "suspended": OrderStatus.PENDING,
    "calculated": OrderStatus.PENDING,
}


class AlpacaAdapter(TradingPlatformAdapter):
    """
    Alpaca Trading API v2 adapter.

    Connects to Alpaca's REST API for order execution.
    Supports stocks and ETFs via paper or live trading.

    Order Types Supported:
    - Market orders
    - Limit orders
    - Stop orders
    - Stop-limit orders
    - Bracket (OCO) orders via order_class="bracket"
    """

    PAPER_BASE_URL = "https://paper-api.alpaca.markets"
    LIVE_BASE_URL = "https://api.alpaca.markets"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: Optional[str] = None,
        max_reconnect_attempts: int = 3,
    ):
        """
        Initialize Alpaca adapter.

        Args:
            api_key: Alpaca API key ID
            secret_key: Alpaca API secret key
            base_url: API base URL (defaults to paper trading)
            max_reconnect_attempts: Maximum reconnection attempts on failure
        """
        super().__init__(platform_name="Alpaca")
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url or self.PAPER_BASE_URL
        self.max_reconnect_attempts = max_reconnect_attempts
        self._client: Optional[httpx.AsyncClient] = None
        self._reconnect_lock = asyncio.Lock()

        masked_key = f"***{api_key[-4:]}" if len(api_key) >= 4 else "***"
        logger.info(
            "alpaca_adapter_initialized",
            api_key=masked_key,
            base_url=self._base_url,
            max_reconnect_attempts=max_reconnect_attempts,
        )

    def _headers(self) -> dict[str, str]:
        """Build authentication headers for Alpaca API."""
        return {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret_key,
        }

    async def connect(self) -> bool:
        """
        Establish connection to Alpaca API by verifying credentials.

        Creates an httpx.AsyncClient and validates by calling GET /v2/account.

        Returns:
            True if connection and authentication successful

        Raises:
            ConnectionError: If connection or authentication fails
        """
        try:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers(),
                timeout=30.0,
            )

            response = await self._client.get("/v2/account")
            response.raise_for_status()

            account = response.json()
            self._set_connected(True)

            logger.info(
                "alpaca_connected",
                account_status=account.get("status"),
                trading_blocked=account.get("trading_blocked"),
            )
            return True

        except httpx.HTTPStatusError as e:
            await self._close_client()
            raise ConnectionError(
                f"Alpaca authentication failed: HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            await self._close_client()
            raise ConnectionError(f"Failed to connect to Alpaca: {e}") from e

    async def disconnect(self) -> bool:
        """
        Close connection to Alpaca API.

        Returns:
            True if disconnection successful
        """
        await self._close_client()
        self._set_connected(False)
        logger.info("alpaca_disconnected")
        return True

    async def _close_client(self) -> None:
        """Close the httpx client if open."""
        if self._client:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    async def _ensure_connected(self) -> None:
        """
        Ensure the adapter is connected, attempting reconnection if needed.

        Uses asyncio.Lock to prevent concurrent reconnection attempts.
        Implements exponential backoff.

        Raises:
            ConnectionError: If reconnection fails after max attempts
        """
        if self.is_connected() and self._client is not None:
            return

        async with self._reconnect_lock:
            # Double-check after acquiring lock
            if self.is_connected() and self._client is not None:
                return

            logger.warning("alpaca_disconnected_detected", message="Attempting reconnection")

            try:
                await self._close_client()
            except Exception:
                logger.debug("alpaca_close_client_error_during_reconnect", exc_info=True)

            delay = 1.0
            for attempt in range(1, self.max_reconnect_attempts + 1):
                try:
                    await self.connect()
                    logger.info("alpaca_reconnected", attempt=attempt)
                    return
                except Exception as e:
                    logger.warning(
                        "alpaca_reconnect_failed",
                        attempt=attempt,
                        error=str(e),
                    )
                    await asyncio.sleep(min(delay, 60.0))
                    delay *= 2

            raise ConnectionError(
                f"Failed to reconnect to Alpaca after {self.max_reconnect_attempts} attempts"
            )

    async def place_order(self, order: Order) -> ExecutionReport:
        """
        Place an order on Alpaca.

        Args:
            order: Order to place

        Returns:
            ExecutionReport with order status

        Raises:
            ValueError: If order validation fails
            ConnectionError: If not connected and reconnection fails
        """
        await self._ensure_connected()
        self.validate_order(order)

        # NOTE: If a network error occurs after Alpaca receives the POST but before
        # we read the response, the order may exist on Alpaca while we return REJECTED
        # locally. Future improvement: use client_order_id=str(order.id) for idempotency.
        try:
            payload = self._build_order_payload(order)

            response = await self._client.post("/v2/orders", json=payload)  # type: ignore[union-attr]
            response.raise_for_status()

            data = response.json()
            report = self._parse_order_response(data, order_id=order.id)

            logger.info(
                "alpaca_order_placed",
                order_id=str(order.id),
                platform_order_id=data.get("id"),
                symbol=order.symbol,
                status=report.status,
            )
            return report

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(
                "alpaca_order_failed",
                status_code=e.response.status_code,
                error=error_body,
                symbol=order.symbol,
            )
            return ExecutionReport(
                order_id=order.id,
                platform_order_id="",
                platform="Alpaca",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                error_message=f"Alpaca HTTP {e.response.status_code}: {error_body}",
            )
        except ConnectionError:
            raise
        except Exception as e:
            logger.error("alpaca_order_placement_error", error=str(e), symbol=order.symbol)
            return ExecutionReport(
                order_id=order.id,
                platform_order_id="",
                platform="Alpaca",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                error_message=str(e),
            )

    async def place_oco_order(self, oco_order: OCOOrder) -> list[ExecutionReport]:
        """
        Place a bracket (OCO) order on Alpaca.

        Uses Alpaca's native bracket order support (order_class="bracket")
        which atomically creates entry + stop loss + take profit.

        Args:
            oco_order: OCO order to place

        Returns:
            List of ExecutionReports for the bracket order

        Raises:
            ConnectionError: If not connected
        """
        await self._ensure_connected()

        primary = oco_order.primary_order
        self.validate_order(primary)

        reports: list[ExecutionReport] = []

        try:
            # Build order payload
            payload = self._build_order_payload(primary)

            # Determine take profit price
            tp_price: Optional[Decimal] = None
            if oco_order.take_profit_order and oco_order.take_profit_order.limit_price:
                tp_price = oco_order.take_profit_order.limit_price
            elif primary.take_profit:
                tp_price = primary.take_profit

            # Determine stop loss price
            sl_price: Optional[Decimal] = None
            if oco_order.stop_loss_order and oco_order.stop_loss_order.stop_price:
                sl_price = oco_order.stop_loss_order.stop_price
            elif primary.stop_loss:
                sl_price = primary.stop_loss

            # Set order_class based on which legs are present
            has_tp = tp_price is not None
            has_sl = sl_price is not None

            if has_tp and has_sl:
                payload["order_class"] = "bracket"
                payload["take_profit"] = {"limit_price": str(tp_price)}
                payload["stop_loss"] = {"stop_price": str(sl_price)}
            elif has_tp or has_sl:
                payload["order_class"] = "oto"
                if has_tp:
                    payload["take_profit"] = {"limit_price": str(tp_price)}
                if has_sl:
                    payload["stop_loss"] = {"stop_price": str(sl_price)}

            response = await self._client.post("/v2/orders", json=payload)  # type: ignore[union-attr]
            response.raise_for_status()

            data = response.json()

            # Primary order report
            primary_report = self._parse_order_response(data, order_id=primary.id)
            reports.append(primary_report)

            # Parse leg orders from response if present
            legs = data.get("legs", [])
            for leg in legs:
                leg_type = leg.get("type", "")
                if leg_type in ("stop", "stop_limit") and oco_order.stop_loss_order:
                    leg_order_id = oco_order.stop_loss_order.id
                elif leg_type == "limit" and oco_order.take_profit_order:
                    leg_order_id = oco_order.take_profit_order.id
                else:
                    leg_order_id = uuid4()
                leg_report = self._parse_order_response(data=leg, order_id=leg_order_id)
                reports.append(leg_report)

            # If no legs returned and primary was not rejected, create submitted reports for SL/TP
            if not legs and primary_report.status != OrderStatus.REJECTED:
                platform_id = data.get("id", "")
                if oco_order.stop_loss_order:
                    reports.append(
                        ExecutionReport(
                            order_id=oco_order.stop_loss_order.id,
                            platform_order_id=platform_id,
                            platform="Alpaca",
                            status=OrderStatus.SUBMITTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=oco_order.stop_loss_order.quantity,
                        )
                    )
                if oco_order.take_profit_order:
                    reports.append(
                        ExecutionReport(
                            order_id=oco_order.take_profit_order.id,
                            platform_order_id=platform_id,
                            platform="Alpaca",
                            status=OrderStatus.SUBMITTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=oco_order.take_profit_order.quantity,
                        )
                    )

            logger.info(
                "alpaca_oco_placed",
                oco_id=str(oco_order.id),
                reports_count=len(reports),
            )
            return reports

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(
                "alpaca_oco_failed",
                status_code=e.response.status_code,
                error=error_body,
            )
            reports.append(
                ExecutionReport(
                    order_id=primary.id,
                    platform_order_id="",
                    platform="Alpaca",
                    status=OrderStatus.REJECTED,
                    filled_quantity=Decimal("0"),
                    remaining_quantity=primary.quantity,
                    error_message=f"Alpaca bracket order HTTP {e.response.status_code}: {error_body}",
                )
            )
            return reports
        except Exception as e:
            logger.error("alpaca_oco_error", error=str(e))
            reports.append(
                ExecutionReport(
                    order_id=primary.id,
                    platform_order_id="",
                    platform="Alpaca",
                    status=OrderStatus.REJECTED,
                    filled_quantity=Decimal("0"),
                    remaining_quantity=primary.quantity,
                    error_message=str(e),
                )
            )
            return reports

    async def close_all_positions(self) -> list[ExecutionReport]:
        """
        Close all open positions on Alpaca.

        Gets all open positions and submits market sell/buy-to-cover orders for each.

        Returns:
            List of ExecutionReports for each position closure attempt
        """
        await self._ensure_connected()

        reports: list[ExecutionReport] = []

        # Cancel all pending orders first to prevent fills during liquidation
        try:
            await self._client.delete("/v2/orders")  # type: ignore[union-attr]
            logger.info("alpaca_kill_switch_pending_orders_cancelled")
        except Exception as e:
            logger.error("alpaca_cancel_all_orders_failed", error=str(e))

        try:
            response = await self._client.get("/v2/positions")  # type: ignore[union-attr]
            response.raise_for_status()

            positions_data = response.json()
            if not positions_data:
                logger.info("alpaca_close_all_no_positions")
                return reports

            for pos in positions_data:
                symbol = pos.get("symbol", "")
                qty = pos.get("qty", "0")
                side = pos.get("side", "")

                # Close by submitting opposite side market order
                close_side = "sell" if side == "long" else "buy"

                try:
                    close_response = await self._client.post(  # type: ignore[union-attr]
                        "/v2/orders",
                        json={
                            "symbol": symbol,
                            "qty": str(abs(Decimal(qty))),
                            "side": close_side,
                            "type": "market",
                            "time_in_force": "gtc",
                        },
                    )
                    close_response.raise_for_status()

                    data = close_response.json()
                    report = self._parse_order_response(data, order_id=uuid4())
                    reports.append(report)

                    logger.info(
                        "alpaca_kill_switch_position_closed",
                        symbol=symbol,
                        qty=qty,
                        platform_order_id=data.get("id"),
                    )
                except httpx.HTTPStatusError as e:
                    reports.append(
                        ExecutionReport(
                            order_id=uuid4(),
                            platform_order_id="",
                            platform="Alpaca",
                            status=OrderStatus.REJECTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=Decimal(str(abs(Decimal(qty)))),
                            error_message=f"Close failed: HTTP {e.response.status_code}: {e.response.text}",
                        )
                    )
                    logger.error(
                        "alpaca_kill_switch_close_failed",
                        symbol=symbol,
                        status_code=e.response.status_code,
                    )
                except Exception as e:
                    reports.append(
                        ExecutionReport(
                            order_id=uuid4(),
                            platform_order_id="",
                            platform="Alpaca",
                            status=OrderStatus.REJECTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=Decimal(str(abs(Decimal(qty)))),
                            error_message=str(e),
                        )
                    )
                    logger.error(
                        "alpaca_kill_switch_close_error",
                        symbol=symbol,
                        error=str(e),
                    )

        except Exception as e:
            logger.error("alpaca_close_all_positions_error", error=str(e))

        logger.info(
            "alpaca_close_all_positions_complete",
            total=len(reports),
        )
        return reports

    async def cancel_order(self, order_id: str) -> ExecutionReport:
        """
        Cancel an open order on Alpaca.

        Args:
            order_id: Alpaca order ID (UUID string)

        Returns:
            ExecutionReport with cancellation status

        Raises:
            ValueError: If order not found or cancel fails
            ConnectionError: If not connected
        """
        await self._ensure_connected()

        try:
            response = await self._client.delete(f"/v2/orders/{order_id}")  # type: ignore[union-attr]
            response.raise_for_status()

            logger.info("alpaca_order_cancelled", order_id=order_id)

            return ExecutionReport(
                order_id=uuid4(),
                platform_order_id=order_id,
                platform="Alpaca",
                status=OrderStatus.CANCELLED,
                filled_quantity=Decimal("0"),
                remaining_quantity=Decimal("0"),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Order {order_id} not found on Alpaca") from e
            raise ValueError(
                f"Cancel failed: HTTP {e.response.status_code} - {e.response.text}"
            ) from e
        except (ValueError, ConnectionError):
            raise
        except Exception as e:
            logger.error("alpaca_cancel_failed", error=str(e), order_id=order_id)
            raise

    async def get_order_status(self, order_id: str) -> ExecutionReport:
        """
        Get current status of an order on Alpaca.

        Args:
            order_id: Alpaca order ID (UUID string)

        Returns:
            ExecutionReport with current status

        Raises:
            ValueError: If order not found
        """
        await self._ensure_connected()

        try:
            response = await self._client.get(f"/v2/orders/{order_id}")  # type: ignore[union-attr]
            response.raise_for_status()

            data = response.json()
            return self._parse_order_response(data, order_id=uuid4())

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Order {order_id} not found on Alpaca") from e
            raise ValueError(f"Get status failed: HTTP {e.response.status_code}") from e

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExecutionReport]:
        """
        Get all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of ExecutionReports for open orders
        """
        await self._ensure_connected()

        params: dict[str, str] = {"status": "open"}
        if symbol:
            params["symbols"] = symbol

        try:
            response = await self._client.get("/v2/orders", params=params)  # type: ignore[union-attr]
            response.raise_for_status()

            orders_data = response.json()
            reports = []
            for data in orders_data:
                report = self._parse_order_response(data, order_id=uuid4())
                reports.append(report)

            return reports
        except httpx.HTTPStatusError as e:
            logger.error(
                "alpaca_get_open_orders_failed",
                status_code=e.response.status_code,
                error=e.response.text,
            )
            raise ValueError(f"Failed to get open orders: HTTP {e.response.status_code}") from e
        except ConnectionError:
            raise
        except Exception as e:
            logger.error("alpaca_get_open_orders_error", error=str(e))
            raise

    def validate_order(self, order: Order) -> bool:
        """
        Validate order for Alpaca platform.

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

        if order.order_type == OrderType.STOP_LIMIT:
            if order.stop_price is None:
                raise ValueError("Stop price required for STOP_LIMIT orders")
            if order.limit_price is None:
                raise ValueError("Limit price required for STOP_LIMIT orders")

        if order.limit_price is not None and order.limit_price <= 0:
            raise ValueError(f"Limit price must be positive, got {order.limit_price}")

        if order.stop_price is not None and order.stop_price <= 0:
            raise ValueError(f"Stop price must be positive, got {order.stop_price}")

        return True

    def _build_order_payload(self, order: Order) -> dict[str, Any]:
        """
        Build Alpaca API order payload from an Order object.

        Args:
            order: Order to convert

        Returns:
            Dict payload for Alpaca POST /v2/orders
        """
        # Map order type
        type_map = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP: "stop",
            OrderType.STOP_LIMIT: "stop_limit",
        }

        # Map side
        side_map = {
            OrderSide.BUY: "buy",
            OrderSide.SELL: "sell",
        }

        # Map time in force
        tif_map = {
            TimeInForce.GTC: "gtc",
            TimeInForce.DAY: "day",
            TimeInForce.IOC: "ioc",
            TimeInForce.FOK: "fok",
        }

        payload: dict[str, Any] = {
            "symbol": order.symbol,
            "qty": str(order.quantity),
            "side": side_map[order.side],
            "type": type_map[order.order_type],
            "time_in_force": tif_map[order.time_in_force],
        }

        if order.limit_price is not None and order.order_type in (
            OrderType.LIMIT,
            OrderType.STOP_LIMIT,
        ):
            payload["limit_price"] = str(order.limit_price)

        if order.stop_price is not None and order.order_type in (
            OrderType.STOP,
            OrderType.STOP_LIMIT,
        ):
            payload["stop_price"] = str(order.stop_price)

        return payload

    def _parse_order_response(
        self, data: dict[str, Any], order_id: Optional[UUID] = None
    ) -> ExecutionReport:
        """
        Parse an Alpaca order response into an ExecutionReport.

        Args:
            data: Alpaca order JSON response
            order_id: Internal order UUID to associate

        Returns:
            ExecutionReport
        """
        alpaca_status = data.get("status", "")
        status = _ALPACA_STATUS_MAP.get(alpaca_status, OrderStatus.PENDING)

        filled_qty = Decimal(data.get("filled_qty") or "0")
        total_qty = Decimal(data.get("qty") or "0")
        remaining_qty = total_qty - filled_qty

        avg_price_str = data.get("filled_avg_price")
        avg_price = Decimal(avg_price_str) if avg_price_str else None

        return ExecutionReport(
            order_id=order_id or uuid4(),
            platform_order_id=data.get("id", ""),
            platform="Alpaca",
            status=status,
            filled_quantity=filled_qty,
            remaining_quantity=remaining_qty,
            average_fill_price=avg_price,
            commission=None,  # Alpaca reports commission separately via account activity
        )
