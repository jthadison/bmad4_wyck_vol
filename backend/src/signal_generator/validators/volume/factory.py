"""
Volume Validator Factory - Story 25.4

Provides factory function for retrieving pattern-specific volume validators.

Usage:
------
>>> from src.signal_generator.validators.volume.factory import get_volume_validator
>>> validator = get_volume_validator("SPRING")
>>> result = await validator.validate(context, config)

Author: Story 25.4
"""

from src.signal_generator.validators.volume.base import VolumeValidationStrategy
from src.signal_generator.validators.volume.lps_validator import LPSVolumeValidator
from src.signal_generator.validators.volume.sos_validator import SOSVolumeValidator
from src.signal_generator.validators.volume.spring_validator import SpringVolumeValidator
from src.signal_generator.validators.volume.utad_validator import UTADVolumeValidator


def get_volume_validator(pattern_type: str) -> VolumeValidationStrategy:
    """
    Get pattern-specific volume validator.

    Parameters:
    -----------
    pattern_type : str
        Pattern type identifier (e.g., "SPRING", "SOS", "LPS", "UTAD")
        Case-insensitive.

    Returns:
    --------
    VolumeValidationStrategy
        Concrete validator instance for the pattern type

    Raises:
    -------
    ValueError
        If pattern_type is not recognized (fails loudly to avoid bypassing validation)

    Example:
    --------
    >>> validator = get_volume_validator("spring")
    >>> isinstance(validator, SpringVolumeValidator)
    True

    >>> validator = get_volume_validator("SOS")
    >>> isinstance(validator, SOSVolumeValidator)
    True

    >>> get_volume_validator("unknown")  # doctest: +SKIP
    ValueError: Unknown pattern_type: 'unknown' (expected SPRING, SOS, LPS, or UTAD)
    """
    # Normalize to uppercase and strip whitespace
    normalized = pattern_type.upper().strip()

    if normalized == "SPRING":
        return SpringVolumeValidator()
    elif normalized == "SOS":
        return SOSVolumeValidator()
    elif normalized == "LPS":
        return LPSVolumeValidator()
    elif normalized == "UTAD":
        return UTADVolumeValidator()
    else:
        raise ValueError(
            f"Unknown pattern_type: '{pattern_type}' "
            "(expected SPRING, SOS, LPS, or UTAD)"
        )
