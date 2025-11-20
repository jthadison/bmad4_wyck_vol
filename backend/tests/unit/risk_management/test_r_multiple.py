"""
Unit tests for R-Multiple validation module.

Tests cover:
- R-multiple calculation formula and Decimal precision
- Minimum R-multiple validation for all pattern types
- Ideal R-multiple warning logic
- Edge case validation (unreasonable R-multiples)
- Division by zero handling
- Validation workflow integration

Author: Story 7.6
"""

from decimal import Decimal

import pytest

from src.risk_management.r_multiple import (
    calculate_r_multiple,
    check_ideal_r_warning,
    validate_minimum_r_multiple,
    validate_r_multiple,
    validate_r_reasonableness,
)


class TestRMultipleCalculation:
    """Test R-multiple calculation formula (AC 1)."""

    def test_basic_calculation(self):
        """Test basic R-multiple calculation: entry=100, stop=95, target=115 -> 3.0R"""
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("115.00")

        r_multiple = calculate_r_multiple(entry, stop, target)

        # R = (115 - 100) / (100 - 95) = 15 / 5 = 3.0
        assert r_multiple == Decimal("3.00")

    def test_high_r_calculation(self):
        """Test entry=50, stop=48, target=60 -> 5.0R"""
        entry = Decimal("50.00")
        stop = Decimal("48.00")
        target = Decimal("60.00")

        r_multiple = calculate_r_multiple(entry, stop, target)

        # R = (60 - 50) / (50 - 48) = 10 / 2 = 5.0
        assert r_multiple == Decimal("5.00")

    def test_decimal_precision_maintained(self):
        """Verify Decimal precision (no floating point drift)"""
        entry = Decimal("100.123456")
        stop = Decimal("98.123456")
        target = Decimal("106.123456")

        r_multiple = calculate_r_multiple(entry, stop, target)

        # R = 6 / 2 = 3.0 (quantized to 2 decimal places)
        assert isinstance(r_multiple, Decimal)
        assert r_multiple == Decimal("3.00")

    def test_division_by_zero_raises_error(self):
        """Test entry == stop raises ValueError (division by zero)"""
        entry = Decimal("100.00")
        stop = Decimal("100.00")  # Same as entry
        target = Decimal("110.00")

        with pytest.raises(ValueError, match="Stop loss cannot equal entry price"):
            calculate_r_multiple(entry, stop, target)

    def test_negative_r_multiple(self):
        """Test negative R-multiple (target < entry) calculates correctly"""
        entry = Decimal("100.00")
        stop = Decimal("95.00")
        target = Decimal("90.00")  # Target below entry (SHORT trade scenario)

        r_multiple = calculate_r_multiple(entry, stop, target)

        # R = (90 - 100) / (100 - 95) = -10 / 5 = -2.0
        assert r_multiple == Decimal("-2.00")


class TestMinimumRValidation:
    """Test minimum R-multiple validation for all pattern types (AC 4, 7)."""

    # Spring tests (minimum 3.0R)
    def test_spring_below_minimum_rejected(self):
        """Spring with R=2.5 rejected (below 3.0 minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.5"), "SPRING")

        assert is_valid is False
        assert "2.5" in reason
        assert "3.0" in reason
        assert "SPRING" in reason

    def test_spring_at_minimum_accepted(self):
        """Spring with R=3.0 accepted (exactly at minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("3.0"), "SPRING")

        assert is_valid is True
        assert reason is None

    def test_spring_above_minimum_accepted(self):
        """Spring with R=4.5 accepted (ideal range)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("4.5"), "SPRING")

        assert is_valid is True
        assert reason is None

    # ST (Secondary Test) tests (minimum 2.5R)
    def test_st_below_minimum_rejected(self):
        """ST with R=2.3 rejected (below 2.5 minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.3"), "ST")

        assert is_valid is False
        assert "2.3" in reason
        assert "2.5" in reason

    def test_st_at_minimum_accepted(self):
        """ST with R=2.5 accepted (exactly at minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.5"), "ST")

        assert is_valid is True
        assert reason is None

    def test_st_above_minimum_with_warning(self):
        """ST with R=3.0 accepted (above min, below ideal 3.5R)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("3.0"), "ST")

        assert is_valid is True
        assert reason is None

    # SOS tests (minimum 2.5R)
    def test_sos_below_minimum_rejected(self):
        """SOS with R=2.3 rejected (below 2.5 minimum) - AC 8"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.3"), "SOS")

        assert is_valid is False
        assert "2.3" in reason
        assert "2.5" in reason
        assert "SOS" in reason

    def test_sos_at_minimum_accepted(self):
        """SOS with R=2.5 accepted (exactly at minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.5"), "SOS")

        assert is_valid is True
        assert reason is None

    # LPS tests (minimum 2.5R)
    def test_lps_below_minimum_rejected(self):
        """LPS with R=2.4 rejected (below 2.5 minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.4"), "LPS")

        assert is_valid is False
        assert "2.4" in reason
        assert "2.5" in reason

    def test_lps_at_minimum_accepted(self):
        """LPS with R=2.5 accepted (exactly at minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("2.5"), "LPS")

        assert is_valid is True
        assert reason is None

    # UTAD tests (minimum 3.5R - SHORT trade)
    def test_utad_below_minimum_rejected(self):
        """UTAD with R=3.3 rejected (below 3.5 minimum for SHORT)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("3.3"), "UTAD")

        assert is_valid is False
        assert "3.3" in reason
        assert "3.5" in reason

    def test_utad_at_minimum_accepted(self):
        """UTAD with R=3.5 accepted (exactly at minimum)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("3.5"), "UTAD")

        assert is_valid is True
        assert reason is None

    def test_utad_above_minimum_with_warning(self):
        """UTAD with R=4.5 accepted (above min 3.5, below ideal 5.0)"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("4.5"), "UTAD")

        assert is_valid is True
        assert reason is None

    def test_unknown_pattern_type_rejected(self):
        """Unknown pattern type rejected with error message"""
        is_valid, reason = validate_minimum_r_multiple(Decimal("3.0"), "UNKNOWN")

        assert is_valid is False
        assert "Unknown pattern type" in reason


class TestIdealRWarning:
    """Test ideal R-multiple warning logic (AC 5)."""

    def test_spring_below_ideal_warning(self):
        """Spring with R=3.5 -> warning (below 4.0 ideal but above 3.0 minimum)"""
        warning = check_ideal_r_warning(Decimal("3.5"), "SPRING")

        assert warning is not None
        assert "3.5" in warning
        assert "4.0" in warning
        assert "SPRING" in warning
        assert "acceptable but suboptimal" in warning

    def test_spring_at_ideal_no_warning(self):
        """Spring with R=4.0 -> no warning (at ideal threshold)"""
        warning = check_ideal_r_warning(Decimal("4.0"), "SPRING")

        assert warning is None

    def test_spring_above_ideal_no_warning(self):
        """Spring with R=4.5 -> no warning (above ideal)"""
        warning = check_ideal_r_warning(Decimal("4.5"), "SPRING")

        assert warning is None

    def test_sos_below_ideal_warning(self):
        """SOS with R=3.0 -> warning (below 3.5 ideal but above 2.5 minimum)"""
        warning = check_ideal_r_warning(Decimal("3.0"), "SOS")

        assert warning is not None
        assert "3.0" in warning
        assert "3.5" in warning

    def test_lps_below_ideal_warning(self):
        """LPS with R=3.0 -> warning (below 3.5 ideal but above 2.5 minimum)"""
        warning = check_ideal_r_warning(Decimal("3.0"), "LPS")

        assert warning is not None
        assert "3.0" in warning
        assert "3.5" in warning

    def test_st_below_ideal_warning(self):
        """ST with R=3.0 -> warning (below 3.5 ideal but above 2.5 minimum)"""
        warning = check_ideal_r_warning(Decimal("3.0"), "ST")

        assert warning is not None
        assert "3.0" in warning
        assert "3.5" in warning

    def test_utad_below_ideal_warning(self):
        """UTAD with R=4.5 -> warning (below 5.0 ideal but above 3.5 minimum)"""
        warning = check_ideal_r_warning(Decimal("4.5"), "UTAD")

        assert warning is not None
        assert "4.5" in warning
        assert "5.0" in warning


class TestEdgeCaseValidation:
    """Test edge case validation for unreasonable R-multiples (AC 6)."""

    def test_spring_exceeds_maximum_rejected(self):
        """Spring with R=15.0 rejected (exceeds 10.0 maximum)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("15.0"), "SPRING")

        assert is_reasonable is False
        assert "15.0" in reason
        assert "10.0" in reason
        assert "unreasonably high" in reason

    def test_spring_at_maximum_accepted(self):
        """Spring with R=10.0 accepted (at maximum boundary)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("10.0"), "SPRING")

        assert is_reasonable is True
        assert reason is None

    def test_sos_exceeds_maximum_rejected(self):
        """SOS with R=10.0 rejected (exceeds 8.0 maximum)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("10.0"), "SOS")

        assert is_reasonable is False
        assert "10.0" in reason
        assert "8.0" in reason

    def test_lps_exceeds_maximum_rejected(self):
        """LPS with R=9.0 rejected (exceeds 8.0 maximum)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("9.0"), "LPS")

        assert is_reasonable is False
        assert "9.0" in reason
        assert "8.0" in reason

    def test_st_exceeds_maximum_rejected(self):
        """ST with R=9.0 rejected (exceeds 8.0 maximum)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("9.0"), "ST")

        assert is_reasonable is False
        assert "9.0" in reason
        assert "8.0" in reason

    def test_utad_exceeds_maximum_rejected(self):
        """UTAD with R=13.0 rejected (exceeds 12.0 maximum)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("13.0"), "UTAD")

        assert is_reasonable is False
        assert "13.0" in reason
        assert "12.0" in reason

    def test_utad_at_maximum_accepted(self):
        """UTAD with R=12.0 accepted (at maximum boundary)"""
        is_reasonable, reason = validate_r_reasonableness(Decimal("12.0"), "UTAD")

        assert is_reasonable is True
        assert reason is None

    def test_extremely_high_r_rejected(self):
        """Extremely small stop distance produces huge R -> rejected"""
        # Entry $100, stop $99.99, target $500
        entry = Decimal("100.00")
        stop = Decimal("99.99")
        target = Decimal("500.00")

        r_multiple = calculate_r_multiple(entry, stop, target)
        # R = 400 / 0.01 = 40000R (extremely unreasonable)

        is_reasonable, reason = validate_r_reasonableness(r_multiple, "SPRING")

        assert is_reasonable is False
        assert "unreasonably high" in reason


class TestUnifiedValidation:
    """Test unified validate_r_multiple function (AC 3)."""

    def test_spring_ideal_r_validation(self):
        """Spring with 4.0R -> IDEAL status"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("120.00"),
            pattern_type="SPRING",
            symbol="AAPL",
        )

        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("4.00")
        assert validation.status == "IDEAL"
        assert validation.rejection_reason is None
        assert validation.warning is None

    def test_spring_acceptable_with_warning(self):
        """Spring with 3.5R -> ACCEPTABLE with warning"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("117.50"),
            pattern_type="SPRING",
        )

        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("3.50")
        assert validation.status == "ACCEPTABLE"
        assert validation.rejection_reason is None
        assert validation.warning is not None
        assert "3.5" in validation.warning
        assert "4.0" in validation.warning

    def test_spring_below_minimum_rejected(self):
        """Spring with 2.5R -> REJECTED"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("112.50"),
            pattern_type="SPRING",
        )

        assert validation.is_valid is False
        assert validation.r_multiple == Decimal("2.50")
        assert validation.status == "REJECTED"
        assert validation.rejection_reason is not None
        assert "2.5" in validation.rejection_reason
        assert "3.0" in validation.rejection_reason

    def test_spring_exceeds_maximum_rejected(self):
        """Spring with unreasonably high R -> REJECTED"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("99.00"),
            target=Decimal("200.00"),
            pattern_type="SPRING",
        )

        # R = 100 / 1 = 100R (exceeds 10.0 max)
        assert validation.is_valid is False
        assert validation.status == "REJECTED"
        assert "unreasonably high" in validation.rejection_reason

    def test_sos_minimum_accepted(self):
        """SOS with exactly 2.5R -> ACCEPTABLE"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("112.50"),
            pattern_type="SOS",
        )

        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("2.50")
        assert validation.status == "ACCEPTABLE"
        assert validation.warning is not None  # Below ideal 3.5R

    def test_sos_rejection_scenario(self):
        """SOS with R=2.3 rejected despite meeting all other criteria (AC 8)"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("111.50"),  # R = 11.5 / 5 = 2.3
            pattern_type="SOS",
            symbol="TEST",
        )

        assert validation.is_valid is False
        assert validation.r_multiple == Decimal("2.30")
        assert validation.status == "REJECTED"
        assert "2.3" in validation.rejection_reason
        assert "2.5" in validation.rejection_reason

    def test_utad_short_ideal(self):
        """UTAD with 5.0R -> IDEAL (SHORT trade)"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("125.00"),
            pattern_type="UTAD",
        )

        assert validation.is_valid is True
        assert validation.r_multiple == Decimal("5.00")
        assert validation.status == "IDEAL"
        assert validation.warning is None

    def test_division_by_zero_handling(self):
        """Division by zero returns REJECTED validation"""
        validation = validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("100.00"),  # Same as entry
            target=Decimal("110.00"),
            pattern_type="SPRING",
        )

        assert validation.is_valid is False
        assert validation.status == "REJECTED"
        assert "division by zero" in validation.rejection_reason.lower()


@pytest.mark.parametrize(
    "pattern_type,r_value,expected_valid,expected_status",
    [
        # Spring tests
        ("SPRING", Decimal("2.5"), False, "REJECTED"),  # Below minimum
        ("SPRING", Decimal("3.0"), True, "ACCEPTABLE"),  # At minimum, below ideal
        ("SPRING", Decimal("3.5"), True, "ACCEPTABLE"),  # Above min, below ideal
        ("SPRING", Decimal("4.0"), True, "IDEAL"),  # At ideal
        ("SPRING", Decimal("4.5"), True, "IDEAL"),  # Above ideal
        # SOS tests
        ("SOS", Decimal("2.3"), False, "REJECTED"),  # Below minimum
        ("SOS", Decimal("2.5"), True, "ACCEPTABLE"),  # At minimum
        ("SOS", Decimal("3.5"), True, "IDEAL"),  # At ideal
        # LPS tests
        ("LPS", Decimal("2.4"), False, "REJECTED"),  # Below minimum
        ("LPS", Decimal("2.5"), True, "ACCEPTABLE"),  # At minimum
        ("LPS", Decimal("3.5"), True, "IDEAL"),  # At ideal
        # ST tests
        ("ST", Decimal("2.3"), False, "REJECTED"),  # Below minimum
        ("ST", Decimal("2.5"), True, "ACCEPTABLE"),  # At minimum
        ("ST", Decimal("3.5"), True, "IDEAL"),  # At ideal
        # UTAD tests
        ("UTAD", Decimal("3.3"), False, "REJECTED"),  # Below minimum
        ("UTAD", Decimal("3.5"), True, "ACCEPTABLE"),  # At minimum
        ("UTAD", Decimal("5.0"), True, "IDEAL"),  # At ideal
    ],
)
def test_parametrized_validation(pattern_type, r_value, expected_valid, expected_status):
    """Parametrized test for all pattern types at various R-multiple thresholds"""
    # Calculate entry/stop/target that produce the desired R-multiple
    # Using fixed entry=100, stop=95 (5 point risk)
    entry = Decimal("100.00")
    stop = Decimal("95.00")
    risk = entry - stop  # 5.00
    reward = r_value * risk
    target = entry + reward

    validation = validate_r_multiple(
        entry=entry, stop=stop, target=target, pattern_type=pattern_type
    )

    assert validation.is_valid == expected_valid
    assert validation.status == expected_status
    assert validation.r_multiple == r_value
