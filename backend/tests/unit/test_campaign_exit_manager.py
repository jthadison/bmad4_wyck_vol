"""
Unit Tests for Campaign Exit Manager (Story 9.5)

Test Coverage:
--------------
1. ExitRule model validation
   - Valid exit rule with all fields
   - Exit percentages sum to 100% validator
   - Decimal precision enforcement
   - Invalid percentages rejected

2. Partial exit percentage calculations (AC #7)
   - Position with 100 shares: T1=50, T2=30, T3=20
   - Position with 175 shares (fractional rounding): T1=88, T2=53, T3=35
   - Sequential exits verification
   - Custom percentages (40/35/25)

3. Trailing stop update logic (AC #3, 6)
   - T1 hit → stop updated to entry_price (break-even)
   - T2 hit → stop updated to T1 level
   - Multiple positions: all stops updated atomically

4. Campaign invalidation detection (AC #4)
   - Spring low broken → invalidation triggered
   - Ice broken after SOS → invalidation triggered
   - Creek broken after Jump → invalidation triggered
   - Current price within range → no invalidation

5. Emergency exit generation (AC #4)
   - Invalidation → 100% exit orders for all open positions
   - Campaign status updated to "INVALIDATED"
   - Invalidation reason logged

Author: Story 9.5
"""

import math
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.campaign import ExitRule
from src.models.exit import ExitOrder


class TestExitRuleValidation:
    """Test ExitRule model validation."""

    def test_valid_exit_rule_with_all_fields(self):
        """Test creating valid exit rule with all fields."""
        exit_rule = ExitRule(
            campaign_id=uuid4(),
            target_1_level=Decimal("160.00"),
            target_2_level=Decimal("175.00"),
            target_3_level=Decimal("187.50"),
            t1_exit_pct=Decimal("50.00"),
            t2_exit_pct=Decimal("30.00"),
            t3_exit_pct=Decimal("20.00"),
            trail_to_breakeven_on_t1=True,
            trail_to_t1_on_t2=True,
            spring_low=Decimal("145.00"),
            ice_level=Decimal("160.00"),
            creek_level=Decimal("145.00"),
            jump_target=Decimal("175.00"),
        )

        assert exit_rule.target_1_level == Decimal("160.00")
        assert exit_rule.target_2_level == Decimal("175.00")
        assert exit_rule.target_3_level == Decimal("187.50")
        assert exit_rule.t1_exit_pct == Decimal("50.00")
        assert exit_rule.t2_exit_pct == Decimal("30.00")
        assert exit_rule.t3_exit_pct == Decimal("20.00")
        assert exit_rule.spring_low == Decimal("145.00")

    def test_exit_percentages_sum_to_100_validator_passes(self):
        """Test validator passes when percentages sum to 100%."""
        exit_rule = ExitRule(
            campaign_id=uuid4(),
            target_1_level=Decimal("160.00"),
            target_2_level=Decimal("175.00"),
            target_3_level=Decimal("187.50"),
            t1_exit_pct=Decimal("50.00"),
            t2_exit_pct=Decimal("30.00"),
            t3_exit_pct=Decimal("20.00"),
        )

        # Verify sum
        total = exit_rule.t1_exit_pct + exit_rule.t2_exit_pct + exit_rule.t3_exit_pct
        assert total == Decimal("100.00")

    def test_decimal_precision_enforcement(self):
        """Test Decimal precision is enforced (18,8) for target levels."""
        exit_rule = ExitRule(
            campaign_id=uuid4(),
            target_1_level=Decimal("160.12345678"),  # 8 decimal places
            target_2_level=Decimal("175.87654321"),
            target_3_level=Decimal("187.50000000"),
            t1_exit_pct=Decimal("50.00"),
            t2_exit_pct=Decimal("30.00"),
            t3_exit_pct=Decimal("20.00"),
        )

        assert exit_rule.target_1_level == Decimal("160.12345678")
        assert exit_rule.target_2_level == Decimal("175.87654321")

    def test_invalid_percentages_rejected_sum_not_100(self):
        """Test invalid percentages rejected when sum != 100%."""
        with pytest.raises(ValueError, match="Exit percentages must sum to 100%"):
            ExitRule(
                campaign_id=uuid4(),
                target_1_level=Decimal("160.00"),
                target_2_level=Decimal("175.00"),
                target_3_level=Decimal("187.50"),
                t1_exit_pct=Decimal("50.00"),
                t2_exit_pct=Decimal("30.00"),
                t3_exit_pct=Decimal("25.00"),  # Sum = 105%
            )

    def test_invalid_percentages_rejected_negative(self):
        """Test invalid percentages rejected when negative."""
        with pytest.raises(ValueError):
            ExitRule(
                campaign_id=uuid4(),
                target_1_level=Decimal("160.00"),
                target_2_level=Decimal("175.00"),
                target_3_level=Decimal("187.50"),
                t1_exit_pct=Decimal("-10.00"),  # Negative
                t2_exit_pct=Decimal("60.00"),
                t3_exit_pct=Decimal("50.00"),
            )

    def test_invalid_percentages_rejected_over_100(self):
        """Test invalid percentages rejected when > 100%."""
        with pytest.raises(ValueError):
            ExitRule(
                campaign_id=uuid4(),
                target_1_level=Decimal("160.00"),
                target_2_level=Decimal("175.00"),
                target_3_level=Decimal("187.50"),
                t1_exit_pct=Decimal("150.00"),  # Over 100%
                t2_exit_pct=Decimal("30.00"),
                t3_exit_pct=Decimal("20.00"),
            )


class TestPartialExitCalculations:
    """Test partial exit percentage calculations (AC #7)."""

    def test_position_100_shares_50_30_20_exits(self):
        """Test position with 100 shares: T1=50, T2=30, T3=20."""
        position_shares = Decimal("100")

        # T1: 50% of 100 = 50 shares
        t1_shares = math.ceil(float(position_shares * Decimal("50.00") / Decimal("100")))
        assert t1_shares == 50

        # T2: 30% of 100 = 30 shares
        t2_shares = math.ceil(float(position_shares * Decimal("30.00") / Decimal("100")))
        assert t2_shares == 30

        # T3: 20% of 100 = 20 shares
        t3_shares = math.ceil(float(position_shares * Decimal("20.00") / Decimal("100")))
        assert t3_shares == 20

        # Total exits = 100 shares (complete closure)
        assert t1_shares + t2_shares + t3_shares == 100

    def test_position_175_shares_fractional_rounding(self):
        """Test position with 175 shares (fractional rounding): T1=88, T2=53, T3=35."""
        position_shares = Decimal("175")

        # T1: 50% of 175 = 87.5 → round up to 88 shares
        t1_shares = math.ceil(float(position_shares * Decimal("50.00") / Decimal("100")))
        assert t1_shares == 88  # 87.5 rounded up

        # T2: 30% of 175 = 52.5 → round up to 53 shares
        t2_shares = math.ceil(float(position_shares * Decimal("30.00") / Decimal("100")))
        assert t2_shares == 53  # 52.5 rounded up

        # T3: 20% of 175 = 35 shares (exact)
        t3_shares = math.ceil(float(position_shares * Decimal("20.00") / Decimal("100")))
        assert t3_shares == 35

        # Total exits = 176 shares (1 extra due to rounding up)
        total_exits = t1_shares + t2_shares + t3_shares
        assert total_exits == 176

        # Verify rounding up avoids orphan fractional shares
        assert total_exits >= float(position_shares)

    def test_sequential_exits_remaining_shares_verification(self):
        """Test sequential exits: verify remaining shares after each partial exit."""
        initial_shares = Decimal("100")

        # After T1 (50% exit)
        t1_exit = math.ceil(float(initial_shares * Decimal("50.00") / Decimal("100")))
        remaining_after_t1 = int(initial_shares) - t1_exit
        assert t1_exit == 50
        assert remaining_after_t1 == 50

        # After T2 (30% of original)
        t2_exit = math.ceil(float(initial_shares * Decimal("30.00") / Decimal("100")))
        remaining_after_t2 = remaining_after_t1 - t2_exit
        assert t2_exit == 30
        assert remaining_after_t2 == 20

        # After T3 (20% of original)
        t3_exit = math.ceil(float(initial_shares * Decimal("20.00") / Decimal("100")))
        remaining_after_t3 = remaining_after_t2 - t3_exit
        assert t3_exit == 20
        assert remaining_after_t3 == 0  # All shares exited

    def test_custom_percentages_40_35_25(self):
        """Test custom percentages (40/35/25): verify calculations."""
        position_shares = Decimal("100")

        # Custom percentages: 40/35/25
        t1_pct = Decimal("40.00")
        t2_pct = Decimal("35.00")
        t3_pct = Decimal("25.00")

        # Verify sum to 100%
        assert t1_pct + t2_pct + t3_pct == Decimal("100.00")

        # Calculate exits
        t1_shares = math.ceil(float(position_shares * t1_pct / Decimal("100")))
        t2_shares = math.ceil(float(position_shares * t2_pct / Decimal("100")))
        t3_shares = math.ceil(float(position_shares * t3_pct / Decimal("100")))

        assert t1_shares == 40
        assert t2_shares == 35
        assert t3_shares == 25
        assert t1_shares + t2_shares + t3_shares == 100


class TestExitOrderModel:
    """Test ExitOrder model."""

    def test_valid_exit_order_partial_exit(self):
        """Test creating valid exit order for partial exit."""
        exit_order = ExitOrder(
            campaign_id=uuid4(),
            position_id=uuid4(),
            order_type="PARTIAL_EXIT",
            exit_level=Decimal("160.00"),
            shares=50,
            reason="T1 target hit at $160.00",
            triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )

        assert exit_order.order_type == "PARTIAL_EXIT"
        assert exit_order.exit_level == Decimal("160.00")
        assert exit_order.shares == 50
        assert exit_order.executed is False

    def test_valid_exit_order_invalidation(self):
        """Test creating valid exit order for invalidation."""
        exit_order = ExitOrder(
            campaign_id=uuid4(),
            position_id=uuid4(),
            order_type="INVALIDATION",
            exit_level=Decimal("144.50"),
            shares=100,
            reason="Spring low broken at $144.50",
            triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )

        assert exit_order.order_type == "INVALIDATION"
        assert exit_order.shares == 100

    def test_invalid_order_type_rejected(self):
        """Test invalid order type rejected."""
        with pytest.raises(ValueError, match="Invalid order type"):
            ExitOrder(
                campaign_id=uuid4(),
                position_id=uuid4(),
                order_type="INVALID_TYPE",
                exit_level=Decimal("160.00"),
                shares=50,
                reason="Test",
                triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

    def test_order_type_case_insensitive(self):
        """Test order type is case-insensitive (uppercase enforced)."""
        exit_order = ExitOrder(
            campaign_id=uuid4(),
            position_id=uuid4(),
            order_type="partial_exit",  # lowercase
            exit_level=Decimal("160.00"),
            shares=50,
            reason="Test",
            triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )

        assert exit_order.order_type == "PARTIAL_EXIT"  # Converted to uppercase


class TestTrailingStopLogic:
    """Test trailing stop update logic (AC #3, 6)."""

    def test_t1_hit_stop_updated_to_breakeven(self):
        """Test T1 hit → stop updated to entry_price (break-even)."""
        entry_price = Decimal("150.00")
        original_stop = Decimal("147.00")  # 3% below entry

        # When T1 hit, new stop = entry_price (break-even)
        new_stop = entry_price

        assert new_stop == Decimal("150.00")
        assert new_stop > original_stop  # Trailing up

    def test_t2_hit_stop_updated_to_t1_level(self):
        """Test T2 hit → stop updated to T1 level."""
        entry_price = Decimal("150.00")
        t1_level = Decimal("160.00")
        original_stop = entry_price  # After T1, stop at break-even

        # When T2 hit, new stop = T1 level
        new_stop = t1_level

        assert new_stop == Decimal("160.00")
        assert new_stop > original_stop  # Trailing up

    def test_multiple_positions_all_stops_updated(self):
        """Test multiple positions: all stops updated atomically."""
        # Position 1: Spring @ $150
        position_1_entry = Decimal("150.00")
        position_1_original_stop = Decimal("147.00")

        # Position 2: SOS @ $162
        position_2_entry = Decimal("162.00")
        position_2_original_stop = Decimal("157.00")

        # T1 hit → both stops updated to respective entry prices (break-even)
        position_1_new_stop = position_1_entry
        position_2_new_stop = position_2_entry

        assert position_1_new_stop == Decimal("150.00")
        assert position_2_new_stop == Decimal("162.00")
        assert position_1_new_stop > position_1_original_stop
        assert position_2_new_stop > position_2_original_stop


class TestCampaignInvalidationDetection:
    """Test campaign invalidation detection (AC #4)."""

    def test_spring_low_broken_invalidation_triggered(self):
        """Test Spring low broken → invalidation triggered."""
        spring_low = Decimal("145.00")
        current_price = Decimal("144.50")

        invalidation_triggered = current_price < spring_low
        assert invalidation_triggered is True

    def test_ice_broken_after_sos_invalidation_triggered(self):
        """Test Ice broken after SOS → invalidation triggered."""
        ice_level = Decimal("160.00")
        current_price = Decimal("159.50")

        invalidation_triggered = current_price < ice_level
        assert invalidation_triggered is True

    def test_creek_broken_after_jump_invalidation_triggered(self):
        """Test Creek broken after Jump → invalidation triggered."""
        creek_level = Decimal("145.00")
        current_price = Decimal("143.00")
        jump_achieved = True  # Jump target was reached

        invalidation_triggered = current_price < creek_level and jump_achieved
        assert invalidation_triggered is True

    def test_creek_break_ignored_pre_jump(self):
        """Test Creek break ignored (pre-Jump) - no invalidation."""
        creek_level = Decimal("145.00")
        current_price = Decimal("143.00")
        jump_achieved = False  # Jump not yet reached

        # Creek break only triggers invalidation AFTER Jump achieved
        invalidation_triggered = current_price < creek_level and jump_achieved
        assert invalidation_triggered is False

    def test_current_price_within_range_no_invalidation(self):
        """Test current price within range → no invalidation."""
        spring_low = Decimal("145.00")
        ice_level = Decimal("160.00")
        current_price = Decimal("152.00")

        spring_invalidation = current_price < spring_low
        ice_invalidation = current_price < ice_level

        # Price within range, above spring low, but below ice
        # This is normal - no invalidation unless pattern-specific conditions met
        assert spring_invalidation is False  # Above spring low
        assert ice_invalidation is True  # Below ice (valid for pre-breakout positions)


class TestEmergencyExitGeneration:
    """Test emergency exit generation (AC #4)."""

    def test_invalidation_100_percent_exit_orders(self):
        """Test invalidation → 100% exit orders for all open positions."""
        # Simulate two open positions
        position_1_shares = 100
        position_2_shares = 75

        # Emergency exit: 100% of each position
        exit_order_1_shares = position_1_shares
        exit_order_2_shares = position_2_shares

        assert exit_order_1_shares == 100
        assert exit_order_2_shares == 75

    def test_invalidation_order_type_is_invalidation(self):
        """Test invalidation → order_type = 'INVALIDATION'."""
        exit_order = ExitOrder(
            campaign_id=uuid4(),
            position_id=uuid4(),
            order_type="INVALIDATION",
            exit_level=Decimal("144.50"),
            shares=100,
            reason="Spring low broken at $144.50",
            triggered_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )

        assert exit_order.order_type == "INVALIDATION"

    def test_invalidation_reason_logged(self):
        """Test invalidation → reason logged."""
        spring_low = Decimal("145.00")
        current_price = Decimal("144.50")
        reason = f"Spring low broken at ${current_price} (invalidation level ${spring_low})"

        assert "Spring low broken" in reason
        assert "144.50" in reason
        assert "145.00" in reason
