"""
Engine Package Interfaces (Story 18.9.1)

Protocol definitions and configuration dataclasses for the consolidated
backtest engine. This module provides the foundation for engine consolidation
by defining clear contracts for signal detection and cost modeling.

Protocols:
----------
- SignalDetector: Strategy pattern for signal detection
- CostModel: Strategy pattern for commission and slippage calculation

Dataclasses:
------------
- EngineConfig: Engine-level configuration for backtesting

Reference: CF-002 from Critical Foundation Refactoring document.
Author: Story 18.9.1
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from src.models.backtest import BacktestOrder
    from src.models.ohlcv import OHLCVBar
    from src.models.signal import TradeSignal


class SignalDetector(Protocol):
    """
    Strategy pattern interface for signal detection.

    Implementations detect trading signals from OHLCV bar data.
    Used by the backtest engine to decouple signal detection
    from the core backtesting logic.

    Methods:
    --------
    detect(bars, index) -> Optional[TradeSignal]
        Analyze bars up to index and return a signal if detected.

    Example Implementation:
    -----------------------
    class SpringSignalDetector:
        def detect(
            self, bars: list[OHLCVBar], index: int
        ) -> Optional[TradeSignal]:
            # Analyze bars[0:index+1] for Spring pattern
            # Return TradeSignal if pattern detected, None otherwise
            ...
    """

    def detect(self, bars: list["OHLCVBar"], index: int) -> Optional["TradeSignal"]:
        """
        Detect a trading signal at the given bar index.

        Args:
            bars: List of OHLCV bars (historical data)
            index: Current bar index to analyze (0-based)

        Returns:
            TradeSignal if a valid signal is detected, None otherwise

        Note:
            Implementation should only use bars[0:index+1] to avoid
            look-ahead bias. The bar at `index` is the current bar.
        """
        ...


class CostModel(Protocol):
    """
    Strategy pattern interface for transaction cost calculation.

    Implementations calculate commission and slippage costs for orders.
    Used by the backtest engine to provide realistic cost modeling
    without coupling to specific broker implementations.

    Methods:
    --------
    calculate_commission(order) -> Decimal
        Calculate commission cost for an order.

    calculate_slippage(order, bar) -> Decimal
        Calculate slippage cost based on order and market conditions.

    Example Implementation:
    -----------------------
    class IBKRCostModel:
        def calculate_commission(self, order: BacktestOrder) -> Decimal:
            # $0.005 per share, min $1.00
            return max(Decimal("1.00"), order.quantity * Decimal("0.005"))

        def calculate_slippage(
            self, order: BacktestOrder, bar: OHLCVBar
        ) -> Decimal:
            # Slippage based on spread and volume
            ...
    """

    def calculate_commission(self, order: "BacktestOrder") -> Decimal:
        """
        Calculate commission cost for an order.

        Args:
            order: The order to calculate commission for

        Returns:
            Commission cost as Decimal (in account currency)
        """
        ...

    def calculate_slippage(self, order: "BacktestOrder", bar: "OHLCVBar") -> Decimal:
        """
        Calculate slippage cost for an order.

        Slippage is the difference between expected and actual fill price,
        typically affected by order size, liquidity, and market volatility.

        Args:
            order: The order to calculate slippage for
            bar: The bar where the order will be filled (for market data)

        Returns:
            Slippage cost as Decimal (price impact per share)
        """
        ...


@dataclass
class EngineConfig:
    """
    Engine-level configuration for backtesting.

    Simplified configuration dataclass for the consolidated backtest engine.
    Provides essential parameters needed for running a backtest without
    the complexity of the full BacktestConfig model in src.models.backtest.

    Attributes:
    -----------
    initial_capital : Decimal
        Starting capital for the backtest (default: $100,000)

    max_position_size : Decimal
        Maximum position size as fraction of capital (default: 0.02 = 2%)

    enable_cost_model : bool
        Whether to apply commission and slippage costs (default: True)

    risk_per_trade : Decimal
        Maximum risk per trade as fraction of capital (default: 0.02 = 2%)

    max_open_positions : int
        Maximum number of concurrent open positions (default: 5, max: 100)

    Example:
    --------
    >>> config = EngineConfig(
    ...     initial_capital=Decimal("50000"),
    ...     max_position_size=Decimal("0.05"),
    ...     enable_cost_model=True
    ... )
    """

    initial_capital: Decimal = field(default_factory=lambda: Decimal("100000"))
    max_position_size: Decimal = field(default_factory=lambda: Decimal("0.02"))
    enable_cost_model: bool = True
    risk_per_trade: Decimal = field(default_factory=lambda: Decimal("0.02"))
    max_open_positions: int = 5

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if self.initial_capital <= Decimal("0"):
            raise ValueError(f"initial_capital must be positive, got {self.initial_capital}")
        if not Decimal("0") < self.max_position_size <= Decimal("1"):
            raise ValueError(f"max_position_size must be in (0, 1], got {self.max_position_size}")
        if not Decimal("0") < self.risk_per_trade <= Decimal("1"):
            raise ValueError(f"risk_per_trade must be in (0, 1], got {self.risk_per_trade}")
        if not 1 <= self.max_open_positions <= 100:
            raise ValueError(
                f"max_open_positions must be in [1, 100], got {self.max_open_positions}"
            )
