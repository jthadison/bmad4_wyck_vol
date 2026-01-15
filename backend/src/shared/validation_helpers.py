"""
Shared validation helpers for level calculator inputs.

Story 18.1: Extract Duplicate Validation Logic (CF-007)

This module eliminates duplicate validation logic between _validate_inputs()
and _validate_ice_inputs() in level_calculator.py by providing a single
parameterized validation function.

Validation Rules:
    - trading_range cannot be None
    - quality_score must be >= 70 (Story 3.3 requirement)
    - cluster must exist and have >= 2 touches
    - bars list cannot be empty
    - volume_analysis length must match bars length
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.models.ohlcv import OHLCVBar
    from src.models.trading_range import TradingRange
    from src.models.volume_analysis import VolumeAnalysis

logger = structlog.get_logger(__name__)

# Default minimum quality score required for level calculation
MIN_QUALITY_SCORE = 70
MIN_CLUSTER_TOUCHES = 2


def validate_level_calculator_inputs(
    trading_range: TradingRange | None,
    bars: list[OHLCVBar],
    volume_analysis: list[VolumeAnalysis],
    level_type: str,
    cluster_attr: str,
    min_quality: int = MIN_QUALITY_SCORE,
) -> None:
    """
    Validate inputs for Creek/Ice level calculations.

    This shared validation function replaces duplicate validation logic in
    _validate_inputs() and _validate_ice_inputs() from level_calculator.py.

    Args:
        trading_range: TradingRange to validate (must not be None)
        bars: List of OHLCV bars (must not be empty)
        volume_analysis: List of VolumeAnalysis matching bars (same length)
        level_type: Type of level being calculated ("Creek" or "Ice") for error messages
        cluster_attr: Attribute name to check ("support_cluster" or "resistance_cluster")
        min_quality: Minimum required quality score (default: 70)

    Raises:
        ValueError: If any validation fails

    Example:
        >>> validate_level_calculator_inputs(
        ...     trading_range, bars, volume_analysis,
        ...     level_type="Creek",
        ...     cluster_attr="support_cluster"
        ... )
    """
    # Validate trading_range exists
    if trading_range is None:
        raise ValueError("trading_range cannot be None")

    # Validate quality score >= min_quality (Story 3.3 requirement)
    if trading_range.quality_score is None or trading_range.quality_score < min_quality:
        logger.error(
            "low_quality_range",
            range_id=str(trading_range.id),
            quality_score=trading_range.quality_score,
            message=f"{level_type} calculation requires quality score >= {min_quality}",
        )
        raise ValueError(
            f"Cannot calculate {level_type.lower()} for range with quality score "
            f"{trading_range.quality_score} (minimum {min_quality})"
        )

    # Validate cluster exists and has minimum touches
    cluster = getattr(trading_range, cluster_attr, None)
    cluster_display_name = cluster_attr.replace("_", " ").title()

    if not cluster or cluster.touch_count < MIN_CLUSTER_TOUCHES:
        logger.error(
            f"invalid_{cluster_attr}",
            range_id=str(trading_range.id),
            message=f"{cluster_display_name} missing or insufficient touches",
        )
        raise ValueError(
            f"Invalid {cluster_attr.replace('_', ' ')} for {level_type.lower()} calculation "
            f"(minimum {MIN_CLUSTER_TOUCHES} touches required)"
        )

    # Validate bars not empty
    if not bars:
        raise ValueError("Bars list cannot be empty")

    # Validate volume_analysis matches bars
    if len(volume_analysis) != len(bars):
        logger.error(
            "bars_volume_mismatch",
            bars_count=len(bars),
            volume_count=len(volume_analysis),
        )
        raise ValueError(
            f"Bars and volume_analysis length mismatch ({len(bars)} vs {len(volume_analysis)})"
        )
