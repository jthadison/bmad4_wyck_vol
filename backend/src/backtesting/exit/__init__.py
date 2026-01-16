"""
Exit Strategies Package - Story 18.11.1

Purpose:
--------
Pluggable exit strategy framework for backtesting engine.
Provides base classes, concrete implementations, and registry.

Public API:
-----------
Base Classes:
- ExitStrategy: Abstract base class for all exit strategies
- ExitContext: Context data for exit evaluation
- ExitSignal: Exit signal with reason and price

Concrete Strategies:
- TrailingStopStrategy: Trailing stop loss exits
- TargetExitStrategy: Profit target exits
- TimeBasedExitStrategy: Time-based forced exits

Registry:
- ExitStrategyRegistry: Runtime strategy selection

Usage:
------
>>> from src.backtesting.exit import (
...     ExitStrategyRegistry,
...     ExitContext,
...     TrailingStopStrategy,
... )
>>> registry = ExitStrategyRegistry()
>>> strategy = registry.get_strategy("trailing_stop")
>>> context = ExitContext(trailing_stop=Decimal("148.50"))
>>> signal = strategy.should_exit(position, bar, context)

Author: Story 18.11.1
"""

from src.backtesting.exit.base import ExitContext, ExitSignal, ExitStrategy
from src.backtesting.exit.target_exit import TargetExitStrategy
from src.backtesting.exit.time_based import TimeBasedExitStrategy
from src.backtesting.exit.trailing_stop import TrailingStopStrategy

__all__ = [
    # Base classes
    "ExitStrategy",
    "ExitContext",
    "ExitSignal",
    # Concrete strategies
    "TrailingStopStrategy",
    "TargetExitStrategy",
    "TimeBasedExitStrategy",
    # Registry
    "ExitStrategyRegistry",
]


class ExitStrategyRegistry:
    """
    Registry for exit strategies with runtime selection.

    Provides centralized access to all available exit strategies
    and allows dynamic strategy instantiation by name.

    Example:
    --------
    >>> registry = ExitStrategyRegistry()
    >>> trailing_stop = registry.get_strategy("trailing_stop")
    >>> target_exit = registry.get_strategy("target_exit")
    >>> all_strategies = registry.list_strategies()
    >>> print(all_strategies)  # ['trailing_stop', 'target_exit', 'time_exit']
    """

    _strategies: dict[str, type[ExitStrategy]] = {
        "trailing_stop": TrailingStopStrategy,
        "target_exit": TargetExitStrategy,
        "time_exit": TimeBasedExitStrategy,
    }

    @classmethod
    def get_strategy(cls, name: str) -> ExitStrategy:
        """
        Get exit strategy instance by name.

        Parameters:
        -----------
        name : str
            Strategy name ("trailing_stop", "target_exit", "time_exit")

        Returns:
        --------
        ExitStrategy
            Instantiated exit strategy

        Raises:
        -------
        ValueError
            If strategy name not found in registry

        Example:
        --------
        >>> strategy = ExitStrategyRegistry.get_strategy("trailing_stop")
        >>> assert strategy.name == "trailing_stop"
        """
        if name not in cls._strategies:
            raise ValueError(
                f"Unknown exit strategy: {name}. "
                f"Available strategies: {', '.join(cls._strategies.keys())}"
            )
        return cls._strategies[name]()

    @classmethod
    def list_strategies(cls) -> list[str]:
        """
        List all registered strategy names.

        Returns:
        --------
        list[str]
            List of available strategy names

        Example:
        --------
        >>> strategies = ExitStrategyRegistry.list_strategies()
        >>> assert "trailing_stop" in strategies
        """
        return list(cls._strategies.keys())

    @classmethod
    def register_strategy(cls, name: str, strategy_class: type[ExitStrategy]) -> None:
        """
        Register a new exit strategy (for extensions).

        Allows custom strategies to be registered at runtime.

        Parameters:
        -----------
        name : str
            Strategy name (must be unique)
        strategy_class : Type[ExitStrategy]
            Strategy class (must inherit from ExitStrategy)

        Raises:
        -------
        ValueError
            If name already registered or class doesn't inherit ExitStrategy

        Example:
        --------
        >>> class CustomExit(ExitStrategy):
        ...     @property
        ...     def name(self) -> str:
        ...         return "custom"
        ...     def should_exit(self, position, bar, context):
        ...         return None
        >>> ExitStrategyRegistry.register_strategy("custom", CustomExit)
        """
        if name in cls._strategies:
            raise ValueError(f"Strategy '{name}' already registered")

        if not issubclass(strategy_class, ExitStrategy):
            raise ValueError(
                f"Strategy class must inherit from ExitStrategy, " f"got {strategy_class.__name__}"
            )

        cls._strategies[name] = strategy_class
