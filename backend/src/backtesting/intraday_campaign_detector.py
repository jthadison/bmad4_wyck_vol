"""
Intraday Wyckoff Campaign Detector (Pattern Integration - Story 13.4, 14.2, 14.3)

Purpose:
--------
Groups detected Wyckoff patterns (Spring, AR, SOS, LPS) into micro-campaigns for
campaign-based trading strategies. Tracks campaign phase progression, extracts
risk metadata, and enforces portfolio risk limits.

Campaign Lifecycle:
-------------------
FORMING (1 pattern detected)
    ↓ (2nd pattern within 48h window OR high-quality AR)
ACTIVE (2+ patterns, valid sequence)
    ↓ (reaches Phase E OR exceeds 72h)
COMPLETED / FAILED

Key Features:
--------------------------
1. Pattern Integration: Spring, AR, SOS, LPS patterns grouped into campaigns (Story 13.4, 14.2)
2. Time-Window Grouping: 48h pattern window, 48h max gap, 72h expiration
3. Sequence Validation: Spring → AR → SOS → LPS (Wyckoff progression)
4. Risk Metadata: Support/resistance levels, strength score, risk/share
5. Portfolio Limits: Max concurrent campaigns, portfolio heat tracking (Story 14.3)
6. AR Activation: High-quality AR (>0.7) can activate FORMING campaigns (Story 14.2)

Author: Developer Agent (Story 13.4, 14.2, 14.3 Implementation)
"""

import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from statistics import mean, median
from typing import Any, Optional, TypeAlias, Union
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

# Volume Analysis Thresholds (Story 14.4 - Issue #5: Extract magic numbers)
VOLUME_TREND_THRESHOLD = 0.7  # Minimum ratio for trend classification (70%)
VOLUME_MINIMUM_PATTERNS = 3  # Minimum patterns needed for volume profile analysis
CLIMAX_VOLUME_THRESHOLD = 2.0  # Volume ratio threshold for climactic events
SPRING_HIGH_EFFORT_THRESHOLD = 0.5  # High volume threshold for Spring patterns
SOS_HIGH_EFFORT_THRESHOLD = 1.5  # High volume threshold for SOS/LPS patterns
SMALL_PRICE_MOVEMENT_THRESHOLD = 2.0  # Price movement % threshold
SPRING_LOW_VOLUME_THRESHOLD = 0.5  # Volume threshold for high-quality absorption
SPRING_MODERATE_VOLUME_THRESHOLD = 0.7  # Volume threshold for moderate absorption
AR_QUICK_REVERSAL_BARS = 3  # Maximum bars for quick AR reversal
AR_MODERATE_REVERSAL_BARS = 5  # Maximum bars for moderate AR reversal


class CampaignState(Enum):
    """
    Campaign lifecycle states.

    State Transitions:
    - FORMING: 1 pattern detected, waiting for second pattern
    - ACTIVE: 2+ patterns, campaign is actionable
    - DORMANT: Campaign inactive but not failed (no recent patterns)
    - COMPLETED: Campaign reached Phase E or successful exit
    - FAILED: Exceeded 72h expiration without completion
    """

    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExitReason(str, Enum):
    """
    Campaign exit reasons (Story 15.1a).

    Attributes:
        TARGET_HIT: Reached profit target (Jump level)
        STOP_OUT: Stop loss triggered
        TIME_EXIT: Manual time-based exit
        PHASE_E: Phase E completion exit
        MANUAL_EXIT: User-initiated manual exit
        UNKNOWN: Exit reason unknown/not specified
    """

    TARGET_HIT = "TARGET_HIT"
    STOP_OUT = "STOP_OUT"
    TIME_EXIT = "TIME_EXIT"
    PHASE_E = "PHASE_E"
    MANUAL_EXIT = "MANUAL_EXIT"
    UNKNOWN = "UNKNOWN"


class VolumeProfile(Enum):
    """
    Volume trend classification for campaign progression (Story 14.4 - Issue #4).

    Attributes:
        INCREASING: Volume rising as campaign progresses (bullish)
        DECLINING: Volume declining as campaign progresses (bearish/absorption)
        NEUTRAL: No clear trend in volume
        UNKNOWN: Insufficient data for classification
    """

    INCREASING = "INCREASING"
    DECLINING = "DECLINING"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class EffortVsResult(Enum):
    """
    Wyckoff effort (volume) vs result (price movement) relationship (Story 14.4 - Issue #4).

    Attributes:
        HARMONY: Volume and price movement align (healthy)
        DIVERGENCE: Volume and price movement diverge (potential reversal)
        UNKNOWN: Insufficient data for classification
    """

    HARMONY = "HARMONY"
    DIVERGENCE = "DIVERGENCE"
    UNKNOWN = "UNKNOWN"


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

        # Position Sizing & Portfolio Heat (Story 14.3)
        position_size: Shares/contracts for this campaign
        dollar_risk: Dollar risk exposure (risk_per_share × position_size)

        # Phase History (FR7.3 / AC7.5 - Story 13.7)
        phase_history: List of (timestamp, phase) tuples tracking all transitions
        phase_transition_count: Number of phase transitions in this campaign

        # Volume Profile Tracking (Story 14.4)
        volume_profile: Volume trend classification (INCREASING/DECLINING/NEUTRAL/UNKNOWN)
        volume_trend_quality: Confidence in volume trend (0.0-1.0)
        effort_vs_result: Effort/result relationship (HARMONY/DIVERGENCE/UNKNOWN)
        climax_detected: Whether climactic volume event detected (SC/BC)
        absorption_quality: Spring absorption quality score (0.0-1.0)
        volume_history: List of recent volume ratios from patterns

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
            position_size=Decimal("400"),
            dollar_risk=Decimal("1800"),
            phase_history=[(datetime(...), WyckoffPhase.C), (datetime(...), WyckoffPhase.D)],
            phase_transition_count=2
        )
    """

    campaign_id: str = field(default_factory=lambda: str(uuid4()))
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
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

    # Story 14.3: Position Sizing and Portfolio Heat
    position_size: Decimal = Decimal("0")  # Shares/contracts for this campaign
    dollar_risk: Decimal = Decimal("0")  # Dollar risk (risk_per_share × position_size)

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

    # Story 14.4: Volume Profile Tracking (Issue #4: Use proper enums)
    volume_profile: VolumeProfile = VolumeProfile.UNKNOWN
    volume_trend_quality: float = 0.0  # 0.0-1.0 confidence
    effort_vs_result: EffortVsResult = EffortVsResult.UNKNOWN
    climax_detected: bool = False
    absorption_quality: float = 0.0  # Spring absorption quality (0.0-1.0)
    volume_history: list[Decimal] = field(default_factory=list)  # Track recent volumes

    # Story 15.1a: Campaign Completion Tracking
    exit_price: Optional[Decimal] = None  # Final exit price
    exit_timestamp: Optional[datetime] = None  # Campaign exit timestamp
    exit_reason: ExitReason = ExitReason.UNKNOWN  # Reason for exit
    r_multiple: Optional[Decimal] = None  # Risk-reward multiple (points_gained / risk_per_share)
    points_gained: Optional[Decimal] = None  # Exit price - entry price
    duration_bars: int = 0  # Campaign duration in bars

    def calculate_performance_metrics(self, exit_price: Decimal) -> None:
        """
        Calculate R-multiple, points gained, and duration (Story 15.1a).

        Args:
            exit_price: Campaign exit price

        Updates:
            - points_gained: exit_price - entry_price
            - r_multiple: points_gained / risk_per_share (if risk_per_share > 0)
            - duration_bars: last_pattern.bar_number - first_pattern.bar_number + 1

        Example:
            >>> campaign = Campaign(patterns=[spring, sos])
            >>> campaign.calculate_performance_metrics(Decimal("55.00"))
            >>> # If entry=50, risk_per_share=2:
            >>> campaign.points_gained  # Decimal("5.00")
            >>> campaign.r_multiple     # Decimal("2.5")
        """
        if not self.patterns:
            logger.warning(
                "Cannot calculate performance metrics without patterns",
                campaign_id=self.campaign_id,
            )
            return

        # Entry from first pattern bar close
        entry_price = self.patterns[0].bar.close

        # Points gained
        self.points_gained = exit_price - entry_price

        # R-multiple
        if self.risk_per_share and self.risk_per_share > Decimal("0"):
            self.r_multiple = self.points_gained / self.risk_per_share
        else:
            logger.warning(
                "Cannot calculate R-multiple with zero or null risk_per_share",
                campaign_id=self.campaign_id,
                risk_per_share=str(self.risk_per_share) if self.risk_per_share else None,
            )
            self.r_multiple = None

        # Duration in bars
        if self.patterns:
            # Use bar_index if available (not all pattern types have it)
            if hasattr(self.patterns[0], "bar_index") and hasattr(self.patterns[-1], "bar_index"):
                first_bar = self.patterns[0].bar_index
                last_bar = self.patterns[-1].bar_index
                self.duration_bars = last_bar - first_bar + 1
            else:
                # Fallback: use pattern count as approximation
                self.duration_bars = len(self.patterns)


def calculate_position_size(
    account_size: Decimal,
    risk_pct_per_trade: Decimal,
    risk_per_share: Decimal,
) -> Decimal:
    """
    Calculate position size based on risk parameters (Story 14.3).

    Formula: position_size = (account_size × risk_pct) / risk_per_share

    Args:
        account_size: Total account size in dollars
        risk_pct_per_trade: Risk percentage per trade (e.g., 2.0 for 2%, max 2.0%)
        risk_per_share: Dollar risk per share (entry_price - stop_loss)

    Returns:
        Position size in shares/contracts (rounded to whole shares)

    Raises:
        ValueError: If risk_pct_per_trade exceeds 2.0% hard limit

    Example:
        >>> calculate_position_size(
        ...     account_size=Decimal("100000"),
        ...     risk_pct_per_trade=Decimal("2.0"),
        ...     risk_per_share=Decimal("5.00")
        ... )
        Decimal("400")  # $100,000 × 2% / $5.00 = 400 shares
    """
    # Validate risk percentage (2.0% hard limit)
    if risk_pct_per_trade > Decimal("2.0"):
        raise ValueError(f"risk_pct_per_trade {risk_pct_per_trade}% exceeds 2.0% hard limit")

    if risk_pct_per_trade < Decimal("0"):
        logger.warning(
            "Negative risk_pct_per_trade for position sizing",
            risk_pct_per_trade=str(risk_pct_per_trade),
        )
        return Decimal("0")

    if risk_per_share <= Decimal("0"):
        logger.warning(
            "Invalid risk_per_share for position sizing",
            risk_per_share=str(risk_per_share),
        )
        return Decimal("0")

    if account_size <= Decimal("0"):
        logger.warning(
            "Invalid account_size for position sizing",
            account_size=str(account_size),
        )
        return Decimal("0")

    # Calculate risk dollars
    risk_dollars = account_size * (risk_pct_per_trade / Decimal("100"))

    # Calculate position size
    position_size = risk_dollars / risk_per_share

    # Round to whole shares
    return position_size.quantize(Decimal("1"))


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
        max_portfolio_heat_pct: Max portfolio heat percentage (default: 10.0)

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
        max_portfolio_heat_pct: Decimal = Decimal("10.0"),
    ):
        """Initialize intraday campaign detector."""
        self.campaign_window_hours = campaign_window_hours
        self.max_pattern_gap_hours = max_pattern_gap_hours
        self.min_patterns_for_active = min_patterns_for_active
        self.expiration_hours = expiration_hours
        self.max_concurrent_campaigns = max_concurrent_campaigns
        self.max_portfolio_heat_pct = max_portfolio_heat_pct

        # Story 15.3: Indexed data structures for O(1) lookups
        self._campaigns_by_id: dict[str, Campaign] = {}  # O(1) lookup by ID
        self._campaigns_by_state: dict[CampaignState, set[str]] = defaultdict(
            set
        )  # O(1) state queries
        # Use dict for O(1) add/remove while preserving insertion order (Python 3.7+)
        # Keys are campaign IDs, values are True (used as ordered set)
        self._active_time_windows: dict[str, bool] = {}  # O(1) operations

        self.logger = logger.bind(
            component="intraday_campaign_detector",
            window_hours=campaign_window_hours,
            max_gap_hours=max_pattern_gap_hours,
            min_patterns=min_patterns_for_active,
            expiration_hours=expiration_hours,
        )

    # ==================================================================================
    # Story 15.3: Backward Compatibility Property & Index Maintenance
    # ==================================================================================

    @property
    def campaigns(self) -> list[Campaign]:
        """
        Backward compatibility: return list of campaigns (Story 15.3).

        Previously this was a direct attribute (self.campaigns = []).
        Now campaigns are stored in _campaigns_by_id for O(1) lookups,
        and this property provides backward-compatible list access.

        Warning:
            Direct mutation of the returned list (e.g., campaigns.append())
            will NOT update indexes. Use add_pattern() or _add_to_indexes()
            for proper index maintenance.

        Returns:
            List of all campaigns (derived from _campaigns_by_id)

        Example:
            >>> detector = IntradayCampaignDetector()
            >>> detector.add_pattern(spring)
            >>> len(detector.campaigns)  # Still works
            1
        """
        warnings.warn(
            "Direct mutation of detector.campaigns is deprecated and will not update "
            "indexes. Use add_pattern() or internal index methods instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return list(self._campaigns_by_id.values())

    def _add_to_indexes(self, campaign: Campaign) -> None:
        """
        Add campaign to all indexes (Story 15.3).

        Updates:
            - _campaigns_by_id: O(1) lookup by ID
            - _campaigns_by_state: O(1) state queries
            - _active_time_windows: Hot-path optimization for recent active campaigns

        Args:
            campaign: Campaign to add to indexes

        Example:
            >>> campaign = Campaign(campaign_id="abc123", state=CampaignState.FORMING)
            >>> detector._add_to_indexes(campaign)
            >>> detector._campaigns_by_id["abc123"]  # O(1) lookup
        """
        # ID index
        self._campaigns_by_id[campaign.campaign_id] = campaign

        # State index
        self._campaigns_by_state[campaign.state].add(campaign.campaign_id)

        # Time window index (if active) - O(1) dict operations
        if campaign.state == CampaignState.ACTIVE:
            self._active_time_windows[campaign.campaign_id] = True

    def _update_indexes(self, campaign: Campaign, old_state: CampaignState) -> None:
        """
        Update indexes when campaign state changes (Story 15.3).

        Args:
            campaign: Campaign that changed state
            old_state: Previous campaign state

        Example:
            >>> campaign.state = CampaignState.ACTIVE  # Was FORMING
            >>> detector._update_indexes(campaign, CampaignState.FORMING)
        """
        # Remove from old state index
        self._campaigns_by_state[old_state].discard(campaign.campaign_id)

        # Add to new state index
        self._campaigns_by_state[campaign.state].add(campaign.campaign_id)

        # Update active time windows - O(1) dict operations
        if campaign.state == CampaignState.ACTIVE:
            self._active_time_windows[campaign.campaign_id] = True
        else:
            self._active_time_windows.pop(campaign.campaign_id, None)

    def _remove_from_indexes(self, campaign_id: str) -> None:
        """
        Remove campaign from all indexes (Story 15.3).

        Args:
            campaign_id: ID of campaign to remove

        Example:
            >>> detector._remove_from_indexes("abc123")
            >>> "abc123" in detector._campaigns_by_id
            False
        """
        if campaign_id not in self._campaigns_by_id:
            return

        campaign = self._campaigns_by_id[campaign_id]

        # Remove from state index
        self._campaigns_by_state[campaign.state].discard(campaign_id)

        # Remove from time windows - O(1) dict operation
        self._active_time_windows.pop(campaign_id, None)

        # Remove from ID index
        del self._campaigns_by_id[campaign_id]

    def _rebuild_indexes(self) -> None:
        """
        Rebuild all indexes from _campaigns_by_id (Story 15.3).

        Used for recovery or after bulk operations. Clears and rebuilds
        all secondary indexes from the primary ID index.

        Example:
            >>> detector._rebuild_indexes()  # Recovers from inconsistent state
        """
        # Clear secondary indexes
        self._campaigns_by_state.clear()
        self._active_time_windows.clear()

        # Rebuild from ID index
        for campaign in self._campaigns_by_id.values():
            self._campaigns_by_state[campaign.state].add(campaign.campaign_id)
            if campaign.state == CampaignState.ACTIVE:
                self._active_time_windows[campaign.campaign_id] = True

        self.logger.debug(
            "Indexes rebuilt",
            total_campaigns=len(self._campaigns_by_id),
            active_campaigns=len(self._active_time_windows),
        )

    # ==================================================================================
    # End Story 15.3 Index Maintenance
    # ==================================================================================

    def _handle_ar_activation(self, campaign: Campaign, pattern: AutomaticRally) -> bool:
        """
        Handle AR pattern activation logic (Story 14.2, 15.3).

        High-quality AR patterns (quality_score > 0.7) can activate FORMING campaigns
        immediately without waiting for a second pattern.

        Args:
            campaign: Campaign to potentially activate
            pattern: AR pattern to evaluate

        Returns:
            bool: True if campaign was activated, False otherwise
        """
        if pattern.quality_score > AR_ACTIVATION_QUALITY_THRESHOLD:
            old_state = campaign.state  # Story 15.3: Track for index update
            campaign.state = CampaignState.ACTIVE
            # Story 15.3: Update indexes on state change
            self._update_indexes(campaign, old_state)
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

    def add_pattern(
        self,
        pattern: WyckoffPattern,
        account_size: Optional[Decimal] = None,
        risk_pct_per_trade: Decimal = Decimal("2.0"),
    ) -> Optional[Campaign]:
        """
        Add detected pattern and update campaigns.

        Tasks 1-3: Pattern integration, grouping, state machine.
        Story 14.3: Added position sizing and portfolio heat checking.

        Args:
            pattern: Detected Spring, SOS, or LPS pattern
            account_size: Total account size for position sizing (optional)
            risk_pct_per_trade: Risk percentage per trade (default 2.0%)

        Returns:
            Campaign that pattern was added to, or None if rejected

        Workflow:
            1. Expire stale campaigns (Task 5)
            2. Find existing campaign or check limits (Task 8)
            3. Calculate position size and heat (Story 14.3)
            4. Validate sequence if adding to existing (Task 7)
            5. Update risk metadata (Task 6)
            6. Transition state if threshold met (Task 3)
        """
        # Task 5: Expire stale campaigns first
        self.expire_stale_campaigns(pattern.detection_timestamp)

        # Task 2: Find or create campaign
        campaign = self._find_active_campaign(pattern)

        if not campaign:
            # Story 14.3: Create campaign first to calculate risk_per_share
            # Start new campaign (temporary, no position sizing yet)
            campaign = Campaign(
                start_time=pattern.detection_timestamp,
                patterns=[pattern],
                state=CampaignState.FORMING,
            )

            # AC4.9: Initialize risk metadata to calculate risk_per_share
            self._update_campaign_metadata(campaign)

            # Story 14.4: Volume profile tracking (Issue #3: Use helper method)
            self._update_volume_analysis(pattern, campaign)

            # Story 14.3: Calculate position sizing and check heat limits
            position_size = Decimal("0")
            new_campaign_risk = None

            if account_size and account_size > Decimal("0"):
                # Use campaign's calculated risk_per_share
                if campaign.risk_per_share and campaign.risk_per_share > Decimal("0"):
                    # Calculate position size
                    position_size = calculate_position_size(
                        account_size, risk_pct_per_trade, campaign.risk_per_share
                    )
                    new_campaign_risk = campaign.risk_per_share * position_size

            # AC4.11 + Story 14.3: Check portfolio limits (concurrent + heat)
            if not self._check_portfolio_limits(account_size, new_campaign_risk):
                self.logger.warning(
                    "Portfolio limits exceeded, cannot create new campaign",
                    active_campaigns=len(self.get_active_campaigns()),
                    max_allowed=self.max_concurrent_campaigns,
                    pattern_type=type(pattern).__name__,
                    new_campaign_risk=str(new_campaign_risk) if new_campaign_risk else None,
                )
                # Campaign rejected - not added to campaigns list
                return None

            # Update campaign with position sizing
            campaign.position_size = position_size
            # Story 15.3: Use indexed data structure instead of list append
            self._add_to_indexes(campaign)

            # Update metadata again to calculate dollar_risk with position_size
            self._update_campaign_metadata(campaign)

            self.logger.info(
                "New campaign started",
                campaign_id=campaign.campaign_id,
                timestamp=pattern.detection_timestamp,
                pattern_type=type(pattern).__name__,
                state=campaign.state.value,
                position_size=str(campaign.position_size),
                dollar_risk=str(campaign.dollar_risk),
            )

            # Story 14.2: AR can activate FORMING campaign if high quality
            if isinstance(pattern, AutomaticRally) and campaign.state == CampaignState.FORMING:
                if self._handle_ar_activation(campaign, pattern):
                    return campaign  # Activated by AR, skip normal activation logic

            return campaign

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

            # Story 14.4: Volume profile tracking (Issue #3: Use helper method)
            self._update_volume_analysis(pattern, campaign)

            return campaign

        # Add to existing campaign
        campaign.patterns.append(pattern)

        # AC4.9: Update risk metadata
        self._update_campaign_metadata(campaign)

        # Story 14.4: Volume profile tracking (Issue #3: Use helper method)
        self._update_volume_analysis(pattern, campaign)

        # Story 14.2: AR can activate FORMING campaign if high quality
        if isinstance(pattern, AutomaticRally) and campaign.state == CampaignState.FORMING:
            if self._handle_ar_activation(campaign, pattern):
                return campaign  # Activated by AR, skip normal activation logic

        # Task 3: Check if we have enough patterns to mark ACTIVE
        if len(campaign.patterns) >= self.min_patterns_for_active:
            if campaign.state == CampaignState.FORMING:
                old_state = campaign.state  # Story 15.3: Track for index update
                campaign.state = CampaignState.ACTIVE
                # Story 15.3: Update indexes on state change
                self._update_indexes(campaign, old_state)
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

        return campaign

    def _find_active_campaign(self, pattern: WyckoffPattern) -> Optional[Campaign]:
        """
        Find campaign that this pattern belongs to (Story 15.3).

        Task 2: Campaign grouping logic (48h window, gap validation).
        Story 15.3: Optimized to use state index for filtering while preserving insertion order.

        Args:
            pattern: Pattern to match against existing campaigns

        Returns:
            Matching campaign or None if no match found

        Matching Logic:
            1. Campaign must be FORMING or ACTIVE
            2. Pattern within campaign_window_hours from start
            3. Pattern within max_pattern_gap_hours from last pattern
        """
        # Story 15.3: Use state index for O(1) state check while preserving insertion order
        # Iterate over campaigns in insertion order (Python 3.7+ dict maintains order)
        # but use state index for fast state filtering
        valid_states = {CampaignState.FORMING, CampaignState.ACTIVE}
        for campaign in self._campaigns_by_id.values():
            if campaign.state not in valid_states:
                continue
            if self._pattern_matches_campaign(pattern, campaign):
                return campaign

        return None

    def _pattern_matches_campaign(self, pattern: WyckoffPattern, campaign: Campaign) -> bool:
        """
        Check if pattern matches campaign criteria (Story 15.3).

        Helper method extracted from _find_active_campaign for reuse.

        Args:
            pattern: Pattern to check
            campaign: Campaign to match against

        Returns:
            True if pattern matches campaign criteria
        """
        # State check is intentionally kept for defensive programming even though
        # callers like _find_active_campaign may pre-filter by state. This ensures
        # the method is safe to call directly from other contexts.
        if campaign.state not in [CampaignState.FORMING, CampaignState.ACTIVE]:
            return False

        hours_since_start = (
            pattern.detection_timestamp - campaign.start_time
        ).total_seconds() / 3600

        if hours_since_start <= self.campaign_window_hours:
            # Check gap from last pattern
            hours_since_last = (
                pattern.detection_timestamp - campaign.patterns[-1].detection_timestamp
            ).total_seconds() / 3600

            if hours_since_last <= self.max_pattern_gap_hours:
                return True

        return False

    def get_active_campaigns(self) -> list[Campaign]:
        """
        Return campaigns in FORMING or ACTIVE state (Story 15.3).

        Task 4: Get active campaigns retrieval method.
        Story 15.3: Uses state index for fast filtering while preserving insertion order.

        Returns:
            List of campaigns in FORMING or ACTIVE state (in insertion order)
        """
        # Story 15.3: Use state index for O(1) state check while preserving insertion order
        # Iterate over campaigns in insertion order and filter by state
        valid_states = {CampaignState.FORMING, CampaignState.ACTIVE}
        return [c for c in self._campaigns_by_id.values() if c.state in valid_states]

    def expire_stale_campaigns(self, current_time: datetime) -> None:
        """
        Mark campaigns as FAILED if expired (Story 15.3).

        Task 5: Campaign expiration (72h → FAILED).
        Story 15.3: Uses state index for O(k) lookup instead of O(n) full scan.

        Args:
            current_time: Current timestamp for expiration check

        Logic:
            - Campaigns in FORMING or ACTIVE state
            - Exceeding expiration_hours from start_time
            - Transitioned to FAILED with reason
        """
        # Story 15.3: Use state index to get only FORMING/ACTIVE campaigns
        active_ids = list(
            self._campaigns_by_state[CampaignState.FORMING]
            | self._campaigns_by_state[CampaignState.ACTIVE]
        )

        for campaign_id in active_ids:
            campaign = self._campaigns_by_id.get(campaign_id)
            if not campaign:
                continue

            hours_elapsed = (current_time - campaign.start_time).total_seconds() / 3600

            if hours_elapsed > self.expiration_hours:
                old_state = campaign.state  # Story 15.3: Track for index update
                campaign.state = CampaignState.FAILED
                campaign.failure_reason = f"Expired after {hours_elapsed:.1f} hours"
                # Story 15.3: Update indexes on state change
                self._update_indexes(campaign, old_state)

                self.logger.info(
                    "Campaign expired",
                    campaign_id=campaign.campaign_id,
                    campaign_start=campaign.start_time,
                    pattern_count=len(campaign.patterns),
                    hours_elapsed=hours_elapsed,
                    failure_reason=campaign.failure_reason,
                )

    def _find_campaign_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """
        Find campaign by ID (Story 15.1a, 15.3).

        Story 15.3: Now uses O(1) hash map lookup instead of O(n) linear search.

        Args:
            campaign_id: Campaign identifier

        Returns:
            Campaign if found, None otherwise
        """
        return self._campaigns_by_id.get(campaign_id)

    def mark_campaign_completed(
        self,
        campaign_id: str,
        exit_price: Decimal,
        exit_reason: ExitReason,
        exit_timestamp: Optional[datetime] = None,
    ) -> Optional[Campaign]:
        """
        Mark campaign as completed (Story 15.1a).

        Args:
            campaign_id: Campaign ID
            exit_price: Exit price
            exit_reason: Reason for exit
            exit_timestamp: Exit time (defaults to now)

        Returns:
            Updated campaign or None

        Raises:
            ValueError: If campaign not in valid state (ACTIVE or DORMANT)

        Example:
            >>> detector = IntradayCampaignDetector()
            >>> campaign = detector.mark_campaign_completed(
            ...     campaign_id="abc123",
            ...     exit_price=Decimal("55.00"),
            ...     exit_reason=ExitReason.TARGET_HIT
            ... )
        """
        # Find campaign
        campaign = self._find_campaign_by_id(campaign_id)
        if not campaign:
            self.logger.warning("Campaign not found", campaign_id=campaign_id)
            return None

        # Validate state
        if campaign.state not in [CampaignState.ACTIVE, CampaignState.DORMANT]:
            raise ValueError(
                f"Cannot complete campaign in {campaign.state.value} state. "
                f"Must be ACTIVE or DORMANT."
            )

        # Update state
        old_state = campaign.state  # Story 15.3: Track for index update
        campaign.state = CampaignState.COMPLETED
        # Story 15.3: Update indexes on state change
        self._update_indexes(campaign, old_state)
        campaign.exit_price = exit_price
        campaign.exit_timestamp = exit_timestamp or datetime.now(UTC)
        campaign.exit_reason = exit_reason

        # Calculate metrics
        campaign.calculate_performance_metrics(exit_price)

        # Log
        self.logger.info(
            "Campaign completed",
            campaign_id=campaign_id,
            exit_reason=exit_reason.value,
            r_multiple=float(campaign.r_multiple) if campaign.r_multiple else None,
            points_gained=float(campaign.points_gained) if campaign.points_gained else None,
            duration_bars=campaign.duration_bars,
            exit_price=str(exit_price),
        )

        return campaign

    def get_completed_campaigns(
        self,
        exit_reason: Optional[ExitReason] = None,
        min_r_multiple: Optional[Decimal] = None,
        max_r_multiple: Optional[Decimal] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Campaign]:
        """
        Get completed campaigns with optional filters (Story 15.1b).

        Args:
            exit_reason: Filter by exit reason
            min_r_multiple: Minimum R-multiple (inclusive)
            max_r_multiple: Maximum R-multiple (inclusive)
            start_date: Filter by exit date >= start_date
            end_date: Filter by exit date <= end_date

        Returns:
            List of completed campaigns matching filters

        Example:
            >>> campaigns = detector.get_completed_campaigns(
            ...     exit_reason=ExitReason.TARGET_HIT,
            ...     min_r_multiple=Decimal("2.0")
            ... )
            >>> len(campaigns)
            2
        """
        # Get all completed campaigns (use internal index to avoid deprecation warning)
        completed = [
            c for c in self._campaigns_by_id.values() if c.state == CampaignState.COMPLETED
        ]
        total_completed = len(completed)

        # Apply filters
        if exit_reason:
            completed = [c for c in completed if c.exit_reason == exit_reason]

        if min_r_multiple is not None:
            completed = [
                c for c in completed if c.r_multiple is not None and c.r_multiple >= min_r_multiple
            ]

        if max_r_multiple is not None:
            completed = [
                c for c in completed if c.r_multiple is not None and c.r_multiple <= max_r_multiple
            ]

        if start_date:
            completed = [
                c for c in completed if c.exit_timestamp and c.exit_timestamp >= start_date
            ]

        if end_date:
            completed = [c for c in completed if c.exit_timestamp and c.exit_timestamp <= end_date]

        self.logger.debug(
            "Completed campaigns query",
            total_completed=total_completed,
            filtered_results=len(completed),
            filters={
                "exit_reason": exit_reason.value if exit_reason else None,
                "min_r": float(min_r_multiple) if min_r_multiple else None,
                "max_r": float(max_r_multiple) if max_r_multiple else None,
                "date_range": f"{start_date} to {end_date}" if start_date or end_date else None,
            },
        )

        return completed

    def get_campaign_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """
        Get campaign by ID (any state) (Story 15.1b).

        Args:
            campaign_id: Unique campaign identifier

        Returns:
            Campaign or None if not found

        Example:
            >>> campaign = detector.get_campaign_by_id("abc123")
        """
        return self._find_campaign_by_id(campaign_id)

    def get_campaigns_by_state(self, state: CampaignState) -> list[Campaign]:
        """
        Get all campaigns in given state (Story 15.1b, 15.3).

        Story 15.3: Now uses O(k) state index lookup instead of O(n) full scan.

        Args:
            state: Campaign state to filter

        Returns:
            List of campaigns in specified state

        Example:
            >>> active = detector.get_campaigns_by_state(CampaignState.ACTIVE)
        """
        # Story 15.3: Use state index for O(k) lookup
        campaign_ids = self._campaigns_by_state[state]
        return [self._campaigns_by_id[cid] for cid in campaign_ids if cid in self._campaigns_by_id]

    def get_winning_campaigns(self) -> list[Campaign]:
        """
        Get all completed campaigns with positive R-multiple (Story 15.1b).

        Returns:
            List of winning campaigns (R > 0)

        Example:
            >>> winners = detector.get_winning_campaigns()
            >>> # All campaigns with R-multiple > 0
        """
        return [
            c
            for c in self._campaigns_by_id.values()
            if c.state == CampaignState.COMPLETED and c.r_multiple is not None and c.r_multiple > 0
        ]

    def get_losing_campaigns(self) -> list[Campaign]:
        """
        Get all completed campaigns with non-positive R-multiple (Story 15.1b).

        Returns:
            List of losing campaigns (R ≤ 0)

        Example:
            >>> losers = detector.get_losing_campaigns()
            >>> # All campaigns with R-multiple ≤ 0
        """
        return [
            c
            for c in self._campaigns_by_id.values()
            if c.state == CampaignState.COMPLETED and c.r_multiple is not None and c.r_multiple <= 0
        ]

    def get_campaign_statistics(self) -> dict[str, Any]:
        """
        Calculate comprehensive campaign statistics (Story 15.2).

        Returns:
            Dictionary with nested statistics:
            {
                "overview": {...},
                "performance": {...},
                "exit_reasons": {...},
                "patterns": {...},
                "phases": {...},
                "generated_at": "2026-01-17T..."
            }

        Example:
            >>> stats = detector.get_campaign_statistics()
            >>> stats["overview"]["win_rate_pct"]
            66.7
            >>> stats["performance"]["avg_r_multiple"]
            2.5
        """
        all_campaigns = list(self._campaigns_by_id.values())
        completed = [c for c in all_campaigns if c.state == CampaignState.COMPLETED]
        failed = [c for c in all_campaigns if c.state == CampaignState.FAILED]
        total = len(all_campaigns)

        # Handle edge case: no campaigns
        if total == 0:
            return self._empty_statistics()

        # Overview metrics
        overview = {
            "total_campaigns": total,
            "completed": len(completed),
            "failed": len(failed),
            "active": len(self.get_active_campaigns()),
            "success_rate_pct": (len(completed) / total * 100) if total > 0 else 0.0,
        }

        # Performance metrics
        r_multiples = [c.r_multiple for c in completed if c.r_multiple is not None]
        winning_campaigns = [c for c in completed if c.r_multiple and c.r_multiple > 0]

        performance = {
            "win_rate_pct": (len(winning_campaigns) / len(completed) * 100) if completed else 0.0,
            "avg_r_multiple": float(mean(r_multiples)) if r_multiples else 0.0,
            "median_r_multiple": float(median(r_multiples)) if r_multiples else 0.0,
            "best_r_multiple": float(max(r_multiples)) if r_multiples else 0.0,
            "worst_r_multiple": float(min(r_multiples)) if r_multiples else 0.0,
            "total_r": float(sum(r_multiples)) if r_multiples else 0.0,
            "avg_duration_bars": mean([c.duration_bars for c in completed]) if completed else 0,
            "profitable_campaigns": len(winning_campaigns),
            "losing_campaigns": len([c for c in completed if c.r_multiple and c.r_multiple <= 0]),
        }

        # Exit reason breakdown
        exit_reasons = self._calculate_exit_reason_stats(completed)

        # Pattern sequence analysis
        pattern_stats = self._calculate_pattern_sequence_stats(completed)

        # Phase analysis
        phase_stats = self._calculate_phase_stats(completed)

        self.logger.info(
            "Campaign statistics generated",
            total_campaigns=total,
            completed=len(completed),
            win_rate=performance["win_rate_pct"],
            avg_r=performance["avg_r_multiple"],
        )

        return {
            "overview": overview,
            "performance": performance,
            "exit_reasons": exit_reasons,
            "patterns": pattern_stats,
            "phases": phase_stats,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _empty_statistics(self) -> dict[str, Any]:
        """
        Return empty statistics structure (Story 15.2).

        Returns:
            Empty statistics dictionary with zero values

        Example:
            >>> stats = detector._empty_statistics()
            >>> stats["overview"]["total_campaigns"]
            0
        """
        return {
            "overview": {
                "total_campaigns": 0,
                "completed": 0,
                "failed": 0,
                "active": 0,
                "success_rate_pct": 0.0,
            },
            "performance": {
                "win_rate_pct": 0.0,
                "avg_r_multiple": 0.0,
                "median_r_multiple": 0.0,
                "best_r_multiple": 0.0,
                "worst_r_multiple": 0.0,
                "total_r": 0.0,
                "avg_duration_bars": 0,
                "profitable_campaigns": 0,
                "losing_campaigns": 0,
            },
            "exit_reasons": {},
            "patterns": {},
            "phases": {},
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _calculate_exit_reason_stats(self, completed: list[Campaign]) -> dict[str, Any]:
        """
        Calculate statistics by exit reason (Story 15.2).

        Args:
            completed: List of completed campaigns

        Returns:
            Dictionary with stats per exit reason:
            {
                "TARGET_HIT": {"count": 20, "win_rate_pct": 100.0, "avg_r_multiple": 3.0},
                "STOP_OUT": {"count": 10, "win_rate_pct": 0.0, "avg_r_multiple": -1.0}
            }

        Example:
            >>> stats = detector._calculate_exit_reason_stats(completed_campaigns)
            >>> stats["TARGET_HIT"]["win_rate_pct"]
            100.0
        """
        stats_by_reason: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "r_multiples": [], "winning": 0}
        )

        for campaign in completed:
            reason = campaign.exit_reason.value
            stats_by_reason[reason]["count"] += 1

            if campaign.r_multiple is not None:
                stats_by_reason[reason]["r_multiples"].append(float(campaign.r_multiple))
                if campaign.r_multiple > 0:
                    stats_by_reason[reason]["winning"] += 1

        # Calculate aggregates
        result = {}
        for reason, data in stats_by_reason.items():
            result[reason] = {
                "count": data["count"],
                "win_rate_pct": (data["winning"] / data["count"] * 100)
                if data["count"] > 0
                else 0.0,
                "avg_r_multiple": mean(data["r_multiples"]) if data["r_multiples"] else 0.0,
            }

        return result

    def _calculate_pattern_sequence_stats(self, completed: list[Campaign]) -> dict[str, Any]:
        """
        Analyze performance by pattern sequence (Story 15.2).

        Sequences analyzed:
        - Spring → SOS
        - Spring → AR → SOS
        - Spring → AR → SOS → LPS
        - Other (patterns not matching above sequences)

        Args:
            completed: List of completed campaigns

        Returns:
            Dictionary with stats per sequence:
            {
                "Spring→SOS": {"count": 20, "win_rate_pct": 75.0, "avg_r_multiple": 2.0},
                "Spring→AR→SOS": {"count": 15, "win_rate_pct": 80.0, "avg_r_multiple": 2.5}
            }

        Example:
            >>> stats = detector._calculate_pattern_sequence_stats(completed_campaigns)
            >>> stats["Spring→AR→SOS→LPS"]["avg_r_multiple"]
            3.0
        """
        sequences: dict[str, dict[str, Any]] = {
            "Spring→SOS": {"campaigns": [], "r_multiples": []},
            "Spring→AR→SOS": {"campaigns": [], "r_multiples": []},
            "Spring→AR→SOS→LPS": {"campaigns": [], "r_multiples": []},
            "Other": {"campaigns": [], "r_multiples": []},
        }

        for campaign in completed:
            pattern_types = [type(p).__name__ for p in campaign.patterns]

            # Classify sequence
            has_spring = "Spring" in pattern_types
            has_ar = "AutomaticRally" in pattern_types or "ARPattern" in pattern_types
            has_sos = "SOSBreakout" in pattern_types
            has_lps = "LPS" in pattern_types or "LPSPattern" in pattern_types

            if has_spring and has_ar and has_sos and has_lps:
                seq_key = "Spring→AR→SOS→LPS"
            elif has_spring and has_ar and has_sos:
                seq_key = "Spring→AR→SOS"
            elif has_spring and has_sos:
                seq_key = "Spring→SOS"
            else:
                seq_key = "Other"

            sequences[seq_key]["campaigns"].append(campaign)
            if campaign.r_multiple is not None:
                sequences[seq_key]["r_multiples"].append(float(campaign.r_multiple))

        # Calculate stats
        result = {}
        for seq_name, data in sequences.items():
            count = len(data["campaigns"])
            if count == 0:
                continue

            winning = len([c for c in data["campaigns"] if c.r_multiple and c.r_multiple > 0])

            result[seq_name] = {
                "count": count,
                "win_rate_pct": (winning / count * 100) if count > 0 else 0.0,
                "avg_r_multiple": mean(data["r_multiples"]) if data["r_multiples"] else 0.0,
                "best_r_multiple": max(data["r_multiples"]) if data["r_multiples"] else 0.0,
            }

        return result

    def _calculate_phase_stats(self, completed: list[Campaign]) -> dict[str, Any]:
        """
        Calculate statistics by entry/exit phase (Story 15.2).

        Args:
            completed: List of completed campaigns

        Returns:
            Dictionary with phase distribution:
            {
                "entry_phase_distribution": {"C": 30, "D": 20},
                "exit_phase_distribution": {"D": 25, "E": 25}
            }

        Example:
            >>> stats = detector._calculate_phase_stats(completed_campaigns)
            >>> stats["entry_phase_distribution"]["C"]
            30
        """
        # Entry phase distribution
        entry_phases = [
            c.patterns[0].phase.value
            if c.patterns and hasattr(c.patterns[0], "phase")
            else "UNKNOWN"
            for c in completed
        ]
        entry_phase_counts = Counter(entry_phases)

        # Exit phase distribution
        exit_phases = [
            c.patterns[-1].phase.value
            if c.patterns and hasattr(c.patterns[-1], "phase")
            else "UNKNOWN"
            for c in completed
        ]
        exit_phase_counts = Counter(exit_phases)

        return {
            "entry_phase_distribution": dict(entry_phase_counts),
            "exit_phase_distribution": dict(exit_phase_counts),
        }

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
            timestamp: Optional timestamp for phase history (defaults to datetime.now(UTC))

        Example:
            >>> detector.update_phase_with_bar_index(campaign, WyckoffPhase.E, 150)
            >>> # campaign.phase_e_start_bar now set to 150
            >>> # campaign.phase_history contains [(timestamp, WyckoffPhase.E)]
        """
        # Only track if phase is actually changing
        if campaign.current_phase == new_phase:
            return

        # FR7.3 / AC7.5: Track phase history
        transition_time = timestamp or datetime.now(UTC)
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
            - Spring → [Spring, AR, SOSBreakout]
            - AR → [SOSBreakout, LPS]
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

    def _update_campaign_metadata(self, campaign: Campaign) -> None:
        """
        Update campaign risk metadata based on patterns.

        Task 6: Risk metadata extraction.
        AC4.9: Extract support/resistance levels, calculate strength and risk metrics.

        Args:
            campaign: Campaign to update

        Metadata Extracted:
            - support_level: Lowest Spring low
            - resistance_level: Highest test/AR high (Story 14.2: AR included)
            - strength_score: Campaign strength using dedicated method
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

        # Story 14.3: Calculate dollar_risk for portfolio heat tracking
        if campaign.risk_per_share and campaign.position_size > Decimal("0"):
            campaign.dollar_risk = campaign.risk_per_share * campaign.position_size
        else:
            campaign.dollar_risk = Decimal("0")

    def _calculate_portfolio_heat(self, account_size: Decimal) -> Decimal:
        """
        Calculate total portfolio heat (dollar risk as % of account).

        Story 14.3: Portfolio heat calculation for risk management.

        Args:
            account_size: Total account size in dollars

        Returns:
            Portfolio heat percentage (0-100)

        Example:
            >>> detector._calculate_portfolio_heat(Decimal("100000"))
            Decimal("6.0")  # 6% portfolio heat
        """
        if account_size <= Decimal("0"):
            self.logger.warning(
                "Invalid account_size for heat calculation",
                account_size=str(account_size),
            )
            return Decimal("0")

        active_campaigns = self.get_active_campaigns()

        total_risk_dollars = Decimal("0")
        for campaign in active_campaigns:
            if campaign.position_size > Decimal("0") and campaign.risk_per_share:
                campaign_risk = campaign.risk_per_share * campaign.position_size
                total_risk_dollars += campaign_risk

        heat_pct = (total_risk_dollars / account_size) * Decimal("100")

        self.logger.debug(
            "Portfolio heat calculated",
            total_risk=str(total_risk_dollars),
            account_size=str(account_size),
            heat_pct=str(heat_pct),
            active_campaigns=len(active_campaigns),
        )

        return heat_pct

    def _check_portfolio_limits(
        self, account_size: Optional[Decimal] = None, new_campaign_risk: Optional[Decimal] = None
    ) -> bool:
        """
        Check if portfolio limits allow new campaign creation.

        Task 8: Portfolio risk limits enforcement.
        AC4.11: Enforce max concurrent campaigns and portfolio heat limits.
        Story 14.3: Added portfolio heat enforcement.

        Args:
            account_size: Total account size for heat calculation (optional)
            new_campaign_risk: Expected dollar risk for new campaign (optional)

        Returns:
            True if limits allow new campaign, False otherwise

        Limits Checked:
            1. Max concurrent campaigns (hard limit)
            2. Portfolio heat limit (if account_size provided)
            3. Warning at 80% of max concurrent campaigns
            4. Warning at 80% of max portfolio heat
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

        # Story 14.3: Check portfolio heat if account_size provided
        if account_size and account_size > Decimal("0"):
            # Calculate current heat
            current_heat = self._calculate_portfolio_heat(account_size)

            # Calculate prospective heat with new campaign
            if new_campaign_risk:
                prospective_heat = current_heat + (
                    new_campaign_risk / account_size * Decimal("100")
                )
            else:
                prospective_heat = current_heat

            # Check heat limit
            if prospective_heat > self.max_portfolio_heat_pct:
                self.logger.warning(
                    "Portfolio heat limit exceeded",
                    current_heat=str(current_heat),
                    prospective_heat=str(prospective_heat),
                    max_allowed=str(self.max_portfolio_heat_pct),
                    new_campaign_risk=str(new_campaign_risk) if new_campaign_risk else None,
                )
                return False

            # Early warning at 80% of limit
            warning_threshold = self.max_portfolio_heat_pct * Decimal("0.8")
            if prospective_heat > warning_threshold:
                self.logger.info(
                    "Portfolio heat approaching limit",
                    heat_pct=str(prospective_heat),
                    threshold=str(warning_threshold),
                    max_allowed=str(self.max_portfolio_heat_pct),
                )

        return True

    # ==================================================================================
    # Story 14.4: Volume Profile Tracking Methods
    # ==================================================================================

    def _update_volume_analysis(self, pattern: WyckoffPattern, campaign: Campaign) -> None:
        """
        Perform all volume profile tracking analysis for a pattern (Issue #3).

        This helper method consolidates volume analysis logic to avoid code duplication.
        Called after adding any pattern to a campaign.

        Updates:
            - Volume profile trend
            - Effort vs Result relationship
            - Climax detection
            - Absorption quality (for Springs)

        Args:
            pattern: Pattern being added
            campaign: Campaign to update
        """
        self._update_volume_profile(campaign)
        self._analyze_effort_vs_result(pattern, campaign)
        self._detect_climax(pattern, campaign)

        # Special: Calculate absorption quality for Springs
        if isinstance(pattern, Spring):
            self._calculate_absorption_quality(pattern, campaign)

    def _update_volume_profile(self, campaign: Campaign) -> None:
        """
        Analyze volume progression and update campaign profile.

        Tracks volume trends to identify professional activity:
        - DECLINING volume on rallies = accumulation (bullish)
        - INCREASING volume on rallies = distribution (bearish)
        - NEUTRAL = mixed signals

        Updates:
            - campaign.volume_profile
            - campaign.volume_trend_quality
            - campaign.volume_history

        Args:
            campaign: Campaign to update
        """
        patterns = campaign.patterns

        if len(patterns) < 2:
            campaign.volume_profile = VolumeProfile.UNKNOWN
            campaign.volume_trend_quality = 0.0
            return

        # Extract volume ratios from patterns (Issue #2: Store as Decimal directly)
        volumes = []
        for pattern in patterns:
            if hasattr(pattern, "volume_ratio"):
                # Store as Decimal directly, avoiding float→string→Decimal conversion
                volumes.append(
                    pattern.volume_ratio
                    if isinstance(pattern.volume_ratio, Decimal)
                    else Decimal(str(pattern.volume_ratio))
                )

        if len(volumes) < VOLUME_MINIMUM_PATTERNS:
            campaign.volume_profile = VolumeProfile.UNKNOWN
            campaign.volume_trend_quality = 0.0
            return

        # Update volume history (already Decimals)
        campaign.volume_history = volumes

        # Analyze trend (last 3-5 volumes)
        recent_volumes = volumes[-min(5, len(volumes)) :]

        # Calculate trend using simple comparison
        declining_count = 0
        increasing_count = 0

        for i in range(len(recent_volumes) - 1):
            if recent_volumes[i + 1] < recent_volumes[i]:
                declining_count += 1
            elif recent_volumes[i + 1] > recent_volumes[i]:
                increasing_count += 1

        total_comparisons = len(recent_volumes) - 1

        # Classify trend (Issue #5: Use named constant)
        if declining_count >= total_comparisons * VOLUME_TREND_THRESHOLD:  # 70%+ declining
            campaign.volume_profile = VolumeProfile.DECLINING
            campaign.volume_trend_quality = declining_count / total_comparisons
        elif increasing_count >= total_comparisons * VOLUME_TREND_THRESHOLD:  # 70%+ increasing
            campaign.volume_profile = VolumeProfile.INCREASING
            campaign.volume_trend_quality = increasing_count / total_comparisons
        else:
            campaign.volume_profile = VolumeProfile.NEUTRAL
            campaign.volume_trend_quality = 0.5

        self.logger.debug(
            "Volume profile updated",
            campaign_id=campaign.campaign_id,
            profile=campaign.volume_profile.value,
            quality=campaign.volume_trend_quality,
            volume_count=len(volumes),
        )

    def _analyze_effort_vs_result(self, pattern: WyckoffPattern, campaign: Campaign) -> None:
        """
        Analyze relationship between volume (effort) and price movement (result).

        Wyckoff's Second Law: Effort vs. Result
        - Harmony: High volume → large price move (normal)
        - Divergence: High volume → small price move (absorption or distribution)

        Key Divergences:
        - Spring: High effort (volume) + small result (price) = absorption (bullish)
        - Top: High effort + small result = distribution (bearish)

        Updates:
            - campaign.effort_vs_result

        Args:
            pattern: Pattern to analyze
            campaign: Campaign to update
        """
        if not hasattr(pattern, "volume_ratio"):
            return

        # Calculate price movement (result)
        # Access bar for price data
        bar = pattern.bar if hasattr(pattern, "bar") else pattern
        price_range = bar.high - bar.low
        price_movement_pct = (bar.close - bar.low) / bar.low * 100 if bar.low > 0 else 0

        # Volume (effort)
        volume_ratio = float(pattern.volume_ratio)

        # Expected: High volume should produce large price movement
        # Divergence: High volume + small price movement

        # High effort threshold (context-dependent) (Issue #5: Use named constants)
        # Springs have max volume_ratio of 0.7, so high effort for Spring is > 0.5
        # SOS/LPS can have high volume, so high effort is > 1.5
        if isinstance(pattern, Spring):
            high_effort = volume_ratio > SPRING_HIGH_EFFORT_THRESHOLD  # High for a Spring
        else:
            high_effort = volume_ratio > SOS_HIGH_EFFORT_THRESHOLD  # High for SOS/LPS

        # Small result threshold (relative to pattern type) (Issue #5: Use named constant)
        small_result = price_movement_pct < SMALL_PRICE_MOVEMENT_THRESHOLD  # < 2% move

        if high_effort and small_result:
            # Divergence detected (Issue #4: Use enum)
            campaign.effort_vs_result = EffortVsResult.DIVERGENCE

            # Context-specific interpretation
            if isinstance(pattern, Spring):
                # Divergence at Spring = absorption (bullish)
                self.logger.info(
                    "Bullish divergence detected - absorption at Spring",
                    campaign_id=campaign.campaign_id,
                    volume_ratio=volume_ratio,
                    price_move_pct=price_movement_pct,
                )
            elif isinstance(pattern, SOSBreakout | LPS):
                # Divergence at rally = potential distribution (bearish warning)
                self.logger.warning(
                    "Bearish divergence detected - potential distribution",
                    campaign_id=campaign.campaign_id,
                    pattern_type=type(pattern).__name__,
                    volume_ratio=volume_ratio,
                    price_move_pct=price_movement_pct,
                )
        else:
            # Normal effort/result relationship (Issue #4: Use enum)
            campaign.effort_vs_result = EffortVsResult.HARMONY

    def _detect_climax(self, pattern: WyckoffPattern, campaign: Campaign) -> None:
        """
        Identify climactic volume events (SC or BC).

        Climax = volume spike > 2.0x average + extreme price movement

        Selling Climax (SC): Downward, ultra-high volume
        Buying Climax (BC): Upward, ultra-high volume

        Updates:
            - campaign.climax_detected

        Args:
            pattern: Pattern to analyze
            campaign: Campaign to update
        """
        if not hasattr(pattern, "volume_ratio"):
            return

        volume_ratio = float(pattern.volume_ratio)

        # Climax threshold: 2.0x+ average volume (Issue #5: Use named constant)
        if volume_ratio > CLIMAX_VOLUME_THRESHOLD:
            campaign.climax_detected = True

            # Determine climax type based on price action
            bar = pattern.bar if hasattr(pattern, "bar") else pattern
            price_change = bar.close - bar.open if hasattr(bar, "open") else Decimal("0")

            if price_change < 0:
                climax_type = "SELLING_CLIMAX"
            else:
                climax_type = "BUYING_CLIMAX"

            log_data = {
                "campaign_id": campaign.campaign_id,
                "climax_type": climax_type,
                "volume_ratio": volume_ratio,
            }
            if hasattr(pattern, "bar_index"):
                log_data["bar_index"] = pattern.bar_index
            self.logger.warning("Climactic volume detected", **log_data)

    def _calculate_absorption_quality(self, spring: Spring, campaign: Campaign) -> None:
        """
        Calculate Spring absorption quality (0.0-1.0) and update campaign.

        High-quality absorption:
        - Very low volume (< 0.5x average)
        - Quick reversal (AR within 3 bars)
        - Clean test of support

        Updates campaign.absorption_quality in place.

        Args:
            spring: Spring pattern to analyze
            campaign: Campaign to update
        """
        score = 0.0

        # Volume component (50% weight) (Issue #5: Use named constants)
        volume_ratio = float(spring.volume_ratio)
        if volume_ratio < SPRING_LOW_VOLUME_THRESHOLD:
            score += 0.5
        elif volume_ratio < SPRING_MODERATE_VOLUME_THRESHOLD:
            score += 0.3

        # Reversal speed (30% weight) - check for AR
        patterns_after_spring = [
            p
            for p in campaign.patterns
            if hasattr(p, "bar_index") and p.bar_index > spring.bar_index
        ]

        # Issue #1: Find AR in single iteration instead of any() + next()
        ar_pattern = next(
            (
                p
                for p in patterns_after_spring[:AR_MODERATE_REVERSAL_BARS]
                if isinstance(p, AutomaticRally)
            ),
            None,
        )

        if ar_pattern:
            bars_to_ar = ar_pattern.bar_index - spring.bar_index

            if bars_to_ar <= AR_QUICK_REVERSAL_BARS:  # Issue #5: Use named constant
                score += 0.3  # Quick AR
            elif bars_to_ar <= AR_MODERATE_REVERSAL_BARS:  # Issue #5: Use named constant
                score += 0.15

        # Support test quality (20% weight)
        if hasattr(spring, "quality_score"):
            score += spring.quality_score * 0.2

        campaign.absorption_quality = min(score, 1.0)

        self.logger.debug(
            "Absorption quality calculated",
            campaign_id=campaign.campaign_id,
            quality=campaign.absorption_quality,
            volume_ratio=volume_ratio,
        )

        # Issue #6: Removed return statement - callers don't use it


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
            max_portfolio_heat_pct=Decimal("10.0"),  # 10% max portfolio heat (FR7.7/AC7.14)
        )

    # Daily and longer: Use standard Wyckoff campaign windows
    else:
        return IntradayCampaignDetector(
            campaign_window_hours=240,  # 10 days pattern window
            max_pattern_gap_hours=120,  # 5 days max gap
            min_patterns_for_active=2,  # 2 patterns → ACTIVE
            expiration_hours=360,  # 15 days expiration
            max_concurrent_campaigns=5,  # Max 5 concurrent campaigns
            max_portfolio_heat_pct=Decimal("10.0"),  # 10% max portfolio heat (FR7.7/AC7.14)
        )
