"""
Intraday Wyckoff Campaign Detector (Pattern Integration - Story 13.4, 14.2)

Purpose:
--------
Groups detected Wyckoff patterns (Spring, AR, SOS, LPS) into micro-campaigns for
campaign-based trading strategies. Tracks campaign phase progression, extracts
risk metadata, and enforces portfolio risk limits.

Campaign Lifecycle:
-------------------
FORMING (1 pattern detected)
    ↓ (2nd pattern within 48h window)
ACTIVE (2+ patterns, valid sequence)
    ↓ (reaches Phase E OR exceeds 72h)
COMPLETED / FAILED

Key Features (Story 13.4):
--------------------------
1. Pattern Integration: Spring, SOS, LPS patterns grouped into campaigns
2. Time-Window Grouping: 48h pattern window, 48h max gap, 72h expiration
3. Sequence Validation: Spring → AR → SOS → LPS (Wyckoff progression)
4. Risk Metadata: Support/resistance levels, strength score, risk/share
5. Portfolio Limits: Max concurrent campaigns, portfolio heat tracking

Author: Developer Agent (Story 13.4 Implementation)
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, TypeAlias, Union
from uuid import uuid4

import structlog

from src.models.automatic_rally import AutomaticRally
from src.models.lps import LPS
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.wyckoff_phase import WyckoffPhase

logger = structlog.get_logger(__name__)

# AR Pattern Quality Thresholds (Story 14.2)
AR_ACTIVATION_QUALITY_THRESHOLD = 0.7  # Minimum quality for AR to activate FORMING campaigns
AR_HIGH_QUALITY_BONUS_THRESHOLD = 0.75  # Minimum quality for AR progression bonus


class CampaignState(Enum):
    """
    Campaign lifecycle states.

    State Transitions:
    - FORMING: 1 pattern detected, waiting for second pattern
    - ACTIVE: 2+ patterns, campaign is actionable
    - COMPLETED: Campaign reached Phase E or successful exit
    - FAILED: Exceeded 72h expiration without completion
    """

    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Type alias for pattern union
WyckoffPattern: TypeAlias = Union[Spring, AutomaticRally, SOSBreakout, LPS]


@dataclass
class Campaign:
    """
    Micro-campaign tracking detected Wyckoff patterns.

    Attributes:
        campaign_id: Unique campaign identifier
        start_time: First pattern timestamp
        patterns: List of detected patterns in chronological order
        state: Current campaign state (FORMING/ACTIVE/COMPLETED/FAILED)
        current_phase: Current Wyckoff phase based on pattern sequence
        failure_reason: Reason for FAILED state (if applicable)

        # Risk Metadata (AC4.9)
        support_level: Lowest Spring low from all Spring patterns
        resistance_level: Highest resistance from AR/test patterns
        strength_score: Average pattern quality score (0.0-1.0)
        risk_per_share: Entry price - support_level
        range_width_pct: (resistance - support) / support * 100

        # Phase History (FR7.3 / AC7.5 - Story 13.7)
        phase_history: List of (timestamp, phase) tuples tracking all transitions
        phase_transition_count: Number of phase transitions in this campaign

    Example:
        Campaign(
            campaign_id="abc123",
            start_time=datetime(2025, 12, 15, 9, 0),
            patterns=[spring, sos],
            state=CampaignState.ACTIVE,
            current_phase=WyckoffPhase.D,
            support_level=Decimal("98.50"),
            resistance_level=Decimal("102.50"),
            strength_score=0.85,
            risk_per_share=Decimal("4.50"),
            range_width_pct=Decimal("4.06"),
            phase_history=[(datetime(...), WyckoffPhase.C), (datetime(...), WyckoffPhase.D)],
            phase_transition_count=2
        )
    """

    campaign_id: str = field(default_factory=lambda: str(uuid4()))
    start_time: datetime = field(default_factory=datetime.utcnow)
    patterns: list[WyckoffPattern] = field(default_factory=list)
    state: CampaignState = CampaignState.FORMING
    current_phase: Optional[WyckoffPhase] = None
    failure_reason: Optional[str] = None

    # AC4.9: Risk Metadata
    support_level: Optional[Decimal] = None
    resistance_level: Optional[Decimal] = None
    strength_score: float = 0.0
    risk_per_share: Optional[Decimal] = None
    range_width_pct: Optional[Decimal] = None

    # FR6.1: Wyckoff Exit Logic - Jump Level
    jump_level: Optional[Decimal] = None  # Measured move target (Ice + range_width)

    # FR6.1.1: Dynamic Jump Level Updates (Story 13.6.1)
    original_ice_level: Optional[Decimal] = None  # Ice at campaign start
    original_jump_level: Optional[Decimal] = None  # Jump at campaign start
    ice_expansion_count: int = 0  # Number of expansions detected
    last_ice_update_bar: Optional[int] = None

    # FR6.2.1: Phase E Tracking (Story 13.6.1)
    phase_e_progress_percent: Decimal = Decimal("0")  # % to Jump Level

    # FR6.5.1: Risk Tracking (Story 13.6.1)
    entry_atr: Optional[Decimal] = None  # ATR at entry
    max_atr_seen: Optional[Decimal] = None  # Highest ATR during campaign
    timeframe: str = "1d"  # Timeframe for intraday adjustments

    # FR6.6.2: Phase Duration Tracking (Story 13.6.3)
    phase_c_start_bar: Optional[int] = None  # Bar index when Phase C started
    phase_d_start_bar: Optional[int] = None  # Bar index when Phase D started
    phase_e_start_bar: Optional[int] = None  # Bar index when Phase E started

    # FR7.3 / AC7.5: Phase History Tracking (Story 13.7)
    phase_history: list[tuple[datetime, WyckoffPhase]] = field(default_factory=list)
    phase_transition_count: int = 0


class IntradayCampaignDetector:
    """
    Wyckoff campaign detector for intraday pattern integration.

    Groups detected patterns (Spring, SOS, LPS) into micro-campaigns based on
    time windows and Wyckoff phase progression. Enforces portfolio risk limits
    and tracks campaign lifecycle.

    Args:
        campaign_window_hours: Max hours between first and last pattern (default: 48)
        max_pattern_gap_hours: Max hours between consecutive patterns (default: 48)
        min_patterns_for_active: Min patterns to transition to ACTIVE (default: 2)
        expiration_hours: Hours before campaign fails (default: 72)
        max_concurrent_campaigns: Max ACTIVE campaigns allowed (default: 3)
        max_portfolio_heat_pct: Max portfolio heat percentage (default: 40.0)

    Example:
        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=3
        )

        detector.add_pattern(spring_pattern)
        detector.add_pattern(sos_pattern)

        active_campaigns = detector.get_active_campaigns()
        # Returns list of ACTIVE campaigns with 2+ patterns
    """

    def __init__(
        self,
        campaign_window_hours: int = 48,
        max_pattern_gap_hours: int = 48,
        min_patterns_for_active: int = 2,
        expiration_hours: int = 72,
        max_concurrent_campaigns: int = 3,
        max_portfolio_heat_pct: float = 10.0,
    ):
        """Initialize intraday campaign detector."""
        self.campaign_window_hours = campaign_window_hours
        self.max_pattern_gap_hours = max_pattern_gap_hours
        self.min_patterns_for_active = min_patterns_for_active
        self.expiration_hours = expiration_hours
        self.max_concurrent_campaigns = max_concurrent_campaigns
        self.max_portfolio_heat_pct = max_portfolio_heat_pct
        self.campaigns: list[Campaign] = []

        self.logger = logger.bind(
            component="intraday_campaign_detector",
            window_hours=campaign_window_hours,
            max_gap_hours=max_pattern_gap_hours,
            min_patterns=min_patterns_for_active,
            expiration_hours=expiration_hours,
        )

    def _handle_ar_activation(self, campaign: Campaign, pattern: AutomaticRally) -> bool:
        """
        Handle AR pattern activation logic (Story 14.2).

        High-quality AR patterns (quality_score > 0.7) can activate FORMING campaigns
        immediately without waiting for a second pattern.

        Args:
            campaign: Campaign to potentially activate
            pattern: AR pattern to evaluate

        Returns:
            bool: True if campaign was activated, False otherwise
        """
        if pattern.quality_score > AR_ACTIVATION_QUALITY_THRESHOLD:
            campaign.state = CampaignState.ACTIVE
            new_phase = self._determine_phase(campaign.patterns)
            self._update_phase_with_history(campaign, new_phase, pattern.detection_timestamp)
            self.logger.info(
                "Campaign activated by high-quality AR",
                campaign_id=campaign.campaign_id,
                ar_quality_score=pattern.quality_score,
                pattern_count=len(campaign.patterns),
                phase=campaign.current_phase.value if campaign.current_phase else None,
            )
            return True
        return False

    def add_pattern(self, pattern: WyckoffPattern) -> None:
        """
        Add detected pattern and update campaigns.

        Tasks 1-3: Pattern integration, grouping, state machine.

        Args:
            pattern: Detected Spring, SOS, or LPS pattern

        Workflow:
            1. Expire stale campaigns (Task 5)
            2. Find existing campaign or check limits (Task 8)
            3. Validate sequence if adding to existing (Task 7)
            4. Update risk metadata (Task 6)
            5. Transition state if threshold met (Task 3)
        """
        # Task 5: Expire stale campaigns first
        self.expire_stale_campaigns(pattern.detection_timestamp)

        # Task 2: Find or create campaign
        campaign = self._find_active_campaign(pattern)

        if not campaign:
            # AC4.11: Check portfolio limits before creating new campaign
            if not self._check_portfolio_limits():
                self.logger.warning(
                    "Portfolio limits exceeded, cannot create new campaign",
                    active_campaigns=len(self.get_active_campaigns()),
                    max_allowed=self.max_concurrent_campaigns,
                    pattern_type=type(pattern).__name__,
                )
                return

            # Start new campaign
            campaign = Campaign(
                start_time=pattern.detection_timestamp,
                patterns=[pattern],
                state=CampaignState.FORMING,
            )
            self.campaigns.append(campaign)

            # AC4.9: Initialize risk metadata
            self._update_campaign_metadata(campaign)

            # Story 14.2: High-quality AR can activate new campaign immediately
            if isinstance(pattern, AutomaticRally):
                if self._handle_ar_activation(campaign, pattern):
                    self.logger.info(
                        "New campaign started and activated by AR",
                        campaign_id=campaign.campaign_id,
                        timestamp=pattern.detection_timestamp,
                    )
                else:
                    self.logger.info(
                        "New campaign started (AR quality insufficient for activation)",
                        campaign_id=campaign.campaign_id,
                        timestamp=pattern.detection_timestamp,
                        ar_quality_score=pattern.quality_score,
                        state=campaign.state.value,
                    )
            else:
                self.logger.info(
                    "New campaign started",
                    campaign_id=campaign.campaign_id,
                    timestamp=pattern.detection_timestamp,
                    pattern_type=type(pattern).__name__,
                    state=campaign.state.value,
                )
            return

        # AC4.10: Validate sequence before adding
        if not self._validate_sequence(campaign.patterns + [pattern]):
            self.logger.warning(
                "Invalid pattern sequence, maintaining previous phase",
                campaign_id=campaign.campaign_id,
                attempted_pattern=type(pattern).__name__,
                existing_patterns=[type(p).__name__ for p in campaign.patterns],
                current_phase=campaign.current_phase.value if campaign.current_phase else None,
            )
            # Still add pattern but don't update phase
            campaign.patterns.append(pattern)
            self._update_campaign_metadata(campaign)
            return

        # Add to existing campaign
        campaign.patterns.append(pattern)

        # AC4.9: Update risk metadata
        self._update_campaign_metadata(campaign)

        # Story 14.2: AR can activate FORMING campaign if high quality
        if isinstance(pattern, AutomaticRally) and campaign.state == CampaignState.FORMING:
            if self._handle_ar_activation(campaign, pattern):
                return  # Activated by AR, skip normal activation logic

        # Task 3: Check if we have enough patterns to mark ACTIVE
        if len(campaign.patterns) >= self.min_patterns_for_active:
            if campaign.state == CampaignState.FORMING:
                campaign.state = CampaignState.ACTIVE
                # AC4.10: Use sequence-based phase determination
                new_phase = self._determine_phase(campaign.patterns)
                # FR7.3 / AC7.5: Track phase history
                self._update_phase_with_history(campaign, new_phase, pattern.detection_timestamp)

                self.logger.info(
                    "Campaign transitioned to ACTIVE",
                    campaign_id=campaign.campaign_id,
                    pattern_count=len(campaign.patterns),
                    phase=campaign.current_phase.value if campaign.current_phase else None,
                    strength_score=campaign.strength_score,
                    support_level=str(campaign.support_level) if campaign.support_level else None,
                    resistance_level=str(campaign.resistance_level)
                    if campaign.resistance_level
                    else None,
                )
            else:
                # Already ACTIVE, just update phase
                new_phase = self._determine_phase(campaign.patterns)
                # FR7.3 / AC7.5: Track phase history
                self._update_phase_with_history(campaign, new_phase, pattern.detection_timestamp)
                self.logger.debug(
                    "Campaign updated",
                    campaign_id=campaign.campaign_id,
                    pattern_count=len(campaign.patterns),
                    phase=campaign.current_phase.value if campaign.current_phase else None,
                )

    def _find_active_campaign(self, pattern: WyckoffPattern) -> Optional[Campaign]:
        """
        Find campaign that this pattern belongs to.

        Task 2: Campaign grouping logic (48h window, gap validation).

        Args:
            pattern: Pattern to match against existing campaigns

        Returns:
            Matching campaign or None if no match found

        Matching Logic:
            1. Campaign must be FORMING or ACTIVE
            2. Pattern within campaign_window_hours from start
            3. Pattern within max_pattern_gap_hours from last pattern
        """
        for campaign in self.campaigns:
            if campaign.state not in [CampaignState.FORMING, CampaignState.ACTIVE]:
                continue

            hours_since_start = (
                pattern.detection_timestamp - campaign.start_time
            ).total_seconds() / 3600

            if hours_since_start <= self.campaign_window_hours:
                # Check gap from last pattern
                hours_since_last = (
                    pattern.detection_timestamp - campaign.patterns[-1].detection_timestamp
                ).total_seconds() / 3600

                if hours_since_last <= self.max_pattern_gap_hours:
                    return campaign

        return None

    def get_active_campaigns(self) -> list[Campaign]:
        """
        Return campaigns in FORMING or ACTIVE state.

        Task 4: Get active campaigns retrieval method.

        Returns:
            List of campaigns in FORMING or ACTIVE state
        """
        return [
            c for c in self.campaigns if c.state in [CampaignState.FORMING, CampaignState.ACTIVE]
        ]

    def expire_stale_campaigns(self, current_time: datetime) -> None:
        """
        Mark campaigns as FAILED if expired.

        Task 5: Campaign expiration (72h → FAILED).

        Args:
            current_time: Current timestamp for expiration check

        Logic:
            - Campaigns in FORMING or ACTIVE state
            - Exceeding expiration_hours from start_time
            - Transitioned to FAILED with reason
        """
        for campaign in self.campaigns:
            if campaign.state in [CampaignState.FORMING, CampaignState.ACTIVE]:
                hours_elapsed = (current_time - campaign.start_time).total_seconds() / 3600

                if hours_elapsed > self.expiration_hours:
                    campaign.state = CampaignState.FAILED
                    campaign.failure_reason = f"Expired after {hours_elapsed:.1f} hours"

                    self.logger.info(
                        "Campaign expired",
                        campaign_id=campaign.campaign_id,
                        campaign_start=campaign.start_time,
                        pattern_count=len(campaign.patterns),
                        hours_elapsed=hours_elapsed,
                        failure_reason=campaign.failure_reason,
                    )

    def _determine_phase(self, patterns: list[WyckoffPattern]) -> Optional[WyckoffPhase]:
        """
        Determine Wyckoff phase based on pattern sequence.

        Task 7: Sequence-based phase assignment.
        AC4.10: Analyzes LATEST pattern in valid sequence, not just existence.
        Story 14.2: AR pattern phase logic added.

        Args:
            patterns: List of patterns in chronological order

        Returns:
            Wyckoff phase based on latest pattern

        Phase Assignment Logic:
            - SOS or LPS → Phase D (markup preparation)
            - Spring → Phase C (testing phase)
            - AR after Spring → Phase C confirmation (accumulation progressing)
            - AR without Spring → Phase B (early accumulation)
            - Default → Phase B (accumulation)
        """
        if not patterns:
            return None

        # Analyze sequence from most recent pattern backwards
        latest_pattern = patterns[-1]

        # Phase D: SOS or LPS indicates markup preparation
        if isinstance(latest_pattern, SOSBreakout | LPS):
            return WyckoffPhase.D

        # AR pattern phase logic (Story 14.2)
        if isinstance(latest_pattern, AutomaticRally):
            # AR after Spring = Phase C confirmation
            if any(isinstance(p, Spring) for p in patterns[:-1]):
                return WyckoffPhase.C
            # AR without Spring = early Phase B
            return WyckoffPhase.B

        # Phase C: Spring indicates testing phase
        if isinstance(latest_pattern, Spring):
            return WyckoffPhase.C

        # Default to Phase B (accumulation)
        return WyckoffPhase.B

    def _calculate_strength_score(self, campaign: Campaign) -> float:
        """
        Calculate campaign strength score (0.0-1.0).

        Story 14.2: Enhanced to reward Spring→AR→SOS progression.

        Args:
            campaign: Campaign to calculate strength for

        Returns:
            Strength score (0.0-1.0)

        Scoring Logic:
            - Base: Pattern count (0.1-0.3)
            - Pattern quality: Average quality scores (0.4 weight)
            - Phase progression: Phase D/E bonus (0.1-0.2)
            - AR bonus: Spring→AR→SOS progression (+0.1)
            - High-quality AR: Quality >0.75 (+0.05 additional)
        """
        score = 0.0
        patterns = campaign.patterns

        if not patterns:
            return 0.0

        # Base score from pattern count
        if len(patterns) >= 3:
            score += 0.3  # Multi-pattern campaign
        elif len(patterns) == 2:
            score += 0.2
        else:
            score += 0.1

        # Pattern quality tier (map quality tiers to numeric scores)
        quality_scores = []
        for p in patterns:
            if isinstance(p, Spring):
                tier = p.quality_tier
                if tier == "IDEAL":
                    quality_scores.append(0.95)
                elif tier == "GOOD":
                    quality_scores.append(0.80)
                elif tier == "ACCEPTABLE":
                    quality_scores.append(0.65)
            elif isinstance(p, AutomaticRally):
                # AR quality based on quality_score (Story 14.1)
                quality_scores.append(p.quality_score)
            elif isinstance(p, SOSBreakout):
                tier = p.quality_tier
                if tier == "EXCELLENT":
                    quality_scores.append(0.95)
                elif tier == "GOOD":
                    quality_scores.append(0.85)
                elif tier == "ACCEPTABLE":
                    quality_scores.append(0.70)
            elif isinstance(p, LPS):
                tier = p.get_overall_quality()
                if tier == "EXCELLENT":
                    quality_scores.append(0.95)
                elif tier == "GOOD":
                    quality_scores.append(0.85)
                elif tier == "ACCEPTABLE":
                    quality_scores.append(0.70)
                elif tier == "POOR":
                    quality_scores.append(0.50)

        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            score += avg_quality * 0.4  # 40% weight on pattern quality

        # AR progression bonus (Story 14.2)
        has_spring = any(isinstance(p, Spring) for p in patterns)
        has_ar = any(isinstance(p, AutomaticRally) for p in patterns)
        has_sos = any(isinstance(p, SOSBreakout) for p in patterns)

        if has_spring and has_ar and has_sos:
            # Complete Spring→AR→SOS progression
            score += 0.1

            # Additional bonus for high-quality AR
            ar_patterns = [p for p in patterns if isinstance(p, AutomaticRally)]
            if ar_patterns:
                # Check if any AR has high quality
                for ar in ar_patterns:
                    if ar.quality_score > AR_HIGH_QUALITY_BONUS_THRESHOLD:
                        score += 0.05  # High-quality AR bonus
                        break  # Only add once

        # Phase progression bonus
        if campaign.current_phase in [WyckoffPhase.D, WyckoffPhase.E]:
            score += 0.2
        elif campaign.current_phase == WyckoffPhase.C:
            score += 0.1

        return min(score, 1.0)

    def update_phase_with_bar_index(
        self,
        campaign: Campaign,
        new_phase: WyckoffPhase,
        bar_index: int,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Update campaign phase and track bar index for phase transitions.

        Story 13.6.3 - Task 1: Phase duration tracking.
        Story 13.7 - AC7.5: Phase history tracking.
        Records bar index when entering Phase C, D, or E.

        Args:
            campaign: Campaign to update
            new_phase: New Wyckoff phase
            bar_index: Current bar index in backtest
            timestamp: Optional timestamp for phase history (defaults to utcnow)

        Example:
            >>> detector.update_phase_with_bar_index(campaign, WyckoffPhase.E, 150)
            >>> # campaign.phase_e_start_bar now set to 150
            >>> # campaign.phase_history contains [(timestamp, WyckoffPhase.E)]
        """
        # Only track if phase is actually changing
        if campaign.current_phase == new_phase:
            return

        # FR7.3 / AC7.5: Track phase history
        transition_time = timestamp or datetime.utcnow()
        campaign.phase_history.append((transition_time, new_phase))
        campaign.phase_transition_count += 1

        # Track phase start bar indices
        if new_phase == WyckoffPhase.C and campaign.phase_c_start_bar is None:
            campaign.phase_c_start_bar = bar_index
            self.logger.debug(
                "phase_c_started",
                campaign_id=campaign.campaign_id,
                bar_index=bar_index,
            )
        elif new_phase == WyckoffPhase.D and campaign.phase_d_start_bar is None:
            campaign.phase_d_start_bar = bar_index
            self.logger.debug(
                "phase_d_started",
                campaign_id=campaign.campaign_id,
                bar_index=bar_index,
            )
        elif new_phase == WyckoffPhase.E and campaign.phase_e_start_bar is None:
            campaign.phase_e_start_bar = bar_index
            self.logger.debug(
                "phase_e_started",
                campaign_id=campaign.campaign_id,
                bar_index=bar_index,
            )

        # Update phase
        campaign.current_phase = new_phase

    def _update_phase_with_history(
        self, campaign: Campaign, new_phase: Optional[WyckoffPhase], timestamp: datetime
    ) -> None:
        """
        Update campaign phase with history tracking (no bar_index).

        FR7.3 / AC7.5: Phase history tracking helper.
        Used when bar_index is not available (e.g., in add_pattern).

        Args:
            campaign: Campaign to update
            new_phase: New Wyckoff phase (or None)
            timestamp: Timestamp for the phase transition
        """
        if new_phase is None:
            return

        # Only track if phase is actually changing
        if campaign.current_phase == new_phase:
            return

        # Track phase history
        campaign.phase_history.append((timestamp, new_phase))
        campaign.phase_transition_count += 1

        # Update phase
        campaign.current_phase = new_phase

    def _validate_sequence(self, patterns: list[WyckoffPattern]) -> bool:
        """
        Validate pattern sequence follows logical Wyckoff progression.

        Task 7: Sequence validation.
        AC4.10: Valid sequences - Spring → SOS → LPS

        Args:
            patterns: Pattern sequence to validate

        Returns:
            True if sequence is valid, False otherwise

        Valid Transitions:
            - Spring → [Spring, SOSBreakout]
            - SOSBreakout → [SOSBreakout, LPS]
            - LPS → [LPS]

        Invalid Examples:
            - Spring after SOS (Phase C cannot follow Phase D)
            - Spring after LPS (Phase C cannot follow Phase D)
        """
        if len(patterns) <= 1:
            return True

        # Define valid transitions
        # Key: current pattern type, Value: list of allowed next patterns
        VALID_TRANSITIONS: dict[type, list[type]] = {
            Spring: [Spring, AutomaticRally, SOSBreakout],  # Spring → AR optional, then SOS
            AutomaticRally: [SOSBreakout, LPS],  # AR → SOS/LPS (confirms accumulation)
            SOSBreakout: [SOSBreakout, LPS],  # Can have multiple SOS, then LPS
            LPS: [LPS],  # LPS can repeat
        }

        # Check each transition
        for i in range(len(patterns) - 1):
            current = patterns[i]
            next_pattern = patterns[i + 1]

            current_type = type(current)
            next_type = type(next_pattern)

            # Check if transition is valid
            if current_type in VALID_TRANSITIONS:
                if next_type not in VALID_TRANSITIONS[current_type]:
                    self.logger.debug(
                        "Invalid transition detected",
                        from_pattern=current_type.__name__,
                        to_pattern=next_type.__name__,
                        valid_transitions=[t.__name__ for t in VALID_TRANSITIONS[current_type]],
                    )
                    return False

        return True

    def _update_campaign_metadata(self, campaign: Campaign) -> None:
        """
        Update campaign risk metadata based on patterns.

        Task 6: Risk metadata extraction.
        AC4.9: Extract support/resistance levels, calculate strength and risk metrics.

        Args:
            campaign: Campaign to update

        Metadata Extracted:
            - support_level: Lowest Spring low
            - resistance_level: Highest test/AR high (Note: AR not in scope, use SOS)
            - strength_score: Average pattern quality scores
            - risk_per_share: Latest price - support_level
            - range_width_pct: (resistance - support) / support * 100
        """
        if not campaign.patterns:
            return

        # Extract support level (lowest Spring low)
        spring_lows = [
            p.spring_low
            for p in campaign.patterns
            if isinstance(p, Spring) and hasattr(p, "spring_low")
        ]
        if spring_lows:
            campaign.support_level = min(spring_lows)

        # Extract resistance level (highest AR/SOS/LPS resistance)
        # Story 14.2: AR patterns now included
        resistance_highs = []
        for p in campaign.patterns:
            if isinstance(p, AutomaticRally) and hasattr(p, "ar_high"):
                # AR high represents resistance level
                resistance_highs.append(p.ar_high)
            elif isinstance(p, SOSBreakout) and hasattr(p, "breakout_price"):
                resistance_highs.append(p.breakout_price)
            elif isinstance(p, LPS) and hasattr(p, "ice_level"):
                # Ice is the resistance that was broken
                resistance_highs.append(p.ice_level)

        if resistance_highs:
            campaign.resistance_level = max(resistance_highs)

        # Calculate strength score using dedicated method (Story 14.2)
        campaign.strength_score = self._calculate_strength_score(campaign)

        # Calculate risk per share (current price - support)
        if campaign.support_level and campaign.patterns:
            latest_pattern = campaign.patterns[-1]
            latest_price = None

            if isinstance(latest_pattern, Spring):
                latest_price = latest_pattern.recovery_price
            elif isinstance(latest_pattern, AutomaticRally):
                latest_price = latest_pattern.ar_high  # Story 14.2
            elif isinstance(latest_pattern, SOSBreakout):
                latest_price = latest_pattern.breakout_price
            elif isinstance(latest_pattern, LPS):
                latest_price = latest_pattern.bar.close  # LPS uses OHLCVBar

            if latest_price:
                campaign.risk_per_share = latest_price - campaign.support_level

        # Calculate range width percentage
        if campaign.support_level and campaign.resistance_level:
            campaign.range_width_pct = (
                (campaign.resistance_level - campaign.support_level)
                / campaign.support_level
                * Decimal("100")
            )

        # FR6.1: Calculate Jump Level (measured move target)
        # Jump = Ice + (Ice - Creek) = Ice + range_width
        if campaign.support_level and campaign.resistance_level:
            range_width = campaign.resistance_level - campaign.support_level
            campaign.jump_level = campaign.resistance_level + range_width

    def _check_portfolio_limits(self) -> bool:
        """
        Check if portfolio limits allow new campaign creation.

        Task 8: Portfolio risk limits enforcement.
        AC4.11: Enforce max concurrent campaigns and portfolio heat limits.

        Returns:
            True if limits allow new campaign, False otherwise

        Limits Checked:
            1. Max concurrent campaigns (hard limit)
            2. Warning at 80% of max concurrent campaigns
            3. Portfolio heat calculation (future enhancement)
        """
        active_campaigns = self.get_active_campaigns()

        # Check concurrent campaign limit
        if len(active_campaigns) >= self.max_concurrent_campaigns:
            self.logger.warning(
                "Max concurrent campaigns reached",
                active=len(active_campaigns),
                max=self.max_concurrent_campaigns,
            )
            return False

        # Log warning if approaching limit (80%)
        if len(active_campaigns) >= self.max_concurrent_campaigns * 0.8:
            self.logger.warning(
                "Approaching max concurrent campaigns",
                active=len(active_campaigns),
                max=self.max_concurrent_campaigns,
                utilization_pct=(len(active_campaigns) / self.max_concurrent_campaigns * 100),
            )

        return True


def create_timeframe_optimized_detector(timeframe: str) -> IntradayCampaignDetector:
    """
    Factory function to create timeframe-optimized campaign detector.

    Creates IntradayCampaignDetector with parameters tuned for specific timeframes:
    - Intraday (15m, 1h): Shorter windows, tighter expiration
    - Daily: Standard windows for traditional Wyckoff analysis

    Args:
        timeframe: Timeframe code ("15m", "1h", "1d", etc.)

    Returns:
        IntradayCampaignDetector configured for timeframe

    Example:
        >>> detector = create_timeframe_optimized_detector("15m")
        >>> detector.add_pattern(spring_pattern)
    """
    # Intraday timeframes: Use micro-campaign windows
    if timeframe in ["1m", "5m", "15m", "1h"]:
        return IntradayCampaignDetector(
            campaign_window_hours=48,  # 48h pattern window
            max_pattern_gap_hours=48,  # 48h max gap between patterns
            min_patterns_for_active=2,  # 2 patterns → ACTIVE
            expiration_hours=72,  # 72h expiration
            max_concurrent_campaigns=3,  # Max 3 concurrent campaigns
            max_portfolio_heat_pct=10.0,  # 10% max portfolio heat (FR7.7/AC7.14)
        )

    # Daily and longer: Use standard Wyckoff campaign windows
    else:
        return IntradayCampaignDetector(
            campaign_window_hours=240,  # 10 days pattern window
            max_pattern_gap_hours=120,  # 5 days max gap
            min_patterns_for_active=2,  # 2 patterns → ACTIVE
            expiration_hours=360,  # 15 days expiration
            max_concurrent_campaigns=5,  # Max 5 concurrent campaigns
            max_portfolio_heat_pct=10.0,  # 10% max portfolio heat (FR7.7/AC7.14)
        )
