"""
Integration tests for Story 23.1: Phase detection facade wiring.

Verifies that all facade classes are properly wired to their real
implementations and no longer raise NotImplementedError.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.pattern_engine.phase_detection import (
    AutomaticRallyDetector,
    DetectionConfig,
    EventType,
    LastPointOfSupportDetector,
    PhaseClassifier,
    PhaseConfidenceScorer,
    PhaseEvent,
    PhaseResult,
    PhaseType,
    SecondaryTestDetector,
    SellingClimaxDetector,
    SignOfStrengthDetector,
    SpringDetector,
)
from src.pattern_engine.phase_detection.confidence_scorer import ScoringFactors


def create_accumulation_dataframe(num_bars: int = 50) -> pd.DataFrame:
    """Create OHLCV DataFrame with accumulation-like pattern.

    Simulates a selling climax (sharp drop on high volume), followed by
    an automatic rally, then sideways range oscillation.
    """
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(num_bars)]
    np.random.seed(42)

    prices: list[float] = []
    base = 100.0
    for i in range(num_bars):
        if i < 5:  # Selling climax - sharp drop
            base -= np.random.uniform(2, 5)
        elif i < 10:  # Automatic rally
            base += np.random.uniform(1, 3)
        else:  # Range oscillation
            base += np.random.uniform(-1, 1)
        prices.append(round(base, 4))

    volumes: list[int] = []
    for i in range(num_bars):
        if i < 5:  # High volume during SC
            volumes.append(int(np.random.uniform(5000000, 10000000)))
        elif i < 10:  # Medium volume during AR
            volumes.append(int(np.random.uniform(2000000, 5000000)))
        else:  # Lower volume during range
            volumes.append(int(np.random.uniform(500000, 2000000)))

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": [round(p + np.random.uniform(-0.5, 0.5), 4) for p in prices],
            "high": [round(p + np.random.uniform(0.5, 2.0), 4) for p in prices],
            "low": [round(p - np.random.uniform(0.5, 2.0), 4) for p in prices],
            "close": prices,
            "volume": volumes,
        }
    )


def create_minimal_dataframe(num_bars: int = 20) -> pd.DataFrame:
    """Create a minimal valid OHLCV DataFrame for smoke tests."""
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(num_bars)]
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": [100.0 + i * 0.1 for i in range(num_bars)],
            "high": [101.0 + i * 0.1 for i in range(num_bars)],
            "low": [99.0 + i * 0.1 for i in range(num_bars)],
            "close": [100.5 + i * 0.1 for i in range(num_bars)],
            "volume": [1000000] * num_bars,
        }
    )


class TestDetectorsDoNotRaiseNotImplementedError:
    """Test that all 6 detectors return results instead of raising NotImplementedError."""

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return create_accumulation_dataframe()

    def test_selling_climax_detector_returns_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = SellingClimaxDetector(config)
        result = detector.detect(df)
        assert isinstance(result, list)

    def test_automatic_rally_detector_returns_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = AutomaticRallyDetector(config)
        result = detector.detect(df)
        assert isinstance(result, list)

    def test_secondary_test_detector_returns_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = SecondaryTestDetector(config)
        result = detector.detect(df)
        assert isinstance(result, list)

    def test_spring_detector_returns_list(self, config: DetectionConfig, df: pd.DataFrame) -> None:
        detector = SpringDetector(config)
        result = detector.detect(df)
        assert isinstance(result, list)

    def test_sign_of_strength_detector_returns_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = SignOfStrengthDetector(config)
        result = detector.detect(df)
        assert isinstance(result, list)

    def test_last_point_of_support_detector_returns_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = LastPointOfSupportDetector(config)
        result = detector.detect(df)
        assert isinstance(result, list)


class TestSCARSTDetectionChain:
    """Test the SC -> AR -> ST sequential detection chain."""

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return create_accumulation_dataframe(num_bars=50)

    def test_sc_detection_returns_phase_events(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        sc_detector = SellingClimaxDetector(config)
        events = sc_detector.detect(df)
        # SC may or may not be detected depending on data, but should not raise
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, PhaseEvent)
            assert event.event_type == EventType.SELLING_CLIMAX

    def test_ar_detection_returns_phase_events(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        ar_detector = AutomaticRallyDetector(config)
        events = ar_detector.detect(df)
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, PhaseEvent)
            assert event.event_type == EventType.AUTOMATIC_RALLY

    def test_st_detection_returns_phase_events(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        st_detector = SecondaryTestDetector(config)
        events = st_detector.detect(df)
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, PhaseEvent)
            assert event.event_type == EventType.SECONDARY_TEST

    def test_detected_events_have_valid_fields(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        """Verify that any detected events have properly populated fields."""
        sc_detector = SellingClimaxDetector(config)
        events = sc_detector.detect(df)
        for event in events:
            assert event.bar_index >= 0
            assert isinstance(event.timestamp, datetime)
            assert event.price > 0
            assert event.volume > 0
            assert 0.0 <= event.confidence <= 1.0
            assert isinstance(event.metadata, dict)


class TestPhaseClassifierWiring:
    """Test PhaseClassifier.classify() is wired to real implementation."""

    def test_classify_returns_phase_result(self) -> None:
        classifier = PhaseClassifier()
        df = create_minimal_dataframe()
        result = classifier.classify(df)
        assert isinstance(result, PhaseResult)

    def test_classify_with_events_returns_phase_result(self) -> None:
        classifier = PhaseClassifier()
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1, 0, 0),
                bar_index=2,
                price=85.0,
                volume=8000000.0,
                confidence=0.85,
                metadata={"volume_ratio": 2.5, "spread_ratio": 2.0},
            ),
            PhaseEvent(
                event_type=EventType.AUTOMATIC_RALLY,
                timestamp=datetime(2024, 1, 1, 5, 0),
                bar_index=7,
                price=92.0,
                volume=3000000.0,
                confidence=0.75,
                metadata={"rally_pct": 0.06, "bars_after_sc": 3, "volume_profile": "HIGH"},
            ),
        ]
        result = classifier.classify(df, events=events)
        assert isinstance(result, PhaseResult)
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_with_sc_ar_events_detects_phase_a(self) -> None:
        """When SC + AR events are provided, classifier should detect Phase A."""
        classifier = PhaseClassifier()
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1, 0, 0),
                bar_index=2,
                price=85.0,
                volume=8000000.0,
                confidence=0.85,
                metadata={"volume_ratio": 2.5, "spread_ratio": 2.0},
            ),
            PhaseEvent(
                event_type=EventType.AUTOMATIC_RALLY,
                timestamp=datetime(2024, 1, 1, 5, 0),
                bar_index=7,
                price=92.0,
                volume=3000000.0,
                confidence=0.75,
                metadata={"rally_pct": 0.06, "bars_after_sc": 3, "volume_profile": "HIGH"},
            ),
        ]
        result = classifier.classify(df, events=events)
        assert result.phase == PhaseType.A

    def test_classify_no_events_returns_result(self) -> None:
        """classify() with no events should still return a PhaseResult (not raise)."""
        classifier = PhaseClassifier()
        df = create_minimal_dataframe()
        result = classifier.classify(df, events=None)
        assert isinstance(result, PhaseResult)


class TestPhaseConfidenceScorerWiring:
    """Test PhaseConfidenceScorer wired to real implementation."""

    def test_calculate_confidence_returns_float(self) -> None:
        scorer = PhaseConfidenceScorer()
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1),
                bar_index=2,
                price=85.0,
                volume=8000000.0,
                confidence=0.85,
                metadata={"volume_ratio": 2.5, "spread_ratio": 2.0},
            ),
            PhaseEvent(
                event_type=EventType.AUTOMATIC_RALLY,
                timestamp=datetime(2024, 1, 1, 5),
                bar_index=7,
                price=92.0,
                volume=3000000.0,
                confidence=0.75,
                metadata={"rally_pct": 0.06, "bars_after_sc": 3, "volume_profile": "HIGH"},
            ),
        ]
        confidence = scorer.calculate_confidence(PhaseType.A, events, df, phase_start_bar=0)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_factors_returns_scoring_factors(self) -> None:
        scorer = PhaseConfidenceScorer()
        df = create_accumulation_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1),
                bar_index=2,
                price=85.0,
                volume=8000000.0,
                confidence=0.85,
                metadata={"volume_ratio": 2.5, "spread_ratio": 2.0},
            ),
        ]
        factors = scorer.calculate_factors(PhaseType.A, events, df, phase_start_bar=0)
        assert isinstance(factors, ScoringFactors)
        assert 0.0 <= factors.volume_score <= 1.0
        assert 0.0 <= factors.timing_score <= 1.0
        assert 0.0 <= factors.structure_score <= 1.0
        assert 0.0 <= factors.event_score <= 1.0


class TestContextDependentDetectorsReturnEmpty:
    """Test that Spring/SOS/LPS detectors return empty lists (not errors).

    These detectors require TradingRange context not available from
    the DataFrame-only interface, so they return empty lists by design.
    """

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return create_minimal_dataframe()

    def test_spring_detector_returns_empty_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = SpringDetector(config)
        result = detector.detect(df)
        assert result == []

    def test_sign_of_strength_detector_returns_empty_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = SignOfStrengthDetector(config)
        result = detector.detect(df)
        assert result == []

    def test_last_point_of_support_detector_returns_empty_list(
        self, config: DetectionConfig, df: pd.DataFrame
    ) -> None:
        detector = LastPointOfSupportDetector(config)
        result = detector.detect(df)
        assert result == []


# ============================================================================
# DataFrame Validation Tests
# ============================================================================


class TestDetectorDataFrameValidation:
    """Test that detectors reject DataFrames missing required columns."""

    @pytest.fixture
    def config(self) -> DetectionConfig:
        return DetectionConfig()

    @pytest.fixture
    def invalid_df(self) -> pd.DataFrame:
        """DataFrame missing required columns."""
        return pd.DataFrame({"timestamp": [datetime(2024, 1, 1)], "price": [100.0]})

    def test_sc_detector_rejects_invalid_dataframe(
        self, config: DetectionConfig, invalid_df: pd.DataFrame
    ) -> None:
        detector = SellingClimaxDetector(config)
        with pytest.raises(ValueError, match="missing required columns"):
            detector.detect(invalid_df)

    def test_ar_detector_rejects_invalid_dataframe(
        self, config: DetectionConfig, invalid_df: pd.DataFrame
    ) -> None:
        detector = AutomaticRallyDetector(config)
        with pytest.raises(ValueError, match="missing required columns"):
            detector.detect(invalid_df)

    def test_st_detector_rejects_invalid_dataframe(
        self, config: DetectionConfig, invalid_df: pd.DataFrame
    ) -> None:
        detector = SecondaryTestDetector(config)
        with pytest.raises(ValueError, match="missing required columns"):
            detector.detect(invalid_df)

    def test_spring_detector_rejects_invalid_dataframe(
        self, config: DetectionConfig, invalid_df: pd.DataFrame
    ) -> None:
        detector = SpringDetector(config)
        with pytest.raises(ValueError, match="missing required columns"):
            detector.detect(invalid_df)

    def test_sos_detector_rejects_invalid_dataframe(
        self, config: DetectionConfig, invalid_df: pd.DataFrame
    ) -> None:
        detector = SignOfStrengthDetector(config)
        with pytest.raises(ValueError, match="missing required columns"):
            detector.detect(invalid_df)

    def test_lps_detector_rejects_invalid_dataframe(
        self, config: DetectionConfig, invalid_df: pd.DataFrame
    ) -> None:
        detector = LastPointOfSupportDetector(config)
        with pytest.raises(ValueError, match="missing required columns"):
            detector.detect(invalid_df)


# ============================================================================
# Model-to-PhaseEvent Converter Tests
# ============================================================================


class TestModelToPhaseEventConverters:
    """Test the conversion functions from model objects to PhaseEvent."""

    def test_selling_climax_to_event(self) -> None:
        from src.pattern_engine.phase_detection.event_detectors import (
            _selling_climax_to_event,
        )

        sc = _make_selling_climax()
        event = _selling_climax_to_event(sc)

        assert event.event_type == EventType.SELLING_CLIMAX
        assert event.bar_index == 3
        assert event.price > 0
        assert event.volume > 0
        assert 0.0 <= event.confidence <= 1.0
        assert "volume_ratio" in event.metadata
        assert "spread_ratio" in event.metadata

    def test_automatic_rally_to_event(self) -> None:
        from src.pattern_engine.phase_detection.event_detectors import (
            _automatic_rally_to_event,
        )

        ar = _make_automatic_rally()
        event = _automatic_rally_to_event(ar)

        assert event.event_type == EventType.AUTOMATIC_RALLY
        assert event.bar_index == 7
        assert event.price > 0
        assert event.volume > 0
        assert "rally_pct" in event.metadata
        assert "bars_after_sc" in event.metadata

    def test_secondary_test_to_event(self) -> None:
        from src.pattern_engine.phase_detection.event_detectors import (
            _secondary_test_to_event,
        )

        st = _make_secondary_test()
        event = _secondary_test_to_event(st)

        assert event.event_type == EventType.SECONDARY_TEST
        assert event.bar_index == 12
        assert event.price > 0
        assert event.volume > 0
        assert 0.0 <= event.confidence <= 1.0
        assert "test_number" in event.metadata
        assert "volume_reduction_pct" in event.metadata


# ============================================================================
# PhaseClassifier Internal Methods Tests
# ============================================================================


class TestPhaseClassifierInternalMethods:
    """Test PhaseClassifier internal methods wired in Story 23.1."""

    @pytest.fixture
    def classifier(self) -> PhaseClassifier:
        return PhaseClassifier()

    @pytest.fixture
    def sc_ar_events(self) -> list[PhaseEvent]:
        return [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1),
                bar_index=2,
                price=85.0,
                volume=8000000.0,
                confidence=0.85,
                metadata={"volume_ratio": 2.5, "spread_ratio": 2.0},
            ),
            PhaseEvent(
                event_type=EventType.AUTOMATIC_RALLY,
                timestamp=datetime(2024, 1, 1, 5),
                bar_index=7,
                price=92.0,
                volume=3000000.0,
                confidence=0.75,
                metadata={"rally_pct": 0.06, "bars_after_sc": 3, "volume_profile": "HIGH"},
            ),
        ]

    def test_determine_phase_from_events_with_sc_ar(
        self, classifier: PhaseClassifier, sc_ar_events: list[PhaseEvent]
    ) -> None:
        result = classifier._determine_phase_from_events(sc_ar_events, current_bar=20)
        assert result == PhaseType.A

    def test_determine_phase_from_events_empty_returns_none(
        self, classifier: PhaseClassifier
    ) -> None:
        result = classifier._determine_phase_from_events([], current_bar=0)
        assert result is None

    def test_check_phase_transition_valid(
        self, classifier: PhaseClassifier, sc_ar_events: list[PhaseEvent]
    ) -> None:
        # Set up classifier with existing events for Phase A
        classifier._detected_events = sc_ar_events
        # Add ST event to trigger A->B transition check
        st_event = PhaseEvent(
            event_type=EventType.SECONDARY_TEST,
            timestamp=datetime(2024, 1, 1, 12),
            bar_index=15,
            price=86.0,
            volume=2000000.0,
            confidence=0.80,
            metadata={"test_number": 1, "volume_reduction_pct": 30.0},
        )
        # Result depends on whether the real classifier detects a transition
        result = classifier._check_phase_transition(PhaseType.A, st_event)
        # Should return None or a valid PhaseType
        assert result is None or isinstance(result, PhaseType)

    def test_validate_phase_duration_sufficient(self, classifier: PhaseClassifier) -> None:
        assert classifier._validate_phase_duration(PhaseType.B, duration_bars=15) is True

    def test_validate_phase_duration_insufficient(self, classifier: PhaseClassifier) -> None:
        assert classifier._validate_phase_duration(PhaseType.B, duration_bars=5) is False

    def test_calculate_phase_confidence(
        self, classifier: PhaseClassifier, sc_ar_events: list[PhaseEvent]
    ) -> None:
        confidence = classifier._calculate_phase_confidence(
            PhaseType.A, sc_ar_events, duration_bars=20
        )
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_reset_clears_state(self, classifier: PhaseClassifier) -> None:
        classifier._current_phase = PhaseType.A
        classifier._phase_start_bar = 10
        classifier._detected_events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1),
                bar_index=2,
                price=85.0,
                volume=8000000.0,
            )
        ]
        classifier.reset()
        assert classifier._current_phase is None
        assert classifier._phase_start_bar == 0
        assert classifier._detected_events == []


# ============================================================================
# Events-to-PhaseEvents Conversion Tests (covers Spring/SOS/LPS branches)
# ============================================================================


class TestEventsToPhaseEventsConversion:
    """Test the _events_to_phase_events helper with all event types."""

    def test_converts_spring_event(self) -> None:
        from src.pattern_engine.phase_detection.phase_classifier import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.SPRING,
                timestamp=datetime(2024, 1, 1),
                bar_index=25,
                price=84.0,
                volume=500000.0,
                confidence=0.9,
                metadata={"depth_pct": 0.02},
            )
        ]
        result = _events_to_phase_events(events)
        assert result.spring is not None
        assert result.spring["bar_index"] == 25

    def test_converts_sos_event(self) -> None:
        from src.pattern_engine.phase_detection.phase_classifier import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.SIGN_OF_STRENGTH,
                timestamp=datetime(2024, 1, 1),
                bar_index=30,
                price=95.0,
                volume=6000000.0,
                confidence=0.88,
                metadata={"breakout_volume_ratio": 2.0},
            )
        ]
        result = _events_to_phase_events(events)
        assert result.sos_breakout is not None
        assert result.sos_breakout["bar_index"] == 30

    def test_converts_lps_event(self) -> None:
        from src.pattern_engine.phase_detection.phase_classifier import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.LAST_POINT_OF_SUPPORT,
                timestamp=datetime(2024, 1, 1),
                bar_index=35,
                price=93.0,
                volume=1500000.0,
                confidence=0.82,
                metadata={"retest_depth_pct": 0.01},
            )
        ]
        result = _events_to_phase_events(events)
        assert result.last_point_of_support is not None
        assert result.last_point_of_support["bar_index"] == 35

    def test_converts_st_event_to_list(self) -> None:
        from src.pattern_engine.phase_detection.phase_classifier import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.SECONDARY_TEST,
                timestamp=datetime(2024, 1, 1),
                bar_index=12,
                price=86.0,
                volume=2000000.0,
                confidence=0.80,
                metadata={"test_number": 1},
            ),
            PhaseEvent(
                event_type=EventType.SECONDARY_TEST,
                timestamp=datetime(2024, 1, 2),
                bar_index=18,
                price=85.5,
                volume=1500000.0,
                confidence=0.75,
                metadata={"test_number": 2},
            ),
        ]
        result = _events_to_phase_events(events)
        assert len(result.secondary_tests) == 2


class TestConfidenceScorerEventsToPhaseEvents:
    """Test the _events_to_phase_events in confidence_scorer module too."""

    def test_converts_spring_event(self) -> None:
        from src.pattern_engine.phase_detection.confidence_scorer import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.SPRING,
                timestamp=datetime(2024, 1, 1),
                bar_index=25,
                price=84.0,
                volume=500000.0,
                confidence=0.9,
            )
        ]
        result = _events_to_phase_events(events)
        assert result.spring is not None

    def test_converts_sos_event(self) -> None:
        from src.pattern_engine.phase_detection.confidence_scorer import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.SIGN_OF_STRENGTH,
                timestamp=datetime(2024, 1, 1),
                bar_index=30,
                price=95.0,
                volume=6000000.0,
                confidence=0.88,
            )
        ]
        result = _events_to_phase_events(events)
        assert result.sos_breakout is not None

    def test_converts_lps_event(self) -> None:
        from src.pattern_engine.phase_detection.confidence_scorer import (
            _events_to_phase_events,
        )

        events = [
            PhaseEvent(
                event_type=EventType.LAST_POINT_OF_SUPPORT,
                timestamp=datetime(2024, 1, 1),
                bar_index=35,
                price=93.0,
                volume=1500000.0,
                confidence=0.82,
            )
        ]
        result = _events_to_phase_events(events)
        assert result.last_point_of_support is not None


# ============================================================================
# Confidence Scorer Volume Scoring Tests
# ============================================================================


class TestVolumeScoringEdgeCases:
    """Test _score_volume_confirmation for various phases and edge cases."""

    @pytest.fixture
    def scorer(self) -> PhaseConfidenceScorer:
        return PhaseConfidenceScorer()

    def test_volume_scoring_empty_dataframe(self, scorer: PhaseConfidenceScorer) -> None:
        empty_df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        result = scorer._score_volume_confirmation(PhaseType.A, [], empty_df)
        assert result == 0.5

    def test_volume_scoring_no_volume_column(self, scorer: PhaseConfidenceScorer) -> None:
        df = pd.DataFrame({"timestamp": [datetime(2024, 1, 1)], "close": [100.0]})
        result = scorer._score_volume_confirmation(PhaseType.A, [], df)
        assert result == 0.5

    def test_volume_scoring_zero_average_volume(self, scorer: PhaseConfidenceScorer) -> None:
        df = pd.DataFrame({"volume": [0, 0, 0]})
        result = scorer._score_volume_confirmation(PhaseType.A, [], df)
        assert result == 0.5

    def test_volume_scoring_no_events(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_minimal_dataframe()
        result = scorer._score_volume_confirmation(PhaseType.A, [], df)
        assert result == 0.5

    def test_volume_scoring_phase_a_high_volume(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SELLING_CLIMAX,
                timestamp=datetime(2024, 1, 1),
                bar_index=2,
                price=85.0,
                volume=5000000.0,
                confidence=0.85,
            )
        ]
        result = scorer._score_volume_confirmation(PhaseType.A, events, df)
        assert 0.0 <= result <= 1.0

    def test_volume_scoring_phase_c_low_volume(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SPRING,
                timestamp=datetime(2024, 1, 1),
                bar_index=25,
                price=84.0,
                volume=200000.0,
                confidence=0.9,
            )
        ]
        result = scorer._score_volume_confirmation(PhaseType.C, events, df)
        assert 0.0 <= result <= 1.0

    def test_volume_scoring_phase_d(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SIGN_OF_STRENGTH,
                timestamp=datetime(2024, 1, 1),
                bar_index=30,
                price=95.0,
                volume=3000000.0,
                confidence=0.88,
            )
        ]
        result = scorer._score_volume_confirmation(PhaseType.D, events, df)
        assert 0.0 <= result <= 1.0

    def test_volume_scoring_phase_b_neutral(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_minimal_dataframe()
        events = [
            PhaseEvent(
                event_type=EventType.SECONDARY_TEST,
                timestamp=datetime(2024, 1, 1),
                bar_index=15,
                price=87.0,
                volume=1000000.0,
                confidence=0.7,
            )
        ]
        result = scorer._score_volume_confirmation(PhaseType.B, events, df)
        assert result == 0.5


# ============================================================================
# Confidence Scorer Structure Scoring Tests
# ============================================================================


class TestStructureScoringEdgeCases:
    """Test _score_structure for various phases and edge cases."""

    @pytest.fixture
    def scorer(self) -> PhaseConfidenceScorer:
        return PhaseConfidenceScorer()

    def test_structure_scoring_empty_dataframe(self, scorer: PhaseConfidenceScorer) -> None:
        empty_df = pd.DataFrame(columns=["high", "low"])
        result = scorer._score_structure(PhaseType.B, empty_df, 0)
        assert result == 0.5

    def test_structure_scoring_single_bar(self, scorer: PhaseConfidenceScorer) -> None:
        df = pd.DataFrame({"high": [101.0], "low": [99.0]})
        result = scorer._score_structure(PhaseType.B, df, 0)
        assert result == 0.5

    def test_structure_scoring_phase_start_beyond_data(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_minimal_dataframe(5)
        result = scorer._score_structure(PhaseType.B, df, phase_start_bar=4)
        assert result == 0.5

    def test_structure_scoring_phase_b(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_accumulation_dataframe(40)
        result = scorer._score_structure(PhaseType.B, df, phase_start_bar=0)
        assert 0.0 <= result <= 1.0

    def test_structure_scoring_phase_c(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_accumulation_dataframe(40)
        result = scorer._score_structure(PhaseType.C, df, phase_start_bar=0)
        assert 0.0 <= result <= 1.0

    def test_structure_scoring_phase_d(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_accumulation_dataframe(40)
        result = scorer._score_structure(PhaseType.D, df, phase_start_bar=0)
        assert 0.0 <= result <= 1.0

    def test_structure_scoring_phase_e(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_accumulation_dataframe(40)
        result = scorer._score_structure(PhaseType.E, df, phase_start_bar=0)
        assert 0.0 <= result <= 1.0

    def test_structure_scoring_phase_a_neutral(self, scorer: PhaseConfidenceScorer) -> None:
        df = create_accumulation_dataframe(40)
        result = scorer._score_structure(PhaseType.A, df, phase_start_bar=0)
        assert result == 0.5

    def test_structure_scoring_zero_first_range(self, scorer: PhaseConfidenceScorer) -> None:
        """If first half range is 0 (all same prices), return neutral."""
        df = pd.DataFrame(
            {
                "high": [100.0, 100.0, 100.0, 101.0],
                "low": [100.0, 100.0, 99.0, 99.0],
            }
        )
        result = scorer._score_structure(PhaseType.B, df, phase_start_bar=0)
        assert 0.0 <= result <= 1.0


# ============================================================================
# Helper functions for building mock model objects
# ============================================================================


def _make_selling_climax():
    """Build a SellingClimax object for testing."""
    from src.models.selling_climax import SellingClimax

    return SellingClimax(
        bar={
            "symbol": "TEST",
            "timeframe": "1h",
            "timestamp": "2024-01-01T03:00:00",
            "open": 90.0,
            "high": 91.0,
            "low": 82.0,
            "close": 83.0,
            "volume": 8000000,
            "spread": 9.0,
        },
        bar_index=3,
        volume_ratio=3.5,
        spread_ratio=2.8,
        confidence=85,
        close_position=0.65,
        prior_close=95.0,
    )


def _make_automatic_rally():
    """Build an AutomaticRally object for testing."""
    from src.models.automatic_rally import AutomaticRally

    return AutomaticRally(
        bar={
            "symbol": "TEST",
            "timeframe": "1h",
            "timestamp": "2024-01-01T07:00:00",
            "open": 84.0,
            "high": 93.0,
            "low": 83.5,
            "close": 92.0,
            "volume": 3000000,
            "spread": 9.5,
        },
        bar_index=7,
        rally_pct=0.08,
        bars_after_sc=4,
        sc_reference={
            "bar_index": 3,
            "confidence": 85,
            "bar": {"timestamp": "2024-01-01T03:00:00", "close": 83.0, "low": 82.0},
        },
        sc_low=82.0,
        ar_high=93.0,
        volume_profile="HIGH",
        quality_score=0.75,
    )


def _make_secondary_test():
    """Build a SecondaryTest object for testing."""
    from src.models.secondary_test import SecondaryTest

    return SecondaryTest(
        bar={
            "symbol": "TEST",
            "timeframe": "1h",
            "timestamp": "2024-01-01T12:00:00",
            "open": 88.0,
            "high": 89.0,
            "low": 84.0,
            "close": 86.0,
            "volume": 2000000,
            "spread": 5.0,
        },
        bar_index=12,
        test_number=1,
        distance_from_sc_low=0.012,
        volume_reduction_pct=0.45,
        test_volume_ratio=1.2,
        sc_volume_ratio=3.5,
        penetration=0.0,
        confidence=80,
        sc_reference={
            "bar_index": 3,
            "confidence": 85,
            "bar": {"timestamp": "2024-01-01T03:00:00", "close": 83.0, "low": 82.0},
        },
        ar_reference={
            "bar_index": 7,
            "confidence": 75,
            "bar": {"timestamp": "2024-01-01T07:00:00", "close": 92.0},
        },
    )
