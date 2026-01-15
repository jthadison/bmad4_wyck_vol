"""
Volume Strategy Registry (Story 18.6.1)

Provides a registry for pattern-specific volume validation strategies.
Strategies can be registered and retrieved by pattern type, enabling
extensibility without modifying existing code.

Reference: CF-006 from Critical Foundation Refactoring document.

Author: Story 18.6.1
"""

from typing import TypeVar

import structlog

from src.signal_generator.validators.volume.base import VolumeValidationStrategy

logger = structlog.get_logger()

# Type variable for strategy classes
T = TypeVar("T", bound=VolumeValidationStrategy)


class VolumeStrategyRegistry:
    """
    Registry for pattern-specific volume validation strategies.

    Provides a centralized store for registering and retrieving volume
    validation strategies by pattern type. This enables the Strategy pattern
    where new validators can be added without modifying existing code.

    Usage:
    ------
    >>> registry = VolumeStrategyRegistry()
    >>> registry.register(SpringVolumeStrategy())
    >>> registry.register(SOSVolumeStrategy())
    >>>
    >>> strategy = registry.get("SPRING")
    >>> result = strategy.validate(context, config)

    Class Methods:
    --------------
    - register(strategy): Register a strategy instance
    - get(pattern_type): Get registered strategy for pattern type
    - has(pattern_type): Check if pattern type has registered strategy
    - get_all(): Get all registered strategies
    - clear(): Remove all registered strategies (for testing)

    Thread Safety:
    --------------
    The registry uses a class-level dict which is thread-safe for reads.
    Registration should happen at startup, not during request handling.

    Implementation Note:
    --------------------
    The class-level `_strategies` dict is intentionally shared across all
    instances (singleton-like pattern). This enables global strategy
    registration without requiring explicit instance passing.
    """

    # Class-level shared registry (intentional singleton pattern)
    _strategies: dict[str, VolumeValidationStrategy] = {}

    @classmethod
    def register(cls, strategy: VolumeValidationStrategy) -> None:
        """
        Register a volume validation strategy.

        The strategy's pattern_type property is used as the registry key.
        If a strategy is already registered for the pattern type, it is
        replaced with a warning.

        Parameters:
        -----------
        strategy : VolumeValidationStrategy
            Strategy instance to register

        Example:
        --------
        >>> registry = VolumeStrategyRegistry()
        >>> registry.register(SpringVolumeStrategy())
        """
        pattern_type = strategy.pattern_type.upper()

        if pattern_type in cls._strategies:
            logger.warning(
                "volume_strategy_replaced",
                pattern_type=pattern_type,
                old_strategy=type(cls._strategies[pattern_type]).__name__,
                new_strategy=type(strategy).__name__,
            )

        cls._strategies[pattern_type] = strategy
        logger.info(
            "volume_strategy_registered",
            pattern_type=pattern_type,
            strategy_class=type(strategy).__name__,
        )

    @classmethod
    def get(cls, pattern_type: str) -> VolumeValidationStrategy | None:
        """
        Get registered strategy for a pattern type.

        Parameters:
        -----------
        pattern_type : str
            Pattern type to look up (case-insensitive)

        Returns:
        --------
        VolumeValidationStrategy | None
            Registered strategy, or None if not found

        Example:
        --------
        >>> strategy = VolumeStrategyRegistry.get("SPRING")
        >>> if strategy:
        ...     result = strategy.validate(context, config)
        """
        return cls._strategies.get(pattern_type.upper())

    @classmethod
    def has(cls, pattern_type: str) -> bool:
        """
        Check if a pattern type has a registered strategy.

        Parameters:
        -----------
        pattern_type : str
            Pattern type to check (case-insensitive)

        Returns:
        --------
        bool
            True if strategy is registered, False otherwise
        """
        return pattern_type.upper() in cls._strategies

    @classmethod
    def get_all(cls) -> dict[str, VolumeValidationStrategy]:
        """
        Get all registered strategies.

        Returns:
        --------
        dict[str, VolumeValidationStrategy]
            Copy of all registered strategies keyed by pattern type
        """
        return cls._strategies.copy()

    @classmethod
    def get_registered_patterns(cls) -> list[str]:
        """
        Get list of all registered pattern types.

        Returns:
        --------
        list[str]
            List of pattern type names with registered strategies
        """
        return list(cls._strategies.keys())

    @classmethod
    def clear(cls) -> None:
        """
        Remove all registered strategies.

        Primarily for testing to reset registry state between tests.

        Example:
        --------
        >>> VolumeStrategyRegistry.clear()
        >>> assert VolumeStrategyRegistry.get("SPRING") is None
        """
        cls._strategies.clear()
        logger.debug("volume_strategy_registry_cleared")

    @classmethod
    def count(cls) -> int:
        """
        Get number of registered strategies.

        Returns:
        --------
        int
            Count of registered strategies
        """
        return len(cls._strategies)
