"""
Wyckoff event detection classes.

This module contains detector classes for identifying specific Wyckoff
events within price/volume data. Facades wire to real implementations
in _phase_detector_impl.py (Story 23.1) and Epic 5 detectors.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

import pandas as pd
import structlog

from src.models.automatic_rally import AutomaticRally
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.secondary_test import SecondaryTest
from src.models.selling_climax import SellingClimax
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine._phase_detector_impl import (
    detect_automatic_rally,
    detect_secondary_test,
    detect_selling_climax,
)
from src.pattern_engine.detectors.lps_detector import detect_lps
from src.pattern_engine.detectors.sos_detector import detect_sos_breakout
from src.pattern_engine.detectors.spring.confidence_scorer import SpringConfidenceScorer
from src.pattern_engine.detectors.spring.detector import SpringDetectorCore
from src.pattern_engine.detectors.spring.risk_analyzer import SpringRiskAnalyzer
from src.pattern_engine.volume_analyzer import VolumeAnalyzer

from .types import DetectionConfig, EventType, PhaseEvent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper functions: DataFrame -> OHLCVBar / VolumeAnalysis conversion
# ---------------------------------------------------------------------------


def _dataframe_to_ohlcv_bars(df: pd.DataFrame) -> list[OHLCVBar]:
    """Convert a DataFrame with OHLCV columns to a list of OHLCVBar objects.

    Args:
        df: DataFrame with columns [timestamp, open, high, low, close, volume]

    Returns:
        List of OHLCVBar instances
    """
    bars: list[OHLCVBar] = []
    for _, row in df.iterrows():
        ts = pd.to_datetime(row["timestamp"])
        # Convert pandas Timestamp to Python datetime
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        high = Decimal(str(row["high"]))
        low = Decimal(str(row["low"]))
        bars.append(
            OHLCVBar(
                symbol="UNKNOWN",
                timeframe="1d",
                timestamp=ts,
                open=Decimal(str(row["open"])),
                high=high,
                low=low,
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]),
                spread=high - low,
            )
        )
    return bars


def _create_volume_analysis(bars: list[OHLCVBar]) -> list[VolumeAnalysis]:
    """Run VolumeAnalyzer on a list of OHLCVBar to produce VolumeAnalysis results.

    Args:
        bars: List of OHLCVBar instances

    Returns:
        List of VolumeAnalysis instances (one per bar)
    """
    analyzer = VolumeAnalyzer()
    return analyzer.analyze(bars)


# ---------------------------------------------------------------------------
# Conversion helpers: model objects -> PhaseEvent
# ---------------------------------------------------------------------------


def _find_bar_index(timestamp: datetime, bars: list[OHLCVBar] | None) -> int:
    """Find bar index by matching timestamp in bars list.

    Returns 0 if bars is None or timestamp not found.
    """
    if bars is None:
        return 0
    for i, bar in enumerate(bars):
        if bar.timestamp == timestamp:
            return i
    return 0


def _selling_climax_to_event(sc: SellingClimax) -> PhaseEvent:
    """Convert a SellingClimax model to a PhaseEvent."""
    return PhaseEvent(
        event_type=EventType.SELLING_CLIMAX,
        bar_index=sc.bar_index,
        timestamp=pd.to_datetime(sc.bar["timestamp"]).to_pydatetime(),
        price=float(sc.bar["close"]),
        volume=float(sc.bar["volume"]),
        confidence=sc.confidence / 100.0,
        metadata={
            "volume_ratio": float(sc.volume_ratio),
            "spread_ratio": float(sc.spread_ratio),
        },
    )


def _automatic_rally_to_event(ar: AutomaticRally) -> PhaseEvent:
    """Convert an AutomaticRally model to a PhaseEvent."""
    return PhaseEvent(
        event_type=EventType.AUTOMATIC_RALLY,
        bar_index=ar.bar_index,
        timestamp=pd.to_datetime(ar.bar["timestamp"]).to_pydatetime(),
        price=float(ar.bar["close"]),
        volume=float(ar.bar["volume"]),
        confidence=ar.quality_score,
        metadata={
            "rally_pct": float(ar.rally_pct),
            "bars_after_sc": ar.bars_after_sc,
            "volume_profile": ar.volume_profile,
        },
    )


def _secondary_test_to_event(st: SecondaryTest) -> PhaseEvent:
    """Convert a SecondaryTest model to a PhaseEvent."""
    return PhaseEvent(
        event_type=EventType.SECONDARY_TEST,
        bar_index=st.bar_index,
        timestamp=pd.to_datetime(st.bar["timestamp"]).to_pydatetime(),
        price=float(st.bar["close"]),
        volume=float(st.bar["volume"]),
        confidence=st.confidence / 100.0,
        metadata={
            "test_number": st.test_number,
            "volume_reduction_pct": float(st.volume_reduction_pct),
        },
    )


def _sos_breakout_to_event(sos: SOSBreakout, bars: list[OHLCVBar] | None = None) -> PhaseEvent:
    """Convert a SOSBreakout model to a PhaseEvent."""
    # Map quality_tier to 0-1 confidence score
    quality_confidence = {"EXCELLENT": 0.9, "GOOD": 0.8, "ACCEPTABLE": 0.65}
    confidence = quality_confidence.get(sos.quality_tier, 0.65)

    # Resolve bar_index by matching timestamp in bars list
    bar_index = _find_bar_index(sos.bar.timestamp, bars)

    return PhaseEvent(
        event_type=EventType.SIGN_OF_STRENGTH,
        bar_index=bar_index,
        timestamp=sos.bar.timestamp,
        price=float(sos.breakout_price),
        volume=float(sos.bar.volume),
        confidence=confidence,
        metadata={
            "breakout_pct": float(sos.breakout_pct),
            "volume_ratio": float(sos.volume_ratio),
            "ice_reference": float(sos.ice_reference),
            "quality_tier": sos.quality_tier,
        },
    )


def _lps_to_event(lps_model: "LPS", bars: list[OHLCVBar] | None = None) -> PhaseEvent:
    """Convert a LPS model to a PhaseEvent."""
    # Build confidence from base + distance quality + effort/result bonuses
    # Base: 0.6 for any valid LPS (passed all validation gates)
    # Distance quality: PREMIUM +0.15, QUALITY +0.10, ACCEPTABLE +0.05
    # Effort/result bonus scaled to 0-1 range (max ±0.10)
    distance_bonus = {"PREMIUM": 0.15, "QUALITY": 0.10, "ACCEPTABLE": 0.05}
    confidence = 0.6 + distance_bonus.get(lps_model.distance_quality, 0.05)
    confidence += lps_model.effort_result_bonus / 100.0
    confidence = max(0.0, min(1.0, confidence))

    # Resolve bar_index by matching timestamp in bars list
    bar_index = _find_bar_index(lps_model.bar.timestamp, bars)

    return PhaseEvent(
        event_type=EventType.LAST_POINT_OF_SUPPORT,
        bar_index=bar_index,
        timestamp=lps_model.bar.timestamp,
        price=float(lps_model.pullback_low),
        volume=float(lps_model.pullback_volume),
        confidence=confidence,
        metadata={
            "distance_from_ice": float(lps_model.distance_from_ice),
            "distance_quality": lps_model.distance_quality,
            "volume_ratio_vs_avg": float(lps_model.volume_ratio_vs_avg),
            "support_quality": "HELD" if lps_model.held_support else "BROKEN",
            "bars_after_sos": lps_model.bars_after_sos,
            "bounce_confirmed": lps_model.bounce_confirmed,
            "effort_result": lps_model.effort_result,
        },
    )


class BaseEventDetector(ABC):
    """
    Base class for all event detectors.

    Provides common interface and configuration for Wyckoff event detection.
    Subclasses implement specific detection logic for each event type.

    Attributes:
        config: Detection configuration parameters
    """

    def __init__(self, config: DetectionConfig) -> None:
        """
        Initialize the event detector.

        Args:
            config: Detection configuration parameters
        """
        self.config = config

    @abstractmethod
    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect events in OHLCV data.

        Args:
            ohlcv: DataFrame with columns [timestamp, open, high, low, close, volume]

        Returns:
            List of detected PhaseEvent objects
        """
        pass

    def _validate_dataframe(self, ohlcv: pd.DataFrame) -> bool:
        """
        Validate that DataFrame has required columns.

        Args:
            ohlcv: DataFrame to validate

        Returns:
            True if valid, False otherwise
        """
        required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
        return required_columns.issubset(set(ohlcv.columns))


class SellingClimaxDetector(BaseEventDetector):
    """
    Detects Selling Climax (SC) events.

    SC is characterized by:
    - Ultra-high volume (>2x average)
    - Wide spread down bar
    - Closes near low
    - Follows downtrend

    Wired to detect_selling_climax() in _phase_detector_impl (Story 23.1).
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Selling Climax events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected SC events

        Raises:
            ValueError: If DataFrame is missing required columns
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        bars = _dataframe_to_ohlcv_bars(ohlcv)
        volume_analysis = _create_volume_analysis(bars)
        try:
            sc = detect_selling_climax(bars, volume_analysis)
        except (ValueError, TypeError) as e:
            logger.error("sc_detection_error", error=str(e))
            return []
        if sc is None:
            return []
        return [_selling_climax_to_event(sc)]


class AutomaticRallyDetector(BaseEventDetector):
    """
    Detects Automatic Rally (AR) events.

    AR is characterized by:
    - Follows SC within a few bars
    - Rally on declining volume
    - Establishes initial resistance

    Wired to detect_automatic_rally() in _phase_detector_impl (Story 23.1).
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Automatic Rally events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected AR events

        Raises:
            ValueError: If DataFrame is missing required columns
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        bars = _dataframe_to_ohlcv_bars(ohlcv)
        volume_analysis = _create_volume_analysis(bars)
        # AR requires SC to be detected first (sequential dependency)
        try:
            sc = detect_selling_climax(bars, volume_analysis)
            if sc is None:
                return []
            ar = detect_automatic_rally(bars, sc, volume_analysis)
        except (ValueError, TypeError) as e:
            logger.error("ar_detection_error", error=str(e))
            return []
        if ar is None:
            return []
        return [_automatic_rally_to_event(ar)]


class SecondaryTestDetector(BaseEventDetector):
    """
    Detects Secondary Test (ST) events.

    ST is characterized by:
    - Tests SC low area
    - Lower volume than SC
    - May or may not reach SC low
    - Confirms support zone

    Wired to detect_secondary_test() in _phase_detector_impl (Story 23.1).
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Secondary Test events in OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            List of detected ST events

        Raises:
            ValueError: If DataFrame is missing required columns
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        bars = _dataframe_to_ohlcv_bars(ohlcv)
        volume_analysis = _create_volume_analysis(bars)
        # ST requires SC + AR first (sequential dependency)
        try:
            sc = detect_selling_climax(bars, volume_analysis)
            if sc is None:
                return []
            ar = detect_automatic_rally(bars, sc, volume_analysis)
            if ar is None:
                return []
            # Detect multiple STs
            events: list[PhaseEvent] = []
            existing_sts: list[SecondaryTest] = []
            for _ in range(10):  # Max 10 STs (safety limit per v2 impl)
                st = detect_secondary_test(bars, sc, ar, volume_analysis, existing_sts)
                if st is None:
                    break
                events.append(_secondary_test_to_event(st))
                existing_sts.append(st)
        except (ValueError, TypeError) as e:
            logger.error("st_detection_error", error=str(e))
            return []
        return events


class SpringDetector(BaseEventDetector):
    """
    Detects Spring events (shakeout below support).

    Spring is characterized by:
    - Price breaks below support (Creek)
    - Low volume on the break (<0.7x average)
    - Quick recovery back above support
    - Occurs in Phase C

    The detect() method returns empty (requires TradingRange context).
    Use detect_with_context() for full Spring detection via SpringDetectorCore.
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Spring events in OHLCV data.

        Returns empty list because Spring detection requires TradingRange
        context (Creek level) not available from a DataFrame-only interface.
        Use detect_with_context() instead.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            Empty list (context-dependent detection not possible here)

        Raises:
            ValueError: If DataFrame is missing required columns
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        logger.debug(
            "spring_detector.no_context",
            message="Spring detection requires TradingRange context "
            "not available in DataFrame-only interface. Use detect_with_context().",
        )
        return []

    def detect_with_context(
        self,
        ohlcv: pd.DataFrame,
        trading_range: TradingRange,
        phase: WyckoffPhase,
        symbol: str,
    ) -> list[PhaseEvent]:
        """
        Detect Spring events with full TradingRange context.

        Delegates to SpringDetectorCore for real detection with Phase C
        validation and volume < 0.7x enforcement (FR12, FR15).

        Args:
            ohlcv: DataFrame with OHLCV columns
            trading_range: Active trading range with Creek level
            phase: Current Wyckoff phase (must be Phase C)
            symbol: Trading symbol

        Returns:
            List of detected Spring PhaseEvents
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")

        bars = _dataframe_to_ohlcv_bars(ohlcv)

        scorer = SpringConfidenceScorer()
        risk_analyzer = SpringRiskAnalyzer()
        detector = SpringDetectorCore(scorer, risk_analyzer)

        try:
            spring = detector.detect(trading_range, bars, phase, symbol)
        except (ValueError, TypeError) as e:
            logger.error("spring_detection_error", error=str(e))
            return []

        if spring is None:
            return []

        # Map quality_tier to 0-1 confidence score
        quality_confidence = {"IDEAL": 0.9, "GOOD": 0.75, "ACCEPTABLE": 0.6}
        confidence = quality_confidence.get(spring.quality_tier, 0.6)

        return [
            PhaseEvent(
                event_type=EventType.SPRING,
                bar_index=spring.bar_index,
                timestamp=spring.bar.timestamp,
                price=float(spring.bar.close),
                volume=float(spring.bar.volume),
                confidence=confidence,
                metadata={
                    "penetration_pct": float(spring.penetration_pct),
                    "volume_ratio": float(spring.volume_ratio),
                    "recovery_bars": spring.recovery_bars,
                    "creek_reference": float(spring.creek_reference),
                    "quality_tier": spring.quality_tier,
                },
            )
        ]


class SignOfStrengthDetector(BaseEventDetector):
    """
    Detects Sign of Strength (SOS) events.

    SOS is characterized by:
    - Decisive break above resistance (Ice)
    - High volume on breakout (>1.5x average)
    - Wide spread up bar
    - Occurs in Phase D

    The detect() method returns empty (requires context).
    Use detect_with_context() for full SOS detection via detect_sos_breakout().
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Sign of Strength events in OHLCV data.

        Returns empty list because SOS detection requires TradingRange
        and PhaseClassification context. Use detect_with_context() instead.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            Empty list (context-dependent detection not possible here)

        Raises:
            ValueError: If DataFrame is missing required columns
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        logger.debug(
            "sos_detector.no_context",
            message="SOS detection requires TradingRange and PhaseClassification "
            "context. Use detect_with_context().",
        )
        return []

    def detect_with_context(
        self,
        ohlcv: pd.DataFrame,
        trading_range: TradingRange,
        volume_analysis: dict,
        phase: PhaseClassification,
        symbol: str,
    ) -> list[PhaseEvent]:
        """
        Detect SOS events with full TradingRange and phase context.

        Delegates to detect_sos_breakout() for real detection with Phase D
        validation and volume >= 1.5x enforcement (FR12, FR15).

        Args:
            ohlcv: DataFrame with OHLCV columns
            trading_range: Active trading range with Ice level
            volume_analysis: Pre-calculated volume ratios from VolumeAnalyzer
            phase: Current Wyckoff phase classification (Phase D required)
            symbol: Trading symbol

        Returns:
            List of detected SOS PhaseEvents
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")

        bars = _dataframe_to_ohlcv_bars(ohlcv)

        try:
            sos = detect_sos_breakout(
                range=trading_range,
                bars=bars,
                volume_analysis=volume_analysis,
                phase=phase,
                symbol=symbol,
            )
        except (ValueError, TypeError) as e:
            logger.error("sos_detection_error", error=str(e))
            return []

        if sos is None:
            return []

        return [_sos_breakout_to_event(sos, bars)]


class LastPointOfSupportDetector(BaseEventDetector):
    """
    Detects Last Point of Support (LPS) events.

    LPS is characterized by:
    - Pullback after SOS
    - Tests broken resistance as new support
    - Lower volume than SOS
    - Occurs in Phase D/E

    The detect() method returns empty (requires context).
    Use detect_with_context() for full LPS detection via detect_lps().
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Last Point of Support events in OHLCV data.

        Returns empty list because LPS detection requires TradingRange
        and SOSBreakout context. Use detect_with_context() instead.

        Args:
            ohlcv: DataFrame with OHLCV data

        Returns:
            Empty list (context-dependent detection not possible here)

        Raises:
            ValueError: If DataFrame is missing required columns
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")
        logger.debug(
            "lps_detector.no_context",
            message="LPS detection requires TradingRange and SOSBreakout "
            "context. Use detect_with_context().",
        )
        return []

    def detect_with_context(
        self,
        ohlcv: pd.DataFrame,
        trading_range: TradingRange,
        sos_breakout: SOSBreakout,
        volume_analysis: dict,
    ) -> list[PhaseEvent]:
        """
        Detect LPS events with full TradingRange and SOS context.

        Delegates to detect_lps() for real detection. LPS requires a
        prior SOS breakout to validate pullback to new support.

        Args:
            ohlcv: DataFrame with OHLCV columns
            trading_range: Active trading range with Ice level
            sos_breakout: Previously detected SOS breakout (required context)
            volume_analysis: Pre-calculated volume ratios from VolumeAnalyzer

        Returns:
            List of detected LPS PhaseEvents
        """
        if not self._validate_dataframe(ohlcv):
            raise ValueError("Invalid DataFrame: missing required columns")

        bars = _dataframe_to_ohlcv_bars(ohlcv)

        try:
            lps_result = detect_lps(
                range=trading_range,
                sos=sos_breakout,
                bars=bars,
                volume_analysis=volume_analysis,
            )
        except (ValueError, TypeError) as e:
            logger.error("lps_detection_error", error=str(e))
            return []

        if lps_result is None:
            return []

        return [_lps_to_event(lps_result, bars)]
