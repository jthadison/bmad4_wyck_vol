"""
Integration tests for Forex Volume Validation (Story 8.3.1).

Tests full volume validation chain with realistic forex data:
- EUR/USD spring with low tick volume during London session
- GBP/JPY spring during NFP news event (rejection)
- AAPL stock validation (backward compatibility)

Author: Story 8.3.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.effort_result import EffortResult
from src.models.forex import ForexSession, NewsEvent, NewsImpactLevel
from src.models.ohlcv import OHLCVBar
from src.models.validation import (
    ValidationContext,
    ValidationStatus,
)
from src.models.volume_analysis import VolumeAnalysis
from src.signal_generator.validators.volume_validator import VolumeValidator


class MockPattern:
    """Mock Pattern for integration testing."""

    def __init__(self, pattern_type: str, timestamp: datetime):
        self.id = uuid4()
        self.pattern_type = pattern_type
        self.test_confirmed = False
        self.pattern_bar_timestamp = timestamp


class MockMarketContext:
    """Mock MarketContext with news events."""

    def __init__(self, news_event: NewsEvent | None = None):
        self.news_event = news_event


def create_realistic_forex_volume_analysis(
    current_tick_volume: int,
    avg_tick_volume: int,
    close_position: Decimal = Decimal("0.5"),
) -> VolumeAnalysis:
    """Create realistic forex VolumeAnalysis with tick volume."""
    volume_ratio = Decimal(str(current_tick_volume)) / Decimal(str(avg_tick_volume))

    ohlcv_bar = OHLCVBar(
        symbol="EUR/USD",
        timeframe="5m",
        timestamp=datetime(2025, 12, 1, 14, 0, tzinfo=UTC),
        open=Decimal("1.0850"),
        high=Decimal("1.0860"),
        low=Decimal("1.0840"),
        close=Decimal("1.0855"),
        volume=current_tick_volume,
        spread=Decimal("0.0002"),
    )

    return VolumeAnalysis(
        bar=ohlcv_bar,
        volume_ratio=volume_ratio,
        close_position=close_position,
        effort_result=EffortResult.NORMAL,
    )


# ============================================================================
# Integration Test 1: EUR/USD Spring with Low Tick Volume (AC 7)
# ============================================================================


@pytest.mark.asyncio
async def test_eur_usd_spring_low_tick_volume_integration() -> None:
    """
    Integration Test: EUR/USD spring with low tick volume during London session.

    Scenario:
    ---------
    - Symbol: EUR/USD (forex pair)
    - Pattern: Spring
    - Timeframe: 5-minute bars
    - Session: London (14:00 UTC = 9am EST)
    - Tick volumes (last 100 bars): avg = 1400 ticks during London session
    - Spring bar: 700 ticks
    - Ratio: 50% (well below 85% threshold)

    Expected:
    ---------
    - Volume validation: PASS
    - Metadata includes:
      * volume_source = "TICK"
      * forex_session = "LONDON"
      * volume_percentile (calculated from historical data)
      * volume_interpretation explaining tick volume
    """
    # Setup: London session timestamp
    pattern_time = datetime(2025, 12, 1, 14, 0, tzinfo=UTC)  # 2pm UTC = London session

    # Create pattern
    pattern = MockPattern("SPRING", timestamp=pattern_time)

    # Create realistic tick volume data (last 100 bars during London session)
    # London session typically has 1200-1600 ticks per 5min bar
    historical_volumes = [
        Decimal(str(v))
        for v in [
            1200,
            1300,
            1400,
            1500,
            1350,
            1450,
            1400,
            1300,
            1250,
            1550,  # 10
            1600,
            1400,
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,
            1350,
            1450,  # 20
            1400,
            1500,
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,
            1400,
            1500,  # 30
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,
            1400,
            1500,
            1350,
            1450,  # 40
            1500,
            1400,
            1300,
            1250,
            1400,
            1500,
            1350,
            1450,
            1500,
            1400,  # 50
            1300,
            1250,
            1400,
            1500,
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,  # 60
            1400,
            1500,
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,
            1400,
            1500,  # 70
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,
            1400,
            1500,
            1350,
            1450,  # 80
            1500,
            1400,
            1300,
            1250,
            1400,
            1500,
            1350,
            1450,
            1500,
            1400,  # 90
            1300,
            1250,
            1400,
            1500,
            1350,
            1450,
            1500,
            1400,
            1300,
            1250,  # 100
        ]
    ]

    # Create volume analysis (spring bar = 700 ticks, avg = 1400)
    volume_analysis = create_realistic_forex_volume_analysis(
        current_tick_volume=700,
        avg_tick_volume=1400,  # 50% ratio
    )

    # Create validation context
    context = ValidationContext(
        pattern=pattern,
        symbol="EUR/USD",
        timeframe="5m",
        volume_analysis=volume_analysis,
        asset_class="FOREX",
        forex_session=ForexSession.LONDON,
        historical_volumes=historical_volumes,
    )

    # Execute validation
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Assertions
    assert (
        result.status == ValidationStatus.PASS
    ), f"Expected PASS, got {result.status}: {result.reason}"

    # Verify forex-specific metadata
    assert result.metadata is not None, "Metadata should be present for PASS result"
    assert result.metadata["volume_source"] == "TICK"
    assert result.metadata["forex_session"] == "LONDON"
    assert result.metadata["baseline_type"] == "session_average"

    # Verify percentile calculation
    assert "volume_percentile" in result.metadata
    percentile = result.metadata["volume_percentile"]
    assert 0 <= percentile <= 100
    # 700 ticks is below all historical values (1200-1600), should be low percentile
    assert percentile < 10, f"Expected low percentile for 700 ticks (avg 1400), got {percentile}"

    # Verify Wyckoff-aware interpretation (P2 enhancement)
    assert "volume_interpretation" in result.metadata
    assert "activity" in result.metadata["volume_interpretation"].lower()
    # Should mention Wyckoff concepts like "selling exhaustion" for spring
    assert (
        "wyckoff" in result.metadata["volume_interpretation"].lower()
        or "exhaustion" in result.metadata["volume_interpretation"].lower()
    )


# ============================================================================
# Integration Test 2: GBP/JPY Spring During NFP (AC 7)
# ============================================================================


@pytest.mark.asyncio
async def test_gbp_jpy_spring_during_nfp_rejected() -> None:
    """
    Integration Test: GBP/JPY spring during NFP news event is rejected.

    Scenario:
    ---------
    - Symbol: GBP/JPY (forex pair)
    - Pattern: Spring
    - Timeframe: 5-minute bars
    - Event: NFP (Non-Farm Payroll) release at 8:30am EST (13:30 UTC)
    - Pattern bar timestamp: 13:30 UTC (exact NFP time)
    - Normal tick volume: 1200 ticks
    - NFP spike tick volume: 4800 ticks (400% spike, below 5x anomaly threshold)
    - Ratio: 400% (massive spike, but news-driven)

    Expected:
    ---------
    - Volume validation: FAIL
    - Rejection reason: "news-driven tick spike"
    - Metadata includes news_event = "NFP"

    Note: Using 4.0x volume (below 5x anomaly threshold) so news event check
          catches it instead of the general spike detector (P2 enhancement).
    """
    # Setup: NFP release time
    nfp_time = datetime(2025, 12, 6, 13, 30, tzinfo=UTC)  # First Friday, 8:30am EST

    # Create NFP news event
    nfp_event = NewsEvent(
        event_type="NFP",
        event_date=nfp_time,
        impact_level=NewsImpactLevel.HIGH,
        affected_symbols=["EUR/USD", "GBP/USD", "GBP/JPY", "USD/JPY"],
    )

    # Create pattern at NFP time
    pattern = MockPattern("SPRING", timestamp=nfp_time)

    # Create volume analysis (4800 tick spike vs 1200 avg = 4.0x ratio)
    # NOTE: Using 4.0x (below 5x anomaly threshold) so news event check catches it
    volume_analysis = VolumeAnalysis(
        bar=OHLCVBar(
            symbol="GBP/JPY",
            timeframe="5m",
            timestamp=nfp_time,
            open=Decimal("193.50"),
            high=Decimal("194.20"),
            low=Decimal("192.80"),
            close=Decimal("193.90"),
            volume=4800,  # 400% tick spike (below 5x anomaly threshold)
            spread=Decimal("0.03"),  # 3 pip spread
        ),
        volume_ratio=Decimal("4.0"),  # 400% spike
        close_position=Decimal("0.7"),
        effort_result=EffortResult.CLIMACTIC,
    )

    # Create market context with NFP event
    market_context = MockMarketContext(news_event=nfp_event)

    # Create validation context
    context = ValidationContext(
        pattern=pattern,
        symbol="GBP/JPY",
        timeframe="5m",
        volume_analysis=volume_analysis,
        asset_class="FOREX",
        forex_session=ForexSession.OVERLAP,  # London/NY overlap
        market_context=market_context,
    )

    # Execute validation
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Assertions
    assert result.status == ValidationStatus.FAIL, "NFP tick spike should be rejected"

    # Verify rejection reason mentions news event
    assert result.reason is not None
    assert "nfp" in result.reason.lower()
    assert "news event" in result.reason.lower() or "news-driven" in result.reason.lower()

    # Verify metadata includes news event
    assert result.metadata is not None
    assert result.metadata["news_event"] == "NFP"
    assert result.metadata["pattern_bar_timestamp"] == nfp_time.isoformat()


# ============================================================================
# Integration Test 3: Stock Backward Compatibility (AC 10)
# ============================================================================


@pytest.mark.asyncio
async def test_stock_aapl_spring_backward_compatibility() -> None:
    """
    Integration Test: AAPL stock spring still uses original volume thresholds.

    Scenario:
    ---------
    - Symbol: AAPL (stock)
    - Pattern: Spring
    - Timeframe: 1-day bars
    - Volume: 800K shares (avg: 1M shares)
    - Ratio: 80% (would PASS forex 85% threshold, but FAIL stock 70%)

    Expected:
    ---------
    - Volume validation: FAIL
    - Threshold used: 0.7 (stock threshold, not forex 0.85)
    - No forex metadata fields
    """
    # Setup: Stock pattern
    pattern_time = datetime(2025, 12, 1, 20, 0, tzinfo=UTC)  # Market close
    pattern = MockPattern("SPRING", timestamp=pattern_time)

    # Create volume analysis (800K vs 1M avg)
    volume_analysis = VolumeAnalysis(
        bar=OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=pattern_time,
            open=Decimal("180.00"),
            high=Decimal("182.00"),
            low=Decimal("178.50"),
            close=Decimal("181.00"),
            volume=800000,  # 800K shares
            spread=Decimal("0.50"),
        ),
        volume_ratio=Decimal("0.80"),  # 80%
        close_position=Decimal("0.6"),
        effort_result=EffortResult.NORMAL,
    )

    # Create validation context (asset_class defaults to STOCK)
    context = ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=volume_analysis,
        asset_class="STOCK",  # Explicit stock validation
    )

    # Execute validation
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Assertions
    assert (
        result.status == ValidationStatus.FAIL
    ), "Stock with 80% volume should fail (> 70% threshold)"

    # Verify stock threshold used (0.7, not forex 0.85)
    assert result.reason is not None
    # Check that the threshold comparison is in the reason (format may vary)
    assert "0.7" in result.reason and ">=" in result.reason

    # Verify NO forex metadata
    assert result.metadata is not None
    assert result.metadata.get("volume_source") != "TICK"
    assert "forex_session" not in result.metadata
    assert result.metadata["asset_class"] == "STOCK"
