"""
Tests for volume validator factory - Story 25.4
"""

import pytest

from src.signal_generator.validators.volume.factory import get_volume_validator
from src.signal_generator.validators.volume.lps_validator import LPSVolumeValidator
from src.signal_generator.validators.volume.sos_validator import SOSVolumeValidator
from src.signal_generator.validators.volume.spring_validator import SpringVolumeValidator
from src.signal_generator.validators.volume.utad_validator import UTADVolumeValidator


def test_factory_returns_spring_validator():
    """Test factory returns SpringVolumeValidator for 'SPRING'."""
    validator = get_volume_validator("SPRING")
    assert isinstance(validator, SpringVolumeValidator)


def test_factory_returns_spring_validator_lowercase():
    """Test factory handles lowercase 'spring'."""
    validator = get_volume_validator("spring")
    assert isinstance(validator, SpringVolumeValidator)


def test_factory_returns_sos_validator():
    """Test factory returns SOSVolumeValidator for 'SOS'."""
    validator = get_volume_validator("SOS")
    assert isinstance(validator, SOSVolumeValidator)


def test_factory_returns_lps_validator():
    """Test factory returns LPSVolumeValidator for 'LPS'."""
    validator = get_volume_validator("LPS")
    assert isinstance(validator, LPSVolumeValidator)


def test_factory_returns_utad_validator():
    """Test factory returns UTADVolumeValidator for 'UTAD'."""
    validator = get_volume_validator("UTAD")
    assert isinstance(validator, UTADVolumeValidator)


def test_factory_handles_whitespace():
    """Test factory strips whitespace from pattern_type."""
    validator = get_volume_validator("  SPRING  ")
    assert isinstance(validator, SpringVolumeValidator)


def test_factory_unknown_type_raises():
    """Test factory raises ValueError for unknown pattern_type."""
    with pytest.raises(ValueError) as exc_info:
        get_volume_validator("unknown_pattern_xyz")

    assert "unknown_pattern_xyz" in str(exc_info.value).lower()
    assert "spring" in str(exc_info.value).lower()  # Mentions expected types


def test_factory_empty_string_raises():
    """Test factory raises ValueError for empty string."""
    with pytest.raises(ValueError):
        get_volume_validator("")


def test_factory_pattern_type_in_error_message():
    """Test error message includes the invalid pattern_type."""
    with pytest.raises(ValueError) as exc_info:
        get_volume_validator("INVALID")

    error_msg = str(exc_info.value)
    assert "INVALID" in error_msg
