"""
Volume Anomaly Detector (Story 18.6.3)

Detects volume spike anomalies beyond news events. Catches flash crashes,
broker outages, 'fat finger' orders, and other non-Wyckoff volume spikes
that news event filtering misses.

Extracted from volume_validator.py per CF-006.

Author: Story 18.6.3
"""

from decimal import Decimal

import structlog

from src.models.validation import ValidationContext

logger = structlog.get_logger()


class VolumeAnomalyDetector:
    """
    Detects volume spike anomalies in forex data.

    Catches extreme volume spikes that are NOT normal Wyckoff activity:
    - Flash crashes
    - Broker outages
    - 'Fat finger' orders
    - Other non-institutional spikes

    Usage:
    ------
    >>> detector = VolumeAnomalyDetector()
    >>> is_anomaly, reason = await detector.check(context, volume_ratio)
    >>> if is_anomaly:
    ...     # Reject pattern due to anomalous volume
    ...     pass
    """

    # Volume spike threshold (5x is NEVER normal Wyckoff activity)
    ANOMALY_THRESHOLD = Decimal("5.0")

    async def check(
        self, context: ValidationContext, volume_ratio: Decimal
    ) -> tuple[bool, str | None]:
        """
        Detect volume spike anomalies.

        Parameters:
        -----------
        context : ValidationContext
            Context with volume_analysis
        volume_ratio : Decimal
            Current bar volume ratio

        Returns:
        --------
        tuple[bool, str | None]
            (is_anomaly, reason if anomaly detected)

        Example:
        --------
        >>> # 5.5x volume spike without news event
        >>> is_anomaly, reason = await detector.check(context, Decimal("5.5"))
        >>> print(is_anomaly)  # True
        >>> print(reason)      # "Volume spike 5.5x exceeds 5.0x anomaly threshold..."
        """
        # Only applies to forex (stocks have different spike characteristics)
        if context.asset_class != "FOREX":
            return False, None

        if volume_ratio >= self.ANOMALY_THRESHOLD:
            reason = (
                f"Volume spike {volume_ratio}x exceeds {self.ANOMALY_THRESHOLD}x anomaly threshold. "
                f"This is NOT normal Wyckoff activity - may be flash crash, broker outage, "
                f"or 'fat finger' order. Symbol: {context.symbol}, "
                f"Pattern bar: {context.pattern.pattern_bar_timestamp.isoformat()}"
            )
            logger.warning(
                "forex_volume_spike_anomaly",
                volume_ratio=float(volume_ratio),
                threshold=float(self.ANOMALY_THRESHOLD),
                symbol=context.symbol,
                pattern_type=context.pattern.pattern_type,
                pattern_bar=context.pattern.pattern_bar_timestamp.isoformat(),
            )
            return True, reason

        return False, None

    def build_rejection_metadata(self, volume_ratio: Decimal, context: ValidationContext) -> dict:
        """
        Build metadata for anomaly rejection.

        Parameters:
        -----------
        volume_ratio : Decimal
            Volume ratio that triggered anomaly
        context : ValidationContext
            Context with pattern info

        Returns:
        --------
        dict
            Metadata dictionary
        """
        return {
            "volume_ratio": float(volume_ratio),
            "anomaly_threshold": float(self.ANOMALY_THRESHOLD),
            "pattern_bar_timestamp": context.pattern.pattern_bar_timestamp.isoformat(),
            "symbol": context.symbol,
        }
