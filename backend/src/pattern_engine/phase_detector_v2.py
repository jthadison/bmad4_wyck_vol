"""
Comprehensive PhaseDetector for Wyckoff Phase Detection (Story 4.7).

This module implements the unified PhaseDetector class that integrates all
Epic 4 components into a cohesive phase detection system with:
- Event detection pipeline (SC → AR → ST → Spring → SOS → LPS)
- Phase classification with confidence scoring
- Phase progression validation
- FR14/FR15 enforcement
- Caching for performance
- Comprehensive risk management

Story 4.7: PhaseDetector Module Integration
Author: Wayne (Analyst), William (Mentor), Victoria (Volume), Rachel (Risk)
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional, Union

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseEvents, WyckoffPhase
from src.models.phase_info import PhaseInfo
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis

# Import phase classifier from Story 4.4
from src.pattern_engine.phase_classifier import classify_phase

# Import existing detectors from Stories 4.1-4.3
# Import confidence calculator (will use existing or create wrapper)
from src.pattern_engine.phase_detector import (
    calculate_phase_confidence,
    detect_automatic_rally,
    detect_secondary_test,
    detect_selling_climax,
)

# Import Story 4.6 phase progression validator
from src.pattern_engine.phase_progression_validator import (
    PhaseHistory,
    enforce_phase_progression,
)

logger = structlog.get_logger(__name__)


class PhaseDetector:
    """
    Unified Wyckoff Phase Detector with comprehensive event detection and risk management.

    This is the primary integration point for Wyckoff phase analysis, unifying:
    - Story 4.1: Selling Climax (SC) detection
    - Story 4.2: Automatic Rally (AR) detection
    - Story 4.3: Secondary Test (ST) detection
    - Story 4.4: Phase classification logic
    - Story 4.5: Confidence scoring
    - Story 4.6: Phase progression validation
    - Story 4.7: Comprehensive integration + enhancements

    Core Responsibilities:
        1. Event detection pipeline (SC → AR → ST → Spring → SOS → LPS)
        2. Phase classification (A, B, C, D, E)
        3. Confidence scoring (0-100, FR3: ≥70%)
        4. Progression tracking (phase transitions)
        5. FR15 enforcement (pattern-phase alignment)
        6. FR14 enforcement (trading restrictions)
        7. Caching (<100ms for 500 bars)
        8. Risk management (invalidation, breakdown, position sizing)

    Usage:
        >>> detector = PhaseDetector()
        >>> phase_info = detector.detect_phase(
        ...     trading_range=range,
        ...     bars=bars,
        ...     volume_analysis=volume_analysis
        ... )
        >>> if phase_info.is_trading_allowed():
        ...     # Generate trading signals
        ...     position_size = calculate_wyckoff_position_size(
        ...         account_size=100000,
        ...         risk_per_trade=0.02,
        ...         entry_price=50.00,
        ...         stop_price=48.50,
        ...         phase_info=phase_info
        ...     )

    Performance Requirements (AC 41):
        - Full 500-bar detection: <100ms
        - Cached results: <5ms
        - Event detection: ~40ms (SC 10ms, AR 5ms, ST 20ms, classify 5ms)

    Integration Points:
        - Epic 5: Spring, SOS, LPS detection (placeholders until implemented)
        - Story 4.6: Phase progression validation
        - VSA Helpers: Volume spread analysis
        - Risk Management: Position sizing, stop placement
    """

    def __init__(self):
        """
        Initialize PhaseDetector with cache.

        Cache Structure:
            {
                "symbol_timeframe": {
                    "bar_count": int,
                    "phase_info": PhaseInfo,
                    "phase_history": PhaseHistory,  # Story 4.6 integration
                    "timestamp": datetime
                }
            }
        """
        self._cache: dict[str, dict] = {}
        logger.info("phase_detector_initialized", message="PhaseDetector ready")

    def detect_phase(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        volume_analysis: list[VolumeAnalysis],
    ) -> PhaseInfo:
        """
        Detect current Wyckoff phase with comprehensive event detection.

        This is the main entry point for phase detection. It orchestrates:
        1. Cache check (AC 5)
        2. Event detection pipeline (AC 3)
        3. Phase classification (Story 4.4)
        4. Confidence scoring (Story 4.5)
        5. Progression tracking (AC 2)
        6. Risk assessment (AC 35-38)
        7. PhaseInfo creation (AC 1)

        Args:
            trading_range: Trading range context (Creek, Ice levels)
            bars: OHLCV bars to analyze (must contain ≥20 bars for valid analysis)
            volume_analysis: Volume analysis results matching bars

        Returns:
            PhaseInfo: Complete phase detection result with risk management

        Raises:
            ValueError: If inputs invalid (empty bars, mismatched lengths, etc.)

        Example:
            >>> detector = PhaseDetector()
            >>> phase_info = detector.detect_phase(range, bars, volume_analysis)
            >>> print(f"Phase: {phase_info.phase}")
            >>> print(f"Confidence: {phase_info.confidence}%")
            >>> print(f"Trading Allowed: {phase_info.is_trading_allowed()}")
            >>> print(f"Risk Level: {phase_info.current_risk_level}")

        Performance:
            - First call: ~75ms (full detection)
            - Cached call: <5ms (cache hit)
            - Target: <100ms for 500 bars (AC 41)
        """
        # Validate inputs
        self._validate_inputs(bars, volume_analysis)

        symbol = bars[0].symbol
        timeframe = bars[0].timeframe
        bar_count = len(bars)
        cache_key = f"{symbol}_{timeframe}"

        logger.info(
            "phase_detection_start",
            symbol=symbol,
            timeframe=timeframe,
            bars_count=bar_count,
        )

        # Check cache (AC 5)
        cached_result = self._check_cache(cache_key, bar_count)
        if cached_result is not None:
            logger.info(
                "phase_detection_cache_hit",
                symbol=symbol,
                cached_phase=cached_result.phase.value if cached_result.phase else None,
                message="Returning cached PhaseInfo",
            )
            return cached_result

        # Detect all events via pipeline (AC 3)
        events = self._detect_all_events(bars, volume_analysis)

        # Classify phase (Story 4.4)
        phase_classification = classify_phase(
            events=events,
            trading_range=trading_range.__dict__ if trading_range else None,
        )

        # Calculate confidence (Story 4.5)
        confidence = calculate_phase_confidence(
            phase=phase_classification.phase if phase_classification.phase else WyckoffPhase.A,
            events=events,
            trading_range=trading_range,
        )

        # ============== Phase 2 Enhancements ==============
        # Determine phase start index for enhancement methods
        phase_start_index = 0
        if events.selling_climax:
            phase_start_index = events.selling_climax["bar_index"]

        # Check for phase invalidations (AC 11-14)
        invalidation = _check_phase_invalidation(
            current_phase=phase_classification.phase,
            bars=bars,
            events=events,
            trading_range=trading_range,
            previous_invalidations=[],  # TODO: Track in cache
        )

        # Check for phase confirmations (AC 15-18)
        confirmation = _check_phase_confirmation(
            current_phase=phase_classification.phase,
            bars=bars,
            events=events,
            trading_range=trading_range,
            previous_confirmations=[],  # TODO: Track in cache
            phase_start_index=phase_start_index,
        )

        # Classify breakdown if applicable (AC 23-26)
        breakdown_type = None
        breakdown_risk_profile = None
        if phase_classification.phase is None:  # Breakdown scenario
            breakdown_type = _classify_breakdown(
                bars=bars,
                volume_analysis=volume_analysis,
                events=events,
                previous_phase=WyckoffPhase.C,  # TODO: Track previous phase
                trading_range=trading_range,
            )
            # Task 38: Create breakdown risk profile
            if breakdown_type:
                breakdown_risk_profile = _get_breakdown_risk_profile(
                    breakdown_type=breakdown_type, bars=bars, trading_range=trading_range
                )

        # Validate Phase B duration (AC 27-30)
        duration_valid = True
        duration_warning = None
        phase_b_context = None
        phase_b_risk_profile = None
        if phase_classification.phase == WyckoffPhase.B:
            duration = len(bars) - 1 - phase_start_index
            duration_valid, duration_warning, phase_b_context = _validate_phase_b_duration(
                phase=phase_classification.phase,
                duration=duration,
                events=events,
                bars=bars,
                volume_analysis=volume_analysis,
            )

            # Task 39: Create Phase B risk profile
            if phase_b_context:
                # Determine exceptional evidence
                has_exceptional = False
                spring_confidence = 0
                if events.spring is not None:
                    spring_confidence = (
                        events.spring.get("confidence", 0) if isinstance(events.spring, dict) else 0
                    )
                st_count = len(events.secondary_tests)
                has_exceptional = spring_confidence > 85 and st_count >= 2

                # Determine minimum duration for context
                minimum_duration_map = {"base_accumulation": 10, "reaccumulation": 5, "volatile": 8}
                minimum_duration = minimum_duration_map.get(phase_b_context, 10)

                phase_b_risk_profile = _get_phase_b_risk_profile(
                    duration=duration,
                    context=phase_b_context,
                    minimum_duration=minimum_duration,
                    has_exceptional_evidence=has_exceptional,
                )

        # Determine sub-phase (AC 19-22)
        sub_phase = _determine_sub_phase(
            phase=phase_classification.phase,
            events=events,
            bars=bars,
            phase_info=None,  # First call, no existing info
            phase_start_index=phase_start_index,
            trading_range=trading_range,
        )

        # Calculate LPS count for Phase E (placeholder until Epic 5)
        lps_count = (
            _count_lps_pullbacks(bars, phase_start_index)
            if phase_classification.phase == WyckoffPhase.E
            else 0
        )

        # Calculate markup slope for Phase E
        markup_slope = (
            _calculate_markup_slope(bars, phase_start_index)
            if phase_classification.phase == WyckoffPhase.E
            else None
        )

        # Task 40: Create Phase E risk profile
        phase_e_risk_profile = None
        if phase_classification.phase == WyckoffPhase.E and sub_phase:
            from src.models.phase_info import PhaseESubState

            if isinstance(sub_phase, PhaseESubState):
                phase_e_risk_profile = _get_phase_e_risk_profile(sub_state=sub_phase)

        logger.info(
            "phase_2_enhancements_applied",
            has_invalidation=invalidation is not None,
            has_confirmation=confirmation is not None,
            breakdown_type=breakdown_type.value if breakdown_type else None,
            sub_phase=sub_phase.value if sub_phase else None,
            duration_valid=duration_valid,
        )

        # ============== Story 4.6 Phase Progression Validation ==============
        # Get or create PhaseHistory for this range
        phase_history = self._get_or_create_phase_history(cache_key, trading_range)

        # Validate phase progression (Story 4.6)
        validated_phase, updated_history = self._validate_and_update_progression(
            phase_history=phase_history,
            new_classification=phase_classification,
            invalidation=invalidation,
            confirmation=confirmation,
            breakdown_type=breakdown_type,
            phase_b_context=phase_b_context,
            current_bar_index=len(bars) - 1,
            bars=bars,
        )

        # Use validated phase (may differ from classified phase if rejected)
        final_phase = validated_phase if validated_phase is not None else phase_classification.phase

        # Update phase_classification with validated phase for PhaseInfo creation
        if final_phase != phase_classification.phase:
            logger.info(
                "using_validated_phase",
                classified_phase=phase_classification.phase.value
                if phase_classification.phase
                else "None",
                validated_phase=final_phase.value if final_phase else "None",
            )

        # Create PhaseInfo (AC 1, 2)
        phase_info = self._create_phase_info(
            phase_classification=phase_classification,
            events=events,
            confidence=confidence,
            trading_range=trading_range,
            bars=bars,
            # Phase 2 enhancement parameters
            invalidation=invalidation,
            confirmation=confirmation,
            breakdown_type=breakdown_type,
            breakdown_risk_profile=breakdown_risk_profile,
            phase_b_context=phase_b_context,
            phase_b_risk_profile=phase_b_risk_profile,
            sub_phase=sub_phase,
            phase_e_risk_profile=phase_e_risk_profile,
            lps_count=lps_count,
            markup_slope=markup_slope,
            # Story 4.6 integration
            phase_history=updated_history,
        )

        # Update cache with phase_info and phase_history
        self._update_cache(cache_key, phase_info, bar_count, updated_history)

        logger.info(
            "phase_detection_complete",
            symbol=symbol,
            phase=phase_info.phase.value if phase_info.phase else "None",
            confidence=phase_info.confidence,
            duration=phase_info.duration,
            risk_level=phase_info.current_risk_level,
        )

        return phase_info

    def is_valid_for_pattern(
        self, phase_info: PhaseInfo, pattern_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if pattern is valid for current phase (FR15 enforcement).

        FR15 Phase-Pattern Alignment Rules:
            - Spring patterns → Phase C only
            - SOS patterns → Phase D only
            - LPS patterns → Phase D or E only

        Args:
            phase_info: Current phase information
            pattern_type: Pattern type ("SPRING", "SOS", "LPS")

        Returns:
            (is_valid, rejection_reason): Tuple of validation result and reason if invalid

        Example:
            >>> phase_info = detector.detect_phase(range, bars, volume_analysis)
            >>> is_valid, reason = detector.is_valid_for_pattern(phase_info, "SPRING")
            >>> if not is_valid:
            ...     print(f"Pattern rejected: {reason}")

        FR15 Context:
            Prevents false signals by ensuring patterns only detected in
            appropriate phases. Spring in Phase A would be premature, SOS
            in Phase B would be invalid breakout.
        """
        if phase_info.phase is None:
            return False, "No phase detected - cannot validate pattern"

        if pattern_type == "SPRING":
            if phase_info.phase == WyckoffPhase.C:
                return True, None
            else:
                return (
                    False,
                    f"Spring pattern requires Phase C, current phase is {phase_info.phase.value}",
                )

        elif pattern_type == "SOS":
            if phase_info.phase == WyckoffPhase.D:
                return True, None
            else:
                return (
                    False,
                    f"SOS pattern requires Phase D, current phase is {phase_info.phase.value}",
                )

        elif pattern_type == "LPS":
            if phase_info.phase in [WyckoffPhase.D, WyckoffPhase.E]:
                return True, None
            else:
                return (
                    False,
                    f"LPS pattern requires Phase D or E, current phase is {phase_info.phase.value}",
                )

        else:
            # Unknown pattern type - allow (conservative)
            return True, None

    def invalidate_cache(
        self, symbol: Optional[str] = None, timeframe: Optional[str] = None
    ) -> None:
        """
        Invalidate cache for specific symbol/timeframe or all cache.

        Args:
            symbol: Symbol to invalidate (None = all)
            timeframe: Timeframe to invalidate (None = all for symbol)

        Example:
            >>> detector.invalidate_cache("AAPL", "1d")  # Invalidate AAPL daily
            >>> detector.invalidate_cache("AAPL")  # Invalidate all AAPL timeframes
            >>> detector.invalidate_cache()  # Invalidate entire cache
        """
        if symbol is None:
            # Clear entire cache
            cache_count = len(self._cache)
            self._cache.clear()
            logger.info(
                "cache_invalidated_all",
                cached_entries_cleared=cache_count,
                message="Entire cache cleared",
            )
        elif timeframe is None:
            # Clear all timeframes for symbol
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{symbol}_")]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(
                "cache_invalidated_symbol",
                symbol=symbol,
                entries_cleared=len(keys_to_remove),
            )
        else:
            # Clear specific symbol/timeframe
            cache_key = f"{symbol}_{timeframe}"
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.info(
                    "cache_invalidated_specific",
                    symbol=symbol,
                    timeframe=timeframe,
                )

    # ============================================================================
    # Private Helper Methods
    # ============================================================================

    def _validate_inputs(self, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]) -> None:
        """Validate detect_phase inputs."""
        if not bars:
            raise ValueError("Bars list cannot be empty")

        if len(bars) != len(volume_analysis):
            raise ValueError(
                f"Bars and volume_analysis length mismatch: "
                f"{len(bars)} bars vs {len(volume_analysis)} volume_analysis"
            )

        if len(bars) < 20:
            logger.warning(
                "insufficient_bars_for_analysis",
                bars_count=len(bars),
                minimum_required=20,
                message="Need ≥20 bars for reliable phase detection",
            )

    def _check_cache(self, cache_key: str, bar_count: int) -> Optional[PhaseInfo]:
        """Check if cached result is still valid."""
        if cache_key not in self._cache:
            return None

        cached = self._cache[cache_key]

        # Cache is valid only if bar count unchanged
        if cached["bar_count"] == bar_count:
            return cached["phase_info"]

        # Bar count changed - cache invalid
        logger.debug(
            "cache_miss_bar_count_changed",
            cache_key=cache_key,
            cached_bar_count=cached["bar_count"],
            current_bar_count=bar_count,
        )
        return None

    def _update_cache(
        self, cache_key: str, phase_info: PhaseInfo, bar_count: int, phase_history: PhaseHistory
    ) -> None:
        """Update cache with latest phase info and history."""
        self._cache[cache_key] = {
            "bar_count": bar_count,
            "phase_info": phase_info,
            "phase_history": phase_history,  # Story 4.6 integration
            "timestamp": datetime.now(UTC),
        }

        logger.debug(
            "cache_updated",
            cache_key=cache_key,
            bar_count=bar_count,
            phase=phase_info.phase.value if phase_info.phase else None,
            transition_count=len(phase_history.transitions),
        )

    def _detect_all_events(
        self, bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]
    ) -> PhaseEvents:
        """
        Detect all Wyckoff events via pipeline (AC 3).

        Event Detection Order:
            1. Selling Climax (SC) - Story 4.1
            2. Automatic Rally (AR) if SC found - Story 4.2
            3. Secondary Tests (STs) if SC+AR found - Story 4.3
            4. Spring (Epic 5 - placeholder)
            5. Sign of Strength (SOS) (Epic 5 - placeholder)
            6. Last Point of Support (LPS) (Epic 5 - placeholder)

        Returns:
            PhaseEvents with all detected events
        """
        logger.debug("event_detection_pipeline_start", bars_count=len(bars))

        # Step 1: Detect Selling Climax (Story 4.1)
        sc = detect_selling_climax(bars, volume_analysis)

        if sc:
            logger.info(
                "event_detected_sc",
                timestamp=sc.bar["timestamp"],
                confidence=sc.confidence,
            )

        # Step 2: Detect Automatic Rally if SC found (Story 4.2)
        ar = None
        if sc:
            ar = detect_automatic_rally(bars, sc, volume_analysis)
            if ar:
                logger.info(
                    "event_detected_ar",
                    timestamp=ar.bar["timestamp"],
                    rally_pct=float(ar.rally_pct),
                )

        # Step 3: Detect all Secondary Tests if SC+AR found (Story 4.3)
        st_list = []
        if sc and ar:
            # Detect multiple STs
            existing_sts = []
            for attempt in range(10):  # Max 10 STs (safety limit)
                st = detect_secondary_test(bars, sc, ar, volume_analysis, existing_sts)
                if st is None:
                    break  # No more STs found
                st_list.append(st)
                existing_sts.append(st)
                logger.info(
                    "event_detected_st",
                    test_number=st.test_number,
                    timestamp=st.bar["timestamp"],
                    confidence=st.confidence,
                )

        # Step 4-6: Placeholders for Epic 5 events
        spring = None  # TODO: Epic 5 - Spring detection
        sos = None  # TODO: Epic 5 - SOS detection
        lps = None  # TODO: Epic 5 - LPS detection

        # Create PhaseEvents directly (Story 4.8 - bar_index now in models)
        events = self._create_phase_events(
            sc=sc, ar=ar, st_list=st_list, spring=spring, sos=sos, lps=lps
        )

        logger.debug(
            "event_detection_pipeline_complete",
            has_sc=sc is not None,
            has_ar=ar is not None,
            st_count=len(st_list),
        )

        return events

    def _create_phase_events(
        self,
        sc,
        ar,
        st_list: list,
        spring,
        sos,
        lps,
    ) -> PhaseEvents:
        """
        Create PhaseEvents from detected event models.

        Story 4.8: Clean pipeline - event models now include bar_index natively.
        No adapter pattern or index injection needed.

        Args:
            sc: SellingClimax object or None
            ar: AutomaticRally object or None
            st_list: List of SecondaryTest objects
            spring: Spring object or None (Epic 5)
            sos: SOS object or None (Epic 5)
            lps: LPS object or None (Epic 5)

        Returns:
            PhaseEvents with all event data including bar_index
        """
        # Serialize events to dicts (bar_index preserved via model_dump)
        sc_dict = sc.model_dump() if sc else None
        ar_dict = ar.model_dump() if ar else None
        st_dicts = [st.model_dump() for st in st_list]

        # Create PhaseEvents with serialized dicts
        events = PhaseEvents(
            selling_climax=sc_dict,
            automatic_rally=ar_dict,
            secondary_tests=st_dicts,
            spring=spring,
            sos_breakout=sos,
            last_point_of_support=lps,
        )

        logger.debug(
            "phase_events_created",
            sc_index=sc_dict["bar_index"] if sc_dict else None,
            ar_index=ar_dict["bar_index"] if ar_dict else None,
            st_count=len(st_dicts),
            message="PhaseEvents created with native bar_index from models",
        )

        return events

    def _create_phase_info(
        self,
        phase_classification,
        events: PhaseEvents,
        confidence: int,
        trading_range: Optional[TradingRange],
        bars: list[OHLCVBar],
        # Phase 2 enhancement parameters
        invalidation: Optional["PhaseInvalidation"] = None,
        confirmation: Optional["PhaseConfirmation"] = None,
        breakdown_type: Optional["BreakdownType"] = None,
        breakdown_risk_profile: Optional["BreakdownRiskProfile"] = None,
        phase_b_context: Optional[str] = None,
        phase_b_risk_profile: Optional["PhaseBRiskProfile"] = None,
        sub_phase: Optional[Union["PhaseCSubState", "PhaseESubState"]] = None,
        phase_e_risk_profile: Optional["PhaseESubStateRiskProfile"] = None,
        lps_count: int = 0,
        markup_slope: Optional["Decimal"] = None,
        # Story 4.6 integration
        phase_history: Optional[PhaseHistory] = None,
    ) -> PhaseInfo:
        """
        Create comprehensive PhaseInfo with all fields.

        This assembles the complete phase detection result including:
        - Core phase/confidence/duration
        - Event tracking
        - Progression history (basic for now, enhanced in Phase 2)
        - Risk management fields (Phase 2 enhancements)
        """
        current_bar_index = len(bars) - 1
        current_bar = bars[current_bar_index]

        # Determine phase start index (simplified for Phase 1)
        # In Phase 2, this will use progression tracking
        phase_start_index = 0
        if events.selling_climax:
            # Get SC bar index from event model (Story 4.8)
            phase_start_index = events.selling_climax["bar_index"]

        duration = current_bar_index - phase_start_index

        # Convert Story 4.6 transitions to PhaseInfo transitions
        from src.models.phase_info import PhaseTransition

        progression_history = []
        if phase_history:
            for story46_transition in phase_history.transitions:
                progression_history.append(
                    PhaseTransition(
                        from_phase=story46_transition.from_phase,
                        to_phase=story46_transition.to_phase,
                        timestamp=story46_transition.timestamp,
                        bar_index=story46_transition.bar_index,
                        trigger_event=story46_transition.reason,
                        confidence=confidence,  # Use current confidence
                    )
                )

        # Create PhaseInfo with Phase 2 enhancements
        phase_info = PhaseInfo(
            # Core fields
            phase=phase_classification.phase,
            sub_phase=sub_phase,  # Phase 2 - sub-phase state machine
            confidence=confidence,
            events=events,
            duration=duration,
            progression_history=progression_history,  # Story 4.6 integration
            trading_range=trading_range,
            phase_start_bar_index=phase_start_index,
            current_bar_index=current_bar_index,
            last_updated=datetime.now(UTC),
            # Enhancement fields (Phase 2)
            invalidations=[invalidation] if invalidation else [],
            confirmations=[confirmation] if confirmation else [],
            breakdown_type=breakdown_type,
            phase_b_duration_context=phase_b_context,
            lps_count=lps_count,
            markup_slope=float(markup_slope) if markup_slope else None,
            # Risk management fields (Phase 2)
            current_risk_level=self._determine_risk_level(phase_classification.phase, invalidation),
            position_action_required=self._determine_position_action(invalidation),
            recommended_stop_level=self._calculate_stop_level(
                trading_range, phase_classification.phase
            ),
            risk_rationale=self._generate_risk_rationale(invalidation, confirmation),
            phase_b_risk_profile=phase_b_risk_profile,  # Task 39: ✅ Complete
            breakdown_risk_profile=breakdown_risk_profile,  # Task 38: ✅ Complete
            phase_e_risk_profile=phase_e_risk_profile,  # Task 40: ✅ Complete
        )

        return phase_info

    def _determine_risk_level(self, phase, invalidation) -> str:
        """Determine current risk level based on phase and invalidations."""
        if invalidation:
            return invalidation.risk_level
        if phase == WyckoffPhase.A:
            return "elevated"  # Still in stopping action
        if phase == WyckoffPhase.B:
            return "normal"  # Building cause
        return "normal"

    def _determine_position_action(self, invalidation) -> str:
        """Determine required position action."""
        if invalidation:
            return invalidation.position_action
        return "none"

    def _calculate_stop_level(self, trading_range, phase) -> Optional[float]:
        """Calculate structural stop level."""
        if not trading_range:
            return None
        # Use Creek (support) as stop level
        return float(
            trading_range.creek.price
            if hasattr(trading_range.creek, "price")
            else trading_range.support
        )

    def _generate_risk_rationale(self, invalidation, confirmation) -> Optional[str]:
        """Generate risk rationale explanation."""
        if invalidation:
            return invalidation.rationale
        if confirmation:
            return f"Phase confirmed: {confirmation.confirmation_reason}"
        return None

    def _get_or_create_phase_history(
        self, cache_key: str, trading_range: TradingRange
    ) -> PhaseHistory:
        """
        Get existing PhaseHistory from cache or create new one.

        Args:
            cache_key: Cache key for this symbol/timeframe
            trading_range: Associated trading range

        Returns:
            PhaseHistory instance
        """
        if cache_key in self._cache and "phase_history" in self._cache[cache_key]:
            return self._cache[cache_key]["phase_history"]

        # Create new PhaseHistory
        import uuid

        phase_history = PhaseHistory(
            transitions=[],
            current_phase=None,
            range_id=uuid.uuid4(),  # Use trading range ID if available
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        logger.info(
            "phase_history_created", cache_key=cache_key, range_id=str(phase_history.range_id)
        )

        return phase_history

    def _validate_and_update_progression(
        self,
        phase_history: PhaseHistory,
        new_classification,
        invalidation,
        confirmation,
        breakdown_type,
        phase_b_context: Optional[str],
        current_bar_index: int,
        bars: list[OHLCVBar],
    ) -> tuple[Optional[WyckoffPhase], PhaseHistory]:
        """
        Validate phase progression using Story 4.6 and update history.

        Integration Logic:
            - Phase invalidation: Bypass Story 4.6, directly update phase
            - Phase confirmation: Bypass Story 4.6, no phase change
            - Normal transition: Call Story 4.6 enforce_phase_progression

        Args:
            phase_history: Current phase history
            new_classification: New phase classification from Story 4.4
            invalidation: Phase invalidation if detected
            confirmation: Phase confirmation if detected
            breakdown_type: Breakdown classification if applicable
            phase_b_context: Phase B duration context
            current_bar_index: Current bar index
            bars: Bar sequence

        Returns:
            Tuple of (validated_phase, updated_history)
        """
        # Handle phase invalidation (bypass Story 4.6)
        if invalidation:
            logger.warning(
                "phase_invalidation_bypass_story46",
                invalidated_phase=invalidation.phase_invalidated.value,
                reverted_to=invalidation.reverted_to_phase.value
                if invalidation.reverted_to_phase
                else None,
                reason=invalidation.invalidation_reason,
            )
            # Directly update to reverted phase
            phase_history.current_phase = invalidation.reverted_to_phase
            phase_history.updated_at = datetime.now(UTC)
            return invalidation.reverted_to_phase, phase_history

        # Handle phase confirmation (bypass Story 4.6, no transition)
        if confirmation:
            logger.info(
                "phase_confirmation_no_transition",
                confirmed_phase=confirmation.phase_confirmed.value,
                reason=confirmation.confirmation_reason,
            )
            # No phase change on confirmation
            return phase_history.current_phase, phase_history

        # Normal transition - validate with Story 4.6
        context = {
            "bar_index": current_bar_index,
            "reason": self._get_transition_reason(new_classification, bars),
            "correlation_id": str(uuid.uuid4()),
            # Phase 2 enhancement contexts
            "phase_a_reset": invalidation and invalidation.invalidation_type == "new_evidence",
            "stronger_climax_detected": confirmation
            and confirmation.confirmation_type == "stronger_climax",
            "spring_test_detected": confirmation
            and confirmation.confirmation_type == "spring_test",
            "new_range_detected": False,  # TODO: Implement range detection
            "range_breakdown": breakdown_type is not None,
            "breakdown_type": breakdown_type.value if breakdown_type else None,
            "phase_b_duration": new_classification.duration
            if new_classification.phase == WyckoffPhase.B
            else None,
            "phase_b_context": phase_b_context,
        }

        # Call Story 4.6 validation
        accepted, updated_history, rejection_reason = enforce_phase_progression(
            history=phase_history, new_classification=new_classification, context=context
        )

        if accepted:
            logger.info(
                "phase_transition_accepted",
                from_phase=phase_history.current_phase.value
                if phase_history.current_phase
                else "None",
                to_phase=new_classification.phase.value if new_classification.phase else "None",
                reason=context["reason"],
            )
            return new_classification.phase, updated_history
        else:
            logger.warning(
                "phase_transition_rejected",
                from_phase=phase_history.current_phase.value
                if phase_history.current_phase
                else "None",
                attempted_to_phase=new_classification.phase.value
                if new_classification.phase
                else "None",
                rejection_reason=rejection_reason,
            )
            # Keep current phase
            return phase_history.current_phase, phase_history

    def _get_transition_reason(self, classification, bars: list[OHLCVBar]) -> str:
        """Generate transition reason based on classification."""
        if not classification.phase:
            return "Breakdown below support"

        phase_events = (
            classification.events_detected if hasattr(classification, "events_detected") else None
        )

        if classification.phase == WyckoffPhase.A:
            return "Selling Climax detected"
        elif classification.phase == WyckoffPhase.B:
            return "Secondary Test detected, building cause"
        elif classification.phase == WyckoffPhase.C:
            return "Spring detected, testing support"
        elif classification.phase == WyckoffPhase.D:
            return "Sign of Strength breakout"
        elif classification.phase == WyckoffPhase.E:
            return "Markup continuation"
        else:
            return "Phase transition"


# ============================================================================
# Standalone Helper Functions (for backward compatibility)
# ============================================================================


def get_current_phase(phase_info: PhaseInfo) -> Optional[WyckoffPhase]:
    """
    Get current Wyckoff phase from PhaseInfo.

    Args:
        phase_info: PhaseInfo result

    Returns:
        Current phase or None

    Example:
        >>> phase = get_current_phase(phase_info)
        >>> if phase == WyckoffPhase.C:
        ...     # Look for Spring patterns
    """
    return phase_info.phase


def is_trading_allowed(phase_info: PhaseInfo) -> bool:
    """
    Check if trading is allowed based on phase (FR14 enforcement).

    This is a convenience wrapper around PhaseInfo.is_trading_allowed().

    Args:
        phase_info: PhaseInfo result

    Returns:
        True if trading allowed, False otherwise

    Example:
        >>> if is_trading_allowed(phase_info):
        ...     signal = generate_signal(phase_info)
    """
    return phase_info.is_trading_allowed()


def get_phase_description(phase: WyckoffPhase) -> str:
    """
    Get human-readable description of Wyckoff phase.

    Args:
        phase: Wyckoff phase

    Returns:
        Description string

    Example:
        >>> desc = get_phase_description(WyckoffPhase.C)
        >>> print(desc)  # "Phase C: Test (Spring - final shakeout)"
    """
    descriptions = {
        WyckoffPhase.A: "Phase A: Stopping Action (SC + AR + ST)",
        WyckoffPhase.B: "Phase B: Building Cause (ST oscillation, 10-40 bars)",
        WyckoffPhase.C: "Phase C: Test (Spring - final shakeout)",
        WyckoffPhase.D: "Phase D: Sign of Strength (SOS breakout above Ice)",
        WyckoffPhase.E: "Phase E: Markup (sustained trend above Ice)",
    }
    return descriptions.get(phase, "Unknown phase")


# ============================================================================
# Phase 2 Enhancements - Wayne's Advanced Detection Logic
# ============================================================================


def _check_phase_invalidation(
    current_phase: Optional[WyckoffPhase],
    bars: list[OHLCVBar],
    events: "PhaseEvents",
    trading_range: Optional["TradingRange"],
    previous_invalidations: list["PhaseInvalidation"],
) -> Optional["PhaseInvalidation"]:
    """
    Detect phase invalidations (AC 11-14).

    Checks for:
    - Failed SOS: Phase D → C reversion when price breaks below Ice
    - Weak Spring: Phase C → B reversion when Spring fails to hold
    - Stronger Climax: Phase A reset when new higher-volume SC detected

    Args:
        current_phase: Current phase classification
        bars: OHLCV bar data
        events: Detected Wyckoff events
        trading_range: Associated trading range
        previous_invalidations: Previous invalidation history

    Returns:
        PhaseInvalidation if invalidation detected, None otherwise

    Example:
        >>> # Failed SOS scenario
        >>> invalidation = _check_phase_invalidation(
        ...     current_phase=WyckoffPhase.D,
        ...     bars=bars_with_breakdown,
        ...     events=events_with_sos,
        ...     trading_range=range,
        ...     previous_invalidations=[]
        ... )
        >>> if invalidation:
        ...     print(f"Phase {invalidation.phase_invalidated} invalidated: {invalidation.invalidation_reason}")
    """
    from decimal import Decimal

    from src.models.phase_info import PhaseInvalidation

    if not current_phase or not bars or not trading_range:
        return None

    current_bar = bars[-1]
    current_bar_index = len(bars) - 1

    # AC 11: Failed SOS - Phase D → C reversion
    if current_phase == WyckoffPhase.D and events.sos_breakout is not None:
        # Check if price has fallen below Ice after SOS breakout
        ice_price = Decimal(
            str(
                trading_range.ice.price
                if hasattr(trading_range.ice, "price")
                else trading_range.resistance
            )
        )
        current_low = Decimal(str(current_bar.low))

        if current_low < ice_price:
            logger.warning(
                "phase_d_invalidation_detected",
                reason="Failed SOS - price fell below Ice",
                current_low=float(current_low),
                ice_price=float(ice_price),
                bar_index=current_bar_index,
            )

            return PhaseInvalidation(
                phase_invalidated=WyckoffPhase.D,
                invalidation_reason="Failed SOS - price fell below Ice after breakout",
                bar_index=current_bar_index,
                timestamp=current_bar.timestamp,
                invalidation_type="failed_event",
                reverted_to_phase=WyckoffPhase.C,
                risk_level="high",
                position_action="exit_all",
                new_stop_level=None,
                risk_reason="SOS breakout failed, pattern still testing (Phase C)",
            )

    # AC 12: Weak Spring - Phase C → B reversion
    if current_phase == WyckoffPhase.C and events.spring is not None:
        # Check if Spring has failed to hold above Creek for 3+ bars
        # Spring should maintain support - if it breaks down, accumulation failed
        creek_price = Decimal(
            str(
                trading_range.creek.price
                if hasattr(trading_range.creek, "price")
                else trading_range.support
            )
        )

        # Count bars since Spring detection (placeholder - Epic 5 will provide Spring bar index)
        # For now, check last 3 bars
        bars_below_creek = 0
        for bar in bars[-3:]:
            if Decimal(str(bar.low)) < creek_price:
                bars_below_creek += 1

        if bars_below_creek >= 3:
            logger.warning(
                "phase_c_invalidation_detected",
                reason="Weak Spring failed to hold above Creek",
                bars_below_creek=bars_below_creek,
                creek_price=float(creek_price),
                bar_index=current_bar_index,
            )

            return PhaseInvalidation(
                phase_invalidated=WyckoffPhase.C,
                invalidation_reason="Weak Spring failed to hold above Creek for 3+ bars",
                bar_index=current_bar_index,
                timestamp=current_bar.timestamp,
                invalidation_type="failed_event",
                reverted_to_phase=WyckoffPhase.B,
                risk_level="elevated",
                position_action="reduce",
                new_stop_level=float(creek_price),
                risk_reason="Spring test failed, continue building cause (Phase B)",
            )

    # AC 14: Stronger Climax - Phase A reset (new evidence, not reversion)
    if current_phase == WyckoffPhase.A and events.selling_climax is not None:
        # Check if we already have an SC and a new one with higher volume is detected
        # This would mean Phase A is resetting with stronger evidence

        # Check if there are multiple SCs in recent history by comparing current SC volume
        # to previous bars (placeholder - full implementation needs SC history tracking)
        sc_volume_ratio = Decimal(str(events.selling_climax.get("volume_ratio", 1.0)))

        # If we have previous invalidations of type "new_evidence" in Phase A,
        # this might be another stronger climax
        recent_phase_a_resets = [
            inv
            for inv in previous_invalidations
            if inv.phase_invalidated == WyckoffPhase.A
            and inv.invalidation_type == "new_evidence"
            and current_bar_index - inv.bar_index < 10
        ]

        # If we detect a very strong SC (volume ratio > 3.0) and we're already in Phase A,
        # this might be a stronger climax (simplified logic for Phase 1)
        if sc_volume_ratio > Decimal("3.0") and len(recent_phase_a_resets) == 0:
            logger.info(
                "phase_a_reset_detected",
                reason="Stronger climax detected",
                new_sc_volume_ratio=float(sc_volume_ratio),
                bar_index=current_bar_index,
            )

            return PhaseInvalidation(
                phase_invalidated=WyckoffPhase.A,
                invalidation_reason="Stronger climax detected - Phase A reset",
                bar_index=current_bar_index,
                timestamp=current_bar.timestamp,
                invalidation_type="new_evidence",
                reverted_to_phase=WyckoffPhase.A,  # Stay in Phase A, but reset start
                risk_level="elevated",
                position_action="hold",
                new_stop_level=float(Decimal(str(current_bar.low)) * Decimal("0.98")),
                risk_reason="New stronger climax resets Phase A accumulation start",
            )

    return None


def _check_phase_confirmation(
    current_phase: Optional[WyckoffPhase],
    bars: list[OHLCVBar],
    events: "PhaseEvents",
    trading_range: Optional["TradingRange"],
    previous_confirmations: list["PhaseConfirmation"],
    phase_start_index: int,
) -> Optional["PhaseConfirmation"]:
    """
    Detect phase confirmations (AC 15-18).

    Checks for:
    - Phase A confirmation: Multiple SC/AR events within same Phase A
    - Phase C confirmation: Spring → Test of Spring progression
    - Phase B confirmation: Additional Secondary Tests detected

    Args:
        current_phase: Current phase classification
        bars: OHLCV bar data
        events: Detected Wyckoff events
        trading_range: Associated trading range
        previous_confirmations: Previous confirmation history
        phase_start_index: Index where current phase started

    Returns:
        PhaseConfirmation if confirmation detected, None otherwise

    Example:
        >>> confirmation = _check_phase_confirmation(
        ...     current_phase=WyckoffPhase.A,
        ...     bars=bars,
        ...     events=events_with_multiple_scs,
        ...     trading_range=range,
        ...     previous_confirmations=[],
        ...     phase_start_index=20
        ... )
        >>> if confirmation:
        ...     print(f"Phase {confirmation.phase_confirmed} confirmed: {confirmation.confirmation_reason}")
    """
    from decimal import Decimal

    from src.models.phase_info import PhaseConfirmation

    if not current_phase or not bars:
        return None

    current_bar = bars[-1]
    current_bar_index = len(bars) - 1

    # AC 15: Phase A confirmation - Multiple SC/AR events
    if current_phase == WyckoffPhase.A and events.selling_climax is not None:
        # Check if this is NOT the first SC in this Phase A
        # Look for previous Phase A confirmations of type "stronger_climax"
        previous_sc_confirmations = [
            conf
            for conf in previous_confirmations
            if conf.phase_confirmed == WyckoffPhase.A
            and conf.confirmation_type == "stronger_climax"
            and conf.bar_index >= phase_start_index
        ]

        # If we have SC data and we're well into Phase A (not just starting),
        # this might be confirmation rather than the initial detection
        bars_in_phase_a = current_bar_index - phase_start_index

        if bars_in_phase_a > 5 and len(previous_sc_confirmations) == 0:
            # This is additional climax evidence confirming Phase A
            logger.info(
                "phase_a_confirmation_detected",
                reason="Additional climax evidence",
                bars_in_phase_a=bars_in_phase_a,
                bar_index=current_bar_index,
            )

            return PhaseConfirmation(
                phase_confirmed=WyckoffPhase.A,
                confirmation_reason="Additional SC/AR evidence confirms Phase A accumulation",
                bar_index=current_bar_index,
                timestamp=current_bar.timestamp,
                confirmation_type="stronger_climax",
                confidence_boost=5,
                context={"stronger_climax_detected": True, "bars_in_phase_a": bars_in_phase_a},
            )

    # AC 16: Phase C confirmation - Spring → Test of Spring
    if current_phase == WyckoffPhase.C and events.spring is not None and trading_range:
        # Detect Test of Spring: price returns to Spring low within 5 bars
        # Spring low should be near Creek (support level)
        creek_price = Decimal(
            str(
                trading_range.creek.price
                if hasattr(trading_range.creek, "price")
                else trading_range.support
            )
        )

        # Check recent bars for a test of Spring low
        # Test of Spring = price comes back down to Spring area without breaking lower
        recent_bars = bars[-5:] if len(bars) >= 5 else bars
        tested_spring = False
        test_bar_index = None

        for i, bar in enumerate(recent_bars):
            bar_low = Decimal(str(bar.low))
            # Check if bar tested Spring area (within 2% of Creek)
            if abs(bar_low - creek_price) / creek_price <= Decimal("0.02"):
                # Check if it held (didn't break significantly lower)
                if bar_low >= creek_price * Decimal("0.98"):
                    tested_spring = True
                    test_bar_index = current_bar_index - len(recent_bars) + i + 1
                    break

        # Check we haven't already logged this Spring test
        previous_spring_tests = [
            conf
            for conf in previous_confirmations
            if conf.phase_confirmed == WyckoffPhase.C
            and conf.confirmation_type == "spring_test"
            and conf.bar_index >= phase_start_index
        ]

        if tested_spring and len(previous_spring_tests) == 0:
            logger.info(
                "phase_c_confirmation_detected",
                reason="Test of Spring detected",
                test_bar_index=test_bar_index,
                creek_price=float(creek_price),
                bar_index=current_bar_index,
            )

            return PhaseConfirmation(
                phase_confirmed=WyckoffPhase.C,
                confirmation_reason="Test of Spring confirms accumulation readiness",
                bar_index=test_bar_index or current_bar_index,
                timestamp=bars[test_bar_index].timestamp
                if test_bar_index
                else current_bar.timestamp,
                confirmation_type="spring_test",
                confidence_boost=10,
                context={"spring_test_detected": True, "test_held_above_creek": True},
            )

    # AC 18: Phase B confirmation - Additional Secondary Tests
    if current_phase == WyckoffPhase.B and len(events.secondary_tests) > 0:
        # Count how many ST confirmations we've already logged
        previous_st_confirmations = [
            conf
            for conf in previous_confirmations
            if conf.phase_confirmed == WyckoffPhase.B
            and conf.confirmation_type == "additional_st"
            and conf.bar_index >= phase_start_index
        ]

        # If we have more STs than confirmations, we have new ST evidence
        if len(events.secondary_tests) > len(previous_st_confirmations):
            logger.info(
                "phase_b_confirmation_detected",
                reason="Additional Secondary Test detected",
                st_count=len(events.secondary_tests),
                previous_confirmations=len(previous_st_confirmations),
                bar_index=current_bar_index,
            )

            return PhaseConfirmation(
                phase_confirmed=WyckoffPhase.B,
                confirmation_reason=f"Additional ST detected (total: {len(events.secondary_tests)})",
                bar_index=current_bar_index,
                timestamp=current_bar.timestamp,
                confirmation_type="additional_st",
                confidence_boost=5,
                context={"total_st_count": len(events.secondary_tests), "cause_building": True},
            )

    return None


def _classify_breakdown(
    bars: list[OHLCVBar],
    volume_analysis: list[VolumeAnalysis],
    events: "PhaseEvents",
    previous_phase: Optional[WyckoffPhase],
    trading_range: Optional["TradingRange"],
) -> Optional["BreakdownType"]:
    """
    Classify breakdown type when accumulation fails (AC 23-26).

    Distinguishes between:
    - Failed Accumulation: Low volume breakdown, weak demand
    - Distribution Pattern: High volume breakdown, institutional selling
    - UTAD Reversal: Upthrust After Distribution disguised as accumulation

    Args:
        bars: OHLCV bar data
        volume_analysis: Volume analysis for breakdown detection
        events: Detected Wyckoff events
        previous_phase: Phase before breakdown (typically C)
        trading_range: Associated trading range

    Returns:
        BreakdownType classification or None if no breakdown

    Example:
        >>> breakdown_type = _classify_breakdown(
        ...     bars=bars_with_breakdown,
        ...     volume_analysis=volume_analysis,
        ...     events=events,
        ...     previous_phase=WyckoffPhase.C,
        ...     trading_range=range
        ... )
        >>> if breakdown_type:
        ...     print(f"Breakdown type: {breakdown_type.value}")
    """
    from decimal import Decimal

    from src.models.phase_info import BreakdownType

    if not bars or not volume_analysis or not trading_range:
        return None

    # Check if we actually have a breakdown (price below Creek/support)
    current_bar = bars[-1]
    creek_price = Decimal(
        str(
            trading_range.creek.price
            if hasattr(trading_range.creek, "price")
            else trading_range.support
        )
    )
    current_low = Decimal(str(current_bar.low))

    if current_low >= creek_price:
        # Not a breakdown, price still above support
        return None

    # Get breakdown bar volume analysis
    breakdown_volume = volume_analysis[-1] if volume_analysis else None
    if not breakdown_volume:
        logger.warning(
            "breakdown_classification_no_volume", message="No volume data for breakdown bar"
        )
        return BreakdownType.FAILED_ACCUMULATION  # Default to failed accumulation

    # AC 24: Analyze volume on breakdown
    breakdown_volume_ratio = breakdown_volume.volume_ratio

    logger.info(
        "breakdown_classification_start",
        previous_phase=previous_phase.value if previous_phase else None,
        breakdown_volume_ratio=float(breakdown_volume_ratio),
        current_low=float(current_low),
        creek_price=float(creek_price),
    )

    # High volume breakdown (>1.5x average) suggests distribution or UTAD
    if breakdown_volume_ratio > Decimal("1.5"):
        # AC 26: Check for UTAD pattern
        # UTAD characteristics:
        # 1. What looked like accumulation (SC, AR, ST pattern)
        # 2. But was actually distribution in disguise
        # 3. High volume on breakdown confirms selling pressure
        # 4. Previous "SC" might have been selling climax in distribution

        # Check if the pattern shows UTAD characteristics:
        # - Phase C Spring may have been an upthrust (false breakout UP then reversal)
        # - High volume throughout what looked like Phase B
        # - Strong selling on breakdown

        utad_indicators = 0

        # Indicator 1: Spring exists but breakdown volume > Spring volume (unusual)
        if events.spring is not None:
            # In true accumulation, breakdown should be low volume
            # In UTAD, breakdown has high volume (selling climax)
            utad_indicators += 1

        # Indicator 2: Check if earlier STs had high volume (distribution characteristic)
        if len(events.secondary_tests) > 0:
            high_volume_sts = sum(
                1 for st in events.secondary_tests if st.get("volume_ratio", 1.0) > 1.3
            )
            if high_volume_sts >= len(events.secondary_tests) * 0.5:  # 50%+ high volume
                utad_indicators += 1

        # Indicator 3: Breakdown volume significantly higher than average (>2.0x)
        if breakdown_volume_ratio > Decimal("2.0"):
            utad_indicators += 1

        # If we have 2+ UTAD indicators, classify as UTAD
        if utad_indicators >= 2:
            logger.warning(
                "breakdown_classified_utad",
                utad_indicators=utad_indicators,
                breakdown_volume_ratio=float(breakdown_volume_ratio),
                message="Pattern was distribution disguised as accumulation",
            )
            return BreakdownType.UTAD_REVERSAL

        # Otherwise, high volume breakdown is distribution
        logger.warning(
            "breakdown_classified_distribution",
            breakdown_volume_ratio=float(breakdown_volume_ratio),
            message="High volume institutional selling",
        )
        return BreakdownType.DISTRIBUTION_PATTERN

    else:
        # AC 23: Low volume breakdown = Failed Accumulation
        # Weak demand, accumulation did not build sufficient cause
        logger.warning(
            "breakdown_classified_failed_accumulation",
            breakdown_volume_ratio=float(breakdown_volume_ratio),
            message="Low volume weak demand failure",
        )
        return BreakdownType.FAILED_ACCUMULATION


def _get_breakdown_risk_profile(
    breakdown_type: "BreakdownType", bars: list[OHLCVBar], trading_range: Optional["TradingRange"]
) -> "BreakdownRiskProfile":
    """
    Create risk profile for breakdown scenarios (Task 38).

    Stop Placement Rules:
        - FAILED_ACCUMULATION: 1% below breakdown low, reduce 50%
        - DISTRIBUTION_PATTERN: 2% below Creek, exit all
        - UTAD_REVERSAL: 2% below current low, exit all

    Args:
        breakdown_type: Classification from _classify_breakdown
        bars: OHLCV bar data
        trading_range: Associated trading range

    Returns:
        BreakdownRiskProfile with stop placement and position action

    Example:
        >>> profile = _get_breakdown_risk_profile(
        ...     breakdown_type=BreakdownType.FAILED_ACCUMULATION,
        ...     bars=bars,
        ...     trading_range=range
        ... )
        >>> print(f"Stop: {profile.stop_placement}")
        >>> print(f"Action: {profile.position_action}")
    """

    from src.models.phase_info import BreakdownRiskProfile

    current_low = float(bars[-1].low)

    # Get Creek price for reference
    creek_price = float(
        trading_range.creek.price
        if trading_range and hasattr(trading_range.creek, "price")
        else current_low
    )

    if breakdown_type.value == "failed_accumulation":
        # AC 36: Failed accumulation - 1% below low, reduce 50%, medium risk
        return BreakdownRiskProfile(
            breakdown_type=breakdown_type,
            stop_placement=current_low * 0.99,  # 1% below breakdown low
            stop_rationale=("Failed accumulation on low volume - weak demand but may stabilize"),
            position_action="reduce_50",
            risk_level="medium",
            reentry_guidance=(
                "Wait for new accumulation cycle with stronger Spring (confidence >85)"
            ),
        )

    elif breakdown_type.value == "distribution_pattern":
        # AC 36: Distribution - 2% below Creek, exit all, critical risk
        return BreakdownRiskProfile(
            breakdown_type=breakdown_type,
            stop_placement=creek_price * 0.98,  # 2% below Creek
            stop_rationale=("High volume breakdown indicates institutional selling"),
            position_action="exit_all",
            risk_level="critical",
            reentry_guidance=("Pattern invalidated - wait for new trading range formation"),
        )

    else:  # UTAD_REVERSAL
        # AC 36: UTAD - 2% below current, exit all, critical risk
        return BreakdownRiskProfile(
            breakdown_type=breakdown_type,
            stop_placement=current_low * 0.98,  # 2% below current low
            stop_rationale=(
                "UTAD detected - Composite Operator distributed while faking accumulation"
            ),
            position_action="exit_all",
            risk_level="critical",
            reentry_guidance=("Avoid this asset - Composite Operator deception confirmed"),
        )


def _validate_phase_b_duration(
    phase: Optional[WyckoffPhase],
    duration: int,
    events: "PhaseEvents",
    bars: list[OHLCVBar],
    volume_analysis: list[VolumeAnalysis],
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate Phase B duration with context-aware minimums (AC 27-30).

    Phase B duration rules:
    - Base accumulation: minimum 10 bars
    - Reaccumulation: minimum 5 bars (after previous accumulation)
    - Volatile assets: minimum 8 bars
    - Override allowed: exceptional Spring strength (>85) + 2+ STs

    Args:
        phase: Current phase
        duration: Bars in current phase
        events: Detected Wyckoff events
        bars: OHLCV bar data
        volume_analysis: Volume analysis

    Returns:
        Tuple of (is_valid, warning_message, context_type)

    Example:
        >>> valid, warning, context = _validate_phase_b_duration(
        ...     phase=WyckoffPhase.B,
        ...     duration=7,
        ...     events=events,
        ...     bars=bars,
        ...     volume_analysis=volume_analysis
        ... )
        >>> if not valid:
        ...     print(f"Warning: {warning}")
    """
    from decimal import Decimal

    if phase != WyckoffPhase.B:
        return (True, None, None)

    # AC 28: Determine accumulation context
    # Check if this is reaccumulation (would need historical phase data)
    # For Phase 1, default to base_accumulation
    # Phase 2 will track previous accumulations
    context_type = "base_accumulation"  # Default
    minimum_duration = 10  # Base accumulation minimum

    # AC 28: Adjust for reaccumulation (placeholder for Phase 2)
    # In real implementation, would check:
    # - Was there a previous Phase E that completed successfully?
    # - Is this a pullback/consolidation before continuation?
    # if is_reaccumulation:
    #     context_type = "reaccumulation"
    #     minimum_duration = 5

    # AC 30: Adjust for asset volatility
    # Calculate volatility from recent bars
    if len(bars) >= 20:
        recent_bars = bars[-20:]
        price_changes = [
            abs(Decimal(str(recent_bars[i].close)) - Decimal(str(recent_bars[i - 1].close)))
            / Decimal(str(recent_bars[i - 1].close))
            for i in range(1, len(recent_bars))
        ]
        avg_volatility = sum(price_changes) / len(price_changes)

        # If volatility > 3%, consider volatile asset
        if avg_volatility > Decimal("0.03"):
            context_type = "volatile"
            minimum_duration = 8
            logger.debug(
                "phase_b_duration_volatile_adjustment",
                avg_volatility=float(avg_volatility),
                adjusted_minimum=minimum_duration,
            )

    # Check if duration meets minimum
    if duration < minimum_duration:
        # AC 29: Check for override conditions
        # Exceptional evidence can override minimum:
        # 1. Spring strength > 85 (very strong Spring)
        # 2. ST count >= 2 (adequate cause building)

        override_allowed = False
        override_reason = None

        if events.spring is not None:
            spring_confidence = (
                events.spring.get("confidence", 0) if isinstance(events.spring, dict) else 0
            )
            st_count = len(events.secondary_tests)

            if spring_confidence > 85 and st_count >= 2:
                override_allowed = True
                override_reason = (
                    f"Exceptional evidence: Spring confidence {spring_confidence}, {st_count} STs"
                )
                logger.info(
                    "phase_b_duration_override_approved",
                    duration=duration,
                    minimum=minimum_duration,
                    spring_confidence=spring_confidence,
                    st_count=st_count,
                )

        if not override_allowed:
            warning = (
                f"Phase B duration {duration} bars < minimum {minimum_duration} for {context_type}"
            )
            logger.warning(
                "phase_b_duration_warning",
                duration=duration,
                minimum=minimum_duration,
                context=context_type,
                message=warning,
            )
            return (False, warning, context_type)

    # Duration is valid
    logger.debug(
        "phase_b_duration_valid", duration=duration, minimum=minimum_duration, context=context_type
    )
    return (True, None, context_type)


def _get_phase_b_risk_profile(
    duration: int, context: str, minimum_duration: int, has_exceptional_evidence: bool
) -> "PhaseBRiskProfile":
    """
    Create Phase B risk profile based on duration validation (Task 39).

    Risk Adjustment Rules:
        - Normal duration (≥minimum): 1.0x (full position size)
        - Short with exceptional evidence: 0.75x (reduce 25%)
        - Very short: 0.5x (reduce 50%)

    Args:
        duration: Actual Phase B duration in bars
        context: Accumulation context (base/reaccumulation/volatile)
        minimum_duration: Required minimum for this context
        has_exceptional_evidence: Spring >85 + ST >=2

    Returns:
        PhaseBRiskProfile with position size adjustment

    Example:
        >>> profile = _get_phase_b_risk_profile(
        ...     duration=7,
        ...     context="base_accumulation",
        ...     minimum_duration=10,
        ...     has_exceptional_evidence=True
        ... )
        >>> print(f"Adjustment: {profile.risk_adjustment_factor}")
    """
    from src.models.phase_info import PhaseBRiskProfile

    # Determine risk adjustment factor
    if duration >= minimum_duration:
        # Normal duration - full position allowed
        return PhaseBRiskProfile(
            duration=duration,
            context=context,
            minimum_duration=minimum_duration,
            has_exceptional_evidence=has_exceptional_evidence,
            risk_adjustment_factor=1.0,
            risk_level="normal",
            risk_rationale="Adequate cause built - full position approved",
        )
    elif has_exceptional_evidence:
        # Short but with exceptional evidence - 75% position
        return PhaseBRiskProfile(
            duration=duration,
            context=context,
            minimum_duration=minimum_duration,
            has_exceptional_evidence=True,
            risk_adjustment_factor=0.75,
            risk_level="elevated",
            risk_rationale=(
                f"Short Phase B (duration={duration}, min={minimum_duration}) "
                "but Spring >85 + ST >=2 - reduce to 75%"
            ),
        )
    else:
        # Very short without exceptional evidence - 50% position
        return PhaseBRiskProfile(
            duration=duration,
            context=context,
            minimum_duration=minimum_duration,
            has_exceptional_evidence=False,
            risk_adjustment_factor=0.5,
            risk_level="high",
            risk_rationale=(
                f"Very short Phase B (duration={duration}, min={minimum_duration}) - "
                "reduce to 50% or skip"
            ),
        )


def _get_phase_e_risk_profile(sub_state: "PhaseESubState") -> "PhaseESubStateRiskProfile":
    """
    Create Phase E risk profile based on sub-state (Task 40).

    Position Actions:
        - EARLY: hold (strong momentum)
        - MATURE: trail_stops (at each LPS)
        - LATE: reduce_50 (slowing momentum)
        - EXHAUSTION: exit_75 (distribution forming)

    Args:
        sub_state: Phase E sub-state

    Returns:
        PhaseESubStateRiskProfile with exit management

    Example:
        >>> profile = _get_phase_e_risk_profile(
        ...     sub_state=PhaseESubState.LATE
        ... )
        >>> print(f"Action: {profile.position_action}")
    """
    from src.models.phase_info import PhaseESubState, PhaseESubStateRiskProfile

    if sub_state == PhaseESubState.EARLY:
        return PhaseESubStateRiskProfile(
            sub_state=sub_state,
            position_action="hold",
            stop_adjustment="Keep stops at Ice or last LPS",
            risk_level="low",
            exit_rationale="Strong momentum - hold full position",
        )

    elif sub_state == PhaseESubState.MATURE:
        return PhaseESubStateRiskProfile(
            sub_state=sub_state,
            position_action="trail_stops",
            stop_adjustment="Trail stops to last LPS",
            risk_level="normal",
            exit_rationale="Trail stops at each LPS to lock profits",
        )

    elif sub_state == PhaseESubState.LATE:
        return PhaseESubStateRiskProfile(
            sub_state=sub_state,
            position_action="reduce_50",
            stop_adjustment="Tighten stops to recent swing low",
            risk_level="elevated",
            exit_rationale="Slowing momentum - take 50% profit",
        )

    else:  # EXHAUSTION
        return PhaseESubStateRiskProfile(
            sub_state=sub_state,
            position_action="exit_75",
            stop_adjustment="Aggressive stop at recent swing low",
            risk_level="high",
            exit_rationale="Declining volume on rallies - exit 75% immediately",
        )


# Temporary file for sub-phase logic - will be merged into phase_detector_v2.py


def _determine_sub_phase(
    phase: Optional["WyckoffPhase"],
    events: "PhaseEvents",
    bars: list["OHLCVBar"],
    phase_info: Optional["PhaseInfo"],
    phase_start_index: int,
    trading_range: Optional["TradingRange"],
) -> Optional[Union["PhaseCSubState", "PhaseESubState"]]:
    """
    Determine sub-phase state for Phase C and Phase E (AC 19-22).

    Phase C sub-states:
    - C_SPRING: Spring just detected
    - C_TEST: Testing Spring low (within 5 bars)
    - C_READY: Spring held, ready for breakout

    Phase E sub-states:
    - E_EARLY: Strong momentum, few pullbacks (duration < 10, LPS = 0)
    - E_MATURE: LPS pullbacks, steady progress (LPS >= 1, good slope)
    - E_LATE: Slowing momentum, wider swings (slope declining)
    - E_EXHAUSTION: Declining volume, potential distribution

    Args:
        phase: Current Wyckoff phase
        events: Detected events
        bars: OHLCV bar data
        phase_info: Current PhaseInfo (for tracking)
        phase_start_index: Where current phase started
        trading_range: Associated trading range

    Returns:
        PhaseCSubState or PhaseESubState or None

    Example:
        >>> sub_phase = _determine_sub_phase(
        ...     phase=WyckoffPhase.C,
        ...     events=events,
        ...     bars=bars,
        ...     phase_info=None,
        ...     phase_start_index=50,
        ...     trading_range=range
        ... )
        >>> print(sub_phase)  # PhaseCSubState.SPRING
    """

    if phase == WyckoffPhase.C:
        return _determine_phase_c_sub_state(events, bars, phase_start_index, trading_range)
    elif phase == WyckoffPhase.E:
        return _determine_phase_e_sub_state(bars, phase_start_index, phase_info)
    return None


def _determine_phase_c_sub_state(
    events: "PhaseEvents",
    bars: list["OHLCVBar"],
    phase_start_index: int,
    trading_range: Optional["TradingRange"],
) -> Optional["PhaseCSubState"]:
    """
    Determine Phase C sub-state (AC 19).

    Logic:
    - If Spring just detected (within last 3 bars) → C_SPRING
    - If Spring tested (price returned to Spring low in last 5 bars) → C_TEST
    - If Spring held and ready for breakout → C_READY

    Args:
        events: Detected events
        bars: OHLCV bar data
        phase_start_index: Where Phase C started
        trading_range: Associated trading range

    Returns:
        PhaseCSubState
    """
    from decimal import Decimal

    from src.models.phase_info import PhaseCSubState

    if not events.spring:
        return PhaseCSubState.SPRING  # Default, waiting for Spring

    # Check if Spring was detected recently (within last 3 bars)
    # In real implementation, Spring would have bar_index
    # For Phase 1, assume Spring is recent if Phase C duration < 5
    current_bar_index = len(bars) - 1
    phase_c_duration = current_bar_index - phase_start_index

    if phase_c_duration <= 3:
        logger.debug("phase_c_substate_spring", reason="Spring just detected")
        return PhaseCSubState.SPRING

    # Check if Spring has been tested (price returned to Spring area)
    if trading_range:
        creek_price = Decimal(
            str(
                trading_range.creek.price
                if hasattr(trading_range.creek, "price")
                else trading_range.support
            )
        )

        # Look at last 5 bars for test of Spring
        recent_bars = bars[-5:] if len(bars) >= 5 else bars
        tested_spring = False

        for bar in recent_bars:
            bar_low = Decimal(str(bar.low))
            # Check if bar tested Spring area (within 2% of Creek)
            if abs(bar_low - creek_price) / creek_price <= Decimal("0.02"):
                # Check if it held (didn't break significantly lower)
                if bar_low >= creek_price * Decimal("0.98"):
                    tested_spring = True
                    break

        if tested_spring:
            logger.debug("phase_c_substate_test", reason="Test of Spring detected")
            return PhaseCSubState.TEST

    # Spring has held for a while, ready for breakout
    if phase_c_duration > 5:
        logger.debug("phase_c_substate_ready", reason="Spring held, ready for breakout")
        return PhaseCSubState.READY

    return PhaseCSubState.SPRING  # Default


def _determine_phase_e_sub_state(
    bars: list["OHLCVBar"], phase_start_index: int, phase_info: Optional["PhaseInfo"]
) -> Optional["PhaseESubState"]:
    """
    Determine Phase E sub-state (AC 20-21).

    Logic:
    - E_EARLY: duration < 10, LPS count = 0, strong momentum
    - E_MATURE: LPS >= 1, markup slope > threshold, steady progress
    - E_LATE: markup slope declining, wider swings
    - E_EXHAUSTION: volume declining significantly, potential distribution

    Args:
        bars: OHLCV bar data
        phase_start_index: Where Phase E started
        phase_info: Current PhaseInfo (for LPS tracking)

    Returns:
        PhaseESubState
    """
    from decimal import Decimal

    from src.models.phase_info import PhaseESubState

    current_bar_index = len(bars) - 1
    duration = current_bar_index - phase_start_index

    # Get LPS count from phase_info (Phase 1 placeholder = 0)
    lps_count = phase_info.lps_count if phase_info else 0

    # Calculate markup slope (price velocity)
    markup_slope = _calculate_markup_slope(bars, phase_start_index)

    # Calculate volume trend
    volume_trend = _detect_volume_trend(bars, phase_start_index)

    logger.debug(
        "phase_e_substate_analysis",
        duration=duration,
        lps_count=lps_count,
        markup_slope=float(markup_slope) if markup_slope else None,
        volume_trend=volume_trend,
    )

    # E_EARLY: Strong momentum, few pullbacks
    if duration < 10 and lps_count == 0:
        logger.debug("phase_e_substate_early", reason="Strong momentum, no LPS yet")
        return PhaseESubState.EARLY

    # E_EXHAUSTION: Declining volume, potential distribution
    if volume_trend == "declining" and markup_slope and markup_slope < Decimal("0.001"):
        logger.debug("phase_e_substate_exhaustion", reason="Declining volume and momentum")
        return PhaseESubState.EXHAUSTION

    # E_LATE: Slowing momentum
    if markup_slope and markup_slope < Decimal("0.002"):
        logger.debug("phase_e_substate_late", reason="Slowing momentum")
        return PhaseESubState.LATE

    # E_MATURE: Steady progress with pullbacks
    if lps_count >= 1 and markup_slope and markup_slope >= Decimal("0.002"):
        logger.debug("phase_e_substate_mature", reason="Steady progress with LPS pullbacks")
        return PhaseESubState.MATURE

    # Default to EARLY
    return PhaseESubState.EARLY


def _calculate_markup_slope(bars: list["OHLCVBar"], phase_start_index: int) -> Optional[Decimal]:
    """
    Calculate price velocity (markup slope) for Phase E.

    Uses linear regression slope of close prices since phase start.

    Args:
        bars: OHLCV bar data
        phase_start_index: Where Phase E started

    Returns:
        Slope as Decimal (price change per bar) or None if insufficient data
    """
    from decimal import Decimal

    if len(bars) - phase_start_index < 3:
        return None  # Need at least 3 bars

    phase_bars = bars[phase_start_index:]
    prices = [Decimal(str(bar.close)) for bar in phase_bars]

    # Simple linear regression
    n = len(prices)
    x_values = [Decimal(str(i)) for i in range(n)]
    x_mean = sum(x_values) / Decimal(str(n))
    y_mean = sum(prices) / Decimal(str(n))

    numerator = sum((x_values[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    if denominator == 0:
        return Decimal("0")

    slope = numerator / denominator
    return slope


def _count_lps_pullbacks(bars: list["OHLCVBar"], phase_start_index: int) -> int:
    """
    Count LPS pullbacks in Phase E.

    LPS (Last Point of Support) = pullback to support that holds before continuation.

    Args:
        bars: OHLCV bar data
        phase_start_index: Where Phase E started

    Returns:
        Count of LPS pullbacks

    Note:
        Full implementation requires Epic 5 LPS detection.
        For Phase 1, returns 0 (placeholder).
    """
    # Placeholder for Epic 5
    # Real implementation will use LPS detector from Epic 5
    return 0


def _detect_volume_trend(bars: list["OHLCVBar"], phase_start_index: int) -> str:
    """
    Detect volume trend in current phase.

    Compares recent volume to earlier phase volume.

    Args:
        bars: OHLCV bar data
        phase_start_index: Where current phase started

    Returns:
        "increasing", "declining", or "stable"
    """
    from decimal import Decimal

    if len(bars) - phase_start_index < 10:
        return "stable"  # Not enough data

    phase_bars = bars[phase_start_index:]
    mid_point = len(phase_bars) // 2

    early_volume = [Decimal(str(bar.volume)) for bar in phase_bars[:mid_point]]
    recent_volume = [Decimal(str(bar.volume)) for bar in phase_bars[mid_point:]]

    early_avg = sum(early_volume) / len(early_volume)
    recent_avg = sum(recent_volume) / len(recent_volume)

    # Compare averages
    ratio = recent_avg / early_avg if early_avg > 0 else Decimal("1")

    if ratio < Decimal("0.8"):
        return "declining"
    elif ratio > Decimal("1.2"):
        return "increasing"
    else:
        return "stable"
