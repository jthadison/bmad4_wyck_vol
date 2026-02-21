"""
Phase Detection Pipeline Stage.

Wraps PhaseClassifier for use in the analysis pipeline.

Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC3, AC4, AC5)
Story 23.1: Migrate to PhaseClassifier (real phase detection implementation)
"""

from datetime import UTC, datetime

import pandas as pd
import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_info import PhaseInfo
from src.models.trading_range import TradingRange
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.pattern_engine.phase_detection import PhaseClassifier
from src.pattern_engine.phase_detection._converters import (
    PHASE_TYPE_TO_WYCKOFF,
    events_to_phase_events,
)
from src.pattern_engine.phase_detection.types import PhaseResult

logger = structlog.get_logger(__name__)


class PhaseDetectionStage(PipelineStage[list[OHLCVBar], PhaseInfo | None]):
    """
    Pipeline stage for Wyckoff phase detection.

    Detects current Wyckoff phase (A-E) with confidence scoring using the
    PhaseClassifier (Story 23.1: real implementation replacing deprecated v2).

    Input: list[OHLCVBar] - Raw OHLCV data
    Output: PhaseInfo | None - Phase info with events and risk, or None if no range

    Context Keys Required:
        - "trading_ranges": list[TradingRange] (from RangeDetectionStage)

    Context Keys Set:
        - "phase_info": PhaseInfo | None (for downstream stages)
        - "current_trading_range": TradingRange | None (most recent active range)

    Example:
        >>> classifier = PhaseClassifier()
        >>> stage = PhaseDetectionStage(classifier)
        >>> result = await stage.run(bars, context)
        >>> if result.success and result.output:
        ...     phase_info = result.output
        ...     print(f"Phase: {phase_info.phase}, Confidence: {phase_info.confidence}%")
    """

    CONTEXT_KEY = "phase_info"
    RANGES_CONTEXT_KEY = "trading_ranges"
    CURRENT_RANGE_KEY = "current_trading_range"

    def __init__(self, phase_classifier: PhaseClassifier) -> None:
        """
        Initialize the phase detection stage.

        Args:
            phase_classifier: Configured PhaseClassifier instance
        """
        self._classifier = phase_classifier

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        return "phase_detection"

    async def execute(self, bars: list[OHLCVBar], context: PipelineContext) -> PhaseInfo | None:
        """
        Execute Wyckoff phase detection on input bars.

        Detects phase using the most recent active trading range.
        Requires trading ranges from context.

        Args:
            bars: List of OHLCV bars to analyze
            context: Pipeline context with trading_ranges

        Returns:
            PhaseInfo with phase, confidence, events, and risk management,
            or None if no active trading range found

        Raises:
            ValueError: If bars list is empty
            TypeError: If bars is not a list or contains non-OHLCVBar items
            RuntimeError: If required context keys not found
        """
        if not isinstance(bars, list):
            raise TypeError(f"Expected list[OHLCVBar], got {type(bars).__name__}")
        if not bars:
            raise ValueError("Cannot detect phase on empty bars list")
        if bars and not isinstance(bars[0], OHLCVBar):
            raise TypeError(f"Expected OHLCVBar items, got {type(bars[0]).__name__}")

        trading_ranges: list[TradingRange] | None = context.get(self.RANGES_CONTEXT_KEY)
        if trading_ranges is None:
            raise RuntimeError(
                f"Required context key '{self.RANGES_CONTEXT_KEY}' not found. "
                "Ensure RangeDetectionStage runs before PhaseDetectionStage."
            )

        logger.debug(
            "phase_detection_executing",
            bar_count=len(bars),
            ranges_count=len(trading_ranges),
            symbol=context.symbol,
            timeframe=context.timeframe,
            correlation_id=str(context.correlation_id),
        )

        current_range = self._get_most_recent_active_range(trading_ranges)
        context.set(self.CURRENT_RANGE_KEY, current_range)

        if current_range is None:
            logger.debug(
                "phase_detection_no_range",
                message="No active trading range found",
                symbol=context.symbol,
                correlation_id=str(context.correlation_id),
            )
            context.set(self.CONTEXT_KEY, None)
            return None

        df = self._bars_to_dataframe(bars)
        result = self._classifier.classify(df)
        phase_info = self._phase_result_to_info(result, current_range, bars)

        context.set(self.CONTEXT_KEY, phase_info)

        logger.debug(
            "phase_detection_complete",
            phase=phase_info.phase.value if phase_info.phase else None,
            confidence=phase_info.confidence,
            duration=phase_info.duration,
            risk_level=phase_info.current_risk_level,
            symbol=context.symbol,
            correlation_id=str(context.correlation_id),
        )

        return phase_info

    def _bars_to_dataframe(self, bars: list[OHLCVBar]) -> pd.DataFrame:
        """
        Convert list of OHLCVBar to DataFrame for PhaseClassifier.

        Args:
            bars: List of OHLCV bars

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        return pd.DataFrame(
            [
                {
                    "timestamp": bar.timestamp,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
                for bar in bars
            ]
        )

    def _phase_result_to_info(
        self,
        result: PhaseResult,
        current_range: TradingRange | None,
        bars: list[OHLCVBar],
    ) -> PhaseInfo:
        """
        Convert PhaseResult (facade) to PhaseInfo (pipeline model).

        Maps PhaseType -> WyckoffPhase, scales confidence 0.0-1.0 -> 0-100,
        and converts facade PhaseEvents to model PhaseEvents.

        Args:
            result: PhaseResult from PhaseClassifier.classify()
            current_range: Active trading range (stored on PhaseInfo)
            bars: Input bars (used for current_bar_index)

        Returns:
            PhaseInfo compatible with all downstream pipeline stages
        """
        phase = PHASE_TYPE_TO_WYCKOFF.get(result.phase) if result.phase is not None else None
        phase_events = events_to_phase_events(result.events)
        # Only pass trading_range when it is a real TradingRange instance so that
        # Pydantic v2's strict model_type validation never rejects a test mock.
        trading_range_val = current_range if isinstance(current_range, TradingRange) else None

        return PhaseInfo(
            phase=phase,
            confidence=int(result.confidence * 100),
            events=phase_events,
            duration=result.duration_bars,
            phase_start_bar_index=result.start_bar,
            current_bar_index=len(bars) - 1,
            last_updated=datetime.now(UTC),
            trading_range=trading_range_val,
        )

    def _get_most_recent_active_range(self, ranges: list[TradingRange]) -> TradingRange | None:
        """
        Get the most recent active trading range.

        Args:
            ranges: List of trading ranges

        Returns:
            Most recent active range, or None if no active ranges
        """
        active_ranges = [r for r in ranges if r.is_active]
        if not active_ranges:
            return None
        return max(active_ranges, key=lambda r: r.end_index)
