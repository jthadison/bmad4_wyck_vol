"""Chart data repository for charting API.

Story 11.5: Advanced Charting Integration
Handles database queries for OHLCV bars, patterns, trading ranges, and Wyckoff data.
"""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from backend.src.models.chart import (
    LEVEL_LINE_CONFIG,
    PATTERN_MARKER_CONFIG,
    PHASE_COLOR_CONFIG,
    PRELIMINARY_EVENT_CONFIG,
    CauseBuildingData,
    ChartBar,
    ChartDataResponse,
    LevelLine,
    PatternMarker,
    PhaseAnnotation,
    PreliminaryEvent,
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
from backend.src.repositories.wyckoff_algorithms import (
    calculate_cause_building,
    match_wyckoff_schematic,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ChartRepository:
    """Repository for chart data operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_chart_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500,
    ) -> ChartDataResponse:
        """Fetch complete chart data for symbol and timeframe.

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval (1D, 1W, 1M)
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of bars (default 500, max 2000)

        Returns:
            ChartDataResponse with all chart data

        Raises:
            ValueError: If no data found for symbol/timeframe
        """
        logger.info(
            "Fetching chart data",
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        # Default date range: last 90 days
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=90)

        # Fetch OHLCV bars
        bars = await self._get_ohlcv_bars(symbol, timeframe, start_date, end_date, limit)

        if not bars:
            raise ValueError(f"No OHLCV data found for {symbol} {timeframe}")

        # Get actual date range from bars
        actual_start = min(bar.time for bar in bars)
        actual_end = max(bar.time for bar in bars)
        actual_start_dt = datetime.utcfromtimestamp(actual_start)
        actual_end_dt = datetime.utcfromtimestamp(actual_end)

        # Fetch patterns for this time range
        patterns = await self._get_pattern_markers(
            symbol, timeframe, actual_start_dt, actual_end_dt
        )

        # Fetch trading range levels
        level_lines, trading_ranges = await self._get_trading_range_levels(
            symbol, timeframe, actual_start_dt, actual_end_dt
        )

        # Fetch phase annotations
        phase_annotations = await self._get_phase_annotations(
            symbol, timeframe, actual_start_dt, actual_end_dt
        )

        # Fetch preliminary events (PS, SC, AR, ST)
        preliminary_events = await self._get_preliminary_events(
            symbol, timeframe, actual_start_dt, actual_end_dt
        )

        # Get schematic matching (if available)
        # Extract creek/ice levels from trading ranges for normalization
        creek_level = trading_ranges[0].creek_level if trading_ranges else None
        ice_level = trading_ranges[0].ice_level if trading_ranges else None

        schematic_match = await self._get_schematic_match(
            symbol, timeframe, actual_start_dt, actual_end_dt, creek_level, ice_level
        )

        # Get cause-building data (if available)
        cause_building = await self._get_cause_building_data(symbol, timeframe, trading_ranges)

        logger.info(
            "Chart data fetched successfully",
            symbol=symbol,
            bar_count=len(bars),
            pattern_count=len(patterns),
            level_line_count=len(level_lines),
        )

        return ChartDataResponse(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            patterns=patterns,
            level_lines=level_lines,
            phase_annotations=phase_annotations,
            trading_ranges=trading_ranges,
            preliminary_events=preliminary_events,
            schematic_match=schematic_match,
            cause_building=cause_building,
            bar_count=len(bars),
            date_range={"start": actual_start_dt.isoformat(), "end": actual_end_dt.isoformat()},
        )

    async def _get_ohlcv_bars(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime, limit: int
    ) -> list[ChartBar]:
        """Fetch OHLCV bars from database.

        Converts to Lightweight Charts format:
        - Timestamps as Unix seconds
        - Decimal prices to float

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start date
            end_date: End date
            limit: Max number of bars

        Returns:
            List of ChartBar objects
        """
        # Map API timeframe to database timeframe
        timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1M"}
        db_timeframe = timeframe_map.get(timeframe, "1d")

        query = (
            select(OHLCVBarORM)
            .where(
                and_(
                    OHLCVBarORM.symbol == symbol,
                    OHLCVBarORM.timeframe == db_timeframe,
                    OHLCVBarORM.timestamp >= start_date,
                    OHLCVBarORM.timestamp <= end_date,
                )
            )
            .order_by(OHLCVBarORM.timestamp.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        orm_bars = result.scalars().all()

        # Convert to ChartBar format (reverse for chronological order)
        chart_bars = []
        for bar in reversed(orm_bars):
            chart_bars.append(
                ChartBar(
                    time=int(bar.timestamp.timestamp()),
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                )
            )

        return chart_bars

    async def _get_pattern_markers(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> list[PatternMarker]:
        """Fetch pattern markers for chart overlay.

        Only returns test-confirmed patterns with confidence >= 70.

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start date
            end_date: End date

        Returns:
            List of PatternMarker objects
        """
        # Map API timeframe to database timeframe
        timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1M"}
        db_timeframe = timeframe_map.get(timeframe, "1d")

        query = (
            select(PatternORM)
            .where(
                and_(
                    PatternORM.symbol == symbol,
                    PatternORM.timeframe == db_timeframe,
                    PatternORM.pattern_bar_timestamp >= start_date,
                    PatternORM.pattern_bar_timestamp <= end_date,
                    PatternORM.test_confirmed == True,  # noqa: E712
                    PatternORM.confidence_score >= 70,
                )
            )
            .order_by(PatternORM.pattern_bar_timestamp.asc())
        )

        result = await self.session.execute(query)
        patterns = result.scalars().all()

        # Convert to PatternMarker objects
        markers = []
        for pattern in patterns:
            config = PATTERN_MARKER_CONFIG.get(pattern.pattern_type, {})
            if not config:
                logger.warning("Unknown pattern type", pattern_type=pattern.pattern_type)
                continue

            markers.append(
                PatternMarker(
                    id=pattern.id,
                    pattern_type=pattern.pattern_type,
                    time=int(pattern.pattern_bar_timestamp.timestamp()),
                    price=float(pattern.entry_price),
                    position=config["position"],
                    confidence_score=pattern.confidence_score,
                    label_text=f"{pattern.pattern_type} ({pattern.confidence_score}%)",
                    icon=config["icon"],
                    color=config["color"],
                    shape=config["shape"],
                    entry_price=float(pattern.entry_price),
                    stop_loss=float(pattern.stop_loss),
                    phase=pattern.phase or "C",
                )
            )

        return markers

    async def _get_trading_range_levels(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> tuple[list[LevelLine], list[TradingRangeLevels]]:
        """Fetch trading range level lines (Creek, Ice, Jump).

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start date
            end_date: End date

        Returns:
            Tuple of (level_lines, trading_ranges)
        """
        # Map API timeframe to database timeframe
        timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1M"}
        db_timeframe = timeframe_map.get(timeframe, "1d")

        query = (
            select(TradingRangeORM)
            .where(
                and_(
                    TradingRangeORM.symbol == symbol,
                    TradingRangeORM.timeframe == db_timeframe,
                    or_(
                        and_(
                            TradingRangeORM.start_time <= end_date,
                            TradingRangeORM.end_time >= start_date,
                        ),
                        TradingRangeORM.deleted_at.is_(None),
                    ),
                )
            )
            .order_by(TradingRangeORM.start_time.desc())
        )

        result = await self.session.execute(query)
        ranges = result.scalars().all()

        level_lines = []
        trading_ranges = []

        for tr in ranges:
            # Determine if range is active or completed
            range_status = "ACTIVE" if tr.deleted_at is None else "COMPLETED"
            line_style = "SOLID" if range_status == "ACTIVE" else "DASHED"

            # Create Creek level line
            creek_config = LEVEL_LINE_CONFIG["CREEK"]
            level_lines.append(
                LevelLine(
                    level_type="CREEK",
                    price=float(tr.creek_level),
                    label=f"{creek_config['label_prefix']}: ${float(tr.creek_level):.2f}",
                    color=creek_config["color"],
                    line_style=line_style,
                    line_width=2,
                )
            )

            # Create Ice level line
            ice_config = LEVEL_LINE_CONFIG["ICE"]
            level_lines.append(
                LevelLine(
                    level_type="ICE",
                    price=float(tr.ice_level),
                    label=f"{ice_config['label_prefix']}: ${float(tr.ice_level):.2f}",
                    color=ice_config["color"],
                    line_style=line_style,
                    line_width=2,
                )
            )

            # Create Jump level line
            jump_config = LEVEL_LINE_CONFIG["JUMP"]
            level_lines.append(
                LevelLine(
                    level_type="JUMP",
                    price=float(tr.jump_target),
                    label=f"{jump_config['label_prefix']}: ${float(tr.jump_target):.2f}",
                    color=jump_config["color"],
                    line_style=line_style,
                    line_width=2,
                )
            )

            # Add to trading ranges list
            trading_ranges.append(
                TradingRangeLevels(
                    trading_range_id=tr.id,
                    symbol=tr.symbol,
                    creek_level=float(tr.creek_level),
                    ice_level=float(tr.ice_level),
                    jump_target=float(tr.jump_target),
                    range_status=range_status,
                )
            )

        return level_lines, trading_ranges

    async def _get_phase_annotations(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> list[PhaseAnnotation]:
        """Fetch phase annotations for background shading.

        Groups patterns by phase and calculates duration.

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start date
            end_date: End date

        Returns:
            List of PhaseAnnotation objects
        """
        # Map API timeframe to database timeframe
        timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1M"}
        db_timeframe = timeframe_map.get(timeframe, "1d")

        # Query patterns grouped by phase
        query = (
            select(
                PatternORM.phase,
                func.min(PatternORM.pattern_bar_timestamp).label("start_time"),
                func.max(PatternORM.pattern_bar_timestamp).label("end_time"),
            )
            .where(
                and_(
                    PatternORM.symbol == symbol,
                    PatternORM.timeframe == db_timeframe,
                    PatternORM.pattern_bar_timestamp >= start_date,
                    PatternORM.pattern_bar_timestamp <= end_date,
                    PatternORM.phase.isnot(None),
                )
            )
            .group_by(PatternORM.phase)
        )

        result = await self.session.execute(query)
        phase_groups = result.all()

        annotations = []
        for phase, start_time, end_time in phase_groups:
            if phase in PHASE_COLOR_CONFIG:
                annotations.append(
                    PhaseAnnotation(
                        phase=phase,
                        start_time=int(start_time.timestamp()),
                        end_time=int(end_time.timestamp()),
                        background_color=PHASE_COLOR_CONFIG[phase],
                        label=f"Phase {phase}",
                    )
                )

        return annotations

    async def _get_preliminary_events(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> list[PreliminaryEvent]:
        """Fetch preliminary Wyckoff events (PS, SC, AR, ST).

        Story 11.5 AC 13: Mark early events before Spring patterns.

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start date
            end_date: End date

        Returns:
            List of PreliminaryEvent objects
        """
        # Map API timeframe to database timeframe
        timeframe_map = {"1D": "1d", "1W": "1w", "1M": "1M"}
        db_timeframe = timeframe_map.get(timeframe, "1d")

        # Query for preliminary event patterns
        # Note: Assuming these are stored as pattern_type in patterns table
        query = (
            select(PatternORM)
            .where(
                and_(
                    PatternORM.symbol == symbol,
                    PatternORM.timeframe == db_timeframe,
                    PatternORM.pattern_bar_timestamp >= start_date,
                    PatternORM.pattern_bar_timestamp <= end_date,
                    PatternORM.pattern_type.in_(["PS", "SC", "AR", "ST"]),
                )
            )
            .order_by(PatternORM.pattern_bar_timestamp.asc())
        )

        result = await self.session.execute(query)
        event_patterns = result.scalars().all()

        events = []
        for pattern in event_patterns:
            event_type = pattern.pattern_type
            config = PRELIMINARY_EVENT_CONFIG.get(event_type, {})
            if not config:
                continue

            events.append(
                PreliminaryEvent(
                    event_type=event_type,
                    time=int(pattern.pattern_bar_timestamp.timestamp()),
                    price=float(pattern.entry_price),
                    label=config["label"],
                    description=config["description"],
                    color=config["color"],
                    shape=config["shape"],
                )
            )

        return events

    async def _get_schematic_match(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        creek_level: Optional[float] = None,
        ice_level: Optional[float] = None,
    ) -> Optional[WyckoffSchematic]:
        """Get Wyckoff schematic matching data.

        Story 11.5.1 AC 1, 7: Schematic matching algorithm.

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start date
            end_date: End date
            creek_level: Support level for normalization
            ice_level: Resistance level for normalization

        Returns:
            WyckoffSchematic if match found (confidence >= 60%), else None
        """
        return await match_wyckoff_schematic(
            self.session,
            symbol,
            timeframe,
            start_date,
            end_date,
            creek_level,
            ice_level,
        )

    async def _get_cause_building_data(
        self, symbol: str, timeframe: str, trading_ranges: list[TradingRangeLevels]
    ) -> Optional[CauseBuildingData]:
        """Get Point & Figure cause-building data.

        Story 11.5.1 AC 4: P&F counting algorithm.

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            trading_ranges: Active trading ranges

        Returns:
            CauseBuildingData if active range found, else None
        """
        return await calculate_cause_building(
            self.session,
            symbol,
            timeframe,
            trading_ranges,
        )
