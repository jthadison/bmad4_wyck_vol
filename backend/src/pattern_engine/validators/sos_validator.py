"""
SOS (Sign of Strength) Breakout Validation Module

Purpose:
--------
Enforces volume expansion and spread expansion requirements for SOS breakout patterns.
Prevents low-volume false breakouts from generating signals (FR12 enforcement).

SOS Breakout Requirements:
--------------------------
- Volume expansion: minimum 1.5x average (FR12 - non-negotiable)
- Spread expansion: minimum 1.2x average (shows price conviction)
- Combined validation: high volume + wide spread = legitimate breakout

Volume Validation (AC 1, FR12):
--------------------------------
CRITICAL: Volume < 1.5x = immediate rejection (non-negotiable)

Volume Interpretation:
- <1.5x: Insufficient buying interest - FALSE BREAKOUT (reject)
- 1.5x-1.99x: Adequate confirmation - genuine breakout
- 2.0x-2.49x: Strong buying interest - high-quality breakout (AC 2)
- >=2.5x: Explosive buying - very strong breakout

Spread Validation (AC 3, 4):
-----------------------------
Narrow-spread breakouts are SUSPECT - suggests absorption at resistance.

Spread Interpretation:
- <1.0x: Spread contraction - very suspicious (selling into breakout)
- 1.0x-1.19x: Minimal expansion - suspect (AC 3)
- 1.2x-1.49x: Adequate expansion - acceptable (AC 4)
- >=1.5x: Wide spread - strong expansion (conviction)

Combined Validation (AC 5):
----------------------------
High volume + wide spread = legitimate breakout (best case)
- 2.5x volume + 1.8x spread: Excellent quality
- 2.0x volume + 1.5x spread: Ideal quality
- 1.5x volume + 1.2x spread: Acceptable quality

Compensation Scenarios:
- High volume (2.5x+) can compensate for narrow spread (1.1x)
- Wide spread (1.5x+) can compensate for moderate volume (1.6x)

Suspicious Patterns (reduce confidence):
- Low volume + narrow spread: likely false breakout
- 1.6x volume + 1.0x spread: suspicious quality
- CRITICAL: High volume (2.5x+) with narrow spread (<1.2x) is SUSPICIOUS
  This suggests absorption at resistance - smart money selling into breakout

FR12 Compliance:
----------------
- Volume validation is NON-NEGOTIABLE (AC 10)
- All rejections logged with specific threshold violated (AC 6)
- Rejection format: "SOS INVALID: Volume {ratio}x < 1.5x - insufficient confirmation (FR12)"

Usage:
------
>>> from src.pattern_engine.validators.sos_validator import SOSValidator
>>>
>>> validator = SOSValidator()
>>>
>>> # Validate SOS breakout
>>> is_valid, warning, result = validator.validate_sos_breakout(
>>>     bar=breakout_bar,
>>>     volume_ratio=Decimal("2.2"),
>>>     spread_ratio=Decimal("1.6"),
>>>     correlation_id="sos-detection-123"
>>> )
>>>
>>> if is_valid:
>>>     print(f"Valid SOS breakout: {result['quality']} quality")
>>>     print(f"Confidence impact: {result['confidence_impact']}")
>>> else:
>>>     print(f"Rejected: {warning}")

Integration:
------------
- Epic 2: VolumeAnalyzer and SpreadAnalyzer provide volume_ratio and spread_ratio
- Story 6.1: SOS breakout detection uses this validator FIRST
- Story 6.5: Confidence scoring uses validation quality metrics

Author: Story 6.2
"""

from __future__ import annotations

from decimal import Decimal

import structlog

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

logger = structlog.get_logger(__name__)


class SOSValidator:
    """
    SOS (Sign of Strength) Breakout Validator.

    Validates volume expansion and spread expansion requirements for SOS breakouts.
    Enforces FR12: volume < 1.5x = immediate rejection (non-negotiable).

    Constants:
    ----------
    VOLUME_MINIMUM_THRESHOLD: Decimal = 1.5 (AC 1 - minimum for SOS breakout)
    VOLUME_IDEAL_THRESHOLD: Decimal = 2.0 (AC 2 - very strong breakout)
    VOLUME_EXCELLENT_THRESHOLD: Decimal = 2.5 (excellent breakout)
    SPREAD_MINIMUM_THRESHOLD: Decimal = 1.2 (AC 4 - minimum spread expansion)
    SPREAD_IDEAL_THRESHOLD: Decimal = 1.5 (ideal spread expansion)

    Methods:
    --------
    validate_sos_volume: Volume validation FIRST (FR12 enforcement)
    classify_volume_quality: Volume quality classification
    validate_sos_spread: Spread validation with warnings
    validate_sos_breakout: Combined volume + spread validation
    get_sos_validation_summary: Comprehensive validation summary

    Example:
    --------
    >>> validator = SOSValidator()
    >>> is_valid, warning, result = validator.validate_sos_breakout(
    ...     bar=breakout_bar,
    ...     volume_ratio=Decimal("2.2"),
    ...     spread_ratio=Decimal("1.6"),
    ...     correlation_id="test-123"
    ... )
    >>> print(f"Quality: {result['quality']}, Confidence: {result['confidence_impact']}")
    """

    # Volume validation constants (AC 1, 2)
    VOLUME_MINIMUM_THRESHOLD = Decimal("1.5")  # AC 1: FR12 non-negotiable
    VOLUME_IDEAL_THRESHOLD = Decimal("2.0")  # AC 2: very strong breakout
    VOLUME_EXCELLENT_THRESHOLD = Decimal("2.5")

    # Spread validation constants (AC 4)
    SPREAD_MINIMUM_THRESHOLD = Decimal("1.2")  # AC 4: minimum spread expansion
    SPREAD_IDEAL_THRESHOLD = Decimal("1.5")

    def validate_sos_volume(
        self, bar: OHLCVBar, volume_ratio: Decimal, correlation_id: str
    ) -> tuple[bool, str | None]:
        """
        Validate SOS breakout volume expansion (FR12 enforcement).

        CRITICAL: Volume < 1.5x = immediate rejection (non-negotiable per FR12).
        This is the FIRST check in the SOS validation pipeline.

        Volume Interpretation:
        ----------------------
        - <1.5x: Insufficient buying interest - FALSE BREAKOUT (reject)
        - 1.5x-1.99x: Adequate confirmation - genuine breakout
        - 2.0x-2.49x: Strong buying interest - high-quality breakout
        - >=2.5x: Explosive buying - very strong breakout

        Parameters:
        -----------
        bar: OHLCVBar
            The breakout bar being validated
        volume_ratio: Decimal
            Current volume / 20-bar average volume
        correlation_id: str
            Correlation ID for distributed tracing

        Returns:
        --------
        Tuple[bool, str | None]
            - is_valid: True if volume >= 1.5x, False otherwise
            - rejection_reason: Reason string if rejected, None if valid

        Example:
        --------
        >>> validator = SOSValidator()
        >>> is_valid, reason = validator.validate_sos_volume(
        ...     bar=breakout_bar,
        ...     volume_ratio=Decimal("1.4"),
        ...     correlation_id="test-123"
        ... )
        >>> assert is_valid is False
        >>> assert "1.5x" in reason
        >>> assert "FR12" in reason
        """
        # AC 1: Volume check FIRST (before other validation)
        if volume_ratio < self.VOLUME_MINIMUM_THRESHOLD:
            rejection_reason = (
                f"SOS INVALID: Volume {volume_ratio:.2f}x < 1.5x - "
                f"insufficient confirmation (FR12)"
            )
            self._log_volume_rejection(bar, volume_ratio, rejection_reason, correlation_id)
            return (False, rejection_reason)

        # AC 2: Log successful validation with volume quality classification
        volume_quality = self.classify_volume_quality(volume_ratio)
        logger.info(
            "sos_volume_validation_passed",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            volume_ratio=str(volume_ratio),
            volume_quality=volume_quality,
            correlation_id=correlation_id,
        )

        return (True, None)

    def classify_volume_quality(self, volume_ratio: Decimal) -> str:
        """
        Classify volume quality for SOS breakouts.

        Volume Quality Levels (AC 2):
        -----------------------------
        - "insufficient": <1.5x (rejection - false breakout risk)
        - "acceptable": 1.5x-1.99x (passes but not ideal)
        - "ideal": 2.0x-2.49x (AC 2 - very strong breakout)
        - "excellent": >=2.5x (very high confidence)

        Parameters:
        -----------
        volume_ratio: Decimal
            Current volume / 20-bar average volume

        Returns:
        --------
        str
            Quality classification: "insufficient", "acceptable", "ideal", "excellent"

        Example:
        --------
        >>> validator = SOSValidator()
        >>> assert validator.classify_volume_quality(Decimal("1.4")) == "insufficient"
        >>> assert validator.classify_volume_quality(Decimal("1.8")) == "acceptable"
        >>> assert validator.classify_volume_quality(Decimal("2.2")) == "ideal"
        >>> assert validator.classify_volume_quality(Decimal("2.8")) == "excellent"
        """
        if volume_ratio < self.VOLUME_MINIMUM_THRESHOLD:
            return "insufficient"
        elif volume_ratio < self.VOLUME_IDEAL_THRESHOLD:
            return "acceptable"
        elif volume_ratio < self.VOLUME_EXCELLENT_THRESHOLD:
            return "ideal"
        else:
            return "excellent"

    def validate_sos_spread(
        self, bar: OHLCVBar, spread_ratio: Decimal, correlation_id: str
    ) -> tuple[bool, str | None, str]:
        """
        Validate SOS breakout spread expansion.

        Narrow-spread breakouts are SUSPECT - suggests absorption at resistance (AC 3).

        Spread Quality Levels:
        ----------------------
        - "insufficient": <1.0x (contraction - very suspicious)
        - "narrow": 1.0x-1.19x (minimal expansion - suspect per AC 3)
        - "acceptable": 1.2x-1.49x (adequate expansion - AC 4)
        - "wide": >=1.5x (strong expansion)

        Spread Interpretation:
        ----------------------
        - <1.0x: Spread contraction - very suspicious (selling into breakout)
        - 1.0x-1.19x: Minimal expansion - suspect (AC 3)
        - 1.2x-1.49x: Adequate expansion - acceptable (AC 4)
        - >=1.5x: Wide spread - strong expansion (conviction)

        Parameters:
        -----------
        bar: OHLCVBar
            The breakout bar being validated
        spread_ratio: Decimal
            Current spread / 20-bar average spread
        correlation_id: str
            Correlation ID for distributed tracing

        Returns:
        --------
        Tuple[bool, str | None, str]
            - is_valid: True (spread doesn't reject, only warns)
            - warning_reason: Warning string if narrow spread, None if acceptable
            - spread_quality: Quality classification string

        Example:
        --------
        >>> validator = SOSValidator()
        >>> is_valid, warning, quality = validator.validate_sos_spread(
        ...     bar=breakout_bar,
        ...     spread_ratio=Decimal("1.0"),
        ...     correlation_id="test-123"
        ... )
        >>> assert is_valid is True  # Doesn't reject, only warns
        >>> assert quality == "narrow"
        >>> assert "narrow" in warning.lower()
        """
        # AC 3, 4: Narrow-spread breakouts are SUSPECT but not immediately rejected
        if spread_ratio < Decimal("1.0"):
            # Contraction - very suspicious
            warning_reason = (
                f"SOS WARNING: Spread {spread_ratio:.2f}x < 1.0x - "
                f"spread contraction suggests absorption at resistance"
            )
            self._log_spread_warning(bar, spread_ratio, warning_reason, correlation_id)
            return (True, warning_reason, "insufficient")

        elif spread_ratio < self.SPREAD_MINIMUM_THRESHOLD:
            # AC 3: Narrow spread - suspect
            warning_reason = (
                f"SOS WARNING: Spread {spread_ratio:.2f}x < 1.2x - "
                f"narrow spread suggests absorption at resistance"
            )
            self._log_spread_warning(bar, spread_ratio, warning_reason, correlation_id)
            return (True, warning_reason, "narrow")

        elif spread_ratio < self.SPREAD_IDEAL_THRESHOLD:
            # AC 4: Acceptable spread
            return (True, None, "acceptable")

        else:
            # Wide spread - ideal
            return (True, None, "wide")

    def validate_sos_breakout(
        self,
        bar: OHLCVBar,
        volume_ratio: Decimal,
        spread_ratio: Decimal,
        correlation_id: str,
    ) -> tuple[bool, str | None, dict]:
        """
        Validate SOS breakout with combined volume and spread validation (AC 5).

        CRITICAL: Volume validation FIRST (FR12 non-negotiable).
        If volume fails: immediate rejection, skip spread validation.
        If volume passes: perform spread validation and combined quality assessment.

        Combined Validation Logic (AC 5):
        ----------------------------------
        - High volume (>=2.0x) + wide spread (>=1.5x) = "excellent" (high confidence)
        - High volume (>=2.5x) + narrow spread (1.0-1.2x) = "suspicious" (REVISED - not "good")
          This pattern suggests absorption at resistance - smart money selling into breakout
        - Wide spread compensates for moderate volume = "good" (moderate confidence)
        - Minimum requirements (1.5x vol + 1.2x spread) = "acceptable" (standard confidence)
        - Low volume + narrow spread = "suspicious" (low confidence - likely false breakout)

        Parameters:
        -----------
        bar: OHLCVBar
            The breakout bar being validated
        volume_ratio: Decimal
            Current volume / 20-bar average volume
        spread_ratio: Decimal
            Current spread / 20-bar average spread
        correlation_id: str
            Correlation ID for distributed tracing

        Returns:
        --------
        Tuple[bool, str | None, dict]
            - is_valid: True if volume >= 1.5x, False otherwise
            - warning: Warning message if issues detected, None otherwise
            - result: Dict with quality metrics:
                {
                    "quality": str,  # "excellent", "good", "acceptable", "suspicious"
                    "confidence_impact": str,  # "high", "moderate", "standard", "low"
                    "volume_quality": str,
                    "spread_quality": str,
                    "warnings": List[str]
                }

        Example:
        --------
        >>> validator = SOSValidator()
        >>> # Best case: high volume + wide spread
        >>> is_valid, warning, result = validator.validate_sos_breakout(
        ...     bar=breakout_bar,
        ...     volume_ratio=Decimal("2.5"),
        ...     spread_ratio=Decimal("1.8"),
        ...     correlation_id="test-123"
        ... )
        >>> assert is_valid is True
        >>> assert result["quality"] == "excellent"
        >>> assert result["confidence_impact"] == "high"
        """
        # STEP 1: Volume validation FIRST (CRITICAL - FR12)
        volume_valid, volume_rejection = self.validate_sos_volume(bar, volume_ratio, correlation_id)

        if not volume_valid:
            # Volume failed: immediate rejection (no need to check spread)
            return (False, volume_rejection, {})

        # STEP 2: Volume quality classification
        volume_quality = self.classify_volume_quality(volume_ratio)

        # STEP 3: Spread validation
        spread_valid, spread_warning, spread_quality = self.validate_sos_spread(
            bar, spread_ratio, correlation_id
        )

        # STEP 4: Combined validation logic (AC 5)
        warnings = []
        if spread_warning:
            warnings.append(spread_warning)

        # Determine combined quality based on volume and spread combinations
        # Check spread contraction (<1.0x) FIRST - always suspicious
        if spread_ratio < Decimal("1.0"):
            combined_quality = "suspicious"
            confidence_impact = "low"
            warning_msg = "Spread contraction suggests selling into breakout"
            if warning_msg not in warnings:
                warnings.append(warning_msg)

        # High volume (>=2.0x) + wide spread (>=1.5x) = excellent (best case)
        elif volume_ratio >= Decimal("2.0") and spread_ratio >= self.SPREAD_IDEAL_THRESHOLD:
            combined_quality = "excellent"
            confidence_impact = "high"

        # High volume (>=2.5x) + narrow spread (1.0-1.2x) = ACCEPTABLE WITH WARNING
        # CRITICAL: This suggests absorption at resistance
        elif (
            volume_ratio >= Decimal("2.5")
            and spread_ratio >= Decimal("1.0")
            and spread_ratio < self.SPREAD_MINIMUM_THRESHOLD
        ):
            combined_quality = "acceptable_with_warning"
            confidence_impact = "moderate_reduced"
            warning_msg = (
                "CAUTION: High volume with narrow spread suggests absorption at resistance"
            )
            if warning_msg not in warnings:
                warnings.append(warning_msg)

        # Moderate volume (2.0-2.5x) + narrow spread (1.0-1.2x) = SUSPICIOUS
        elif (
            volume_ratio >= Decimal("2.0")
            and volume_ratio < Decimal("2.5")
            and spread_ratio >= Decimal("1.0")
            and spread_ratio < self.SPREAD_MINIMUM_THRESHOLD
        ):
            combined_quality = "suspicious"
            confidence_impact = "low_moderate"
            warning_msg = "Narrow spread despite high volume suggests selling into breakout"
            if warning_msg not in warnings:
                warnings.append(warning_msg)

        # Wide spread (>=1.5x) compensates for moderate volume (1.5-2.0x)
        elif (
            volume_ratio >= self.VOLUME_MINIMUM_THRESHOLD
            and volume_ratio < Decimal("2.0")
            and spread_ratio >= self.SPREAD_IDEAL_THRESHOLD
        ):
            combined_quality = "good"
            confidence_impact = "moderate"

        # Minimum requirements met (volume >= 1.5, spread >= 1.2)
        elif (
            volume_ratio >= self.VOLUME_MINIMUM_THRESHOLD
            and spread_ratio >= self.SPREAD_MINIMUM_THRESHOLD
        ):
            combined_quality = "acceptable"
            confidence_impact = "standard"

        # Low volume (1.5-2.0x) + narrow spread (<1.2x) = SUSPICIOUS
        elif volume_ratio < Decimal("2.0") and spread_ratio < self.SPREAD_MINIMUM_THRESHOLD:
            combined_quality = "suspicious"
            confidence_impact = "low"
            warning_msg = "Low volume + narrow spread suggests false breakout"
            if warning_msg not in warnings:
                warnings.append(warning_msg)

        else:
            # Fallback: acceptable quality
            combined_quality = "acceptable"
            confidence_impact = "standard"

        # Build result dict
        result = {
            "quality": combined_quality,
            "confidence_impact": confidence_impact,
            "volume_quality": volume_quality,
            "spread_quality": spread_quality,
            "warnings": warnings,
        }

        # Log combined validation result
        self._log_validation_success(
            bar, volume_ratio, spread_ratio, combined_quality, correlation_id
        )

        # Return warning message (first warning if any)
        warning = warnings[0] if warnings else None
        return (True, warning, result)

    def get_sos_validation_summary(self, volume_ratio: Decimal, spread_ratio: Decimal) -> dict:
        """
        Get comprehensive validation summary for SOS breakout.

        Used by Story 6.1 for detailed logging and Story 6.5 for confidence scoring.

        Parameters:
        -----------
        volume_ratio: Decimal
            Current volume / 20-bar average volume
        spread_ratio: Decimal
            Current spread / 20-bar average spread

        Returns:
        --------
        dict
            Comprehensive summary with volume, spread, and combined metrics:
            {
                "volume": {
                    "ratio": Decimal,
                    "quality": str,
                    "is_valid": bool,
                    "threshold": Decimal,
                    "distance_from_threshold": Decimal
                },
                "spread": {
                    "ratio": Decimal,
                    "quality": str,
                    "is_valid": bool,
                    "threshold": Decimal,
                    "distance_from_threshold": Decimal
                },
                "combined": {
                    "overall_quality": str,
                    "confidence_impact": str,
                    "warnings": List[str]
                }
            }

        Example:
        --------
        >>> validator = SOSValidator()
        >>> summary = validator.get_sos_validation_summary(
        ...     volume_ratio=Decimal("2.2"),
        ...     spread_ratio=Decimal("1.6")
        ... )
        >>> print(summary["volume"]["quality"])  # "ideal"
        >>> print(summary["spread"]["quality"])  # "wide"
        >>> print(summary["combined"]["overall_quality"])  # "excellent"
        """
        # Volume metrics
        volume_quality = self.classify_volume_quality(volume_ratio)
        volume_valid = volume_ratio >= self.VOLUME_MINIMUM_THRESHOLD
        volume_distance = volume_ratio - self.VOLUME_MINIMUM_THRESHOLD

        # Spread metrics
        if spread_ratio < Decimal("1.0"):
            spread_quality = "insufficient"
        elif spread_ratio < self.SPREAD_MINIMUM_THRESHOLD:
            spread_quality = "narrow"
        elif spread_ratio < self.SPREAD_IDEAL_THRESHOLD:
            spread_quality = "acceptable"
        else:
            spread_quality = "wide"

        spread_valid = spread_ratio >= self.SPREAD_MINIMUM_THRESHOLD
        spread_distance = spread_ratio - self.SPREAD_MINIMUM_THRESHOLD

        # Combined quality (simplified logic without logging)
        warnings = []

        if volume_ratio >= Decimal("2.0") and spread_ratio >= self.SPREAD_IDEAL_THRESHOLD:
            overall_quality = "excellent"
            confidence_impact = "high"
        elif (
            volume_ratio >= Decimal("2.5")
            and spread_ratio >= Decimal("1.0")
            and spread_ratio < self.SPREAD_MINIMUM_THRESHOLD
        ):
            overall_quality = "acceptable_with_warning"
            confidence_impact = "moderate_reduced"
            warnings.append("High volume with narrow spread suggests absorption at resistance")
        elif (
            volume_ratio >= self.VOLUME_MINIMUM_THRESHOLD
            and spread_ratio >= self.SPREAD_IDEAL_THRESHOLD
        ):
            overall_quality = "good"
            confidence_impact = "moderate"
        elif (
            volume_ratio >= self.VOLUME_MINIMUM_THRESHOLD
            and spread_ratio >= self.SPREAD_MINIMUM_THRESHOLD
        ):
            overall_quality = "acceptable"
            confidence_impact = "standard"
        elif volume_ratio < Decimal("2.0") and spread_ratio < self.SPREAD_MINIMUM_THRESHOLD:
            overall_quality = "suspicious"
            confidence_impact = "low"
            warnings.append("Low volume + narrow spread suggests false breakout")
        elif (
            volume_ratio >= Decimal("2.0")
            and spread_ratio >= Decimal("1.0")
            and spread_ratio < self.SPREAD_MINIMUM_THRESHOLD
        ):
            overall_quality = "suspicious"
            confidence_impact = "low_moderate"
            warnings.append("Narrow spread despite high volume suggests selling into breakout")
        else:
            overall_quality = "acceptable"
            confidence_impact = "standard"

        return {
            "volume": {
                "ratio": volume_ratio,
                "quality": volume_quality,
                "is_valid": volume_valid,
                "threshold": self.VOLUME_MINIMUM_THRESHOLD,
                "distance_from_threshold": volume_distance,
            },
            "spread": {
                "ratio": spread_ratio,
                "quality": spread_quality,
                "is_valid": spread_valid,
                "threshold": self.SPREAD_MINIMUM_THRESHOLD,
                "distance_from_threshold": spread_distance,
            },
            "combined": {
                "overall_quality": overall_quality,
                "confidence_impact": confidence_impact,
                "warnings": warnings,
            },
        }

    # -------------------------------------------------------------------------
    # Private helper methods for FR12 compliance logging (AC 6, 10)
    # -------------------------------------------------------------------------

    def _log_volume_rejection(
        self, bar: OHLCVBar, volume_ratio: Decimal, rejection_reason: str, correlation_id: str
    ) -> None:
        """
        Log volume rejection with FR12 compliance marker (AC 6, 10).

        AC 10: All rejections logged to audit trail.
        AC 6: Specific threshold violated included in log.

        Parameters:
        -----------
        bar: OHLCVBar
            The bar being rejected
        volume_ratio: Decimal
            The volume ratio that failed validation
        rejection_reason: str
            The rejection reason string
        correlation_id: str
            Correlation ID for distributed tracing
        """
        logger.warning(
            "sos_volume_validation_failed",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            volume_ratio=str(volume_ratio),
            threshold_violated=str(self.VOLUME_MINIMUM_THRESHOLD),
            rejection_reason=rejection_reason,
            fr12_compliance="ENFORCED",  # AC 6, 10: FR12 compliance marker
            correlation_id=correlation_id,
        )

    def _log_spread_warning(
        self, bar: OHLCVBar, spread_ratio: Decimal, warning_reason: str, correlation_id: str
    ) -> None:
        """
        Log spread warning at INFO level (warnings, not rejections).

        Parameters:
        -----------
        bar: OHLCVBar
            The bar with narrow spread
        spread_ratio: Decimal
            The spread ratio that triggered warning
        warning_reason: str
            The warning reason string
        correlation_id: str
            Correlation ID for distributed tracing
        """
        logger.info(
            "sos_spread_warning",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            spread_ratio=str(spread_ratio),
            warning_reason=warning_reason,
            correlation_id=correlation_id,
        )

    def _log_validation_success(
        self,
        bar: OHLCVBar,
        volume_ratio: Decimal,
        spread_ratio: Decimal,
        quality: str,
        correlation_id: str,
    ) -> None:
        """
        Log successful validation at INFO level with quality classification.

        Parameters:
        -----------
        bar: OHLCVBar
            The validated bar
        volume_ratio: Decimal
            The volume ratio
        spread_ratio: Decimal
            The spread ratio
        quality: str
            The combined quality classification
        correlation_id: str
            Correlation ID for distributed tracing
        """
        logger.info(
            "sos_validation_passed",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            volume_ratio=str(volume_ratio),
            spread_ratio=str(spread_ratio),
            combined_quality=quality,
            correlation_id=correlation_id,
        )

    # -------------------------------------------------------------------------
    # Task 16: Integration with VolumeAnalyzer (AC all)
    # -------------------------------------------------------------------------

    def validate_sos_bar_with_context(
        self, bars: list[OHLCVBar], bar_index: int, correlation_id: str
    ) -> tuple[bool, str | None, dict]:
        """
        Validate SOS breakout using bar context for volume/spread calculation.

        This is a convenience wrapper that integrates with VolumeAnalyzer
        to calculate volume_ratio from historical context (20-bar average).
        Spread ratio is taken from the bar's pre-calculated spread_ratio field.

        Integration:
        ------------
        - Uses calculate_volume_ratio from VolumeAnalyzer (Epic 2, Story 2.5)
        - Uses spread_ratio field from OHLCVBar (pre-calculated)
        - Validates against SOS thresholds and returns combined result

        Parameters:
        -----------
        bars: List[OHLCVBar]
            List of bars in chronological order (context for ratio calculation)
        bar_index: int
            Index of the bar to validate (must have >= 20 bars before it)
        correlation_id: str
            Correlation ID for distributed tracing

        Returns:
        --------
        Tuple[bool, str | None, dict]
            Same as validate_sos_breakout:
            - is_valid: True if volume >= 1.5x, False otherwise
            - warning: Warning message if issues detected, None otherwise
            - result: Dict with quality metrics

        Raises:
        -------
        ValueError
            If bar_index < 20 (insufficient historical data)
            If bar_index >= len(bars) (invalid index)
            If volume_ratio calculation returns None

        Example:
        --------
        >>> validator = SOSValidator()
        >>> # Assume bars is a list of 50+ bars
        >>> is_valid, warning, result = validator.validate_sos_bar_with_context(
        ...     bars=bars,
        ...     bar_index=30,  # Validate bar at index 30
        ...     correlation_id="sos-detection-123"
        ... )
        >>> if is_valid:
        ...     print(f"Valid SOS: {result['quality']}")
        ... else:
        ...     print(f"Rejected: {warning}")

        Note:
        -----
        This function requires at least 20 bars before bar_index for volume
        ratio calculation. If bar_index < 20, ValueError is raised.
        """
        # Validate input
        if bar_index < 20:
            raise ValueError(
                f"bar_index must be >= 20 for volume ratio calculation, got {bar_index}"
            )
        if bar_index >= len(bars):
            raise ValueError(f"bar_index {bar_index} out of bounds for bars list (len={len(bars)})")

        bar = bars[bar_index]

        # Calculate volume ratio using VolumeAnalyzer (Epic 2 integration)
        volume_ratio_float = calculate_volume_ratio(bars, bar_index)
        if volume_ratio_float is None:
            raise ValueError(
                f"Failed to calculate volume_ratio for bar at index {bar_index} "
                f"(symbol={bar.symbol}, timestamp={bar.timestamp})"
            )

        volume_ratio = Decimal(str(volume_ratio_float))

        # Get spread ratio from bar (pre-calculated)
        spread_ratio = bar.spread_ratio

        # Validate SOS breakout with calculated ratios
        return self.validate_sos_breakout(bar, volume_ratio, spread_ratio, correlation_id)
