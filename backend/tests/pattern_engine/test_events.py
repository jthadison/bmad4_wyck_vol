"""
Unit tests for PatternDetectedEvent and related event models.

Story 19.3: Pattern Detection Integration

Tests cover:
- PatternDetectedEvent creation and validation
- Factory methods for each pattern type
- Serialization and JSON encoding
- Event ID uniqueness
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.pattern_engine.events import PatternDetectedEvent, PatternType

# =============================
# Fixtures
# =============================


@pytest.fixture
def sample_bar() -> OHLCVBar:
    """Create a sample OHLCVBar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1m",
        timestamp=datetime.now(UTC),
        open=Decimal("150.00"),
        high=Decimal("151.00"),
        low=Decimal("149.50"),
        close=Decimal("150.50"),
        volume=100000,
        spread=Decimal("1.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


# =============================
# PatternType Tests
# =============================


class TestPatternType:
    """Tests for PatternType enum."""

    def test_all_pattern_types_defined(self):
        """All 6 Wyckoff pattern types are defined."""
        assert PatternType.SPRING.value == "SPRING"
        assert PatternType.SOS.value == "SOS"
        assert PatternType.LPS.value == "LPS"
        assert PatternType.UTAD.value == "UTAD"
        assert PatternType.AR.value == "AR"
        assert PatternType.SC.value == "SC"

    def test_pattern_type_count(self):
        """Exactly 6 pattern types are defined."""
        assert len(PatternType) == 6


# =============================
# PatternDetectedEvent Tests
# =============================


class TestPatternDetectedEventCreation:
    """Tests for PatternDetectedEvent creation."""

    def test_create_event_with_required_fields(self, sample_bar):
        """Event can be created with required fields."""
        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        assert event.symbol == "AAPL"
        assert event.pattern_type == PatternType.SPRING
        assert event.confidence == 0.85
        assert event.phase == WyckoffPhase.C
        assert event.bar_data is not None

    def test_event_id_is_uuid(self, sample_bar):
        """Event ID is a valid UUID."""
        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        assert isinstance(event.event_id, UUID)

    def test_event_ids_are_unique(self, sample_bar):
        """Each event gets a unique ID."""
        event1 = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )
        event2 = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        assert event1.event_id != event2.event_id

    def test_timestamp_defaults_to_now(self, sample_bar):
        """Timestamp defaults to current UTC time."""
        before = datetime.now(UTC)
        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )
        after = datetime.now(UTC)

        assert before <= event.timestamp <= after

    def test_levels_defaults_to_empty_dict(self, sample_bar):
        """Levels defaults to empty dict."""
        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        assert event.levels == {}

    def test_metadata_defaults_to_empty_dict(self, sample_bar):
        """Metadata defaults to empty dict."""
        event = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.85,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )

        assert event.metadata == {}


class TestPatternDetectedEventValidation:
    """Tests for PatternDetectedEvent validation."""

    def test_confidence_must_be_between_0_and_1(self, sample_bar):
        """Confidence must be between 0.0 and 1.0."""
        # Valid lower bound
        event_low = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=0.0,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )
        assert event_low.confidence == 0.0

        # Valid upper bound
        event_high = PatternDetectedEvent(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            confidence=1.0,
            phase=WyckoffPhase.C,
            bar_data=sample_bar.model_dump(),
        )
        assert event_high.confidence == 1.0

        # Invalid: below 0
        with pytest.raises(ValueError):
            PatternDetectedEvent(
                symbol="AAPL",
                pattern_type=PatternType.SPRING,
                confidence=-0.1,
                phase=WyckoffPhase.C,
                bar_data=sample_bar.model_dump(),
            )

        # Invalid: above 1
        with pytest.raises(ValueError):
            PatternDetectedEvent(
                symbol="AAPL",
                pattern_type=PatternType.SPRING,
                confidence=1.1,
                phase=WyckoffPhase.C,
                bar_data=sample_bar.model_dump(),
            )

    def test_symbol_must_not_be_empty(self, sample_bar):
        """Symbol must not be empty."""
        with pytest.raises(ValueError):
            PatternDetectedEvent(
                symbol="",
                pattern_type=PatternType.SPRING,
                confidence=0.85,
                phase=WyckoffPhase.C,
                bar_data=sample_bar.model_dump(),
            )


# =============================
# Factory Method Tests
# =============================


class TestPatternDetectedEventFactoryMethods:
    """Tests for factory methods creating events from patterns."""

    def test_from_spring(self, sample_bar):
        """from_spring creates Spring event correctly."""
        event = PatternDetectedEvent.from_spring(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.C,
            confidence=0.85,
            creek_level=148.50,
            ice_level=152.00,
            penetration_pct=0.02,
            volume_ratio=0.65,
        )

        assert event.pattern_type == PatternType.SPRING
        assert event.symbol == "AAPL"
        assert event.phase == WyckoffPhase.C
        assert event.confidence == 0.85
        assert event.levels["creek"] == 148.50
        assert event.levels["ice"] == 152.00
        assert event.metadata["penetration_pct"] == 0.02
        assert event.metadata["volume_ratio"] == 0.65

    def test_from_sos(self, sample_bar):
        """from_sos creates SOS event correctly."""
        event = PatternDetectedEvent.from_sos(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.D,
            confidence=0.90,
            ice_level=152.00,
            breakout_pct=0.03,
            volume_ratio=1.8,
        )

        assert event.pattern_type == PatternType.SOS
        assert event.phase == WyckoffPhase.D
        assert event.levels["ice"] == 152.00
        assert event.metadata["breakout_pct"] == 0.03
        assert event.metadata["volume_ratio"] == 1.8

    def test_from_lps(self, sample_bar):
        """from_lps creates LPS event correctly."""
        event = PatternDetectedEvent.from_lps(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.D,
            confidence=0.80,
            ice_level=152.00,
            pullback_pct=0.015,
        )

        assert event.pattern_type == PatternType.LPS
        assert event.phase == WyckoffPhase.D
        assert event.levels["ice"] == 152.00
        assert event.metadata["pullback_pct"] == 0.015

    def test_from_utad(self, sample_bar):
        """from_utad creates UTAD event correctly."""
        event = PatternDetectedEvent.from_utad(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.D,
            confidence=0.75,
            ice_level=152.00,
            penetration_pct=0.025,
            volume_ratio=1.6,
        )

        assert event.pattern_type == PatternType.UTAD
        assert event.levels["ice"] == 152.00
        assert event.metadata["penetration_pct"] == 0.025
        assert event.metadata["volume_ratio"] == 1.6

    def test_from_ar(self, sample_bar):
        """from_ar creates AR event correctly."""
        event = PatternDetectedEvent.from_ar(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.A,
            confidence=0.80,
            recovery_pct=0.45,
            prior_pattern="SC",
        )

        assert event.pattern_type == PatternType.AR
        assert event.phase == WyckoffPhase.A
        assert event.metadata["recovery_pct"] == 0.45
        assert event.metadata["prior_pattern"] == "SC"

    def test_from_sc(self, sample_bar):
        """from_sc creates SC event correctly."""
        event = PatternDetectedEvent.from_sc(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.A,
            confidence=0.85,
            volume_ratio=2.5,
        )

        assert event.pattern_type == PatternType.SC
        assert event.phase == WyckoffPhase.A
        assert event.metadata["volume_ratio"] == 2.5


# =============================
# Serialization Tests
# =============================


class TestPatternDetectedEventSerialization:
    """Tests for event serialization."""

    def test_model_dump_serializes_correctly(self, sample_bar):
        """model_dump() produces serializable dict."""
        event = PatternDetectedEvent.from_spring(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.C,
            confidence=0.85,
            creek_level=148.50,
        )

        data = event.model_dump()

        assert data["symbol"] == "AAPL"
        assert data["pattern_type"] == "SPRING"
        assert data["confidence"] == 0.85
        assert data["phase"] == "C"
        assert "event_id" in data
        assert "timestamp" in data

    def test_json_encoding(self, sample_bar):
        """Event can be serialized to JSON."""
        event = PatternDetectedEvent.from_spring(
            symbol="AAPL",
            bar=sample_bar,
            phase=WyckoffPhase.C,
            confidence=0.85,
            creek_level=148.50,
        )

        json_str = event.model_dump_json()

        assert '"symbol":"AAPL"' in json_str
        assert '"pattern_type":"SPRING"' in json_str
        assert '"phase":"C"' in json_str
