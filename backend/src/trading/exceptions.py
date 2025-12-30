"""
Paper Trading Exception Classes (Story 12.8 Task 19)

Custom exception hierarchy for paper trading operations.
Provides specific error types for better error handling and user feedback.

Author: Story 12.8
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID


class PaperTradingError(Exception):
    """Base exception for all paper trading errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        """
        Initialize paper trading error.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PaperAccountNotFoundError(PaperTradingError):
    """Raised when paper trading account is not found or not enabled."""

    def __init__(self, message: str = "Paper trading not enabled. Enable paper trading first."):
        super().__init__(message)


class InsufficientCapitalError(PaperTradingError):
    """Raised when account has insufficient capital for a trade."""

    def __init__(
        self,
        required: Decimal,
        available: Decimal,
        symbol: str,
        message: Optional[str] = None,
    ):
        """
        Initialize insufficient capital error.

        Args:
            required: Capital required for trade
            available: Available capital in account
            symbol: Trading symbol
            message: Optional custom message
        """
        if message is None:
            message = (
                f"Insufficient capital for {symbol}: "
                f"need ${required:.2f}, have ${available:.2f}"
            )

        super().__init__(
            message,
            details={
                "required": float(required),
                "available": float(available),
                "symbol": symbol,
                "shortfall": float(required - available),
            },
        )
        self.required = required
        self.available = available
        self.symbol = symbol


class RiskLimitExceededError(PaperTradingError):
    """Raised when a trade would exceed risk management limits."""

    def __init__(
        self,
        limit_type: str,
        limit_value: Decimal,
        actual_value: Decimal,
        symbol: str,
        message: Optional[str] = None,
    ):
        """
        Initialize risk limit exceeded error.

        Args:
            limit_type: Type of limit exceeded (per_trade_risk, portfolio_heat, etc.)
            limit_value: Maximum allowed value
            actual_value: Actual value that exceeded limit
            symbol: Trading symbol
            message: Optional custom message
        """
        if message is None:
            message = (
                f"{limit_type} exceeded for {symbol}: "
                f"{actual_value:.2f}% exceeds limit of {limit_value:.2f}%"
            )

        super().__init__(
            message,
            details={
                "limit_type": limit_type,
                "limit_value": float(limit_value),
                "actual_value": float(actual_value),
                "symbol": symbol,
                "excess": float(actual_value - limit_value),
            },
        )
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.actual_value = actual_value
        self.symbol = symbol


class PositionNotFoundError(PaperTradingError):
    """Raised when a position cannot be found."""

    def __init__(self, position_id: UUID, message: Optional[str] = None):
        """
        Initialize position not found error.

        Args:
            position_id: UUID of missing position
            message: Optional custom message
        """
        if message is None:
            message = f"Position not found: {position_id}"

        super().__init__(message, details={"position_id": str(position_id)})
        self.position_id = position_id


class InvalidPositionStateError(PaperTradingError):
    """Raised when attempting an operation on a position in invalid state."""

    def __init__(
        self,
        position_id: UUID,
        current_state: str,
        required_state: str,
        message: Optional[str] = None,
    ):
        """
        Initialize invalid position state error.

        Args:
            position_id: UUID of position
            current_state: Current position state
            required_state: Required state for operation
            message: Optional custom message
        """
        if message is None:
            message = (
                f"Position {position_id} is in state '{current_state}', "
                f"but operation requires '{required_state}'"
            )

        super().__init__(
            message,
            details={
                "position_id": str(position_id),
                "current_state": current_state,
                "required_state": required_state,
            },
        )
        self.position_id = position_id
        self.current_state = current_state
        self.required_state = required_state


class MarketDataUnavailableError(PaperTradingError):
    """Raised when market data is unavailable for a symbol."""

    def __init__(self, symbol: str, message: Optional[str] = None):
        """
        Initialize market data unavailable error.

        Args:
            symbol: Trading symbol
            message: Optional custom message
        """
        if message is None:
            message = f"Market data unavailable for {symbol}"

        super().__init__(message, details={"symbol": symbol})
        self.symbol = symbol


class StalePositionError(PaperTradingError):
    """Raised when a position has not been updated recently (stale data)."""

    def __init__(
        self,
        position_id: UUID,
        symbol: str,
        last_update_minutes: int,
        threshold_minutes: int = 60,
        message: Optional[str] = None,
    ):
        """
        Initialize stale position error.

        Args:
            position_id: UUID of position
            symbol: Trading symbol
            last_update_minutes: Minutes since last update
            threshold_minutes: Threshold for considering stale
            message: Optional custom message
        """
        if message is None:
            message = (
                f"Position {position_id} for {symbol} is stale: "
                f"last updated {last_update_minutes} minutes ago "
                f"(threshold: {threshold_minutes} minutes)"
            )

        super().__init__(
            message,
            details={
                "position_id": str(position_id),
                "symbol": symbol,
                "last_update_minutes": last_update_minutes,
                "threshold_minutes": threshold_minutes,
            },
        )
        self.position_id = position_id
        self.symbol = symbol
        self.last_update_minutes = last_update_minutes


class NegativeBalanceError(PaperTradingError):
    """Raised when account balance would become negative."""

    def __init__(
        self,
        current_balance: Decimal,
        deduction: Decimal,
        message: Optional[str] = None,
    ):
        """
        Initialize negative balance error.

        Args:
            current_balance: Current account balance
            deduction: Amount attempting to deduct
            message: Optional custom message
        """
        if message is None:
            message = (
                f"Operation would result in negative balance: "
                f"current ${current_balance:.2f}, deduction ${deduction:.2f}"
            )

        super().__init__(
            message,
            details={
                "current_balance": float(current_balance),
                "deduction": float(deduction),
                "resulting_balance": float(current_balance - deduction),
            },
        )
        self.current_balance = current_balance
        self.deduction = deduction


class DuplicateSignalError(PaperTradingError):
    """Raised when attempting to execute the same signal multiple times."""

    def __init__(self, signal_id: UUID, message: Optional[str] = None):
        """
        Initialize duplicate signal error.

        Args:
            signal_id: UUID of duplicate signal
            message: Optional custom message
        """
        if message is None:
            message = f"Signal {signal_id} has already been executed"

        super().__init__(message, details={"signal_id": str(signal_id)})
        self.signal_id = signal_id


class InvalidConfigurationError(PaperTradingError):
    """Raised when paper trading configuration is invalid."""

    def __init__(self, config_field: str, message: str):
        """
        Initialize invalid configuration error.

        Args:
            config_field: Name of invalid configuration field
            message: Error message
        """
        super().__init__(message, details={"config_field": config_field})
        self.config_field = config_field
