"""
Percentile Calculator (Story 18.6.3)

Calculates broker-relative percentiles for tick volume and provides
Wyckoff-aware interpretations. Tick volume varies by broker, so absolute
values are meaningless - percentile ranking within broker's own historical
data provides comparable measurements.

Extracted from volume_validator.py per CF-006.

Author: Story 18.6.3
"""

import bisect
from decimal import Decimal

import structlog

logger = structlog.get_logger()


class PercentileCalculator:
    """
    Calculates broker-relative volume percentiles.

    Tick volume varies by broker, so this class provides:
    1. Percentile ranking within broker's historical data
    2. Wyckoff-aware interpretation of percentile values

    Usage:
    ------
    >>> calculator = PercentileCalculator()
    >>> percentile = calculator.calculate(current_volume, historical_volumes)
    >>> interpretation = calculator.interpret(percentile, "SPRING")
    """

    def calculate(self, current_volume: Decimal, historical_volumes: list[Decimal]) -> int:
        """
        Calculate broker-relative percentile for tick volume.

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
        >>> calculator.calculate(Decimal("750"), historical)
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

        # Find position of current volume using bisect for O(log n) lookup
        # bisect_right returns insertion point after any equal values
        position = bisect.bisect_right(sorted_volumes, current_volume)

        # Calculate percentile (0-100)
        percentile = int((position / len(sorted_volumes)) * 100)

        logger.debug(
            "volume_percentile_calculated",
            current_volume=float(current_volume),
            percentile=percentile,
            sample_size=len(historical_volumes),
        )

        return percentile

    def interpret(self, percentile: int, pattern_type: str) -> str:
        """
        Generate human-readable interpretation of volume percentile.

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
        >>> calculator.interpret(15, "SPRING")
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
