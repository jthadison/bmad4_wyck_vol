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
- Portfolio heat validation (10% max - FR18)
- Campaign risk validation (5% max - FR18)
- Correlated risk validation (6% max - FR18)
- Support for both LONG and SHORT positions
- Integration with platform adapters (Story 16.4a)
- Retry logic for transient failures
- Order state tracking

Signal Types:
-------------
- ENTRY: Initial campaign entry (Spring for long, UTAD for short)
- ADD: Position add (SOS pattern)
- EXIT: Position exit (LPS or target hit)

Author: Story 16.4b
"""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4

import structlog

from src.models.campaign_event import CampaignEvent, CampaignEventType
from src.risk_management.execution_risk_gate import ExecutionRiskGate

logger = structlog.get_logger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode for automated trading."""

    DISABLED = "DISABLED"  # Automation off
    PAPER = "PAPER"  # Paper trading mode
    LIVE = "LIVE"  # Live trading mode


class TradeDirection(str, Enum):
    """Trade direction for position."""

    LONG = "LONG"  # Buy low, sell high
    SHORT = "SHORT"  # Sell high, buy low


class SignalAction(str, Enum):
    """Campaign signal action types."""

    ENTRY = "ENTRY"  # Initial entry (Spring/UTAD)
    ADD = "ADD"  # Add to position (SOS)
    EXIT = "EXIT"  # Exit position


class OrderState(str, Enum):
    """Order lifecycle states."""

    PENDING = "PENDING"  # Created, not yet submitted
    SUBMITTED = "SUBMITTED"  # Sent to platform
    FILLED = "FILLED"  # Execution complete
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partial execution
    CANCELLED = "CANCELLED"  # Cancelled by user or system
    REJECTED = "REJECTED"  # Rejected by platform
    EXPIRED = "EXPIRED"  # Order expired
    FAILED = "FAILED"  # Execution failed


class PatternType(str, Enum):
    """
    Wyckoff pattern types with trade direction mapping.

    Long Patterns (accumulation):
    - Spring: Shakeout below support (Phase C entry)
    - SOS: Sign of Strength breakout (Phase D add)
    - LPS: Last Point of Support retest (Phase E add/exit)
    - SC: Selling Climax (Phase A)
    - AR: Automatic Rally (Phase A)
    - ST: Secondary Test (confirmation, not entry)

    Short Patterns (distribution):
    - UTAD: Upthrust After Distribution (Phase C entry)
    - SOW: Sign of Weakness breakdown
    - LPSY: Last Point of Supply
    """

    # Long patterns (accumulation)
    SPRING = "Spring"
    SOS = "SOS"
    LPS = "LPS"
    SC = "SC"
    AR = "AR"
    ST = "ST"

    # Short patterns (distribution)
    UTAD = "UTAD"
    SOW = "SOW"
    LPSY = "LPSY"

    @classmethod
    def get_direction(cls, pattern: str) -> TradeDirection:
        """Get trade direction for a pattern type."""
        short_patterns = {cls.UTAD.value, cls.SOW.value, cls.LPSY.value}
        if pattern in short_patterns:
            return TradeDirection.SHORT
        return TradeDirection.LONG

    @classmethod
    def get_action(cls, pattern: str) -> SignalAction | None:
        """Get signal action for a pattern type."""
        entry_patterns = {cls.SPRING.value, cls.UTAD.value}
        add_patterns = {cls.SOS.value, cls.SOW.value}
        exit_patterns = {cls.LPS.value, cls.LPSY.value, "Exit"}

        if pattern in entry_patterns:
            return SignalAction.ENTRY
        elif pattern in add_patterns:
            return SignalAction.ADD
        elif pattern in exit_patterns:
            return SignalAction.EXIT
        return None


# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_MS = 100
DEFAULT_EXECUTION_LOG_SIZE = 500


@dataclass
class ExecutionConfig:
    """Configuration for automated execution."""

    # Risk limits (FR18 - Non-negotiable)
    max_risk_per_trade_pct: Decimal = Decimal("2.0")  # 2% max per trade
    max_campaign_risk_pct: Decimal = Decimal("5.0")  # 5% max per campaign
    max_correlated_risk_pct: Decimal = Decimal("6.0")  # 6% max correlated
    max_portfolio_heat_pct: Decimal = Decimal("10.0")  # 10% max portfolio heat

    # Position limits
    max_position_size: Decimal = Decimal("10000")  # Max shares/lots
    max_position_value_pct: Decimal = Decimal("20.0")  # 20% max position value

    # Execution settings
    order_timeout_ms: int = 500  # Max execution time before warning
    cancel_on_timeout: bool = False  # Cancel order if timeout exceeded

    # Safety checks
    require_balance_check: bool = True
    require_position_check: bool = True
    require_portfolio_heat_check: bool = True
    require_campaign_risk_check: bool = True
    require_correlated_risk_check: bool = True

    # Retry settings
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay_ms: int = DEFAULT_RETRY_DELAY_MS

    # Logging
    execution_log_size: int = DEFAULT_EXECUTION_LOG_SIZE


@dataclass
class Order:
    """Order to be submitted to trading platform."""

    id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    action: SignalAction = SignalAction.ENTRY
    direction: TradeDirection = TradeDirection.LONG
    quantity: Decimal = Decimal("0")
    order_type: str = "MARKET"  # MARKET, LIMIT, STOP
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    state: OrderState = OrderState.PENDING
    campaign_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_state(self, new_state: OrderState) -> None:
        """Update order state with timestamp."""
        self.state = new_state
        self.updated_at = datetime.now(UTC)


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
    retry_count: int = 0
    final_state: OrderState = OrderState.PENDING


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

    async def get_portfolio_heat(self) -> Decimal:
        """Get current portfolio heat as percentage."""
        ...

    async def get_campaign_risk(self, campaign_id: str) -> Decimal:
        """Get current campaign risk as percentage."""
        ...

    async def get_correlated_risk(self, symbol: str) -> Decimal:
        """Get correlated risk for symbol as percentage."""
        ...

    async def place_order(self, order: Order) -> ExecutionReport:
        """Place order on platform."""
        ...

    async def cancel_order(self, order_id: UUID) -> bool:
        """Cancel pending order."""
        ...

    async def get_order_status(self, order_id: UUID) -> OrderState:
        """Get current order status."""
        ...


# Type alias for risk check callback
RiskCheckCallback = Callable[[str, Decimal], bool]


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
    - 2% max risk per trade (FR18)
    - 5% max campaign risk (FR18)
    - 6% max correlated risk (FR18)
    - 10% max portfolio heat (FR18)
    - Pre-trade balance validation
    - Position existence checks
    - Order validation
    - Kill switch for emergencies
    - Retry logic for transient failures
    - Order state tracking
    """

    def __init__(
        self,
        adapter: TradingPlatformAdapter | None = None,
        config: ExecutionConfig | None = None,
        risk_gate: ExecutionRiskGate | None = None,
    ):
        """
        Initialize automated execution service.

        Args:
            adapter: Trading platform adapter (optional, can be set later)
            config: Execution configuration
            risk_gate: Pre-flight risk gate (Story 23.11). If None, a default is created.
        """
        self._adapter = adapter
        self._config = config or ExecutionConfig()
        self._risk_gate = risk_gate or ExecutionRiskGate()
        self._mode = ExecutionMode.DISABLED
        self._kill_switch_active = False

        # Use deque for efficient log management (auto-prunes)
        self._execution_log: deque[dict[str, Any]] = deque(maxlen=self._config.execution_log_size)

        # Track pending orders for state management
        self._pending_orders: dict[UUID, Order] = {}

        logger.info(
            "automated_execution_service_initialized",
            mode=self._mode.value,
            max_risk_pct=float(self._config.max_risk_per_trade_pct),
            max_campaign_risk_pct=float(self._config.max_campaign_risk_pct),
            max_correlated_risk_pct=float(self._config.max_correlated_risk_pct),
            max_portfolio_heat_pct=float(self._config.max_portfolio_heat_pct),
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

    def get_order(self, order_id: UUID) -> Order | None:
        """Get order by ID from pending orders."""
        return self._pending_orders.get(order_id)

    def get_pending_orders(self) -> list[Order]:
        """Get all pending orders."""
        return list(self._pending_orders.values())

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

        # Determine action and direction from event type
        action, direction = self._determine_action_and_direction(event)
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

        # Run safety checks (includes all FR18 risk limits)
        await self._run_safety_checks(
            symbol=symbol,
            action=action,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            account_balance=account_balance,
            campaign_id=event.campaign_id,
        )

        # Calculate position size
        quantity = self._calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            account_balance=account_balance,
            direction=direction,
        )

        # Build order
        order = Order(
            symbol=symbol,
            action=action,
            direction=direction,
            quantity=quantity,
            order_type="MARKET",
            stop_loss=stop_loss,
            campaign_id=event.campaign_id,
        )

        # Validate order
        self._validate_order(order)

        # Track order
        self._pending_orders[order.id] = order

        # Execute with retry logic
        report = await self._execute_with_retry(order, entry_price, start_time)

        return report

    def _determine_action_and_direction(
        self, event: CampaignEvent
    ) -> tuple[SignalAction | None, TradeDirection]:
        """Determine signal action and trade direction from campaign event."""
        direction = TradeDirection.LONG  # Default

        if event.event_type == CampaignEventType.CAMPAIGN_FORMED:
            # Check metadata for direction hint
            if event.metadata.get("direction") == "SHORT":
                direction = TradeDirection.SHORT
            return SignalAction.ENTRY, direction

        if event.event_type == CampaignEventType.PATTERN_DETECTED:
            pattern_type = event.pattern_type
            if pattern_type:
                direction = PatternType.get_direction(pattern_type)
                action = PatternType.get_action(pattern_type)
                return action, direction

        return None, direction

    async def _execute_with_retry(
        self,
        order: Order,
        entry_price: Decimal,
        start_time: datetime,
    ) -> ExecutionReport:
        """Execute order with retry logic for transient failures."""
        last_error: str | None = None
        retry_count = 0

        for attempt in range(self._config.max_retries + 1):
            # Double-check kill switch before each attempt (race condition fix)
            if self._kill_switch_active:
                logger.warning(
                    "execution_aborted_kill_switch",
                    order_id=str(order.id),
                    attempt=attempt,
                )
                order.update_state(OrderState.CANCELLED)
                return ExecutionReport(
                    order_id=order.id,
                    success=False,
                    error_message="Kill switch activated during execution",
                    retry_count=retry_count,
                    final_state=OrderState.CANCELLED,
                )

            try:
                # Final risk gate enforcement (Story 23.11)
                # Compute actual trade risk from position size and stop loss,
                # then query portfolio state from adapter for heat/campaign/correlated.
                try:
                    current_heat = await self._adapter.get_portfolio_heat()
                except AttributeError:
                    # Fail-closed: can't determine heat, block the order
                    current_heat = Decimal("100")
                    logger.warning(
                        "portfolio_heat_unknown_fail_closed",
                        order_id=str(order.id),
                        reason="Adapter does not support get_portfolio_heat",
                    )

                # Compute actual trade risk from order details
                if order.stop_loss and entry_price > 0:
                    try:
                        acct_balance = await self._adapter.get_account_balance()
                    except Exception:
                        acct_balance = Decimal("0")
                    risk_per_unit = abs(entry_price - order.stop_loss)
                    if acct_balance > 0:
                        actual_trade_risk = (
                            order.quantity * risk_per_unit / acct_balance
                        ) * Decimal("100")
                    else:
                        # Fail-closed: no balance info
                        actual_trade_risk = Decimal("100")
                else:
                    # Fail-closed: can't compute risk without stop loss
                    actual_trade_risk = Decimal("100")

                # Query campaign risk if available
                campaign_risk: Decimal | None = None
                try:
                    if order.campaign_id:
                        campaign_risk = await self._adapter.get_campaign_risk(order.campaign_id)
                except AttributeError:
                    pass

                # Query correlated risk if available
                correlated_risk: Decimal | None = None
                try:
                    correlated_risk = await self._adapter.get_correlated_risk(order.symbol)
                except AttributeError:
                    pass

                preflight = self._risk_gate.check_risk_values(
                    order_id=str(order.id),
                    symbol=order.symbol,
                    trade_risk_pct=actual_trade_risk,
                    portfolio_heat_pct=current_heat,
                    campaign_risk_pct=campaign_risk,
                    correlated_risk_pct=correlated_risk,
                )
                if preflight.blocked:
                    violation_msgs = "; ".join(v.message for v in preflight.violations)
                    logger.warning(
                        "execution_blocked_by_risk_gate",
                        order_id=str(order.id),
                        violations=violation_msgs,
                    )
                    order.update_state(OrderState.REJECTED)
                    return ExecutionReport(
                        order_id=order.id,
                        success=False,
                        error_message=f"Risk gate blocked: {violation_msgs}",
                        retry_count=retry_count,
                        final_state=OrderState.REJECTED,
                    )

                order.update_state(OrderState.SUBMITTED)

                logger.info(
                    "executing_order",
                    order_id=str(order.id),
                    symbol=order.symbol,
                    action=order.action.value,
                    direction=order.direction.value,
                    quantity=float(order.quantity),
                    entry_price=float(entry_price),
                    attempt=attempt + 1,
                )

                report = await self._adapter.place_order(order)

                # Calculate execution time
                end_time = datetime.now(UTC)
                report.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
                report.retry_count = retry_count

                if report.success:
                    order.update_state(OrderState.FILLED)
                    report.final_state = OrderState.FILLED

                    # Remove from pending
                    self._pending_orders.pop(order.id, None)

                    # Log success
                    self._log_execution(
                        event="ORDER_EXECUTED",
                        success=True,
                        details={
                            "order_id": str(order.id),
                            "symbol": order.symbol,
                            "action": order.action.value,
                            "direction": order.direction.value,
                            "quantity": float(order.quantity),
                            "fill_price": float(report.fill_price) if report.fill_price else None,
                            "execution_time_ms": report.execution_time_ms,
                            "retry_count": retry_count,
                        },
                    )

                    # Check execution time and handle timeout
                    if report.execution_time_ms > self._config.order_timeout_ms:
                        logger.warning(
                            "execution_timeout_exceeded",
                            execution_time_ms=report.execution_time_ms,
                            limit_ms=self._config.order_timeout_ms,
                        )

                    return report

                # Order failed but not retryable
                last_error = report.error_message
                if not self._is_retryable_error(report.error_message):
                    break

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "order_execution_error",
                    order_id=str(order.id),
                    attempt=attempt + 1,
                    error=str(e),
                )

                if not self._is_retryable_error(str(e)):
                    break

            # Wait before retry
            if attempt < self._config.max_retries:
                retry_count += 1
                await asyncio.sleep(self._config.retry_delay_ms / 1000)

        # All retries exhausted
        order.update_state(OrderState.FAILED)

        # Handle timeout with cancel if configured
        if self._config.cancel_on_timeout:
            try:
                await self._adapter.cancel_order(order.id)
                order.update_state(OrderState.CANCELLED)
            except Exception as cancel_error:
                logger.error(
                    "order_cancel_failed",
                    order_id=str(order.id),
                    error=str(cancel_error),
                )

        # Remove from pending
        self._pending_orders.pop(order.id, None)

        self._log_execution(
            event="ORDER_FAILED",
            success=False,
            details={
                "order_id": str(order.id),
                "symbol": order.symbol,
                "error": last_error,
                "retry_count": retry_count,
            },
        )

        end_time = datetime.now(UTC)
        return ExecutionReport(
            order_id=order.id,
            success=False,
            error_message=last_error,
            execution_time_ms=int((end_time - start_time).total_seconds() * 1000),
            retry_count=retry_count,
            final_state=order.state,
        )

    def _is_retryable_error(self, error: str | None) -> bool:
        """Check if error is transient and retryable."""
        if not error:
            return False

        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "retry",
            "503",
            "504",
        ]
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in retryable_patterns)

    async def _run_safety_checks(
        self,
        symbol: str,
        action: SignalAction,
        direction: TradeDirection,
        entry_price: Decimal,
        stop_loss: Decimal,
        account_balance: Decimal,
        campaign_id: str,
    ) -> None:
        """
        Run all safety checks before execution.

        Validates all FR18 risk limits:
        - Per-trade risk (2%)
        - Campaign risk (5%)
        - Correlated risk (6%)
        - Portfolio heat (10%)

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

        # Direction-aware stop loss validation
        if direction == TradeDirection.LONG:
            if stop_loss >= entry_price:
                raise SafetyCheckError(
                    "validation",
                    "Stop loss must be below entry price for LONG positions",
                    {
                        "entry_price": float(entry_price),
                        "stop_loss": float(stop_loss),
                        "direction": direction.value,
                    },
                )
        else:  # SHORT
            if stop_loss <= entry_price:
                raise SafetyCheckError(
                    "validation",
                    "Stop loss must be above entry price for SHORT positions",
                    {
                        "entry_price": float(entry_price),
                        "stop_loss": float(stop_loss),
                        "direction": direction.value,
                    },
                )

        # Portfolio heat check (10% max - FR18)
        if self._config.require_portfolio_heat_check:
            try:
                current_heat = await self._adapter.get_portfolio_heat()
                if current_heat >= self._config.max_portfolio_heat_pct:
                    raise SafetyCheckError(
                        "portfolio_heat",
                        f"Portfolio heat {current_heat}% exceeds limit of {self._config.max_portfolio_heat_pct}%",
                        {
                            "current_heat": float(current_heat),
                            "limit": float(self._config.max_portfolio_heat_pct),
                        },
                    )
            except AttributeError:
                # Adapter doesn't support portfolio heat check
                logger.debug("portfolio_heat_check_skipped_not_supported")

        # Campaign risk check (5% max - FR18)
        if self._config.require_campaign_risk_check and campaign_id:
            try:
                campaign_risk = await self._adapter.get_campaign_risk(campaign_id)
                if campaign_risk >= self._config.max_campaign_risk_pct:
                    raise SafetyCheckError(
                        "campaign_risk",
                        f"Campaign risk {campaign_risk}% exceeds limit of {self._config.max_campaign_risk_pct}%",
                        {
                            "campaign_id": campaign_id,
                            "current_risk": float(campaign_risk),
                            "limit": float(self._config.max_campaign_risk_pct),
                        },
                    )
            except AttributeError:
                # Adapter doesn't support campaign risk check
                logger.debug("campaign_risk_check_skipped_not_supported")

        # Correlated risk check (6% max - FR18)
        if self._config.require_correlated_risk_check:
            try:
                correlated_risk = await self._adapter.get_correlated_risk(symbol)
                if correlated_risk >= self._config.max_correlated_risk_pct:
                    raise SafetyCheckError(
                        "correlated_risk",
                        f"Correlated risk {correlated_risk}% exceeds limit of {self._config.max_correlated_risk_pct}%",
                        {
                            "symbol": symbol,
                            "current_risk": float(correlated_risk),
                            "limit": float(self._config.max_correlated_risk_pct),
                        },
                    )
            except AttributeError:
                # Adapter doesn't support correlated risk check
                logger.debug("correlated_risk_check_skipped_not_supported")

        logger.debug(
            "safety_checks_passed",
            symbol=symbol,
            action=action.value,
            direction=direction.value,
            balance=float(account_balance),
        )

    def _calculate_position_size(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        account_balance: Decimal,
        direction: TradeDirection = TradeDirection.LONG,
    ) -> Decimal:
        """
        Calculate position size using 2% risk rule.

        Formula: Position Size = (Account * Risk%) / |Entry - Stop|

        Supports both LONG and SHORT positions.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            account_balance: Account balance
            direction: Trade direction (LONG or SHORT)

        Returns:
            Position size (shares/lots)
        """
        # Calculate risk per share (absolute value for both directions)
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share <= Decimal("0"):
            raise SafetyCheckError(
                "position_sizing",
                "Invalid risk per share (entry and stop cannot be equal)",
                {
                    "entry_price": float(entry_price),
                    "stop_loss": float(stop_loss),
                    "direction": direction.value,
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

        # Apply max position value limit (20% of equity - FR18)
        max_value = account_balance * (self._config.max_position_value_pct / Decimal("100"))
        max_shares_by_value = max_value / entry_price
        if position_size > max_shares_by_value:
            logger.info(
                "position_size_capped_by_value",
                calculated=float(position_size),
                max_by_value=float(max_shares_by_value),
            )
            position_size = max_shares_by_value

        # Round down to whole shares
        position_size = position_size.quantize(Decimal("1"), rounding="ROUND_DOWN")

        logger.debug(
            "position_size_calculated",
            position_size=float(position_size),
            risk_amount=float(max_risk_amount),
            risk_per_share=float(risk_per_share),
            direction=direction.value,
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
        """Log execution event to deque (auto-prunes at maxlen)."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "success": success,
            "mode": self._mode.value,
            **details,
        }
        self._execution_log.append(log_entry)

    def get_execution_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent execution log entries."""
        log_list = list(self._execution_log)
        return log_list[-limit:] if limit < len(log_list) else log_list
