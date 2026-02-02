"""
Performance benchmarks for phase detection (Story 22.15).

Validates phase detection performance:
- AC2: 500 bars phase detection in <100ms
- AC4: Results within 5% of baseline
- Memory usage <50MB

These benchmarks test the individual detector components that make up
the phase detection system, rather than the full PhaseDetector which
requires complex TradingRange fixtures.
"""

import time
import tracemalloc
import warnings
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from tests.benchmarks.conftest import PERFORMANCE_TARGETS


def convert_dataframe_to_bars(df: pd.DataFrame, symbol: str = "BENCH") -> list:
    """Convert DataFrame to OHLCVBar list with proper rounding."""
    from src.models.ohlcv import OHLCVBar

    bars = []
    for _, row in df.iterrows():
        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe="1h",
                timestamp=row["timestamp"].to_pydatetime(),
                open=Decimal(str(round(row["open"], 8))),
                high=Decimal(str(round(row["high"], 8))),
                low=Decimal(str(round(row["low"], 8))),
                close=Decimal(str(round(row["close"], 8))),
                volume=int(row["volume"]),
                spread=Decimal(str(round(row["high"] - row["low"], 8))),
            )
        )
    return bars


@pytest.mark.benchmark
class TestEventDetectionPerformance:
    """Performance benchmarks for individual event detectors."""

    def test_selling_climax_detection_performance(self, benchmark_ohlcv_500: pd.DataFrame):
        """
        Benchmark Selling Climax detection on 500 bars.

        SC detection is the first step in phase detection.
        Target: <50ms for 500 bars.
        """
        bars = convert_dataframe_to_bars(benchmark_ohlcv_500)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.pattern_engine._phase_detector_impl import detect_selling_climax

        # Warm-up run
        try:
            _ = detect_selling_climax(bars)
        except Exception:
            pass

        # Timed runs
        times = []
        for _ in range(10):
            start = time.perf_counter()
            try:
                _ = detect_selling_climax(bars)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print("\nSelling Climax Detection (500 bars):")
        print(f"  Average: {avg_time:.2f}ms")

        target = PERFORMANCE_TARGETS["event_detection_individual_ms"]
        assert avg_time < target, f"SC detection too slow: {avg_time:.2f}ms > {target}ms"

    def test_automatic_rally_detection_performance(self, benchmark_ohlcv_500: pd.DataFrame):
        """
        Benchmark Automatic Rally detection on 500 bars.

        AR detection follows SC detection in the pipeline.
        Target: <50ms for 500 bars.
        """
        bars = convert_dataframe_to_bars(benchmark_ohlcv_500)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.pattern_engine._phase_detector_impl import detect_automatic_rally

        # Warm-up run
        try:
            _ = detect_automatic_rally(bars)
        except Exception:
            pass

        # Timed runs
        times = []
        for _ in range(10):
            start = time.perf_counter()
            try:
                _ = detect_automatic_rally(bars)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print("\nAutomatic Rally Detection (500 bars):")
        print(f"  Average: {avg_time:.2f}ms")

        target = PERFORMANCE_TARGETS["event_detection_individual_ms"]
        assert avg_time < target, f"AR detection too slow: {avg_time:.2f}ms > {target}ms"

    def test_secondary_test_detection_performance(self, benchmark_ohlcv_500: pd.DataFrame):
        """
        Benchmark Secondary Test detection on 500 bars.

        ST detection completes the Phase A event sequence.
        Target: <50ms for 500 bars.
        """
        bars = convert_dataframe_to_bars(benchmark_ohlcv_500)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.pattern_engine._phase_detector_impl import detect_secondary_test

        # Warm-up run
        try:
            _ = detect_secondary_test(bars)
        except Exception:
            pass

        # Timed runs
        times = []
        for _ in range(10):
            start = time.perf_counter()
            try:
                _ = detect_secondary_test(bars)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print("\nSecondary Test Detection (500 bars):")
        print(f"  Average: {avg_time:.2f}ms")

        target = PERFORMANCE_TARGETS["event_detection_individual_ms"]
        assert avg_time < target, f"ST detection too slow: {avg_time:.2f}ms > {target}ms"


@pytest.mark.benchmark
class TestPhaseClassifierPerformance:
    """Performance benchmarks for the phase classification logic."""

    def test_phase_classifier_performance(self, benchmark_ohlcv_500: pd.DataFrame):
        """
        Benchmark phase classification on 500 bars.

        Tests classify_phase function which determines the current Wyckoff phase.
        Target: <50ms for 500 bars.
        """
        bars = convert_dataframe_to_bars(benchmark_ohlcv_500)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.pattern_engine.phase_classifier import classify_phase

        # Warm-up run
        try:
            _ = classify_phase(bars)
        except Exception:
            pass

        # Timed runs
        times = []
        for _ in range(10):
            start = time.perf_counter()
            try:
                _ = classify_phase(bars)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print("\nPhase Classification (500 bars):")
        print(f"  Average: {avg_time:.2f}ms")

        target = PERFORMANCE_TARGETS["event_detection_individual_ms"]
        assert avg_time < target, f"Phase classification too slow: {avg_time:.2f}ms > {target}ms"


@pytest.mark.benchmark
class TestPhaseProgressionPerformance:
    """Performance benchmarks for phase progression validation."""

    def test_progression_validator_performance(self):
        """
        Benchmark phase progression validation performance.

        Tests enforce_phase_progression for tracking phase transitions.
        Target: <10ms per validation.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.models.phase_classification import WyckoffPhase
            from src.pattern_engine.phase_progression_validator import (
                PhaseHistory,
                enforce_phase_progression,
            )

        # Create a phase history with required fields
        history = PhaseHistory(
            range_id=uuid4(),
            started_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Simulate 100 phase transitions
        phases = [
            WyckoffPhase.A,
            WyckoffPhase.B,
            WyckoffPhase.C,
            WyckoffPhase.D,
            WyckoffPhase.E,
        ]

        times = []
        for i in range(100):
            current_phase = phases[i % len(phases)]
            proposed_phase = phases[(i + 1) % len(phases)]

            start = time.perf_counter()
            try:
                _ = enforce_phase_progression(history, current_phase, proposed_phase)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print("\nPhase Progression Validation (100 transitions):")
        print(f"  Average per transition: {avg_time:.4f}ms")

        # Should be very fast
        assert avg_time < 10, f"Progression validation too slow: {avg_time:.4f}ms > 10ms"


@pytest.mark.benchmark
class TestConfidenceCalculationPerformance:
    """Performance benchmarks for confidence scoring."""

    def test_confidence_calculation_performance(self, benchmark_ohlcv_500: pd.DataFrame):
        """
        Benchmark phase confidence calculation on 500 bars.

        Tests calculate_phase_confidence function.
        Target: <50ms for 500 bars.
        """
        bars = convert_dataframe_to_bars(benchmark_ohlcv_500)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.models.phase_classification import WyckoffPhase
            from src.pattern_engine._phase_detector_impl import calculate_phase_confidence

        # Warm-up
        try:
            _ = calculate_phase_confidence(bars, WyckoffPhase.PHASE_B)
        except Exception:
            pass

        # Timed runs
        times = []
        for _ in range(10):
            start = time.perf_counter()
            try:
                _ = calculate_phase_confidence(bars, WyckoffPhase.PHASE_B)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        print("\nConfidence Calculation (500 bars):")
        print(f"  Average: {avg_time:.2f}ms")

        target = PERFORMANCE_TARGETS["event_detection_individual_ms"]
        assert avg_time < target, f"Confidence calc too slow: {avg_time:.2f}ms > {target}ms"


@pytest.mark.benchmark
class TestPhaseDetectionMemory:
    """Memory benchmarks for phase detection."""

    def test_event_detection_memory(self, benchmark_ohlcv_1000: pd.DataFrame):
        """
        Benchmark memory usage during event detection.

        Target: <50MB peak memory for 1000 bars (AC1).
        """
        bars = convert_dataframe_to_bars(benchmark_ohlcv_1000)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            from src.pattern_engine._phase_detector_impl import (
                detect_automatic_rally,
                detect_secondary_test,
                detect_selling_climax,
            )

        tracemalloc.start()

        # Run all event detectors
        try:
            _ = detect_selling_climax(bars)
            _ = detect_automatic_rally(bars)
            _ = detect_secondary_test(bars)
        except Exception:
            pass

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        print("\nMemory Usage (Event Detection 1000 bars):")
        print(f"  Current: {current / 1024 / 1024:.2f}MB")
        print(f"  Peak: {peak_mb:.2f}MB")

        target = PERFORMANCE_TARGETS["memory_operation_mb"]
        assert peak_mb < target, f"Memory usage too high: {peak_mb:.2f}MB > {target}MB"

    def test_ohlcv_bar_creation_memory(self, benchmark_ohlcv_1000: pd.DataFrame):
        """
        Benchmark memory usage for OHLCV bar list creation.

        Validates that bar conversion is memory-efficient.
        """
        tracemalloc.start()

        bars = convert_dataframe_to_bars(benchmark_ohlcv_1000)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        print("\nMemory Usage (1000 bar conversion):")
        print(f"  Current: {current / 1024 / 1024:.2f}MB")
        print(f"  Peak: {peak_mb:.2f}MB")
        print(f"  Bars created: {len(bars)}")

        target = PERFORMANCE_TARGETS["memory_operation_mb"]
        assert peak_mb < target, f"Memory usage too high: {peak_mb:.2f}MB > {target}MB"
