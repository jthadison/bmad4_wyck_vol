"""
Validation Data Models - Multi-Purpose Validation Tracking

Purpose:
--------
Provides Pydantic models for:
1. RiskManager validation tracking (Story 7.8) - Legacy models
2. Multi-stage signal validation workflow (Story 8.2) - New validation chain

Data Models:
------------
Story 7.8 (Legacy - RiskManager):
- RiskValidationResult: Single validation step outcome
- RiskValidationPipeline: Complete pipeline execution history with all 8 steps

Story 8.2 (New - Signal Validation Chain):
- ValidationStatus: PASS/FAIL/WARN enum
- ValidationResult: Single validator stage outcome
- ValidationChain: Multi-stage validation workflow results
- ValidationContext: Context data passed to validators

Integration:
------------
- Story 7.8: RiskManager.validate_and_size()
- Story 8.2: Signal Generator multi-stage validation (Volume → Phase → Levels → Risk → Strategy)

Author: Story 7.8, Story 8.2
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_serializer, model_validator

# ============================================================================
# Story 7.8: RiskManager Validation Models (Legacy)
# ============================================================================


class RiskValidationResult(BaseModel):
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


class RiskValidationPipeline(BaseModel):
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

    results: list[RiskValidationResult] = Field(
        default_factory=list, description="All validation step results"
    )
    is_valid: bool = Field(default=True, description="Overall validation status")
    rejection_reason: str | None = Field(
        default=None, description="First rejection reason encountered"
    )
    total_execution_time_ms: float | None = Field(
        default=None, description="Total pipeline execution time"
    )

    def add_result(self, result: RiskValidationResult) -> None:
        """
        Add validation result and update overall status.

        If result is invalid (is_valid=False), pipeline becomes invalid
        and rejection_reason is set to first failure.

        Parameters:
        -----------
        result : RiskValidationResult
            Validation step result to add
        """
        self.results.append(result)
        if not result.is_valid:
            self.is_valid = False
            if self.rejection_reason is None:
                self.rejection_reason = f"{result.validation_step}: {result.rejection_reason}"

    def get_first_failure(self) -> RiskValidationResult | None:
        """
        Get first failed validation step.

        Returns:
        --------
        RiskValidationResult | None
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


# Backward compatibility aliases for Story 7.8 (in case any code still uses old names)
ValidationResult = RiskValidationResult
ValidationPipeline = RiskValidationPipeline

# PhaseValidation has been moved to src.models.phase_validation (Story 7.9)
# Re-export for backward compatibility
from src.models.phase_validation import PhaseValidation  # noqa: E402, F401

# ============================================================================
# Story 8.2: Multi-Stage Signal Validation Models (New)
# ============================================================================


class ValidationStatus(str, Enum):
    """
    Status of a single validation stage.

    Values:
    -------
    - PASS: Validation passed, continue to next stage
    - FAIL: Validation failed, reject signal immediately (early exit)
    - WARN: Warning issued, but continue processing
    """

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class StageValidationResult(BaseModel):
    """
    Result of a single validation stage in the multi-stage validation chain.

    Captures the outcome of one validation stage (Volume, Phase, Levels, Risk,
    or Strategy) with detailed reasoning, metadata, and timestamp.

    Fields:
    -------
    - stage: Validation stage name (e.g., "Volume", "Phase", "Levels")
    - status: PASS, FAIL, or WARN
    - reason: Detailed explanation for FAIL or WARN (required if not PASS)
    - timestamp: When validation executed (UTC)
    - validator_id: Identifier of validator function/module
    - metadata: Optional stage-specific metadata (e.g., volume ratios, risk metrics)

    Validation Rules:
    -----------------
    - reason is REQUIRED if status is FAIL or WARN
    - reason can be None if status is PASS
    - timestamp is UTC-aware datetime

    Example:
    --------
    >>> from decimal import Decimal
    >>> result = StageValidationResult(
    ...     stage="Volume",
    ...     status=ValidationStatus.FAIL,
    ...     reason="Spring volume 0.75x exceeds 0.60x threshold",
    ...     validator_id="VOLUME_VALIDATOR",
    ...     metadata={
    ...         "volume_ratio": "0.75",
    ...         "threshold": "0.60",
    ...         "pattern_type": "SPRING"
    ...     }
    ... )
    """

    stage: str = Field(..., description="Validation stage name (e.g., 'VOLUME', 'PHASE')")
    status: ValidationStatus = Field(..., description="PASS, FAIL, or WARN")
    reason: str | None = Field(default=None, description="Detailed explanation for FAIL/WARN")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Validation execution timestamp (UTC)",
    )
    validator_id: str = Field(..., description="Unique identifier of validator")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional stage-specific data"
    )

    @model_validator(mode="after")
    def reason_required_for_fail_warn(self) -> "StageValidationResult":
        """Ensure reason is present if status is FAIL or WARN."""
        if (
            self.status in [ValidationStatus.FAIL, ValidationStatus.WARN, "FAIL", "WARN"]
            and not self.reason
        ):
            status_str = self.status.value if hasattr(self.status, "value") else str(self.status)
            raise ValueError(f"Reason is required when status is {status_str}")
        return self

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), Decimal: str, UUID: str},
        use_enum_values=True,
    )


class ValidationChain(BaseModel):
    """
    Complete multi-stage validation chain execution results.

    Accumulates validation results from all 5 stages (Volume → Phase → Levels →
    Risk → Strategy) and tracks overall validation status with early exit support.

    Fields:
    -------
    - signal_id: Signal being validated (None if not created yet)
    - pattern_id: Pattern that triggered validation
    - validation_results: Ordered list of validations performed
    - overall_status: Final status (FAIL if any stage failed, WARN if any warned, else PASS)
    - rejection_stage: Stage where validation failed (if applicable)
    - rejection_reason: Consolidated rejection reason
    - warnings: All warning messages accumulated
    - started_at: Chain start timestamp (UTC)
    - completed_at: Chain completion timestamp (UTC)

    Computed Properties:
    -------------------
    - is_valid: Returns True if overall_status != FAIL
    - has_warnings: Returns True if warnings list not empty

    Methods:
    --------
    - add_result(result): Append validation result and update overall status

    Example:
    --------
    >>> chain = ValidationChain(pattern_id=UUID("..."))
    >>> chain.add_result(StageValidationResult(
    ...     stage="Volume",
    ...     status=ValidationStatus.PASS,
    ...     validator_id="VOLUME_VALIDATOR"
    ... ))
    >>> print(chain.overall_status)  # ValidationStatus.PASS
    >>> print(chain.is_valid)  # True
    """

    signal_id: UUID | None = Field(default=None, description="Signal being validated")
    pattern_id: UUID = Field(..., description="Pattern that triggered validation")
    validation_results: list[StageValidationResult] = Field(
        default_factory=list, description="Ordered list of validations performed"
    )
    overall_status: ValidationStatus = Field(
        default=ValidationStatus.PASS, description="Final validation status"
    )
    rejection_stage: str | None = Field(default=None, description="Stage where FAIL occurred")
    rejection_reason: str | None = Field(default=None, description="Consolidated rejection reason")
    warnings: list[str] = Field(default_factory=list, description="Accumulated warning messages")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Chain start timestamp (UTC)"
    )
    completed_at: datetime | None = Field(
        default=None, description="Chain completion timestamp (UTC)"
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_valid(self) -> bool:
        """Returns True if validation chain did not fail."""
        return self.overall_status != ValidationStatus.FAIL

    @computed_field  # type: ignore[misc]
    @property
    def has_warnings(self) -> bool:
        """Returns True if any warnings were issued."""
        return len(self.warnings) > 0

    def add_result(self, result: StageValidationResult) -> None:
        """
        Add validation result and update overall status.

        Updates overall_status based on result:
        - FAIL: Sets overall_status to FAIL, updates rejection_stage/reason
        - WARN: Sets overall_status to WARN (if not already FAIL)
        - PASS: No change to overall_status

        Parameters:
        -----------
        result : StageValidationResult
            Validation stage result to add
        """
        self.validation_results.append(result)

        if result.status == ValidationStatus.FAIL:
            self.overall_status = ValidationStatus.FAIL
            self.rejection_stage = result.stage
            self.rejection_reason = result.reason
        elif result.status == ValidationStatus.WARN:
            if self.overall_status != ValidationStatus.FAIL:
                self.overall_status = ValidationStatus.WARN
            if result.reason:
                self.warnings.append(f"{result.stage}: {result.reason}")

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), Decimal: str, UUID: str},
        use_enum_values=True,
    )


class ValidationContext(BaseModel):
    """
    Context object passed to all validators containing shared data.

    Provides all data needed for multi-stage validation workflow, with volume_analysis
    as a REQUIRED field (per Wyckoff Team Recommendation) since Volume is the first
    mandatory validator.

    Fields:
    -------
    - pattern: Pattern being validated (REQUIRED)
    - symbol: Trading symbol (REQUIRED)
    - timeframe: Timeframe of pattern (REQUIRED)
    - volume_analysis: Volume data for volume validation (REQUIRED)
    - phase_info: Phase detection data (optional - checked by PhaseValidator)
    - trading_range: Range levels for level validation (optional - checked by LevelValidator)
    - portfolio_context: Portfolio state for risk validation (optional - checked by RiskValidator)
    - market_context: Market data for strategy validation (optional - checked by StrategyValidator)
    - config: Configuration overrides (for testing)

    Note:
    -----
    volume_analysis is REQUIRED (not optional) since Volume is first mandatory validator.
    Other validators check for presence of their required context fields before using them.

    Example:
    --------
    >>> from backend.src.models.volume_analysis import VolumeAnalysis
    >>> context = ValidationContext(
    ...     pattern=spring_pattern,
    ...     symbol="AAPL",
    ...     timeframe="1d",
    ...     volume_analysis=VolumeAnalysis(...),
    ...     phase_info=phase_info,
    ...     trading_range=trading_range
    ... )
    """

    # REQUIRED fields
    pattern: Any = Field(..., description="Pattern being validated")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe of pattern")
    volume_analysis: Any = Field(
        ..., description="Volume data (REQUIRED - Wyckoff Team Recommendation)"
    )

    # Optional fields - validators check for presence before using
    phase_info: Any | None = Field(default=None, description="Phase detection data")
    trading_range: Any | None = Field(default=None, description="Range levels for level validation")
    portfolio_context: Any | None = Field(
        default=None, description="Portfolio state for risk validation"
    )
    market_context: Any | None = Field(
        default=None, description="Market data for strategy validation"
    )

    # Configuration
    config: dict[str, Any] = Field(
        default_factory=dict, description="Configuration overrides (for testing)"
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow complex types like Pattern, VolumeAnalysis, etc.
    )
