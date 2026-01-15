"""
Volume Validation Strategy Package (Story 18.6.1)

Provides strategy pattern infrastructure for pattern-specific volume validation.
This allows new validators to be added without modifying existing code.

Exports:
--------
- VolumeValidationStrategy: Abstract base class for volume validators
- VolumeStrategyRegistry: Registry for pattern-specific strategies
- ValidationMetadataBuilder: Helper for consistent metadata building
"""

from src.signal_generator.validators.volume.base import VolumeValidationStrategy
from src.signal_generator.validators.volume.helpers import ValidationMetadataBuilder
from src.signal_generator.validators.volume.registry import VolumeStrategyRegistry

__all__ = [
    "VolumeValidationStrategy",
    "VolumeStrategyRegistry",
    "ValidationMetadataBuilder",
]
