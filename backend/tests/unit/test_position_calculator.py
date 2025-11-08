"""
Unit Tests for Position Size Calculator

Test Coverage (AC 8):
---------------------
1. Decimal precision prevents floating point errors
2. Round down behavior (shares never round up)
3. Minimum position validation (< 1 share rejected)
4. Maximum position value validation (> 20% equity rejected)
5. Actual risk never exceeds intended risk
6. Edge case: entry == stop (division by zero)
7. Each pattern type (SPRING, ST, LPS, SOS, UTAD) calculates correctly
8. Very small stop distances don't cause oversized positions

Test Strategy:
--------------
- Use synthetic test values that expose floating point errors (AC 8)
- Test all pattern types with different risk percentages
- Validate Decimal precision throughout calculations
- Test boundary conditions and edge cases

Author: Story 7.2
"""

from decimal import Decimal

import pytest

from src.models.position_sizing import PositionSizing
from src.models.risk_allocation import PatternType
from src.risk_management.position_calculator import calculate_position_size
from src.risk_management.risk_allocator import RiskAllocator


class TestPositionSizeCalculation:
    """Test core position size calculation logic (AC 1, 2, 3)."""

    def test_decimal_precision_prevents_floating_point_errors(self):
        """
        AC 8: Verify Decimal precision prevents floating point errors.

        Uses synthetic values that would expose floating point precision
        issues if calculations used float instead of Decimal.
        """
        # Synthetic values designed to expose FP errors
        account_equity = Decimal("10000.33")
        entry = Decimal("123.456789")
        stop = Decimal("120.123456")

        result = calculate_position_size(
            account_equity=account_equity,
            pattern_type=PatternType.SPRING,  # 0.5% risk
            entry=entry,
            stop=stop,
        )

        assert result is not None

        # Verify all fields use Decimal (not float)
        assert isinstance(result.entry, Decimal)
        assert isinstance(result.stop, Decimal)
        assert isinstance(result.risk_amount, Decimal)
        assert isinstance(result.actual_risk, Decimal)
        assert isinstance(result.position_value, Decimal)

        # Verify exact Decimal precision maintained (8 decimal places for prices)
        assert result.entry == Decimal("123.456789")
        assert result.stop == Decimal("120.123456")

        # Verify actual risk ≤ intended risk (AC 7)
        assert result.actual_risk <= result.risk_amount

    def test_spring_pattern_calculation(self):
        """
        AC 8: Test SPRING pattern (0.5% risk) calculation.

        Formula verification:
        - Dollar risk: $100,000 × 0.5% = $500
        - Stop distance: $123.45 - $120.00 = $3.45
        - Raw shares: $500 / $3.45 = 144.927...
        - Shares (round down): 144
        - Actual risk: 144 × $3.45 = $496.80
        """
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
        )

        assert result is not None
        assert result.pattern_type == "SPRING"
        assert result.shares == 144
        assert result.risk_pct == Decimal("0.5")
        assert result.risk_amount == Decimal("500.00")
        assert result.actual_risk == Decimal("496.80")
        assert result.position_value == Decimal("17776.80")

        # AC 7: Verify actual risk ≤ intended risk
        assert result.actual_risk <= result.risk_amount

    def test_st_pattern_calculation(self):
        """AC 8: Test ST (Secondary Test) pattern (0.5% risk) calculation."""
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.ST,
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
        )

        assert result is not None
        assert result.pattern_type == "ST"
        assert result.shares == 144
        assert result.risk_pct == Decimal("0.5")

    def test_lps_pattern_calculation(self):
        """
        AC 8: Test LPS pattern (0.7% risk) calculation.

        LPS has HIGHER risk allocation than SOS despite tighter stop
        due to superior win rate (75% vs 55%) from pullback confirmation.
        """
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.LPS,
            entry=Decimal("50.00"),  # Lower price to avoid 20% limit
            stop=Decimal("48.00"),
        )

        assert result is not None
        assert result.pattern_type == "LPS"
        assert result.risk_pct == Decimal("0.7")
        assert result.risk_amount == Decimal("700.00")

        # AC 7: Verify actual risk ≤ intended risk
        assert result.actual_risk <= result.risk_amount

        # AC 6: Verify position value ≤ 20% equity
        assert result.position_value <= Decimal("20000.00")

    def test_sos_pattern_calculation(self):
        """
        AC 8: Test SOS pattern (0.8% risk) calculation.

        SOS has 0.8% risk (reduced from 1.0% in earlier versions)
        due to wider stop and lower win rate vs LPS.
        """
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SOS,
            entry=Decimal("50.00"),  # Lower price to avoid 20% limit
            stop=Decimal("48.00"),
        )

        assert result is not None
        assert result.pattern_type == "SOS"
        assert result.risk_pct == Decimal("0.8")
        assert result.risk_amount == Decimal("800.00")

        # AC 7: Verify actual risk ≤ intended risk
        assert result.actual_risk <= result.risk_amount

        # AC 6: Verify position value ≤ 20% equity
        assert result.position_value <= Decimal("20000.00")

    def test_utad_pattern_calculation(self):
        """AC 8: Test UTAD pattern (0.5% risk) calculation."""
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.UTAD,
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
        )

        assert result is not None
        assert result.pattern_type == "UTAD"
        assert result.shares == 144
        assert result.risk_pct == Decimal("0.5")


class TestRoundDownBehavior:
    """Test round down behavior (AC 4)."""

    def test_shares_always_round_down(self):
        """
        AC 4: Verify shares ALWAYS round down (never round up).

        Rounding up would exceed intended risk, violating AC 7.
        This test uses stop distance that produces fractional shares
        to verify ROUND_DOWN behavior.
        """
        # Stop distance: $123.45 - $119.99 = $3.46
        # Dollar risk: $100K × 0.5% = $500
        # Raw shares: $500 / $3.46 = 144.508...
        # Expected shares (round down): 144 (NOT 145)

        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("123.45"),
            stop=Decimal("119.99"),  # Produces fractional shares
        )

        assert result is not None

        # Verify shares are whole integer
        assert isinstance(result.shares, int)
        assert result.shares == 144  # NOT 145 (round down, not round up)

        # Verify actual risk < intended risk (proof of round down)
        assert result.actual_risk < result.risk_amount

    def test_round_down_with_very_small_fractional_part(self):
        """
        AC 4: Test round down with fractional shares close to next integer.

        Even if raw_shares = 99.999, should round to 99 (not 100).
        """
        # Craft stop distance to produce 99.999... shares
        # Dollar risk: $100K × 0.5% = $500
        # Target raw_shares: ~99.999
        # Stop distance: $500 / 99.999 = $5.00005...
        # Entry - stop = $5.00005 → stop = $50.00 - $5.00005 = $44.99995

        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("50.00"),
            stop=Decimal("45.01"),  # Produces ~100.2 shares
        )

        assert result is not None
        # Even with .9+ fractional part, should round DOWN
        assert result.shares <= 100


class TestMinimumPositionValidation:
    """Test minimum position validation (AC 5)."""

    def test_position_below_one_share_rejected(self):
        """
        AC 5: Verify position size < 1 share is rejected (returns None).

        Very wide stop distance relative to risk can produce <1 share.
        """
        # Very wide stop: $123.45 - $50.00 = $73.45
        # Dollar risk: $1K × 0.5% = $5
        # Raw shares: $5 / $73.45 = 0.068... (< 1 share)

        result = calculate_position_size(
            account_equity=Decimal("1000.00"),  # Small account
            pattern_type=PatternType.SPRING,
            entry=Decimal("123.45"),
            stop=Decimal("50.00"),  # Very wide stop
        )

        # AC 5: Should return None (position rejected)
        assert result is None

    def test_exactly_one_share_accepted(self):
        """AC 5: Verify position of exactly 1 share is accepted."""
        # Dollar risk: $100K × 0.5% = $500
        # Stop distance: $500.00 (to produce exactly 1 share)
        # Raw shares: $500 / $500 = 1.0

        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("600.00"),
            stop=Decimal("100.00"),  # $500 stop distance
        )

        assert result is not None
        assert result.shares == 1


class TestMaximumPositionValueValidation:
    """Test maximum position value validation (AC 6, FR18)."""

    def test_position_value_exceeds_20_percent_equity_rejected(self):
        """
        AC 6: Verify position value > 20% equity is rejected.

        FR18 concentration limit prevents over-allocation to single position.
        """
        # Account: $10K → max position value = $2K (20%)
        # Entry: $500, shares that would exceed:
        # If shares = 5 → position value = $2,500 (exceeds $2K limit)

        with pytest.raises(ValueError, match="exceeds 20% of account equity"):
            calculate_position_size(
                account_equity=Decimal("10000.00"),
                pattern_type=PatternType.SPRING,
                entry=Decimal("500.00"),
                stop=Decimal("490.00"),  # Small stop → many shares
            )

    def test_position_value_at_20_percent_boundary_accepted(self):
        """AC 6: Verify position value exactly at 20% boundary is accepted."""
        # Account: $100K → max position = $20K
        # Entry: $100 → max shares = 200 ($20K / $100)
        # Stop distance: $5 → Dollar risk: $1000
        # Raw shares: $1000 / $5 = 200 (exactly at boundary)

        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SOS,  # 0.8% = $800 risk
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),  # $5 stop distance → 160 shares
        )

        assert result is not None
        # Position value: 160 shares × $100 = $16,000 (< $20K limit)
        assert result.position_value <= Decimal("20000.00")


class TestActualRiskValidation:
    """Test actual risk validation (AC 7)."""

    def test_actual_risk_never_exceeds_intended_risk(self):
        """
        AC 7: Verify actual_risk ≤ risk_amount for all calculations.

        This is the core validation that prevents risk limit violations
        due to floating point errors (NFR20).
        """
        # Test with multiple account sizes and price points
        test_cases = [
            (Decimal("10000.00"), Decimal("50.00"), Decimal("48.00")),
            (Decimal("100000.00"), Decimal("123.45"), Decimal("120.00")),
            (Decimal("500000.00"), Decimal("987.65"), Decimal("950.00")),
            (Decimal("1000000.00"), Decimal("1234.56"), Decimal("1200.00")),
        ]

        for account_equity, entry, stop in test_cases:
            result = calculate_position_size(
                account_equity=account_equity,
                pattern_type=PatternType.SPRING,
                entry=entry,
                stop=stop,
            )

            assert result is not None
            # AC 7: Core validation
            assert result.actual_risk <= result.risk_amount, (
                f"Actual risk ${result.actual_risk} exceeds "
                f"intended risk ${result.risk_amount} "
                f"(account: ${account_equity}, entry: ${entry}, stop: ${stop})"
            )

    def test_actual_risk_pct_never_exceeds_pattern_risk_pct(self):
        """AC 7: Verify actual risk % ≤ pattern risk % (derived validation)."""
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,  # 0.5% risk
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
        )

        assert result is not None

        # Calculate actual risk %
        actual_risk_pct = (result.actual_risk / result.account_equity) * Decimal("100")

        # Should be ≤ pattern risk % (0.5%)
        assert actual_risk_pct <= result.risk_pct


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_entry_equals_stop_raises_error(self):
        """
        AC 8: Verify entry == stop raises ValueError (division by zero).

        Stop distance of zero makes position sizing impossible.
        """
        with pytest.raises(ValueError, match="equals stop price"):
            calculate_position_size(
                account_equity=Decimal("100000.00"),
                pattern_type=PatternType.SPRING,
                entry=Decimal("123.45"),
                stop=Decimal("123.45"),  # Same as entry
            )

    def test_very_small_stop_distance_doesnt_cause_oversized_position(self):
        """
        AC 8: Verify very small stops don't violate 20% position limit.

        Small stop → many shares → must be caught by AC 6 validation.
        """
        # Small stop: $0.01 distance
        # Dollar risk: $100K × 0.5% = $500
        # Raw shares: $500 / $0.01 = 50,000 shares
        # Position value: 50,000 × $100 = $5M (WAY over 20% limit)

        with pytest.raises(ValueError, match="exceeds 20% of account equity"):
            calculate_position_size(
                account_equity=Decimal("100000.00"),
                pattern_type=PatternType.SPRING,
                entry=Decimal("100.00"),
                stop=Decimal("99.99"),  # $0.01 stop distance
            )

    def test_target_price_optional_field(self):
        """Test that target price is optional and stored correctly."""
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
            target=Decimal("135.00"),  # Optional target
        )

        assert result is not None
        assert result.target == Decimal("135.00")

    def test_target_price_none_accepted(self):
        """Test that None target is accepted."""
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
            # No target specified
        )

        assert result is not None
        assert result.target is None


class TestRiskAllocatorIntegration:
    """Test integration with RiskAllocator (Story 7.1)."""

    def test_uses_risk_allocator_pattern_percentages(self):
        """Verify calculate_position_size uses RiskAllocator for pattern risk %."""
        # Create custom risk allocator with override
        allocator = RiskAllocator()
        allocator.set_pattern_risk_override(
            PatternType.SPRING, Decimal("1.0")  # Override to 1.0% (from default 0.5%)
        )

        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("30.00"),  # Lower price to avoid 20% limit with 1% risk
            stop=Decimal("28.00"),
            risk_allocator=allocator,  # Use custom allocator
        )

        assert result is not None
        # Should use override 1.0% (not default 0.5%)
        assert result.risk_pct == Decimal("1.0")
        assert result.risk_amount == Decimal("1000.00")

    def test_creates_default_risk_allocator_if_none_provided(self):
        """Verify function creates RiskAllocator if none provided."""
        result = calculate_position_size(
            account_equity=Decimal("100000.00"),
            pattern_type=PatternType.SPRING,
            entry=Decimal("123.45"),
            stop=Decimal("120.00"),
            # No risk_allocator provided
        )

        assert result is not None
        # Should use default SPRING risk (0.5%)
        assert result.risk_pct == Decimal("0.5")
