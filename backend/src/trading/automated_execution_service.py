"""
Automated Execution Service with Safety Checks (Story 16.4b)

Purpose:
--------
Provides automated order execution for campaign signals with comprehensive
safety checks, position sizing based on 2% risk rule, and emergency kill switch.

Features:
---------
- Enable/disable automation toggle
- Emergency kill switch (stops all execution immediately)
- Pre-trade balance validation
- Existing position checks
- Order validation before submission
- 2% risk rule position sizing
- Integration with platform adapters (Story 16.4a)

Signal Types:
-------------
- ENTRY: Initial campaign entry (Spring pattern)
- ADD: Position add (SOS pattern)
- EXIT: Position exit

Author: Story 16.4b
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4

import structlog

from src.models.campaign_event import CampaignEvent, CampaignEventType

logger = structlog.get_logger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode for automated trading."""

    DISABLED = "DISABLED"  # Automation off
    PAPER = "PAPER"  # Paper trading mode
    LIVE = "LIVE"  # Live trading mode


class SignalAction(str, Enum):
    """Campaign signal action types."""

    ENTRY = "ENTRY"  # Initial entry (Spring)
    ADD = "ADD"  # Add to position (SOS)
    EXIT = "EXIT"  # Exit position


@dataclass
class ExecutionConfig:
    """Configuration for automated execution."""

    max_risk_per_trade_pct: Decimal = Decimal("2.0")  # FR18: 2% max
    max_position_size: Decimal = Decimal("10000")  # Max shares/lots
    max_portfolio_heat_pct: Decimal = Decimal("10.0")  # FR18: 10% max
    order_timeout_ms: int = 500  # Max execution time
    require_balance_check: bool = True
    require_position_check: bool = True


@dataclass
class Order:
    """Order to be submitted to trading platform."""

    id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    action: SignalAction = SignalAction.ENTRY
    quantity: Decimal = Decimal("0")
    order_type: str = "MARKET"  # MARKET, LIMIT, STOP
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ExecutionReport:
    """Report of order execution result."""

    order_id: UUID
    success: bool
    fill_price: Decimal | None = None
    fill_quantity: Decimal | None = None
    commission: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    executed_at: datetime | None = None
    error_message: str | None = None
    execution_time_ms: int = 0


class TradingPlatformAdapter(Protocol):
    """
    Protocol for trading platform adapters (Story 16.4a).

    Adapters implement this interface to connect to different platforms
    (TradingView, MetaTrader, Alpaca, etc.).
    """

    async def connect(self) -> bool:
        """Connect to trading platform."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from trading platform."""
        ...

    async def get_account_balance(self) -> Decimal:
        """Get current account balance."""
        ...

    async def get_position(self, symbol: str) -> dict[str, Any] | None:
        """Get current position for symbol."""
        ...

    async def place_order(self, order: Order) -> ExecutionReport:
        """Place order on platform."""
        ...

    async def cancel_order(self, order_id: UUID) -> bool:
        """Cancel pending order."""
        ...


class SafetyCheckError(Exception):
    """Raised when a safety check fails."""

    def __init__(self, check_type: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.check_type = check_type
        self.message = message
        self.details = details or {}


class AutomatedExecutionService:
    """
    Automated execution service with safety checks.

    Executes campaign signals automatically while enforcing:
    - 2% max risk per trade
    - Pre-trade balance validation
    - Position existence checks
    - Order validation
    - Kill switch for emergencies
    """

    def __init__(
        self,
        adapter: TradingPlatformAdapter | None = None,
        config: ExecutionConfig | None = None,
    ):
        """
        Initialize automated execution service.

        Args:
            adapter: Trading platform adapter (optional, can be set later)
            config: Execution configuration
        """
        self._adapter = adapter
        self._config = config or ExecutionConfig()
        self._mode = ExecutionMode.DISABLED
        self._kill_switch_active = False
        self._execution_log: list[dict[str, Any]] = []

        logger.info(
            "automated_execution_service_initialized",
            mode=self._mode.value,
            max_risk_pct=float(self._config.max_risk_per_trade_pct),
        )

    @property
    def is_enabled(self) -> bool:
        """Check if automation is enabled."""
        return self._mode != ExecutionMode.DISABLED and not self._kill_switch_active

    @property
    def mode(self) -> ExecutionMode:
        """Get current execution mode."""
        return self._mode

    @property
    def kill_switch_active(self) -> bool:
        """Check if kill switch is active."""
        return self._kill_switch_active

    def enable(self, mode: ExecutionMode = ExecutionMode.PAPER) -> None:
        """
        Enable automated execution.

        Args:
            mode: Execution mode (PAPER or LIVE)
        """
        if mode == ExecutionMode.DISABLED:
            raise ValueError("Use disable() to disable automation")

        if self._kill_switch_active:
            logger.warning("enable_blocked_kill_switch_active")
            raise SafetyCheckError(
                "kill_switch",
                "Cannot enable automation while kill switch is active",
            )

        self._mode = mode
        logger.info("automation_enabled", mode=mode.value)

    def disable(self) -> None:
        """Disable automated execution."""
        self._mode = ExecutionMode.DISABLED
        logger.info("automation_disabled")

    def activate_kill_switch(self, reason: str = "manual") -> None:
        """
        Activate emergency kill switch.

        Immediately stops all automated execution. Requires manual reset.

        Args:
            reason: Reason for activation
        """
        self._kill_switch_active = True
        self._mode = ExecutionMode.DISABLED

        logger.critical(
            "kill_switch_activated",
            reason=reason,
            timestamp=datetime.now(UTC).isoformat(),
        )

        self._log_execution(
            event="KILL_SWITCH_ACTIVATED",
            success=True,
            details={"reason": reason},
        )

    def reset_kill_switch(self) -> None:
        """
        Reset kill switch after emergency.

        Requires explicit call to re-enable automation after reset.
        """
        self._kill_switch_active = False
        logger.warning("kill_switch_reset")

        self._log_execution(
            event="KILL_SWITCH_RESET",
            success=True,
            details={},
        )

    def set_adapter(self, adapter: TradingPlatformAdapter) -> None:
        """Set trading platform adapter."""
        self._adapter = adapter
        logger.info("adapter_set", adapter_type=type(adapter).__name__)

    async def execute_signal(
        self,
        event: CampaignEvent,
        entry_price: Decimal,
        stop_loss: Decimal,
        account_balance: Decimal | None = None,
    ) -> ExecutionReport | None:
        """
        Execute a campaign signal with safety checks.

        Args:
            event: Campaign event (CAMPAIGN_FORMED, PATTERN_DETECTED)
            entry_price: Entry price for the trade
            stop_loss: Stop loss price
            account_balance: Account balance (fetched if not provided)

        Returns:
            ExecutionReport if executed, None if skipped

        Raises:
            SafetyCheckError: If any safety check fails
        """
        start_time = datetime.now(UTC)

        # Check if execution is allowed
        if not self.is_enabled:
            logger.debug(
                "execution_skipped_disabled",
                campaign_id=event.campaign_id,
                mode=self._mode.value,
                kill_switch=self._kill_switch_active,
            )
            return None

        if self._adapter is None:
            logger.warning("execution_skipped_no_adapter", campaign_id=event.campaign_id)
            return None

        # Determine action from event type
        action = self._determine_action(event)
        if action is None:
            logger.debug(
                "execution_skipped_invalid_event",
                event_type=event.event_type.value,
                campaign_id=event.campaign_id,
            )
            return None

        symbol = event.metadata.get("symbol", "")
        if not symbol:
            raise SafetyCheckError("validation", "Missing symbol in event metadata")

        # Fetch account balance if not provided
        if account_balance is None:
            account_balance = await self._adapter.get_account_balance()

        # Run safety checks
        await self._run_safety_checks(
            symbol=symbol,
            action=action,
            entry_price=entry_price,
            stop_loss=stop_loss,
            account_balance=account_balance,
        )

        # Calculate position size
        quantity = self._calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            account_balance=account_balance,
        )

        # Build and validate order
        order = Order(
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type="MARKET",
            stop_loss=stop_loss,
        )

        self._validate_order(order)

        # Execute order
        logger.info(
            "executing_order",
            order_id=str(order.id),
            symbol=symbol,
            action=action.value,
            quantity=float(quantity),
            entry_price=float(entry_price),
        )

        report = await self._adapter.place_order(order)

        # Calculate execution time
        end_time = datetime.now(UTC)
        report.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Log execution
        self._log_execution(
            event="ORDER_EXECUTED" if report.success else "ORDER_FAILED",
            success=report.success,
            details={
                "order_id": str(order.id),
                "symbol": symbol,
                "action": action.value,
                "quantity": float(quantity),
                "fill_price": float(report.fill_price) if report.fill_price else None,
                "execution_time_ms": report.execution_time_ms,
                "error": report.error_message,
            },
        )

        # Check execution time
        if report.execution_time_ms > self._config.order_timeout_ms:
            logger.warning(
                "execution_timeout_exceeded",
                execution_time_ms=report.execution_time_ms,
                limit_ms=self._config.order_timeout_ms,
            )

        return report

    def _determine_action(self, event: CampaignEvent) -> SignalAction | None:
        """Determine signal action from campaign event."""
        if event.event_type == CampaignEventType.CAMPAIGN_FORMED:
            return SignalAction.ENTRY

        if event.event_type == CampaignEventType.PATTERN_DETECTED:
            pattern_type = event.pattern_type
            if pattern_type == "Spring":
                return SignalAction.ENTRY
            elif pattern_type == "SOS":
                return SignalAction.ADD
            elif pattern_type in ("LPS", "Exit"):
                return SignalAction.EXIT

        return None

    async def _run_safety_checks(
        self,
        symbol: str,
        action: SignalAction,
        entry_price: Decimal,
        stop_loss: Decimal,
        account_balance: Decimal,
    ) -> None:
        """
        Run all safety checks before execution.

        Raises:
            SafetyCheckError: If any check fails
        """
        # Balance check
        if self._config.require_balance_check:
            if account_balance <= Decimal("0"):
                raise SafetyCheckError(
                    "balance",
                    f"Insufficient balance: ${account_balance}",
                    {"balance": float(account_balance)},
                )

        # Position check for ADD/EXIT
        if self._config.require_position_check and action in (
            SignalAction.ADD,
            SignalAction.EXIT,
        ):
            position = await self._adapter.get_position(symbol)
            if action == SignalAction.ADD and position is None:
                raise SafetyCheckError(
                    "position",
                    f"Cannot ADD: no existing position for {symbol}",
                    {"symbol": symbol, "action": action.value},
                )
            if action == SignalAction.EXIT and position is None:
                raise SafetyCheckError(
                    "position",
                    f"Cannot EXIT: no position for {symbol}",
                    {"symbol": symbol, "action": action.value},
                )

        # Entry price/stop loss validation
        if entry_price <= Decimal("0"):
            raise SafetyCheckError(
                "validation",
                "Entry price must be positive",
                {"entry_price": float(entry_price)},
            )

        if stop_loss <= Decimal("0"):
            raise SafetyCheckError(
                "validation",
                "Stop loss must be positive",
                {"stop_loss": float(stop_loss)},
            )

        if stop_loss >= entry_price:
            raise SafetyCheckError(
                "validation",
                "Stop loss must be below entry price for long positions",
                {"entry_price": float(entry_price), "stop_loss": float(stop_loss)},
            )

        logger.debug(
            "safety_checks_passed",
            symbol=symbol,
            action=action.value,
            balance=float(account_balance),
        )

    def _calculate_position_size(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        account_balance: Decimal,
    ) -> Decimal:
        """
        Calculate position size using 2% risk rule.

        Formula: Position Size = (Account * Risk%) / (Entry - Stop)

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            account_balance: Account balance

        Returns:
            Position size (shares/lots)
        """
        risk_per_share = entry_price - stop_loss

        if risk_per_share <= Decimal("0"):
            raise SafetyCheckError(
                "position_sizing",
                "Invalid risk per share (entry must be above stop)",
                {
                    "entry_price": float(entry_price),
                    "stop_loss": float(stop_loss),
                    "risk_per_share": float(risk_per_share),
                },
            )

        # 2% risk rule
        max_risk_amount = account_balance * (self._config.max_risk_per_trade_pct / Decimal("100"))
        position_size = max_risk_amount / risk_per_share

        # Apply max position size limit
        if position_size > self._config.max_position_size:
            logger.info(
                "position_size_capped",
                calculated=float(position_size),
                max=float(self._config.max_position_size),
            )
            position_size = self._config.max_position_size

        # Round down to whole shares
        position_size = position_size.quantize(Decimal("1"), rounding="ROUND_DOWN")

        logger.debug(
            "position_size_calculated",
            position_size=float(position_size),
            risk_amount=float(max_risk_amount),
            risk_per_share=float(risk_per_share),
        )

        return position_size

    def _validate_order(self, order: Order) -> None:
        """
        Validate order before submission.

        Raises:
            SafetyCheckError: If order is invalid
        """
        if not order.symbol:
            raise SafetyCheckError("validation", "Order missing symbol")

        if order.quantity <= Decimal("0"):
            raise SafetyCheckError(
                "validation",
                f"Invalid order quantity: {order.quantity}",
                {"quantity": float(order.quantity)},
            )

        if order.quantity > self._config.max_position_size:
            raise SafetyCheckError(
                "validation",
                f"Order quantity {order.quantity} exceeds max {self._config.max_position_size}",
                {
                    "quantity": float(order.quantity),
                    "max": float(self._config.max_position_size),
                },
            )

        logger.debug("order_validated", order_id=str(order.id), symbol=order.symbol)

    def _log_execution(
        self,
        event: str,
        success: bool,
        details: dict[str, Any],
    ) -> None:
        """Log execution event."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "success": success,
            "mode": self._mode.value,
            **details,
        }
        self._execution_log.append(log_entry)

        # Keep log manageable
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-500:]

    def get_execution_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent execution log entries."""
        return self._execution_log[-limit:]
