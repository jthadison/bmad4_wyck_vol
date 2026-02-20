"""
Trading Platform Adapter Base Class (Story 16.4a)

Abstract base class defining the interface for trading platform adapters.
All platform-specific implementations must inherit from this class.

Author: Story 16.4a
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Optional

import structlog

from src.models.order import ExecutionReport, OCOOrder, Order

logger = structlog.get_logger(__name__)


class TradingPlatformAdapter(ABC):
    """
    Abstract base class for trading platform adapters.

    Defines the standard interface that all platform adapters must implement.
    Each platform (TradingView, MetaTrader, Alpaca, etc.) provides a concrete
    implementation of this interface.

    Adapter Pattern: Translates generic Order objects into platform-specific
    order formats and handles platform-specific communication.
    """

    def __init__(self, platform_name: str):
        """
        Initialize the adapter.

        Args:
            platform_name: Name of the trading platform
        """
        self.platform_name = platform_name
        self._connected = False
        self._connected_at: datetime | None = None
        logger.info("trading_platform_adapter_initialized", platform=platform_name)

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the trading platform.

        Returns:
            True if connection successful, False otherwise

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Close connection to the trading platform.

        Returns:
            True if disconnection successful
        """
        pass

    @abstractmethod
    async def place_order(self, order: Order) -> ExecutionReport:
        """
        Place an order on the trading platform.

        Args:
            order: Order to place

        Returns:
            ExecutionReport with order status

        Raises:
            ValueError: If order validation fails
            ConnectionError: If platform connection is lost
        """
        pass

    @abstractmethod
    async def place_oco_order(self, oco_order: OCOOrder) -> list[ExecutionReport]:
        """
        Place a One-Cancels-Other (OCO) order pair.

        Args:
            oco_order: OCO order containing primary, stop loss, and take profit orders

        Returns:
            List of ExecutionReports for each order in the OCO group

        Raises:
            ValueError: If OCO order validation fails
            NotImplementedError: If platform doesn't support OCO orders
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> ExecutionReport:
        """
        Cancel an open order.

        Args:
            order_id: Platform-specific order ID

        Returns:
            ExecutionReport with cancellation status

        Raises:
            ValueError: If order not found
            ConnectionError: If platform connection is lost
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> ExecutionReport:
        """
        Get current status of an order.

        Args:
            order_id: Platform-specific order ID

        Returns:
            ExecutionReport with current order status

        Raises:
            ValueError: If order not found
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExecutionReport]:
        """
        Get all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of ExecutionReports for open orders
        """
        pass

    @abstractmethod
    def validate_order(self, order: Order) -> bool:
        """
        Validate order before submission.

        Checks order fields for platform-specific requirements.

        Args:
            order: Order to validate

        Returns:
            True if valid

        Raises:
            ValueError: If order validation fails with details
        """
        pass

    @abstractmethod
    async def close_all_positions(self) -> list[ExecutionReport]:
        """
        Close all open positions on the trading platform.

        Used by kill switch for emergency liquidation of all positions.

        Returns:
            List of ExecutionReports for each position closure attempt
        """
        pass

    @abstractmethod
    async def get_account_info(self) -> dict[str, Any]:
        """
        Get account information from the trading platform.

        Returns:
            Dict with account details. Expected keys:
            - account_id: str | None
            - balance: Decimal | None
            - buying_power: Decimal | None
            - cash: Decimal | None
            - margin_used: Decimal | None
            - margin_available: Decimal | None
            - margin_level_pct: Decimal | None
        """
        pass

    def is_connected(self) -> bool:
        """
        Check if adapter is connected to the platform.

        Returns:
            True if connected
        """
        return self._connected

    @property
    def connected_at(self) -> datetime | None:
        """Return the timestamp when the adapter last connected, or None."""
        return self._connected_at

    def _set_connected(self, connected: bool) -> None:
        """
        Set connection status (for subclass use).

        Args:
            connected: Connection status
        """
        self._connected = connected
        if connected:
            self._connected_at = datetime.now(UTC)
        else:
            self._connected_at = None
        logger.info(
            "trading_platform_connection_status_changed",
            platform=self.platform_name,
            connected=connected,
        )
