"""
MetaTrader Platform Adapter (Story 16.4a)

Adapter for MetaTrader 4/5 platform using the MetaTrader5 Python API.
Supports order placement, cancellation, and status queries.

Requires:
- MetaTrader 5 terminal installed
- MetaTrader5 Python package (pip install MetaTrader5)
- Terminal running with API enabled

Author: Story 16.4a
"""

from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

import structlog

from src.brokers.base_adapter import TradingPlatformAdapter
from src.models.order import (
    ExecutionReport,
    OCOOrder,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)

logger = structlog.get_logger(__name__)


class MetaTraderAdapter(TradingPlatformAdapter):
    """
    MetaTrader platform adapter using MT5 Python API.

    Connects to local MetaTrader 5 terminal and executes trades.
    Supports stocks, forex, and futures.

    Connection:
    - Requires MT5 terminal running locally
    - Uses account credentials for authentication
    - Maintains persistent connection

    Order Types Supported:
    - Market orders (immediate execution)
    - Limit orders (pending at specified price)
    - Stop orders (pending at stop price)
    """

    def __init__(
        self,
        account: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        timeout: int = 60000,
    ):
        """
        Initialize MetaTrader adapter.

        Args:
            account: MT5 account number
            password: MT5 account password
            server: MT5 server name (e.g., "MetaQuotes-Demo")
            timeout: Connection timeout in milliseconds
        """
        super().__init__(platform_name="MetaTrader5")
        self.account = account
        self.password = password
        self.server = server
        self.timeout = timeout
        self._mt5: Optional[Any] = None  # Will hold MetaTrader5 module reference

        logger.info(
            "metatrader_adapter_initialized",
            account=account,
            server=server,
            timeout=timeout,
        )

    async def connect(self) -> bool:
        """
        Establish connection to MetaTrader 5 terminal.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
            ImportError: If MetaTrader5 package not installed
        """
        try:
            # Import MetaTrader5 (lazy import to avoid dependency if not used)
            try:
                import MetaTrader5 as mt5

                self._mt5 = mt5
            except ImportError as e:
                raise ImportError(
                    "MetaTrader5 package not installed. " "Install with: pip install MetaTrader5"
                ) from e

            # Initialize connection
            if not self._mt5.initialize():
                error_code = self._mt5.last_error()
                raise ConnectionError(f"MT5 initialization failed: {error_code}")

            # Login if credentials provided
            if self.account and self.password and self.server:
                if not self._mt5.login(self.account, password=self.password, server=self.server):
                    error_code = self._mt5.last_error()
                    raise ConnectionError(f"MT5 login failed: {error_code}")

            self._set_connected(True)
            logger.info("metatrader_connected", account=self.account, server=self.server)
            return True

        except Exception as e:
            logger.error("metatrader_connection_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to MetaTrader: {e}") from e

    async def disconnect(self) -> bool:
        """
        Close connection to MetaTrader 5 terminal.

        Returns:
            True if disconnection successful
        """
        if self._mt5:
            self._mt5.shutdown()
            self._set_connected(False)
            logger.info("metatrader_disconnected")
        return True

    async def place_order(self, order: Order) -> ExecutionReport:
        """
        Place an order on MetaTrader platform.

        Args:
            order: Order to place

        Returns:
            ExecutionReport with order status

        Raises:
            ValueError: If order validation fails
            ConnectionError: If not connected to MT5
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MetaTrader. Call connect() first.")

        # Validate order
        self.validate_order(order)

        try:
            # Map order type to MT5 constants
            mt5_order_type = self._map_order_type(order.order_type, order.side)

            # Prepare order request
            symbol = order.symbol
            lot = float(order.quantity)  # MT5 uses lots
            price = float(order.limit_price) if order.limit_price else 0.0
            stop_loss = float(order.stop_loss) if order.stop_loss else 0.0
            take_profit = float(order.take_profit) if order.take_profit else 0.0

            # Build request
            request = {
                "action": self._mt5.TRADE_ACTION_DEAL
                if order.order_type == OrderType.MARKET
                else self._mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot,
                "type": mt5_order_type,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 20,  # Max price deviation in points
                "magic": 234000,  # EA magic number
                "comment": f"BMAD_{order.id}",
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": self._mt5.ORDER_FILLING_IOC,
            }

            # Send order
            result = self._mt5.order_send(request)

            if result.retcode != self._mt5.TRADE_RETCODE_DONE:
                logger.error(
                    "metatrader_order_failed",
                    retcode=result.retcode,
                    comment=result.comment,
                    symbol=symbol,
                )
                return ExecutionReport(
                    order_id=order.id,
                    platform_order_id=str(result.order),
                    platform="MetaTrader5",
                    status=OrderStatus.REJECTED,
                    filled_quantity=Decimal("0"),
                    remaining_quantity=order.quantity,
                    error_message=f"MT5 error {result.retcode}: {result.comment}",
                )

            # Success - create execution report
            # Note: MT5 commission retrieval requires querying deal history after execution
            # result.comment is a text string, not numeric commission value
            execution_report = ExecutionReport(
                order_id=order.id,
                platform_order_id=str(result.order),
                platform="MetaTrader5",
                status=OrderStatus.FILLED if result.volume == lot else OrderStatus.PARTIAL_FILL,
                filled_quantity=Decimal(str(result.volume)),
                remaining_quantity=Decimal(str(lot - result.volume)),
                average_fill_price=Decimal(str(result.price)),
                commission=None,  # TODO: Query deal history for actual commission
            )

            logger.info(
                "metatrader_order_placed",
                order_id=str(order.id),
                platform_order_id=result.order,
                symbol=symbol,
                status=execution_report.status,
            )

            return execution_report

        except Exception as e:
            logger.error("metatrader_order_placement_error", error=str(e), symbol=order.symbol)
            return ExecutionReport(
                order_id=order.id,
                platform_order_id="",
                platform="MetaTrader5",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                error_message=str(e),
            )

    async def place_oco_order(self, oco_order: OCOOrder) -> list[ExecutionReport]:
        """
        Place OCO order pair on MetaTrader.

        MT5 supports OCO through linked stop loss and take profit orders.

        Args:
            oco_order: OCO order to place

        Returns:
            List of ExecutionReports

        Raises:
            NotImplementedError: If OCO not fully supported
        """
        logger.warning("metatrader_oco_limited_support", message="OCO via SL/TP only")

        # Place primary order with SL/TP attached
        primary_report = await self.place_order(oco_order.primary_order)

        return [primary_report]

    async def cancel_order(self, order_id: str) -> ExecutionReport:
        """
        Cancel a pending order on MetaTrader.

        Args:
            order_id: Platform-specific order ID

        Returns:
            ExecutionReport with cancellation status

        Raises:
            ValueError: If order not found
            ConnectionError: If not connected
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MetaTrader")

        try:
            request = {
                "action": self._mt5.TRADE_ACTION_REMOVE,
                "order": int(order_id),
            }

            result = self._mt5.order_send(request)

            if result.retcode != self._mt5.TRADE_RETCODE_DONE:
                raise ValueError(f"Cancel failed: {result.comment}")

            logger.info("metatrader_order_cancelled", order_id=order_id)

            # Note: order_id parameter is the MT5 ticket number (platform_order_id)
            # Generating new UUID since we don't have access to original Order.id
            # Callers should use platform_order_id for order tracking
            return ExecutionReport(
                order_id=uuid4(),
                platform_order_id=order_id,
                platform="MetaTrader5",
                status=OrderStatus.CANCELLED,
                filled_quantity=Decimal("0"),
                remaining_quantity=Decimal("0"),
            )

        except Exception as e:
            logger.error("metatrader_cancel_failed", error=str(e), order_id=order_id)
            raise

    async def get_order_status(self, order_id: str) -> ExecutionReport:
        """
        Get current status of an order.

        Args:
            order_id: Platform-specific order ID

        Returns:
            ExecutionReport with current status

        Raises:
            ValueError: If order not found
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MetaTrader")

        # Query order from MT5
        orders = self._mt5.orders_get(ticket=int(order_id))

        if not orders:
            raise ValueError(f"Order {order_id} not found")

        order_info = orders[0]

        # Note: Generating new UUID since we don't have access to original Order.id
        # Callers should use platform_order_id (MT5 ticket) for order tracking
        return ExecutionReport(
            order_id=uuid4(),
            platform_order_id=order_id,
            platform="MetaTrader5",
            status=OrderStatus.PENDING,  # Simplification
            filled_quantity=Decimal(str(order_info.volume_current)),
            remaining_quantity=Decimal(str(order_info.volume_initial - order_info.volume_current)),
            average_fill_price=Decimal(str(order_info.price_current)),
        )

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExecutionReport]:
        """
        Get all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of ExecutionReports for open orders
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MetaTrader")

        orders = self._mt5.orders_get(symbol=symbol) if symbol else self._mt5.orders_get()

        # Note: Generating new UUIDs since we don't have access to original Order.id values
        # Callers should use platform_order_id (MT5 ticket) for order tracking
        execution_reports = []
        for order in orders:
            report = ExecutionReport(
                order_id=uuid4(),
                platform_order_id=str(order.ticket),
                platform="MetaTrader5",
                status=OrderStatus.PENDING,
                filled_quantity=Decimal(str(order.volume_current)),
                remaining_quantity=Decimal(str(order.volume_initial - order.volume_current)),
                average_fill_price=Decimal(str(order.price_current)),
            )
            execution_reports.append(report)

        return execution_reports

    def validate_order(self, order: Order) -> bool:
        """
        Validate order for MetaTrader platform.

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

        # Validate order type specific requirements
        if order.order_type == OrderType.LIMIT and order.limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")

        if order.order_type == OrderType.STOP and order.stop_price is None:
            raise ValueError("Stop price required for STOP orders")

        return True

    def _map_order_type(self, order_type: OrderType, side: OrderSide) -> int:
        """
        Map generic OrderType to MT5 order type constant.

        Args:
            order_type: Generic order type
            side: Order side (BUY/SELL)

        Returns:
            MT5 order type constant
        """
        if order_type == OrderType.MARKET:
            return self._mt5.ORDER_TYPE_BUY if side == OrderSide.BUY else self._mt5.ORDER_TYPE_SELL
        elif order_type == OrderType.LIMIT:
            return (
                self._mt5.ORDER_TYPE_BUY_LIMIT
                if side == OrderSide.BUY
                else self._mt5.ORDER_TYPE_SELL_LIMIT
            )
        elif order_type == OrderType.STOP:
            return (
                self._mt5.ORDER_TYPE_BUY_STOP
                if side == OrderSide.BUY
                else self._mt5.ORDER_TYPE_SELL_STOP
            )
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
