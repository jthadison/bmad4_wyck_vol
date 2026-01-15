"""
Volume Validation Strategies Package (Story 18.6.2)

Provides pattern-specific volume validation strategies for:
- Spring: Low volume validation (< 0.7x) - selling exhaustion
- SOS: High volume validation (> 2.0x) - strong buying
- LPS: Moderate volume validation with absorption support
- UTAD: High volume on failure validation

Each strategy implements VolumeValidationStrategy and is registered
with VolumeStrategyRegistry for pattern-type lookups.

Reference: CF-006 from Critical Foundation Refactoring document.

Author: Story 18.6.2
"""

from src.signal_generator.validators.volume.registry import VolumeStrategyRegistry
from src.signal_generator.validators.volume.strategies.lps_volume import (
    LPSVolumeStrategy,
)
from src.signal_generator.validators.volume.strategies.sos_volume import (
    SOSVolumeStrategy,
)
from src.signal_generator.validators.volume.strategies.spring_volume import (
    SpringVolumeStrategy,
)
from src.signal_generator.validators.volume.strategies.utad_volume import (
    UTADVolumeStrategy,
)


def register_all_strategies() -> None:
    """
    Register all volume validation strategies with the registry.

    This function should be called at application startup to ensure
    all pattern-specific strategies are available for validation.

    Registers:
    ----------
    - SpringVolumeStrategy (SPRING)
    - SOSVolumeStrategy (SOS)
    - LPSVolumeStrategy (LPS)
    - UTADVolumeStrategy (UTAD)

    Example:
    --------
    >>> from src.signal_generator.validators.volume.strategies import register_all_strategies
    >>> register_all_strategies()
    >>> # Now strategies are available via registry
    >>> strategy = VolumeStrategyRegistry.get("SPRING")
    """
    VolumeStrategyRegistry.register(SpringVolumeStrategy())
    VolumeStrategyRegistry.register(SOSVolumeStrategy())
    VolumeStrategyRegistry.register(LPSVolumeStrategy())
    VolumeStrategyRegistry.register(UTADVolumeStrategy())


__all__ = [
    "SpringVolumeStrategy",
    "SOSVolumeStrategy",
    "LPSVolumeStrategy",
    "UTADVolumeStrategy",
    "register_all_strategies",
]
