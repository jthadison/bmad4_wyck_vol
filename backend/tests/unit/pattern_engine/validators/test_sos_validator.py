"""
Unit tests for SOS (Sign of Strength) breakout validator.

Tests volume expansion and spread expansion validation for SOS breakouts.
Enforces FR12: volume < 1.5x = immediate rejection (non-negotiable).

Test Coverage:
--------------
- Task 7: Volume threshold boundary (AC 7)
- Task 8: High volume with narrow spread (AC 8)
- Task 9: Combined validation scenarios (AC 5)
- Task 10: Volume quality classification (AC 2)
- Task 11: Spread quality classification (AC 3, 4)
- Task 13: FR12 logging compliance (AC 6, 10)
- Task 14: Parametrized tests for comprehensive coverage (AC all)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.validators.sos_validator import SOSValidator


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
def validator() -> SOSValidator:
    """Fixture for SOSValidator instance."""
    return SOSValidator()


@pytest.fixture
def sample_bar() -> OHLCVBar:
    """
    Fixture for sample OHLCVBar with SOS breakout characteristics.

    Creates a bar that represents a potential SOS breakout above resistance.
    """
    return OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.50"),
        close=Decimal("154.50"),
        volume=2500000,
        spread=Decimal("5.50"),
        spread_ratio=Decimal("1.5"),  # Default - tests will override
        volume_ratio=Decimal("2.0"),  # Default - tests will override
    )


@pytest.fixture
def correlation_id() -> str:
    """Fixture for correlation ID."""
    return "test-correlation-123"


# -------------------------------------------------------------------------
# Task 7: Unit test for volume threshold boundary (AC 7)
# -------------------------------------------------------------------------


def test_sos_volume_below_threshold_rejects(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test AC 7: 1.4x volume rejects even with perfect spread/close.

    Volume < 1.5x must reject per FR12, regardless of other factors.
    """
    # Arrange: 1.4x volume (below 1.5x threshold)
    volume_ratio = Decimal("1.4")

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        sample_bar, volume_ratio, correlation_id
    )

    # Assert
    assert is_valid is False, "1.4x volume should reject (AC 7)"
    assert rejection_reason is not None
    assert "1.5x" in rejection_reason, "Rejection should mention 1.5x threshold"
    assert "insufficient confirmation" in rejection_reason
    assert "FR12" in rejection_reason, "Rejection should include FR12 compliance marker"


def test_sos_volume_at_threshold_passes(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test volume at exact threshold (1.5x) passes validation.

    Boundary case: volume_ratio = 1.5x should pass.
    """
    # Arrange: 1.5x volume (at threshold)
    volume_ratio = Decimal("1.5")

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        sample_bar, volume_ratio, correlation_id
    )

    # Assert
    assert is_valid is True, "1.5x volume should pass (at threshold)"
    assert rejection_reason is None


def test_sos_volume_above_threshold_passes(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test volume above threshold (1.51x) passes validation.

    Boundary case: volume_ratio = 1.51x should pass.
    """
    # Arrange: 1.51x volume (above threshold)
    volume_ratio = Decimal("1.51")

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        sample_bar, volume_ratio, correlation_id
    )

    # Assert
    assert is_valid is True, "1.51x volume should pass (above threshold)"
    assert rejection_reason is None


def test_sos_volume_boundary_cases(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test volume boundary cases around 1.5x threshold.

    - 1.49x: should reject
    - 1.50x: should pass
    - 1.51x: should pass
    """
    # 1.49x: reject
    is_valid_1_49, _ = validator.validate_sos_volume(
        sample_bar, Decimal("1.49"), correlation_id
    )
    assert is_valid_1_49 is False, "1.49x should reject"

    # 1.50x: pass
    is_valid_1_50, _ = validator.validate_sos_volume(
        sample_bar, Decimal("1.50"), correlation_id
    )
    assert is_valid_1_50 is True, "1.50x should pass"

    # 1.51x: pass
    is_valid_1_51, _ = validator.validate_sos_volume(
        sample_bar, Decimal("1.51"), correlation_id
    )
    assert is_valid_1_51 is True, "1.51x should pass"


# -------------------------------------------------------------------------
# Task 8: Unit test for narrow spread with high volume (AC 8)
# -------------------------------------------------------------------------


def test_high_volume_narrow_spread_reduces_confidence(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test AC 8: 2.5x volume with 0.9x spread (narrow) reduces confidence significantly.

    REVISED: High volume with narrow spread is SUSPICIOUS (not "good").
    This pattern suggests absorption at resistance - smart money selling into breakout.
    """
    # Arrange: 2.5x volume (excellent) + 0.9x spread (narrow/contraction)
    volume_ratio = Decimal("2.5")
    spread_ratio = Decimal("0.9")

    # Act
    is_valid, warning, validation_result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert (AC 8 - REVISED)
    assert is_valid is True, "High volume (2.5x) should pass volume validation"
    # REVISED: Quality should be "suspicious" not "good"
    assert validation_result["quality"] == "suspicious", (
        "High volume with narrow spread should be suspicious (REVISED)"
    )
    assert validation_result["confidence_impact"] in ["low", "low_moderate"]
    assert warning is not None, "Should have warning about narrow spread"
    assert (
        "absorption" in warning.lower() or "selling" in warning.lower()
    ), "Warning should mention absorption or selling"

    # CRITICAL: Narrow spread (0.9x = contraction) is VERY concerning
    # Even with high volume, this suggests distribution/absorption at resistance
    # This is NOT a "good" breakout - it's suspicious


def test_spread_contraction_scenarios(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test spread contraction scenarios with REVISED expectations.

    - 2.0x volume + 0.8x spread: passes but SUSPICIOUS (not good)
    - 2.5x volume + 1.0x spread: passes, SUSPICIOUS (warns about absorption)
    - 2.5x volume + 1.1x spread: passes, ACCEPTABLE WITH WARNING (moderate_reduced confidence)
    - 3.0x volume + 0.9x spread: passes but SUSPICIOUS with warning logged
    """
    # 2.0x volume + 0.8x spread: SUSPICIOUS
    is_valid_1, warning_1, result_1 = validator.validate_sos_breakout(
        sample_bar, Decimal("2.0"), Decimal("0.8"), correlation_id
    )
    assert is_valid_1 is True, "Should pass volume validation"
    assert result_1["quality"] == "suspicious", "Should be suspicious (contraction)"

    # 2.5x volume + 1.0x spread: ACCEPTABLE WITH WARNING (high volume compensates slightly)
    is_valid_2, warning_2, result_2 = validator.validate_sos_breakout(
        sample_bar, Decimal("2.5"), Decimal("1.0"), correlation_id
    )
    assert is_valid_2 is True, "Should pass volume validation"
    assert result_2["quality"] == "acceptable_with_warning", (
        "2.5x volume + 1.0x spread = acceptable with warning (REVISED logic)"
    )
    assert warning_2 is not None, "Should have warning"

    # 2.5x volume + 1.1x spread: ACCEPTABLE WITH WARNING
    is_valid_3, warning_3, result_3 = validator.validate_sos_breakout(
        sample_bar, Decimal("2.5"), Decimal("1.1"), correlation_id
    )
    assert is_valid_3 is True, "Should pass volume validation"
    assert result_3["quality"] == "acceptable_with_warning", (
        "Should be acceptable with warning (narrow but high volume)"
    )
    assert result_3["confidence_impact"] == "moderate_reduced"

    # 3.0x volume + 0.9x spread: SUSPICIOUS
    is_valid_4, warning_4, result_4 = validator.validate_sos_breakout(
        sample_bar, Decimal("3.0"), Decimal("0.9"), correlation_id
    )
    assert is_valid_4 is True, "Should pass volume validation"
    assert result_4["quality"] == "suspicious", "Should be suspicious despite very high volume"


# -------------------------------------------------------------------------
# Task 9: Unit test for combined validation scenarios (AC 5)
# -------------------------------------------------------------------------


def test_high_volume_wide_spread_excellent(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test best case: high volume + wide spread = excellent breakout.

    2.5x volume + 1.8x spread = excellent quality, high confidence.
    """
    # Arrange: 2.5x volume + 1.8x spread
    volume_ratio = Decimal("2.5")
    spread_ratio = Decimal("1.8")

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert
    assert is_valid is True
    assert result["quality"] == "excellent", "Best case should be excellent"
    assert result["confidence_impact"] == "high"
    assert warning is None, "No warnings for best case"


def test_minimum_requirements_acceptable(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test acceptable case: minimum requirements met.

    1.5x volume + 1.2x spread = acceptable quality, standard confidence.
    """
    # Arrange: 1.5x volume + 1.2x spread (minimum requirements)
    volume_ratio = Decimal("1.5")
    spread_ratio = Decimal("1.2")

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert
    assert is_valid is True
    assert result["quality"] == "acceptable", "Minimum requirements should be acceptable"
    assert result["confidence_impact"] == "standard"


def test_low_volume_narrow_spread_suspicious(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test suspicious case: low volume + narrow spread (AC 5).

    1.6x volume + 1.0x spread = suspicious quality, low confidence.
    Likely false breakout.
    """
    # Arrange: 1.6x volume + 1.0x spread
    volume_ratio = Decimal("1.6")
    spread_ratio = Decimal("1.0")

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert
    assert is_valid is True, "Passes minimum volume, but suspicious"
    assert result["quality"] == "suspicious", "Low volume + narrow spread should be suspicious"
    assert result["confidence_impact"] == "low"
    assert warning is not None
    # Warning contains either spread warning or false breakout warning
    assert (
        "false breakout" in warning.lower() or
        "narrow" in warning.lower() or
        "absorption" in warning.lower()
    ), "Warning should mention false breakout, narrow spread, or absorption"


def test_wide_spread_compensates_for_moderate_volume(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test compensation scenario: wide spread compensates for moderate volume.

    1.6x volume + 1.6x spread = good quality, moderate confidence.
    """
    # Arrange: 1.6x volume + 1.6x spread (wide spread compensates)
    volume_ratio = Decimal("1.6")
    spread_ratio = Decimal("1.6")

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert
    assert is_valid is True
    assert result["quality"] == "good", "Wide spread should compensate for moderate volume"
    assert result["confidence_impact"] == "moderate"


# -------------------------------------------------------------------------
# Task 10: Unit test for volume quality classification (AC 2)
# -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "volume_ratio,expected_quality",
    [
        (Decimal("1.3"), "insufficient"),  # Below 1.5x
        (Decimal("1.4"), "insufficient"),  # Below 1.5x
        (Decimal("1.5"), "acceptable"),  # At minimum
        (Decimal("1.8"), "acceptable"),  # Above minimum
        (Decimal("1.99"), "acceptable"),  # Just below ideal
        (Decimal("2.0"), "ideal"),  # AC 2: ideal threshold
        (Decimal("2.3"), "ideal"),  # Within ideal range
        (Decimal("2.49"), "ideal"),  # Just below excellent
        (Decimal("2.5"), "excellent"),  # Excellent breakout
        (Decimal("3.0"), "excellent"),  # Very strong
    ],
)
def test_volume_quality_classification(
    validator: SOSValidator, volume_ratio: Decimal, expected_quality: str
) -> None:
    """
    Test volume quality classification for all ranges (AC 2).

    Quality levels:
    - insufficient: <1.5x
    - acceptable: 1.5x-1.99x
    - ideal: 2.0x-2.49x (AC 2)
    - excellent: >=2.5x
    """
    quality = validator.classify_volume_quality(volume_ratio)
    assert quality == expected_quality, (
        f"Volume {volume_ratio}x should be {expected_quality}, got {quality}"
    )


# -------------------------------------------------------------------------
# Task 11: Unit test for spread quality classification (AC 3, 4)
# -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spread_ratio,expected_quality",
    [
        (Decimal("0.8"), "insufficient"),  # Contraction
        (Decimal("0.9"), "insufficient"),  # Contraction
        (Decimal("1.0"), "narrow"),  # Minimal expansion
        (Decimal("1.1"), "narrow"),  # AC 3: suspect
        (Decimal("1.19"), "narrow"),  # Just below acceptable
        (Decimal("1.2"), "acceptable"),  # AC 4: minimum threshold
        (Decimal("1.4"), "acceptable"),  # Adequate
        (Decimal("1.49"), "acceptable"),  # Just below wide
        (Decimal("1.5"), "wide"),  # Ideal expansion
        (Decimal("2.0"), "wide"),  # Very wide
    ],
)
def test_spread_quality_classification(
    validator: SOSValidator,
    sample_bar: OHLCVBar,
    correlation_id: str,
    spread_ratio: Decimal,
    expected_quality: str,
) -> None:
    """
    Test spread quality classification for all ranges (AC 3, 4).

    Quality levels:
    - insufficient: <1.0x (contraction)
    - narrow: 1.0x-1.19x (AC 3: suspect)
    - acceptable: 1.2x-1.49x (AC 4: minimum threshold)
    - wide: >=1.5x (ideal)
    """
    _, _, quality = validator.validate_sos_spread(sample_bar, spread_ratio, correlation_id)
    assert quality == expected_quality, (
        f"Spread {spread_ratio}x should be {expected_quality}, got {quality}"
    )


# -------------------------------------------------------------------------
# Task 13: Unit test for FR12 logging compliance (AC 6, 10)
# -------------------------------------------------------------------------


def test_volume_rejection_logging(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test AC 6, 10: Volume rejection logging with FR12 compliance.

    AC 10: All rejections logged to audit trail.
    AC 6: Specific threshold violated included in log.

    NOTE: This test verifies rejection reason includes threshold and FR12 marker.
    Structlog outputs are verified manually via captured stdout in test runs.
    """
    # Arrange: 1.3x volume (below threshold)
    volume_ratio = Decimal("1.3")

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        sample_bar, volume_ratio, correlation_id
    )

    # Assert: Rejection occurred
    assert is_valid is False
    assert rejection_reason is not None

    # AC 6: Specific threshold violated in rejection message
    assert "1.5" in rejection_reason, (
        "Rejection reason should include 1.5x threshold (AC 6)"
    )

    # AC 10: FR12 compliance marker in rejection message
    assert "FR12" in rejection_reason, (
        "Rejection reason should include FR12 compliance marker (AC 10)"
    )

    # Verify rejection reason includes key information
    assert "insufficient confirmation" in rejection_reason
    assert "1.3" in rejection_reason or "Volume" in rejection_reason


def test_spread_warning_logging(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test spread warning logging at INFO level.

    Spread warnings are logged at INFO level (not rejections).

    NOTE: This test verifies warning message content.
    Structlog outputs are verified manually via captured stdout in test runs.
    """
    # Arrange: 1.0x spread (narrow)
    spread_ratio = Decimal("1.0")

    # Act
    is_valid, warning, quality = validator.validate_sos_spread(
        sample_bar, spread_ratio, correlation_id
    )

    # Assert: Warning issued but not rejected
    assert is_valid is True, "Spread doesn't reject, only warns"
    assert warning is not None
    assert "narrow" in warning.lower() or "absorption" in warning.lower()
    assert quality == "narrow"


def test_validation_success_logging(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test successful validation logging at INFO level.

    Successful validations are logged at INFO level with quality metrics.

    NOTE: This test verifies validation result structure.
    Structlog outputs are verified manually via captured stdout in test runs.
    """
    # Arrange: 2.2x volume + 1.6x spread (ideal)
    volume_ratio = Decimal("2.2")
    spread_ratio = Decimal("1.6")

    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert: Validation passed
    assert is_valid is True
    assert result["quality"] == "excellent"
    assert result["confidence_impact"] == "high"
    assert result["volume_quality"] == "ideal"
    assert result["spread_quality"] == "wide"


# -------------------------------------------------------------------------
# Task 14: Parametrized tests for comprehensive coverage (AC all)
# -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "volume_ratio,spread_ratio,expected_valid,expected_quality",
    [
        # Rejections (volume < 1.5x)
        (Decimal("1.0"), Decimal("1.5"), False, None),
        (Decimal("1.4"), Decimal("2.0"), False, None),
        # Suspicious (low volume + narrow spread OR high volume + narrow spread)
        (Decimal("1.6"), Decimal("1.0"), True, "suspicious"),
        (Decimal("1.7"), Decimal("1.1"), True, "suspicious"),
        # REVISED: High volume with narrow spread is also SUSPICIOUS
        (Decimal("2.0"), Decimal("1.0"), True, "suspicious"),
        (Decimal("2.5"), Decimal("1.1"), True, "acceptable_with_warning"),  # Not "good"
        # Acceptable (minimum requirements)
        (Decimal("1.5"), Decimal("1.2"), True, "acceptable"),
        (Decimal("1.8"), Decimal("1.3"), True, "acceptable"),
        # Good (wide spread compensates)
        (Decimal("1.6"), Decimal("1.6"), True, "good"),  # Wide spread compensates
        # Excellent (best case: high volume + wide spread)
        (Decimal("2.2"), Decimal("1.5"), True, "excellent"),
        (Decimal("2.8"), Decimal("1.8"), True, "excellent"),
    ],
)
def test_volume_spread_combinations(
    validator: SOSValidator,
    sample_bar: OHLCVBar,
    correlation_id: str,
    volume_ratio: Decimal,
    spread_ratio: Decimal,
    expected_valid: bool,
    expected_quality: str | None,
) -> None:
    """
    Test comprehensive volume and spread combinations with REVISED expectations.

    Covers all quality levels: excellent, good, acceptable, suspicious, rejected.
    """
    # Act
    is_valid, warning, result = validator.validate_sos_breakout(
        sample_bar, volume_ratio, spread_ratio, correlation_id
    )

    # Assert
    assert is_valid == expected_valid, (
        f"Volume {volume_ratio}x + Spread {spread_ratio}x: "
        f"expected valid={expected_valid}, got {is_valid}"
    )

    if expected_valid:
        assert result["quality"] == expected_quality, (
            f"Volume {volume_ratio}x + Spread {spread_ratio}x: "
            f"expected quality={expected_quality}, got {result['quality']}"
        )


# -------------------------------------------------------------------------
# Additional edge cases
# -------------------------------------------------------------------------


def test_get_sos_validation_summary(validator: SOSValidator) -> None:
    """
    Test validation summary helper function (Task 15).

    Validates comprehensive summary structure with volume, spread, and combined metrics.
    """
    # Arrange: 2.2x volume + 1.6x spread
    volume_ratio = Decimal("2.2")
    spread_ratio = Decimal("1.6")

    # Act
    summary = validator.get_sos_validation_summary(volume_ratio, spread_ratio)

    # Assert: Structure
    assert "volume" in summary
    assert "spread" in summary
    assert "combined" in summary

    # Assert: Volume metrics
    assert summary["volume"]["ratio"] == volume_ratio
    assert summary["volume"]["quality"] == "ideal"
    assert summary["volume"]["is_valid"] is True
    assert summary["volume"]["threshold"] == Decimal("1.5")
    assert summary["volume"]["distance_from_threshold"] == Decimal("0.7")

    # Assert: Spread metrics
    assert summary["spread"]["ratio"] == spread_ratio
    assert summary["spread"]["quality"] == "wide"
    assert summary["spread"]["is_valid"] is True
    assert summary["spread"]["threshold"] == Decimal("1.2")
    assert summary["spread"]["distance_from_threshold"] == Decimal("0.4")

    # Assert: Combined metrics
    assert summary["combined"]["overall_quality"] == "excellent"
    assert summary["combined"]["confidence_impact"] == "high"
    assert isinstance(summary["combined"]["warnings"], list)


def test_very_low_volume_rejection(
    validator: SOSValidator, sample_bar: OHLCVBar, correlation_id: str
) -> None:
    """
    Test very low volume (far below threshold) is rejected.

    0.5x volume should be rejected with clear message.
    """
    # Arrange: 0.5x volume (very low)
    volume_ratio = Decimal("0.5")

    # Act
    is_valid, rejection_reason = validator.validate_sos_volume(
        sample_bar, volume_ratio, correlation_id
    )

    # Assert
    assert is_valid is False
    assert rejection_reason is not None
    assert "0.5" in rejection_reason or "0.50" in rejection_reason
    assert "FR12" in rejection_reason
