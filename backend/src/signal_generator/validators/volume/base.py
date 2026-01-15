"""
Volume Validation Strategy Base Classes (Story 18.6.1)

Provides abstract base class for pattern-specific volume validation strategies.
This enables the Strategy pattern where each pattern type has its own validator
that can be registered and retrieved without modifying existing code.

Reference: CF-006 from Critical Foundation Refactoring document.

Author: Story 18.6.1
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)

logger = structlog.get_logger()


class VolumeValidationStrategy(ABC):
    """
    Abstract base class for pattern-specific volume validation strategies.

    Each pattern type (SPRING, SOS, UTAD, LPS) implements this interface
    to provide its own volume validation logic. Strategies are registered
    with VolumeStrategyRegistry and retrieved by pattern type.

    Properties (must be overridden):
    --------------------------------
    - pattern_type: Pattern type this strategy handles (e.g., "SPRING", "SOS")
    - volume_threshold_type: Whether pattern requires "max" or "min" volume
    - default_stock_threshold: Default threshold for stock validation
    - default_forex_threshold: Default threshold for forex validation

    Methods:
    --------
    - validate(context, config): Execute pattern-specific volume validation
    - get_threshold(context, config): Get appropriate threshold for asset class/session
    - create_result(status, reason, metadata): Helper factory for StageValidationResult

    Example Implementation:
    -----------------------
    >>> class SpringVolumeStrategy(VolumeValidationStrategy):
    ...     @property
    ...     def pattern_type(self) -> str:
    ...         return "SPRING"
    ...
    ...     @property
    ...     def volume_threshold_type(self) -> str:
    ...         return "max"  # Spring requires LOW volume
    ...
    ...     @property
    ...     def default_stock_threshold(self) -> Decimal:
    ...         return Decimal("0.7")
    ...
    ...     @property
    ...     def default_forex_threshold(self) -> Decimal:
    ...         return Decimal("0.85")
    ...
    ...     def validate(self, context, config) -> StageValidationResult:
    ...         # Spring-specific validation logic
    ...         ...
    """

    # Validator identification (shared across all strategies)
    VALIDATOR_ID = "VOLUME_VALIDATOR"
    STAGE_NAME = "Volume"

    @property
    @abstractmethod
    def pattern_type(self) -> str:
        """
        Pattern type this strategy validates.

        Returns:
        --------
        str
            Pattern type in uppercase (e.g., "SPRING", "SOS", "UTAD", "LPS")
        """
        pass

    @property
    @abstractmethod
    def volume_threshold_type(self) -> str:
        """
        Type of threshold comparison for this pattern.

        Returns:
        --------
        str
            "max" if pattern requires volume BELOW threshold (e.g., Spring)
            "min" if pattern requires volume ABOVE threshold (e.g., SOS)
        """
        pass

    @property
    @abstractmethod
    def default_stock_threshold(self) -> Decimal:
        """
        Default volume ratio threshold for stock validation.

        Returns:
        --------
        Decimal
            Default threshold value for stocks (actual volume)
        """
        pass

    @property
    @abstractmethod
    def default_forex_threshold(self) -> Decimal:
        """
        Default volume ratio threshold for forex validation.

        Returns:
        --------
        Decimal
            Default threshold value for forex (tick volume)
        """
        pass

    @abstractmethod
    def validate(
        self, context: ValidationContext, config: VolumeValidationConfig
    ) -> StageValidationResult:
        """
        Execute pattern-specific volume validation.

        This is the core validation method that must be implemented by all
        concrete strategy classes. It receives validation context and config,
        performs pattern-specific checks, and returns a result.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, asset_class, forex_session, etc.
        config : VolumeValidationConfig
            Configuration with thresholds for stock/forex validation

        Returns:
        --------
        StageValidationResult
            Result with PASS or FAIL status (never WARN per FR12)
        """
        pass

    def get_threshold(self, context: ValidationContext, config: VolumeValidationConfig) -> Decimal:
        """
        Get appropriate threshold based on asset class and session.

        Override this method for patterns with session-specific thresholds
        (e.g., Asian session adjustments). The default implementation uses
        strategy-defined thresholds; subclasses can leverage config for
        user-configurable overrides.

        Parameters:
        -----------
        context : ValidationContext
            Context with asset_class and forex_session
        config : VolumeValidationConfig
            Configuration with all threshold values (available for subclass overrides)

        Returns:
        --------
        Decimal
            Threshold value to use for validation

        Note:
        -----
        The config parameter is included in the signature for subclasses that
        need configurable thresholds. The base implementation uses strategy
        defaults for simplicity; concrete strategies (Story 18.6.2+) may
        leverage config values like config.spring_max_volume.
        """
        if context.asset_class == "FOREX":
            return self.default_forex_threshold
        return self.default_stock_threshold

    def create_result(
        self,
        status: ValidationStatus,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StageValidationResult:
        """
        Helper factory method for creating StageValidationResult.

        Automatically fills in stage name, validator_id, and timestamp.

        Parameters:
        -----------
        status : ValidationStatus
            PASS or FAIL (never WARN per FR12)
        reason : str | None
            Detailed explanation (REQUIRED for FAIL, optional for PASS)
        metadata : dict[str, Any] | None
            Optional validation-specific data (volume ratios, thresholds, etc.)

        Returns:
        --------
        StageValidationResult
            Fully populated validation result

        Example:
        --------
        >>> return self.create_result(
        ...     ValidationStatus.FAIL,
        ...     reason="Spring volume 0.75x exceeds 0.70x threshold",
        ...     metadata={"volume_ratio": 0.75, "threshold": 0.70}
        ... )
        """
        return StageValidationResult(
            stage=self.STAGE_NAME,
            status=status,
            reason=reason,
            timestamp=datetime.now(UTC),
            validator_id=self.VALIDATOR_ID,
            metadata=metadata,
        )

    def log_validation_start(self, context: ValidationContext) -> None:
        """
        Log validation start for this pattern type.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and symbol information
        """
        logger.debug(
            "volume_strategy_validation_started",
            pattern_type=self.pattern_type,
            pattern_id=str(context.pattern.id),
            symbol=context.symbol,
            asset_class=context.asset_class,
        )

    def log_validation_passed(
        self, context: ValidationContext, volume_ratio: Decimal, threshold: Decimal
    ) -> None:
        """
        Log successful validation for this pattern type.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and symbol information
        volume_ratio : Decimal
            Actual volume ratio that passed validation
        threshold : Decimal
            Threshold value that was compared against
        """
        logger.info(
            "volume_validation_passed",
            pattern_type=self.pattern_type,
            volume_ratio=float(volume_ratio),
            threshold=float(threshold),
            symbol=context.symbol,
            asset_class=context.asset_class,
        )

    def log_validation_failed(
        self,
        context: ValidationContext,
        volume_ratio: Decimal,
        threshold: Decimal,
        reason: str,
    ) -> None:
        """
        Log failed validation for this pattern type.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and symbol information
        volume_ratio : Decimal
            Actual volume ratio that failed validation
        threshold : Decimal
            Threshold value that was compared against
        reason : str
            Detailed reason for failure
        """
        logger.error(
            "volume_validation_failed",
            pattern_type=self.pattern_type,
            volume_ratio=float(volume_ratio),
            threshold=float(threshold),
            symbol=context.symbol,
            asset_class=context.asset_class,
            reason=reason,
        )
