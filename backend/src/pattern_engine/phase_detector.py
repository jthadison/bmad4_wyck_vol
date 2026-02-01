"""
DEPRECATED: This module is deprecated and will be removed in v0.3.0.

Migration Guide
===============
Use the new phase_detection package instead:

    # Old (deprecated):
    from pattern_engine.phase_detector import detect_selling_climax, detect_automatic_rally

    # New (recommended):
    from pattern_engine.phase_detection import SellingClimaxDetector, AutomaticRallyDetector

Timeline:
    - v0.2.0: Deprecation warnings added (current)
    - v0.3.0: This module will be removed

See phase_detection package documentation for migration details.
"""

import warnings
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, Optional, TypeVar

# Re-export types from new package for gradual migration
from .phase_detection import DetectionConfig, EventType, PhaseEvent, PhaseResult, PhaseType

if TYPE_CHECKING:
    from src.models.automatic_rally import AutomaticRally
    from src.models.ohlcv import OHLCVBar
    from src.models.phase_classification import PhaseEvents, WyckoffPhase
    from src.models.secondary_test import SecondaryTest
    from src.models.selling_climax import SellingClimax, SellingClimaxZone
    from src.models.trading_range import TradingRange
    from src.models.volume_analysis import VolumeAnalysis

# FR3 requirement: minimum 70% confidence for trading
MIN_PHASE_CONFIDENCE = 70

F = TypeVar("F", bound=Callable[..., Any])


def _deprecation_warning(old_name: str, new_import: str) -> None:
    """Issue deprecation warning with migration guidance."""
    warnings.warn(
        f"'{old_name}' is deprecated. Use '{new_import}' instead. "
        "This will be removed in v0.3.0.",
        DeprecationWarning,
        stacklevel=3,
    )


def _deprecated(new_import: str) -> Callable[[F], F]:
    """Decorator to add deprecation warning to functions."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _deprecation_warning(
                f"pattern_engine.phase_detector.{func.__name__}",
                new_import,
            )
            # Import and call original implementation
            from src.pattern_engine import _phase_detector_impl as impl

            return getattr(impl, func.__name__)(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


@_deprecated("pattern_engine.phase_detection.SellingClimaxDetector")
def detect_selling_climax(
    bars: "list[OHLCVBar]", volume_analysis: "list[VolumeAnalysis]"
) -> "Optional[SellingClimax]":
    """DEPRECATED: Use SellingClimaxDetector from phase_detection package."""
    ...


@_deprecated("pattern_engine.phase_detection.SellingClimaxDetector")
def detect_sc_zone(
    bars: "list[OHLCVBar]", volume_analysis: "list[VolumeAnalysis]", max_gap_bars: int = 10
) -> "Optional[SellingClimaxZone]":
    """DEPRECATED: Use SellingClimaxDetector from phase_detection package."""
    ...


@_deprecated("pattern_engine.phase_detection.AutomaticRallyDetector")
def detect_automatic_rally(
    bars: "list[OHLCVBar]", sc: "SellingClimax", volume_analysis: "list[VolumeAnalysis]"
) -> "Optional[AutomaticRally]":
    """DEPRECATED: Use AutomaticRallyDetector from phase_detection package."""
    ...


@_deprecated("pattern_engine.phase_detection.SecondaryTestDetector")
def detect_secondary_test(
    bars: "list[OHLCVBar]",
    sc: "SellingClimax",
    ar: "AutomaticRally",
    volume_analysis: "list[VolumeAnalysis]",
    existing_sts: "Optional[list[SecondaryTest]]" = None,
) -> "Optional[SecondaryTest]":
    """DEPRECATED: Use SecondaryTestDetector from phase_detection package."""
    ...


@_deprecated("pattern_engine.phase_detection.PhaseClassifier")
def is_phase_a_confirmed(sc: "Optional[SellingClimax]", ar: "Optional[AutomaticRally]") -> bool:
    """DEPRECATED: Use PhaseClassifier from phase_detection package."""
    ...


@_deprecated("pattern_engine.phase_detection.PhaseConfidenceScorer")
def calculate_phase_confidence(
    phase: "WyckoffPhase",
    events: "PhaseEvents",
    trading_range: "Optional[TradingRange]" = None,
) -> int:
    """DEPRECATED: Use PhaseConfidenceScorer from phase_detection package."""
    ...


@_deprecated("MIN_PHASE_CONFIDENCE constant")
def should_reject_phase(confidence: int) -> bool:
    """DEPRECATED: Check confidence against MIN_PHASE_CONFIDENCE directly."""
    ...


__all__ = [
    # Types (re-exported from new package)
    "PhaseType",
    "EventType",
    "PhaseEvent",
    "PhaseResult",
    "DetectionConfig",
    # Deprecated functions
    "detect_selling_climax",
    "detect_sc_zone",
    "detect_automatic_rally",
    "detect_secondary_test",
    "is_phase_a_confirmed",
    "calculate_phase_confidence",
    "should_reject_phase",
    "MIN_PHASE_CONFIDENCE",
]

# Issue warning on module import
warnings.warn(
    "The 'pattern_engine.phase_detector' module is deprecated. "
    "Import from 'pattern_engine.phase_detection' instead. "
    "This module will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)
