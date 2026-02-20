"""
Pattern API Routes (Story 10.7, P3-F12, P3-F13)

Purpose:
--------
Provides REST API endpoints for pattern analysis and statistics.
Supports educational features showing historical pattern performance.

Endpoints:
----------
GET /api/v1/patterns/statistics - Get historical pattern performance statistics
GET /api/v1/patterns/{symbol}/trading-ranges - Get historical trading ranges (P3-F12)
GET /api/v1/patterns/{symbol}/volume-profile - Volume profile by Wyckoff phase (P3-F13)

Author: Story 10.7 (AC 5), P3-F12 (Historical Trading Range Browser), P3-F13 (Volume Profile by Phase)
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from src.models.ohlcv import OHLCVBar
from src.models.pattern_statistics import PatternStatistics
from src.models.trading_range_history import (
    TradingRangeEvent,
    TradingRangeHistory,
    TradingRangeListResponse,
    TradingRangeOutcome,
    TradingRangeType,
)
from src.models.volume_profile import VolumeProfileResponse
from src.pattern_engine.volume_profile import compute_volume_profile_by_phase

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/patterns", tags=["patterns"])


# ============================================================================
# Mock Data (Replace with database repository in production)
# ============================================================================

# Mock historical statistics data
# In production, this would query the database for actual pattern outcomes
_mock_statistics: dict[tuple[str, str], PatternStatistics] = {
    ("SPRING", "volume_high"): PatternStatistics(
        pattern_type="SPRING",
        rejection_category="volume_high",
        invalid_win_rate=Decimal("23.5"),
        valid_win_rate=Decimal("68.2"),
        sample_size_invalid=147,
        sample_size_valid=523,
        sufficient_data=True,
        message="Springs with volume >0.7x: 23% win rate vs 68% for valid springs",
    ),
    ("UTAD", "volume_high"): PatternStatistics(
        pattern_type="UTAD",
        rejection_category="volume_high",
        invalid_win_rate=Decimal("18.3"),
        valid_win_rate=Decimal("72.1"),
        sample_size_invalid=89,
        sample_size_valid=412,
        sufficient_data=True,
        message="UTADs with volume >0.7x: 18% win rate vs 72% for valid UTADs",
    ),
    ("SOS", "volume_low"): PatternStatistics(
        pattern_type="SOS",
        rejection_category="volume_low",
        invalid_win_rate=Decimal("31.2"),
        valid_win_rate=Decimal("75.8"),
        sample_size_invalid=234,
        sample_size_valid=681,
        sufficient_data=True,
        message="SOS with volume <1.3x: 31% win rate vs 76% for valid SOS",
    ),
    ("LPS", "volume_high"): PatternStatistics(
        pattern_type="LPS",
        rejection_category="volume_high",
        invalid_win_rate=Decimal("28.7"),
        valid_win_rate=Decimal("69.4"),
        sample_size_invalid=156,
        sample_size_valid=498,
        sufficient_data=True,
        message="LPS with volume >0.8x: 29% win rate vs 69% for valid LPS",
    ),
    ("SC", "volume_low"): PatternStatistics(
        pattern_type="SC",
        rejection_category="volume_low",
        invalid_win_rate=Decimal("22.1"),
        valid_win_rate=Decimal("64.3"),
        sample_size_invalid=67,
        sample_size_valid=289,
        sufficient_data=True,
        message="Selling Climax with volume <1.5x: 22% win rate vs 64% for valid SC",
    ),
    ("AR", "volume_low"): PatternStatistics(
        pattern_type="AR",
        rejection_category="volume_low",
        invalid_win_rate=Decimal("26.4"),
        valid_win_rate=Decimal("67.9"),
        sample_size_invalid=94,
        sample_size_valid=341,
        sufficient_data=True,
        message="Automatic Rally with volume <1.3x: 26% win rate vs 68% for valid AR",
    ),
    ("ST", "volume_high"): PatternStatistics(
        pattern_type="ST",
        rejection_category="volume_high",
        invalid_win_rate=Decimal("24.8"),
        valid_win_rate=Decimal("71.2"),
        sample_size_invalid=112,
        sample_size_valid=387,
        sufficient_data=True,
        message="Secondary Test with volume >0.8x: 25% win rate vs 71% for valid ST",
    ),
}


async def get_pattern_statistics(
    pattern_type: str, rejection_category: str | None
) -> PatternStatistics | None:
    """
    Fetch historical pattern performance statistics from database.

    TODO: Replace with actual repository call when pattern repository is implemented.

    Parameters:
    -----------
    pattern_type : str
        Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST)
    rejection_category : str | None
        Rejection category (volume_high, volume_low, test_not_confirmed, etc.)

    Returns:
    --------
    PatternStatistics | None
        Statistics if available, None if insufficient data
    """
    # PLACEHOLDER: Return from mock data
    # In production, replace with:
    # from src.repositories.pattern_repository import PatternRepository
    # repo = PatternRepository()
    # return await repo.get_statistics(pattern_type, rejection_category)

    logger.debug(
        "get_pattern_statistics_called",
        pattern_type=pattern_type,
        rejection_category=rejection_category,
        note="Using mock data",
    )

    # Look up mock statistics
    key = (pattern_type.upper(), rejection_category or "")
    return _mock_statistics.get(key)


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/statistics",
    response_model=PatternStatistics,
    summary="Get historical pattern performance statistics",
    description="""
    Retrieve historical performance data for pattern types.

    Shows comparative win rates between patterns that violated specific rules
    vs patterns that followed the rules correctly.

    Used for educational context in rejection detail dialogs.

    Query Parameters:
    - pattern_type (required): SPRING, UTAD, SOS, LPS, SC, AR, ST
    - rejection_category (optional): volume_high, volume_low, test_not_confirmed, etc.

    Returns 200 OK with statistics data.
    Returns 404 Not Found if insufficient historical data available.
    Returns 400 Bad Request if pattern_type is invalid.
    """,
)
async def get_statistics(
    pattern_type: str = Query(
        ...,
        description="Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST)",
        examples=["SPRING"],
    ),
    rejection_category: str | None = Query(
        None,
        description="Rejection category (volume_high, volume_low, etc.)",
        examples=["volume_high"],
    ),
) -> PatternStatistics:
    """
    Get historical pattern performance statistics (AC: 5).

    Fetches win rate data comparing invalid vs valid patterns for educational context.

    Parameters:
    -----------
    pattern_type : str
        Pattern type (SPRING, UTAD, SOS, LPS, SC, AR, ST)
    rejection_category : str | None
        Specific rejection category to query

    Returns:
    --------
    PatternStatistics
        Historical performance data with win rates and sample sizes

    Raises:
    -------
    HTTPException 400
        If pattern_type is invalid
    HTTPException 404
        If insufficient historical data available (sample_size < 20)
    """
    logger.info(
        "pattern_statistics_requested",
        pattern_type=pattern_type,
        rejection_category=rejection_category,
    )

    # Validate pattern_type
    valid_pattern_types = {"SPRING", "UTAD", "SOS", "LPS", "SC", "AR", "ST"}
    if pattern_type.upper() not in valid_pattern_types:
        logger.warning("invalid_pattern_type", pattern_type=pattern_type)
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pattern_type: {pattern_type}. Must be one of {valid_pattern_types}",
        )

    # Fetch statistics from repository
    stats = await get_pattern_statistics(pattern_type.upper(), rejection_category)

    if stats is None or not stats.sufficient_data:
        logger.warning(
            "insufficient_statistics_data",
            pattern_type=pattern_type,
            rejection_category=rejection_category,
        )
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Insufficient historical data for {pattern_type} with {rejection_category or 'any'} rejection",
        )

    logger.info(
        "pattern_statistics_returned",
        pattern_type=pattern_type,
        invalid_win_rate=str(stats.invalid_win_rate),
        valid_win_rate=str(stats.valid_win_rate),
    )

    return stats


# ============================================================================
# Trading Range History Endpoint (P3-F12)
# ============================================================================


def _build_mock_trading_ranges(symbol: str, timeframe: str) -> list[TradingRangeHistory]:
    """
    Build mock trading range data for demonstration.

    TODO: Replace with real TradingRangeDetector pipeline once market data
    repository is wired up. The real implementation would:
    1. Fetch OHLCV bars from OHLCVRepository
    2. Run VolumeAnalyzer on bars
    3. Run TradingRangeDetector.detect_ranges(bars, volume_analysis)
    4. Classify each range type and outcome from event_history and post-range price
    """
    return [
        TradingRangeHistory(
            id=str(uuid4()),
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime(2025, 11, 15, tzinfo=UTC),
            end_date=None,
            duration_bars=23,
            low=100.0,
            high=115.0,
            range_pct=(115.0 - 100.0) / 100.0 * 100,
            creek_level=101.50,
            ice_level=113.80,
            range_type=TradingRangeType.ACCUMULATION,
            outcome=TradingRangeOutcome.ACTIVE,
            key_events=[
                TradingRangeEvent(
                    event_type="SC",
                    timestamp=datetime(2025, 11, 16, tzinfo=UTC),
                    price=100.50,
                    volume=2500000.0,
                    significance=0.9,
                ),
                TradingRangeEvent(
                    event_type="AR",
                    timestamp=datetime(2025, 11, 18, tzinfo=UTC),
                    price=112.00,
                    volume=1800000.0,
                    significance=0.7,
                ),
                TradingRangeEvent(
                    event_type="ST",
                    timestamp=datetime(2025, 11, 25, tzinfo=UTC),
                    price=101.20,
                    volume=900000.0,
                    significance=0.6,
                ),
            ],
            avg_bar_volume=1200000.0,
            total_volume=1200000.0 * 23,
            price_change_pct=None,
        ),
        TradingRangeHistory(
            id=str(uuid4()),
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime(2025, 8, 1, tzinfo=UTC),
            end_date=datetime(2025, 10, 15, tzinfo=UTC),
            duration_bars=45,
            low=95.0,
            high=108.0,
            range_pct=(108.0 - 95.0) / 95.0 * 100,
            creek_level=96.20,
            ice_level=107.00,
            range_type=TradingRangeType.ACCUMULATION,
            outcome=TradingRangeOutcome.MARKUP,
            key_events=[
                TradingRangeEvent(
                    event_type="SC",
                    timestamp=datetime(2025, 8, 3, tzinfo=UTC),
                    price=95.50,
                    volume=3100000.0,
                    significance=0.95,
                ),
                TradingRangeEvent(
                    event_type="SPRING",
                    timestamp=datetime(2025, 9, 20, tzinfo=UTC),
                    price=94.80,
                    volume=500000.0,
                    significance=0.9,
                ),
                TradingRangeEvent(
                    event_type="SOS",
                    timestamp=datetime(2025, 10, 10, tzinfo=UTC),
                    price=109.00,
                    volume=2800000.0,
                    significance=0.85,
                ),
            ],
            avg_bar_volume=1400000.0,
            total_volume=1400000.0 * 45,
            price_change_pct=12.5,
        ),
        TradingRangeHistory(
            id=str(uuid4()),
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime(2025, 4, 10, tzinfo=UTC),
            end_date=datetime(2025, 6, 20, tzinfo=UTC),
            duration_bars=38,
            low=78.0,
            high=91.0,
            range_pct=(91.0 - 78.0) / 78.0 * 100,
            creek_level=79.20,  # Creek = support floor (near low=78.0)
            ice_level=89.50,  # Ice = resistance ceiling (near high=91.0)
            range_type=TradingRangeType.DISTRIBUTION,
            outcome=TradingRangeOutcome.MARKDOWN,
            key_events=[
                TradingRangeEvent(
                    event_type="BC",
                    timestamp=datetime(2025, 4, 12, tzinfo=UTC),
                    price=90.50,
                    volume=2900000.0,
                    significance=0.9,
                ),
                TradingRangeEvent(
                    event_type="UTAD",
                    timestamp=datetime(2025, 5, 28, tzinfo=UTC),
                    price=91.50,
                    volume=600000.0,
                    significance=0.85,
                ),
                TradingRangeEvent(
                    event_type="SOW",
                    timestamp=datetime(2025, 6, 15, tzinfo=UTC),
                    price=77.00,
                    volume=2600000.0,
                    significance=0.8,
                ),
            ],
            avg_bar_volume=1100000.0,
            total_volume=1100000.0 * 38,
            price_change_pct=-15.2,
        ),
        TradingRangeHistory(
            id=str(uuid4()),
            symbol=symbol,
            timeframe=timeframe,
            start_date=datetime(2025, 1, 5, tzinfo=UTC),
            end_date=datetime(2025, 3, 1, tzinfo=UTC),
            duration_bars=30,
            low=82.0,
            high=90.0,
            range_pct=(90.0 - 82.0) / 82.0 * 100,
            creek_level=83.00,
            ice_level=89.00,
            range_type=TradingRangeType.ACCUMULATION,
            outcome=TradingRangeOutcome.FAILED,
            key_events=[
                TradingRangeEvent(
                    event_type="SC",
                    timestamp=datetime(2025, 1, 8, tzinfo=UTC),
                    price=82.50,
                    volume=2200000.0,
                    significance=0.85,
                ),
                TradingRangeEvent(
                    event_type="SPRING",
                    timestamp=datetime(2025, 2, 15, tzinfo=UTC),
                    price=81.50,
                    volume=1500000.0,
                    significance=0.5,
                ),
            ],
            avg_bar_volume=1000000.0,
            total_volume=1000000.0 * 30,
            price_change_pct=-8.3,
        ),
    ]


@router.get(
    "/{symbol}/trading-ranges",
    response_model=TradingRangeListResponse,
    summary="Get historical trading ranges for a symbol",
    description="""
    Retrieve historical and active trading ranges (accumulation/distribution zones)
    for a given symbol. Each range includes Wyckoff events, creek/ice levels,
    outcome classification, and volume data.

    Used by the Historical Trading Range Browser component.
    """,
)
async def get_trading_ranges(
    symbol: str,
    timeframe: str = Query(
        "1d",
        description="Bar timeframe",
        pattern=r"^(1m|5m|15m|1h|1d|1M|5M|15M|1H|1D|4H|1W)$",
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum ranges to return"),
) -> TradingRangeListResponse:
    """Get historical trading ranges for a symbol (P3-F12)."""
    logger.info(
        "trading_ranges_requested",
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )

    # TODO: Wire to real TradingRangeDetector pipeline.
    # For now, return mock data that demonstrates realistic Wyckoff ranges.
    all_ranges = _build_mock_trading_ranges(symbol.upper(), timeframe)

    # Separate active from historical
    active_range = next((r for r in all_ranges if r.outcome == TradingRangeOutcome.ACTIVE), None)
    historical = [r for r in all_ranges if r.outcome != TradingRangeOutcome.ACTIVE]

    # Sort historical by start_date descending
    historical.sort(key=lambda r: r.start_date, reverse=True)

    # Apply limit to historical only (active is always shown)
    historical = historical[:limit]

    response = TradingRangeListResponse(
        symbol=symbol.upper(),
        timeframe=timeframe,
        ranges=historical,
        active_range=active_range,
        total_count=len(historical) + (1 if active_range else 0),
    )
    logger.info(
        "trading_ranges_returned",
        symbol=response.symbol,
        total_count=response.total_count,
        has_active=response.active_range is not None,
    )
    return response


# ============================================================================
# Volume Profile by Wyckoff Phase (P3-F13)
# ============================================================================


def _generate_mock_bars(symbol: str, timeframe: str, count: int) -> list[OHLCVBar]:
    """Generate synthetic OHLCV bars for demonstration when no DB is available."""
    import math
    import random

    random.seed(42)
    bars: list[OHLCVBar] = []
    base_price = 100.0
    base_volume = 1_000_000

    for i in range(count):
        # Create a price wave simulating accumulation pattern
        cycle = math.sin(2 * math.pi * i / count) * 10
        trend = i * 0.02  # Slight uptrend
        noise = random.uniform(-2, 2)
        mid = base_price + cycle + trend + noise

        spread = random.uniform(0.5, 3.0)
        o = mid + random.uniform(-spread / 2, spread / 2)
        h = mid + spread / 2 + random.uniform(0, 1)
        low_p = mid - spread / 2 - random.uniform(0, 1)
        c = mid + random.uniform(-spread / 2, spread / 2)

        # Volume varies by phase position (realistic Wyckoff proportions)
        vol_multiplier = 1.0
        pct = i / count
        if pct < 0.05:
            vol_multiplier = 2.5  # Phase A: high volume (SC)
        elif pct < 0.70:
            vol_multiplier = 1.2  # Phase B: moderate (long cause-building)
        elif pct < 0.75:
            vol_multiplier = 0.6  # Phase C: low volume (Spring)
        elif pct < 0.90:
            vol_multiplier = 1.8  # Phase D: rising volume (SOS)
        else:
            vol_multiplier = 1.0  # Phase E: normal

        vol = int(base_volume * vol_multiplier * random.uniform(0.7, 1.3))

        ts = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i)

        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                open=Decimal(str(round(o, 2))),
                high=Decimal(str(round(h, 2))),
                low=Decimal(str(round(low_p, 2))),
                close=Decimal(str(round(c, 2))),
                volume=vol,
                spread=Decimal(str(round(h - low_p, 2))),
            )
        )

    return bars


def _assign_mock_phases(count: int) -> list[str]:
    """Assign Wyckoff phases with realistic proportions.

    Realistic durations per Wyckoff methodology:
      A:  ~5%  - Stopping action (SC, AR, ST) — brief
      B: ~65%  - Cause building — longest phase by far
      C:  ~5%  - Testing (Spring/UTAD) — very brief
      D: ~15%  - Markup/markdown (SOS/LPS)
      E: ~10%  - Trend continuation
    """
    phases: list[str] = []
    for i in range(count):
        pct = i / count
        if pct < 0.05:
            phases.append("A")
        elif pct < 0.70:
            phases.append("B")
        elif pct < 0.75:
            phases.append("C")
        elif pct < 0.90:
            phases.append("D")
        else:
            phases.append("E")
    return phases


@router.get(
    "/{symbol}/volume-profile",
    response_model=VolumeProfileResponse,
    summary="Get volume profile segmented by Wyckoff phase",
    description="""
    Compute VPVR (Volume Profile Visible Range) segmented by Wyckoff phase.

    Shows how volume distributes across price levels for each phase,
    making it visually obvious where institutions accumulated/distributed.

    Query Parameters:
    - timeframe: Bar timeframe (default "1d")
    - bars: Number of bars to analyze (50-1000, default 200)
    - num_bins: Number of price bins (20-100, default 50)

    Returns volume profile with POC, value area, and per-phase breakdown.
    """,
)
async def get_volume_profile(
    symbol: str,
    timeframe: str = Query(
        "1d",
        description="Bar timeframe",
        pattern=r"^(1m|5m|15m|1h|1d|1M|5M|15M|1H|1D|4H|1W)$",
    ),
    bars: int = Query(200, ge=50, le=1000, description="Number of bars to analyze"),
    num_bins: int = Query(50, ge=20, le=100, description="Number of price bins"),
) -> VolumeProfileResponse:
    """Get volume profile segmented by Wyckoff phase (P3-F13)."""
    logger.info(
        "volume_profile_requested",
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        num_bins=num_bins,
    )

    # Generate mock data (production: fetch from DB + run PhaseClassifier)
    mock_bars = _generate_mock_bars(symbol, timeframe, bars)
    phase_labels = _assign_mock_phases(bars)

    try:
        # Run CPU-bound computation off the event loop to avoid blocking
        result = await asyncio.to_thread(
            compute_volume_profile_by_phase, mock_bars, phase_labels, num_bins
        )
    except ValueError as exc:
        logger.warning("volume_profile_invalid_input", symbol=symbol, error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info(
        "volume_profile_computed",
        symbol=symbol,
        phases_present=len(result.phases),
        combined_volume=result.combined.total_volume,
    )

    return result
