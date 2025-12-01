"""
Base Validator Interface for Multi-Stage Validation Chain (Story 8.2)

Purpose:
--------
Provides abstract base class for all validation stages in the multi-stage
validation workflow (Volume → Phase → Levels → Risk → Strategy).

Abstract Base Class:
--------------------
- BaseValidator: Defines interface that all validators must implement

All validators must:
- Inherit from BaseValidator
- Implement async validate() method
- Define validator_id and stage_name properties
- Use create_result() helper for consistent ValidationResult creation

Integration:
------------
- Story 8.2: Foundation for validation chain orchestrator
- Stories 8.3-8.7: Concrete validator implementations

Author: Story 8.2
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from src.models.validation import StageValidationResult, ValidationContext, ValidationStatus


class BaseValidator(ABC):
    """
    Abstract base class for all validation stages.

    All concrete validators (VolumeValidator, PhaseValidator, etc.) must
    inherit from this class and implement the validate() method.

    Properties (must be overridden):
    --------------------------------
    - validator_id: Unique identifier for this validator (e.g., 'VOLUME_VALIDATOR')
    - stage_name: Human-readable stage name (e.g., 'Volume')

    Methods:
    --------
    - validate(context): Execute validation logic (MUST be implemented by subclass)
    - create_result(status, reason, metadata): Helper factory for StageValidationResult

    Example Concrete Validator:
    ---------------------------
    >>> class VolumeValidator(BaseValidator):
    ...     @property
    ...     def validator_id(self) -> str:
    ...         return "VOLUME_VALIDATOR"
    ...
    ...     @property
    ...     def stage_name(self) -> str:
    ...         return "Volume"
    ...
    ...     async def validate(self, context: ValidationContext) -> StageValidationResult:
    ...         # Validation logic here
    ...         if volume_too_high:
    ...             return self.create_result(
    ...                 ValidationStatus.FAIL,
    ...                 reason="Volume exceeds threshold",
    ...                 metadata={"volume_ratio": "0.75"}
    ...             )
    ...         return self.create_result(ValidationStatus.PASS)
    """

    @property
    @abstractmethod
    def validator_id(self) -> str:
        """
        Unique identifier for this validator.

        Returns:
        --------
        str
            Validator ID (e.g., 'VOLUME_VALIDATOR', 'PHASE_VALIDATOR')
        """
        pass

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """
        Human-readable stage name.

        Returns:
        --------
        str
            Stage name (e.g., 'Volume', 'Phase', 'Levels', 'Risk', 'Strategy')
        """
        pass

    @abstractmethod
    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute validation logic for this stage.

        This is the core validation method that must be implemented by all
        concrete validators. It receives a ValidationContext with all necessary
        data and returns a StageValidationResult with PASS, FAIL, or WARN status.

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern, volume_analysis, and optional phase_info,
            trading_range, portfolio_context, market_context

        Returns:
        --------
        StageValidationResult
            Result with status (PASS/FAIL/WARN), reason, and metadata

        Example Implementation:
        -----------------------
        >>> async def validate(self, context: ValidationContext) -> StageValidationResult:
        ...     # Check if required data is present
        ...     if context.phase_info is None:
        ...         return self.create_result(
        ...             ValidationStatus.FAIL,
        ...             reason="Phase information not available"
        ...         )
        ...
        ...     # Perform validation logic
        ...     if validation_passes:
        ...         return self.create_result(ValidationStatus.PASS)
        ...     else:
        ...         return self.create_result(
        ...             ValidationStatus.FAIL,
        ...             reason="Validation failed",
        ...             metadata={"details": "..."}
        ...         )
        """
        pass

    def create_result(
        self,
        status: ValidationStatus,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StageValidationResult:
        """
        Helper factory method for creating StageValidationResult.

        Automatically fills in stage name, validator_id, and timestamp
        from the validator instance.

        Parameters:
        -----------
        status : ValidationStatus
            PASS, FAIL, or WARN
        reason : str | None
            Detailed explanation (REQUIRED for FAIL/WARN, optional for PASS)
        metadata : dict[str, Any] | None
            Optional stage-specific data (e.g., volume ratios, risk metrics)

        Returns:
        --------
        StageValidationResult
            Fully populated validation result

        Example:
        --------
        >>> return self.create_result(
        ...     ValidationStatus.FAIL,
        ...     reason="Volume 0.75x exceeds 0.60x threshold",
        ...     metadata={"volume_ratio": "0.75", "threshold": "0.60"}
        ... )
        """
        return StageValidationResult(
            stage=self.stage_name,
            status=status,
            reason=reason,
            timestamp=datetime.now(UTC),
            validator_id=self.validator_id,
            metadata=metadata,
        )
