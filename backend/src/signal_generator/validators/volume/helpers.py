"""
Volume Validation Helpers (Story 18.6.1)

Provides shared helper utilities for volume validation strategies:
- ValidationMetadataBuilder: Consistent metadata structure building
- Volume percentile calculations
- Wyckoff interpretation helpers

These utilities extract common patterns from the original volume_validator.py
to enable code reuse across pattern-specific strategies.

Reference: CF-006 from Critical Foundation Refactoring document.

Author: Story 18.6.1
"""

from decimal import Decimal
from typing import Any

import structlog

from src.models.validation import ValidationContext

logger = structlog.get_logger()


class ValidationMetadataBuilder:
    """
    Builder for consistent validation metadata structures.

    Provides a fluent interface for building metadata dictionaries
    with proper types and structure for volume validation results.

    Usage:
    ------
    >>> builder = ValidationMetadataBuilder()
    >>> metadata = (
    ...     builder
    ...     .with_volume_ratio(Decimal("0.65"))
    ...     .with_threshold(Decimal("0.70"))
    ...     .with_pattern_info("SPRING", context)
    ...     .with_forex_info(context)
    ...     .build()
    ... )

    Methods:
    --------
    - with_volume_ratio(ratio): Add actual volume ratio
    - with_threshold(threshold): Add threshold value
    - with_pattern_info(pattern_type, context): Add pattern metadata
    - with_forex_info(context): Add forex-specific metadata (session, percentile)
    - with_custom(key, value): Add custom metadata field
    - build(): Return completed metadata dict
    """

    def __init__(self) -> None:
        """Initialize empty metadata dictionary."""
        self._metadata: dict[str, Any] = {}

    def with_volume_ratio(self, volume_ratio: Decimal) -> "ValidationMetadataBuilder":
        """
        Add actual volume ratio to metadata.

        Parameters:
        -----------
        volume_ratio : Decimal
            Volume ratio being validated

        Returns:
        --------
        ValidationMetadataBuilder
            Self for method chaining
        """
        self._metadata["actual_volume_ratio"] = float(volume_ratio)
        return self

    def with_threshold(self, threshold: Decimal) -> "ValidationMetadataBuilder":
        """
        Add threshold value to metadata.

        Parameters:
        -----------
        threshold : Decimal
            Threshold used for comparison

        Returns:
        --------
        ValidationMetadataBuilder
            Self for method chaining
        """
        self._metadata["threshold"] = float(threshold)
        return self

    def with_pattern_info(
        self, pattern_type: str, context: ValidationContext
    ) -> "ValidationMetadataBuilder":
        """
        Add pattern and symbol information to metadata.

        Parameters:
        -----------
        pattern_type : str
            Pattern type being validated
        context : ValidationContext
            Context with pattern and symbol info

        Returns:
        --------
        ValidationMetadataBuilder
            Self for method chaining
        """
        self._metadata["pattern_type"] = pattern_type
        self._metadata["symbol"] = context.symbol
        self._metadata["asset_class"] = context.asset_class
        self._metadata["pattern_bar_timestamp"] = context.pattern.pattern_bar_timestamp.isoformat()
        return self

    def with_volume_source(self, asset_class: str) -> "ValidationMetadataBuilder":
        """
        Add volume source type (ACTUAL or TICK) based on asset class.

        Parameters:
        -----------
        asset_class : str
            Asset class (STOCK, FOREX, etc.)

        Returns:
        --------
        ValidationMetadataBuilder
            Self for method chaining
        """
        self._metadata["volume_source"] = "TICK" if asset_class == "FOREX" else "ACTUAL"
        return self

    def with_forex_info(self, context: ValidationContext) -> "ValidationMetadataBuilder":
        """
        Add forex-specific metadata if applicable.

        Includes session, volume percentile, and interpretation
        when context contains forex data.

        Parameters:
        -----------
        context : ValidationContext
            Context with forex_session and historical_volumes

        Returns:
        --------
        ValidationMetadataBuilder
            Self for method chaining
        """
        if context.asset_class != "FOREX":
            return self

        self._metadata["forex_session"] = (
            context.forex_session.value if context.forex_session else None
        )
        self._metadata["baseline_type"] = "session_average"

        # Add percentile if historical volumes available
        if context.historical_volumes and context.volume_analysis:
            current_volume = Decimal(str(context.volume_analysis.bar.volume))
            percentile = calculate_volume_percentile(current_volume, context.historical_volumes)
            self._metadata["volume_percentile"] = percentile

            # Add interpretation for pattern type if available
            pattern_type = self._metadata.get("pattern_type")
            if pattern_type:
                self._metadata["volume_interpretation"] = interpret_volume_percentile(
                    percentile, pattern_type
                )

        return self

    def with_custom(self, key: str, value: Any) -> "ValidationMetadataBuilder":
        """
        Add custom metadata field.

        Parameters:
        -----------
        key : str
            Metadata key
        value : Any
            Metadata value

        Returns:
        --------
        ValidationMetadataBuilder
            Self for method chaining
        """
        self._metadata[key] = value
        return self

    def build(self) -> dict[str, Any]:
        """
        Build and return the metadata dictionary.

        Returns:
        --------
        dict[str, Any]
            Completed metadata dictionary
        """
        return self._metadata.copy()


def calculate_volume_percentile(current_volume: Decimal, historical_volumes: list[Decimal]) -> int:
    """
    Calculate broker-relative percentile for tick volume (Story 8.3.1, AC 5).

    Tick volume varies by broker, so absolute values are meaningless.
    Percentile ranking within broker's own historical data provides
    comparable measurements.

    Parameters:
    -----------
    current_volume : Decimal
        Current bar tick volume
    historical_volumes : list[Decimal]
        Last 100+ bars of tick volume from same broker

    Returns:
    --------
    int
        Percentile (0-100) where current volume ranks

    Example:
    --------
    >>> historical = [Decimal(str(v)) for v in [500, 600, 700, 800, 900]]
    >>> calculate_volume_percentile(Decimal("750"), historical)
    60  # 750 is at 60th percentile (above 60% of historical bars)
    """
    if not historical_volumes:
        logger.warning(
            "volume_percentile_calculation_failed",
            reason="Empty historical volumes",
        )
        return 50  # Default to median if no data

    # Sort volumes in ascending order
    sorted_volumes = sorted(historical_volumes)

    # Find position of current volume
    position = sum(1 for v in sorted_volumes if v <= current_volume)

    # Calculate percentile (0-100)
    percentile = int((position / len(sorted_volumes)) * 100)

    logger.debug(
        "volume_percentile_calculated",
        current_volume=float(current_volume),
        percentile=percentile,
        sample_size=len(historical_volumes),
    )

    return percentile


def interpret_volume_percentile(percentile: int, pattern_type: str) -> str:
    """
    Generate human-readable interpretation of volume percentile (Wyckoff crew P2).

    Provides context-aware interpretation based on pattern type and
    Wyckoff principles (selling exhaustion, demand overwhelming supply, etc.).

    Parameters:
    -----------
    percentile : int
        Volume percentile (0-100)
    pattern_type : str
        Pattern type (SPRING, SOS, etc.)

    Returns:
    --------
    str
        Human-readable interpretation explaining what the percentile means

    Example:
    --------
    >>> interpret_volume_percentile(15, "SPRING")
    "Very low activity (bottom 15% of recent volume). This supports..."
    """
    if percentile < 10:
        if pattern_type == "SPRING":
            return (
                f"Extremely low activity (bottom {percentile}% of recent volume). "
                "This strongly supports the Wyckoff principle of 'selling exhaustion' - "
                "supply has dried up, indicating sellers are depleted."
            )
        else:
            return (
                f"Extremely low activity (bottom {percentile}% of recent volume). "
                "This is unusually quiet and may indicate lack of institutional participation."
            )

    elif percentile < 25:
        if pattern_type == "SPRING":
            return (
                f"Very low activity (bottom 25% of recent volume, specifically {percentile}th percentile). "
                "This supports 'selling exhaustion' - weak hands are exiting without conviction."
            )
        else:
            return (
                f"Very low activity (bottom 25%, specifically {percentile}th percentile). "
                "Below-average participation suggests caution."
            )

    elif percentile < 50:
        return (
            f"Below average activity ({percentile}th percentile). "
            f"Volume is in the lower half of recent history."
        )

    elif percentile < 75:
        if pattern_type == "SOS":
            return (
                f"Above average activity ({percentile}th percentile). "
                "This shows increased participation, supporting institutional accumulation."
            )
        else:
            return (
                f"Above average activity ({percentile}th percentile). "
                "Volume is in the upper half of recent history."
            )

    elif percentile < 90:
        if pattern_type == "SOS":
            return (
                f"High activity (top 25%, specifically {percentile}th percentile). "
                "Strong participation confirms demand overwhelming supply (Wyckoff 'sign of strength')."
            )
        else:
            return (
                f"High activity (top 25%, specifically {percentile}th percentile). "
                "This indicates elevated institutional interest."
            )

    else:  # percentile >= 90
        if pattern_type == "SOS":
            return (
                f"Climactic activity (top {100 - percentile}% of recent volume). "
                "Exceptional participation confirms institutional accumulation completing (Wyckoff climax)."
            )
        else:
            return (
                f"Climactic activity (top {100 - percentile}% of recent volume). "
                "This represents extreme participation and potential turning point."
            )


def build_failure_reason(
    pattern_type: str,
    volume_ratio: Decimal,
    threshold: Decimal,
    threshold_type: str,
    context: ValidationContext,
    volume_source: str = "ACTUAL",
) -> str:
    """
    Build consistent failure reason message for volume validation.

    Parameters:
    -----------
    pattern_type : str
        Pattern type being validated
    volume_ratio : Decimal
        Actual volume ratio
    threshold : Decimal
        Threshold value
    threshold_type : str
        "max" or "min" - determines comparison direction in message
    context : ValidationContext
        Context with symbol and pattern info
    volume_source : str
        "ACTUAL" or "TICK" for volume type description

    Returns:
    --------
    str
        Formatted failure reason message
    """
    source_label = volume_source.lower()

    if threshold_type == "max":
        comparison = f"{volume_ratio}x >= {threshold}x"
        direction = "too high"
    else:
        comparison = f"{volume_ratio}x < {threshold}x"
        direction = "too low"

    session_info = ""
    if context.asset_class == "FOREX" and context.forex_session:
        session_info = f", session: {context.forex_session.value}"

    return (
        f"{pattern_type} {source_label} volume {direction}: {comparison} threshold "
        f"(symbol: {context.symbol}{session_info}, "
        f"pattern_bar: {context.pattern.pattern_bar_timestamp.isoformat()})"
    )
