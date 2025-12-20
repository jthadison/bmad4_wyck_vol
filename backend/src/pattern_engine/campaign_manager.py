"""
Campaign State Machine Module

Purpose:
--------
Tracks explicit campaign states across Wyckoff phases and manages position
entry/exit across multiple phases with sector rotation capabilities.

Story 11.9g: Campaign State Machine (Team Enhancement)

Campaign States:
----------------
- BUILDING_CAUSE: Phase A/B (accumulation in progress)
- TESTING: Phase C (Spring/UTAD testing)
- BREAKOUT: Phase D (SOS breakout)
- MARKUP: Phase E (price advancing)
- DISTRIBUTION: Exit phase (taking profits)
- EXITED: Campaign complete

Position Sizing by Phase:
-------------------------
- Phase 1 (SOS): 33% of max position
- Phase 2 (LPS): 50% of max position
- Phase 3 (Continuation): 17% of max position

Usage:
------
>>> from src.pattern_engine.campaign_manager import CampaignStateMachine, CampaignState
>>> from decimal import Decimal
>>>
>>> state_machine = CampaignStateMachine()
>>>
>>> # Transition through states
>>> current_state = CampaignState.BUILDING_CAUSE
>>> new_state = state_machine.transition_state(current_state, "SPRING_DETECTED")
>>> print(f"Transitioned to: {new_state}")  # TESTING
>>>
>>> # Calculate position size for current state
>>> position = state_machine.calculate_campaign_position(
...     campaign_state=CampaignState.BREAKOUT,
...     quality_grade="EXCELLENT"
... )
>>> print(f"Position: {position}% of max")  # 33%

Author: Story 11.9g - Campaign State Machine Implementation
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class CampaignState(Enum):
    """
    Campaign state enumeration.

    Represents the current state of a Wyckoff trading campaign across
    all phases from accumulation to exit.

    States:
        BUILDING_CAUSE: Phase A/B - Accumulation in progress
        TESTING: Phase C - Testing support/resistance (Spring/UTAD)
        BREAKOUT: Phase D - SOS/SOW breakout
        MARKUP: Phase E - Price advancing/declining
        DISTRIBUTION: Exit phase - Taking profits
        EXITED: Campaign complete - All positions closed
    """

    BUILDING_CAUSE = "BUILDING_CAUSE"
    TESTING = "TESTING"
    BREAKOUT = "BREAKOUT"
    MARKUP = "MARKUP"
    DISTRIBUTION = "DISTRIBUTION"
    EXITED = "EXITED"


# State transition rules
STATE_TRANSITIONS: dict[CampaignState, dict[str, CampaignState]] = {
    CampaignState.BUILDING_CAUSE: {
        "SPRING_DETECTED": CampaignState.TESTING,
        "UTAD_DETECTED": CampaignState.TESTING,
        "SOS_DETECTED": CampaignState.BREAKOUT,  # Direct breakout without test
    },
    CampaignState.TESTING: {
        "TEST_CONFIRMED": CampaignState.BREAKOUT,
        "SOS_DETECTED": CampaignState.BREAKOUT,
        "TEST_FAILED": CampaignState.BUILDING_CAUSE,  # Return to accumulation
    },
    CampaignState.BREAKOUT: {
        "LPS_DETECTED": CampaignState.MARKUP,
        "CONTINUATION": CampaignState.MARKUP,
        "FAILED_BREAKOUT": CampaignState.BUILDING_CAUSE,
    },
    CampaignState.MARKUP: {
        "TARGET_REACHED": CampaignState.DISTRIBUTION,
        "DISTRIBUTION_DETECTED": CampaignState.DISTRIBUTION,
        "LPS_DETECTED": CampaignState.MARKUP,  # Continue markup
    },
    CampaignState.DISTRIBUTION: {
        "EXIT_COMPLETE": CampaignState.EXITED,
    },
    CampaignState.EXITED: {
        # Terminal state - no transitions
    },
}

# Position percentages by state (as percentage of max position)
POSITION_PERCENTAGES: dict[CampaignState, Decimal] = {
    CampaignState.BUILDING_CAUSE: Decimal("0"),  # No position yet
    CampaignState.TESTING: Decimal("0"),  # Wait for confirmation
    CampaignState.BREAKOUT: Decimal("33"),  # Phase 1: 33% on SOS
    CampaignState.MARKUP: Decimal("50"),  # Phase 2: Add 17% on LPS (total 50%)
    CampaignState.DISTRIBUTION: Decimal("0"),  # Exiting positions
    CampaignState.EXITED: Decimal("0"),  # Campaign complete
}


class CampaignStateMachine:
    """
    Campaign state machine for Wyckoff trading campaigns.

    Manages state transitions across campaign phases and calculates
    appropriate position sizes for each phase.

    Example:
        >>> machine = CampaignStateMachine()
        >>> state = CampaignState.BUILDING_CAUSE
        >>>
        >>> # Detect spring - transition to TESTING
        >>> state = machine.transition_state(state, "SPRING_DETECTED")
        >>> print(state)  # TESTING
        >>>
        >>> # Confirm test - transition to BREAKOUT
        >>> state = machine.transition_state(state, "SOS_DETECTED")
        >>> print(state)  # BREAKOUT
        >>>
        >>> # Calculate position for current state
        >>> position_pct = machine.calculate_campaign_position(state, "EXCELLENT")
        >>> print(f"Position: {position_pct}%")  # 33%
    """

    def __init__(self) -> None:
        """Initialize campaign state machine."""
        logger.debug("campaign_state_machine_initialized")

    def transition_state(
        self,
        current_state: CampaignState,
        pattern_event: str,
    ) -> CampaignState:
        """
        Transition campaign state based on pattern events.

        Args:
            current_state: Current campaign state
            pattern_event: Pattern event triggering transition
                (e.g., "SPRING_DETECTED", "SOS_DETECTED", "LPS_DETECTED")

        Returns:
            New campaign state after transition

        Valid Events:
            - SPRING_DETECTED: Spring pattern detected
            - UTAD_DETECTED: UTAD pattern detected
            - SOS_DETECTED: Sign of Strength breakout
            - TEST_CONFIRMED: Test confirmation
            - TEST_FAILED: Test failure
            - LPS_DETECTED: Last Point of Support
            - CONTINUATION: Markup continuation
            - TARGET_REACHED: Price target reached
            - DISTRIBUTION_DETECTED: Distribution signals
            - EXIT_COMPLETE: All positions exited
            - FAILED_BREAKOUT: Breakout failed

        Example:
            >>> state = CampaignState.BUILDING_CAUSE
            >>> state = machine.transition_state(state, "SPRING_DETECTED")
            >>> print(state)  # TESTING
        """
        # Get valid transitions for current state
        valid_transitions = STATE_TRANSITIONS.get(current_state, {})

        # Check if event is valid for current state
        if pattern_event not in valid_transitions:
            logger.warning(
                "invalid_state_transition",
                current_state=current_state.value,
                pattern_event=pattern_event,
                valid_events=list(valid_transitions.keys()),
            )
            return current_state  # No transition

        # Perform transition
        new_state = valid_transitions[pattern_event]

        logger.info(
            "campaign_state_transition",
            from_state=current_state.value,
            to_state=new_state.value,
            trigger_event=pattern_event,
        )

        return new_state

    def calculate_campaign_position(
        self,
        campaign_state: CampaignState,
        quality_grade: str,
    ) -> Decimal:
        """
        Calculate position size for current campaign state.

        Position sizes are defined as percentages of max position:
        - Phase 1 (SOS/BREAKOUT): 33% of max position
        - Phase 2 (LPS/MARKUP): 50% of max position (add 17%)
        - Phase 3 (Continuation): Can add final 17% (total 67%)

        Args:
            campaign_state: Current campaign state
            quality_grade: Range quality grade (EXCELLENT/GOOD/FAIR/POOR)

        Returns:
            Position size as percentage of max position (0-100)

        Example:
            >>> # BREAKOUT state = 33% position
            >>> position = machine.calculate_campaign_position(
            ...     CampaignState.BREAKOUT,
            ...     "EXCELLENT"
            ... )
            >>> print(f"Position: {position}%")  # 33
            >>>
            >>> # MARKUP state = 50% position
            >>> position = machine.calculate_campaign_position(
            ...     CampaignState.MARKUP,
            ...     "EXCELLENT"
            ... )
            >>> print(f"Position: {position}%")  # 50
        """
        # Get base position percentage for state
        base_position = POSITION_PERCENTAGES.get(campaign_state, Decimal("0"))

        # Apply quality adjustment (reduce position for lower quality)
        quality_multiplier = self._get_quality_multiplier(quality_grade)
        adjusted_position = base_position * quality_multiplier

        logger.debug(
            "campaign_position_calculated",
            campaign_state=campaign_state.value,
            quality_grade=quality_grade,
            base_position=float(base_position),
            quality_multiplier=float(quality_multiplier),
            adjusted_position=float(adjusted_position),
        )

        return adjusted_position

    def _get_quality_multiplier(self, quality_grade: str) -> Decimal:
        """
        Get quality multiplier for position sizing.

        Args:
            quality_grade: Quality grade (EXCELLENT/GOOD/FAIR/POOR)

        Returns:
            Multiplier (0.5 to 1.0)
        """
        multipliers = {
            "EXCELLENT": Decimal("1.0"),
            "GOOD": Decimal("0.9"),
            "FAIR": Decimal("0.7"),
            "POOR": Decimal("0.5"),
        }
        return multipliers.get(quality_grade, Decimal("0.5"))

    def get_valid_transitions(self, current_state: CampaignState) -> list[str]:
        """
        Get list of valid transition events for current state.

        Args:
            current_state: Current campaign state

        Returns:
            List of valid pattern events that trigger transitions

        Example:
            >>> valid_events = machine.get_valid_transitions(CampaignState.TESTING)
            >>> print(valid_events)  # ['TEST_CONFIRMED', 'SOS_DETECTED', 'TEST_FAILED']
        """
        return list(STATE_TRANSITIONS.get(current_state, {}).keys())
