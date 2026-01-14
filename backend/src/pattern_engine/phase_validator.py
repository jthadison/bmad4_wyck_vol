"""
Pattern-Phase Validation Module (Story 13.7)

Validates that detected Wyckoff patterns match expected phases,
ensuring pattern detection aligns with Wyckoff methodology.

This module implements:
- FR7.2: Pattern-Phase Validation
- FR7.2.5: Level Proximity Validation (Sam's addition)
- FR7.4: Phase Confidence Adjustment
- FR7.4.1: Volume-Phase Confidence Integration (Victoria's addition)
- FR7.3: Campaign Phase Progression Tracking

Author: Story 13.7 Implementation
"""

from decimal import Decimal
from typing import Optional, Union

import structlog

from src.models.lps import LPS
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.trading_range import TradingRange

logger = structlog.get_logger(__name__)


# ============================================================================
# Expected phases for each pattern type (FR7.2)
# Updated 2026-01-13: LPS now includes Phase D (Philip - Phase Identifier)
# Updated 2026-01-13: Added SecondaryTest for Phase B (Philip - Phase Identifier)
# ============================================================================
PATTERN_PHASE_EXPECTATIONS = {
    "Spring": [WyckoffPhase.C],
    "SOSBreakout": [WyckoffPhase.D, WyckoffPhase.E],
    "LPS": [WyckoffPhase.D, WyckoffPhase.E],  # LPS can occur in late Phase D (AC7.23)
    "SecondaryTest": [WyckoffPhase.B],  # ST is Phase B pattern
    "SellingClimax": [WyckoffPhase.A],
    "AutomaticRally": [WyckoffPhase.A, WyckoffPhase.B],
}


# ============================================================================
# Valid phase transitions - Wyckoff progression (FR7.3)
# Updated 2026-01-13: Added B → D for Schematic #1 (AC7.22 - Philip)
# ============================================================================
VALID_PHASE_TRANSITIONS = {
    None: [WyckoffPhase.A, WyckoffPhase.B],  # Campaign can start in A or B
    WyckoffPhase.A: [WyckoffPhase.B],
    WyckoffPhase.B: [WyckoffPhase.B, WyckoffPhase.C, WyckoffPhase.D],  # B→D for Schematic #1
    WyckoffPhase.C: [WyckoffPhase.C, WyckoffPhase.D],  # Can stay in C (multiple tests)
    WyckoffPhase.D: [WyckoffPhase.D, WyckoffPhase.E],  # Can stay in D
    WyckoffPhase.E: [WyckoffPhase.E],  # Can stay in Phase E during markup
}


# ============================================================================
# Phase-Volume Expectations (FR7.4.1 - Victoria's addition)
# Each phase has expected volume characteristics
# ============================================================================
PHASE_VOLUME_EXPECTATIONS: dict[WyckoffPhase, dict[str, float | str]] = {
    WyckoffPhase.A: {"min": 2.0, "max": 5.0, "desc": "climactic"},
    WyckoffPhase.B: {"min": 0.6, "max": 1.0, "desc": "declining"},
    WyckoffPhase.C: {"min": 0.3, "max": 0.7, "desc": "low (test)"},
    WyckoffPhase.D: {"min": 1.5, "max": 3.0, "desc": "expanding"},
    WyckoffPhase.E: {"min": 0.8, "max": 1.2, "desc": "moderate"},
}


# ============================================================================
# Pattern-Phase Validation Functions (FR7.2)
# ============================================================================


def validate_pattern_phase_consistency(
    pattern: Union[Spring, SOSBreakout, LPS],
    detected_phase: PhaseClassification,
) -> tuple[bool, Optional[str]]:
    """
    Validate that pattern matches expected Wyckoff phase.

    FR7.2: Pattern-Phase Validation Rules:
        - Spring patterns → Phase C only
        - SOS patterns → Phase D, early E
        - LPS patterns → Phase D (late), E

    Args:
        pattern: Detected pattern (Spring, SOS, LPS, etc.)
        detected_phase: Current phase from PhaseDetector

    Returns:
        tuple: (is_valid: bool, rejection_reason: Optional[str])

    Example:
        >>> spring = Spring(...)
        >>> phase = PhaseClassification(phase=WyckoffPhase.C, ...)
        >>> is_valid, reason = validate_pattern_phase_consistency(spring, phase)
        >>> assert is_valid  # Spring is valid in Phase C
    """
    pattern_type = type(pattern).__name__
    expected_phases = PATTERN_PHASE_EXPECTATIONS.get(pattern_type, [])

    if not expected_phases:
        # Unknown pattern type - allow by default
        logger.warning(
            "unknown_pattern_type",
            pattern_type=pattern_type,
            message="Pattern type not in expectations, allowing by default",
        )
        return (True, None)

    # Check if detected phase is in expected phases
    if detected_phase.phase not in expected_phases:
        expected_str = "/".join(p.name for p in expected_phases)
        reason = f"{pattern_type} in {detected_phase.phase.name} - expected {expected_str}"

        logger.warning(
            "pattern_phase_mismatch",
            pattern_type=pattern_type,
            detected_phase=detected_phase.phase.name,
            expected_phases=expected_str,
            pattern_timestamp=getattr(pattern, "timestamp", None),
        )
        return (False, reason)

    # Valid pattern-phase match
    logger.debug(
        "pattern_phase_validation_passed",
        pattern_type=pattern_type,
        phase=detected_phase.phase.name,
        confidence=detected_phase.confidence,
    )
    return (True, None)


# ============================================================================
# Level Proximity Validation Functions (FR7.2.5 - Sam's addition)
# ============================================================================


def validate_pattern_level_proximity(
    pattern: Union[Spring, SOSBreakout, LPS],
    trading_range: TradingRange,
    current_price: Decimal,
) -> tuple[bool, Optional[str]]:
    """
    Validate pattern occurs at appropriate price level.

    FR7.2.5: Level Proximity Rules (Sam - Supply/Demand Mapper):
        - Spring: At or below Creek (support) - +0.5% tolerance
        - SOS: Above Ice (resistance) - must break Ice
        - LPS: Near Ice (now support) - ±2% from Ice
        - ST: Near Creek (support) - ±1.5% from Creek

    Wyckoff patterns require BOTH:
        - Correct phase (temporal)
        - Correct level proximity (spatial)

    Args:
        pattern: Detected pattern
        trading_range: Current trading range with Ice/Creek
        current_price: Price at pattern detection

    Returns:
        tuple: (is_valid: bool, rejection_reason: Optional[str])

    Example:
        >>> spring = Spring(...)
        >>> is_valid, reason = validate_pattern_level_proximity(
        ...     spring, trading_range, Decimal("1.0520")
        ... )
    """
    pattern_type = type(pattern).__name__

    # Get Creek (support) and Ice (resistance) levels
    creek = _get_creek_price(trading_range)
    ice = _get_ice_price(trading_range)

    # Spring: Must be at/below Creek (support test) - +0.5% tolerance above
    if pattern_type == "Spring":
        max_valid_price = creek * Decimal("1.005")  # 0.5% tolerance above Creek
        if current_price > max_valid_price:
            reason = (
                f"Spring at {current_price:.4f} too far above Creek {creek:.4f} "
                f"(max: {max_valid_price:.4f})"
            )
            logger.warning(
                "spring_level_invalid",
                current_price=float(current_price),
                creek=float(creek),
                max_valid=float(max_valid_price),
            )
            return (False, reason)

    # SOS: Must break above Ice (resistance breakout)
    elif pattern_type == "SOSBreakout":
        if current_price < ice:
            reason = f"SOS at {current_price:.4f} hasn't broken Ice {ice:.4f}"
            logger.warning(
                "sos_level_invalid",
                current_price=float(current_price),
                ice=float(ice),
            )
            return (False, reason)

    # LPS: Must be near Ice (now support after breakout) - ±2% tolerance
    elif pattern_type == "LPS":
        distance_pct = abs(current_price - ice) / ice * Decimal("100")
        if distance_pct > Decimal("2.0"):
            reason = (
                f"LPS at {current_price:.4f} is {distance_pct:.1f}% from Ice {ice:.4f} " f"(max 2%)"
            )
            logger.warning(
                "lps_level_invalid",
                current_price=float(current_price),
                ice=float(ice),
                distance_pct=float(distance_pct),
            )
            return (False, reason)

    # SecondaryTest: Must be near Creek - ±1.5% tolerance
    elif pattern_type == "SecondaryTest":
        distance_pct = abs(current_price - creek) / creek * Decimal("100")
        if distance_pct > Decimal("1.5"):
            reason = (
                f"ST at {current_price:.4f} is {distance_pct:.1f}% from Creek {creek:.4f} "
                f"(max 1.5%)"
            )
            logger.warning(
                "st_level_invalid",
                current_price=float(current_price),
                creek=float(creek),
                distance_pct=float(distance_pct),
            )
            return (False, reason)

    logger.debug(
        "pattern_level_validation_passed",
        pattern_type=pattern_type,
        current_price=float(current_price),
        creek=float(creek),
        ice=float(ice),
    )
    return (True, None)


def validate_pattern_phase_and_level(
    pattern: Union[Spring, SOSBreakout, LPS],
    detected_phase: PhaseClassification,
    trading_range: TradingRange,
    current_price: Decimal,
) -> tuple[bool, Optional[str]]:
    """
    Combined validation: BOTH phase AND level must be valid.

    This is the primary validation function that should be called
    for all pattern validation (AC7.24).

    Validation Order: Phase → Level → (Volume in separate function)

    Args:
        pattern: Detected pattern
        detected_phase: Current phase from PhaseDetector
        trading_range: Current trading range with Ice/Creek
        current_price: Price at pattern detection

    Returns:
        tuple: (is_valid: bool, rejection_reason: Optional[str])

    Example:
        >>> is_valid, reason = validate_pattern_phase_and_level(
        ...     spring, detected_phase, trading_range, current_price
        ... )
        >>> if not is_valid:
        ...     print(f"Pattern rejected: {reason}")
    """
    # Phase validation first (AC7.24 - order matters)
    phase_valid, phase_reason = validate_pattern_phase_consistency(pattern, detected_phase)
    if not phase_valid:
        return (False, f"Phase validation failed: {phase_reason}")

    # Level validation second
    level_valid, level_reason = validate_pattern_level_proximity(
        pattern, trading_range, current_price
    )
    if not level_valid:
        return (False, f"Level validation failed: {level_reason}")

    logger.info(
        "combined_validation_passed",
        pattern_type=type(pattern).__name__,
        phase=detected_phase.phase.name,
        price=float(current_price),
    )
    return (True, None)


# ============================================================================
# Phase Confidence Adjustment Functions (FR7.4)
# ============================================================================


def adjust_pattern_confidence_for_phase(
    pattern_confidence: int,
    phase_classification: PhaseClassification,
) -> int:
    """
    Adjust pattern confidence based on phase classification quality.

    FR7.4: Phase Confidence Adjustment Formula:
        adjusted = base * (0.5 + 0.5 * phase_confidence / 100)

    Low phase confidence → Lower pattern confidence (ambiguous structure)
    High phase confidence → Pattern confidence maintained

    Args:
        pattern_confidence: Base pattern confidence (0-100)
        phase_classification: Detected phase with confidence

    Returns:
        Adjusted confidence (0-100)

    Example:
        >>> # Base: 85, Phase: 80%
        >>> adjusted = adjust_pattern_confidence_for_phase(85, phase_80pct)
        >>> print(adjusted)  # 85 * 0.9 = 76.5 → 76

        >>> # Base: 85, Phase: 40% (low)
        >>> adjusted = adjust_pattern_confidence_for_phase(85, phase_40pct)
        >>> print(adjusted)  # 85 * 0.7 = 59.5 → 59 (below 70 threshold)
    """
    phase_confidence = phase_classification.confidence
    multiplier = 0.5 + 0.5 * (phase_confidence / 100.0)

    adjusted = int(pattern_confidence * multiplier)

    if adjusted < pattern_confidence:
        logger.info(
            "pattern_confidence_adjusted_for_phase",
            base_confidence=pattern_confidence,
            adjusted_confidence=adjusted,
            phase_confidence=phase_confidence,
            phase=phase_classification.phase.name if phase_classification.phase else "None",
        )

    return adjusted


# ============================================================================
# Volume-Phase Confidence Integration (FR7.4.1 - Victoria's addition)
# ============================================================================


def calculate_volume_multiplier(
    phase: Optional[WyckoffPhase],
    volume_ratio: float,
) -> float:
    """
    Calculate confidence multiplier based on volume-phase alignment.

    FR7.4.1: Volume Signatures by Phase (Victoria - Volume Specialist):
        - Phase A: Ultra-high (climactic) - 2.0-5.0x
        - Phase B: Declining, mixed - 0.6-1.0x
        - Phase C: Very low on test - 0.3-0.7x
        - Phase D: Expanding on breakout - 1.5-3.0x
        - Phase E: Sustained moderate - 0.8-1.2x

    Returns:
        Multiplier between 0.7 (penalized) and 1.1 (boosted)

    Example:
        >>> # Spring with low volume (correct for Phase C)
        >>> mult = calculate_volume_multiplier(WyckoffPhase.C, 0.5)
        >>> print(mult)  # 1.1 (boost)

        >>> # Spring with high volume (suspicious for Phase C)
        >>> mult = calculate_volume_multiplier(WyckoffPhase.C, 1.4)
        >>> print(mult)  # 0.7 (penalty)
    """
    if phase is None:
        return 1.0

    expectations = PHASE_VOLUME_EXPECTATIONS.get(phase)
    if not expectations:
        return 1.0

    min_vol = float(expectations["min"])
    max_vol = float(expectations["max"])

    if min_vol <= volume_ratio <= max_vol:
        # Volume matches phase expectations - slight boost
        return 1.1
    elif volume_ratio < min_vol * 0.5 or volume_ratio > max_vol * 2.0:
        # Volume significantly mismatches - strong penalty
        return 0.7
    else:
        # Volume slightly outside range - minor penalty
        return 0.9


def adjust_pattern_confidence_for_phase_and_volume(
    pattern_confidence: int,
    phase_classification: PhaseClassification,
    volume_ratio: float,
) -> int:
    """
    Adjust confidence based on BOTH phase AND volume context.

    This is the enhanced version integrating Victoria's volume analysis (FR7.4.1).

    Combined adjustment = phase_multiplier * volume_multiplier

    Args:
        pattern_confidence: Base pattern confidence (0-100)
        phase_classification: Detected phase with confidence
        volume_ratio: Current volume relative to session average

    Returns:
        Adjusted confidence (0-100)

    Example:
        >>> # Ideal Spring: Phase C (87%), volume 0.58x
        >>> adjusted = adjust_pattern_confidence_for_phase_and_volume(
        ...     85, phase_c_87pct, 0.58
        ... )
        >>> # 85 * 0.935 * 1.1 ≈ 87 ✅

        >>> # Suspicious Spring: Phase C (87%), volume 1.4x
        >>> adjusted = adjust_pattern_confidence_for_phase_and_volume(
        ...     85, phase_c_87pct, 1.4
        ... )
        >>> # 85 * 0.935 * 0.7 ≈ 56 ❌ (below 70)
    """
    # Phase multiplier (existing logic)
    phase_multiplier = 0.5 + 0.5 * (phase_classification.confidence / 100.0)

    # Volume multiplier (Victoria's addition)
    volume_multiplier = calculate_volume_multiplier(
        phase_classification.phase,
        volume_ratio,
    )

    # Combined adjustment
    combined_multiplier = phase_multiplier * volume_multiplier
    adjusted = int(pattern_confidence * combined_multiplier)

    logger.info(
        "pattern_confidence_adjusted_for_phase_and_volume",
        base_confidence=pattern_confidence,
        adjusted_confidence=adjusted,
        phase=phase_classification.phase.name if phase_classification.phase else "None",
        phase_confidence=phase_classification.confidence,
        phase_multiplier=f"{phase_multiplier:.2f}",
        volume_ratio=f"{volume_ratio:.2f}x",
        volume_multiplier=f"{volume_multiplier:.2f}",
        combined_multiplier=f"{combined_multiplier:.2f}",
    )

    return adjusted


# ============================================================================
# Phase Transition Validation (FR7.3)
# ============================================================================


def is_valid_phase_transition(
    current_phase: Optional[WyckoffPhase],
    new_phase: WyckoffPhase,
) -> bool:
    """
    Validate phase transition follows Wyckoff progression.

    FR7.3: Valid Phase Transitions (updated AC7.22):
        - None → A or B (campaign start)
        - A → B
        - B → B, C, or D (B→D for Schematic #1 without Spring)
        - C → C or D
        - D → D or E
        - E → E (stay in markup)

    Args:
        current_phase: Current campaign phase (None if starting)
        new_phase: New phase to transition to

    Returns:
        True if transition is valid

    Example:
        >>> is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.D)
        True  # Schematic #1 (no Spring)

        >>> is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.A)
        False  # Invalid regression
    """
    valid_next_phases = VALID_PHASE_TRANSITIONS.get(current_phase, [])

    is_valid = new_phase in valid_next_phases

    if not is_valid:
        current_name = current_phase.name if current_phase else "START"
        logger.warning(
            "invalid_phase_transition",
            current_phase=current_name,
            new_phase=new_phase.name,
            valid_transitions=[p.name for p in valid_next_phases],
        )
    else:
        # Check for special Schematic #1 (B→D without Spring)
        if current_phase == WyckoffPhase.B and new_phase == WyckoffPhase.D:
            logger.info(
                "schematic_1_detected",
                message="Following Accumulation Schematic #1 (no Spring)",
            )

    return is_valid


def get_transition_description(
    from_phase: Optional[WyckoffPhase],
    to_phase: WyckoffPhase,
) -> str:
    """
    Get human-readable description of phase transition.

    Args:
        from_phase: Starting phase
        to_phase: Target phase

    Returns:
        Description string
    """
    from_name = from_phase.name if from_phase else "START"
    to_name = to_phase.name

    descriptions = {
        ("START", "A"): "Campaign started with Selling Climax detected",
        ("START", "B"): "Campaign started in range building (Phase B)",
        ("A", "B"): "Transition to building cause after Selling Climax",
        ("B", "C"): "Spring detected, entering test phase",
        ("B", "D"): "Following Schematic #1 - SOS breakout without Spring",
        ("C", "D"): "Spring held, Sign of Strength breakout",
        ("D", "E"): "Breakout confirmed, entering markup phase",
    }

    return descriptions.get((from_name, to_name), f"Phase transition: {from_name} → {to_name}")


# ============================================================================
# Helper Functions
# ============================================================================


def _get_creek_price(trading_range: TradingRange) -> Decimal:
    """Extract Creek (support) price from trading range."""
    if hasattr(trading_range.creek, "price"):
        return Decimal(str(trading_range.creek.price))
    return Decimal(str(trading_range.support))


def _get_ice_price(trading_range: TradingRange) -> Decimal:
    """Extract Ice (resistance) price from trading range."""
    if hasattr(trading_range, "ice") and trading_range.ice:
        if hasattr(trading_range.ice, "price"):
            return Decimal(str(trading_range.ice.price))
    return Decimal(str(trading_range.resistance))
