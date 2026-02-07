"""
Phase Validator - Multi-Stage Validation Chain (Story 8.4)

Purpose:
--------
Validates pattern-phase alignment per FR14 and FR15 functional requirements.
Enforces that patterns occur in appropriate Wyckoff phases with adequate confidence.

Second stage in the validation chain: Volume → Phase → Levels → Risk → Strategy.

Functional Requirements Enforced:
----------------------------------
FR3: Phase confidence must be ≥70%
FR14: Early phase rejection (no trading in Phase A or Phase B <10 bars)
FR15: Phase-pattern alignment rules:
    - Spring: Only Phase C allowed
    - SOS: Phase D primary, late Phase C if confidence ≥85%
    - LPS: Phase D or E only
    - UTAD: Distribution Phase C or D

Integration:
------------
- Story 8.2: BaseValidator, StageValidationResult, ValidationContext, ValidationStatus
- Story 4.4: PhaseClassification, WyckoffPhase
- Story 8.1: Master Orchestrator builds ValidationContext with phase_info

Author: Story 8.4 (full implementation)
"""

import structlog

from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.validation import StageValidationResult, ValidationContext, ValidationStatus
from src.signal_generator.validators.base import BaseValidator

logger = structlog.get_logger()


class PhaseValidator(BaseValidator):
    """
    Phase validation stage.

    Validates pattern-phase alignment per FR14 and FR15:
    - FR3: Phase confidence ≥70%
    - FR14: No trading in Phase A or early Phase B (<10 bars)
    - FR15: Phase-pattern alignment (Spring→C, SOS→D/late C, LPS→D/E, UTAD→Distribution C/D)

    Properties:
    -----------
    - validator_id: "PHASE_VALIDATOR"
    - stage_name: "Phase"

    Example Usage:
    --------------
    >>> validator = PhaseValidator()
    >>> result = await validator.validate(context)
    >>> if result.status == ValidationStatus.PASS:
    ...     print(f"Phase validation passed for {context.pattern.pattern_type}")
    """

    @property
    def validator_id(self) -> str:
        """Unique identifier for this validator."""
        return "PHASE_VALIDATOR"

    @property
    def stage_name(self) -> str:
        """Human-readable stage name."""
        return "Phase"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute phase validation logic.

        Validates:
        1. Phase info presence
        2. FR3: Phase confidence ≥70%
        3. FR14: Early phase rejection (no Phase A, no Phase B <10 bars)
        4. FR15: Phase-pattern alignment (Spring→C, SOS→D/late C, etc.)

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and phase_info

        Returns:
        --------
        StageValidationResult
            PASS if all validations pass, FAIL with detailed reason otherwise
        """
        # Step 1: Validate phase_info presence
        if context.phase_info is None:
            logger.error(
                "phase_info_missing",
                pattern_id=str(context.pattern.id) if hasattr(context.pattern, "id") else "unknown",
                pattern_type=context.pattern.pattern_type
                if hasattr(context.pattern, "pattern_type")
                else "unknown",
            )
            return self.create_result(
                ValidationStatus.FAIL, reason="Phase information not available for validation"
            )

        phase_classification: PhaseClassification = context.phase_info
        pattern_type: str = (
            context.pattern.pattern_type if hasattr(context.pattern, "pattern_type") else "UNKNOWN"
        )
        phase: WyckoffPhase = phase_classification.phase
        confidence: int = phase_classification.confidence

        logger.info(
            "phase_validation_started",
            pattern_id=str(context.pattern.id) if hasattr(context.pattern, "id") else "unknown",
            pattern_type=pattern_type,
            current_phase=phase.value if phase else "None",
            phase_confidence=confidence,
        )

        # Step 2: Validate FR3 phase confidence ≥70%
        is_valid, reason = self._validate_phase_confidence(phase_classification)
        if not is_valid:
            logger.warning(
                "phase_validation_failed",
                pattern_type=pattern_type,
                phase=phase.value if phase else "None",
                confidence=confidence,
                reason=reason,
                failed_requirement="FR3",
            )
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Step 3: Validate FR14 early phase rejection
        is_valid, reason = self._validate_fr14_early_phase(phase_classification)
        if not is_valid:
            logger.warning(
                "phase_validation_failed",
                pattern_type=pattern_type,
                phase=phase.value if phase else "None",
                reason=reason,
                failed_requirement="FR14",
            )
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Step 4: Validate FR15 phase-pattern alignment
        is_valid, reason = self._validate_fr15_phase_pattern_alignment(
            pattern_type, phase, confidence
        )
        if not is_valid:
            logger.warning(
                "phase_validation_failed",
                pattern_type=pattern_type,
                phase=phase.value if phase else "None",
                reason=reason,
                failed_requirement="FR15",
            )
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # All validations passed
        metadata = {
            "phase": phase.value if phase else "None",
            "phase_confidence": confidence,
            "pattern_type": pattern_type,
            "phase_duration": phase_classification.duration,
            "trading_allowed": phase_classification.trading_allowed,
            "fr14_check": "PASS",
            "fr15_check": "PASS",
            "fr3_confidence_check": "PASS",
        }

        logger.info(
            "phase_validation_passed",
            pattern_type=pattern_type,
            phase=phase.value if phase else "None",
            confidence=confidence,
            metadata=metadata,
        )

        return self.create_result(ValidationStatus.PASS, metadata=metadata)

    def _validate_phase_confidence(
        self, phase_classification: PhaseClassification
    ) -> tuple[bool, str | None]:
        """
        Validate FR3: Phase confidence must be ≥70%.

        Parameters:
        -----------
        phase_classification : PhaseClassification
            Phase classification data

        Returns:
        --------
        tuple[bool, str | None]
            (True, None) if confidence ≥70%, (False, reason) otherwise
        """
        confidence = phase_classification.confidence
        phase = phase_classification.phase

        logger.debug(
            "fr3_confidence_check",
            phase=phase.value if phase else "None",
            confidence=confidence,
            minimum_required=70,
            passes=(confidence >= 70),
        )

        if confidence < 70:
            return (
                False,
                f"Phase {phase.value if phase else 'None'} confidence {confidence}% below 70% minimum requirement (FR3)",
            )

        return (True, None)

    def _validate_fr14_early_phase(
        self, phase_classification: PhaseClassification
    ) -> tuple[bool, str | None]:
        """
        Validate FR14: Early phase rejection.

        Rules:
        - Phase A: Always reject (stopping action, no trading)
        - Phase B <10 bars: Reject (insufficient cause)
        - Phase B ≥10 bars: Allow (adequate cause)
        - Phase C/D/E: Allow (tradable phases)

        Parameters:
        -----------
        phase_classification : PhaseClassification
            Phase classification data

        Returns:
        --------
        tuple[bool, str | None]
            (True, None) if phase allows trading, (False, reason) otherwise
        """
        phase = phase_classification.phase
        duration = phase_classification.duration

        logger.debug(
            "fr14_early_phase_check",
            phase=phase.value if phase else "None",
            duration=duration,
            trading_allowed=phase_classification.trading_allowed,
        )

        # Phase A: Always reject
        if phase == WyckoffPhase.A:
            return (
                False,
                "Phase A (Stopping Action) - no patterns tradable until Phase B with adequate cause (FR14)",
            )

        # Phase B: Check duration
        if phase == WyckoffPhase.B:
            if duration < 10:
                return (
                    False,
                    f"Phase B duration {duration} bars < 10 bars minimum - insufficient cause built, wait for adequate accumulation (FR14)",
                )

        # Phase B ≥10 bars, or Phase C/D/E - trading allowed
        return (True, None)

    def _validate_fr15_phase_pattern_alignment(
        self, pattern_type: str, phase: WyckoffPhase, phase_confidence: int
    ) -> tuple[bool, str | None]:
        """
        Validate FR15: Phase-pattern alignment rules.

        Rules:
        - SPRING: Only Phase C allowed
        - SOS: Phase D primary, late Phase C if confidence ≥85%
        - LPS: Phase D or E only
        - UTAD: Distribution Phase C or D

        Parameters:
        -----------
        pattern_type : str
            Pattern type (SPRING, SOS, LPS, UTAD)
        phase : WyckoffPhase
            Current Wyckoff phase
        phase_confidence : int
            Phase confidence score 0-100

        Returns:
        --------
        tuple[bool, str | None]
            (True, None) if alignment valid, (False, reason) otherwise
        """
        # Spring Pattern Rules
        if pattern_type == "SPRING":
            if phase != WyckoffPhase.C:
                logger.debug(
                    "fr15_alignment_check",
                    pattern_type=pattern_type,
                    required_phase="C",
                    actual_phase=phase.value if phase else "None",
                    valid=False,
                )
                return (
                    False,
                    f"Spring pattern detected in Phase {phase.value if phase else 'None'} - Springs only valid in Phase C after adequate cause building (FR15)",
                )

        # SOS Pattern Rules
        elif pattern_type == "SOS":
            if phase == WyckoffPhase.D:
                # Ideal phase for SOS
                pass
            elif phase == WyckoffPhase.C and phase_confidence >= 85:
                # Late Phase C acceptable with high confidence
                pass
            elif phase == WyckoffPhase.C and phase_confidence < 85:
                logger.debug(
                    "fr15_alignment_check",
                    pattern_type=pattern_type,
                    required_phase="D or late C with 85+ confidence",
                    actual_phase=phase.value if phase else "None",
                    phase_confidence=phase_confidence,
                    valid=False,
                )
                return (
                    False,
                    f"SOS in late Phase C requires ≥85% confidence, currently {phase_confidence}% (FR15)",
                )
            else:
                logger.debug(
                    "fr15_alignment_check",
                    pattern_type=pattern_type,
                    required_phase="D or late C with 85+ confidence",
                    actual_phase=phase.value if phase else "None",
                    valid=False,
                )
                return (
                    False,
                    f"SOS pattern detected in Phase {phase.value if phase else 'None'} - SOS primarily valid in Phase D (or late Phase C with 85+ confidence) (FR15)",
                )

        # LPS Pattern Rules
        elif pattern_type == "LPS":
            if phase not in [WyckoffPhase.D, WyckoffPhase.E]:
                logger.debug(
                    "fr15_alignment_check",
                    pattern_type=pattern_type,
                    required_phase="D or E",
                    actual_phase=phase.value if phase else "None",
                    valid=False,
                )
                return (
                    False,
                    f"LPS pattern detected in Phase {phase.value if phase else 'None'} - LPS only valid in Phase D or Phase E markup (FR15)",
                )

        # UTAD Pattern Rules
        elif pattern_type == "UTAD":
            if phase not in [WyckoffPhase.C, WyckoffPhase.D]:
                logger.debug(
                    "fr15_alignment_check",
                    pattern_type=pattern_type,
                    required_phase="C or D (Distribution)",
                    actual_phase=phase.value if phase else "None",
                    valid=False,
                )
                return (
                    False,
                    f"UTAD pattern detected in Phase {phase.value if phase else 'None'} - UTAD only valid in Distribution Phase C or D (FR15)",
                )

        # Unknown pattern type - log warning but don't block
        else:
            logger.warning(
                "unknown_pattern_type",
                pattern_type=pattern_type,
                phase=phase.value if phase else "None",
            )

        logger.debug(
            "fr15_alignment_check",
            pattern_type=pattern_type,
            actual_phase=phase.value if phase else "None",
            valid=True,
        )

        return (True, None)
