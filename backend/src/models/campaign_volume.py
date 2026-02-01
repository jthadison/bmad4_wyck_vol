"""
Campaign Volume Profile - Story 22.10

Purpose:
--------
Volume analysis for campaigns extracted from the monolithic Campaign
dataclass for improved Single Responsibility Principle compliance.

Contains volume profile data, effort vs result analysis, and volume
confirmation status for Wyckoff-based trading decisions.

Classes:
--------
- VolumeProfile: Volume trend classification enum
- EffortVsResult: Effort/result relationship enum
- CampaignVolumeProfile: Volume analysis dataclass

Author: Story 22.10 - Decompose Campaign Dataclass
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class VolumeProfile(Enum):
    """
    Volume trend classification for campaign progression.

    Wyckoff analysis relies heavily on volume patterns to confirm or
    invalidate price action. Volume should decline during consolidation
    phases and expand during breakout/breakdown.

    Attributes:
        INCREASING: Volume rising as campaign progresses (bullish confirmation)
        DECLINING: Volume declining (bearish/absorption during accumulation)
        NEUTRAL: No clear trend in volume
        UNKNOWN: Insufficient data for classification
    """

    INCREASING = "INCREASING"
    DECLINING = "DECLINING"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class EffortVsResult(Enum):
    """
    Wyckoff effort (volume) vs result (price movement) relationship.

    The effort vs result principle states that price movement should be
    proportional to volume effort. Divergences signal potential reversals.

    Attributes:
        HARMONY: Volume and price movement align (healthy trend)
        DIVERGENCE: Volume and price movement diverge (potential reversal)
        UNKNOWN: Insufficient data for classification

    Example:
        - High volume + small price move = DIVERGENCE (effort without result)
        - High volume + large price move = HARMONY (effort with result)
        - Low volume + large price move = DIVERGENCE (result without effort)
    """

    HARMONY = "HARMONY"
    DIVERGENCE = "DIVERGENCE"
    UNKNOWN = "UNKNOWN"


# Volume Analysis Thresholds
VOLUME_TREND_THRESHOLD = 0.7  # Minimum ratio for trend classification (70%)
VOLUME_MINIMUM_PATTERNS = 3  # Minimum patterns needed for volume profile analysis
CLIMAX_VOLUME_THRESHOLD = 2.0  # Volume ratio threshold for climactic events
SPRING_HIGH_EFFORT_THRESHOLD = 0.5  # High volume threshold for Spring patterns
SOS_HIGH_EFFORT_THRESHOLD = 1.5  # High volume threshold for SOS/LPS patterns


@dataclass
class CampaignVolumeProfile:
    """
    Volume analysis for a campaign.

    Contains volume profile data, effort vs result analysis, and volume
    confirmation status. This information is critical for Wyckoff analysis
    where "volume precedes price" is the foundational principle.

    Attributes:
        volume_profile: Overall volume trend (INCREASING/DECLINING/NEUTRAL)
        volume_trend_quality: Confidence in volume trend (0.0-1.0)
        effort_vs_result: Effort/result relationship (HARMONY/DIVERGENCE)
        volume_confirmation: Whether volume confirms price action
        relative_volume: Current volume vs average (e.g., 1.5 = 150% of avg)

        # Key volume events
        climax_detected: Whether climactic volume event detected (SC/BC)
        climax_volume: Volume level at climax event
        spring_volume: Volume at Spring pattern (should be low < 0.7x)
        breakout_volume: Volume at SOS breakout (should be high > 1.5x)

        # Volume history
        volume_history: List of recent volume ratios from patterns
        absorption_quality: Spring absorption quality score (0.0-1.0)

    Wyckoff Volume Rules:
        - Springs MUST have low volume (< 0.7x average) - violations reject signal
        - SOS breakouts MUST have high volume (> 1.5x average) - violations reject
        - Volume precedes price - expansion before breakout

    Example:
        >>> from decimal import Decimal
        >>> volume = CampaignVolumeProfile(
        ...     volume_profile=VolumeProfile.DECLINING,
        ...     effort_vs_result=EffortVsResult.HARMONY,
        ...     volume_confirmation=True,
        ...     relative_volume=0.6
        ... )
        >>> volume.is_volume_confirming()
        True
    """

    # Volume classification
    volume_profile: VolumeProfile = VolumeProfile.UNKNOWN
    volume_trend_quality: float = 0.0  # 0.0-1.0 confidence
    effort_vs_result: EffortVsResult = EffortVsResult.UNKNOWN
    volume_confirmation: bool = False
    relative_volume: float = 1.0  # Current vs average

    # Key volume events
    climax_detected: bool = False
    climax_volume: Optional[Decimal] = None
    spring_volume: Optional[Decimal] = None
    breakout_volume: Optional[Decimal] = None

    # Volume history (for trend analysis)
    volume_history: list[Decimal] = field(default_factory=list)

    # Absorption quality (Spring-specific)
    absorption_quality: float = 0.0  # 0.0-1.0

    def is_volume_confirming(self) -> bool:
        """
        Check if volume confirms price action.

        Volume is confirming when both the volume_confirmation flag is True
        AND the effort vs result relationship shows harmony (not divergence).

        Returns:
            True if volume confirms price action

        Example:
            >>> vol = CampaignVolumeProfile(
            ...     volume_confirmation=True,
            ...     effort_vs_result=EffortVsResult.HARMONY
            ... )
            >>> vol.is_volume_confirming()
            True
        """
        return self.volume_confirmation and self.effort_vs_result == EffortVsResult.HARMONY

    def is_spring_valid(self) -> bool:
        """
        Check if Spring volume is valid (low volume rule).

        Wyckoff Springs must occur on low volume (< 0.7x average) to indicate
        absorption/accumulation rather than genuine selling. High volume
        Springs are typically failed patterns.

        Returns:
            True if spring_volume is set and below threshold

        Example:
            >>> vol = CampaignVolumeProfile(spring_volume=Decimal("0.5"))
            >>> vol.is_spring_valid()
            True  # 0.5 < 0.7 threshold
        """
        if self.spring_volume is None:
            return False
        return float(self.spring_volume) < SPRING_HIGH_EFFORT_THRESHOLD

    def is_breakout_valid(self) -> bool:
        """
        Check if SOS breakout volume is valid (high volume rule).

        Sign of Strength (SOS) breakouts must occur on high volume (> 1.5x avg)
        to confirm institutional participation. Low volume breakouts often fail.

        Returns:
            True if breakout_volume is set and above threshold

        Example:
            >>> vol = CampaignVolumeProfile(breakout_volume=Decimal("1.8"))
            >>> vol.is_breakout_valid()
            True  # 1.8 > 1.5 threshold
        """
        if self.breakout_volume is None:
            return False
        return float(self.breakout_volume) > SOS_HIGH_EFFORT_THRESHOLD

    def has_climax(self) -> bool:
        """
        Check if climactic volume was detected.

        Climactic volume (> 2x average) indicates potential exhaustion and
        marks Phase A (Selling Climax) or Phase E end (Buying Climax).

        Returns:
            True if climax was detected

        Example:
            >>> vol = CampaignVolumeProfile(climax_detected=True)
            >>> vol.has_climax()
            True
        """
        return self.climax_detected

    def add_volume_reading(self, volume_ratio: Decimal) -> None:
        """
        Add a volume reading to history for trend analysis.

        Maintains a rolling history of volume ratios from pattern detections
        for volume profile classification.

        Args:
            volume_ratio: Volume relative to average (e.g., 1.2 = 120%)

        Example:
            >>> vol = CampaignVolumeProfile()
            >>> vol.add_volume_reading(Decimal("1.2"))
            >>> vol.add_volume_reading(Decimal("1.5"))
            >>> len(vol.volume_history)
            2
        """
        self.volume_history.append(volume_ratio)

    def classify_trend(self) -> VolumeProfile:
        """
        Classify volume trend from history.

        Analyzes volume_history to determine if volume is increasing,
        declining, or neutral. Requires minimum patterns for classification.

        Returns:
            VolumeProfile classification

        Example:
            >>> vol = CampaignVolumeProfile()
            >>> vol.volume_history = [Decimal("1.0"), Decimal("1.2"), Decimal("1.5")]
            >>> vol.classify_trend()
            VolumeProfile.INCREASING
        """
        if len(self.volume_history) < VOLUME_MINIMUM_PATTERNS:
            return VolumeProfile.UNKNOWN

        # Simple trend detection: compare first half to second half
        mid = len(self.volume_history) // 2
        first_half_avg = sum(self.volume_history[:mid]) / Decimal(mid)
        second_half_avg = sum(self.volume_history[mid:]) / Decimal(len(self.volume_history) - mid)

        ratio = float(second_half_avg / first_half_avg) if first_half_avg else 1.0

        if ratio > 1.0 + (1.0 - VOLUME_TREND_THRESHOLD):
            return VolumeProfile.INCREASING
        elif ratio < VOLUME_TREND_THRESHOLD:
            return VolumeProfile.DECLINING
        else:
            return VolumeProfile.NEUTRAL

    def update_classification(self) -> None:
        """
        Update volume profile classification from current history.

        Recalculates volume_profile and volume_trend_quality based on
        the current volume_history data.

        Example:
            >>> vol = CampaignVolumeProfile()
            >>> vol.volume_history = [Decimal("1.0"), Decimal("0.8"), Decimal("0.6")]
            >>> vol.update_classification()
            >>> vol.volume_profile
            VolumeProfile.DECLINING
        """
        self.volume_profile = self.classify_trend()

        # Calculate trend quality (confidence)
        if len(self.volume_history) < VOLUME_MINIMUM_PATTERNS:
            self.volume_trend_quality = 0.0
        else:
            # More patterns = higher confidence
            self.volume_trend_quality = min(1.0, len(self.volume_history) / 10.0)

    def get_average_volume(self) -> Optional[Decimal]:
        """
        Get average volume ratio from history.

        Returns:
            Average volume ratio or None if no history

        Example:
            >>> vol = CampaignVolumeProfile()
            >>> vol.volume_history = [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")]
            >>> vol.get_average_volume()
            Decimal('1.5')
        """
        if not self.volume_history:
            return None
        total = sum(self.volume_history)
        return total / Decimal(len(self.volume_history))

    def record_spring(self, volume_ratio: Decimal) -> None:
        """
        Record Spring pattern volume.

        Args:
            volume_ratio: Volume at Spring relative to average

        Example:
            >>> vol = CampaignVolumeProfile()
            >>> vol.record_spring(Decimal("0.4"))
            >>> vol.spring_volume
            Decimal('0.4')
            >>> vol.absorption_quality
            1.0  # Low volume = high absorption quality
        """
        self.spring_volume = volume_ratio
        self.add_volume_reading(volume_ratio)

        # Calculate absorption quality (lower volume = higher quality)
        # Scale: 0.0 volume = 1.0 quality, 0.7+ volume = 0.0 quality
        vol_float = float(volume_ratio)
        if vol_float <= 0:
            self.absorption_quality = 1.0
        elif vol_float >= SPRING_HIGH_EFFORT_THRESHOLD:
            self.absorption_quality = 0.0
        else:
            self.absorption_quality = 1.0 - (vol_float / SPRING_HIGH_EFFORT_THRESHOLD)

    def record_breakout(self, volume_ratio: Decimal) -> None:
        """
        Record SOS breakout volume.

        Args:
            volume_ratio: Volume at breakout relative to average

        Example:
            >>> vol = CampaignVolumeProfile()
            >>> vol.record_breakout(Decimal("2.0"))
            >>> vol.breakout_volume
            Decimal('2.0')
        """
        self.breakout_volume = volume_ratio
        self.add_volume_reading(volume_ratio)

        # Check for climactic volume
        if float(volume_ratio) >= CLIMAX_VOLUME_THRESHOLD:
            self.climax_detected = True
            self.climax_volume = volume_ratio
