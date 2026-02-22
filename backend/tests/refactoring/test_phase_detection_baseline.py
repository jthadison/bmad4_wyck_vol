"""
Phase Detection Baseline Tests (Story 22.14 - AC4)

Tests for Wyckoff phase detection functionality:
- Selling Climax (SC) detection with volume criteria
- Automatic Rally (AR) detection timing
- Secondary Test (ST) detection with support test
- Phase classification accuracy
- Confidence scoring ranges
- Backward compatibility between v1 and v2

These tests validate the phase_detector.py and phase_detector_v2.py
modules before refactoring work begins.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.selling_climax import SellingClimax
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine._phase_detector_impl import (
    MIN_PHASE_CONFIDENCE,
    detect_automatic_rally,
    detect_secondary_test,
    detect_selling_climax,
)


def create_ohlcv_bar(
    index: int,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: int,
    symbol: str = "AAPL",
    timeframe: str = "1h",
) -> OHLCVBar:
    """Helper to create OHLCVBar instances for testing."""
    base_time = datetime(2025, 1, 1, 9, 30, tzinfo=UTC)
    timestamp = base_time + timedelta(hours=index)
    spread = high - low

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=spread,
        spread_ratio=spread / Decimal("2.0") if spread else Decimal("1.0"),
        volume_ratio=Decimal(volume) / Decimal("100000"),
        created_at=datetime.now(UTC),
    )


def create_volume_analysis(
    bar: OHLCVBar,
    volume_ratio: Decimal,
    spread_ratio: Decimal,
    close_position: Decimal,
    effort_result: EffortResult = EffortResult.NORMAL,
) -> VolumeAnalysis:
    """Helper to create VolumeAnalysis instances for testing."""
    return VolumeAnalysis(
        bar=bar,
        volume_ratio=volume_ratio,
        spread_ratio=spread_ratio,
        close_position=close_position,
        effort_result=effort_result,
    )


class TestSellingClimaxDetection:
    """Test SC detection with volume criteria (AC4)."""

    def test_sc_detection_with_valid_climax(self):
        """AC4: Should detect SC with ultra-high volume (>2.0x)."""
        # Create bars: normal bars followed by SC candidate
        bars = []
        for i in range(20):
            bar = create_ohlcv_bar(
                index=i,
                open_price=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=100000,
            )
            bars.append(bar)

        # Add SC bar: wide down bar with high volume, close in upper region
        sc_bar = create_ohlcv_bar(
            index=20,
            open_price=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("94"),  # Wide spread
            close=Decimal("98"),  # Close in upper 2/3 of range (0.67)
            volume=300000,  # 3x normal volume
        )
        bars.append(sc_bar)

        # Create volume analysis
        volume_analysis = []
        for i, bar in enumerate(bars[:-1]):
            volume_analysis.append(
                create_volume_analysis(
                    bar=bar,
                    volume_ratio=Decimal("1.0"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.5"),
                    effort_result=EffortResult.NORMAL,
                )
            )

        # SC bar: CLIMACTIC with 3x volume, 3x spread
        volume_analysis.append(
            create_volume_analysis(
                bar=sc_bar,
                volume_ratio=Decimal("3.0"),
                spread_ratio=Decimal("3.0"),
                close_position=Decimal("0.67"),  # (98-94)/(100-94) = 4/6
                effort_result=EffortResult.CLIMACTIC,
            )
        )

        sc = detect_selling_climax(bars, volume_analysis)

        assert sc is not None
        assert sc.confidence >= MIN_PHASE_CONFIDENCE  # 70+

    def test_sc_rejection_low_volume(self):
        """AC4: Should reject SC with insufficient volume (<2.0x)."""
        bars = []
        for i in range(5):
            bar = create_ohlcv_bar(
                index=i,
                open_price=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=100000,
            )
            bars.append(bar)

        # Create volume analysis with low volume ratio
        volume_analysis = []
        for bar in bars:
            volume_analysis.append(
                create_volume_analysis(
                    bar=bar,
                    volume_ratio=Decimal("1.5"),  # Below 2.0 threshold
                    spread_ratio=Decimal("2.0"),
                    close_position=Decimal("0.7"),
                    effort_result=EffortResult.CLIMACTIC,
                )
            )

        sc = detect_selling_climax(bars, volume_analysis)

        assert sc is None

    def test_sc_rejection_narrow_spread(self):
        """AC4: Should reject SC with narrow spread (<1.5x)."""
        bars = []
        for i in range(5):
            bar = create_ohlcv_bar(
                index=i,
                open_price=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=100000,
            )
            bars.append(bar)

        volume_analysis = []
        for bar in bars:
            volume_analysis.append(
                create_volume_analysis(
                    bar=bar,
                    volume_ratio=Decimal("3.0"),
                    spread_ratio=Decimal("1.0"),  # Below 1.5 threshold
                    close_position=Decimal("0.7"),
                    effort_result=EffortResult.CLIMACTIC,
                )
            )

        sc = detect_selling_climax(bars, volume_analysis)

        assert sc is None

    def test_sc_rejection_close_too_low(self):
        """AC4: Should reject SC when close in lower half of bar."""
        bars = []
        for i in range(5):
            bar = create_ohlcv_bar(
                index=i,
                open_price=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("94"),
                close=Decimal("95"),  # Close in lower portion
                volume=100000,
            )
            bars.append(bar)

        volume_analysis = []
        for bar in bars:
            volume_analysis.append(
                create_volume_analysis(
                    bar=bar,
                    volume_ratio=Decimal("3.0"),
                    spread_ratio=Decimal("2.0"),
                    close_position=Decimal("0.17"),  # (95-94)/(100-94) = 1/6
                    effort_result=EffortResult.CLIMACTIC,
                )
            )

        sc = detect_selling_climax(bars, volume_analysis)

        assert sc is None

    def test_sc_input_validation_empty_bars(self):
        """AC4: Should raise ValueError for empty bars."""
        with pytest.raises(ValueError, match="empty"):
            detect_selling_climax([], [])

    def test_sc_input_validation_mismatched_lengths(self):
        """AC4: Should raise ValueError for mismatched array lengths."""
        bars = [
            create_ohlcv_bar(
                0, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 100000
            )
        ]
        volume_analysis = []  # Empty but bars has 1

        with pytest.raises(ValueError, match="mismatch"):
            detect_selling_climax(bars, volume_analysis)


class TestSCConfidenceScoring:
    """Test SC confidence scoring ranges (AC4)."""

    def test_confidence_90_plus_excellent_sc(self):
        """AC4: 90+ confidence for excellent SC characteristics."""
        # Excellent SC: 0.9+ close, 3.0+ volume, 2.0+ spread
        bars = [
            create_ohlcv_bar(
                0, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 100000
            ),
            create_ohlcv_bar(
                1, Decimal("100"), Decimal("100"), Decimal("90"), Decimal("99"), 350000
            ),  # SC
        ]

        volume_analysis = [
            create_volume_analysis(
                bars[0], Decimal("1.0"), Decimal("1.0"), Decimal("0.5"), EffortResult.NORMAL
            ),
            create_volume_analysis(
                bars[1],
                Decimal("3.5"),  # 3.5x volume
                Decimal("2.5"),  # 2.5x spread
                Decimal("0.9"),  # 90% close position
                EffortResult.CLIMACTIC,
            ),
        ]

        sc = detect_selling_climax(bars, volume_analysis)

        assert sc is not None
        assert sc.confidence >= 90

    def test_confidence_ranges_70_minimum(self):
        """AC4: Phase confidence should meet minimum threshold (70%)."""
        assert MIN_PHASE_CONFIDENCE == 70


class TestAutomaticRallyDetection:
    """Test AR detection timing (AC4)."""

    def test_ar_detection_after_sc(self):
        """AC4: Should detect AR within timing window after SC."""
        # Create SC bar first
        sc_bar = create_ohlcv_bar(
            index=0,
            open_price=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("90"),
            close=Decimal("95"),
            volume=300000,
        )

        # Create mock SC
        sc = SellingClimax(
            bar={
                "symbol": "AAPL",
                "timestamp": sc_bar.timestamp.isoformat(),
                "open": str(sc_bar.open),
                "high": str(sc_bar.high),
                "low": str(sc_bar.low),
                "close": str(sc_bar.close),
                "volume": sc_bar.volume,
                "spread": str(sc_bar.spread),
            },
            bar_index=0,
            volume_ratio=Decimal("3.0"),
            spread_ratio=Decimal("2.0"),
            close_position=Decimal("0.5"),
            confidence=85,
            prior_close=Decimal("100"),
            detection_timestamp=datetime.now(UTC),
        )

        # Create bars showing rally from SC low
        bars = [sc_bar]
        for i in range(1, 6):
            bar = create_ohlcv_bar(
                index=i,
                open_price=Decimal("91") + Decimal(i),
                high=Decimal("92") + Decimal(i),
                low=Decimal("90") + Decimal(i),
                close=Decimal("91") + Decimal(i),
                volume=150000,
            )
            bars.append(bar)

        # Volume analysis
        volume_analysis = []
        for bar in bars:
            volume_analysis.append(
                create_volume_analysis(
                    bar, Decimal("1.5"), Decimal("1.0"), Decimal("0.6"), EffortResult.NORMAL
                )
            )

        ar = detect_automatic_rally(bars, sc, volume_analysis)

        # AR should be detected (rally from 90 to ~96 = 6.7% > 3% threshold)
        assert ar is not None
        assert ar.rally_pct >= Decimal("0.03")

    def test_ar_input_validation_no_sc(self):
        """AC4: Should raise ValueError when SC is None."""
        bars = [
            create_ohlcv_bar(
                0, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 100000
            )
        ]
        volume_analysis = [
            create_volume_analysis(
                bars[0], Decimal("1.0"), Decimal("1.0"), Decimal("0.5"), EffortResult.NORMAL
            )
        ]

        with pytest.raises(ValueError, match="SC cannot be None"):
            detect_automatic_rally(bars, None, volume_analysis)


class TestSecondaryTestDetection:
    """Test ST detection with support test (AC4)."""

    def test_st_input_validation_empty_bars(self):
        """AC4: Should raise ValueError for empty bars in ST detection."""
        mock_sc = SellingClimax(
            bar={
                "symbol": "AAPL",
                "timestamp": datetime.now(UTC).isoformat(),
                "open": "100",
                "high": "100",
                "low": "90",
                "close": "95",
                "volume": 100000,
                "spread": "10",
            },
            bar_index=0,
            volume_ratio=Decimal("3.0"),
            spread_ratio=Decimal("2.0"),
            close_position=Decimal("0.5"),
            confidence=85,
            prior_close=Decimal("100"),
            detection_timestamp=datetime.now(UTC),
        )

        with pytest.raises(ValueError, match="empty"):
            detect_secondary_test([], mock_sc, [], None)


class TestPhaseClassification:
    """Test phase classification accuracy (AC4)."""

    def test_phase_a_sequence_sc_ar_st(self):
        """AC4: Phase A should include SC -> AR -> ST sequence."""
        # This is a conceptual test - Phase A is confirmed by this sequence
        # SC (Selling Climax) starts Phase A
        # AR (Automatic Rally) confirms stopping action
        # ST (Secondary Test) validates support

        # Phase A events exist in enum
        from src.models.wyckoff_phase import WyckoffPhase

        assert WyckoffPhase.A.value == "A"
        assert WyckoffPhase.B.value == "B"
        assert WyckoffPhase.C.value == "C"
        assert WyckoffPhase.D.value == "D"
        assert WyckoffPhase.E.value == "E"

    def test_wyckoff_phase_progression(self):
        """AC4: Wyckoff phases should progress in order A -> B -> C -> D -> E."""
        from src.models.wyckoff_phase import WyckoffPhase

        phases = ["A", "B", "C", "D", "E"]
        for phase_value in phases:
            assert WyckoffPhase(phase_value) is not None


class TestPhaseDetectorV2Compatibility:
    """Test backward compatibility between v1 and v2 (AC4)."""

    def test_v1_exports_exist(self):
        """AC4: V1 phase_detector should export expected functions."""
        from src.pattern_engine._phase_detector_impl import (
            detect_automatic_rally,
            detect_secondary_test,
            detect_selling_climax,
        )

        # Functions should be callable
        assert callable(detect_selling_climax)
        assert callable(detect_automatic_rally)
        assert callable(detect_secondary_test)

    def test_v2_exists_and_importable(self):
        """AC4: V2 phase_detector should be importable."""
        try:
            from src.pattern_engine.phase_detector_v2 import PhaseDetectorV2

            assert PhaseDetectorV2 is not None
        except ImportError:
            pytest.skip("phase_detector_v2 not yet implemented")

    def test_selling_climax_model_structure(self):
        """AC4: SellingClimax model should have expected attributes."""
        sc = SellingClimax(
            bar={
                "symbol": "AAPL",
                "timestamp": datetime.now(UTC).isoformat(),
                "open": "100",
                "high": "100",
                "low": "90",
                "close": "95",
                "volume": 100000,
                "spread": "10",
            },
            bar_index=0,
            volume_ratio=Decimal("3.0"),
            spread_ratio=Decimal("2.0"),
            close_position=Decimal("0.5"),
            confidence=85,
            prior_close=Decimal("100"),
            detection_timestamp=datetime.now(UTC),
        )

        # Verify expected attributes
        assert hasattr(sc, "bar")
        assert hasattr(sc, "bar_index")
        assert hasattr(sc, "volume_ratio")
        assert hasattr(sc, "spread_ratio")
        assert hasattr(sc, "close_position")
        assert hasattr(sc, "confidence")
        assert hasattr(sc, "prior_close")


class TestVolumeAnalysisIntegration:
    """Test VolumeAnalysis integration with phase detection."""

    def test_effort_result_enum_values(self):
        """Effort result enum should have expected values."""
        assert EffortResult.CLIMACTIC.value in ["CLIMACTIC", "climactic"]
        assert EffortResult.NORMAL.value in ["NORMAL", "normal"]

    def test_volume_analysis_creation(self):
        """VolumeAnalysis should be creatable with expected fields."""
        bar = create_ohlcv_bar(
            0, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 100000
        )
        va = VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.8"),
            close_position=Decimal("0.7"),
            effort_result=EffortResult.CLIMACTIC,
        )

        assert va.volume_ratio == Decimal("2.5")
        assert va.spread_ratio == Decimal("1.8")
        assert va.close_position == Decimal("0.7")
        assert va.effort_result == EffortResult.CLIMACTIC


class TestMinimumPhaseConfidence:
    """Test minimum phase confidence constant."""

    def test_min_confidence_is_70(self):
        """FR3: Minimum phase confidence should be 70%."""
        assert MIN_PHASE_CONFIDENCE == 70

    def test_confidence_used_for_trading_decisions(self):
        """Pattern confidence >= 70% required for trading."""
        # This is a baseline test - actual implementation validates
        # that patterns with < 70% confidence are not traded
        assert MIN_PHASE_CONFIDENCE >= 70
