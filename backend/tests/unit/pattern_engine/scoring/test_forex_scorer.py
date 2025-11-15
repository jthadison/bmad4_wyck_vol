"""
Unit tests for forex_scorer module.

Tests ForexConfidenceScorer class properties and initialization.
Full integration tests with pattern objects will be added when integration
test infrastructure is available.

This test file validates:
- Forex scorer initialization with correct properties
- Class attributes (asset_class, volume_reliability, max_confidence)
- Inheritance from ConfidenceScorer base class
"""


from src.pattern_engine.scoring.forex_scorer import ForexConfidenceScorer
from src.pattern_engine.scoring.stock_scorer import StockConfidenceScorer

# ============================================================================
# FOREX SCORER INITIALIZATION TESTS
# ============================================================================


def test_forex_scorer_initialization():
    """Test ForexConfidenceScorer initializes with correct properties."""
    scorer = ForexConfidenceScorer()

    assert scorer.asset_class == "forex"
    assert scorer.volume_reliability == "LOW"
    assert scorer.max_confidence == 85


def test_forex_scorer_vs_stock_scorer_properties():
    """Test forex scorer has different properties from stock scorer."""
    forex_scorer = ForexConfidenceScorer()
    stock_scorer = StockConfidenceScorer()

    # Asset class different
    assert forex_scorer.asset_class == "forex"
    assert stock_scorer.asset_class == "stock"

    # Volume reliability different
    assert forex_scorer.volume_reliability == "LOW"
    assert stock_scorer.volume_reliability == "HIGH"

    # Max confidence different (85 vs 100)
    assert forex_scorer.max_confidence == 85
    assert stock_scorer.max_confidence == 100


def test_forex_scorer_max_confidence_lower_than_stock():
    """Test forex max confidence is 15 points lower than stock (volume uncertainty discount)."""
    forex_scorer = ForexConfidenceScorer()
    stock_scorer = StockConfidenceScorer()

    # Volume uncertainty discount = 15 points
    volume_uncertainty_discount = stock_scorer.max_confidence - forex_scorer.max_confidence
    assert volume_uncertainty_discount == 15


def test_forex_scorer_repr():
    """Test ForexConfidenceScorer string representation."""
    scorer = ForexConfidenceScorer()

    repr_str = repr(scorer)
    assert "ForexConfidenceScorer" in repr_str
    assert "asset_class=forex" in repr_str
    assert "reliability=LOW" in repr_str
    assert "max_confidence=85" in repr_str


def test_forex_scorer_has_required_methods():
    """Test ForexConfidenceScorer has required abstract methods implemented."""
    scorer = ForexConfidenceScorer()

    # Check methods exist and are callable
    assert hasattr(scorer, "calculate_spring_confidence")
    assert callable(scorer.calculate_spring_confidence)

    assert hasattr(scorer, "calculate_sos_confidence")
    assert callable(scorer.calculate_sos_confidence)


# ============================================================================
# VOLUME RELIABILITY VALIDATION TESTS
# ============================================================================


def test_forex_volume_reliability_is_low():
    """Test forex markets have LOW volume reliability (tick volume only)."""
    scorer = ForexConfidenceScorer()

    assert scorer.volume_reliability == "LOW"

    # LOW reliability means:
    # - Tick volume only (not real institutional volume)
    # - Cannot confirm institutional accumulation/distribution
    # - Volume weight reduced to 10 points (vs 35-40 for stocks)


def test_asset_class_validation():
    """Test asset_class is set correctly for forex."""
    scorer = ForexConfidenceScorer()

    assert scorer.asset_class == "forex"

    # Valid asset classes from base class: stock, forex, futures, crypto
    # Forex is valid
    assert scorer.asset_class in ["stock", "forex", "futures", "crypto"]


# ============================================================================
# MAX CONFIDENCE VALIDATION TESTS
# ============================================================================


def test_max_confidence_cap_at_85():
    """Test max confidence capped at 85 for forex (volume uncertainty discount)."""
    scorer = ForexConfidenceScorer()

    assert scorer.max_confidence == 85

    # 15-point volume uncertainty discount
    # "Pattern valid, but volume confirmation incomplete"


def test_max_confidence_within_valid_range():
    """Test max confidence is within valid range (1-100)."""
    scorer = ForexConfidenceScorer()

    assert 1 <= scorer.max_confidence <= 100
    assert scorer.max_confidence == 85  # Specific forex value


# ============================================================================
# INHERITANCE TESTS
# ============================================================================


def test_forex_scorer_inherits_from_confidence_scorer():
    """Test ForexConfidenceScorer inherits from ConfidenceScorer base class."""
    from src.pattern_engine.base.confidence_scorer import ConfidenceScorer

    scorer = ForexConfidenceScorer()

    assert isinstance(scorer, ConfidenceScorer)


def test_forex_scorer_base_class_initialization():
    """Test base class ConfidenceScorer initialized correctly."""
    scorer = ForexConfidenceScorer()

    # Base class properties should be set
    assert hasattr(scorer, "asset_class")
    assert hasattr(scorer, "volume_reliability")
    assert hasattr(scorer, "max_confidence")

    # Values should match forex requirements
    assert scorer.asset_class == "forex"
    assert scorer.volume_reliability == "LOW"
    assert scorer.max_confidence == 85


# ============================================================================
# DOCUMENTATION TESTS
# ============================================================================


def test_forex_scorer_has_docstring():
    """Test ForexConfidenceScorer class has comprehensive docstring."""
    assert ForexConfidenceScorer.__doc__ is not None
    assert len(ForexConfidenceScorer.__doc__) > 100

    # Should mention tick volume limitations
    assert "tick volume" in ForexConfidenceScorer.__doc__.lower()


def test_calculate_spring_confidence_has_docstring():
    """Test calculate_spring_confidence method has comprehensive docstring."""
    scorer = ForexConfidenceScorer()

    assert scorer.calculate_spring_confidence.__doc__ is not None
    assert len(scorer.calculate_spring_confidence.__doc__) > 100

    # Should mention forex adaptations
    docstring_lower = scorer.calculate_spring_confidence.__doc__.lower()
    assert "forex" in docstring_lower


def test_calculate_sos_confidence_has_docstring():
    """Test calculate_sos_confidence method has comprehensive docstring."""
    scorer = ForexConfidenceScorer()

    assert scorer.calculate_sos_confidence.__doc__ is not None
    assert len(scorer.calculate_sos_confidence.__doc__) > 100

    # Should mention forex adaptations
    docstring_lower = scorer.calculate_sos_confidence.__doc__.lower()
    assert "forex" in docstring_lower


# ============================================================================
# MODULE CONSTANTS TESTS
# ============================================================================


def test_minimum_confidence_constant_exists():
    """Test MINIMUM_CONFIDENCE constant exists in module."""
    from src.pattern_engine.scoring.forex_scorer import MINIMUM_CONFIDENCE

    assert MINIMUM_CONFIDENCE == 70  # Same as stock


# ============================================================================
# COMPARISON TESTS
# ============================================================================


def test_forex_vs_stock_volume_weight_difference():
    """
    Test that forex volume weight is significantly lower than stock.

    This is a conceptual test - the actual weight difference is:
    - Stock: 40pts (spring), 35pts (SOS)
    - Forex: 10pts (spring), 10pts (SOS)

    Difference: 30pts (spring), 25pts (SOS)
    """
    forex_scorer = ForexConfidenceScorer()
    stock_scorer = StockConfidenceScorer()

    # Volume reliability difference
    assert forex_scorer.volume_reliability == "LOW"
    assert stock_scorer.volume_reliability == "HIGH"

    # This results in:
    # - Forex: Volume weight 10pts (pattern consistency only)
    # - Stock: Volume weight 35-40pts (institutional confirmation)


def test_forex_vs_stock_max_confidence_difference():
    """Test forex max confidence is 15 points lower than stock."""
    forex_scorer = ForexConfidenceScorer()
    stock_scorer = StockConfidenceScorer()

    # Max confidence difference
    assert stock_scorer.max_confidence == 100
    assert forex_scorer.max_confidence == 85

    # 15-point "volume uncertainty discount"
    assert stock_scorer.max_confidence - forex_scorer.max_confidence == 15


# ============================================================================
# NOTES ON INTEGRATION TESTING
# ============================================================================

"""
Integration tests with full Spring/SOSBreakout pattern objects require:
1. Complete trading range fixtures with all required fields
2. Spring/SOS models with all required fields (bar_index, creek_reference, etc.)
3. Test/LPS models with all required fields
4. Phase classification fixtures

These tests will be added in integration test suite once pattern detection
infrastructure from Stories 5.x and 6.x is available.

For now, unit tests validate:
- Class initialization and properties (✓)
- Inheritance from base class (✓)
- Method signatures and docstrings (✓)
- Volume reliability and max confidence settings (✓)

Actual scoring logic correctness will be validated through integration tests
using real pattern detection output from spring_detector and sos_detector modules.
"""
