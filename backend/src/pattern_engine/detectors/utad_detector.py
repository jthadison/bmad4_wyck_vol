"""
UTAD (Upthrust After Distribution) Detector Module

Purpose:
--------
Detects UTAD patterns - the distribution counterpart to Spring detection.
UTAD represents a false breakout above Ice (resistance) on high volume that
quickly fails back below Ice, signaling distribution and potential short opportunities.

Story 11.9e: UTAD Detector Implementation (Team Enhancement)

Detection Criteria:
-------------------
1. Penetration above Ice level (0-5% maximum upward thrust)
2. High volume (>1.5x average) - indicates professional selling
3. Price fails back below Ice within 1-5 bars
4. Preliminary Supply (PS) events present 10-20 bars before UTAD

Volume Requirement (Critical):
------------------------------
- ≥1.5x average volume: Distribution signal (professional selling into demand)
- <1.5x average volume: Breakout, NOT UTAD

Usage:
------
>>> from src.pattern_engine.detectors.utad_detector import UTADDetector
>>> from decimal import Decimal
>>>
>>> detector = UTADDetector(max_penetration_pct=Decimal("5.0"))
>>> utad = detector.detect_utad(trading_range, bars, ice_level)
>>>
>>> if utad:
...     print(f"UTAD detected: {utad.penetration_pct:.2%} above Ice")
...     print(f"Volume: {utad.volume_ratio:.2f}x (high volume = distribution)")
...     print(f"Failed within {utad.failure_bar_index - utad.utad_bar_index} bars")

Author: Story 11.9e - UTAD Detector Implementation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

if TYPE_CHECKING:
    from src.models.phase_classification import WyckoffPhase

logger = structlog.get_logger(__name__)


@dataclass
class UTAD:
    """
    UTAD (Upthrust After Distribution) pattern data structure.

    Represents a false breakout above Ice on high volume that quickly fails,
    signaling distribution and potential bearish reversal.

    Attributes:
        utad_bar_index: Index of the UTAD bar (thrust above Ice)
        utad_timestamp: Timestamp of the UTAD event
        utad_high: Highest price during UTAD thrust
        ice_level: Ice resistance level that was penetrated
        penetration_pct: Percentage penetration above Ice (0-5%)
        volume_ratio: Volume ratio (should be >1.5x for valid UTAD)
        failure_bar_index: Index where price failed back below Ice
        confidence: Confidence score (0-100)
        preliminary_supply_count: Number of PS events before UTAD
    """

    utad_bar_index: int
    utad_timestamp: datetime
    utad_high: Decimal
    ice_level: Decimal
    penetration_pct: Decimal
    volume_ratio: Decimal
    failure_bar_index: int
    confidence: int
    preliminary_supply_count: int


class UTADDetector:
    """
    UTAD (Upthrust After Distribution) pattern detector.

    Detects false breakouts above Ice (resistance) that quickly fail back below,
    signaling distribution and potential short opportunities. This is the bearish
    counterpart to Spring detection.

    Attributes:
        max_penetration_pct: Maximum allowed penetration above Ice (default: 5.0%)

    Example:
        >>> detector = UTADDetector(max_penetration_pct=Decimal("5.0"))
        >>> utad = detector.detect_utad(trading_range, bars, ice_level)
        >>> if utad and utad.confidence >= 70:
        ...     print("High-confidence UTAD detected - distribution signal")
    """

    def __init__(self, max_penetration_pct: Decimal = Decimal("5.0")) -> None:
        """
        Initialize UTAD detector.

        Args:
            max_penetration_pct: Maximum penetration above Ice as percentage (default: 5.0)

        Raises:
            ValueError: If max_penetration_pct is outside valid range (0-10)
        """
        if max_penetration_pct <= 0 or max_penetration_pct > 10:
            raise ValueError(f"max_penetration_pct must be 0-10, got {max_penetration_pct}")

        self.max_penetration_pct = max_penetration_pct

        logger.debug(
            "utad_detector_initialized",
            max_penetration_pct=float(max_penetration_pct),
        )

    def detect_utad(
        self,
        trading_range: TradingRange,
        bars: list[OHLCVBar],
        ice_level: Decimal,
        phase: Optional[WyckoffPhase] = None,
    ) -> Optional[UTAD]:
        """
        Detect UTAD pattern (distribution).

        Scans for false breakouts above Ice that quickly fail back below,
        indicating professional selling and potential distribution.

        Args:
            trading_range: Trading range to analyze
            bars: OHLCV bars to scan (minimum 20 bars for volume calculation)
            ice_level: Ice resistance level to check for penetration
            phase: Current Wyckoff phase (should be Phase D for valid UTAD).
                When None, phase validation is skipped for backward compatibility.

        Returns:
            UTAD instance if valid pattern detected, None otherwise

        Detection Steps:
            1. Validate phase is D (if provided)
            2. Scan last 20 bars for penetration above Ice
            3. Validate volume >1.5x average (high volume = distribution)
            4. Confirm failure back below Ice within 1-5 bars
            5. Count Preliminary Supply events 10-20 bars before UTAD
            6. Calculate confidence score

        Example:
            >>> utad = detector.detect_utad(range, bars, Decimal("175.50"), phase=WyckoffPhase.D)
            >>> if utad:
            ...     print(f"UTAD at ${utad.utad_high} ({utad.confidence}% confidence)")
        """
        try:
            # Input validation
            if not bars:
                logger.debug("utad_detection_skipped", reason="empty_bars")
                return None

            if len(bars) < 20:
                logger.debug(
                    "utad_detection_skipped",
                    reason="insufficient_bars",
                    bar_count=len(bars),
                )
                return None

            if ice_level <= 0:
                logger.error("invalid_ice_level", ice_level=str(ice_level))
                return None

            # Phase validation (FR15): UTAD is only valid in Phase D
            if phase is not None:
                from src.models.phase_classification import WyckoffPhase as WP

                if phase != WP.D:
                    logger.warning(
                        "utad_wrong_phase",
                        phase=phase.value,
                        required="D",
                        message=f"UTAD rejected: Phase {phase.value} (requires Phase D)",
                    )
                    return None
            else:
                logger.info(
                    "utad_phase_not_provided",
                    message="Phase not provided - skipping phase validation for backward compatibility",
                )

            # Scan last 20 bars for UTAD candidates
            for i in range(len(bars) - 20, len(bars)):
                bar = bars[i]

                # Check for penetration above Ice
                if bar.high <= ice_level:
                    continue

                # Calculate penetration percentage
                penetration_pct = ((bar.high - ice_level) / ice_level) * 100

                # Validate penetration within limits (0-5%)
                if penetration_pct > self.max_penetration_pct:
                    continue

                # Calculate volume ratio
                volume_ratio = calculate_volume_ratio(bars, i)
                if volume_ratio is None:
                    continue

                # Validate high volume (>1.5x required for UTAD)
                if volume_ratio < 1.5:
                    continue  # Low volume = breakout, not UTAD

                # Check for failure back below Ice within 1-5 bars
                failure_bar_index = None
                for j in range(i + 1, min(i + 6, len(bars))):
                    if bars[j].close < ice_level:
                        failure_bar_index = j
                        break

                if failure_bar_index is None:
                    continue  # No failure = valid breakout, not UTAD

                # Count Preliminary Supply events (high volume bars 10-20 bars before)
                ps_count = 0
                if i >= 20:
                    for k in range(i - 20, i - 10):
                        ps_volume_ratio = calculate_volume_ratio(bars, k)
                        if ps_volume_ratio and ps_volume_ratio >= 1.3:
                            ps_count += 1

                # Calculate confidence score
                confidence = self._calculate_confidence(
                    penetration_pct,
                    volume_ratio,
                    failure_bar_index - i,
                    ps_count,
                )

                # Return first valid UTAD found
                utad = UTAD(
                    utad_bar_index=i,
                    utad_timestamp=bar.timestamp,
                    utad_high=bar.high,
                    ice_level=ice_level,
                    penetration_pct=penetration_pct,
                    volume_ratio=Decimal(str(volume_ratio)),
                    failure_bar_index=failure_bar_index,
                    confidence=confidence,
                    preliminary_supply_count=ps_count,
                )

                logger.info(
                    "utad_detected",
                    utad_bar_index=i,
                    penetration_pct=float(penetration_pct),
                    volume_ratio=volume_ratio,
                    failure_bars=failure_bar_index - i,
                    ps_count=ps_count,
                    confidence=confidence,
                )

                return utad

            # No UTAD found
            logger.debug("no_utad_detected", bars_scanned=len(bars))
            return None

        except Exception as e:
            logger.error("utad_detection_failed", error=str(e))
            return None

    def _calculate_confidence(
        self,
        penetration_pct: Decimal,
        volume_ratio: float,
        failure_bars: int,
        ps_count: int,
    ) -> int:
        """
        Calculate UTAD confidence score (0-100).

        Args:
            penetration_pct: Percentage penetration above Ice
            volume_ratio: Volume ratio (higher = more distribution)
            failure_bars: Number of bars until failure (fewer = stronger)
            ps_count: Count of Preliminary Supply events

        Returns:
            Confidence score 0-100

        Scoring:
            - Base: 60 points (valid UTAD detected)
            - Volume bonus: +10 points if ≥2.0x (very high volume)
            - Failure speed bonus: +10 points if fails within 2 bars
            - PS bonus: +10 points if 3+ PS events
            - Penetration bonus: +10 points if <2% penetration (tight false breakout)
        """
        confidence = 60  # Base score for valid UTAD

        # Volume bonus (higher volume = more distribution)
        if volume_ratio >= 2.0:
            confidence += 10

        # Failure speed bonus (faster failure = stronger distribution)
        if failure_bars <= 2:
            confidence += 10

        # Preliminary Supply bonus
        if ps_count >= 3:
            confidence += 10

        # Tight penetration bonus (smaller thrust = cleaner UTAD)
        if penetration_pct < Decimal("2.0"):
            confidence += 10

        return min(confidence, 100)
