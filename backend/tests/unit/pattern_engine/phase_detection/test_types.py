"""
Unit tests for phase_detection types module.

Tests all type imports, enum values, and dataclass instantiation.
"""

from datetime import datetime


class TestPhaseTypeEnum:
    """Tests for PhaseType enum."""

    def test_phase_type_values(self):
        """Test that PhaseType has all expected values."""
        from src.pattern_engine.phase_detection import PhaseType

        assert PhaseType.A.value == "A"
        assert PhaseType.B.value == "B"
        assert PhaseType.C.value == "C"
        assert PhaseType.D.value == "D"
        assert PhaseType.E.value == "E"

    def test_phase_type_has_five_phases(self):
        """Test that PhaseType has exactly 5 phases."""
        from src.pattern_engine.phase_detection import PhaseType

        assert len(PhaseType) == 5

    def test_phase_type_docstring_exists(self):
        """Test that PhaseType has documentation."""
        from src.pattern_engine.phase_detection import PhaseType

        assert PhaseType.__doc__ is not None
        assert "Wyckoff" in PhaseType.__doc__


class TestEventTypeEnum:
    """Tests for EventType enum."""

    def test_event_type_phase_a_events(self):
        """Test Phase A event types."""
        from src.pattern_engine.phase_detection import EventType

        assert EventType.SELLING_CLIMAX.value == "SC"
        assert EventType.AUTOMATIC_RALLY.value == "AR"
        assert EventType.SECONDARY_TEST.value == "ST"

    def test_event_type_phase_bc_events(self):
        """Test Phase B/C event types."""
        from src.pattern_engine.phase_detection import EventType

        assert EventType.SPRING.value == "SPRING"
        assert EventType.UPTHRUST_AFTER_DISTRIBUTION.value == "UTAD"

    def test_event_type_phase_d_events(self):
        """Test Phase D event types."""
        from src.pattern_engine.phase_detection import EventType

        assert EventType.SIGN_OF_STRENGTH.value == "SOS"
        assert EventType.SIGN_OF_WEAKNESS.value == "SOW"
        assert EventType.LAST_POINT_OF_SUPPORT.value == "LPS"
        assert EventType.LAST_POINT_OF_SUPPLY.value == "LPSY"


class TestPhaseEventDataclass:
    """Tests for PhaseEvent dataclass."""

    def test_phase_event_instantiation(self):
        """Test basic PhaseEvent instantiation."""
        from src.pattern_engine.phase_detection import EventType, PhaseEvent

        event = PhaseEvent(
            event_type=EventType.SELLING_CLIMAX,
            timestamp=datetime(2024, 1, 15, 10, 30),
            bar_index=100,
            price=150.50,
            volume=1000000.0,
        )

        assert event.event_type == EventType.SELLING_CLIMAX
        assert event.bar_index == 100
        assert event.price == 150.50
        assert event.volume == 1000000.0

    def test_phase_event_default_confidence(self):
        """Test PhaseEvent default confidence value."""
        from src.pattern_engine.phase_detection import EventType, PhaseEvent

        event = PhaseEvent(
            event_type=EventType.SPRING,
            timestamp=datetime.now(),
            bar_index=50,
            price=100.0,
            volume=500000.0,
        )

        assert event.confidence == 0.0

    def test_phase_event_default_metadata(self):
        """Test PhaseEvent default metadata is empty dict."""
        from src.pattern_engine.phase_detection import EventType, PhaseEvent

        event = PhaseEvent(
            event_type=EventType.SIGN_OF_STRENGTH,
            timestamp=datetime.now(),
            bar_index=200,
            price=175.0,
            volume=2000000.0,
        )

        assert event.metadata == {}
        assert isinstance(event.metadata, dict)

    def test_phase_event_with_metadata(self):
        """Test PhaseEvent with custom metadata."""
        from src.pattern_engine.phase_detection import EventType, PhaseEvent

        metadata = {"volume_ratio": 2.5, "spread": 5.0}
        event = PhaseEvent(
            event_type=EventType.SELLING_CLIMAX,
            timestamp=datetime.now(),
            bar_index=100,
            price=150.0,
            volume=1000000.0,
            confidence=0.85,
            metadata=metadata,
        )

        assert event.confidence == 0.85
        assert event.metadata["volume_ratio"] == 2.5


class TestPhaseResultDataclass:
    """Tests for PhaseResult dataclass."""

    def test_phase_result_instantiation(self):
        """Test basic PhaseResult instantiation."""
        from src.pattern_engine.phase_detection import PhaseResult, PhaseType

        result = PhaseResult(
            phase=PhaseType.B,
            confidence=0.75,
        )

        assert result.phase == PhaseType.B
        assert result.confidence == 0.75

    def test_phase_result_default_events(self):
        """Test PhaseResult default events is empty list."""
        from src.pattern_engine.phase_detection import PhaseResult, PhaseType

        result = PhaseResult(phase=PhaseType.A, confidence=0.8)

        assert result.events == []
        assert isinstance(result.events, list)

    def test_phase_result_default_values(self):
        """Test PhaseResult default values."""
        from src.pattern_engine.phase_detection import PhaseResult, PhaseType

        result = PhaseResult(phase=PhaseType.C, confidence=0.65)

        assert result.start_bar == 0
        assert result.duration_bars == 0
        assert result.metadata == {}

    def test_phase_result_with_events(self):
        """Test PhaseResult with events list."""
        from src.pattern_engine.phase_detection import (
            EventType,
            PhaseEvent,
            PhaseResult,
            PhaseType,
        )

        events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime.now(),
                bar_index=10,
                price=100.0,
                volume=1000000.0,
            ),
            PhaseEvent(
                event_type=EventType.AUTOMATIC_RALLY,
                timestamp=datetime.now(),
                bar_index=15,
                price=110.0,
                volume=500000.0,
            ),
        ]

        result = PhaseResult(
            phase=PhaseType.A,
            confidence=0.9,
            events=events,
            start_bar=10,
            duration_bars=20,
        )

        assert len(result.events) == 2
        assert result.events[0].event_type == EventType.SELLING_CLIMAX
        assert result.start_bar == 10
        assert result.duration_bars == 20


class TestDetectionConfigDataclass:
    """Tests for DetectionConfig dataclass."""

    def test_detection_config_default_values(self):
        """Test DetectionConfig default values."""
        from src.pattern_engine.phase_detection import DetectionConfig

        config = DetectionConfig()

        assert config.min_phase_duration == 10
        assert config.volume_threshold_sc == 2.0
        assert config.volume_threshold_sos == 1.5
        assert config.spring_volume_max == 0.7
        assert config.lookback_bars == 100
        assert config.confidence_threshold == 0.6

    def test_detection_config_custom_values(self):
        """Test DetectionConfig with custom values."""
        from src.pattern_engine.phase_detection import DetectionConfig

        config = DetectionConfig(
            min_phase_duration=15,
            volume_threshold_sc=2.5,
            volume_threshold_sos=1.8,
            spring_volume_max=0.6,
            lookback_bars=150,
            confidence_threshold=0.7,
        )

        assert config.min_phase_duration == 15
        assert config.volume_threshold_sc == 2.5
        assert config.volume_threshold_sos == 1.8
        assert config.spring_volume_max == 0.6
        assert config.lookback_bars == 150
        assert config.confidence_threshold == 0.7


class TestPackageImports:
    """Tests for package-level imports."""

    def test_import_types_from_package(self):
        """Test importing types from package root."""
        from src.pattern_engine.phase_detection import (
            DetectionConfig,
            EventType,
            PhaseEvent,
            PhaseResult,
            PhaseType,
        )

        # Verify all imports work
        assert PhaseType is not None
        assert EventType is not None
        assert PhaseEvent is not None
        assert PhaseResult is not None
        assert DetectionConfig is not None

    def test_import_detectors_from_package(self):
        """Test importing detector classes from package root."""
        from src.pattern_engine.phase_detection import (
            AutomaticRallyDetector,
            BaseEventDetector,
            LastPointOfSupportDetector,
            SecondaryTestDetector,
            SellingClimaxDetector,
            SignOfStrengthDetector,
            SpringDetector,
        )

        # Verify all imports work
        assert BaseEventDetector is not None
        assert SellingClimaxDetector is not None
        assert AutomaticRallyDetector is not None
        assert SecondaryTestDetector is not None
        assert SpringDetector is not None
        assert SignOfStrengthDetector is not None
        assert LastPointOfSupportDetector is not None

    def test_import_classifier_from_package(self):
        """Test importing PhaseClassifier from package root."""
        from src.pattern_engine.phase_detection import PhaseClassifier

        assert PhaseClassifier is not None

    def test_import_scorer_from_package(self):
        """Test importing scorer classes from package root."""
        from src.pattern_engine.phase_detection import (
            PhaseConfidenceScorer,
            ScoringFactors,
        )

        assert PhaseConfidenceScorer is not None
        assert ScoringFactors is not None

    def test_all_exports_defined(self):
        """Test that __all__ is properly defined."""
        from src.pattern_engine import phase_detection

        assert hasattr(phase_detection, "__all__")
        assert len(phase_detection.__all__) > 0

        # Verify all exports are accessible
        for name in phase_detection.__all__:
            assert hasattr(phase_detection, name), f"Missing export: {name}"


class TestScoringFactors:
    """Tests for ScoringFactors dataclass."""

    def test_scoring_factors_default_values(self):
        """Test ScoringFactors default values."""
        from src.pattern_engine.phase_detection import ScoringFactors

        factors = ScoringFactors()

        assert factors.volume_score == 0.0
        assert factors.timing_score == 0.0
        assert factors.structure_score == 0.0
        assert factors.event_score == 0.0

    def test_scoring_factors_aggregate_default_weights(self):
        """Test ScoringFactors aggregate with default weights."""
        from src.pattern_engine.phase_detection import ScoringFactors

        factors = ScoringFactors(
            volume_score=0.8,
            timing_score=0.7,
            structure_score=0.9,
            event_score=0.6,
        )

        # Default weights: volume=0.3, timing=0.2, structure=0.25, event=0.25
        expected = 0.8 * 0.3 + 0.7 * 0.2 + 0.9 * 0.25 + 0.6 * 0.25
        assert abs(factors.aggregate() - expected) < 0.001

    def test_scoring_factors_aggregate_custom_weights(self):
        """Test ScoringFactors aggregate with custom weights."""
        from src.pattern_engine.phase_detection import ScoringFactors

        factors = ScoringFactors(
            volume_score=1.0,
            timing_score=0.5,
            structure_score=0.5,
            event_score=0.5,
        )

        custom_weights = {
            "volume": 0.5,
            "timing": 0.2,
            "structure": 0.2,
            "event": 0.1,
        }

        expected = 1.0 * 0.5 + 0.5 * 0.2 + 0.5 * 0.2 + 0.5 * 0.1
        assert abs(factors.aggregate(custom_weights) - expected) < 0.001
