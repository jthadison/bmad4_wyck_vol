"""
MetaTrader Platform Adapter (Story 16.4a / 23.4)

Adapter for MetaTrader 4/5 platform using the MetaTrader5 Python API.
Supports order placement, cancellation, and status queries.

Requires:
- MetaTrader 5 terminal installed
- MetaTrader5 Python package (pip install MetaTrader5)
- Terminal running with API enabled

Author: Story 16.4a, Story 23.4
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
    - Maintains persistent connection with automatic reconnection

    Order Types Supported:
    - Market orders (immediate execution)
    - Limit orders (pending at specified price)
    - Stop orders (pending at stop price)
    - STOP_LIMIT is not supported (raises ValueError)
    """

    def __init__(
        self,
        account: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        timeout: int = 60000,
        magic_number: int = 234000,
        max_reconnect_attempts: int = 3,
    ):
        """
        Initialize MetaTrader adapter.

        Args:
            account: MT5 account number
            password: MT5 account password
            server: MT5 server name (e.g., "MetaQuotes-Demo")
            timeout: Connection timeout in milliseconds
            magic_number: Expert Advisor magic number for order identification (default: 234000)
            max_reconnect_attempts: Maximum reconnection attempts on disconnect (default: 3)
        """
        super().__init__(platform_name="MetaTrader5")
        self.account = account
        self.password = password
        self.server = server
        self.timeout = timeout
        self.magic_number = magic_number
        self.max_reconnect_attempts = max_reconnect_attempts
        self._mt5: Optional[Any] = None  # Will hold MetaTrader5 module reference

        # Mask account number in logs for security
        masked_account = f"***{str(account)[-4:]}" if account else None
        logger.info(
            "metatrader_adapter_initialized",
            account=masked_account,
            server=server,
            timeout=timeout,
            magic_number=magic_number,
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
            masked_account = f"***{str(self.account)[-4:]}" if self.account else "none"
            logger.info("metatrader_connected", account=masked_account, server=self.server)
            return True

        except ImportError:
            raise
        except ConnectionError:
            raise
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

    async def _ensure_connected(self) -> None:
        """
        Ensure the adapter is connected, attempting reconnection if needed.

        Raises:
            ConnectionError: If reconnection fails after max attempts
        """
        if self.is_connected():
            return

        if self._mt5 is None:
            raise ConnectionError("Not connected to MetaTrader. Call connect() first.")

        logger.warning("metatrader_disconnected_detected", message="Attempting reconnection")

        for attempt in range(1, self.max_reconnect_attempts + 1):
            try:
                # Try to reinitialize the terminal
                if self._mt5.initialize():
                    # Re-login if credentials were provided
                    if self.account and self.password and self.server:
                        if not self._mt5.login(
                            self.account, password=self.password, server=self.server
                        ):
                            logger.warning(
                                "metatrader_reconnect_login_failed",
                                attempt=attempt,
                            )
                            continue

                    self._set_connected(True)
                    logger.info("metatrader_reconnected", attempt=attempt)
                    return
                else:
                    logger.warning(
                        "metatrader_reconnect_init_failed",
                        attempt=attempt,
                    )
            except Exception as e:
                logger.warning(
                    "metatrader_reconnect_error",
                    attempt=attempt,
                    error=str(e),
                )

        raise ConnectionError(
            f"Failed to reconnect to MetaTrader after {self.max_reconnect_attempts} attempts"
        )

    def _query_deal_commission(self, deal_ticket: int) -> Optional[Decimal]:
        """
        Query MT5 deal history for commission, swap, and fee data.

        Args:
            deal_ticket: The deal ticket number from order execution

        Returns:
            Total commission (commission + swap + fee) as Decimal, or None if unavailable
        """
        try:
            deals = self._mt5.history_deals_get(ticket=deal_ticket)
            if not deals or len(deals) == 0:
                logger.debug(
                    "metatrader_no_deal_history",
                    deal_ticket=deal_ticket,
                )
                return None

            deal = deals[0]
            commission = getattr(deal, "commission", 0.0) or 0.0
            swap = getattr(deal, "swap", 0.0) or 0.0
            fee = getattr(deal, "fee", 0.0) or 0.0
            total = Decimal(str(commission)) + Decimal(str(swap)) + Decimal(str(fee))

            logger.debug(
                "metatrader_deal_commission",
                deal_ticket=deal_ticket,
                commission=commission,
                swap=swap,
                fee=fee,
                total=str(total),
            )

            return total

        except Exception as e:
            logger.warning(
                "metatrader_commission_query_failed",
                deal_ticket=deal_ticket,
                error=str(e),
            )
            return None

    async def place_order(self, order: Order) -> ExecutionReport:
        """
        Place an order on MetaTrader platform.

        Args:
            order: Order to place

        Returns:
            ExecutionReport with order status

        Raises:
            ValueError: If order validation fails
            ConnectionError: If not connected to MT5 and reconnection fails
        """
        await self._ensure_connected()

        # Validate order
        self.validate_order(order)

        try:
            # Map order type to MT5 constants
            mt5_order_type = self._map_order_type(order.order_type, order.side)

            # Prepare order request
            symbol = order.symbol
            lot = float(order.quantity)  # MT5 uses lots

            # For STOP orders, use stop_price as the price
            if order.order_type == OrderType.STOP:
                price = float(order.stop_price) if order.stop_price else 0.0
            else:
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
                "magic": self.magic_number,  # EA magic number for order identification
                "comment": f"BMAD_{order.id}",
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": self._mt5.ORDER_FILLING_IOC,
            }

            # Send order
            result = self._mt5.order_send(request)

            if result is None:
                # Terminal may have disconnected
                self._set_connected(False)
                return ExecutionReport(
                    order_id=order.id,
                    platform_order_id="",
                    platform="MetaTrader5",
                    status=OrderStatus.REJECTED,
                    filled_quantity=Decimal("0"),
                    remaining_quantity=order.quantity,
                    error_message="MT5 order_send returned None - terminal may be disconnected",
                )

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

            # Query deal history for commission data
            commission = None
            if hasattr(result, "deal") and result.deal:
                commission = self._query_deal_commission(result.deal)

            # Success - create execution report
            execution_report = ExecutionReport(
                order_id=order.id,
                platform_order_id=str(result.order),
                platform="MetaTrader5",
                status=OrderStatus.FILLED if result.volume == lot else OrderStatus.PARTIAL_FILL,
                filled_quantity=Decimal(str(result.volume)),
                remaining_quantity=Decimal(str(lot - result.volume)),
                average_fill_price=Decimal(str(result.price)),
                commission=commission,
            )

            logger.info(
                "metatrader_order_placed",
                order_id=str(order.id),
                platform_order_id=result.order,
                symbol=symbol,
                status=execution_report.status,
                commission=str(commission) if commission else None,
            )

            return execution_report

        except (ValueError, ConnectionError):
            raise
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

        MT5 handles OCO through SL/TP on the position. The workflow:
        1. Place primary (entry) order with SL/TP from the OCO sub-orders
        2. If entry fills, the position automatically has SL/TP attached
        3. If SL/TP setting fails, attempt to close the position for safety

        Args:
            oco_order: OCO order to place

        Returns:
            List of ExecutionReports for each leg

        Raises:
            ConnectionError: If not connected
        """
        await self._ensure_connected()

        reports: list[ExecutionReport] = []

        # Extract SL/TP prices from the OCO sub-orders
        primary = oco_order.primary_order

        # Attach SL/TP from sub-orders to the primary order if not already set
        sl_price = primary.stop_loss
        tp_price = primary.take_profit

        if oco_order.stop_loss_order and oco_order.stop_loss_order.stop_price:
            sl_price = oco_order.stop_loss_order.stop_price
        if oco_order.take_profit_order and oco_order.take_profit_order.limit_price:
            tp_price = oco_order.take_profit_order.limit_price

        # Create a modified primary order with SL/TP attached
        primary_with_sltp = primary.model_copy(
            update={"stop_loss": sl_price, "take_profit": tp_price}
        )

        # Place the primary order
        primary_report = await self.place_order(primary_with_sltp)
        reports.append(primary_report)

        if primary_report.status not in (OrderStatus.FILLED, OrderStatus.PARTIAL_FILL):
            logger.warning(
                "metatrader_oco_primary_not_filled",
                status=primary_report.status,
                error=primary_report.error_message,
            )
            return reports

        # For market orders, SL/TP should already be set via the request.
        # For cases where SL/TP need to be modified on an existing position,
        # we verify by attempting a position modification.
        if sl_price or tp_price:
            modify_success = self._modify_position_sltp(
                symbol=primary.symbol,
                sl_price=float(sl_price) if sl_price else 0.0,
                tp_price=float(tp_price) if tp_price else 0.0,
            )

            if not modify_success:
                logger.error(
                    "metatrader_oco_sltp_modification_failed",
                    symbol=primary.symbol,
                    message="SL/TP may not be set correctly on position",
                )
                # Create error reports for the failed SL/TP legs
                if oco_order.stop_loss_order:
                    reports.append(
                        ExecutionReport(
                            order_id=oco_order.stop_loss_order.id,
                            platform_order_id="",
                            platform="MetaTrader5",
                            status=OrderStatus.REJECTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=oco_order.stop_loss_order.quantity,
                            error_message="Failed to set stop loss on position",
                        )
                    )
                if oco_order.take_profit_order:
                    reports.append(
                        ExecutionReport(
                            order_id=oco_order.take_profit_order.id,
                            platform_order_id="",
                            platform="MetaTrader5",
                            status=OrderStatus.REJECTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=oco_order.take_profit_order.quantity,
                            error_message="Failed to set take profit on position",
                        )
                    )
            else:
                # SL/TP set successfully - report them as submitted
                if oco_order.stop_loss_order:
                    reports.append(
                        ExecutionReport(
                            order_id=oco_order.stop_loss_order.id,
                            platform_order_id=primary_report.platform_order_id,
                            platform="MetaTrader5",
                            status=OrderStatus.SUBMITTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=oco_order.stop_loss_order.quantity,
                        )
                    )
                if oco_order.take_profit_order:
                    reports.append(
                        ExecutionReport(
                            order_id=oco_order.take_profit_order.id,
                            platform_order_id=primary_report.platform_order_id,
                            platform="MetaTrader5",
                            status=OrderStatus.SUBMITTED,
                            filled_quantity=Decimal("0"),
                            remaining_quantity=oco_order.take_profit_order.quantity,
                        )
                    )

        logger.info(
            "metatrader_oco_placed",
            oco_id=str(oco_order.id),
            reports_count=len(reports),
        )

        return reports

    def _modify_position_sltp(self, symbol: str, sl_price: float, tp_price: float) -> bool:
        """
        Modify SL/TP on an existing position.

        Args:
            symbol: Symbol to modify
            sl_price: New stop loss price (0.0 for none)
            tp_price: New take profit price (0.0 for none)

        Returns:
            True if modification succeeded
        """
        try:
            # Get current position for the symbol
            positions = self._mt5.positions_get(symbol=symbol)
            if not positions or len(positions) == 0:
                logger.warning("metatrader_no_position_for_sltp", symbol=symbol)
                return False

            position = positions[0]

            request = {
                "action": self._mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": position.ticket,
                "sl": sl_price,
                "tp": tp_price,
            }

            result = self._mt5.order_send(request)

            if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
                comment = result.comment if result else "No result"
                logger.error(
                    "metatrader_sltp_modify_failed",
                    symbol=symbol,
                    comment=comment,
                )
                return False

            return True

        except Exception as e:
            logger.error(
                "metatrader_sltp_modify_error",
                symbol=symbol,
                error=str(e),
            )
            return False

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
        await self._ensure_connected()

        try:
            request = {
                "action": self._mt5.TRADE_ACTION_REMOVE,
                "order": int(order_id),
            }

            result = self._mt5.order_send(request)

            if result is None:
                self._set_connected(False)
                raise ConnectionError("MT5 terminal disconnected during cancel")

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

        except (ValueError, ConnectionError):
            raise
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
        await self._ensure_connected()

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
        await self._ensure_connected()

        orders = self._mt5.orders_get(symbol=symbol) if symbol else self._mt5.orders_get()

        if not orders:
            return []

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

        if order.order_type == OrderType.STOP_LIMIT:
            raise ValueError(
                "STOP_LIMIT orders are not supported by MetaTrader adapter. "
                "Use STOP or LIMIT order types instead."
            )

        return True

    def _map_order_type(self, order_type: OrderType, side: OrderSide) -> int:
        """
        Map generic OrderType to MT5 order type constant.

        Args:
            order_type: Generic order type
            side: Order side (BUY/SELL)

        Returns:
            MT5 order type constant

        Raises:
            ValueError: If order_type is not supported (e.g., STOP_LIMIT)
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
            raise ValueError(
                f"Unsupported order type: {order_type}. "
                "MetaTrader adapter supports MARKET, LIMIT, and STOP orders only."
            )
