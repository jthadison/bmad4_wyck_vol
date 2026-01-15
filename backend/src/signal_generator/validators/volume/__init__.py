"""
Volume Validation Strategy Package (Story 18.6.1, 18.6.2)

Provides strategy pattern infrastructure for pattern-specific volume validation.
This allows new validators to be added without modifying existing code.

Exports:
--------
Base Infrastructure (Story 18.6.1):
- VolumeValidationStrategy: Abstract base class for volume validators
- VolumeStrategyRegistry: Registry for pattern-specific strategies
- ValidationMetadataBuilder: Helper for consistent metadata building

Pattern Strategies (Story 18.6.2):
- SpringVolumeStrategy: Low volume validation for Spring patterns
- SOSVolumeStrategy: High volume validation for SOS patterns
- LPSVolumeStrategy: Moderate volume validation for LPS patterns
- UTADVolumeStrategy: High volume validation for UTAD patterns
- register_all_strategies: Register all strategies with registry
"""

from src.signal_generator.validators.volume.base import VolumeValidationStrategy
from src.signal_generator.validators.volume.helpers import ValidationMetadataBuilder
from src.signal_generator.validators.volume.registry import VolumeStrategyRegistry
from src.signal_generator.validators.volume.strategies import (
    LPSVolumeStrategy,
    SOSVolumeStrategy,
    SpringVolumeStrategy,
    UTADVolumeStrategy,
    register_all_strategies,
)

__all__ = [
    # Base infrastructure (Story 18.6.1)
    "VolumeValidationStrategy",
    "VolumeStrategyRegistry",
    "ValidationMetadataBuilder",
    # Pattern strategies (Story 18.6.2)
    "SpringVolumeStrategy",
    "SOSVolumeStrategy",
    "LPSVolumeStrategy",
    "UTADVolumeStrategy",
    "register_all_strategies",
]
