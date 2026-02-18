"""
UTAD (Upthrust After Distribution) Pattern Detector Module

Purpose:
--------
Detects UTAD patterns (breakout above Ice with high volume that fails back below).
UTADs signal Phase E completion and distribution beginning - exit signals for long positions.

FR Requirements:
----------------
- FR6.2: UTAD detection (0.5-1.0% break above Ice, >1.5x volume, failure within 3 bars)
- AC6.3: UTAD validation (Phase D/E only, high volume required)

Author: Generated for Story 13.6 Task #2
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.trading_range import TradingRange
from src.models.utad import UTAD
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

logger = structlog.get_logger(__name__)

# Minimum confidence threshold for pattern validation
MINIMUM_CONFIDENCE_THRESHOLD = 70


def detect_utad(
    trading_range: TradingRange,
    bars: list[OHLCVBar],
    phase: WyckoffPhase,
    start_index: int = 20,
    skip_indices: Optional[set[int]] = None,
) -> Optional[UTAD]:
    """
    Detect UTAD (Upthrust After Distribution) patterns.

    An UTAD is a critical Wyckoff distribution signal that indicates Phase E markup
    is complete. It breaks above Ice resistance on high volume to trap buyers,
    then rapidly fails back below Ice.

    Args:
        trading_range: Active trading range with Ice level (trading_range.ice must not be None)
        bars: OHLCV bars (minimum 20 bars for volume ratio calculation)
        phase: Current Wyckoff phase (must be Phase D or E per FR6.2)
        start_index: Index to start scanning from (default: 20 for volume calculation)
        skip_indices: Set of bar indices to skip (already detected UTADs)

    Returns:
        Optional[UTAD]: UTAD if detected, None if not found or rejected

    Raises:
        ValueError: If trading_range is None, trading_range.ice is None,
            or trading_range.ice.price <= 0

    FR Requirements:
        - FR6.2: UTAD detection (0.5-1.0% breakout above Ice)
        - FR6.2: Volume validation (>1.5x required, binary rejection)
        - FR6.2: Failure validation (close back below Ice within 3 bars)
        - AC6.3: Phase D/E only (UTADs invalid in other phases)

    Example:
        >>> utad = detect_utad(range, bars, WyckoffPhase.E)
        >>> if utad:
        ...     print(f"UTAD: {utad.breakout_pct:.2%} above Ice")
        ...     print(f"Volume: {utad.volume_ratio:.2f}x (high volume)")
        ...     print(f"Failed in {utad.bars_to_failure} bars")
    """
    # ============================================================
    # INPUT VALIDATION
    # ============================================================

    # Validate trading range
    if trading_range is None:
        logger.error("trading_range_missing")
        raise ValueError("Trading range required for UTAD detection")

    # Validate Ice exists (FR6.2)
    if trading_range.ice is None or trading_range.ice.price <= 0:
        logger.error(
            "ice_missing_or_invalid",
            symbol=trading_range.symbol,
            ice=trading_range.ice.price if trading_range.ice else None,
        )
        raise ValueError("Valid Ice level required for UTAD detection")

    # Validate sufficient bars for volume calculation
    if len(bars) < 20:
        logger.warning(
            "insufficient_bars_for_utad_detection",
            bars_available=len(bars),
            bars_required=20,
            message="Need at least 20 bars for volume average calculation",
        )
        return None

    # ============================================================
    # PHASE VALIDATION (FR6.2)
    # ============================================================

    if phase not in [WyckoffPhase.D, WyckoffPhase.E]:
        logger.debug(
            "utad_wrong_phase",
            current_phase=phase.value,
            required_phase="D or E",
            message="UTAD only valid in Phase D or E (FR6.2)",
        )
        return None

    # ============================================================
    # EXTRACT ICE LEVEL
    # ============================================================

    ice_level = trading_range.ice.price  # Decimal from IceLevel model

    logger.debug(
        "utad_detection_starting",
        symbol=trading_range.symbol,
        ice_level=float(ice_level),
        phase=phase.value,
        bars_to_scan=min(20, len(bars)),
    )

    # ============================================================
    # SCAN FOR UTAD PATTERN
    # ============================================================

    # Initialize skip_indices if None
    if skip_indices is None:
        skip_indices = set()

    # Scan from start_index to end of bars for breakout above Ice
    # Ensure start_index is at least 20 (minimum for volume calculation)
    scan_start = max(20, start_index)

    for i in range(scan_start, len(bars)):
        # Skip if this index was already detected
        if i in skip_indices:
            continue
        bar = bars[i]

        # Check if bar broke above Ice
        if bar.high <= ice_level:
            continue  # No breakout, skip

        # ============================================================
        # CALCULATE BREAKOUT PERCENTAGE (AC6.3)
        # ============================================================

        # Quantize to 4 decimal places to match UTAD model constraint
        breakout_pct = ((bar.high - ice_level) / ice_level).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # ============================================================
        # VALIDATE BREAKOUT DISTANCE (AC6.3)
        # ============================================================

        if breakout_pct < Decimal("0.005"):  # 0.5% min
            logger.debug(
                "utad_breakout_too_small",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                breakout_pct=float(breakout_pct),
                min_allowed=0.005,
                message="Breakout <0.5% too small - may be noise, not UTAD",
            )
            continue  # Skip this candidate, try next bar

        if breakout_pct > Decimal("0.010"):  # 1.0% max
            logger.debug(
                "utad_breakout_too_large",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                breakout_pct=float(breakout_pct),
                max_allowed=0.010,
                message="Breakout >1.0% too large - indicates genuine breakout, not UTAD",
            )
            continue  # Skip this candidate, try next bar

        # ============================================================
        # CRITICAL VOLUME VALIDATION (FR6.2)
        # ============================================================

        # Calculate volume ratio using standard VolumeAnalyzer
        volume_ratio_float = calculate_volume_ratio(bars, i)

        if volume_ratio_float is None:
            logger.error(
                "volume_ratio_calculation_failed",
                bar_timestamp=bar.timestamp.isoformat(),
                bar_index=i,
                message="VolumeAnalyzer returned None (insufficient data or zero average)",
            )
            continue  # Skip candidate

        # Convert float to Decimal and quantize to 4 decimal places
        volume_ratio = Decimal(str(volume_ratio_float)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # FR6.2 enforcement - HIGH VOLUME required for UTAD (AC6.3)
        if volume_ratio <= Decimal("1.5"):
            logger.debug(
                "utad_invalid_low_volume",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                volume_ratio=float(volume_ratio),
                threshold=1.5,
                message=f"UTAD INVALID: Volume {volume_ratio:.2f}x <= 1.5x threshold [FR6.2]",
            )
            continue  # REJECT immediately - no further processing

        # ============================================================
        # FAILURE VALIDATION (AC6.3)
        # ============================================================

        # Check if price fails back below Ice within 3 bars
        failure_window_end = min(i + 4, len(bars))  # Current + next 3 bars
        failure_window = bars[i:failure_window_end]

        bars_to_failure = None
        failure_price = None

        for j, failure_bar in enumerate(failure_window):
            if failure_bar.close < ice_level:
                # Failure confirmed!
                bars_to_failure = j if j > 0 else 1  # Minimum 1 bar
                failure_price = failure_bar.close
                break

        if bars_to_failure is None:
            # No failure within 3 bars - might be genuine breakout
            logger.debug(
                "utad_no_failure",
                symbol=bar.symbol,
                breakout_timestamp=bar.timestamp.isoformat(),
                ice_level=float(ice_level),
                message="Price did not fail below Ice within 3 bars - not UTAD (genuine breakout?)",
            )
            continue  # Try next breakout candidate

        # ============================================================
        # CALCULATE CONFIDENCE SCORE
        # ============================================================

        confidence = _calculate_utad_confidence(
            breakout_pct=breakout_pct,
            volume_ratio=volume_ratio,
            bars_to_failure=bars_to_failure,
        )

        if confidence < MINIMUM_CONFIDENCE_THRESHOLD:
            logger.debug(
                "utad_low_confidence",
                symbol=bar.symbol,
                bar_timestamp=bar.timestamp.isoformat(),
                confidence=confidence,
                threshold=MINIMUM_CONFIDENCE_THRESHOLD,
                message=f"UTAD confidence {confidence} < {MINIMUM_CONFIDENCE_THRESHOLD} threshold",
            )
            continue  # Skip low-confidence patterns

        # ============================================================
        # CREATE UTAD INSTANCE (AC6.3)
        # ============================================================

        utad = UTAD(
            timestamp=bar.timestamp,
            breakout_price=bar.high,
            failure_price=failure_price,
            ice_level=ice_level,
            volume_ratio=volume_ratio,
            bars_to_failure=bars_to_failure,
            breakout_pct=breakout_pct,
            confidence=confidence,
            phase=phase,
            trading_range_id=trading_range.id,
            detection_timestamp=datetime.now(UTC),
            bar_index=i,
        )

        logger.info(
            "utad_detected",
            symbol=bar.symbol,
            utad_timestamp=bar.timestamp.isoformat(),
            breakout_pct=float(breakout_pct),
            volume_ratio=float(volume_ratio),
            bars_to_failure=bars_to_failure,
            ice_level=float(ice_level),
            phase=phase.value,
            confidence=confidence,
            quality_tier=utad.quality_tier,
            message=(
                f"UTAD detected: {breakout_pct*100:.2f}% break above Ice, "
                f"{volume_ratio:.2f}x volume, failed in {bars_to_failure} bars"
            ),
        )

        # Return first valid UTAD
        return utad

    # ============================================================
    # NO UTAD DETECTED
    # ============================================================

    logger.debug(
        "no_utad_detected",
        symbol=trading_range.symbol,
        phase=phase.value,
        bars_analyzed=len(bars),
        message="No valid UTAD pattern found in analyzed bars",
    )

    return None


def _calculate_utad_confidence(
    breakout_pct: Decimal,
    volume_ratio: Decimal,
    bars_to_failure: int,
) -> int:
    """
    Calculate UTAD pattern confidence score (70-100).

    Confidence Factors:
    - Breakout Size: Ideal 0.6-0.8% (80 pts), acceptable 0.5-1.0% (70 pts)
    - Volume Spike: >2.0x = excellent (90 pts), 1.7-2.0x = good (85 pts), 1.5-1.7x = acceptable (75 pts)
    - Failure Speed: 1-2 bars = rapid (90 pts), 3 bars = acceptable (80 pts)

    Args:
        breakout_pct: Breakout percentage above Ice
        volume_ratio: Volume ratio (>1.5x)
        bars_to_failure: Bars to failure (1-3)

    Returns:
        int: Confidence score (70-100)

    Example:
        >>> _calculate_utad_confidence(Decimal("0.007"), Decimal("2.2"), 2)
        88
    """
    # Base confidence
    confidence = 70

    # Breakout size scoring
    if Decimal("0.006") <= breakout_pct <= Decimal("0.008"):
        confidence += 10  # Ideal breakout size
    elif Decimal("0.005") <= breakout_pct <= Decimal("0.009"):
        confidence += 5  # Good breakout size

    # Volume spike scoring
    if volume_ratio >= Decimal("2.0"):
        confidence += 15  # Excellent volume spike
    elif volume_ratio >= Decimal("1.7"):
        confidence += 10  # Good volume spike

    # Failure speed scoring
    if bars_to_failure <= 2:
        confidence += 5  # Rapid failure

    return min(confidence, 100)  # Cap at 100


# Backward compatibility class for tests that expect object-oriented API
class UTADDetector:
    """
    Backward compatibility wrapper for UTAD detection.

    This class provides an object-oriented interface that wraps the
    functional `detect_utad()` API. Use this for legacy tests or code
    that expects a class-based detector.

    Deprecated: Use the functional `detect_utad()` API directly instead.
    This class will be removed in v0.3.0.

    Args:
        max_penetration_pct: Maximum breakout percentage (not used, for compatibility)
        min_volume_ratio: Minimum volume ratio (not used, for compatibility)
    """

    def __init__(
        self,
        max_penetration_pct: Optional[Decimal] = None,
        min_volume_ratio: Optional[Decimal] = None,
    ) -> None:
        """Initialize detector with optional config (compatibility only)."""
        # Store params for compatibility, but don't use them
        # The functional API has these hardcoded per FR6.2 requirements
        self.max_penetration_pct = max_penetration_pct or Decimal("1.0")
        self.min_volume_ratio = min_volume_ratio or Decimal("1.5")

    def detect(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        phase: WyckoffPhase,
        start_index: int = 20,
        skip_indices: Optional[set[int]] = None,
    ) -> Optional[UTAD]:
        """
        Detect UTAD pattern (wrapper for functional API).

        Args:
            trading_range: Trading range with Ice level
            bars: List of OHLCV bars to analyze
            phase: Current Wyckoff phase (D or E only)
            start_index: Minimum bars for volume baseline (default: 20)
            skip_indices: Bar indices to skip during detection

        Returns:
            UTAD instance if detected, None otherwise
        """
        return detect_utad(trading_range, bars, phase, start_index, skip_indices)

    def detect_utad(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        ice_level: Decimal,  # Compatibility: ice_level parameter for old API
        phase: Optional[WyckoffPhase] = None,
    ) -> Optional[UTAD]:
        """
        Legacy method signature for UTAD detection.

        Args:
            trading_range: Trading range with Ice level
            bars: List of OHLCV bars to analyze
            ice_level: Ice level (for backward compatibility - sets range.ice if missing)
            phase: Current Wyckoff phase (defaults to Phase E if not provided)

        Returns:
            UTAD instance if detected, None otherwise
        """
        # Default to Phase E for UTAD detection
        phase = phase or WyckoffPhase.E

        # Backward compatibility: If trading_range doesn't have ice set,
        # create a temporary IceLevel from the passed ice_level parameter
        if trading_range.ice is None:
            from datetime import UTC, datetime

            from src.models.ice_level import IceLevel

            # Create a minimal IceLevel with all required fields for backward compatibility
            # This supports legacy code that passes ice_level as a Decimal parameter
            now = datetime.now(UTC)
            trading_range.ice = IceLevel(
                price=ice_level,
                absolute_high=ice_level,  # Use same as price (no historical data available)
                touch_count=2,  # Minimum valid touch count
                touch_details=[],  # Empty list (no historical touch data available)
                strength_score=60,  # Moderate strength (60/100) for compatibility
                strength_rating="MODERATE",  # Corresponds to strength_score=60
                last_test_timestamp=now,
                first_test_timestamp=now,
                hold_duration=0,  # No historical duration data
                confidence="MEDIUM",  # Medium confidence for backward compat
                volume_trend="FLAT",  # Neutral volume trend (no data)
            )

        return detect_utad(trading_range, bars, phase)
