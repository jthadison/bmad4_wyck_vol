"""Wyckoff algorithm implementations for Story 11.5.1.

Schematic matching and P&F counting algorithms.
"""

from datetime import datetime
from typing import Optional

import structlog
from backend.src.models.chart import (
    SCHEMATIC_TEMPLATES,
    CauseBuildingData,
    TradingRangeLevels,
    WyckoffSchematic,
)
from backend.src.orm.models import (
    OHLCVBar as OHLCVBarORM,
)
from backend.src.orm.models import (
    Pattern as PatternORM,
)
from backend.src.orm.models import (
    TradingRange as TradingRangeORM,
)
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def match_wyckoff_schematic(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    creek_level: Optional[float] = None,
    ice_level: Optional[float] = None,
) -> Optional[WyckoffSchematic]:
    """Match detected patterns to Wyckoff schematic templates.

    Story 11.5.1 AC 1, 7: Schematic matching algorithm.

    Args:
        session: Database session
        symbol: Ticker symbol
        timeframe: Bar interval (1D/1W/1M)
        start_date: Start date
        end_date: End date
        creek_level: Support level (for normalization)
        ice_level: Resistance level (for normalization)

    Returns:
        WyckoffSchematic if match found (confidence >= 60%), else None
    """
    # Map timeframe to database format
    timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1mo"}
    db_timeframe = timeframe_map.get(timeframe, "1d")

    # Query detected patterns
    query = (
        select(PatternORM)
        .where(
            and_(
                PatternORM.symbol == symbol,
                PatternORM.timeframe == db_timeframe,
                PatternORM.pattern_bar_timestamp >= start_date,
                PatternORM.pattern_bar_timestamp <= end_date,
                PatternORM.confidence_score >= 70,  # Test-confirmed patterns only
            )
        )
        .order_by(PatternORM.pattern_bar_timestamp.asc())
    )

    result = await session.execute(query)
    patterns = result.scalars().all()

    if not patterns:
        logger.debug("No patterns found for schematic matching", symbol=symbol)
        return None

    # Extract pattern sequence
    pattern_types = [p.pattern_type for p in patterns]

    # Determine accumulation vs distribution
    has_spring = "SPRING" in pattern_types
    has_utad = "UTAD" in pattern_types
    has_sos = "SOS" in pattern_types
    has_sow = "SOW" in pattern_types or "LPSY" in pattern_types

    # Match to schematic templates
    best_match = None
    best_confidence = 0

    for schematic_type, template in SCHEMATIC_TEMPLATES.items():
        confidence = _calculate_schematic_confidence(
            patterns, schematic_type, creek_level, ice_level
        )

        if confidence > best_confidence and confidence >= 60:
            best_confidence = confidence
            best_match = (schematic_type, template)

    if not best_match:
        logger.debug("No schematic match with sufficient confidence", symbol=symbol)
        return None

    schematic_type, template = best_match

    return WyckoffSchematic(
        schematic_type=schematic_type, confidence_score=int(best_confidence), template_data=template
    )


def _calculate_schematic_confidence(
    patterns: list[PatternORM],
    schematic_type: str,
    creek_level: Optional[float],
    ice_level: Optional[float],
) -> float:
    """Calculate confidence score for schematic match.

    Args:
        patterns: Detected patterns
        schematic_type: Template type
        creek_level: Support level
        ice_level: Resistance level

    Returns:
        Confidence score (0-100)
    """
    pattern_types = [p.pattern_type for p in patterns]

    # Define expected pattern sequences for each schematic
    expected_sequences = {
        "ACCUMULATION_1": ["PS", "SC", "AR", "ST", "SPRING", "SOS"],
        "ACCUMULATION_2": ["PS", "SC", "AR", "ST", "LPS", "SOS"],
        "DISTRIBUTION_1": ["PSY", "BC", "AR", "ST", "UTAD", "SOW"],
        "DISTRIBUTION_2": ["PSY", "BC", "AR", "ST", "LPSY", "SOW"],
    }

    expected = expected_sequences.get(schematic_type, [])
    if not expected:
        return 0.0

    # Count matched patterns
    matched_count = sum(1 for exp in expected if exp in pattern_types)

    # Base confidence from pattern presence
    base_confidence = (matched_count / len(expected)) * 100

    # Adjust for critical patterns
    critical_patterns = {
        "ACCUMULATION_1": "SPRING",
        "ACCUMULATION_2": "LPS",
        "DISTRIBUTION_1": "UTAD",
        "DISTRIBUTION_2": "LPSY",
    }

    critical = critical_patterns.get(schematic_type)
    if critical and critical in pattern_types:
        base_confidence += 10  # Bonus for critical pattern

    # Cap at 95% (perfect matches rare in real data)
    return min(base_confidence, 95.0)


async def calculate_cause_building(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    trading_ranges: list[TradingRangeLevels],
) -> Optional[CauseBuildingData]:
    """Calculate Point & Figure cause-building data.

    Story 11.5.1 AC 4: P&F counting algorithm.

    Args:
        session: Database session
        symbol: Ticker symbol
        timeframe: Bar interval
        trading_ranges: Active trading ranges

    Returns:
        CauseBuildingData if active range found, else None
    """
    # Find active trading range
    active_range = next((tr for tr in trading_ranges if tr.range_status == "ACTIVE"), None)

    if not active_range:
        logger.debug("No active trading range for P&F counting", symbol=symbol)
        return None

    # Map timeframe
    timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1mo"}
    db_timeframe = timeframe_map.get(timeframe, "1d")

    # Query trading range from ORM to get start/end timestamps
    tr_query = select(TradingRangeORM).where(TradingRangeORM.id == active_range.trading_range_id)
    tr_result = await session.execute(tr_query)
    tr_orm = tr_result.scalar_one_or_none()

    if not tr_orm:
        return None

    # Query OHLCV bars within trading range
    query = (
        select(OHLCVBarORM)
        .where(
            and_(
                OHLCVBarORM.symbol == symbol,
                OHLCVBarORM.timeframe == db_timeframe,
                OHLCVBarORM.timestamp >= tr_orm.start_timestamp,
                OHLCVBarORM.timestamp <= tr_orm.end_timestamp,
            )
        )
        .order_by(OHLCVBarORM.timestamp.asc())
    )

    result = await session.execute(query)
    bars = result.scalars().all()

    if not bars:
        return None

    # Calculate ATR for volatility baseline
    atr = _calculate_atr(bars, period=14)

    # Count accumulation columns (wide-range bars)
    column_count = sum(1 for bar in bars if (float(bar.high) - float(bar.low)) > (2.0 * atr))

    # Calculate target column count
    duration_bars = len(bars)
    target_column_count = min(18, duration_bars // 5)

    # Ensure at least 1 target column
    target_column_count = max(target_column_count, 1)

    # Calculate projected Jump target
    creek = active_range.creek_level
    ice = active_range.ice_level
    range_height = ice - creek
    projected_jump = creek + (range_height * column_count * 0.5)

    # Calculate progress percentage
    progress_percentage = (column_count / target_column_count) * 100
    progress_percentage = min(progress_percentage, 100.0)

    # Methodology explanation
    methodology = (
        f"P&F Count: Counted {column_count} wide-range bars (range > 2× ATR) "
        f"within {duration_bars}-bar trading range. "
        f"Target: {target_column_count} columns (min(18, bars/5)). "
        f"Projected Jump = Creek + (Range × Columns × 0.5)"
    )

    return CauseBuildingData(
        column_count=column_count,
        target_column_count=target_column_count,
        projected_jump=projected_jump,
        progress_percentage=progress_percentage,
        count_methodology=methodology,
    )


def _calculate_atr(bars: list[OHLCVBarORM], period: int = 14) -> float:
    """Calculate Average True Range.

    Args:
        bars: OHLCV bars
        period: ATR period

    Returns:
        ATR value
    """
    if len(bars) < period:
        # Fallback: simple average range
        ranges = [float(bar.high) - float(bar.low) for bar in bars]
        return sum(ranges) / len(ranges) if ranges else 1.0

    true_ranges = []
    for i in range(1, len(bars)):
        high = float(bars[i].high)
        low = float(bars[i].low)
        prev_close = float(bars[i - 1].close)

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Simple moving average of true ranges
    if len(true_ranges) >= period:
        recent_tr = true_ranges[-period:]
        return sum(recent_tr) / period
    else:
        return sum(true_ranges) / len(true_ranges) if true_ranges else 1.0
