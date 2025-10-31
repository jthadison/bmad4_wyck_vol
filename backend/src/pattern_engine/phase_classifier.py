"""
Wyckoff Phase Classification Logic.

This module implements the phase classification system that determines the current
Wyckoff accumulation phase (A, B, C, D, E) based on detected events.

Phase Detection Flow:
    1. Check Phase E (most advanced): sustained above Ice
    2. Check Phase D: SOS breakout detected
    3. Check Phase C: Spring detected
    4. Check Phase B: ST detected
    5. Check Phase A: SC + AR detected
    6. Default: No phase detected

FR14 Trading Restrictions:
    - Phase A: NOT allowed
    - Phase B (<10 bars): NOT allowed
    - Phase B (≥10 bars): ALLOWED
    - Phase C/D/E: ALLOWED

Example:
    >>> from backend.src.pattern_engine.phase_classifier import classify_phase
    >>> from backend.src.models.phase_classification import PhaseEvents
    >>>
    >>> events = PhaseEvents(
    ...     selling_climax=sc_dict,
    ...     automatic_rally=ar_dict,
    ...     secondary_tests=[st1_dict, st2_dict]
    ... )
    >>> classification = classify_phase(events, trading_range_dict)
    >>> print(f"Phase: {classification.phase.value}")
    >>> print(f"Trading Allowed: {classification.trading_allowed}")
"""

import structlog
from datetime import datetime, timezone
from typing import Optional, List

from src.models.phase_classification import (
    WyckoffPhase,
    PhaseEvents,
    PhaseClassification,
)

logger = structlog.get_logger(__name__)


def calculate_ar_confidence_proxy(ar: dict) -> int:
    """
    Calculate AR confidence proxy from rally metrics when confidence not available.

    Wyckoff Principle: AR strength indicates professional interest level.
    - Strong AR (8%+ rally, 1-3 bars): professionals stepping in aggressively
    - Moderate AR (5-8% rally, 4-5 bars): decent support
    - Weak AR (3-5% rally, 6-10 bars): tentative support

    Args:
        ar: AutomaticRally dict with rally_pct, bars_after_sc

    Returns:
        int: Proxy confidence score 60-95
    """
    rally_pct = ar.get("rally_pct", 0)
    bars_after_sc = ar.get("bars_after_sc", 0)

    # Base score: 70 (decent AR by definition if it exists)
    confidence = 70

    # Rally vigor (0-20 points)
    if rally_pct >= 0.08:  # 8%+ rally
        confidence += 20  # Strong professional interest
    elif rally_pct >= 0.05:  # 5-8% rally
        confidence += 10  # Moderate
    else:  # 3-5% rally
        confidence += 0  # Minimal (met 3% threshold)

    # Timing quality (0-5 points)
    if 1 <= bars_after_sc <= 3:
        confidence += 5  # Immediate response
    elif 4 <= bars_after_sc <= 5:
        confidence += 3  # Good timing
    else:
        confidence += 0  # Slower response

    return min(95, confidence)  # Cap at 95 (not perfect without explicit confidence)


def calculate_phase_a_confidence(events: PhaseEvents) -> int:
    """
    Calculate Phase A confidence based on SC quality, AR quality, vigor, and event sequence.

    Confidence Components (0-100):
    - SC quality (50 points): SC confidence / 2
    - AR quality (20 points): AR confidence / 5
    - AR vigor (10 points): Rally strength bonus (3-5%=0, 5-8%=5, 8%+=10)
    - Event sequence (20 points): AR timing after SC

    Args:
        events: PhaseEvents containing SC and AR

    Returns:
        int: Confidence score 0-100
    """
    if not events.selling_climax or not events.automatic_rally:
        return 0

    sc = events.selling_climax
    ar = events.automatic_rally

    # SC quality (50 points max)
    sc_confidence = sc.get("confidence", 0)
    sc_pts = min(50, int(sc_confidence / 2))

    # AR quality (20 points max) - reduced from 30
    if "confidence" in ar:
        ar_confidence = ar["confidence"]
    else:
        # Calculate proxy confidence from rally metrics
        ar_confidence = calculate_ar_confidence_proxy(ar)
        logger.debug(
            "phase_a.ar_confidence_proxy",
            ar_confidence=ar_confidence,
            rally_pct=ar.get("rally_pct"),
            bars_after_sc=ar.get("bars_after_sc"),
        )

    ar_pts = min(20, int(ar_confidence / 5))

    # AR vigor bonus (0-10 points) - Wyckoff principle
    rally_pct = ar.get("rally_pct", 0)
    if rally_pct >= 0.08:  # 8%+ rally
        vigor_bonus = 10  # Strong professional interest
    elif rally_pct >= 0.05:  # 5-8%
        vigor_bonus = 5  # Moderate
    else:  # 3-5%
        vigor_bonus = 0  # Minimal

    # Event sequence (20 points max)
    # AR should occur 1-5 bars after SC for ideal sequence
    bars_after_sc = ar.get("bars_after_sc", 0)
    if 1 <= bars_after_sc <= 5:
        sequence_pts = 20
    elif 6 <= bars_after_sc <= 10:
        sequence_pts = 10
    else:
        sequence_pts = 5

    total = sc_pts + ar_pts + vigor_bonus + sequence_pts

    logger.debug(
        "phase_a_confidence_breakdown",
        sc_pts=sc_pts,
        ar_pts=ar_pts,
        vigor_bonus=vigor_bonus,
        sequence_pts=sequence_pts,
        total=total,
    )

    return min(100, total)


def analyze_st_progression(secondary_tests: List[dict]) -> int:
    """
    Analyze Secondary Test progression quality per Wyckoff principles.

    Wyckoff Teaching: Quality of cause matters. Look for:
    1. Consistent volume absorption (50%+ reduction maintained)
    2. Tightening to support (later STs closer to SC low)

    Args:
        secondary_tests: List of SecondaryTest dicts

    Returns:
        int: Progression quality score 0-15 points
        - 0-8 points: Volume absorption trend
        - 0-7 points: Distance tightening
    """
    if len(secondary_tests) < 2:
        return 0  # Need multiple tests to see trend

    # Volume reduction trend analysis (0-8 points)
    volume_reductions = [st.get("volume_reduction_pct", 0) for st in secondary_tests]
    avg_reduction = sum(volume_reductions) / len(volume_reductions)

    volume_pts = 0
    if avg_reduction >= 0.50:  # 50%+ avg reduction (excellent absorption)
        volume_pts = 8
    elif avg_reduction >= 0.40:  # 40-50% (good)
        volume_pts = 6
    elif avg_reduction >= 0.30:  # 30-40% (adequate)
        volume_pts = 4
    elif avg_reduction >= 0.20:  # 20-30% (weak)
        volume_pts = 2

    # Distance tightening analysis (0-7 points)
    distances = [st.get("distance_from_sc_low", 1.0) for st in secondary_tests]

    tightening_pts = 0
    first_distance = distances[0]
    last_distance = distances[-1]

    if last_distance < first_distance:
        # Tightening = support firming (Wyckoff excellence indicator)
        improvement = (first_distance - last_distance) / first_distance

        if improvement >= 0.40:  # 40%+ tighter
            tightening_pts = 7  # Excellent tightening
        elif improvement >= 0.25:  # 25-40% tighter
            tightening_pts = 5  # Good tightening
        elif improvement >= 0.10:  # 10-25% tighter
            tightening_pts = 3  # Moderate tightening
        else:
            tightening_pts = 1  # Slight tightening

    total_pts = volume_pts + tightening_pts

    logger.debug(
        "st_progression_analysis",
        st_count=len(secondary_tests),
        avg_volume_reduction=avg_reduction,
        volume_pts=volume_pts,
        tightening_pts=tightening_pts,
        total_pts=total_pts,
    )

    return total_pts


def calculate_phase_b_confidence(events: PhaseEvents, duration: int) -> int:
    """
    Calculate Phase B confidence with Wyckoff-optimized weights.

    Wyckoff-Aligned Weights:
    - ST quality (35 points): Average ST confidence quality
    - ST count (25 points): Number of tests (cause building)
    - Duration (20 points): Time in range (10-40+ bars)
    - ST progression (20 points): Improving quality trend

    Previous weights: 40/30/30/0 (no progression analysis)

    Args:
        events: PhaseEvents containing STs
        duration: Phase B duration in bars

    Returns:
        int: Confidence score 0-100
    """
    if not events.secondary_tests:
        return 0

    # ST quality (35 points max) - reduced from 40
    st_confidences = [st.get("confidence", 0) for st in events.secondary_tests]
    avg_st_confidence = (
        sum(st_confidences) / len(st_confidences) if st_confidences else 0
    )
    st_quality_pts = min(35, int(avg_st_confidence * 0.35))

    # ST count (25 points max) - reduced from 30
    st_count = len(events.secondary_tests)
    if st_count == 1:
        st_count_pts = 8  # Minimal cause (reduced from 10)
    elif st_count == 2:
        st_count_pts = 17  # Moderate cause (reduced from 20)
    else:  # 3+
        st_count_pts = 25  # Strong cause (reduced from 30)

    # Duration (20 points max) - reduced from 30
    if 10 <= duration <= 20:
        duration_pts = 10  # Minimal cause (reduced from 15)
    elif 21 <= duration <= 30:
        duration_pts = 17  # Moderate cause (reduced from 25)
    else:  # 31-40+ bars
        duration_pts = 20  # Strong/extended cause (reduced from 30)

    # ST progression (20 points max) - NEW
    progression_pts = analyze_st_progression(events.secondary_tests)

    total = st_quality_pts + st_count_pts + duration_pts + progression_pts

    logger.debug(
        "phase_b_confidence_breakdown",
        st_quality=st_quality_pts,
        st_count=st_count_pts,
        duration=duration_pts,
        progression=progression_pts,
        total=total,
    )

    return min(100, total)


def calculate_phase_c_confidence(events: PhaseEvents) -> int:
    """
    Calculate Phase C confidence based on Spring quality.

    Args:
        events: PhaseEvents containing Spring

    Returns:
        int: Confidence score 0-100 (based on Spring confidence)
    """
    if not events.spring:
        return 0

    # Spring confidence maps directly to Phase C confidence
    spring_confidence = events.spring.get("confidence", 0)
    # If Spring confidence >= 80, Phase C confidence = 85+
    if spring_confidence >= 80:
        return min(100, spring_confidence + 5)
    return spring_confidence


def calculate_phase_d_confidence(events: PhaseEvents) -> int:
    """
    Calculate Phase D confidence based on SOS breakout quality.

    Args:
        events: PhaseEvents containing SOS breakout

    Returns:
        int: Confidence score 0-100 (based on SOS confidence)
    """
    if not events.sos_breakout:
        return 0

    # SOS confidence maps directly to Phase D confidence
    sos_confidence = events.sos_breakout.get("confidence", 0)
    # If SOS confidence >= 80, Phase D confidence = 85+
    if sos_confidence >= 80:
        return min(100, sos_confidence + 5)
    return sos_confidence


def calculate_phase_e_confidence(events: PhaseEvents) -> int:
    """
    Calculate Phase E confidence based on sustained move and LPS presence.

    Args:
        events: PhaseEvents containing LPS (optional)

    Returns:
        int: Confidence score 0-100
    """
    # If LPS detected, high confidence
    if events.last_point_of_support:
        lps_confidence = events.last_point_of_support.get("confidence", 0)
        return min(100, lps_confidence + 5)  # 85+ if LPS confidence >= 80

    # No LPS but sustained move (this function called only if sustained)
    return 75


def classify_phase_a(
    events: PhaseEvents, current_bar_index: Optional[int] = None
) -> Optional[PhaseClassification]:
    """
    Classify Phase A based on SC + AR presence.

    Phase A Requirements:
    - SC detected: events.selling_climax is not None
    - AR detected: events.automatic_rally is not None

    Phase A Duration:
    - Start: SC bar index
    - End: first ST bar index OR current bar if no ST yet

    Trading: NOT allowed (FR14)

    Args:
        events: PhaseEvents containing SC and AR
        current_bar_index: Current bar index for real-time analysis (optional).
                          If provided, enables accurate duration calculation for
                          phases still in progress. If None, uses historical mode.

    Returns:
        PhaseClassification if Phase A, None otherwise
    """
    logger.debug(
        "classify_phase_a.checking",
        has_sc=events.selling_climax is not None,
        has_ar=events.automatic_rally is not None,
    )

    if not events.selling_climax or not events.automatic_rally:
        logger.debug("classify_phase_a.failed", reason="Missing SC or AR")
        return None

    sc = events.selling_climax
    ar = events.automatic_rally

    # Phase A duration calculation
    sc_index = sc["bar"]["index"]

    if events.secondary_tests:
        # Phase A ended when first ST appeared
        end_index = events.secondary_tests[0]["bar"]["index"]
    elif current_bar_index is not None:
        # Real-time: Still in Phase A, use current bar
        end_index = current_bar_index
    else:
        # Historical fallback: use AR bar (acknowledging limitation)
        end_index = ar["bar"]["index"]
        logger.warning(
            "phase_a.duration_approximation",
            message="No ST or current bar, using AR index as fallback",
        )

    duration = end_index - sc_index

    # Calculate confidence
    confidence = calculate_phase_a_confidence(events)

    # Get phase start timestamp from SC bar
    phase_start_timestamp = datetime.fromisoformat(sc["bar"]["timestamp"])

    logger.info(
        "classify_phase_a.success",
        phase="A",
        confidence=confidence,
        duration=duration,
        trading_allowed=False,
    )

    return PhaseClassification(
        phase=WyckoffPhase.A,
        confidence=confidence,
        duration=duration,
        events_detected=events,
        trading_range=None,
        trading_allowed=False,
        rejection_reason="Phase A - stopping action, accumulation not established",
        phase_start_index=sc_index,
        phase_start_timestamp=phase_start_timestamp,
    )


def classify_phase_b(
    events: PhaseEvents,
    trading_range: Optional[dict] = None,
    current_bar_index: Optional[int] = None,
) -> Optional[PhaseClassification]:
    """
    Classify Phase B based on ST presence and range oscillation.

    Phase B Requirements:
    - ST completed: len(events.secondary_tests) >= 1
    - Price oscillating in range (trading_range provided)

    Phase B Duration:
    - Start: first ST bar index
    - End: Spring bar index OR current bar if no Spring yet

    Trading Logic (FR14):
    - Duration < 10 bars: NOT allowed (insufficient cause)
    - Duration >= 10 bars: ALLOWED (adequate cause)

    Args:
        events: PhaseEvents containing STs
        trading_range: Associated trading range (optional)
        current_bar_index: Current bar index for real-time analysis (optional).
                          If provided, enables accurate duration calculation for
                          phases still in progress. If None, uses historical mode.

    Returns:
        PhaseClassification if Phase B, None otherwise
    """
    logger.debug("classify_phase_b.checking", st_count=len(events.secondary_tests))

    if not events.secondary_tests:
        logger.debug("classify_phase_b.failed", reason="No STs detected")
        return None

    first_st = events.secondary_tests[0]
    first_st_index = first_st["bar"]["index"]

    # Phase B duration calculation
    if events.spring:
        # Phase B ended when Spring appeared
        end_index = events.spring["bar"]["index"]
    elif current_bar_index is not None:
        # Real-time: Still in Phase B, use current bar
        end_index = current_bar_index
    else:
        # Historical fallback: use last ST bar index
        end_index = events.secondary_tests[-1]["bar"]["index"]
        if len(events.secondary_tests) == 1:
            logger.warning(
                "phase_b.duration_approximation",
                message="Only 1 ST, no current bar - duration may be 0",
            )

    duration = end_index - first_st_index

    # FR14 Trading Logic
    trading_allowed = duration >= 10
    rejection_reason = (
        None
        if trading_allowed
        else "Early Phase B - insufficient cause (need 10+ bars)"
    )

    # Calculate confidence
    confidence = calculate_phase_b_confidence(events, duration)

    # Get phase start timestamp from first ST
    phase_start_timestamp = datetime.fromisoformat(first_st["bar"]["timestamp"])

    logger.info(
        "classify_phase_b.success",
        phase="B",
        confidence=confidence,
        duration=duration,
        trading_allowed=trading_allowed,
    )

    return PhaseClassification(
        phase=WyckoffPhase.B,
        confidence=confidence,
        duration=duration,
        events_detected=events,
        trading_range=trading_range,
        trading_allowed=trading_allowed,
        rejection_reason=rejection_reason,
        phase_start_index=first_st_index,
        phase_start_timestamp=phase_start_timestamp,
    )


def classify_phase_c(
    events: PhaseEvents, current_bar_index: Optional[int] = None
) -> Optional[PhaseClassification]:
    """
    Classify Phase C based on Spring detection.

    Phase C Requirements:
    - Spring detected: events.spring is not None
    - Occurs after adequate Phase B duration (10+ bars)

    Phase C Duration:
    - Start: Spring bar index
    - End: SOS breakout index OR current bar if no SOS yet

    Trading: ALLOWED (FR14)

    Args:
        events: PhaseEvents containing Spring
        current_bar_index: Current bar index for real-time analysis (optional).
                          If provided, enables accurate duration calculation for
                          phases still in progress. If None, uses historical mode.

    Returns:
        PhaseClassification if Phase C, None otherwise
    """
    logger.debug("classify_phase_c.checking", has_spring=events.spring is not None)

    if not events.spring:
        logger.debug("classify_phase_c.failed", reason="No Spring detected")
        return None

    spring = events.spring
    spring_index = spring["bar"]["index"]

    # Phase C duration calculation
    if events.sos_breakout:
        end_index = events.sos_breakout["bar"]["index"]
    else:
        # Use Spring bar as current
        end_index = spring_index

    duration = end_index - spring_index

    # Calculate confidence
    confidence = calculate_phase_c_confidence(events)

    # Get phase start timestamp from Spring
    phase_start_timestamp = datetime.fromisoformat(spring["bar"]["timestamp"])

    logger.info(
        "classify_phase_c.success",
        phase="C",
        confidence=confidence,
        duration=duration,
        trading_allowed=True,
    )

    return PhaseClassification(
        phase=WyckoffPhase.C,
        confidence=confidence,
        duration=duration,
        events_detected=events,
        trading_range=None,
        trading_allowed=True,
        rejection_reason=None,
        phase_start_index=spring_index,
        phase_start_timestamp=phase_start_timestamp,
    )


def classify_phase_d(
    events: PhaseEvents, current_bar_index: Optional[int] = None
) -> Optional[PhaseClassification]:
    """
    Classify Phase D based on SOS breakout detection.

    Phase D Requirements:
    - SOS breakout detected: events.sos_breakout is not None
    - Breakout above Ice with high volume

    Phase D Duration:
    - Start: SOS breakout bar index
    - End: current bar OR LPS if detected

    Trading: ALLOWED (FR14)

    Args:
        events: PhaseEvents containing SOS breakout
        current_bar_index: Current bar index for real-time analysis (optional).
                          If provided, enables accurate duration calculation for
                          phases still in progress. If None, uses historical mode.

    Returns:
        PhaseClassification if Phase D, None otherwise
    """
    logger.debug("classify_phase_d.checking", has_sos=events.sos_breakout is not None)

    if not events.sos_breakout:
        logger.debug("classify_phase_d.failed", reason="No SOS breakout detected")
        return None

    sos = events.sos_breakout
    sos_index = sos["bar"]["index"]

    # Phase D duration calculation
    if events.last_point_of_support:
        end_index = events.last_point_of_support["bar"]["index"]
    else:
        # Use SOS bar as current
        end_index = sos_index

    duration = end_index - sos_index

    # Calculate confidence
    confidence = calculate_phase_d_confidence(events)

    # Get phase start timestamp from SOS
    phase_start_timestamp = datetime.fromisoformat(sos["bar"]["timestamp"])

    logger.info(
        "classify_phase_d.success",
        phase="D",
        confidence=confidence,
        duration=duration,
        trading_allowed=True,
    )

    return PhaseClassification(
        phase=WyckoffPhase.D,
        confidence=confidence,
        duration=duration,
        events_detected=events,
        trading_range=None,
        trading_allowed=True,
        rejection_reason=None,
        phase_start_index=sos_index,
        phase_start_timestamp=phase_start_timestamp,
    )


def classify_phase_e(
    events: PhaseEvents,
    trading_range: Optional[dict] = None,
    current_bar_index: Optional[int] = None,
) -> Optional[PhaseClassification]:
    """
    Classify Phase E based on sustained markup above Ice.

    Phase E Requirements:
    - Price trending above Ice level
    - Sustained move (multiple bars above Ice)
    - LPS may be present (pullback to Ice, holds, continues)

    Phase E Duration:
    - Start: first bar above Ice after SOS OR LPS bar
    - End: current bar

    Trading: ALLOWED (FR14)

    Args:
        events: PhaseEvents (may contain LPS)
        trading_range: Trading range with Ice level
        current_bar_index: Current bar index for real-time analysis (optional).
                          If provided, enables accurate duration calculation for
                          phases still in progress. If None, uses historical mode.

    Returns:
        PhaseClassification if Phase E, None otherwise
    """
    logger.debug(
        "classify_phase_e.checking",
        has_lps=events.last_point_of_support is not None,
        has_sos=events.sos_breakout is not None,
    )

    # Phase E requires SOS to have occurred first
    if not events.sos_breakout:
        logger.debug("classify_phase_e.failed", reason="No SOS (Phase D not complete)")
        return None

    # Check if sustained above Ice
    # For now, we'll detect Phase E if LPS is present OR if we have explicit signal
    # This will be enhanced in Epic 5 with actual Ice level checking

    # Phase E start calculation
    if events.last_point_of_support:
        # Start from LPS
        phase_start_index = events.last_point_of_support["bar"]["index"]
        phase_start_timestamp = datetime.fromisoformat(
            events.last_point_of_support["bar"]["timestamp"]
        )
        # Duration from LPS to current (assume current = LPS for now)
        duration = 0  # Will be updated when we have current bar context
    else:
        # No Phase E without LPS or sustained move indicator
        logger.debug(
            "classify_phase_e.failed", reason="No sustained move above Ice detected"
        )
        return None

    # Calculate confidence
    confidence = calculate_phase_e_confidence(events)

    logger.info(
        "classify_phase_e.success",
        phase="E",
        confidence=confidence,
        duration=duration,
        trading_allowed=True,
    )

    return PhaseClassification(
        phase=WyckoffPhase.E,
        confidence=confidence,
        duration=duration,
        events_detected=events,
        trading_range=trading_range,
        trading_allowed=True,
        rejection_reason=None,
        phase_start_index=phase_start_index,
        phase_start_timestamp=phase_start_timestamp,
    )


def classify_phase(
    events: PhaseEvents,
    trading_range: Optional[dict] = None,
    current_bar_index: Optional[int] = None,
) -> PhaseClassification:
    """
    Classify current Wyckoff phase based on detected events.

    Phase Detection Order (most advanced first):
    1. Try Phase E: sustained above Ice
    2. Try Phase D: SOS breakout
    3. Try Phase C: Spring detected
    4. Try Phase B: ST detected
    5. Try Phase A: SC + AR detected
    6. Default: No phase detected

    Args:
        events: PhaseEvents from Stories 4.1-4.3 + Epic 5
        trading_range: Associated trading range (optional)
        current_bar_index: Current bar index for real-time analysis (optional).
                          When provided, enables accurate duration calculation for phases
                          still in progress. For historical/batch analysis, leave as None.

    Returns:
        PhaseClassification with phase, confidence, trading_allowed

    Example (Historical Mode):
        >>> events = PhaseEvents(
        ...     selling_climax=sc_dict,
        ...     automatic_rally=ar_dict,
        ...     secondary_tests=[st1_dict, st2_dict]
        ... )
        >>> classification = classify_phase(events)
        >>> if classification.trading_allowed:
        ...     print(f"Phase {classification.phase.value} - Trading allowed")
        ... else:
        ...     print(f"Rejected: {classification.rejection_reason}")

    Example (Real-time Mode):
        >>> # Real-time streaming at bar index 125
        >>> classification = classify_phase(events, trading_range, current_bar_index=125)
        >>> print(f"Duration: {classification.duration} bars (still in progress)")
    """
    # Log analysis mode (real-time vs historical)
    analysis_mode = "real-time" if current_bar_index is not None else "historical"
    logger.info(
        "classify_phase.start",
        mode=analysis_mode,
        current_bar_index=current_bar_index,
        has_sc=events.selling_climax is not None,
        has_ar=events.automatic_rally is not None,
        st_count=len(events.secondary_tests),
        has_spring=events.spring is not None,
        has_sos=events.sos_breakout is not None,
        has_lps=events.last_point_of_support is not None,
    )

    # Try phases in reverse order (most advanced first)
    if phase_e := classify_phase_e(events, trading_range, current_bar_index):
        logger.info("classify_phase.result", phase="E", mode=analysis_mode)
        return phase_e

    if phase_d := classify_phase_d(events, current_bar_index):
        logger.info("classify_phase.result", phase="D", mode=analysis_mode)
        return phase_d

    if phase_c := classify_phase_c(events, current_bar_index):
        logger.info("classify_phase.result", phase="C", mode=analysis_mode)
        return phase_c

    if phase_b := classify_phase_b(events, trading_range, current_bar_index):
        logger.info("classify_phase.result", phase="B", mode=analysis_mode)
        return phase_b

    if phase_a := classify_phase_a(events, current_bar_index):
        logger.info("classify_phase.result", phase="A", mode=analysis_mode)
        return phase_a

    # No phase detected
    logger.warning("classify_phase.no_phase_detected")
    return PhaseClassification(
        phase=None,
        confidence=0,
        duration=0,
        events_detected=events,
        trading_range=trading_range,
        trading_allowed=False,
        rejection_reason="No clear Wyckoff phase detected",
        phase_start_index=0,
        phase_start_timestamp=datetime.now(timezone.utc),
    )


# Helper utilities


def get_phase_description(phase: WyckoffPhase) -> str:
    """
    Get human-readable description of a Wyckoff phase.

    Args:
        phase: WyckoffPhase enum value

    Returns:
        str: Human-readable phase description
    """
    descriptions = {
        WyckoffPhase.A: "Stopping Action - Accumulation Beginning",
        WyckoffPhase.B: "Building Cause - Price Oscillation",
        WyckoffPhase.C: "Test - Final Shakeout Before Markup",
        WyckoffPhase.D: "Sign of Strength - Breakout and Markup Beginning",
        WyckoffPhase.E: "Markup - Trend Continuation",
    }
    return descriptions.get(phase, "Unknown Phase")


def get_typical_duration(phase: WyckoffPhase) -> tuple[int, int]:
    """
    Get typical duration range for a Wyckoff phase.

    Args:
        phase: WyckoffPhase enum value

    Returns:
        tuple[int, int]: (min_bars, max_bars) typical for phase
    """
    durations = {
        WyckoffPhase.A: (3, 10),
        WyckoffPhase.B: (10, 40),
        WyckoffPhase.C: (1, 5),
        WyckoffPhase.D: (5, 15),
        WyckoffPhase.E: (10, 999),  # Unlimited, trending
    }
    return durations.get(phase, (0, 0))
