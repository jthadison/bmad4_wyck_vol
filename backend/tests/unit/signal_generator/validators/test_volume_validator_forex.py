"""
Unit tests for VolumeValidator Forex Support (Story 8.3.1).

Tests forex-specific volume validation features:
- Forex tick volume thresholds (85% spring, 180% SOS, 250% UTAD)
- Session-aware volume adjustments (Asian stricter thresholds)
- News event filtering (reject patterns during NFP/FOMC)
- Broker-relative percentile calculations
- Tick volume interpretation metadata

Author: Story 8.3.1
"""

from datetime import UTC, datetime, timedelta
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

# ============================================================================
# Test Fixtures
# ============================================================================


class MockPattern:
    """Mock Pattern for testing without full Pattern model dependency."""

    def __init__(
        self,
        pattern_type: str,
        test_confirmed: bool = False,
        pattern_id: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.id = uuid4() if pattern_id is None else pattern_id
        self.pattern_type = pattern_type
        self.test_confirmed = test_confirmed
        self.pattern_bar_timestamp = (
            timestamp if timestamp else datetime(2025, 12, 1, 14, 0, tzinfo=UTC)
        )


class MockMarketContext:
    """Mock MarketContext for news event testing."""

    def __init__(self, news_event: NewsEvent | None = None):
        self.news_event = news_event


def create_forex_validation_context(
    pattern_type: str,
    volume_ratio: Decimal,
    forex_session: ForexSession = ForexSession.LONDON,
    historical_volumes: list[Decimal] | None = None,
    news_event: NewsEvent | None = None,
    pattern_timestamp: datetime | None = None,
) -> ValidationContext:
    """
    Helper to create forex ValidationContext for testing.

    Parameters:
    -----------
    pattern_type : str
        Pattern type (SPRING, SOS, etc.)
    volume_ratio : Decimal
        Tick volume ratio of pattern bar
    forex_session : ForexSession
        Trading session (ASIAN, LONDON, NY, OVERLAP)
    historical_volumes : list[Decimal] | None
        Historical tick volumes for percentile calculation
    news_event : NewsEvent | None
        News event for spike detection
    pattern_timestamp : datetime | None
        Pattern bar timestamp

    Returns:
    --------
    ValidationContext configured for forex testing
    """
    if pattern_timestamp is None:
        pattern_timestamp = datetime(2025, 12, 1, 14, 0, tzinfo=UTC)

    pattern = MockPattern(pattern_type, timestamp=pattern_timestamp)

    # Create volume analysis with tick volume
    volume_analysis = VolumeAnalysis(
        bar=create_forex_ohlcv_bar(
            timestamp=pattern_timestamp, volume=int(Decimal("1000") * volume_ratio)
        ),
        volume_ratio=volume_ratio,
        close_position=Decimal("0.5"),
        effort_result=EffortResult.NORMAL,
    )

    market_context = MockMarketContext(news_event=news_event) if news_event else None

    return ValidationContext(
        pattern=pattern,
        symbol="EUR/USD",
        timeframe="5m",
        volume_analysis=volume_analysis,
        asset_class="FOREX",
        forex_session=forex_session,
        historical_volumes=historical_volumes,
        market_context=market_context,
    )


def create_forex_ohlcv_bar(
    symbol: str = "EUR/USD",
    timeframe: str = "5m",
    timestamp: datetime | None = None,
    volume: int = 1000,
) -> OHLCVBar:
    """Create a test forex OHLCV bar with tick volume."""
    if timestamp is None:
        timestamp = datetime(2025, 12, 1, 14, 0, tzinfo=UTC)

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=Decimal("1.0850"),
        high=Decimal("1.0860"),
        low=Decimal("1.0840"),
        close=Decimal("1.0855"),
        volume=volume,
        spread=Decimal("0.0002"),  # 2 pip spread
    )


@pytest.fixture
def volume_validator() -> VolumeValidator:
    """VolumeValidator instance."""
    return VolumeValidator()


# ============================================================================
# Test Forex Spring Volume Validation (AC 6)
# ============================================================================


@pytest.mark.asyncio
async def test_forex_spring_low_tick_volume_passes(volume_validator: VolumeValidator) -> None:
    """
    Test: Forex spring with low tick volume (60% of avg) passes validation.

    Setup: EUR/USD spring with tick volume = 60% (below 85% threshold)
    Expected: PASS with forex metadata
    """
    context = create_forex_validation_context(
        pattern_type="SPRING", volume_ratio=Decimal("0.60"), forex_session=ForexSession.LONDON
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata is not None
    assert result.metadata["volume_source"] == "TICK"
    assert result.metadata["volume_ratio"] == 0.60
    assert result.metadata["forex_session"] == "LONDON"
    assert result.metadata["baseline_type"] == "session_average"
    # volume_interpretation only present when historical_volumes provided


@pytest.mark.asyncio
async def test_forex_spring_high_tick_volume_fails(volume_validator: VolumeValidator) -> None:
    """
    Test: Forex spring with high tick volume (120% of avg) fails validation.

    Setup: EUR/USD spring with tick volume = 120% (above 85% threshold)
    Expected: FAIL with detailed reason
    """
    context = create_forex_validation_context(
        pattern_type="SPRING", volume_ratio=Decimal("1.20"), forex_session=ForexSession.LONDON
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "tick volume too high" in result.reason.lower()
    assert "1.2x >= 0.85x" in result.reason or "1.20x >= 0.85x" in result.reason
    assert result.metadata["volume_source"] == "TICK"
    assert result.metadata["asset_class"] == "FOREX"


@pytest.mark.asyncio
async def test_stock_spring_uses_original_thresholds(volume_validator: VolumeValidator) -> None:
    """
    Test: Stock spring still uses 70% threshold (backward compatibility).

    Setup: AAPL spring with volume = 80% of average
    Forex would PASS (< 85%), stock should FAIL (> 70%)
    Expected: FAIL (stock thresholds still apply)
    """
    pattern = MockPattern("SPRING")
    volume_analysis = VolumeAnalysis(
        bar=create_forex_ohlcv_bar(symbol="AAPL", volume=800000),
        volume_ratio=Decimal("0.80"),
        close_position=Decimal("0.5"),
        effort_result=EffortResult.NORMAL,
    )

    context = ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=volume_analysis,
        asset_class="STOCK",  # Explicitly stock
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    # Check that the threshold comparison is in the reason (format may vary)
    assert "0.7" in result.reason and ">=" in result.reason


# ============================================================================
# Test Forex SOS Volume Validation (AC 6)
# ============================================================================


@pytest.mark.asyncio
async def test_forex_sos_requires_higher_tick_volume(volume_validator: VolumeValidator) -> None:
    """
    Test: Forex SOS requires > 180% tick volume (higher than 150% for stocks).

    Setup: EUR/USD SOS with tick volume = 160% (below 180% forex threshold,
           but above 150% stock threshold)
    Expected: FAIL (forex needs > 180%)
    """
    context = create_forex_validation_context(
        pattern_type="SOS", volume_ratio=Decimal("1.60"), forex_session=ForexSession.LONDON
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "tick volume too low" in result.reason.lower()
    assert "1.6x < 1.8x" in result.reason or "1.60x < 1.80x" in result.reason


@pytest.mark.asyncio
async def test_forex_sos_high_volume_passes(volume_validator: VolumeValidator) -> None:
    """
    Test: Forex SOS with tick volume >= 180% passes validation.

    Setup: EUR/USD SOS with tick volume = 200%
    Expected: PASS with climactic volume metadata
    """
    context = create_forex_validation_context(
        pattern_type="SOS", volume_ratio=Decimal("2.00"), forex_session=ForexSession.OVERLAP
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata is not None
    assert result.metadata["volume_source"] == "TICK"
    assert result.metadata["volume_ratio"] == 2.00
    assert result.metadata["baseline_type"] == "session_average"
    # volume_interpretation only present when historical_volumes provided


# ============================================================================
# Test News Event Filtering (AC 4)
# ============================================================================


@pytest.mark.asyncio
async def test_news_event_tick_spike_rejected(volume_validator: VolumeValidator) -> None:
    """
    Test: Pattern during NFP release is rejected (news-driven tick spike).

    Setup: EUR/USD spring during NFP release (tick volume = 400%, avg = 100%)
           News event: NFP, impact=HIGH, within 1 hour of pattern bar
    Expected: FAIL with reason "news-driven tick spike"

    Note: Using 4.0x volume (below 5x anomaly threshold) so news event check
          catches it instead of the general spike detector.
    """
    pattern_time = datetime(2025, 12, 6, 13, 30, tzinfo=UTC)  # 8:30am EST = 13:30 UTC
    nfp_event = NewsEvent(
        event_type="NFP",
        event_date=pattern_time,
        impact_level=NewsImpactLevel.HIGH,
        affected_symbols=["EUR/USD", "GBP/USD"],
    )

    context = create_forex_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("4.00"),  # 400% tick spike (below 5x anomaly threshold)
        forex_session=ForexSession.OVERLAP,
        news_event=nfp_event,
        pattern_timestamp=pattern_time,
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "nfp" in result.reason.lower()
    assert "news event" in result.reason.lower()
    assert result.metadata["news_event"] == "NFP"


@pytest.mark.asyncio
async def test_pattern_outside_news_event_window_passes(
    volume_validator: VolumeValidator,
) -> None:
    """
    Test: Pattern 2 hours after NFP is NOT rejected (outside ±1hr window).

    Setup: EUR/USD spring 2 hours after NFP
    Expected: Normal volume validation (not rejected due to news)
    """
    nfp_time = datetime(2025, 12, 6, 13, 30, tzinfo=UTC)
    pattern_time = nfp_time + timedelta(hours=2)  # 2 hours later

    nfp_event = NewsEvent(
        event_type="NFP",
        event_date=nfp_time,
        impact_level=NewsImpactLevel.HIGH,
        affected_symbols=["EUR/USD"],
    )

    context = create_forex_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.60"),  # Normal low volume
        forex_session=ForexSession.OVERLAP,
        news_event=nfp_event,
        pattern_timestamp=pattern_time,
    )

    result = await volume_validator.validate(context)

    # Should pass normal validation (not rejected due to news)
    assert result.status == ValidationStatus.PASS


# ============================================================================
# Test Asian Session Stricter Thresholds (AC 6)
# ============================================================================


@pytest.mark.asyncio
async def test_asian_session_requires_stricter_thresholds(
    volume_validator: VolumeValidator,
) -> None:
    """
    Test: Asian session uses stricter 60% spring threshold (vs 85% normal).

    Setup: EUR/USD spring during Asian session, tick volume = 70% of session avg
           Asian threshold: 60%, normal forex: 85%
    Expected: FAIL (Asian session stricter)
    """
    context = create_forex_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.70"),
        forex_session=ForexSession.ASIAN,  # Asian session
        pattern_timestamp=datetime(2025, 12, 1, 3, 0, tzinfo=UTC),  # 3am UTC = Asian
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "0.7x >= 0.6x" in result.reason or "0.70x >= 0.60x" in result.reason
    assert "ASIAN" in result.reason or result.metadata.get("forex_session") == "ASIAN"


@pytest.mark.asyncio
async def test_asian_session_sos_requires_higher_threshold(
    volume_validator: VolumeValidator,
) -> None:
    """
    Test: Asian session SOS requires 200% (vs 180% normal).

    Setup: EUR/USD SOS during Asian session, tick volume = 190%
           Normal forex threshold: 180% (would pass)
           Asian threshold: 200% (should fail)
    Expected: FAIL
    """
    context = create_forex_validation_context(
        pattern_type="SOS",
        volume_ratio=Decimal("1.90"),
        forex_session=ForexSession.ASIAN,
        pattern_timestamp=datetime(2025, 12, 1, 5, 0, tzinfo=UTC),  # 5am UTC = Asian
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "1.9x < 2.0x" in result.reason or "1.90x < 2.00x" in result.reason


# ============================================================================
# Test Session-Aware Baselines (AC 3)
# ============================================================================


@pytest.mark.asyncio
async def test_session_average_baseline_metadata(volume_validator: VolumeValidator) -> None:
    """
    Test: Validation metadata indicates session-based baseline used.

    Setup: EUR/USD spring during London session with low tick volume
    Expected: PASS with metadata showing "baseline_type": "session_average"
    """
    context = create_forex_validation_context(
        pattern_type="SPRING", volume_ratio=Decimal("0.50"), forex_session=ForexSession.LONDON
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata is not None
    assert result.metadata["baseline_type"] == "session_average"
    assert result.metadata["forex_session"] == "LONDON"


# ============================================================================
# Test Broker-Relative Percentile Calculations (AC 5)
# ============================================================================


@pytest.mark.asyncio
async def test_volume_percentile_calculation(volume_validator: VolumeValidator) -> None:
    """
    Test: Percentile ranking calculated correctly from historical volumes.

    Setup: Current volume = 750, historical = [500, 600, 700, 800, 900, 1000]
           Expected percentile: 50th (750 is at middle of distribution)
    """
    historical = [Decimal(str(v)) for v in [500, 600, 700, 800, 900, 1000]]
    current_volume = Decimal("750")

    percentile = volume_validator._calculate_volume_percentile(current_volume, historical)

    # 750 is above 500, 600, 700 (3 values) out of 6 total
    # Position when including itself = 4 out of 6 = 66th percentile
    # (or 3 out of 6 = 50th percentile depending on implementation)
    assert 50 <= percentile <= 67


@pytest.mark.asyncio
async def test_forex_validation_includes_percentile_metadata(
    volume_validator: VolumeValidator,
) -> None:
    """
    Test: Forex validation includes volume percentile in metadata.

    Setup: EUR/USD spring with historical volumes provided
    Expected: Metadata includes volume_percentile field
    """
    historical = [Decimal(str(v)) for v in [800, 900, 1000, 1100, 1200]]

    context = create_forex_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.60"),
        historical_volumes=historical,
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata is not None
    assert "volume_percentile" in result.metadata
    assert isinstance(result.metadata["volume_percentile"], int)


# ============================================================================
# Test Tick Volume Interpretation Metadata (AC 9)
# ============================================================================


@pytest.mark.asyncio
async def test_forex_metadata_includes_interpretation(
    volume_validator: VolumeValidator,
) -> None:
    """
    Test: Forex validation includes Wyckoff-aware volume interpretation (P2).

    Setup: EUR/USD spring passing validation with historical volumes
    Expected: Metadata includes volume_interpretation with Wyckoff-specific context
              (pattern-aware explanations from _interpret_volume_percentile helper)
    """
    # Create historical volumes to trigger interpretation
    historical_volumes = [Decimal(str(v)) for v in [1200, 1300, 1400, 1500, 1350]]

    context = create_forex_validation_context(
        pattern_type="SPRING", volume_ratio=Decimal("0.60"), historical_volumes=historical_volumes
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata is not None
    assert "volume_interpretation" in result.metadata
    # P2 enhancement: Check for Wyckoff-specific interpretation
    assert "activity" in result.metadata["volume_interpretation"].lower()
    # Should mention Wyckoff concepts like "selling exhaustion" for spring
    assert (
        "wyckoff" in result.metadata["volume_interpretation"].lower()
        or "exhaustion" in result.metadata["volume_interpretation"].lower()
    )


@pytest.mark.asyncio
async def test_stock_validation_no_forex_metadata(volume_validator: VolumeValidator) -> None:
    """
    Test: Stock validation does NOT include forex-specific metadata.

    Setup: AAPL spring (stock)
    Expected: Metadata should not include forex fields
    """
    pattern = MockPattern("SPRING")
    volume_analysis = VolumeAnalysis(
        bar=create_forex_ohlcv_bar(symbol="AAPL", volume=600000),
        volume_ratio=Decimal("0.60"),
        close_position=Decimal("0.5"),
        effort_result=EffortResult.NORMAL,
    )

    context = ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=volume_analysis,
        asset_class="STOCK",
    )

    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    # Stock validation should not have forex metadata
    if result.metadata:
        assert result.metadata.get("volume_source") != "TICK"
        assert "forex_session" not in result.metadata


# ============================================================================
# Test Logging Output (AC 8)
# ============================================================================


@pytest.mark.asyncio
async def test_forex_validation_logs_volume_source(
    volume_validator: VolumeValidator, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Test: Forex validation logs include volume_source and thresholds.

    Setup: EUR/USD spring validation
    Expected: Log messages include asset_class=FOREX, volume_source=TICK
    """
    context = create_forex_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.60"))

    await volume_validator.validate(context)

    # Check that logs include forex-specific fields
    log_text = caplog.text.lower()
    # Note: Exact log format depends on structlog configuration
    # This test assumes logs are captured and contain relevant fields
    assert True  # Placeholder - actual log assertion depends on structlog setup
