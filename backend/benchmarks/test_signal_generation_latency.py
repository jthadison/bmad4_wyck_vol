"""
Signal Generation Latency Benchmarks (Story 12.9 Task 2).

Benchmarks signal generation pipeline components to validate NFR1 requirement:
<1 second per symbol per bar analyzed.

Component budget breakdown:
- Volume analysis: <50ms per bar
- Spring detection: <200ms per bar
- SOS detection: <150ms per bar
- UTAD detection: <150ms per bar
- Full pipeline: <1000ms total

Author: Story 12.9 Task 2
"""

import pytest

from benchmarks.benchmark_config import (
    NFR1_TARGET_SECONDS,
    SOS_DETECTION_TARGET_MS,
    SPRING_DETECTION_TARGET_MS,
    UTAD_DETECTION_TARGET_MS,
    VOLUME_ANALYSIS_TARGET_MS,
)
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.detectors.sos_detector import SOSDetector
from src.pattern_engine.detectors.spring_detector import SpringDetector
from src.pattern_engine.detectors.utad_detector import UTADDetector
from src.pattern_engine.volume_analyzer import calculate_volume_ratio


class TestVolumeAnalysisLatency:
    """Benchmark volume analysis calculations (Task 2 Subtask 2.2)."""

    @pytest.mark.benchmark
    def test_volume_analysis_latency(self, benchmark, sample_ohlcv_bars: list[OHLCVBar]) -> None:
        """
        Benchmark volume_ratio calculation for 100 bars.

        Target: <50ms per bar (NFR1 component budget).
        """

        def calculate_volume_for_bars() -> list[float | None]:
            """Calculate volume ratios for all bars."""
            ratios = []
            for i in range(20, min(120, len(sample_ohlcv_bars))):  # 100 bars
                ratio = calculate_volume_ratio(sample_ohlcv_bars, i)
                ratios.append(ratio)
            return ratios

        result = benchmark(calculate_volume_for_bars)

        # Verify results are valid
        assert len(result) > 0
        assert all(r is None or r > 0 for r in result)

        # Check against target (convert to milliseconds)
        stats = benchmark.stats
        mean_time_ms = stats.mean * 1000  # Convert to ms
        per_bar_ms = mean_time_ms / 100  # 100 bars processed

        assert (
            per_bar_ms < VOLUME_ANALYSIS_TARGET_MS
        ), f"Volume analysis too slow: {per_bar_ms:.2f}ms per bar (target: <{VOLUME_ANALYSIS_TARGET_MS}ms)"


class TestPatternDetectionLatency:
    """Benchmark pattern detector performance (Task 2 Subtasks 2.3-2.5)."""

    @pytest.fixture
    def mock_trading_range(self, sample_ohlcv_bars: list[OHLCVBar]) -> TradingRange:
        """Create mock trading range for pattern detection."""
        from datetime import UTC, datetime
        from decimal import Decimal
        from uuid import uuid4

        return TradingRange(
            id=uuid4(),
            symbol="BENCH",
            timeframe="1d",
            range_low=Decimal("145.00"),
            range_high=Decimal("155.00"),
            creek=Decimal("147.00"),
            ice=Decimal("153.00"),
            start_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            status=RangeStatus.ACTIVE,
        )

    @pytest.mark.benchmark
    def test_spring_detection_latency(
        self,
        benchmark,
        sample_ohlcv_bars: list[OHLCVBar],
        mock_trading_range: TradingRange,
    ) -> None:
        """
        Benchmark Spring pattern detection on 100 bars.

        Target: <200ms per bar (most expensive pattern detection).
        """
        detector = SpringDetector()

        def detect_spring_pattern() -> int:
            """Run Spring detection on bars."""
            from src.pattern_engine.detectors.spring_detector import detect_spring

            # Detect spring for Phase C
            result = detect_spring(
                trading_range=mock_trading_range,
                bars=sample_ohlcv_bars[:120],  # 100 analyzable bars after warmup
                phase=WyckoffPhase.C,
                symbol="BENCH",
                start_index=20,
            )
            return 1 if result else 0

        benchmark(detect_spring_pattern)

        stats = benchmark.stats
        mean_time_ms = stats.mean * 1000

        # Note: detect_spring processes multiple bars internally
        # This measures full detection cycle
        assert (
            mean_time_ms < SPRING_DETECTION_TARGET_MS * 10
        ), f"Spring detection too slow: {mean_time_ms:.2f}ms (target: <{SPRING_DETECTION_TARGET_MS * 10}ms for 100 bars)"

    @pytest.mark.benchmark
    def test_sos_detection_latency(
        self,
        benchmark,
        sample_ohlcv_bars: list[OHLCVBar],
        mock_trading_range: TradingRange,
    ) -> None:
        """
        Benchmark SOS pattern detection.

        Target: <150ms per bar.
        """
        detector = SOSDetector()

        def detect_sos_pattern() -> int:
            """Run SOS detection on bars."""
            from src.pattern_engine.detectors.sos_detector import detect_sos

            result = detect_sos(
                trading_range=mock_trading_range,
                bars=sample_ohlcv_bars[:120],
                phase=WyckoffPhase.D,
                symbol="BENCH",
            )
            return 1 if result else 0

        benchmark(detect_sos_pattern)

        stats = benchmark.stats
        mean_time_ms = stats.mean * 1000

        assert (
            mean_time_ms < SOS_DETECTION_TARGET_MS * 10
        ), f"SOS detection too slow: {mean_time_ms:.2f}ms"

    @pytest.mark.benchmark
    def test_utad_detection_latency(
        self,
        benchmark,
        sample_ohlcv_bars: list[OHLCVBar],
        mock_trading_range: TradingRange,
    ) -> None:
        """
        Benchmark UTAD pattern detection.

        Target: <150ms per bar.
        """
        detector = UTADDetector()

        def detect_utad_pattern() -> int:
            """Run UTAD detection on bars."""
            from src.pattern_engine.detectors.utad_detector import detect_utad

            result = detect_utad(
                trading_range=mock_trading_range,
                bars=sample_ohlcv_bars[:120],
                phase=WyckoffPhase.C,
                symbol="BENCH",
            )
            return 1 if result else 0

        benchmark(detect_utad_pattern)

        stats = benchmark.stats
        mean_time_ms = stats.mean * 1000

        assert (
            mean_time_ms < UTAD_DETECTION_TARGET_MS * 10
        ), f"UTAD detection too slow: {mean_time_ms:.2f}ms"


class TestFullPipelineLatency:
    """Benchmark end-to-end signal generation pipeline (Task 2 Subtasks 2.6-2.8)."""

    @pytest.mark.benchmark
    def test_full_pipeline_latency(self, benchmark, sample_ohlcv_bars: list[OHLCVBar]) -> None:
        """
        Benchmark complete signal generation pipeline.

        Target: NFR1 <1 second per symbol per bar analyzed.
        This is the critical NFR1 compliance test.
        """

        def run_full_pipeline() -> dict:
            """
            Execute full signal generation workflow:
            1. Volume analysis
            2. Pattern detection (all detectors)
            3. Signal validation
            """
            from datetime import UTC, datetime
            from decimal import Decimal
            from uuid import uuid4

            # Create mock trading range
            trading_range = TradingRange(
                id=uuid4(),
                symbol="BENCH",
                timeframe="1d",
                range_low=Decimal("145.00"),
                range_high=Decimal("155.00"),
                creek=Decimal("147.00"),
                ice=Decimal("153.00"),
                start_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                status=RangeStatus.ACTIVE,
            )

            results = {
                "volume_ratios": [],
                "patterns_detected": 0,
            }

            # 1. Volume analysis
            for i in range(20, min(120, len(sample_ohlcv_bars))):
                ratio = calculate_volume_ratio(sample_ohlcv_bars, i)
                results["volume_ratios"].append(ratio)

            # 2. Pattern detection (run all detectors)
            from src.pattern_engine.detectors.sos_detector import detect_sos
            from src.pattern_engine.detectors.spring_detector import detect_spring
            from src.pattern_engine.detectors.utad_detector import detect_utad

            spring = detect_spring(
                trading_range=trading_range,
                bars=sample_ohlcv_bars[:120],
                phase=WyckoffPhase.C,
                symbol="BENCH",
            )
            if spring:
                results["patterns_detected"] += 1

            sos = detect_sos(
                trading_range=trading_range,
                bars=sample_ohlcv_bars[:120],
                phase=WyckoffPhase.D,
                symbol="BENCH",
            )
            if sos:
                results["patterns_detected"] += 1

            utad = detect_utad(
                trading_range=trading_range,
                bars=sample_ohlcv_bars[:120],
                phase=WyckoffPhase.C,
                symbol="BENCH",
            )
            if utad:
                results["patterns_detected"] += 1

            return results

        result = benchmark(run_full_pipeline)

        # Verify pipeline executed
        assert len(result["volume_ratios"]) > 0

        # Check against NFR1 target
        stats = benchmark.stats
        mean_time_seconds = stats.mean

        assert (
            mean_time_seconds < float(NFR1_TARGET_SECONDS)
        ), f"Full pipeline too slow: {mean_time_seconds:.3f}s per symbol (NFR1 target: <{NFR1_TARGET_SECONDS}s)"

        # Log performance summary
        print("\n=== NFR1 Performance Summary ===")
        print(f"Mean time: {mean_time_seconds:.3f}s")
        print(f"p95 time: {stats.get('percentiles', {}).get(95, 0):.3f}s")
        print(f"Target: <{NFR1_TARGET_SECONDS}s")
        print(f"Status: {'✓ PASS' if mean_time_seconds < float(NFR1_TARGET_SECONDS) else '✗ FAIL'}")
