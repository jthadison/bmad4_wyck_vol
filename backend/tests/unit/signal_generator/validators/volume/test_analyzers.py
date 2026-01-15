"""
Unit tests for extracted volume analyzer components (Story 18.6.3).

Tests the analyzers extracted from volume_validator.py:
- NewsEventDetector
- VolumeAnomalyDetector
- PercentileCalculator
- ForexThresholdAdjuster
"""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import yaml

from src.models.effort_result import EffortResult
from src.models.forex import ForexSession
from src.models.market_context import AssetClass, MarketContext, MarketRegime, NewsEvent
from src.models.ohlcv import OHLCVBar
from src.models.validation import (
    ValidationContext,
    VolumeValidationConfig,
)
from src.models.volume_analysis import VolumeAnalysis
from src.signal_generator.validators.volume.analyzers import (
    NewsEventDetector,
    PercentileCalculator,
    VolumeAnomalyDetector,
)
from src.signal_generator.validators.volume.forex import ForexThresholdAdjuster

# ============================================================================
# Mock Pattern for Testing
# ============================================================================


class MockPattern:
    """Mock Pattern for testing without full Pattern model dependency."""

    def __init__(
        self,
        pattern_type: str = "SPRING",
        pattern_id: str | None = None,
    ) -> None:
        self.id = uuid4() if pattern_id is None else pattern_id
        self.pattern_type = pattern_type
        self.pattern_bar_timestamp = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)


# ============================================================================
# Helper Functions
# ============================================================================


def create_test_ohlcv_bar(
    symbol: str = "EURUSD",
    timeframe: str = "1h",
    timestamp: datetime | None = None,
    volume: int = 1000,
) -> OHLCVBar:
    """Create a test OHLCV bar."""
    if timestamp is None:
        timestamp = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=Decimal("1.0850"),
        high=Decimal("1.0860"),
        low=Decimal("1.0840"),
        close=Decimal("1.0855"),
        volume=volume,
        spread=Decimal("0.0002"),
    )


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def volume_config() -> VolumeValidationConfig:
    """Default volume validation configuration."""
    return VolumeValidationConfig()


@pytest.fixture
def base_pattern() -> MockPattern:
    """Create a basic MockPattern for testing."""
    return MockPattern(pattern_type="SPRING")


@pytest.fixture
def volume_analysis() -> VolumeAnalysis:
    """Create a basic VolumeAnalysis for testing."""
    bar = create_test_ohlcv_bar()
    return VolumeAnalysis(
        bar=bar,
        volume_ratio=Decimal("0.5"),
        spread_ratio=Decimal("1.0"),
        close_position=Decimal("0.7"),
        effort_result=EffortResult.NORMAL,
    )


@pytest.fixture
def forex_context(base_pattern: MockPattern, volume_analysis: VolumeAnalysis) -> ValidationContext:
    """Create a forex ValidationContext for testing."""
    return ValidationContext(
        pattern=base_pattern,  # type: ignore[arg-type]
        symbol="EURUSD",
        timeframe="1h",
        volume_analysis=volume_analysis,
        asset_class="FOREX",
        forex_session=ForexSession.LONDON,
    )


@pytest.fixture
def stock_context(volume_analysis: VolumeAnalysis) -> ValidationContext:
    """Create a stock ValidationContext for testing."""
    pattern = MockPattern(pattern_type="SPRING")
    return ValidationContext(
        pattern=pattern,  # type: ignore[arg-type]
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=volume_analysis,
        asset_class="STOCK",
    )


# ============================================================================
# NewsEventDetector Tests
# ============================================================================


class TestNewsEventDetector:
    """Tests for NewsEventDetector class."""

    def test_init(self) -> None:
        """Test detector initialization."""
        detector = NewsEventDetector()
        assert detector is not None

    def test_news_window_constant(self) -> None:
        """Test news window is 1 hour."""
        assert NewsEventDetector.NEWS_WINDOW_HOURS == 1.0

    @pytest.mark.asyncio
    async def test_check_no_market_context(self, forex_context: ValidationContext) -> None:
        """Test check returns False when no market context."""
        detector = NewsEventDetector()
        forex_context.market_context = None

        is_spike, event = await detector.check(forex_context)

        assert is_spike is False
        assert event is None

    @pytest.mark.asyncio
    async def test_check_stock_asset_class_skipped(self, stock_context: ValidationContext) -> None:
        """Test check skips non-forex asset classes."""
        detector = NewsEventDetector()

        is_spike, event = await detector.check(stock_context)

        assert is_spike is False
        assert event is None

    def test_build_rejection_reason(self, forex_context: ValidationContext) -> None:
        """Test rejection reason formatting."""
        detector = NewsEventDetector()
        event_type = "NFP"

        reason = detector.build_rejection_reason(event_type, forex_context)

        assert "NFP" in reason
        assert "EURUSD" in reason
        assert "news event" in reason.lower()

    def test_build_rejection_metadata(self, forex_context: ValidationContext) -> None:
        """Test rejection metadata structure."""
        detector = NewsEventDetector()
        event_type = "FOMC"

        metadata = detector.build_rejection_metadata(event_type, forex_context)

        assert metadata["news_event"] == "FOMC"
        assert "pattern_bar_timestamp" in metadata
        assert metadata["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_check_at_exactly_one_hour_boundary_not_spike(
        self, forex_context: ValidationContext
    ) -> None:
        """Test that event at exactly 1.0 hour boundary is NOT detected as spike.

        The detector uses strict less-than comparison (time_diff < 1.0), so exactly
        1.0 hours should NOT trigger a spike detection.
        """
        detector = NewsEventDetector()

        # Create pattern timestamp
        pattern_time = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        forex_context.pattern.pattern_bar_timestamp = pattern_time

        # Create news event exactly 1.0 hour before pattern
        event_time = pattern_time - timedelta(hours=1.0)
        news_event = NewsEvent(
            symbol="EURUSD",
            event_date=event_time,
            event_type="NFP",
            impact_level="HIGH",
            description="Non-Farm Payrolls",
        )

        # Create market context with the news event
        market_context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="EURUSD",
            current_volatility=Decimal("0.5"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.SIDEWAYS,
            time_of_day=time(14, 30),
            market_session="REGULAR",
            forex_session=ForexSession.LONDON,
            news_event=news_event,
        )
        forex_context.market_context = market_context

        is_spike, event = await detector.check(forex_context)

        # At exactly 1.0 hour, should NOT be detected as spike (strict < comparison)
        assert is_spike is False
        assert event is None

    @pytest.mark.asyncio
    async def test_check_just_under_one_hour_is_spike(
        self, forex_context: ValidationContext
    ) -> None:
        """Test that event just under 1.0 hour IS detected as spike."""
        detector = NewsEventDetector()

        # Create pattern timestamp
        pattern_time = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        forex_context.pattern.pattern_bar_timestamp = pattern_time

        # Create news event 59 minutes before pattern (just under 1 hour)
        event_time = pattern_time - timedelta(minutes=59)
        news_event = NewsEvent(
            symbol="EURUSD",
            event_date=event_time,
            event_type="NFP",
            impact_level="HIGH",
            description="Non-Farm Payrolls",
        )

        # Create market context with the news event
        market_context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="EURUSD",
            current_volatility=Decimal("0.5"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.SIDEWAYS,
            time_of_day=time(14, 30),
            market_session="REGULAR",
            forex_session=ForexSession.LONDON,
            news_event=news_event,
        )
        forex_context.market_context = market_context

        is_spike, event = await detector.check(forex_context)

        # Just under 1.0 hour SHOULD be detected as spike
        assert is_spike is True
        assert event == "NFP"


# ============================================================================
# VolumeAnomalyDetector Tests
# ============================================================================


class TestVolumeAnomalyDetector:
    """Tests for VolumeAnomalyDetector class."""

    def test_anomaly_threshold_constant(self) -> None:
        """Test anomaly threshold is 5.0x."""
        assert VolumeAnomalyDetector.ANOMALY_THRESHOLD == Decimal("5.0")

    @pytest.mark.asyncio
    async def test_check_below_threshold(self, forex_context: ValidationContext) -> None:
        """Test check returns False for volume below threshold."""
        detector = VolumeAnomalyDetector()
        volume_ratio = Decimal("4.9")

        is_anomaly, reason = await detector.check(forex_context, volume_ratio)

        assert is_anomaly is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_at_threshold(self, forex_context: ValidationContext) -> None:
        """Test check returns True for volume at threshold."""
        detector = VolumeAnomalyDetector()
        volume_ratio = Decimal("5.0")

        is_anomaly, reason = await detector.check(forex_context, volume_ratio)

        assert is_anomaly is True
        assert reason is not None
        assert "5.0x" in reason

    @pytest.mark.asyncio
    async def test_check_above_threshold(self, forex_context: ValidationContext) -> None:
        """Test check returns True for volume above threshold."""
        detector = VolumeAnomalyDetector()
        volume_ratio = Decimal("7.5")

        is_anomaly, reason = await detector.check(forex_context, volume_ratio)

        assert is_anomaly is True
        assert "7.5x" in reason
        assert "flash crash" in reason.lower() or "fat finger" in reason.lower()

    @pytest.mark.asyncio
    async def test_check_stock_asset_class_skipped(self, stock_context: ValidationContext) -> None:
        """Test check skips non-forex asset classes."""
        detector = VolumeAnomalyDetector()
        # Even with extreme volume, stocks should be skipped
        volume_ratio = Decimal("10.0")

        is_anomaly, reason = await detector.check(stock_context, volume_ratio)

        assert is_anomaly is False
        assert reason is None

    def test_build_rejection_metadata(self, forex_context: ValidationContext) -> None:
        """Test rejection metadata structure."""
        detector = VolumeAnomalyDetector()
        volume_ratio = Decimal("6.5")

        metadata = detector.build_rejection_metadata(volume_ratio, forex_context)

        assert metadata["volume_ratio"] == 6.5
        assert metadata["anomaly_threshold"] == 5.0
        assert metadata["symbol"] == "EURUSD"
        assert "pattern_bar_timestamp" in metadata


# ============================================================================
# PercentileCalculator Tests
# ============================================================================


class TestPercentileCalculator:
    """Tests for PercentileCalculator class."""

    def test_calculate_empty_history(self) -> None:
        """Test calculate returns 50 for empty history."""
        calculator = PercentileCalculator()
        current = Decimal("100")
        history: list[Decimal] = []

        percentile = calculator.calculate(current, history)

        assert percentile == 50

    def test_calculate_lowest_value(self) -> None:
        """Test calculate for value below all history."""
        calculator = PercentileCalculator()
        current = Decimal("50")
        history = [Decimal(str(v)) for v in [100, 200, 300, 400, 500]]

        percentile = calculator.calculate(current, history)

        assert percentile == 0

    def test_calculate_highest_value(self) -> None:
        """Test calculate for value above all history."""
        calculator = PercentileCalculator()
        current = Decimal("600")
        history = [Decimal(str(v)) for v in [100, 200, 300, 400, 500]]

        percentile = calculator.calculate(current, history)

        assert percentile == 100

    def test_calculate_middle_value(self) -> None:
        """Test calculate for value in middle of history."""
        calculator = PercentileCalculator()
        current = Decimal("250")
        history = [Decimal(str(v)) for v in [100, 200, 300, 400, 500]]

        percentile = calculator.calculate(current, history)

        # 250 is above 100, 200 (2 values) = 40th percentile
        assert percentile == 40

    def test_interpret_extremely_low_spring(self) -> None:
        """Test interpretation for extremely low volume spring."""
        calculator = PercentileCalculator()

        interpretation = calculator.interpret(5, "SPRING")

        assert "exhaustion" in interpretation.lower()
        assert "bottom" in interpretation.lower()

    def test_interpret_very_low_spring(self) -> None:
        """Test interpretation for very low volume spring."""
        calculator = PercentileCalculator()

        interpretation = calculator.interpret(20, "SPRING")

        assert "exhaustion" in interpretation.lower()

    def test_interpret_below_average(self) -> None:
        """Test interpretation for below average volume."""
        calculator = PercentileCalculator()

        interpretation = calculator.interpret(35, "SPRING")

        assert "below average" in interpretation.lower()

    def test_interpret_above_average_sos(self) -> None:
        """Test interpretation for above average SOS."""
        calculator = PercentileCalculator()

        interpretation = calculator.interpret(60, "SOS")

        assert "above average" in interpretation.lower()
        assert "accumulation" in interpretation.lower()

    def test_interpret_high_volume_sos(self) -> None:
        """Test interpretation for high volume SOS."""
        calculator = PercentileCalculator()

        interpretation = calculator.interpret(85, "SOS")

        assert "top" in interpretation.lower() or "high" in interpretation.lower()
        assert "demand" in interpretation.lower() or "strength" in interpretation.lower()

    def test_interpret_climactic_sos(self) -> None:
        """Test interpretation for climactic volume SOS."""
        calculator = PercentileCalculator()

        interpretation = calculator.interpret(95, "SOS")

        assert "climactic" in interpretation.lower() or "exceptional" in interpretation.lower()


# ============================================================================
# ForexThresholdAdjuster Tests
# ============================================================================


class TestForexThresholdAdjuster:
    """Tests for ForexThresholdAdjuster class."""

    def setup_method(self) -> None:
        """Clear threshold cache before each test."""
        ForexThresholdAdjuster.clear_cache()

    def test_get_threshold_spring_london_session(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test spring threshold for London session."""
        adjuster = ForexThresholdAdjuster()
        forex_context.forex_session = ForexSession.LONDON

        threshold = adjuster.get_threshold("SPRING", "max", volume_config, forex_context)

        assert threshold == volume_config.forex_spring_max_volume

    def test_get_threshold_spring_asian_session(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test spring threshold for Asian session (stricter)."""
        adjuster = ForexThresholdAdjuster()
        forex_context.forex_session = ForexSession.ASIAN

        threshold = adjuster.get_threshold("SPRING", "max", volume_config, forex_context)

        # Asian session should use stricter threshold
        assert threshold == volume_config.forex_asian_spring_max_volume

    def test_get_threshold_sos_london_session(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test SOS threshold for London session."""
        adjuster = ForexThresholdAdjuster()
        forex_context.forex_session = ForexSession.LONDON

        threshold = adjuster.get_threshold("SOS", "min", volume_config, forex_context)

        assert threshold == volume_config.forex_sos_min_volume

    def test_get_threshold_sos_asian_session(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test SOS threshold for Asian session (stricter)."""
        adjuster = ForexThresholdAdjuster()
        forex_context.forex_session = ForexSession.ASIAN

        threshold = adjuster.get_threshold("SOS", "min", volume_config, forex_context)

        # Asian session should use stricter threshold
        assert threshold == volume_config.forex_asian_sos_min_volume

    def test_get_threshold_test_max(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test TEST pattern max threshold."""
        adjuster = ForexThresholdAdjuster()

        threshold = adjuster.get_threshold("TEST", "max", volume_config, forex_context)

        assert threshold == volume_config.forex_test_max_volume

    def test_get_threshold_utad_min(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test UTAD pattern min threshold."""
        adjuster = ForexThresholdAdjuster()

        threshold = adjuster.get_threshold("UTAD", "min", volume_config, forex_context)

        assert threshold == volume_config.forex_utad_min_volume

    def test_get_threshold_unknown_pattern_max(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test unknown pattern falls back to stock threshold."""
        adjuster = ForexThresholdAdjuster()

        threshold = adjuster.get_threshold("UNKNOWN", "max", volume_config, forex_context)

        # Falls back to stock spring threshold
        assert threshold == volume_config.spring_max_volume

    def test_get_threshold_unknown_pattern_min(
        self,
        volume_config: VolumeValidationConfig,
        forex_context: ValidationContext,
    ) -> None:
        """Test unknown pattern min falls back to stock threshold."""
        adjuster = ForexThresholdAdjuster()

        threshold = adjuster.get_threshold("UNKNOWN", "min", volume_config, forex_context)

        # Falls back to stock SOS threshold
        assert threshold == volume_config.sos_min_volume

    def test_clear_cache(self) -> None:
        """Test cache clearing functionality."""
        # First load config to populate cache
        adjuster = ForexThresholdAdjuster()
        adjuster._load_volume_thresholds_from_config()

        # Clear and verify
        ForexThresholdAdjuster.clear_cache()

        assert ForexThresholdAdjuster._threshold_config_cache is None

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """Test config loading when file doesn't exist.

        Uses tmp_path fixture for cleaner testing without complex Path mocks.
        """
        # Create a fake module path structure that will resolve to tmp_path
        fake_module = tmp_path / "a" / "b" / "c" / "d" / "e" / "fake.py"
        fake_module.parent.mkdir(parents=True, exist_ok=True)

        # Patch Path(__file__) to return our fake path
        with patch(
            "src.signal_generator.validators.volume.forex.threshold_adjuster.Path"
        ) as mock_path:
            mock_path.return_value = fake_module

            ForexThresholdAdjuster.clear_cache()
            config = ForexThresholdAdjuster._load_volume_thresholds_from_config()

        # Config should be empty dict when file doesn't exist
        assert config == {}


# ============================================================================
# Integration Tests
# ============================================================================


class TestAnalyzersIntegration:
    """Integration tests for analyzer components working together."""

    @pytest.mark.asyncio
    async def test_analyzers_imported_from_package(self) -> None:
        """Test all analyzers are properly exported from package."""
        from src.signal_generator.validators.volume.analyzers import (
            NewsEventDetector,
            PercentileCalculator,
            VolumeAnomalyDetector,
        )
        from src.signal_generator.validators.volume.forex import ForexThresholdAdjuster

        assert NewsEventDetector is not None
        assert VolumeAnomalyDetector is not None
        assert PercentileCalculator is not None
        assert ForexThresholdAdjuster is not None

    @pytest.mark.asyncio
    async def test_volume_validator_uses_analyzers(self) -> None:
        """Test VolumeValidator facade delegates to analyzers."""
        from src.signal_generator.validators.volume_validator import VolumeValidator

        validator = VolumeValidator()

        # Verify analyzer instances are created
        assert hasattr(validator, "_news_detector")
        assert hasattr(validator, "_anomaly_detector")
        assert hasattr(validator, "_threshold_adjuster")
        assert hasattr(validator, "_percentile_calculator")

        # Verify they are correct types
        assert isinstance(validator._news_detector, NewsEventDetector)
        assert isinstance(validator._anomaly_detector, VolumeAnomalyDetector)
        assert isinstance(validator._threshold_adjuster, ForexThresholdAdjuster)
        assert isinstance(validator._percentile_calculator, PercentileCalculator)
