"""
Quality-Based Position Sizing Module

Purpose:
--------
Integrates range quality scoring with position sizing and Relative Strength (RS)
filters to optimize position sizes based on setup quality and market leadership.

Story 11.9f: Quality Position Sizing Integration (Team Enhancement)

Position Sizing Rules:
----------------------
Quality Multipliers:
- EXCELLENT (80-100): 1.0x (100% of base position)
- GOOD (60-79): 0.75x (75% of base position)
- FAIR (40-59): 0.5x (50% of base position)
- POOR (0-39): 0.25x (25% of base position or skip)

RS Multipliers:
- Sector leader (top 20% RS): +20% (1.2x)
- Market leader (beating SPY): +10% (1.1x)
- Underperformer (negative RS): -20% (0.8x)

Combined multipliers capped at 1.5x maximum (risk control)

Usage:
------
>>> from src.pattern_engine.position_sizer import QualityPositionSizer
>>> from src.pattern_engine.range_quality import RangeQualityScore
>>> from decimal import Decimal
>>>
>>> sizer = QualityPositionSizer()
>>> base_size = Decimal("100")  # Base position: 100 shares
>>>
>>> # EXCELLENT quality, sector leader
>>> score = RangeQualityScore(total_score=85, ...)
>>> position = sizer.calculate_position_size(
...     base_size=base_size,
...     quality_score=score,
...     is_sector_leader=True
... )
>>> # Result: 120 shares (1.0 quality × 1.2 sector leader = 1.2x, capped at 1.5x)

Author: Story 11.9f - Quality Position Sizing Integration
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Quality multipliers based on range quality grade
QUALITY_MULTIPLIERS = {
    "EXCELLENT": Decimal("1.0"),  # 100% of base position
    "GOOD": Decimal("0.75"),  # 75% of base position
    "FAIR": Decimal("0.50"),  # 50% of base position
    "POOR": Decimal("0.25"),  # 25% of base position (or skip)
}

# RS (Relative Strength) multipliers
RS_MULTIPLIERS = {
    "sector_leader": Decimal("1.2"),  # +20% for top 20% RS
    "market_leader": Decimal("1.1"),  # +10% for beating SPY
    "underperformer": Decimal("0.8"),  # -20% for negative RS
}

# Maximum combined multiplier (risk control)
MAX_MULTIPLIER = Decimal("1.5")


class QualityPositionSizer:
    """
    Quality-based position sizer with RS integration.

    Calculates position sizes by combining range quality grades with
    Relative Strength (RS) analysis to favor high-quality setups in
    strong stocks.

    Example:
        >>> sizer = QualityPositionSizer()
        >>> # EXCELLENT quality, sector leader
        >>> position = sizer.calculate_position_size(
        ...     base_size=Decimal("100"),
        ...     quality_grade="EXCELLENT",
        ...     is_sector_leader=True
        ... )
        >>> print(f"Position size: {position} shares")
        Position size: 120 shares
    """

    def __init__(self) -> None:
        """Initialize quality position sizer."""
        logger.debug("quality_position_sizer_initialized")

    def calculate_position_size(
        self,
        base_size: Decimal,
        quality_score: Optional[object] = None,
        quality_grade: Optional[str] = None,
        rs_score: Optional[Decimal] = None,
        is_sector_leader: bool = False,
        is_market_leader: bool = False,
    ) -> Decimal:
        """
        Calculate position size with quality and RS adjustments.

        Args:
            base_size: Base position size (shares/contracts)
            quality_score: RangeQualityScore object (optional, will use quality_grade if provided)
            quality_grade: Quality grade string (EXCELLENT/GOOD/FAIR/POOR)
            rs_score: RS score for manual classification (optional)
            is_sector_leader: True if stock is in top 20% RS for sector
            is_market_leader: True if stock is beating SPY

        Returns:
            Adjusted position size (shares/contracts)

        Example:
            >>> # Using quality_score object
            >>> from src.pattern_engine.range_quality import RangeQualityScore
            >>> score = RangeQualityScore(total_score=85, ...)
            >>> size = sizer.calculate_position_size(
            ...     base_size=Decimal("100"),
            ...     quality_score=score,
            ...     is_sector_leader=True
            ... )
            >>>
            >>> # Using quality_grade directly
            >>> size = sizer.calculate_position_size(
            ...     base_size=Decimal("100"),
            ...     quality_grade="EXCELLENT",
            ...     is_market_leader=True
            ... )
        """
        # Extract quality grade
        if quality_score is not None and hasattr(quality_score, "quality_grade"):
            grade = quality_score.quality_grade
        elif quality_grade is not None:
            grade = quality_grade
        else:
            logger.error(
                "missing_quality_input",
                message="Either quality_score or quality_grade must be provided",
            )
            return Decimal("0")

        # Get quality multiplier
        quality_multiplier = QUALITY_MULTIPLIERS.get(grade, Decimal("0.5"))

        # Get RS multiplier
        rs_multiplier = self._calculate_rs_multiplier(
            rs_score=rs_score,
            is_sector_leader=is_sector_leader,
            is_market_leader=is_market_leader,
        )

        # Calculate combined multiplier
        combined_multiplier = quality_multiplier * rs_multiplier

        # Cap at maximum multiplier (risk control)
        if combined_multiplier > MAX_MULTIPLIER:
            logger.debug(
                "multiplier_capped",
                original_multiplier=float(combined_multiplier),
                capped_multiplier=float(MAX_MULTIPLIER),
            )
            combined_multiplier = MAX_MULTIPLIER

        # Calculate final position size
        position_size = base_size * combined_multiplier

        logger.info(
            "position_size_calculated",
            base_size=float(base_size),
            quality_grade=grade,
            quality_multiplier=float(quality_multiplier),
            rs_multiplier=float(rs_multiplier),
            combined_multiplier=float(combined_multiplier),
            position_size=float(position_size),
            is_sector_leader=is_sector_leader,
            is_market_leader=is_market_leader,
        )

        return position_size

    def _calculate_rs_multiplier(
        self,
        rs_score: Optional[Decimal],
        is_sector_leader: bool,
        is_market_leader: bool,
    ) -> Decimal:
        """
        Calculate RS multiplier based on relative strength.

        Args:
            rs_score: RS score (optional, for manual classification)
            is_sector_leader: True if top 20% RS in sector
            is_market_leader: True if beating SPY

        Returns:
            RS multiplier (0.8 to 1.2)

        Priority:
            1. Sector leader (strongest signal)
            2. Market leader
            3. RS score analysis
            4. Default 1.0 (neutral)
        """
        # Sector leader gets highest priority
        if is_sector_leader:
            return RS_MULTIPLIERS["sector_leader"]

        # Market leader (beating SPY)
        if is_market_leader:
            return RS_MULTIPLIERS["market_leader"]

        # RS score analysis (if provided)
        if rs_score is not None:
            if rs_score < 0:
                return RS_MULTIPLIERS["underperformer"]
            elif rs_score > Decimal("0.8"):
                return RS_MULTIPLIERS["sector_leader"]
            elif rs_score > Decimal("0.5"):
                return RS_MULTIPLIERS["market_leader"]

        # Default: neutral (1.0x)
        return Decimal("1.0")
