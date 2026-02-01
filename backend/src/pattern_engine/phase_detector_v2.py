"""
DEPRECATED: This module is deprecated and will be removed in v0.3.0.

Migration Guide
===============
Use the new phase_detection package instead:

    # Old (deprecated):
    from pattern_engine.phase_detector_v2 import PhaseDetector

    # New (recommended):
    from pattern_engine.phase_detection import PhaseClassifier

Timeline:
    - v0.2.0: Deprecation warnings added (current)
    - v0.3.0: This module will be removed

See phase_detection package documentation for migration details.
"""

import warnings
from typing import TYPE_CHECKING, Any, Optional

# Re-export types from new package for gradual migration
from .phase_detection import DetectionConfig, EventType, PhaseEvent, PhaseResult, PhaseType

if TYPE_CHECKING:
    from src.models.phase_classification import WyckoffPhase
    from src.models.phase_info import PhaseInfo


def _deprecation_warning(old_name: str, new_import: str) -> None:
    """Issue deprecation warning with migration guidance."""
    warnings.warn(
        f"'{old_name}' is deprecated. Use '{new_import}' instead. "
        "This will be removed in v0.3.0.",
        DeprecationWarning,
        stacklevel=3,
    )


class PhaseDetector:
    """DEPRECATED: Use PhaseClassifier from phase_detection package."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize PhaseDetector with deprecation warning."""
        _deprecation_warning(
            "pattern_engine.phase_detector_v2.PhaseDetector",
            "pattern_engine.phase_detection.PhaseClassifier",
        )
        # Import and instantiate original implementation
        from src.pattern_engine._phase_detector_v2_impl import (
            PhaseDetector as _PhaseDetector,
        )

        self._impl = _PhaseDetector(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to implementation."""
        return getattr(self._impl, name)


def get_current_phase(phase_info: "PhaseInfo") -> "Optional[WyckoffPhase]":
    """DEPRECATED: Use PhaseClassifier from phase_detection package."""
    _deprecation_warning(
        "pattern_engine.phase_detector_v2.get_current_phase",
        "pattern_engine.phase_detection.PhaseClassifier",
    )
    from src.pattern_engine._phase_detector_v2_impl import get_current_phase as _impl

    return _impl(phase_info)


def is_trading_allowed(phase_info: "PhaseInfo") -> bool:
    """DEPRECATED: Use PhaseClassifier from phase_detection package."""
    _deprecation_warning(
        "pattern_engine.phase_detector_v2.is_trading_allowed",
        "pattern_engine.phase_detection.PhaseClassifier",
    )
    from src.pattern_engine._phase_detector_v2_impl import is_trading_allowed as _impl

    return _impl(phase_info)


def get_phase_description(phase: "WyckoffPhase") -> str:
    """DEPRECATED: Use PhaseClassifier from phase_detection package."""
    _deprecation_warning(
        "pattern_engine.phase_detector_v2.get_phase_description",
        "pattern_engine.phase_detection.PhaseClassifier",
    )
    from src.pattern_engine._phase_detector_v2_impl import get_phase_description as _impl

    return _impl(phase)


__all__ = [
    # Types (re-exported from new package)
    "PhaseType",
    "EventType",
    "PhaseEvent",
    "PhaseResult",
    "DetectionConfig",
    # Deprecated classes/functions
    "PhaseDetector",
    "get_current_phase",
    "is_trading_allowed",
    "get_phase_description",
]

# Issue warning on module import
warnings.warn(
    "The 'pattern_engine.phase_detector_v2' module is deprecated. "
    "Import from 'pattern_engine.phase_detection' instead. "
    "This module will be removed in v0.3.0.",
    DeprecationWarning,
    stacklevel=2,
)
