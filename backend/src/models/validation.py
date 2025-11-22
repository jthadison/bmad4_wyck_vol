"""
Validation Pipeline Data Models - RiskManager Validation Tracking

Purpose:
--------
Provides Pydantic models for tracking individual validation step results
and aggregating them into a complete validation pipeline execution history
for the RiskManager module (Story 7.8).

Data Models:
------------
1. ValidationResult: Single validation step outcome
2. ValidationPipeline: Complete pipeline execution history with all 8 steps

Integration:
------------
- Story 7.8: Core validation tracking for RiskManager.validate_and_size()
- Used by all validation steps (7.1-7.9) to report results

Author: Story 7.8
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class ValidationResult(BaseModel):
    """
    Result of a single validation step in the risk pipeline.

    Captures the outcome of one validation step (pattern risk, R-multiple,
    portfolio heat, etc.) with execution timing and warning messages.

    Fields:
    -------
    - is_valid: Whether validation passed (True) or failed (False)
    - validation_step: Name of validation step (e.g., "pattern_risk", "r_multiple")
    - rejection_reason: Detailed rejection reason if failed (None if passed)
    - warnings: List of warning messages (non-blocking issues)
    - execution_time_ms: Step execution time in milliseconds

    Example:
    --------
    >>> from decimal import Decimal
    >>> result = ValidationResult(
    ...     is_valid=True,
    ...     validation_step="r_multiple",
    ...     rejection_reason=None,
    ...     warnings=["R-multiple 3.5 below ideal 4.0 for SPRING"],
    ...     execution_time_ms=0.5
    ... )
    """

    is_valid: bool = Field(..., description="Whether validation passed")
    validation_step: str = Field(..., description="Name of validation step")
    rejection_reason: str | None = Field(default=None, description="Reason for rejection if failed")
    warnings: list[str] = Field(default_factory=list, description="Warning messages (non-blocking)")
    execution_time_ms: float | None = Field(
        default=None, description="Step execution time in milliseconds"
    )

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with proper types."""
        return {
            "is_valid": self.is_valid,
            "validation_step": self.validation_step,
            "rejection_reason": self.rejection_reason,
            "warnings": self.warnings,
            "execution_time_ms": self.execution_time_ms,
        }


class ValidationPipeline(BaseModel):
    """
    Complete validation pipeline execution history.

    Tracks all 8 validation steps in RiskManager.validate_and_size():
    1. Pattern risk validation
    2. Phase prerequisite validation
    3. R-multiple validation
    4. Structural stop calculation
    5. Position size calculation
    6. Portfolio heat validation
    7. Campaign risk validation
    8. Correlated risk validation

    Aggregates results, warnings, and provides overall validation status.

    Fields:
    -------
    - results: List of ValidationResult for each step
    - is_valid: Overall pipeline status (False if ANY step failed)
    - rejection_reason: First rejection reason encountered
    - total_execution_time_ms: Total pipeline execution time

    Example:
    --------
    >>> pipeline = ValidationPipeline()
    >>> pipeline.add_result(ValidationResult(
    ...     is_valid=True,
    ...     validation_step="pattern_risk",
    ...     execution_time_ms=0.2
    ... ))
    >>> pipeline.add_result(ValidationResult(
    ...     is_valid=False,
    ...     validation_step="portfolio_heat",
    ...     rejection_reason="Portfolio heat would exceed 10% limit",
    ...     execution_time_ms=1.2
    ... ))
    >>> print(pipeline.is_valid)  # False
    >>> print(pipeline.rejection_reason)  # "portfolio_heat: Portfolio heat would exceed 10% limit"
    """

    results: list[ValidationResult] = Field(
        default_factory=list, description="All validation step results"
    )
    is_valid: bool = Field(default=True, description="Overall validation status")
    rejection_reason: str | None = Field(
        default=None, description="First rejection reason encountered"
    )
    total_execution_time_ms: float | None = Field(
        default=None, description="Total pipeline execution time"
    )

    def add_result(self, result: ValidationResult) -> None:
        """
        Add validation result and update overall status.

        If result is invalid (is_valid=False), pipeline becomes invalid
        and rejection_reason is set to first failure.

        Parameters:
        -----------
        result : ValidationResult
            Validation step result to add
        """
        self.results.append(result)
        if not result.is_valid:
            self.is_valid = False
            if self.rejection_reason is None:
                self.rejection_reason = f"{result.validation_step}: {result.rejection_reason}"

    def get_first_failure(self) -> ValidationResult | None:
        """
        Get first failed validation step.

        Returns:
        --------
        ValidationResult | None
            First failed step, or None if all passed
        """
        for result in self.results:
            if not result.is_valid:
                return result
        return None

    @property
    def all_warnings(self) -> list[str]:
        """
        Aggregate all warnings from all steps.

        Returns:
        --------
        list[str]
            All warning messages from all validation steps
        """
        warnings = []
        for result in self.results:
            warnings.extend(result.warnings)
        return warnings

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with nested ValidationResults."""
        return {
            "results": [result.serialize_model() for result in self.results],
            "is_valid": self.is_valid,
            "rejection_reason": self.rejection_reason,
            "total_execution_time_ms": self.total_execution_time_ms,
        }


# PhaseValidation has been moved to src.models.phase_validation (Story 7.9)
# Re-export for backward compatibility
from src.models.phase_validation import PhaseValidation  # noqa: E402, F401
