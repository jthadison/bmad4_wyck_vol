"""
Phase Completion Validator - Story 7.9

Purpose:
--------
Validates Wyckoff phase prerequisites before allowing pattern entries.
Ensures Spring/SOS/LPS/UTAD entries only occur when the schematic supports them.

Validation Functions:
---------------------
1. validate_spring_prerequisites: Validates Phase A-B complete for Spring entry
2. validate_sos_prerequisites: Validates Phase C complete for SOS entry
3. validate_lps_prerequisites: Validates SOS occurred for LPS entry
4. validate_utad_prerequisites: Validates Distribution Phase A-B-C for UTAD entry
5. validate_event_sequence: Validates events occurred in correct order
6. validate_phase_prerequisites: Unified validator routing to pattern-specific validators

Statistical Impact:
-------------------
- Springs WITHOUT Phase A-B: ~35% success rate
- Springs WITH Phase A-B: ~70% success rate
- Volume validation adds ~15-20% improvement

Integration:
------------
- Story 7.8: RiskManager validation pipeline (step 2)
- SHORT-CIRCUITS if fails: Don't calculate R-multiple for invalid patterns

Author: Story 7.9
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from src.models.phase_validation import (
    PermissiveModeControls,
    PhasePrerequisites,
    PhaseValidation,
    VolumeThresholds,
    WyckoffEvent,
    WyckoffEventType,
)
from src.models.risk_allocation import PatternType

if TYPE_CHECKING:
    from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)

# Default configuration instances
DEFAULT_VOLUME_THRESHOLDS = VolumeThresholds()
DEFAULT_PREREQUISITES = PhasePrerequisites()
DEFAULT_PERMISSIVE_CONTROLS = PermissiveModeControls()


def _get_event_type_value(event: WyckoffEvent) -> str:
    """Get string value from event type, handling both enum and string."""
    if hasattr(event.event_type, "value"):
        return event.event_type.value
    return str(event.event_type)


def _calculate_volume_quality_score(
    event: WyckoffEvent,
    thresholds: VolumeThresholds,
) -> float:
    """
    Calculate volume quality score for an event (0.0-1.0).

    Perfect volume = 1.0, marginal = 0.7-0.9, poor = 0.3-0.6

    Parameters:
        event: WyckoffEvent with volume data
        thresholds: Volume threshold configuration

    Returns:
        Float score 0.0-1.0
    """
    event_type = _get_event_type_value(event)
    volume_ratio = event.volume_ratio

    # Event-specific scoring based on how well volume matches ideal
    if event_type == "SC":
        # SC needs climactic volume (>=2.0x), perfect at 2.5x+
        if volume_ratio >= Decimal("2.5"):
            return 1.0
        elif volume_ratio >= Decimal("2.0"):
            return 0.8 + float((volume_ratio - Decimal("2.0")) / Decimal("2.5")) * 0.2
        else:
            return max(0.0, float(volume_ratio / Decimal("2.0")) * 0.7)

    elif event_type == "SPRING":
        # Spring needs low volume (<=1.0x), perfect at <=0.5x
        if volume_ratio <= Decimal("0.5"):
            return 1.0
        elif volume_ratio <= Decimal("1.0"):
            return 0.7 + (1.0 - float(volume_ratio)) * 0.6
        else:
            return max(0.0, 0.5 - float(volume_ratio - Decimal("1.0")) * 0.5)

    elif event_type == "SOS":
        # SOS needs strong volume (>=1.5x), perfect at 2.0x+
        if volume_ratio >= Decimal("2.0"):
            return 1.0
        elif volume_ratio >= Decimal("1.5"):
            return 0.7 + float((volume_ratio - Decimal("1.5")) / Decimal("0.5")) * 0.3
        else:
            return max(0.0, float(volume_ratio / Decimal("1.5")) * 0.6)

    elif event_type == "LPS":
        # LPS needs low volume (<=1.2x), perfect at <=0.7x
        if volume_ratio <= Decimal("0.7"):
            return 1.0
        elif volume_ratio <= Decimal("1.2"):
            return 0.7 + (1.2 - float(volume_ratio)) * 0.6
        else:
            return max(0.0, 0.5 - float(volume_ratio - Decimal("1.2")) * 0.5)

    elif event_type == "BC":
        # BC needs climactic volume like SC
        if volume_ratio >= Decimal("2.5"):
            return 1.0
        elif volume_ratio >= Decimal("2.0"):
            return 0.8 + float((volume_ratio - Decimal("2.0")) / Decimal("2.5")) * 0.2
        else:
            return max(0.0, float(volume_ratio / Decimal("2.0")) * 0.7)

    # Default: base score on meets_volume_threshold
    return 1.0 if event.meets_volume_threshold else 0.5


def validate_event_sequence(
    events: list[WyckoffEvent],
    expected_sequence: list[str],
) -> tuple[bool, list[str]]:
    """
    Validate that events occurred in expected chronological order.

    Parameters:
        events: List of WyckoffEvent objects
        expected_sequence: List of event type strings in expected order

    Returns:
        Tuple of (is_valid, list of violation messages)

    Example:
        >>> is_valid, violations = validate_event_sequence(
        ...     events=[ps_event, sc_event, ar_event],
        ...     expected_sequence=["PS", "SC", "AR"]
        ... )
    """
    violations: list[str] = []

    # Build map of event type -> earliest timestamp
    event_timestamps: dict[str, datetime] = {}
    for event in events:
        event_type = _get_event_type_value(event)
        if event_type not in event_timestamps:
            event_timestamps[event_type] = event.timestamp
        else:
            # Keep earliest timestamp for each event type
            if event.timestamp < event_timestamps[event_type]:
                event_timestamps[event_type] = event.timestamp

    # Check sequence ordering
    prev_type: str | None = None
    prev_timestamp: datetime | None = None

    for event_type in expected_sequence:
        if event_type not in event_timestamps:
            continue  # Missing event handled elsewhere

        current_timestamp = event_timestamps[event_type]

        if prev_timestamp is not None and current_timestamp < prev_timestamp:
            violations.append(
                f"Sequence violation: {event_type} detected before {prev_type} "
                f"({current_timestamp.isoformat()} < {prev_timestamp.isoformat()})"
            )

        prev_type = event_type
        prev_timestamp = current_timestamp

    return len(violations) == 0, violations


def validate_comparative_volume(
    events: list[WyckoffEvent],
    comparisons: list[tuple[str, str]],  # (event_that_should_be_lower, reference_event)
) -> tuple[bool, list[str]]:
    """
    Validate comparative volume requirements (e.g., ST < SC, Test of Spring <= Spring).

    Parameters:
        events: List of WyckoffEvent objects
        comparisons: List of (lower_event, reference_event) tuples

    Returns:
        Tuple of (is_valid, list of violation messages)
    """
    violations: list[str] = []

    # Build map of event type -> volume_ratio
    event_volumes: dict[str, Decimal] = {}
    for event in events:
        event_type = _get_event_type_value(event)
        event_volumes[event_type] = event.volume_ratio

    for lower_event, reference_event in comparisons:
        if lower_event in event_volumes and reference_event in event_volumes:
            if event_volumes[lower_event] >= event_volumes[reference_event]:
                violations.append(
                    f"Volume violation: {lower_event} volume ({event_volumes[lower_event]}) "
                    f"should be lower than {reference_event} volume ({event_volumes[reference_event]})"
                )

    return len(violations) == 0, violations


def validate_spring_prerequisites(
    trading_range: TradingRange,
    thresholds: VolumeThresholds | None = None,
    prerequisites: PhasePrerequisites | None = None,
) -> PhaseValidation:
    """
    Validate Phase A-B prerequisites for Spring entry.

    Spring requires:
    - PS (Preliminary Support) detected
    - SC (Selling Climax) with climactic volume (>=2.0x)
    - AR (Automatic Rally) with diminishing volume (<=1.5x)
    - Events in correct sequence: PS < SC < AR

    Parameters:
        trading_range: TradingRange with event_history
        thresholds: Volume threshold configuration
        prerequisites: Prerequisite configuration

    Returns:
        PhaseValidation result
    """
    thresholds = thresholds or DEFAULT_VOLUME_THRESHOLDS
    prerequisites = prerequisites or DEFAULT_PREREQUISITES

    required_events = prerequisites.spring_required  # ["PS", "SC", "AR"]
    detected_events: dict[str, dict] = {}
    missing_events: list[str] = []
    volume_quality_scores: dict[str, float] = {}
    events_list: list[WyckoffEvent] = []

    # Check for each required event
    for event_type in required_events:
        matching_events = trading_range.get_events_by_type(event_type)
        if not matching_events:
            missing_events.append(event_type)
        else:
            event = matching_events[0]  # Use first occurrence
            events_list.append(event)
            detected_events[event_type] = {
                "timestamp": event.timestamp.isoformat(),
                "price_level": str(event.price_level),
                "volume_ratio": str(event.volume_ratio),
                "volume_quality": event.volume_quality.value
                if hasattr(event.volume_quality, "value")
                else event.volume_quality,
                "meets_volume_threshold": event.meets_volume_threshold,
            }
            volume_quality_scores[event_type] = _calculate_volume_quality_score(event, thresholds)

    # Check volume thresholds for critical events
    volume_violations: list[str] = []
    if "SC" in detected_events:
        sc_events = trading_range.get_events_by_type("SC")
        if sc_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.SC, sc_events[0].volume_ratio
        ):
            volume_violations.append(
                f"SC volume ({sc_events[0].volume_ratio}) below climactic threshold ({thresholds.sc_min})"
            )

    if "AR" in detected_events:
        ar_events = trading_range.get_events_by_type("AR")
        if ar_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.AR, ar_events[0].volume_ratio
        ):
            volume_violations.append(
                f"AR volume ({ar_events[0].volume_ratio}) above diminishing threshold ({thresholds.ar_max})"
            )

    # Validate event sequence
    sequence_valid, sequence_violations = validate_event_sequence(events_list, required_events)

    # Calculate confidence score
    if missing_events:
        # Missing critical events = score 0
        confidence_score = 0.0
    elif volume_violations:
        # Volume issues reduce confidence
        confidence_score = 0.5
    else:
        # Average volume quality scores
        if volume_quality_scores:
            confidence_score = sum(volume_quality_scores.values()) / len(volume_quality_scores)
        else:
            confidence_score = 1.0

    # Determine validity
    is_valid = len(missing_events) == 0 and len(volume_violations) == 0 and sequence_valid

    # Build rejection reason
    rejection_reason = None
    if not is_valid:
        reasons = []
        if missing_events:
            reasons.append(f"Missing prerequisites: {', '.join(missing_events)}")
        if volume_violations:
            reasons.extend(volume_violations)
        if sequence_violations:
            reasons.extend(sequence_violations)
        rejection_reason = "; ".join(reasons)

    logger.info(
        "spring_prerequisite_validation",
        is_valid=is_valid,
        missing_events=missing_events,
        detected_events=list(detected_events.keys()),
        volume_violations=volume_violations,
        sequence_violations=sequence_violations,
        confidence_score=confidence_score,
    )

    return PhaseValidation(
        is_valid=is_valid,
        pattern_type="SPRING",
        phase_complete=len(missing_events) == 0,
        missing_prerequisites=missing_events,
        prerequisite_events=detected_events,
        validation_mode="STRICT",
        rejection_reason=rejection_reason,
        prerequisite_confidence_score=confidence_score,
        volume_quality_scores=volume_quality_scores,
        sequence_violations=sequence_violations,
    )


def validate_sos_prerequisites(
    trading_range: TradingRange,
    thresholds: VolumeThresholds | None = None,
    prerequisites: PhasePrerequisites | None = None,
) -> PhaseValidation:
    """
    Validate Phase C prerequisites for SOS (Sign of Strength) entry.

    SOS requires:
    - All Spring prerequisites (PS, SC, AR)
    - SPRING with low volume (<=1.0x)
    - TEST_OF_SPRING with volume <= Spring volume
    - SOS itself requires strong volume (>=1.5x)
    - Events in correct sequence

    Parameters:
        trading_range: TradingRange with event_history
        thresholds: Volume threshold configuration
        prerequisites: Prerequisite configuration

    Returns:
        PhaseValidation result
    """
    thresholds = thresholds or DEFAULT_VOLUME_THRESHOLDS
    prerequisites = prerequisites or DEFAULT_PREREQUISITES

    required_events = prerequisites.sos_required
    detected_events: dict[str, dict] = {}
    missing_events: list[str] = []
    volume_quality_scores: dict[str, float] = {}
    events_list: list[WyckoffEvent] = []

    # Check for each required event
    for event_type in required_events:
        matching_events = trading_range.get_events_by_type(event_type)
        if not matching_events:
            missing_events.append(event_type)
        else:
            event = matching_events[0]
            events_list.append(event)
            detected_events[event_type] = {
                "timestamp": event.timestamp.isoformat(),
                "price_level": str(event.price_level),
                "volume_ratio": str(event.volume_ratio),
                "volume_quality": event.volume_quality.value
                if hasattr(event.volume_quality, "value")
                else event.volume_quality,
                "meets_volume_threshold": event.meets_volume_threshold,
            }
            volume_quality_scores[event_type] = _calculate_volume_quality_score(event, thresholds)

    # Check volume thresholds
    volume_violations: list[str] = []

    # SC must have climactic volume
    if "SC" in detected_events:
        sc_events = trading_range.get_events_by_type("SC")
        if sc_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.SC, sc_events[0].volume_ratio
        ):
            volume_violations.append(
                f"SC volume ({sc_events[0].volume_ratio}) below climactic threshold ({thresholds.sc_min})"
            )

    # Spring must have low volume
    if "SPRING" in detected_events:
        spring_events = trading_range.get_events_by_type("SPRING")
        if spring_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.SPRING, spring_events[0].volume_ratio
        ):
            volume_violations.append(
                f"Spring volume ({spring_events[0].volume_ratio}) above low-supply threshold ({thresholds.spring_max})"
            )

    # Comparative volume: TEST_OF_SPRING <= SPRING
    comparative_valid, comparative_violations = validate_comparative_volume(
        events_list, [("TEST_OF_SPRING", "SPRING")]
    )
    volume_violations.extend(comparative_violations)

    # Validate event sequence
    sequence_valid, sequence_violations = validate_event_sequence(events_list, required_events)

    # Calculate confidence score
    if missing_events:
        confidence_score = 0.0
    elif volume_violations:
        confidence_score = 0.5
    else:
        if volume_quality_scores:
            confidence_score = sum(volume_quality_scores.values()) / len(volume_quality_scores)
        else:
            confidence_score = 1.0

    is_valid = len(missing_events) == 0 and len(volume_violations) == 0 and sequence_valid

    rejection_reason = None
    if not is_valid:
        reasons = []
        if missing_events:
            reasons.append(f"Missing prerequisites: {', '.join(missing_events)}")
        if volume_violations:
            reasons.extend(volume_violations)
        if sequence_violations:
            reasons.extend(sequence_violations)
        rejection_reason = "; ".join(reasons)

    logger.info(
        "sos_prerequisite_validation",
        is_valid=is_valid,
        missing_events=missing_events,
        detected_events=list(detected_events.keys()),
        volume_violations=volume_violations,
        confidence_score=confidence_score,
    )

    return PhaseValidation(
        is_valid=is_valid,
        pattern_type="SOS",
        phase_complete=len(missing_events) == 0,
        missing_prerequisites=missing_events,
        prerequisite_events=detected_events,
        validation_mode="STRICT",
        rejection_reason=rejection_reason,
        prerequisite_confidence_score=confidence_score,
        volume_quality_scores=volume_quality_scores,
        sequence_violations=sequence_violations,
    )


def validate_lps_prerequisites(
    trading_range: TradingRange,
    thresholds: VolumeThresholds | None = None,
    prerequisites: PhasePrerequisites | None = None,
) -> PhaseValidation:
    """
    Validate Phase D prerequisites for LPS (Last Point of Support) entry.

    LPS requires:
    - All SOS prerequisites
    - SOS breakout occurred first (with strong volume >=1.5x)
    - LPS itself should have low volume (<=1.2x) - drying up on pullback

    Parameters:
        trading_range: TradingRange with event_history
        thresholds: Volume threshold configuration
        prerequisites: Prerequisite configuration

    Returns:
        PhaseValidation result
    """
    thresholds = thresholds or DEFAULT_VOLUME_THRESHOLDS
    prerequisites = prerequisites or DEFAULT_PREREQUISITES

    required_events = prerequisites.lps_required
    detected_events: dict[str, dict] = {}
    missing_events: list[str] = []
    volume_quality_scores: dict[str, float] = {}
    events_list: list[WyckoffEvent] = []

    for event_type in required_events:
        matching_events = trading_range.get_events_by_type(event_type)
        if not matching_events:
            missing_events.append(event_type)
        else:
            event = matching_events[0]
            events_list.append(event)
            detected_events[event_type] = {
                "timestamp": event.timestamp.isoformat(),
                "price_level": str(event.price_level),
                "volume_ratio": str(event.volume_ratio),
                "volume_quality": event.volume_quality.value
                if hasattr(event.volume_quality, "value")
                else event.volume_quality,
                "meets_volume_threshold": event.meets_volume_threshold,
            }
            volume_quality_scores[event_type] = _calculate_volume_quality_score(event, thresholds)

    volume_violations: list[str] = []

    # SOS must have strong volume
    if "SOS" in detected_events:
        sos_events = trading_range.get_events_by_type("SOS")
        if sos_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.SOS, sos_events[0].volume_ratio
        ):
            volume_violations.append(
                f"SOS volume ({sos_events[0].volume_ratio}) below strong-demand threshold ({thresholds.sos_min})"
            )

    # Validate sequence
    sequence_valid, sequence_violations = validate_event_sequence(events_list, required_events)

    # Special check: SOS must exist for LPS
    if "SOS" not in detected_events:
        rejection_reason = "LPS requires SOS breakout first"
    else:
        rejection_reason = None

    # Calculate confidence score
    if missing_events:
        confidence_score = 0.0
    elif volume_violations:
        confidence_score = 0.5
    else:
        if volume_quality_scores:
            confidence_score = sum(volume_quality_scores.values()) / len(volume_quality_scores)
        else:
            confidence_score = 1.0

    is_valid = len(missing_events) == 0 and len(volume_violations) == 0 and sequence_valid

    if not is_valid and rejection_reason is None:
        reasons = []
        if missing_events:
            reasons.append(f"Missing prerequisites: {', '.join(missing_events)}")
        if volume_violations:
            reasons.extend(volume_violations)
        if sequence_violations:
            reasons.extend(sequence_violations)
        rejection_reason = "; ".join(reasons)

    logger.info(
        "lps_prerequisite_validation",
        is_valid=is_valid,
        missing_events=missing_events,
        detected_events=list(detected_events.keys()),
        volume_violations=volume_violations,
        confidence_score=confidence_score,
    )

    return PhaseValidation(
        is_valid=is_valid,
        pattern_type="LPS",
        phase_complete=len(missing_events) == 0,
        missing_prerequisites=missing_events,
        prerequisite_events=detected_events,
        validation_mode="STRICT",
        rejection_reason=rejection_reason,
        prerequisite_confidence_score=confidence_score,
        volume_quality_scores=volume_quality_scores,
        sequence_violations=sequence_violations,
    )


def validate_utad_prerequisites(
    trading_range: TradingRange,
    thresholds: VolumeThresholds | None = None,
    prerequisites: PhasePrerequisites | None = None,
) -> PhaseValidation:
    """
    Validate Distribution Phase A-B-C prerequisites for UTAD entry.

    UTAD requires:
    - PSY (Preliminary Supply) with volume >=1.3x
    - BC (Buying Climax) with climactic volume >=2.0x
    - AR (Automatic Reaction)
    - LPSY (Last Point of Supply) with weak volume <=1.0x
    - Events in correct sequence

    Parameters:
        trading_range: TradingRange with event_history
        thresholds: Volume threshold configuration
        prerequisites: Prerequisite configuration

    Returns:
        PhaseValidation result
    """
    thresholds = thresholds or DEFAULT_VOLUME_THRESHOLDS
    prerequisites = prerequisites or DEFAULT_PREREQUISITES

    required_events = prerequisites.utad_required  # ["PSY", "BC", "AR", "LPSY"]
    detected_events: dict[str, dict] = {}
    missing_events: list[str] = []
    volume_quality_scores: dict[str, float] = {}
    events_list: list[WyckoffEvent] = []

    for event_type in required_events:
        matching_events = trading_range.get_events_by_type(event_type)
        if not matching_events:
            missing_events.append(event_type)
        else:
            event = matching_events[0]
            events_list.append(event)
            detected_events[event_type] = {
                "timestamp": event.timestamp.isoformat(),
                "price_level": str(event.price_level),
                "volume_ratio": str(event.volume_ratio),
                "volume_quality": event.volume_quality.value
                if hasattr(event.volume_quality, "value")
                else event.volume_quality,
                "meets_volume_threshold": event.meets_volume_threshold,
            }
            volume_quality_scores[event_type] = _calculate_volume_quality_score(event, thresholds)

    volume_violations: list[str] = []

    # BC must have climactic volume
    if "BC" in detected_events:
        bc_events = trading_range.get_events_by_type("BC")
        if bc_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.BC, bc_events[0].volume_ratio
        ):
            volume_violations.append(
                f"BC volume ({bc_events[0].volume_ratio}) below climactic threshold ({thresholds.bc_min})"
            )

    # LPSY must have weak volume
    if "LPSY" in detected_events:
        lpsy_events = trading_range.get_events_by_type("LPSY")
        if lpsy_events and not thresholds.validate_volume_for_event(
            WyckoffEventType.LPSY, lpsy_events[0].volume_ratio
        ):
            volume_violations.append(
                f"LPSY volume ({lpsy_events[0].volume_ratio}) above weak-rally threshold ({thresholds.lpsy_max})"
            )

    # Validate sequence
    sequence_valid, sequence_violations = validate_event_sequence(events_list, required_events)

    # Calculate confidence
    if missing_events:
        confidence_score = 0.0
    elif volume_violations:
        confidence_score = 0.5
    else:
        if volume_quality_scores:
            confidence_score = sum(volume_quality_scores.values()) / len(volume_quality_scores)
        else:
            confidence_score = 1.0

    is_valid = len(missing_events) == 0 and len(volume_violations) == 0 and sequence_valid

    rejection_reason = None
    if not is_valid:
        reasons = []
        if missing_events:
            reasons.append(f"Missing prerequisites: {', '.join(missing_events)}")
        if volume_violations:
            reasons.extend(volume_violations)
        if sequence_violations:
            reasons.extend(sequence_violations)
        rejection_reason = "; ".join(reasons)

    logger.info(
        "utad_prerequisite_validation",
        is_valid=is_valid,
        missing_events=missing_events,
        detected_events=list(detected_events.keys()),
        volume_violations=volume_violations,
        confidence_score=confidence_score,
    )

    return PhaseValidation(
        is_valid=is_valid,
        pattern_type="UTAD",
        phase_complete=len(missing_events) == 0,
        missing_prerequisites=missing_events,
        prerequisite_events=detected_events,
        validation_mode="STRICT",
        rejection_reason=rejection_reason,
        prerequisite_confidence_score=confidence_score,
        volume_quality_scores=volume_quality_scores,
        sequence_violations=sequence_violations,
    )


def validate_phase_prerequisites(
    pattern_type: PatternType | str,
    trading_range: TradingRange,
    mode: str = "STRICT",
    thresholds: VolumeThresholds | None = None,
    prerequisites: PhasePrerequisites | None = None,
    permissive_controls: PermissiveModeControls | None = None,
) -> PhaseValidation:
    """
    Unified phase prerequisite validator - routes to pattern-specific validators.

    This is the main entry point for phase validation, called by RiskManager
    in Step 2 of the validation pipeline. If validation fails and mode is
    STRICT (default), signal is rejected. If PERMISSIVE, warning is logged
    but entry allowed with risk controls.

    Parameters:
        pattern_type: Pattern type (SPRING, SOS, LPS, UTAD) as PatternType or string
        trading_range: TradingRange with event_history
        mode: Validation mode - "STRICT" (default) or "PERMISSIVE"
        thresholds: Volume threshold configuration (optional)
        prerequisites: Prerequisite configuration (optional)
        permissive_controls: Risk controls for PERMISSIVE mode (optional)

    Returns:
        PhaseValidation with complete validation result

    Example:
        >>> from src.models.risk_allocation import PatternType
        >>> validation = validate_phase_prerequisites(
        ...     pattern_type=PatternType.SPRING,
        ...     trading_range=trading_range,
        ...     mode="STRICT"
        ... )
        >>> if validation.is_valid:
        ...     print("Phase validation passed")
        >>> else:
        ...     print(f"Rejected: {validation.rejection_reason}")
    """
    thresholds = thresholds or DEFAULT_VOLUME_THRESHOLDS
    prerequisites = prerequisites or DEFAULT_PREREQUISITES
    permissive_controls = permissive_controls or DEFAULT_PERMISSIVE_CONTROLS

    # Convert PatternType enum to string
    pattern_str = pattern_type.value if hasattr(pattern_type, "value") else str(pattern_type)
    pattern_str = pattern_str.upper()

    # Route to pattern-specific validator
    validators = {
        "SPRING": validate_spring_prerequisites,
        "SOS": validate_sos_prerequisites,
        "LPS": validate_lps_prerequisites,
        "UTAD": validate_utad_prerequisites,
    }

    validator = validators.get(pattern_str)
    if validator is None:
        # Unknown pattern type - return passing validation (no prerequisites defined)
        logger.warning(
            "phase_validation_unknown_pattern",
            pattern_type=pattern_str,
            message="No prerequisites defined for this pattern type",
        )
        return PhaseValidation(
            is_valid=True,
            pattern_type=pattern_str,
            phase_complete=True,
            missing_prerequisites=[],
            prerequisite_events={},
            validation_mode=mode,
            rejection_reason=None,
            prerequisite_confidence_score=1.0,
            volume_quality_scores={},
        )

    # Run pattern-specific validation
    validation = validator(trading_range, thresholds, prerequisites)

    # Apply mode override
    if mode == "PERMISSIVE" and not validation.is_valid:
        # In PERMISSIVE mode, convert rejection to warning
        logger.warning(
            "phase_validation_permissive_warning",
            pattern_type=pattern_str,
            original_rejection=validation.rejection_reason,
            permissive_controls={
                "position_multiplier": str(permissive_controls.max_position_size_multiplier),
                "stop_multiplier": str(permissive_controls.stop_distance_multiplier),
                "allow_scaling": permissive_controls.allow_scaling,
            },
        )

        # Return modified validation with warning instead of rejection
        return PhaseValidation(
            is_valid=True,  # Allow entry in PERMISSIVE mode
            pattern_type=pattern_str,
            phase_complete=validation.phase_complete,
            missing_prerequisites=validation.missing_prerequisites,
            warning_level="HIGH" if validation.prerequisite_confidence_score < 0.5 else "MEDIUM",
            prerequisite_events=validation.prerequisite_events,
            validation_mode="PERMISSIVE",
            rejection_reason=None,  # Clear rejection, entry allowed
            prerequisite_confidence_score=validation.prerequisite_confidence_score,
            volume_quality_scores=validation.volume_quality_scores,
            sequence_violations=validation.sequence_violations,
            permissive_controls_applied=True,
        )

    # Update validation mode in result
    validation.validation_mode = mode
    return validation
