"""
Pattern API Routes (Story 10.7)

Purpose:
--------
Provides REST API endpoints for pattern analysis and statistics.
Supports educational features showing historical pattern performance.

Endpoints:
----------
GET /api/v1/patterns/statistics - Get historical pattern performance statistics

Author: Story 10.7 (AC 5)
"""

from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from src.models.pattern_statistics import PatternStatistics

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
