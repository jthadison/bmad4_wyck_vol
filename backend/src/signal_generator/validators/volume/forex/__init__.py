"""
Forex Volume Validation Package (Story 18.6.3)

Provides forex-specific volume validation utilities:
- ForexThresholdAdjuster: Session-aware threshold adjustments

Extracted from volume_validator.py per CF-006.

Author: Story 18.6.3
"""

from src.signal_generator.validators.volume.forex.threshold_adjuster import (
    ForexThresholdAdjuster,
)

__all__ = [
    "ForexThresholdAdjuster",
]
