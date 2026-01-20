"""Trading services package."""

from src.trading.automated_execution_service import (
    AutomatedExecutionService,
    ExecutionConfig,
    ExecutionMode,
    ExecutionReport,
    Order,
    OrderState,
    PatternType,
    SafetyCheckError,
    SignalAction,
    TradeDirection,
    TradingPlatformAdapter,
)

__all__ = [
    "AutomatedExecutionService",
    "ExecutionConfig",
    "ExecutionMode",
    "ExecutionReport",
    "Order",
    "OrderState",
    "PatternType",
    "SafetyCheckError",
    "SignalAction",
    "TradeDirection",
    "TradingPlatformAdapter",
]
