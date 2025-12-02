"""
Level Validator - Trading Range Level Quality Validation (Story 8.5)

Purpose:
--------
Validates Creek/Ice/Jump level strength, positioning, and Wyckoff cause-effect
relationships. Third stage in validation chain (Volume → Phase → Levels → Risk → Strategy).

Functional Requirements:
------------------------
FR9: Creek/Ice strength_score ≥ 60 (reliable support/resistance)
FR1: Range size ≥ 3% (meaningful profit potential)
FR10: Cause factor based on range duration (2.0x/2.5x/3.0x)

Wyckoff Cause-Effect Validation:
--------------------------------
CRITICAL: Validates Jump targets honor Wyckoff's Second Law (Cause & Effect)
- Conservative targets (<80% expected): WARN - may leave profit on table
- Aggressive targets (>200% expected): FAIL - unrealistic per Wyckoff principles
- Acceptable range (80%-200%): PASS - natural cause-effect proportions

Validation Checks:
-----------------
1. Creek strength ≥ 60 (FR9)
2. Ice strength ≥ 60, Ice > Creek
3. Jump > Ice, correct cause_factor, Wyckoff Cause-Effect validation
4. Level ordering: Creek < Ice < Jump
5. Range size ≥ 3% (FR1)

Integration:
------------
- Story 8.2: BaseValidator framework
- Story 8.5: Full level validation implementation
- Epic 3: TradingRange, Creek/Ice/Jump level models

Author: Story 8.5
"""

from decimal import Decimal

import structlog

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.jump_level import JumpLevel
from src.models.trading_range import TradingRange
from src.models.validation import StageValidationResult, ValidationContext, ValidationStatus
from src.signal_generator.validators.base import BaseValidator

logger = structlog.get_logger()


class LevelValidator(BaseValidator):
    """
    Level validation stage - validates Creek/Ice/Jump level quality.

    Validates trading range levels meet minimum strength, positioning, and
    Wyckoff cause-effect requirements before signal creation.

    Properties:
    -----------
    - validator_id: "LEVEL_VALIDATOR"
    - stage_name: "Levels"

    Validation Rules:
    -----------------
    1. Creek strength ≥ 60 (FR9) - reliable support for stop placement
    2. Ice strength ≥ 60 (FR9), Ice > Creek - reliable resistance for entry
    3. Jump > Ice, correct cause_factor (FR10), Wyckoff Cause-Effect validation
    4. Level ordering: Creek < Ice < Jump (structural integrity)
    5. Range size ≥ 3% (FR1) - meaningful profit potential

    Wyckoff Cause-Effect Validation:
    --------------------------------
    Validates Jump projection aligns with accumulation "cause":
    - Expected move = range_width × cause_factor
    - Acceptable: actual move 80%-200% of expected
    - WARN: <80% (conservative, leaving profit on table)
    - FAIL: >200% (unrealistic, target too aggressive)

    Example Usage:
    --------------
    >>> validator = LevelValidator()
    >>> result = await validator.validate(context)
    >>> if result.status == ValidationStatus.PASS:
    ...     print(f"Creek: ${result.metadata['creek_price']}")
    ...     print(f"Ice: ${result.metadata['ice_price']}")
    ...     print(f"Jump: ${result.metadata['jump_price']}")
    """

    @property
    def validator_id(self) -> str:
        """Unique identifier for this validator."""
        return "LEVEL_VALIDATOR"

    @property
    def stage_name(self) -> str:
        """Human-readable stage name."""
        return "Levels"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute level validation logic.

        Validates all level quality requirements in order:
        1. Trading range presence
        2. Creek level validation (strength ≥ 60, positive price)
        3. Ice level validation (strength ≥ 60, Ice > Creek)
        4. Jump level validation (Jump > Ice, Cause-Effect, correct cause_factor)
        5. Level ordering (Creek < Ice < Jump)
        6. Range size (≥ 3%)

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and trading_range

        Returns:
        --------
        StageValidationResult
            PASS if all checks pass, FAIL if any check fails, WARN for conservative Jump
        """
        logger.info(
            "level_validation_started",
            pattern_id=str(context.pattern.id),
            pattern_type=context.pattern.pattern_type,
            symbol=context.symbol,
        )

        # Step 1: Validate trading_range presence
        if context.trading_range is None:
            logger.error(
                "trading_range_missing",
                pattern_id=str(context.pattern.id),
                pattern_type=context.pattern.pattern_type,
            )
            return self.create_result(
                ValidationStatus.FAIL,
                reason="Trading range information not available for level validation",
            )

        trading_range: TradingRange = context.trading_range

        # Ensure all levels exist
        if trading_range.creek is None:
            return self.create_result(
                ValidationStatus.FAIL, reason="Creek level not calculated for trading range"
            )
        if trading_range.ice is None:
            return self.create_result(
                ValidationStatus.FAIL, reason="Ice level not calculated for trading range"
            )
        if trading_range.jump is None:
            return self.create_result(
                ValidationStatus.FAIL, reason="Jump level not calculated for trading range"
            )

        creek = trading_range.creek
        ice = trading_range.ice
        jump = trading_range.jump

        # Step 2: Validate Creek level
        creek_valid, creek_reason = self._validate_creek_level(creek)
        if not creek_valid:
            logger.warning(
                "level_validation_failed",
                reason=creek_reason,
                failed_check="creek",
                creek_strength=creek.strength_score,
            )
            return self.create_result(ValidationStatus.FAIL, reason=creek_reason)

        # Step 3: Validate Ice level
        ice_valid, ice_reason = self._validate_ice_level(ice, creek)
        if not ice_valid:
            logger.warning(
                "level_validation_failed",
                reason=ice_reason,
                failed_check="ice",
                ice_strength=ice.strength_score,
                creek_price=float(creek.price),
                ice_price=float(ice.price),
            )
            return self.create_result(ValidationStatus.FAIL, reason=ice_reason)

        # Step 4: Validate Jump level (includes Wyckoff Cause-Effect validation)
        jump_valid, jump_reason, jump_status = self._validate_jump_level(
            jump, ice, creek, trading_range.duration
        )
        if jump_status == ValidationStatus.FAIL:
            logger.warning(
                "level_validation_failed",
                reason=jump_reason,
                failed_check="jump",
                jump_price=float(jump.price),
                ice_price=float(ice.price),
                cause_factor=float(jump.cause_factor),
                range_duration=trading_range.duration,
            )
            return self.create_result(ValidationStatus.FAIL, reason=jump_reason)

        # Step 5: Validate level ordering
        ordering_valid, ordering_reason = self._validate_level_ordering(creek, ice, jump)
        if not ordering_valid:
            logger.warning(
                "level_validation_failed",
                reason=ordering_reason,
                failed_check="ordering",
                creek_price=float(creek.price),
                ice_price=float(ice.price),
                jump_price=float(jump.price),
            )
            return self.create_result(ValidationStatus.FAIL, reason=ordering_reason)

        # Step 6: Validate range size
        size_valid, size_reason = self._validate_range_size(creek, ice)
        if not size_valid:
            logger.warning(
                "level_validation_failed",
                reason=size_reason,
                failed_check="range_size",
                creek_price=float(creek.price),
                ice_price=float(ice.price),
            )
            return self.create_result(ValidationStatus.FAIL, reason=size_reason)

        # Calculate range metrics for metadata
        range_width = ice.price - creek.price
        range_pct = (range_width / creek.price) * Decimal("100")

        # Build metadata
        metadata = {
            "creek_price": float(creek.price),
            "creek_strength": creek.strength_score,
            "ice_price": float(ice.price),
            "ice_strength": ice.strength_score,
            "jump_price": float(jump.price),
            "cause_factor": float(jump.cause_factor),
            "range_duration": trading_range.duration,
            "range_width": float(range_width),
            "range_pct": float(range_pct),
            "creek_check": "PASS",
            "ice_check": "PASS",
            "jump_check": "PASS" if jump_status == ValidationStatus.PASS else "WARN",
            "ordering_check": "PASS",
            "size_check": "PASS",
        }

        # If Jump validation returned WARN (conservative target), return WARN overall
        if jump_status == ValidationStatus.WARN:
            logger.info(
                "level_validation_warning",
                creek_strength=creek.strength_score,
                ice_strength=ice.strength_score,
                range_pct=float(range_pct),
                warning=jump_reason,
            )
            return self.create_result(ValidationStatus.WARN, reason=jump_reason, metadata=metadata)

        # All validations passed
        logger.info(
            "level_validation_passed",
            creek_strength=creek.strength_score,
            ice_strength=ice.strength_score,
            range_pct=float(range_pct),
        )
        return self.create_result(ValidationStatus.PASS, metadata=metadata)

    def _validate_creek_level(self, creek: CreekLevel) -> tuple[bool, str | None]:
        """
        Validate Creek level strength and price.

        Checks:
        - Creek strength_score ≥ 60 (FR9)
        - Creek price > 0

        Parameters:
        -----------
        creek : CreekLevel
            Creek level to validate

        Returns:
        --------
        tuple[bool, str | None]
            (is_valid, rejection_reason)
        """
        logger.debug(
            "creek_level_check",
            creek_price=float(creek.price),
            creek_strength=creek.strength_score,
            minimum_required=60,
            passes=creek.strength_score >= 60,
        )

        if creek.strength_score < 60:
            return (
                False,
                f"Creek level strength {creek.strength_score} below 60 minimum requirement (FR9) - "
                f"support level unreliable for pattern validation",
            )

        if creek.price <= 0:
            return (False, f"Creek price {creek.price} invalid - must be positive")

        return (True, None)

    def _validate_ice_level(self, ice: IceLevel, creek: CreekLevel) -> tuple[bool, str | None]:
        """
        Validate Ice level strength and positioning.

        Checks:
        - Ice strength_score ≥ 60 (FR9)
        - Ice price > Creek price (resistance above support)
        - Ice price > 0

        Parameters:
        -----------
        ice : IceLevel
            Ice level to validate
        creek : CreekLevel
            Creek level for comparison

        Returns:
        --------
        tuple[bool, str | None]
            (is_valid, rejection_reason)
        """
        logger.debug(
            "ice_level_check",
            ice_price=float(ice.price),
            ice_strength=ice.strength_score,
            creek_price=float(creek.price),
            ice_greater_than_creek=ice.price > creek.price,
        )

        if ice.strength_score < 60:
            return (
                False,
                f"Ice level strength {ice.strength_score} below 60 minimum requirement (FR9) - "
                f"resistance level unreliable for breakout validation",
            )

        if ice.price <= creek.price:
            return (
                False,
                f"Invalid range structure: Ice price ${float(ice.price):.2f} not greater than "
                f"Creek price ${float(creek.price):.2f} - resistance must be above support",
            )

        if ice.price <= 0:
            return (False, f"Ice price {ice.price} invalid - must be positive")

        return (True, None)

    def _validate_jump_level(
        self, jump: JumpLevel, ice: IceLevel, creek: CreekLevel, range_duration: int
    ) -> tuple[bool, str | None, ValidationStatus]:
        """
        Validate Jump level target and Wyckoff cause-effect relationship.

        CRITICAL: Wyckoff Cause-Effect Validation
        -----------------------------------------
        Validates Jump projection honors Wyckoff's Second Law:
        - Expected move = range_width × cause_factor
        - Acceptable: actual move 80%-200% of expected
        - <80%: WARN - conservative, may leave profit on table
        - >200%: FAIL - unrealistic target per Wyckoff principles

        Checks:
        - Jump price > Ice price (target above resistance)
        - Range duration ≥ 15 bars (sufficient cause, FR10)
        - Cause factor correct for duration (FR10)
        - Wyckoff Cause-Effect validation (actual vs expected move)
        - Jump price > 0

        Parameters:
        -----------
        jump : JumpLevel
            Jump level to validate
        ice : IceLevel
            Ice level for comparison
        creek : CreekLevel
            Creek level for range width calculation
        range_duration : int
            Range duration in bars

        Returns:
        --------
        tuple[bool, str | None, ValidationStatus]
            (is_valid, reason, status) - status can be PASS, WARN, or FAIL
        """
        # Validate Jump > Ice
        if jump.price <= ice.price:
            return (
                False,
                f"Jump target ${float(jump.price):.2f} not greater than Ice level "
                f"${float(ice.price):.2f} - invalid profit target placement",
                ValidationStatus.FAIL,
            )

        # Validate positive price
        if jump.price <= 0:
            return (
                False,
                f"Jump price {jump.price} invalid - must be positive",
                ValidationStatus.FAIL,
            )

        # Validate minimum duration
        if range_duration < 15:
            return (
                False,
                f"Range duration {range_duration} bars < 15 minimum - insufficient cause for "
                f"Jump calculation (FR10)",
                ValidationStatus.FAIL,
            )

        # Determine expected cause_factor based on duration (FR10)
        if range_duration >= 40:
            expected_cause_factor = Decimal("3.0")
        elif range_duration >= 25:
            expected_cause_factor = Decimal("2.5")
        else:  # 15-24 bars
            expected_cause_factor = Decimal("2.0")

        # Verify cause_factor matches expected (allow ±0.1 tolerance for floating point)
        if abs(jump.cause_factor - expected_cause_factor) > Decimal("0.1"):
            return (
                False,
                f"Jump cause_factor {float(jump.cause_factor)} incorrect for duration "
                f"{range_duration} bars (expected {float(expected_cause_factor)}, FR10)",
                ValidationStatus.FAIL,
            )

        # WYCKOFF CAUSE-EFFECT VALIDATION (CRITICAL - DO NOT SKIP)
        range_width = ice.price - creek.price
        expected_jump_move = range_width * jump.cause_factor
        actual_jump_move = jump.price - ice.price

        # Log Wyckoff validation
        logger.debug(
            "jump_level_check",
            jump_price=float(jump.price),
            ice_price=float(ice.price),
            cause_factor=float(jump.cause_factor),
            range_duration=range_duration,
            expected_cause_factor=float(expected_cause_factor),
            range_width=float(range_width),
            expected_move=float(expected_jump_move),
            actual_move=float(actual_jump_move),
            move_ratio=float(actual_jump_move / expected_jump_move)
            if expected_jump_move > 0
            else 0,
        )

        # Conservative target: actual move < 80% of expected
        if actual_jump_move < (expected_jump_move * Decimal("0.8")):
            expected_target = ice.price + expected_jump_move
            return (
                True,
                f"Jump projection ${float(jump.price):.2f} conservative for cause built "
                f"(range: {range_duration} bars, ${float(range_width):.2f} range width). "
                f"Wyckoff cause-effect relationship suggests higher target of "
                f"${float(expected_target):.2f} - may be leaving profit on table.",
                ValidationStatus.WARN,
            )

        # Aggressive target: actual move > 200% of expected
        if actual_jump_move > (expected_jump_move * Decimal("2.0")):
            max_realistic_target = ice.price + (expected_jump_move * Decimal("2.0"))
            move_percentage = (actual_jump_move / expected_jump_move) * Decimal("100")
            return (
                False,
                f"Jump projection ${float(jump.price):.2f} too aggressive for cause built "
                f"(range: {range_duration} bars, expected move: ${float(expected_jump_move):.2f}). "
                f"Target ${float(actual_jump_move):.2f} is {float(move_percentage):.0f}% of "
                f"expected - unrealistic per Wyckoff principles. Adjust to "
                f"${float(max_realistic_target):.2f} maximum.",
                ValidationStatus.FAIL,
            )

        # Jump within acceptable range (80%-200% of expected) - PASS
        return (True, None, ValidationStatus.PASS)

    def _validate_level_ordering(
        self, creek: CreekLevel, ice: IceLevel, jump: JumpLevel
    ) -> tuple[bool, str | None]:
        """
        Validate complete level ordering: Creek < Ice < Jump.

        Parameters:
        -----------
        creek : CreekLevel
            Creek level
        ice : IceLevel
            Ice level
        jump : JumpLevel
            Jump level

        Returns:
        --------
        tuple[bool, str | None]
            (is_valid, rejection_reason)
        """
        ordering_valid = creek.price < ice.price < jump.price

        logger.debug(
            "level_ordering_check",
            creek=float(creek.price),
            ice=float(ice.price),
            jump=float(jump.price),
            ordering_valid=ordering_valid,
        )

        if not ordering_valid:
            return (
                False,
                f"Level ordering violated: Creek ${float(creek.price):.2f} < Ice "
                f"${float(ice.price):.2f} < Jump ${float(jump.price):.2f} - "
                f"structural integrity compromised",
            )

        return (True, None)

    def _validate_range_size(self, creek: CreekLevel, ice: IceLevel) -> tuple[bool, str | None]:
        """
        Validate range size meets 3% minimum (FR1).

        Parameters:
        -----------
        creek : CreekLevel
            Creek level
        ice : IceLevel
            Ice level

        Returns:
        --------
        tuple[bool, str | None]
            (is_valid, rejection_reason)
        """
        range_width = ice.price - creek.price
        range_pct = (range_width / creek.price) * Decimal("100")

        logger.debug(
            "range_size_check",
            range_width=float(range_width),
            range_pct=float(range_pct),
            minimum_pct=3.0,
            passes=range_pct >= Decimal("3.0"),
        )

        if range_pct < Decimal("3.0"):
            return (
                False,
                f"Range size {float(range_pct):.2f}% below 3.0% minimum requirement (FR1) - "
                f"range too narrow for reliable pattern detection",
            )

        return (True, None)
