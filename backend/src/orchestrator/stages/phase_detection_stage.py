"""
Phase Detection Pipeline Stage.

Wraps PhaseClassifier for use in the analysis pipeline.

Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC3, AC4, AC5)
Story 23.1: Wire phase detection facades to real implementations
"""

from datetime import UTC, datetime

import pandas as pd
import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseEvents, WyckoffPhase
from src.models.phase_info import PhaseInfo
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.stages.base import PipelineStage
from src.pattern_engine.phase_detection import PhaseClassifier
from src.pattern_engine.phase_detection._converters import PHASE_TYPE_TO_WYCKOFF
from src.pattern_engine.phase_detection.types import PhaseResult

logger = structlog.get_logger(__name__)


def _bars_to_dataframe(bars: list[OHLCVBar]) -> pd.DataFrame:
    """Convert OHLCVBar list to DataFrame for PhaseClassifier.

    Args:
        bars: List of OHLCV bars.

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume.
    """
    return pd.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
            "volume": [b.volume for b in bars],
        }
    )


def _phase_result_to_info(
    result: PhaseResult,
    bars: list[OHLCVBar],
    trading_range: TradingRange | None,
) -> PhaseInfo:
    """Convert a PhaseResult from PhaseClassifier to PhaseInfo for downstream stages.

    Args:
        result: PhaseResult from PhaseClassifier.classify().
        bars: Original OHLCV bars (for bar index context).
        trading_range: The active trading range, if any.

    Returns:
        PhaseInfo populated from the PhaseResult with safe defaults.
    """
    # Map PhaseType -> WyckoffPhase (None stays None)
    wyckoff_phase: WyckoffPhase | None = None
    if result.phase is not None:
        wyckoff_phase = PHASE_TYPE_TO_WYCKOFF.get(result.phase)

    # Confidence: PhaseResult uses 0.0-1.0, PhaseInfo uses 0-100
    confidence = min(100, max(0, int(result.confidence * 100)))

    duration = max(0, result.duration_bars)
    current_bar_index = len(bars) - 1 if bars else 0
    phase_start = max(0, result.start_bar)

    # Determine trading_allowed and risk from metadata
    trading_allowed = result.metadata.get("trading_allowed", True)
    rejection_reason = result.metadata.get("rejection_reason")

    risk_level = "normal"
    if wyckoff_phase == WyckoffPhase.A:
        risk_level = "high"
    elif wyckoff_phase == WyckoffPhase.B and duration < 10:
        risk_level = "elevated"

    # Only pass trading_range if it's a real TradingRange (not a mock/proxy)
    safe_range = trading_range if isinstance(trading_range, TradingRange) else None

    return PhaseInfo(
        phase=wyckoff_phase,
        confidence=confidence,
        events=PhaseEvents(),
        duration=duration,
        trading_range=safe_range,
        phase_start_bar_index=phase_start,
        current_bar_index=current_bar_index,
        last_updated=datetime.now(UTC),
        current_risk_level=risk_level,
        risk_rationale=rejection_reason,
    )


class PhaseDetectionStage(PipelineStage[list[OHLCVBar], PhaseInfo | None]):
    """
    Pipeline stage for Wyckoff phase detection.

    Detects current Wyckoff phase (A-E) with confidence scoring using
    PhaseClassifier (the real phase detection implementation).

    Input: list[OHLCVBar] - Raw OHLCV data
    Output: PhaseInfo | None - Phase info with events and risk, or None if no range

    Context Keys Required:
        - "volume_analysis": list[VolumeAnalysis] (from VolumeAnalysisStage)
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
    VOLUME_CONTEXT_KEY = "volume_analysis"
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
        Requires volume analysis and trading ranges from context.

        Args:
            bars: List of OHLCV bars to analyze
            context: Pipeline context with volume_analysis and trading_ranges

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

        volume_analysis: list[VolumeAnalysis] | None = context.get(self.VOLUME_CONTEXT_KEY)
        if volume_analysis is None:
            raise RuntimeError(
                f"Required context key '{self.VOLUME_CONTEXT_KEY}' not found. "
                "Ensure VolumeAnalysisStage runs before PhaseDetectionStage."
            )

        trading_ranges: list[TradingRange] | None = context.get(self.RANGES_CONTEXT_KEY)
        if trading_ranges is None:
            raise RuntimeError(
                f"Required context key '{self.RANGES_CONTEXT_KEY}' not found. "
                "Ensure RangeDetectionStage runs before PhaseDetectionStage."
            )

        logger.debug(
            "phase_detection_executing",
            bar_count=len(bars),
            volume_analysis_count=len(volume_analysis),
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

        # Convert bars to DataFrame and classify using PhaseClassifier
        df = _bars_to_dataframe(bars)
        phase_result = self._classifier.classify(df)

        # Convert PhaseResult to PhaseInfo for downstream stages
        phase_info = _phase_result_to_info(phase_result, bars, current_range)

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
