"""
Simple unit tests for SOS confidence scoring - focused on core functionality.

Tests key scenarios without complex fixture dependencies.
"""


from src.pattern_engine.scoring.sos_confidence_scorer import get_confidence_quality

# Test: get_confidence_quality helper (no dependencies)


def test_get_confidence_quality_excellent():
    """Test EXCELLENT quality range (90-100)."""
    assert get_confidence_quality(100) == "EXCELLENT"
    assert get_confidence_quality(95) == "EXCELLENT"
    assert get_confidence_quality(90) == "EXCELLENT"


def test_get_confidence_quality_strong():
    """Test STRONG quality range (80-89)."""
    assert get_confidence_quality(89) == "STRONG"
    assert get_confidence_quality(85) == "STRONG"
    assert get_confidence_quality(80) == "STRONG"


def test_get_confidence_quality_acceptable():
    """Test ACCEPTABLE quality range (70-79)."""
    assert get_confidence_quality(79) == "ACCEPTABLE"
    assert get_confidence_quality(75) == "ACCEPTABLE"
    assert get_confidence_quality(70) == "ACCEPTABLE"


def test_get_confidence_quality_weak():
    """Test WEAK quality range (0-69)."""
    assert get_confidence_quality(69) == "WEAK"
    assert get_confidence_quality(50) == "WEAK"
    assert get_confidence_quality(0) == "WEAK"
