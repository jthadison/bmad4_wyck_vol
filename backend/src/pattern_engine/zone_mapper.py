"""
Zone Mapper module for supply and demand zone detection.

This module provides functions to identify supply and demand zones within trading ranges
based on Wyckoff methodology. Zones represent areas where smart money absorbed supply
(demand zones) or distributed shares (supply zones) on high volume with narrow spreads.

Key Functions:
    - detect_demand_zones: Identify bullish absorption zones
    - detect_supply_zones: Identify bearish distribution zones
    - map_supply_demand_zones: Main function integrating all zone detection logic
    - count_zone_touches: Track how many times price returned to a zone
    - classify_zone_strength: FRESH/TESTED/EXHAUSTED based on touches
    - calculate_zone_proximity: Determine if zone is near Creek or Ice
    - calculate_significance_score: 0-100 score based on strength + proximity + quality
    - check_zone_invalidation: Detect when zone is broken

Performance:
    - Single zone mapping (one range): <20ms
    - Batch zone mapping (10 ranges): <200ms
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import structlog

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.ohlcv import OHLCVBar
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.models.zone import PriceRange, Zone, ZoneStrength, ZoneType

# Rebuild TradingRange model after Zone is imported to resolve forward references
TradingRange.model_rebuild()

logger = structlog.get_logger(__name__)

# Constants for zone detection
HIGH_VOLUME_THRESHOLD = Decimal("1.3")  # AC 2: High volume requirement
NARROW_SPREAD_THRESHOLD = Decimal("0.8")  # AC 2: Narrow spread requirement
PROXIMITY_THRESHOLD_PCT = Decimal("0.02")  # AC 7: 2% proximity for significance
INVALIDATION_VOLUME_THRESHOLD = Decimal("1.5")  # High volume for zone breaks


def detect_demand_zones(bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]) -> list[Zone]:
    """
    Identify bullish absorption zones (demand zones).

    Demand zones show smart money accumulation through high volume absorption
    with narrow spreads and closes in the upper half of the bar. These zones
    represent areas where institutional buyers stepped in aggressively.

    Wyckoff Context:
        Demand zones are created when:
        - High volume (>1.3x avg): Smart money buying aggressively
        - Narrow spread (<0.8x avg): Price controlled despite volume (absorption)
        - Close in upper 50%: Buyers won, close near high (bullish)

    Detection Criteria (AC 2, 3):
        - volume_ratio >= 1.3 (high volume)
        - spread_ratio <= 0.8 (narrow spread)
        - close_position >= 0.5 (close in upper half)

    Args:
        bars: List of OHLCV bars in chronological order
        volume_analysis: List of VolumeAnalysis matching bars (same length)

    Returns:
        List[Zone]: Detected demand zones with DEMAND type

    Raises:
        ValueError: If bars and volume_analysis lengths don't match
        ValueError: If inputs are empty

    Example:
        >>> bars = [OHLCVBar(...), ...]
        >>> vol_analysis = [VolumeAnalysis(...), ...]
        >>> demand_zones = detect_demand_zones(bars, vol_analysis)
        >>> print(f"Found {len(demand_zones)} demand zones")
    """
    # Validate inputs
    if not bars:
        raise ValueError("Bars list cannot be empty")
    if not volume_analysis:
        raise ValueError("Volume analysis list cannot be empty")
    if len(bars) != len(volume_analysis):
        raise ValueError(
            f"Bars count {len(bars)} does not match volume analysis count {len(volume_analysis)}"
        )

    logger.info(
        "demand_zone_detection_start",
        bar_count=len(bars),
        symbol=bars[0].symbol if bars else None,
        timeframe=bars[0].timeframe if bars else None,
    )

    demand_zones: list[Zone] = []

    # Iterate through bars checking demand zone conditions
    for i, (bar, vol_analysis) in enumerate(zip(bars, volume_analysis, strict=False)):
        # Check all three conditions for demand zone (AC 2, 3)
        if vol_analysis.volume_ratio is None or vol_analysis.spread_ratio is None:
            continue  # Skip bars without complete volume analysis

        is_high_volume = vol_analysis.volume_ratio >= HIGH_VOLUME_THRESHOLD
        is_narrow_spread = vol_analysis.spread_ratio <= NARROW_SPREAD_THRESHOLD
        is_close_upper_half = vol_analysis.close_position >= Decimal("0.5")

        if is_high_volume and is_narrow_spread and is_close_upper_half:
            # Calculate zone boundaries
            zone_low = bar.low
            zone_high = bar.high
            midpoint = (zone_low + zone_high) / 2
            width_pct = (zone_high - zone_low) / zone_low

            # Create PriceRange
            price_range = PriceRange(
                low=zone_low, high=zone_high, midpoint=midpoint, width_pct=width_pct
            )

            # Calculate average volume for context
            volume_avg = Decimal(str(bar.volume)) / vol_analysis.volume_ratio

            # Create Zone object
            zone = Zone(
                id=uuid4(),
                zone_type=ZoneType.DEMAND,
                price_range=price_range,
                formation_bar_index=i,
                formation_timestamp=bar.timestamp,
                strength=ZoneStrength.FRESH,  # Initial strength, will be updated
                touch_count=0,  # Initial count, will be updated
                formation_volume=bar.volume,
                formation_volume_ratio=vol_analysis.volume_ratio,
                formation_spread_ratio=vol_analysis.spread_ratio,
                volume_avg=volume_avg,
                close_position=vol_analysis.close_position,
                proximity_to_level=None,  # Will be calculated later
                proximity_distance_pct=None,
                significance_score=0,  # Will be calculated later
                is_active=True,
                last_touch_timestamp=None,
                invalidation_timestamp=None,
            )

            demand_zones.append(zone)

            logger.debug(
                "demand_zone_detected",
                zone_id=str(zone.id),
                bar_index=i,
                price_range_low=str(zone_low),
                price_range_high=str(zone_high),
                volume_ratio=str(vol_analysis.volume_ratio),
                spread_ratio=str(vol_analysis.spread_ratio),
                close_position=str(vol_analysis.close_position),
            )

    logger.info("demand_zone_detection_complete", zones_detected=len(demand_zones))

    return demand_zones


def detect_supply_zones(bars: list[OHLCVBar], volume_analysis: list[VolumeAnalysis]) -> list[Zone]:
    """
    Identify bearish distribution zones (supply zones).

    Supply zones show smart money distribution through high volume selling
    with narrow spreads and closes in the lower half of the bar. These zones
    represent areas where institutional sellers distributed shares aggressively.

    Wyckoff Context:
        Supply zones are created when:
        - High volume (>1.3x avg): Smart money selling aggressively
        - Narrow spread (<0.8x avg): Price controlled despite volume (distribution)
        - Close in lower 50%: Sellers won, close near low (bearish)

    Detection Criteria (AC 4):
        - volume_ratio >= 1.3 (high volume)
        - spread_ratio <= 0.8 (narrow spread)
        - close_position < 0.5 (close in lower half)

    Args:
        bars: List of OHLCV bars in chronological order
        volume_analysis: List of VolumeAnalysis matching bars (same length)

    Returns:
        List[Zone]: Detected supply zones with SUPPLY type

    Raises:
        ValueError: If bars and volume_analysis lengths don't match
        ValueError: If inputs are empty

    Example:
        >>> bars = [OHLCVBar(...), ...]
        >>> vol_analysis = [VolumeAnalysis(...), ...]
        >>> supply_zones = detect_supply_zones(bars, vol_analysis)
        >>> print(f"Found {len(supply_zones)} supply zones")
    """
    # Validate inputs
    if not bars:
        raise ValueError("Bars list cannot be empty")
    if not volume_analysis:
        raise ValueError("Volume analysis list cannot be empty")
    if len(bars) != len(volume_analysis):
        raise ValueError(
            f"Bars count {len(bars)} does not match volume analysis count {len(volume_analysis)}"
        )

    logger.info(
        "supply_zone_detection_start",
        bar_count=len(bars),
        symbol=bars[0].symbol if bars else None,
        timeframe=bars[0].timeframe if bars else None,
    )

    supply_zones: list[Zone] = []

    # Iterate through bars checking supply zone conditions
    for i, (bar, vol_analysis) in enumerate(zip(bars, volume_analysis, strict=False)):
        # Check all three conditions for supply zone (AC 4)
        if vol_analysis.volume_ratio is None or vol_analysis.spread_ratio is None:
            continue  # Skip bars without complete volume analysis

        is_high_volume = vol_analysis.volume_ratio >= HIGH_VOLUME_THRESHOLD
        is_narrow_spread = vol_analysis.spread_ratio <= NARROW_SPREAD_THRESHOLD
        is_close_lower_half = vol_analysis.close_position < Decimal("0.5")

        if is_high_volume and is_narrow_spread and is_close_lower_half:
            # Calculate zone boundaries
            zone_low = bar.low
            zone_high = bar.high
            midpoint = (zone_low + zone_high) / 2
            width_pct = (zone_high - zone_low) / zone_low

            # Create PriceRange
            price_range = PriceRange(
                low=zone_low, high=zone_high, midpoint=midpoint, width_pct=width_pct
            )

            # Calculate average volume for context
            volume_avg = Decimal(str(bar.volume)) / vol_analysis.volume_ratio

            # Create Zone object
            zone = Zone(
                id=uuid4(),
                zone_type=ZoneType.SUPPLY,
                price_range=price_range,
                formation_bar_index=i,
                formation_timestamp=bar.timestamp,
                strength=ZoneStrength.FRESH,  # Initial strength, will be updated
                touch_count=0,  # Initial count, will be updated
                formation_volume=bar.volume,
                formation_volume_ratio=vol_analysis.volume_ratio,
                formation_spread_ratio=vol_analysis.spread_ratio,
                volume_avg=volume_avg,
                close_position=vol_analysis.close_position,
                proximity_to_level=None,  # Will be calculated later
                proximity_distance_pct=None,
                significance_score=0,  # Will be calculated later
                is_active=True,
                last_touch_timestamp=None,
                invalidation_timestamp=None,
            )

            supply_zones.append(zone)

            logger.debug(
                "supply_zone_detected",
                zone_id=str(zone.id),
                bar_index=i,
                price_range_low=str(zone_low),
                price_range_high=str(zone_high),
                volume_ratio=str(vol_analysis.volume_ratio),
                spread_ratio=str(vol_analysis.spread_ratio),
                close_position=str(vol_analysis.close_position),
            )

    logger.info("supply_zone_detection_complete", zones_detected=len(supply_zones))

    return supply_zones


def count_zone_touches(
    zone: Zone, bars: list[OHLCVBar], start_index: int
) -> tuple[int, datetime | None]:
    """
    Count how many times price returned to a zone after formation.

    A "touch" occurs when a subsequent bar overlaps with the zone's price range.
    This helps classify zone strength (FRESH/TESTED/EXHAUSTED).

    Args:
        zone: The zone to check for touches
        bars: List of OHLCV bars in chronological order
        start_index: Index to start counting from (typically formation_bar_index + 1)

    Returns:
        Tuple[int, Optional[datetime]]: (touch_count, last_touch_timestamp)
            - touch_count: Number of times price returned to zone
            - last_touch_timestamp: Timestamp of most recent touch (None if no touches)

    Example:
        >>> zone = Zone(...)  # Zone formed at index 10
        >>> touch_count, last_touch = count_zone_touches(zone, bars, start_index=11)
        >>> print(f"Zone touched {touch_count} times")
    """
    touch_count = 0
    last_touch_timestamp: datetime | None = None

    # Iterate through bars after zone formation
    for i in range(start_index, len(bars)):
        bar = bars[i]

        # Check if bar overlaps with zone: bar.low <= zone.high AND bar.high >= zone.low
        if bar.low <= zone.price_range.high and bar.high >= zone.price_range.low:
            touch_count += 1
            last_touch_timestamp = bar.timestamp

            logger.debug(
                "zone_touch_detected",
                zone_id=str(zone.id),
                zone_type=zone.zone_type.value,
                bar_index=i,
                bar_timestamp=bar.timestamp.isoformat(),
                touch_count=touch_count,
            )

    return touch_count, last_touch_timestamp


def classify_zone_strength(touch_count: int) -> ZoneStrength:
    """
    Classify zone strength based on number of touches.

    Strength Classification (AC 5):
        - FRESH: 0 touches (untested, strongest)
        - TESTED: 1-2 touches (validated but still active)
        - EXHAUSTED: 3+ touches (absorbed, no longer valid)

    Args:
        touch_count: Number of times price returned to zone

    Returns:
        ZoneStrength: FRESH, TESTED, or EXHAUSTED

    Example:
        >>> classify_zone_strength(0)
        ZoneStrength.FRESH
        >>> classify_zone_strength(2)
        ZoneStrength.TESTED
        >>> classify_zone_strength(3)
        ZoneStrength.EXHAUSTED
    """
    if touch_count == 0:
        return ZoneStrength.FRESH
    elif touch_count <= 2:
        return ZoneStrength.TESTED
    else:
        return ZoneStrength.EXHAUSTED


def calculate_zone_proximity(
    zone: Zone, creek_level: CreekLevel | None, ice_level: IceLevel | None
) -> tuple[str | None, Decimal | None]:
    """
    Calculate zone proximity to Creek or Ice levels.

    Zones near levels are more significant (AC 7):
        - Demand zones near Creek: reinforce support
        - Supply zones near Ice: reinforce resistance

    Proximity Threshold: 2% (PROXIMITY_THRESHOLD_PCT)

    Args:
        zone: The zone to check proximity for
        creek_level: Creek level (demand zone reference), may be None
        ice_level: Ice level (supply zone reference), may be None

    Returns:
        Tuple[Optional[str], Optional[Decimal]]:
            - proximity_label: "NEAR_CREEK" or "NEAR_ICE" or None
            - distance_pct: Distance to nearest level as percentage (None if not near)

    Example:
        >>> zone = Zone(zone_type=ZoneType.DEMAND, ...)
        >>> creek = CreekLevel(price=Decimal("172.50"), ...)
        >>> proximity, distance = calculate_zone_proximity(zone, creek, None)
        >>> print(f"Proximity: {proximity}, Distance: {distance}%")
    """
    zone_mid = zone.price_range.midpoint

    # Check proximity to Creek (for demand zones)
    if zone.zone_type == ZoneType.DEMAND and creek_level is not None:
        distance_pct = abs(zone_mid - creek_level.price) / creek_level.price
        if distance_pct <= PROXIMITY_THRESHOLD_PCT:
            logger.debug(
                "zone_near_creek",
                zone_id=str(zone.id),
                zone_midpoint=str(zone_mid),
                creek_price=str(creek_level.price),
                distance_pct=str(distance_pct),
            )
            return "NEAR_CREEK", distance_pct

    # Check proximity to Ice (for supply zones)
    if zone.zone_type == ZoneType.SUPPLY and ice_level is not None:
        distance_pct = abs(zone_mid - ice_level.price) / ice_level.price
        if distance_pct <= PROXIMITY_THRESHOLD_PCT:
            logger.debug(
                "zone_near_ice",
                zone_id=str(zone.id),
                zone_midpoint=str(zone_mid),
                ice_price=str(ice_level.price),
                distance_pct=str(distance_pct),
            )
            return "NEAR_ICE", distance_pct

    return None, None


def calculate_significance_score(zone: Zone) -> int:
    """
    Calculate zone significance score (0-100).

    Scoring Components (AC 7):
        - Strength (40 points): FRESH=40, TESTED=25, EXHAUSTED=0
        - Proximity (30 points): NEAR_CREEK/ICE=30, else=0
        - Formation Quality (30 points):
            - Volume ratio component: (vol_ratio - 1.3) / 2.0 * 15 (max 15 pts)
            - Spread tightness component: (0.8 - spread_ratio) / 0.8 * 15 (max 15 pts)

    Args:
        zone: The zone to score

    Returns:
        int: Significance score 0-100 (capped)

    Example:
        >>> zone = Zone(
        ...     strength=ZoneStrength.FRESH,
        ...     proximity_to_level="NEAR_CREEK",
        ...     formation_volume_ratio=Decimal("1.8"),
        ...     formation_spread_ratio=Decimal("0.6")
        ... )
        >>> score = calculate_significance_score(zone)
        >>> print(f"Significance: {score}/100")
    """
    score = 0

    # Strength component (40 points)
    if zone.strength == ZoneStrength.FRESH:
        score += 40
    elif zone.strength == ZoneStrength.TESTED:
        score += 25
    # EXHAUSTED = 0 points

    # Proximity component (30 points)
    if zone.proximity_to_level in ["NEAR_CREEK", "NEAR_ICE"]:
        score += 30

    # Formation quality component (30 points)
    # Volume ratio: higher is better (1.3 = min, 3.3+ = max 15 pts)
    volume_component = min(
        float((zone.formation_volume_ratio - Decimal("1.3")) / Decimal("2.0")) * 15, 15
    )
    score += int(volume_component)

    # Spread tightness: tighter is better (0.8 = min 0 pts, 0.0 = max 15 pts)
    spread_component = float((Decimal("0.8") - zone.formation_spread_ratio) / Decimal("0.8")) * 15
    score += int(spread_component)

    # Cap at 100
    final_score = min(score, 100)

    logger.debug(
        "zone_significance_calculated",
        zone_id=str(zone.id),
        strength=zone.strength.value,
        proximity=zone.proximity_to_level,
        volume_ratio=str(zone.formation_volume_ratio),
        spread_ratio=str(zone.formation_spread_ratio),
        final_score=final_score,
    )

    return final_score


def check_zone_invalidation(zone: Zone, bars: list[OHLCVBar], current_index: int) -> bool:
    """
    Check if zone has been invalidated (broken).

    Zone Invalidation Criteria:
        - Demand zone: Close below zone.price_range.low with volume > 1.5x
        - Supply zone: Close above zone.price_range.high with volume > 1.5x

    Args:
        zone: The zone to check for invalidation
        bars: List of OHLCV bars in chronological order
        current_index: Current bar index to check

    Returns:
        bool: True if zone is invalidated, False otherwise

    Example:
        >>> zone = Zone(zone_type=ZoneType.DEMAND, ...)
        >>> is_broken = check_zone_invalidation(zone, bars, current_bar_index)
        >>> if is_broken:
        ...     zone.is_active = False
    """
    if current_index >= len(bars):
        return False

    bar = bars[current_index]

    # Demand zone invalidation: close below zone low with high volume
    if zone.zone_type == ZoneType.DEMAND:
        if bar.close < zone.price_range.low and bar.volume_ratio >= INVALIDATION_VOLUME_THRESHOLD:
            logger.info(
                "demand_zone_invalidated",
                zone_id=str(zone.id),
                bar_index=current_index,
                bar_close=str(bar.close),
                zone_low=str(zone.price_range.low),
                volume_ratio=str(bar.volume_ratio),
            )
            return True

    # Supply zone invalidation: close above zone high with high volume
    if zone.zone_type == ZoneType.SUPPLY:
        if bar.close > zone.price_range.high and bar.volume_ratio >= INVALIDATION_VOLUME_THRESHOLD:
            logger.info(
                "supply_zone_invalidated",
                zone_id=str(zone.id),
                bar_index=current_index,
                bar_close=str(bar.close),
                zone_high=str(zone.price_range.high),
                volume_ratio=str(bar.volume_ratio),
            )
            return True

    return False


def map_supply_demand_zones(
    trading_range: TradingRange,
    bars: list[OHLCVBar],
    volume_analysis: list[VolumeAnalysis],
    creek_level: CreekLevel | None = None,
    ice_level: IceLevel | None = None,
) -> list[Zone]:
    """
    Map supply and demand zones within a trading range.

    This is the main function that integrates all zone detection logic:
        1. Validate inputs (quality range, matching lengths)
        2. Extract bars within range boundaries
        3. Detect demand and supply zones
        4. Count zone touches
        5. Classify zone strength
        6. Calculate proximity to Creek/Ice
        7. Calculate significance scores
        8. Filter out exhausted zones
        9. Sort by significance

    Requirements:
        - Only processes quality ranges (score >= 70) per AC and Story 3.3
        - Returns only FRESH and TESTED zones (filters EXHAUSTED)
        - Sorts zones by significance score (highest first)

    Args:
        trading_range: TradingRange to analyze for zones
        bars: Complete list of OHLCV bars
        volume_analysis: Complete list of VolumeAnalysis matching bars
        creek_level: Optional Creek level for proximity calculation
        ice_level: Optional Ice level for proximity calculation

    Returns:
        List[Zone]: Active zones sorted by significance (highest first)

    Raises:
        ValueError: If trading range quality < 70
        ValueError: If bars and volume_analysis lengths don't match
        ValueError: If inputs are empty

    Example:
        >>> trading_range = TradingRange(quality_score=85, ...)
        >>> bars = [OHLCVBar(...), ...]
        >>> vol_analysis = [VolumeAnalysis(...), ...]
        >>> creek = CreekLevel(...)
        >>> ice = IceLevel(...)
        >>> zones = map_supply_demand_zones(trading_range, bars, vol_analysis, creek, ice)
        >>> print(f"Found {len(zones)} active zones")
        >>> for zone in zones[:3]:  # Top 3 zones
        ...     print(f"Zone: {zone.zone_type.value}, Score: {zone.significance_score}")
    """
    # Validate quality range (AC requirement + Story 3.3)
    if trading_range.quality_score is None or trading_range.quality_score < 70:
        logger.error(
            "low_quality_range",
            range_id=str(trading_range.id),
            quality_score=trading_range.quality_score,
            message="Zone mapping requires quality score >= 70",
        )
        raise ValueError(
            f"Cannot map zones for low-quality range "
            f"(quality_score={trading_range.quality_score}, minimum=70)"
        )

    # Validate inputs
    if not bars:
        raise ValueError("Bars list cannot be empty")
    if not volume_analysis:
        raise ValueError("Volume analysis list cannot be empty")
    if len(bars) != len(volume_analysis):
        raise ValueError(
            f"Bars count {len(bars)} does not match volume analysis count {len(volume_analysis)}"
        )

    logger.info(
        "zone_mapping_start",
        range_id=str(trading_range.id),
        symbol=trading_range.symbol,
        timeframe=trading_range.timeframe,
        start_index=trading_range.start_index,
        end_index=trading_range.end_index,
        quality_score=trading_range.quality_score,
        total_bars=len(bars),
    )

    # Extract bars within trading range
    range_bars = bars[trading_range.start_index : trading_range.end_index + 1]
    range_volume_analysis = volume_analysis[trading_range.start_index : trading_range.end_index + 1]

    logger.info(
        "range_bars_extracted",
        range_bar_count=len(range_bars),
        start_index=trading_range.start_index,
        end_index=trading_range.end_index,
    )

    # Detect zones
    demand_zones = detect_demand_zones(range_bars, range_volume_analysis)
    supply_zones = detect_supply_zones(range_bars, range_volume_analysis)
    all_zones = demand_zones + supply_zones

    logger.info(
        "zones_detected",
        demand_zones=len(demand_zones),
        supply_zones=len(supply_zones),
        total_zones=len(all_zones),
    )

    # Process each zone: count touches, classify strength, calculate proximity and significance
    for zone in all_zones:
        # Count touches (after formation bar)
        start_touch_index = zone.formation_bar_index + 1
        touch_count, last_touch = count_zone_touches(zone, range_bars, start_touch_index)
        zone.touch_count = touch_count
        zone.last_touch_timestamp = last_touch

        # Classify strength based on touches
        zone.strength = classify_zone_strength(touch_count)

        # Set is_active based on strength
        if zone.strength == ZoneStrength.EXHAUSTED:
            zone.is_active = False

        # Calculate proximity to Creek/Ice
        proximity_label, proximity_distance = calculate_zone_proximity(zone, creek_level, ice_level)
        zone.proximity_to_level = proximity_label
        zone.proximity_distance_pct = proximity_distance

        # Calculate significance score
        zone.significance_score = calculate_significance_score(zone)

        logger.debug(
            "zone_processed",
            zone_id=str(zone.id),
            zone_type=zone.zone_type.value,
            strength=zone.strength.value,
            touch_count=touch_count,
            proximity=proximity_label,
            significance_score=zone.significance_score,
            is_active=zone.is_active,
        )

    # Filter out exhausted zones (keep only FRESH and TESTED)
    active_zones = [z for z in all_zones if z.is_active and z.strength != ZoneStrength.EXHAUSTED]

    logger.info(
        "zones_filtered",
        total_zones=len(all_zones),
        active_zones=len(active_zones),
        exhausted_removed=len(all_zones) - len(active_zones),
    )

    # Sort zones by significance score (highest first)
    active_zones.sort(key=lambda z: z.significance_score, reverse=True)

    # Log top zones
    if active_zones:
        top_zones = active_zones[:3]
        logger.info(
            "top_zones_summary",
            top_zone_count=len(top_zones),
            top_zones=[
                {
                    "type": z.zone_type.value,
                    "strength": z.strength.value,
                    "proximity": z.proximity_to_level,
                    "significance": z.significance_score,
                    "price_range": f"{z.price_range.low}-{z.price_range.high}",
                }
                for z in top_zones
            ],
        )

    logger.info(
        "zone_mapping_complete",
        range_id=str(trading_range.id),
        active_zones=len(active_zones),
        demand_zones_active=len([z for z in active_zones if z.zone_type == ZoneType.DEMAND]),
        supply_zones_active=len([z for z in active_zones if z.zone_type == ZoneType.SUPPLY]),
    )

    return active_zones


# Story 11.9d: ZoneMapper class
class ZoneMapper:
    """
    Class-based zone mapper for Story 11.9d implementation.

    Provides an object-oriented interface for mapping supply and demand zones.
    This class wraps the functional map_supply_demand_zones() API to match
    Story 11.9 requirements while maintaining backward compatibility.

    Attributes:
        zone_thickness_pct: Zone thickness as percentage (default: 0.02 = 2%)

    Example:
        >>> mapper = ZoneMapper(zone_thickness_pct=0.02)
        >>> supply_zones = mapper.map_supply_zones(bars, lookback=100)
        >>> demand_zones = mapper.map_demand_zones(bars, lookback=100)
    """

    def __init__(self, zone_thickness_pct: float = 0.02) -> None:
        """
        Initialize zone mapper with zone thickness percentage.

        Args:
            zone_thickness_pct: Zone thickness as decimal (default: 0.02 = 2%)

        Note:
            Zone thickness determines the vertical size of zones. The current
            implementation uses bar-based zone detection rather than percentage-based
            thickness, so this parameter is for interface compatibility.
        """
        self.zone_thickness_pct = zone_thickness_pct

        logger.debug(
            "zone_mapper_initialized",
            zone_thickness_pct=zone_thickness_pct,
        )

    def map_supply_zones(
        self,
        bars: list[OHLCVBar],
        lookback: int = 100,
        volume_analysis: list[VolumeAnalysis] | None = None,
        trading_range: TradingRange | None = None,
    ) -> list[Zone]:
        """
        Map supply zones in price action.

        Args:
            bars: OHLCV bars to analyze
            lookback: Number of bars to analyze (default: 100)
            volume_analysis: Optional volume analysis results
            trading_range: Optional trading range for zone proximity calculation

        Returns:
            List of Zone objects with type=SUPPLY

        Example:
            >>> supply_zones = mapper.map_supply_zones(bars, lookback=100)
            >>> for zone in supply_zones:
            ...     if zone.strength == ZoneStrength.FRESH:
            ...         print(f"Fresh supply zone at ${zone.price_range.midpoint}")
        """
        if trading_range is None or volume_analysis is None:
            # Cannot use the full map_supply_demand_zones function without trading range
            logger.warning(
                "incomplete_parameters",
                message="trading_range and volume_analysis required for zone mapping",
            )
            return []

        # Use the existing function to get all zones
        all_zones = map_supply_demand_zones(trading_range, bars, volume_analysis)

        # Filter for supply zones only
        supply_zones = [z for z in all_zones if z.zone_type == ZoneType.SUPPLY]

        return supply_zones

    def map_demand_zones(
        self,
        bars: list[OHLCVBar],
        lookback: int = 100,
        volume_analysis: list[VolumeAnalysis] | None = None,
        trading_range: TradingRange | None = None,
    ) -> list[Zone]:
        """
        Map demand zones in price action.

        Args:
            bars: OHLCV bars to analyze
            lookback: Number of bars to analyze (default: 100)
            volume_analysis: Optional volume analysis results
            trading_range: Optional trading range for zone proximity calculation

        Returns:
            List of Zone objects with type=DEMAND

        Example:
            >>> demand_zones = mapper.map_demand_zones(bars, lookback=100)
            >>> for zone in demand_zones:
            ...     if zone.strength == ZoneStrength.FRESH:
            ...         print(f"Fresh demand zone at ${zone.price_range.midpoint}")
        """
        if trading_range is None or volume_analysis is None:
            # Cannot use the full map_supply_demand_zones function without trading range
            logger.warning(
                "incomplete_parameters",
                message="trading_range and volume_analysis required for zone mapping",
            )
            return []

        # Use the existing function to get all zones
        all_zones = map_supply_demand_zones(trading_range, bars, volume_analysis)

        # Filter for demand zones only
        demand_zones = [z for z in all_zones if z.zone_type == ZoneType.DEMAND]

        return demand_zones
