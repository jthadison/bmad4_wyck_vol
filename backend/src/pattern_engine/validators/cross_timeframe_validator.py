"""
Cross-Timeframe Validation for Wyckoff Pattern Confirmation (Story 16.6b)

Purpose:
--------
Provides cross-timeframe validation to confirm intraday signals with higher
timeframe (HTF) trends. Validates that lower timeframe patterns align with
the dominant trend on daily/weekly charts for higher probability setups.

Key Features:
-------------
1. Higher Timeframe Confirmation: Validates 1h signals with 4h/1d trends
2. Timeframe Alignment Checks: Ensures pattern direction matches HTF
3. Multi-Timeframe Campaign Correlation: Links campaigns across timeframes
4. Strict Mode: Optional requirement for HTF confirmation

Timeframe Hierarchy:
--------------------
1w > 1d > 4h > 1h > 15m > 5m > 1m

- Each lower timeframe should align with its immediate higher timeframe
- For maximum confidence, validate up 2 timeframe levels (e.g., 1h → 4h → 1d)

Validation Rules:
-----------------
- ACCUMULATION (bullish) on HTF confirms: SPRING, SOS, LPS signals
- DISTRIBUTION (bearish) on HTF confirms: UTAD signals
- Trading against HTF generates warning (not rejection unless strict mode)

Author: Story 16.6b - Cross-Timeframe Validation & Integration
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

import structlog

logger = structlog.get_logger(__name__)


class TimeframeHierarchy(str, Enum):
    """
    Timeframe hierarchy for cross-timeframe validation.

    Higher values indicate longer timeframes with more significance
    for trend direction.
    """

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


# Timeframe hierarchy order (lower index = lower timeframe)
TIMEFRAME_ORDER: list[str] = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]

# HTF mapping: for each timeframe, the recommended higher timeframe to check
HTF_MAPPING: dict[str, list[str]] = {
    "1m": ["5m", "15m"],
    "5m": ["15m", "1h"],
    "15m": ["1h", "4h"],
    "1h": ["4h", "1d"],
    "4h": ["1d", "1w"],
    "1d": ["1w"],
    "1w": [],  # No higher timeframe available
}

# Bullish patterns (confirmed by ACCUMULATION)
BULLISH_PATTERNS: set[str] = {"SPRING", "SOS", "LPS", "AR"}

# Bearish patterns (confirmed by DISTRIBUTION)
BEARISH_PATTERNS: set[str] = {"UTAD", "SOW", "LPSY"}


class HTFTrend(str, Enum):
    """Higher timeframe trend classification."""

    ACCUMULATION = "ACCUMULATION"  # Bullish - confirms long signals
    DISTRIBUTION = "DISTRIBUTION"  # Bearish - confirms short signals
    NEUTRAL = "NEUTRAL"  # No clear direction
    UNKNOWN = "UNKNOWN"  # Insufficient data


class ValidationSeverity(str, Enum):
    """Severity of HTF validation result."""

    CONFIRMED = "CONFIRMED"  # Pattern aligned with HTF trend
    WARNING = "WARNING"  # Pattern against HTF trend (tradeable with caution)
    REJECTED = "REJECTED"  # Pattern rejected (strict mode only)
    SKIPPED = "SKIPPED"  # No HTF data available


@dataclass
class HTFCampaignSnapshot:
    """
    Snapshot of higher timeframe campaign state for validation.

    Attributes:
        symbol: Trading symbol
        timeframe: Timeframe of HTF campaign
        trend: Classified trend direction
        phase: Current Wyckoff phase (A, B, C, D, E)
        confidence: Trend confidence score (0.0 - 1.0)
        last_updated: When HTF analysis was last updated
    """

    symbol: str
    timeframe: str
    trend: HTFTrend
    phase: Literal["A", "B", "C", "D", "E"]
    confidence: Decimal = Decimal("0.5")
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CrossTimeframeValidationResult:
    """
    Result of cross-timeframe validation.

    Attributes:
        is_valid: Whether pattern passes validation
        severity: Validation result severity
        htf_trend: Detected HTF trend
        htf_timeframe: Timeframe used for HTF validation
        confidence_adjustment: Confidence multiplier (-0.3 to +0.2)
        warning_message: Optional warning for trader
        htf_phase: HTF Wyckoff phase if available
        strict_mode_applied: Whether strict mode was active
    """

    is_valid: bool
    severity: ValidationSeverity
    htf_trend: HTFTrend
    htf_timeframe: Optional[str] = None
    confidence_adjustment: Decimal = Decimal("0.0")
    warning_message: Optional[str] = None
    htf_phase: Optional[str] = None
    strict_mode_applied: bool = False


class CrossTimeframeValidator:
    """
    Cross-timeframe pattern validator (Story 16.6b).

    Validates lower timeframe patterns against higher timeframe trends
    to confirm signal direction and adjust confidence scores.

    Usage:
        >>> validator = CrossTimeframeValidator()
        >>> result = validator.validate_pattern(
        ...     pattern_type="SPRING",
        ...     pattern_timeframe="1h",
        ...     symbol="EUR/USD",
        ...     htf_campaigns={"1d": htf_snapshot}
        ... )
        >>> if result.is_valid:
        ...     adjusted_confidence = base_confidence * (1 + result.confidence_adjustment)
    """

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator with optional strict mode.

        Args:
            strict_mode: If True, reject patterns that trade against HTF.
                        If False, issue warnings but allow trades.
        """
        self.strict_mode = strict_mode
        self.logger = logger.bind(validator="cross_timeframe")

    def validate_pattern(
        self,
        pattern_type: str,
        pattern_timeframe: str,
        symbol: str,
        htf_campaigns: dict[str, HTFCampaignSnapshot],
    ) -> CrossTimeframeValidationResult:
        """
        Validate pattern against higher timeframe campaigns.

        Args:
            pattern_type: Type of pattern (SPRING, SOS, LPS, UTAD, etc.)
            pattern_timeframe: Timeframe of the detected pattern
            symbol: Trading symbol
            htf_campaigns: Dictionary of HTF campaign snapshots by timeframe

        Returns:
            CrossTimeframeValidationResult with validation details
        """
        # Get recommended HTF timeframes to check
        htf_timeframes = self._get_htf_timeframes(pattern_timeframe)

        if not htf_timeframes:
            # No higher timeframe available (e.g., 1w patterns)
            return CrossTimeframeValidationResult(
                is_valid=True,
                severity=ValidationSeverity.SKIPPED,
                htf_trend=HTFTrend.UNKNOWN,
                htf_timeframe=None,
                warning_message="No higher timeframe available for validation",
            )

        # Find the first available HTF campaign
        htf_snapshot: Optional[HTFCampaignSnapshot] = None
        htf_timeframe_used: Optional[str] = None

        for tf in htf_timeframes:
            if tf in htf_campaigns:
                htf_snapshot = htf_campaigns[tf]
                htf_timeframe_used = tf
                break

        if htf_snapshot is None:
            # No HTF data available
            return CrossTimeframeValidationResult(
                is_valid=True,
                severity=ValidationSeverity.SKIPPED,
                htf_trend=HTFTrend.UNKNOWN,
                htf_timeframe=None,
                warning_message=f"No HTF campaign data for {symbol} on {htf_timeframes}",
            )

        # Validate alignment
        return self._validate_alignment(
            pattern_type=pattern_type,
            pattern_timeframe=pattern_timeframe,
            htf_snapshot=htf_snapshot,
            htf_timeframe=htf_timeframe_used,
        )

    def _get_htf_timeframes(self, pattern_timeframe: str) -> list[str]:
        """Get list of higher timeframes to check for validation."""
        return HTF_MAPPING.get(pattern_timeframe, [])

    def _validate_alignment(
        self,
        pattern_type: str,
        pattern_timeframe: str,
        htf_snapshot: HTFCampaignSnapshot,
        htf_timeframe: Optional[str],
    ) -> CrossTimeframeValidationResult:
        """
        Validate if pattern aligns with HTF trend.

        Returns validated result with confidence adjustment.
        """
        pattern_upper = pattern_type.upper()
        is_bullish_pattern = pattern_upper in BULLISH_PATTERNS
        is_bearish_pattern = pattern_upper in BEARISH_PATTERNS

        htf_trend = htf_snapshot.trend
        htf_phase = htf_snapshot.phase
        htf_confidence = htf_snapshot.confidence

        # Determine alignment
        is_aligned = False
        confidence_adjustment = Decimal("0.0")
        warning_message: Optional[str] = None

        if htf_trend == HTFTrend.ACCUMULATION:
            # HTF is bullish - confirms bullish patterns
            if is_bullish_pattern:
                is_aligned = True
                confidence_adjustment = Decimal("0.15") * htf_confidence
            elif is_bearish_pattern:
                is_aligned = False
                warning_message = (
                    f"Bearish {pattern_type} on {pattern_timeframe} conflicts with "
                    f"ACCUMULATION trend on {htf_timeframe}"
                )
                confidence_adjustment = Decimal("-0.25")

        elif htf_trend == HTFTrend.DISTRIBUTION:
            # HTF is bearish - confirms bearish patterns
            if is_bearish_pattern:
                is_aligned = True
                confidence_adjustment = Decimal("0.15") * htf_confidence
            elif is_bullish_pattern:
                is_aligned = False
                warning_message = (
                    f"Bullish {pattern_type} on {pattern_timeframe} conflicts with "
                    f"DISTRIBUTION trend on {htf_timeframe}"
                )
                confidence_adjustment = Decimal("-0.25")

        elif htf_trend == HTFTrend.NEUTRAL:
            # HTF is ranging - allow but no bonus
            is_aligned = True
            confidence_adjustment = Decimal("0.0")
            warning_message = f"HTF {htf_timeframe} is in neutral/ranging state"

        else:
            # HTF unknown - skip validation
            return CrossTimeframeValidationResult(
                is_valid=True,
                severity=ValidationSeverity.SKIPPED,
                htf_trend=htf_trend,
                htf_timeframe=htf_timeframe,
                htf_phase=htf_phase,
            )

        # Determine final validity based on strict mode
        is_valid = is_aligned or not self.strict_mode
        severity = (
            ValidationSeverity.CONFIRMED
            if is_aligned
            else (ValidationSeverity.REJECTED if self.strict_mode else ValidationSeverity.WARNING)
        )

        self.logger.info(
            "cross_timeframe_validation",
            pattern_type=pattern_type,
            pattern_timeframe=pattern_timeframe,
            htf_timeframe=htf_timeframe,
            htf_trend=htf_trend.value,
            htf_phase=htf_phase,
            is_aligned=is_aligned,
            is_valid=is_valid,
            severity=severity.value,
            confidence_adjustment=str(confidence_adjustment),
        )

        return CrossTimeframeValidationResult(
            is_valid=is_valid,
            severity=severity,
            htf_trend=htf_trend,
            htf_timeframe=htf_timeframe,
            confidence_adjustment=confidence_adjustment,
            warning_message=warning_message,
            htf_phase=htf_phase,
            strict_mode_applied=self.strict_mode,
        )

    def get_timeframe_rank(self, timeframe: str) -> int:
        """
        Get numeric rank of timeframe (higher = longer timeframe).

        Args:
            timeframe: Timeframe string (e.g., "1h", "1d")

        Returns:
            Rank index (0 = 1m, 6 = 1w)

        Raises:
            ValueError: If timeframe is not supported
        """
        try:
            return TIMEFRAME_ORDER.index(timeframe)
        except ValueError as e:
            raise ValueError(
                f"Unsupported timeframe: '{timeframe}'. "
                f"Must be one of: {', '.join(TIMEFRAME_ORDER)}"
            ) from e

    def is_higher_timeframe(self, tf1: str, tf2: str) -> bool:
        """
        Check if tf1 is higher than tf2.

        Args:
            tf1: First timeframe
            tf2: Second timeframe

        Returns:
            True if tf1 > tf2
        """
        return self.get_timeframe_rank(tf1) > self.get_timeframe_rank(tf2)


def create_htf_snapshot_from_campaign(
    symbol: str,
    timeframe: str,
    phase: Literal["A", "B", "C", "D", "E"],
    campaign_type: Literal["ACCUMULATION", "DISTRIBUTION"] | None = None,
    confidence: Decimal = Decimal("0.5"),
) -> HTFCampaignSnapshot:
    """
    Factory function to create HTF snapshot from campaign data.

    Args:
        symbol: Trading symbol
        timeframe: Campaign timeframe
        phase: Current Wyckoff phase
        campaign_type: Optional explicit campaign type
        confidence: Confidence score (0.0 - 1.0)

    Returns:
        HTFCampaignSnapshot for cross-timeframe validation
    """
    # Determine trend from phase and campaign type
    if campaign_type == "DISTRIBUTION":
        trend = HTFTrend.DISTRIBUTION
    elif campaign_type == "ACCUMULATION":
        trend = HTFTrend.ACCUMULATION
    elif phase in ("D", "E"):
        # Phases D and E indicate markup (bullish)
        trend = HTFTrend.ACCUMULATION
    elif phase == "A":
        # Phase A is neutral (stopping action)
        trend = HTFTrend.NEUTRAL
    else:
        # Phases B and C are building cause (still accumulation)
        trend = HTFTrend.ACCUMULATION

    return HTFCampaignSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        trend=trend,
        phase=phase,
        confidence=confidence,
        last_updated=datetime.now(UTC),
    )
