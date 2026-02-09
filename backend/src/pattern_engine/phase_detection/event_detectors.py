"""
Wyckoff event detection classes.

This module contains detector classes for identifying specific Wyckoff
events within price/volume data. Facades wire to real implementations
in _phase_detector_impl.py (Story 23.1).
"""

from abc import ABC, abstractmethod
from decimal import Decimal

import pandas as pd
import structlog

from src.models.automatic_rally import AutomaticRally
from src.models.ohlcv import OHLCVBar
from src.models.secondary_test import SecondaryTest
from src.models.selling_climax import SellingClimax
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine._phase_detector_impl import (
    detect_automatic_rally,
    detect_secondary_test,
    detect_selling_climax,
)
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

    Note: Spring detection requires TradingRange context (Creek level)
    not available from OHLCV DataFrame alone. Full detection is wired
    through the PhaseDetector v2 pipeline.
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Spring events in OHLCV data.

        Returns empty list because Spring detection requires TradingRange
        context (Creek level) that is not available from a DataFrame-only
        interface. Full Spring detection uses the PhaseDetector v2 pipeline.

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
            "not available in DataFrame-only interface",
        )
        return []


class SignOfStrengthDetector(BaseEventDetector):
    """
    Detects Sign of Strength (SOS) events.

    SOS is characterized by:
    - Decisive break above resistance (Ice)
    - High volume on breakout (>1.5x average)
    - Wide spread up bar
    - Occurs in Phase D

    Note: SOS detection requires TradingRange (Ice level) and
    PhaseClassification context not available from OHLCV DataFrame alone.
    Full detection is wired through the SOSDetector orchestrator.
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Sign of Strength events in OHLCV data.

        Returns empty list because SOS detection requires TradingRange
        and PhaseClassification context not available from a DataFrame-only
        interface. Full SOS detection uses the SOSDetector orchestrator.

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
            "context not available in DataFrame-only interface",
        )
        return []


class LastPointOfSupportDetector(BaseEventDetector):
    """
    Detects Last Point of Support (LPS) events.

    LPS is characterized by:
    - Pullback after SOS
    - Tests broken resistance as new support
    - Lower volume than SOS
    - Occurs in Phase D/E

    Note: LPS detection requires TradingRange and SOSBreakout context
    not available from OHLCV DataFrame alone. Full detection is wired
    through the LPSDetector orchestrator.
    """

    def detect(self, ohlcv: pd.DataFrame) -> list[PhaseEvent]:
        """
        Detect Last Point of Support events in OHLCV data.

        Returns empty list because LPS detection requires TradingRange
        and SOSBreakout context not available from a DataFrame-only
        interface. Full LPS detection uses the LPSDetector orchestrator.

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
            "context not available in DataFrame-only interface",
        )
        return []
