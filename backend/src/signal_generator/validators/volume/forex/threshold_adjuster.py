"""
Forex Threshold Adjuster (Story 18.6.3)

Provides session-aware threshold adjustments for forex volume validation.
Different trading sessions (Asian, London, NY, Overlap) have different
liquidity profiles requiring adjusted thresholds.

Extracted from volume_validator.py per CF-006.

Author: Story 18.6.3
"""

from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import structlog
import yaml

from src.models.forex import ForexSession
from src.models.validation import ValidationContext, VolumeValidationConfig

logger = structlog.get_logger()


class ForexThresholdAdjuster:
    """
    Adjusts volume thresholds based on forex session.

    Different forex sessions have different liquidity profiles:
    - Asian: Low liquidity, stricter thresholds
    - London/NY/Overlap: Normal liquidity, standard thresholds

    Also supports session-specific overrides from YAML config (Story 9.1).

    Usage:
    ------
    >>> adjuster = ForexThresholdAdjuster()
    >>> threshold = adjuster.get_threshold("SPRING", "max", config, context)
    """

    # Class-level cache for YAML config (Story 9.1)
    _threshold_config_cache: Optional[dict[str, Any]] = None

    @classmethod
    def _load_volume_thresholds_from_config(cls) -> dict[str, Any]:
        """
        Load volume thresholds from YAML configuration file (Story 9.1).

        Returns cached config if available, otherwise loads from file.

        Returns:
        --------
        dict[str, Any]
            Threshold configuration including forex_session_overrides
        """
        # Return cached config if available
        if cls._threshold_config_cache is not None:
            return cls._threshold_config_cache

        # Locate config file
        config_path = (
            Path(__file__).parent.parent.parent.parent.parent / "config" / "volume_thresholds.yaml"
        )

        if not config_path.exists():
            logger.warning(
                "volume_thresholds_config_not_found",
                config_path=str(config_path),
                note="Using VolumeValidationConfig defaults",
            )
            cls._threshold_config_cache = {}
            return cls._threshold_config_cache

        # Load YAML
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            logger.info(
                "volume_thresholds_config_loaded",
                config_path=str(config_path),
                has_session_overrides="forex_session_overrides" in config,
            )

            # Cache the config
            cls._threshold_config_cache = config
            return config

        except Exception as e:
            logger.error(
                "volume_thresholds_config_load_error",
                config_path=str(config_path),
                error=str(e),
            )
            cls._threshold_config_cache = {}
            return cls._threshold_config_cache

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the threshold config cache (for testing)."""
        cls._threshold_config_cache = None

    def get_threshold(
        self,
        pattern_type: str,
        threshold_type: str,
        config: VolumeValidationConfig,
        context: ValidationContext,
    ) -> Decimal:
        """
        Get forex-specific threshold with session adjustments.

        Applies session-based adjustments:
        - Asian session: Stricter thresholds (low liquidity)
        - UTAD: Session-specific optimized thresholds from YAML config (Story 9.1)

        Parameters:
        -----------
        pattern_type : str
            Pattern type (SPRING, SOS, UTAD, etc.)
        threshold_type : str
            "max" or "min"
        config : VolumeValidationConfig
            VolumeValidationConfig with forex thresholds
        context : ValidationContext
            Context with forex_session

        Returns:
        --------
        Decimal
            Session-adjusted threshold

        Example:
        --------
        >>> # UTAD during OVERLAP session (Story 9.1 optimization)
        >>> threshold = adjuster.get_threshold("UTAD", "min", config, context)
        >>> print(threshold)  # Decimal("2.20") - optimized from 2.50!
        """
        forex_session = context.forex_session

        # Story 9.1: Check for session-specific UTAD threshold overrides
        if pattern_type == "UTAD" and threshold_type == "min":
            yaml_config = self._load_volume_thresholds_from_config()
            overrides = yaml_config.get("forex_session_overrides", {})

            if overrides and forex_session is not None:
                session_name = forex_session.value
                session_override = overrides.get(session_name, {})

                if "utad_min_volume" in session_override:
                    override_threshold = Decimal(str(session_override["utad_min_volume"]))

                    logger.debug(
                        "forex_utad_session_override_applied",
                        session=session_name,
                        baseline_threshold=float(config.forex_utad_min_volume),
                        override_threshold=float(override_threshold),
                        story="9.1",
                    )

                    return override_threshold

            # Fall through to baseline if no override found
            return config.forex_utad_min_volume

        # Asian session uses stricter thresholds (low liquidity) - Story 8.3.1
        if forex_session == ForexSession.ASIAN:
            if pattern_type == "SPRING" and threshold_type == "max":
                return config.forex_asian_spring_max_volume
            elif pattern_type == "SOS" and threshold_type == "min":
                return config.forex_asian_sos_min_volume

        # All other sessions use standard forex thresholds
        if pattern_type == "SPRING" and threshold_type == "max":
            return config.forex_spring_max_volume
        elif pattern_type == "TEST" and threshold_type == "max":
            return config.forex_test_max_volume
        elif pattern_type == "SOS" and threshold_type == "min":
            return config.forex_sos_min_volume
        elif pattern_type == "UTAD" and threshold_type == "min":
            return config.forex_utad_min_volume
        else:
            # Fallback to stock thresholds if unknown pattern
            if threshold_type == "max":
                return config.spring_max_volume
            else:
                return config.sos_min_volume
