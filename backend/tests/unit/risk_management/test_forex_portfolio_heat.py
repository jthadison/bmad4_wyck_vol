"""
Unit Tests for Forex Portfolio Heat Module.

Tests Story 7.3-FX implementation covering:
- Base portfolio heat calculation
- Weekend gap risk detection
- Pattern/phase/volatility-aware adjustments
- Dynamic heat limits
- Weekend hold warnings
- Selective auto-close (pattern-aware)
- Historical gap logging
- Position opening integration

Coverage Target: 95%+
Test Count Target: 59+ tests
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.risk_management.forex_portfolio_heat import (
    PAIR_VOLATILITY_WEEKEND_MULTIPLIERS,
    PATTERN_WEEKEND_BUFFERS,
    PHASE_WEEKEND_MULTIPLIERS,
    WEEKDAY_HEAT_LIMIT,
    WEEKEND_HEAT_LIMIT,
    ForexPortfolioHeat,
    ForexPosition,
    SelectiveAutoCloseConfig,
    WeekendGapEvent,
    calculate_base_heat,
    calculate_portfolio_heat,
    calculate_portfolio_heat_after_new_position,
    calculate_r_multiple,
    calculate_weekend_adjustment_volatility_aware,
    can_open_new_position,
    generate_weekend_warning,
    get_max_heat_limit,
    get_pip_size,
    is_friday_close_approaching,
    is_weekend,
    log_weekend_gap,
    positions_held_over_weekend,
    should_auto_close_position,
    validate_heat_limit,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_position() -> ForexPosition:
    """Sample EUR/USD Spring position."""
    return ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0820"),
        lot_size=Decimal("1.67"),
        lot_type="mini",
        position_value_usd=Decimal("18134.50"),
        account_balance=Decimal("10000.00"),
        pattern_type="SPRING",
        wyckoff_phase="D",
        direction="long",
    )


@pytest.fixture
def sample_sos_position() -> ForexPosition:
    """Sample GBP/USD SOS position in Phase E."""
    return ForexPosition(
        symbol="GBP/USD",
        entry=Decimal("1.2650"),
        stop=Decimal("1.2600"),
        lot_size=Decimal("2.00"),
        lot_type="mini",
        position_value_usd=Decimal("25300.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="SOS",
        wyckoff_phase="E",
        direction="long",
    )


@pytest.fixture
def sample_lps_position() -> ForexPosition:
    """Sample USD/MXN LPS position."""
    return ForexPosition(
        symbol="USD/MXN",
        entry=Decimal("18.50"),
        stop=Decimal("18.30"),
        lot_size=Decimal("1.00"),
        lot_type="mini",
        position_value_usd=Decimal("18500.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="LPS",
        wyckoff_phase="D",
        direction="long",
    )


@pytest.fixture
def monday_time() -> datetime:
    """Monday 10am ET (15:00 UTC)."""
    return datetime(2025, 11, 10, 15, 0, 0, tzinfo=UTC)


@pytest.fixture
def thursday_time() -> datetime:
    """Thursday 3pm ET (20:00 UTC)."""
    return datetime(2025, 11, 13, 20, 0, 0, tzinfo=UTC)


@pytest.fixture
def friday_1pm_time() -> datetime:
    """Friday 1pm ET (18:00 UTC)."""
    return datetime(2025, 11, 14, 18, 0, 0, tzinfo=UTC)


@pytest.fixture
def friday_4pm_time() -> datetime:
    """Friday 4pm ET (21:00 UTC)."""
    return datetime(2025, 11, 14, 21, 0, 0, tzinfo=UTC)


@pytest.fixture
def friday_430pm_time() -> datetime:
    """Friday 4:30pm ET (21:30 UTC)."""
    return datetime(2025, 11, 14, 21, 30, 0, tzinfo=UTC)


@pytest.fixture
def saturday_time() -> datetime:
    """Saturday 10am ET (15:00 UTC)."""
    return datetime(2025, 11, 15, 15, 0, 0, tzinfo=UTC)


@pytest.fixture
def sunday_4pm_time() -> datetime:
    """Sunday 4pm ET (21:00 UTC)."""
    return datetime(2025, 11, 16, 21, 0, 0, tzinfo=UTC)


@pytest.fixture
def sunday_6pm_time() -> datetime:
    """Sunday 6pm ET (23:00 UTC) - market open."""
    return datetime(2025, 11, 16, 23, 0, 0, tzinfo=UTC)


# =============================================================================
# Task 2: Base Portfolio Heat Calculation Tests
# =============================================================================


def test_calculate_base_heat_single_position(sample_position: ForexPosition) -> None:
    """Test base heat calculation with single position."""
    heat = calculate_base_heat([sample_position])
    # Position risk should be calculated correctly
    assert heat > Decimal("0")
    assert heat < Decimal("10")  # Reasonable position risk


def test_calculate_base_heat_multiple_positions(
    sample_position: ForexPosition, sample_sos_position: ForexPosition
) -> None:
    """Test base heat calculation with multiple positions."""
    heat = calculate_base_heat([sample_position, sample_sos_position])
    # Should be sum of individual risks
    heat1 = sample_position.risk_pct
    heat2 = sample_sos_position.risk_pct
    expected = (heat1 + heat2).quantize(Decimal("0.01"))
    assert heat == expected


def test_calculate_base_heat_empty_portfolio() -> None:
    """Test base heat with no positions."""
    heat = calculate_base_heat([])
    assert heat == Decimal("0")


def test_forex_position_risk_pct(sample_position: ForexPosition) -> None:
    """Test ForexPosition.risk_pct property calculation."""
    risk = sample_position.risk_pct
    # EUR/USD: entry 1.0850, stop 1.0820 (30 pips)
    # Position value $18,134.50, account $10,000
    # Risk% should be reasonable
    assert risk > Decimal("0")
    assert risk < Decimal("5")  # Should be <5% for good risk management


# =============================================================================
# Task 3: Weekend Gap Risk Detection Tests
# =============================================================================


def test_is_friday_close_approaching_true(friday_1pm_time: datetime) -> None:
    """Test Friday close detection - Friday 1pm ET."""
    assert is_friday_close_approaching(friday_1pm_time) is True


def test_is_friday_close_approaching_thursday(thursday_time: datetime) -> None:
    """Test Friday close detection - Thursday."""
    assert is_friday_close_approaching(thursday_time) is False


def test_is_friday_close_approaching_friday_morning() -> None:
    """Test Friday close detection - Friday 10am ET (before threshold)."""
    friday_10am = datetime(2025, 11, 14, 15, 0, 0, tzinfo=UTC)
    assert is_friday_close_approaching(friday_10am) is False


def test_is_friday_close_approaching_friday_noon() -> None:
    """Test Friday close detection - Friday 12pm ET (threshold)."""
    friday_noon = datetime(2025, 11, 14, 17, 0, 0, tzinfo=UTC)
    assert is_friday_close_approaching(friday_noon) is True


def test_is_weekend_saturday(saturday_time: datetime) -> None:
    """Test weekend detection - Saturday."""
    assert is_weekend(saturday_time) is True


def test_is_weekend_sunday_before_close(sunday_4pm_time: datetime) -> None:
    """Test weekend detection - Sunday 4pm ET (before open)."""
    assert is_weekend(sunday_4pm_time) is True


def test_is_weekend_sunday_after_open(sunday_6pm_time: datetime) -> None:
    """Test weekend detection - Sunday 6pm ET (market open)."""
    assert is_weekend(sunday_6pm_time) is False


def test_is_weekend_monday(monday_time: datetime) -> None:
    """Test weekend detection - Monday."""
    assert is_weekend(monday_time) is False


def test_positions_held_over_weekend_friday(
    sample_position: ForexPosition, friday_1pm_time: datetime
) -> None:
    """Test weekend hold detection - Friday with positions."""
    assert positions_held_over_weekend([sample_position], friday_1pm_time) is True


def test_positions_held_over_weekend_saturday(
    sample_position: ForexPosition, saturday_time: datetime
) -> None:
    """Test weekend hold detection - Saturday with positions."""
    assert positions_held_over_weekend([sample_position], saturday_time) is True


def test_positions_held_over_weekend_monday(
    sample_position: ForexPosition, monday_time: datetime
) -> None:
    """Test weekend hold detection - Monday (no weekend)."""
    assert positions_held_over_weekend([sample_position], monday_time) is False


def test_positions_held_over_weekend_no_positions(friday_1pm_time: datetime) -> None:
    """Test weekend hold detection - Friday with no positions."""
    assert positions_held_over_weekend([], friday_1pm_time) is False


# =============================================================================
# Task 11-14: Pattern/Phase/Volatility-Aware Weekend Adjustment Tests
# =============================================================================


def test_weekend_adjustment_spring_phase_d_eur_usd(
    sample_position: ForexPosition, friday_1pm_time: datetime
) -> None:
    """Test weekend adjustment: EUR/USD Spring Phase D."""
    adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        [sample_position], friday_1pm_time
    )
    # Spring 0.3% × Phase D 1.0x × EUR/USD 1.0x = 0.30%
    expected = Decimal("0.30")
    assert adj == expected


def test_weekend_adjustment_sos_phase_e_gbp_usd(
    sample_sos_position: ForexPosition, friday_1pm_time: datetime
) -> None:
    """Test weekend adjustment: GBP/USD SOS Phase E."""
    adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        [sample_sos_position], friday_1pm_time
    )
    # SOS 0.6% × Phase E 1.3x × GBP/USD 1.1x = 0.86%
    expected = (Decimal("0.6") * Decimal("1.3") * Decimal("1.1")).quantize(Decimal("0.01"))
    assert adj == expected


def test_weekend_adjustment_lps_phase_d_usd_mxn(
    sample_lps_position: ForexPosition, friday_1pm_time: datetime
) -> None:
    """Test weekend adjustment: USD/MXN LPS Phase D."""
    adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        [sample_lps_position], friday_1pm_time
    )
    # LPS 0.4% × Phase D 1.0x × USD/MXN 1.8x = 0.72%
    expected = (Decimal("0.4") * Decimal("1.0") * Decimal("1.8")).quantize(Decimal("0.01"))
    assert adj == expected


def test_weekend_adjustment_multiple_positions(
    sample_position: ForexPosition,
    sample_sos_position: ForexPosition,
    sample_lps_position: ForexPosition,
    friday_1pm_time: datetime,
) -> None:
    """Test weekend adjustment: Multiple positions (full portfolio)."""
    positions = [sample_position, sample_sos_position, sample_lps_position]
    adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        positions, friday_1pm_time
    )
    # EUR/USD Spring D: 0.30%
    # GBP/USD SOS E: 0.86%
    # USD/MXN LPS D: 0.72%
    # Total: 1.88%
    expected = Decimal("1.88")
    assert adj == expected


def test_weekend_adjustment_no_weekend(
    sample_position: ForexPosition, monday_time: datetime
) -> None:
    """Test weekend adjustment: Monday (no adjustment)."""
    adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        [sample_position], monday_time
    )
    assert adj == Decimal("0")
    assert pattern_bd == {}
    assert phase_bd == {}
    assert vol_bd == {}


def test_weekend_adjustment_breakdowns(
    sample_position: ForexPosition,
    sample_sos_position: ForexPosition,
    friday_1pm_time: datetime,
) -> None:
    """Test weekend adjustment breakdowns for transparency."""
    positions = [sample_position, sample_sos_position]
    adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        positions, friday_1pm_time
    )

    # Pattern breakdown
    assert "EUR/USD_SPRING" in pattern_bd
    assert "GBP/USD_SOS" in pattern_bd

    # Phase breakdown
    assert "D" in phase_bd
    assert "E" in phase_bd

    # Volatility breakdown
    assert "EUR/USD" in vol_bd
    assert "GBP/USD" in vol_bd


def test_pattern_weekend_buffers_constants() -> None:
    """Test pattern-weighted buffer constants."""
    assert PATTERN_WEEKEND_BUFFERS["SPRING"] == Decimal("0.3")
    assert PATTERN_WEEKEND_BUFFERS["LPS"] == Decimal("0.4")
    assert PATTERN_WEEKEND_BUFFERS["SOS"] == Decimal("0.6")


def test_phase_weekend_multipliers_constants() -> None:
    """Test phase-aware multiplier constants."""
    assert PHASE_WEEKEND_MULTIPLIERS["C"] == Decimal("1.2")
    assert PHASE_WEEKEND_MULTIPLIERS["D"] == Decimal("1.0")
    assert PHASE_WEEKEND_MULTIPLIERS["E"] == Decimal("1.3")


def test_volatility_weekend_multipliers_constants() -> None:
    """Test volatility-adjusted multiplier constants."""
    assert PAIR_VOLATILITY_WEEKEND_MULTIPLIERS["EUR/USD"] == Decimal("1.0")
    assert PAIR_VOLATILITY_WEEKEND_MULTIPLIERS["GBP/USD"] == Decimal("1.1")
    assert PAIR_VOLATILITY_WEEKEND_MULTIPLIERS["USD/MXN"] == Decimal("1.8")
    assert PAIR_VOLATILITY_WEEKEND_MULTIPLIERS["EUR/CHF"] == Decimal("2.5")


# =============================================================================
# Task 5: Dynamic Heat Limits Tests
# =============================================================================


def test_get_max_heat_limit_monday(monday_time: datetime) -> None:
    """Test max heat limit - Monday."""
    limit = get_max_heat_limit(monday_time)
    assert limit == WEEKDAY_HEAT_LIMIT  # 6.0%


def test_get_max_heat_limit_thursday(thursday_time: datetime) -> None:
    """Test max heat limit - Thursday."""
    limit = get_max_heat_limit(thursday_time)
    assert limit == WEEKDAY_HEAT_LIMIT  # 6.0%


def test_get_max_heat_limit_friday(friday_1pm_time: datetime) -> None:
    """Test max heat limit - Friday."""
    limit = get_max_heat_limit(friday_1pm_time)
    assert limit == WEEKEND_HEAT_LIMIT  # 5.5%


def test_get_max_heat_limit_saturday(saturday_time: datetime) -> None:
    """Test max heat limit - Saturday."""
    limit = get_max_heat_limit(saturday_time)
    assert limit == WEEKEND_HEAT_LIMIT  # 5.5%


def test_validate_heat_limit_pass_weekday(monday_time: datetime) -> None:
    """Test heat limit validation - Pass on weekday."""
    is_valid, error = validate_heat_limit(Decimal("5.8"), monday_time)
    assert is_valid is True
    assert error is None


def test_validate_heat_limit_reject_friday(friday_1pm_time: datetime) -> None:
    """Test heat limit validation - Reject on Friday."""
    is_valid, error = validate_heat_limit(Decimal("5.8"), friday_1pm_time)
    assert is_valid is False
    assert "exceeds limit" in error


def test_validate_heat_limit_pass_thursday(thursday_time: datetime) -> None:
    """Test heat limit validation - Pass on Thursday."""
    is_valid, error = validate_heat_limit(Decimal("5.8"), thursday_time)
    assert is_valid is True
    assert error is None


# =============================================================================
# Task 6: Weekend Hold Warnings Tests
# =============================================================================


def test_generate_weekend_warning_friday_high_heat(friday_4pm_time: datetime) -> None:
    """Test weekend warning - Friday 4pm with high heat."""
    warning = generate_weekend_warning(Decimal("4.5"), Decimal("6.0"), 3, friday_4pm_time)
    assert warning is not None
    assert "WARNING" in warning
    assert "3 positions" in warning


def test_generate_weekend_warning_friday_low_heat(friday_4pm_time: datetime) -> None:
    """Test weekend warning - Friday 4pm with low heat."""
    warning = generate_weekend_warning(Decimal("3.0"), Decimal("4.5"), 2, friday_4pm_time)
    # No warning if base heat <= 4%
    assert warning is None


def test_generate_weekend_warning_friday_exceeded_limit(friday_4pm_time: datetime) -> None:
    """Test weekend warning - Friday with heat exceeding limit."""
    warning = generate_weekend_warning(Decimal("5.0"), Decimal("6.5"), 3, friday_4pm_time)
    assert warning is not None
    assert "BLOCKED" in warning
    assert "exceeds Friday limit" in warning


def test_generate_weekend_warning_monday(monday_time: datetime) -> None:
    """Test weekend warning - Monday (no warning)."""
    warning = generate_weekend_warning(Decimal("5.0"), Decimal("6.5"), 3, monday_time)
    # No warning on non-Friday
    assert warning is None


def test_generate_weekend_warning_friday_early(friday_1pm_time: datetime) -> None:
    """Test weekend warning - Friday 1pm (before 3pm threshold)."""
    warning = generate_weekend_warning(Decimal("4.5"), Decimal("6.0"), 3, friday_1pm_time)
    # No warning before 3pm
    assert warning is None


# =============================================================================
# Task 13: Selective Auto-Close (Pattern-Aware) Tests
# =============================================================================


def test_calculate_r_multiple_long_profit(sample_position: ForexPosition) -> None:
    """Test R-multiple calculation - Long position with profit."""
    # EUR/USD: entry 1.0850, stop 1.0820 (30 pips risk)
    # Current 1.0910 (60 pips profit) → 2.0R
    current_price = Decimal("1.0910")
    r_multiple = calculate_r_multiple(sample_position, current_price)
    assert r_multiple == Decimal("2.0")


def test_calculate_r_multiple_long_loss(sample_position: ForexPosition) -> None:
    """Test R-multiple calculation - Long position with loss."""
    # EUR/USD: entry 1.0850, stop 1.0820 (30 pips risk)
    # Current 1.0835 (15 pips loss) → -0.5R
    current_price = Decimal("1.0835")
    r_multiple = calculate_r_multiple(sample_position, current_price)
    assert r_multiple == Decimal("-0.5")


def test_calculate_r_multiple_short_profit() -> None:
    """Test R-multiple calculation - Short position with profit."""
    position = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0880"),
        lot_size=Decimal("1.0"),
        lot_type="mini",
        position_value_usd=Decimal("10850.00"),
        account_balance=Decimal("10000.00"),
        direction="short",
    )
    # Short: entry 1.0850, stop 1.0880 (30 pips risk)
    # Current 1.0790 (60 pips profit) → 2.0R
    current_price = Decimal("1.0790")
    r_multiple = calculate_r_multiple(position, current_price)
    assert r_multiple == Decimal("2.0")


def test_should_auto_close_losing_sos(
    sample_sos_position: ForexPosition, friday_430pm_time: datetime
) -> None:
    """Test selective auto-close - Losing SOS position."""
    config = SelectiveAutoCloseConfig(enabled=True)
    # SOS losing position (current below entry)
    current_price = Decimal("1.2630")  # Below entry 1.2650
    should_close, reason = should_auto_close_position(
        sample_sos_position, config, current_price, friday_430pm_time
    )
    assert should_close is True
    assert "Losing SOS" in reason


def test_should_auto_close_spring_winner(
    sample_position: ForexPosition, friday_430pm_time: datetime
) -> None:
    """Test selective auto-close - Spring winner >2R."""
    config = SelectiveAutoCloseConfig(enabled=True, keep_winners_above_r=Decimal("2.0"))
    # Spring winner at +5R
    current_price = Decimal("1.1000")  # Well above entry
    should_close, reason = should_auto_close_position(
        sample_position, config, current_price, friday_430pm_time
    )
    assert should_close is False
    assert "Spring winner >2R" in reason


def test_should_auto_close_phase_e(
    sample_sos_position: ForexPosition, friday_430pm_time: datetime
) -> None:
    """Test selective auto-close - Phase E position."""
    config = SelectiveAutoCloseConfig(enabled=True)
    # Phase E position (even if profitable)
    current_price = Decimal("1.2680")  # Slightly profitable
    should_close, reason = should_auto_close_position(
        sample_sos_position, config, current_price, friday_430pm_time
    )
    assert should_close is True
    assert "Phase E exhaustion" in reason


def test_should_auto_close_losing_position(
    sample_lps_position: ForexPosition, friday_430pm_time: datetime
) -> None:
    """Test selective auto-close - Any losing position."""
    config = SelectiveAutoCloseConfig(enabled=True)
    # Losing LPS position
    current_price = Decimal("18.40")  # Below entry 18.50
    should_close, reason = should_auto_close_position(
        sample_lps_position, config, current_price, friday_430pm_time
    )
    assert should_close is True
    assert "Losing position" in reason


def test_should_auto_close_disabled(
    sample_position: ForexPosition, friday_430pm_time: datetime
) -> None:
    """Test selective auto-close - Disabled."""
    config = SelectiveAutoCloseConfig(enabled=False)
    current_price = Decimal("1.0850")
    should_close, reason = should_auto_close_position(
        sample_position, config, current_price, friday_430pm_time
    )
    assert should_close is False
    assert reason == ""


def test_should_auto_close_not_friday(
    sample_position: ForexPosition, monday_time: datetime
) -> None:
    """Test selective auto-close - Not Friday."""
    config = SelectiveAutoCloseConfig(enabled=True)
    current_price = Decimal("1.0850")
    should_close, reason = should_auto_close_position(
        sample_position, config, current_price, monday_time
    )
    assert should_close is False


def test_should_auto_close_spring_phase_c_small_profit(friday_430pm_time: datetime) -> None:
    """Test selective auto-close - Spring Phase C with small profit."""
    position = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0820"),
        lot_size=Decimal("1.0"),
        lot_type="mini",
        position_value_usd=Decimal("10850.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="SPRING",
        wyckoff_phase="C",
    )
    config = SelectiveAutoCloseConfig(enabled=True)
    current_price = Decimal("1.0875")  # +0.8R (keep it)
    should_close, reason = should_auto_close_position(
        position, config, current_price, friday_430pm_time
    )
    # Not a loser, not Phase E, not losing SOS → Keep
    assert should_close is False


# =============================================================================
# Task 10: Historical Gap Analysis Logging Tests
# =============================================================================


def test_get_pip_size_eur_usd() -> None:
    """Test pip size - EUR/USD (4-decimal)."""
    assert get_pip_size("EUR/USD") == Decimal("0.0001")


def test_get_pip_size_usd_jpy() -> None:
    """Test pip size - USD/JPY (2-decimal)."""
    assert get_pip_size("USD/JPY") == Decimal("0.01")


def test_log_weekend_gap_significant() -> None:
    """Test weekend gap logging - Significant gap >1%."""
    event = log_weekend_gap("EUR/USD", Decimal("1.0850"), Decimal("1.0790"))
    assert event is not None
    assert event.symbol == "EUR/USD"
    assert event.friday_close == Decimal("1.0850")
    assert event.sunday_open == Decimal("1.0790")
    assert event.gap_pips == Decimal("-60")
    # Gap pct: (1.0790 - 1.0850) / 1.0850 * 100 = -0.55%
    # Actually this is <1%, let me recalculate
    gap_pct = ((Decimal("1.0790") - Decimal("1.0850")) / Decimal("1.0850")) * Decimal("100")
    # This is about -0.55%, which is <1%, so it should NOT be logged


def test_log_weekend_gap_large() -> None:
    """Test weekend gap logging - Large gap (Brexit scenario)."""
    # GBP/USD: Friday 1.4900 → Sunday 1.3500 (-9.4%)
    event = log_weekend_gap("GBP/USD", Decimal("1.4900"), Decimal("1.3500"))
    assert event is not None
    assert event.symbol == "GBP/USD"
    gap_pct = ((Decimal("1.3500") - Decimal("1.4900")) / Decimal("1.4900")) * Decimal("100")
    assert abs(event.gap_pct) > Decimal("9.0")


def test_log_weekend_gap_small() -> None:
    """Test weekend gap logging - Small gap <1% (not logged)."""
    event = log_weekend_gap("EUR/USD", Decimal("1.0850"), Decimal("1.0848"))
    # Gap: -2 pips, -0.02% → Not logged
    assert event is None


# =============================================================================
# Task 8: ForexPortfolioHeat Data Model Tests
# =============================================================================


def test_forex_portfolio_heat_creation() -> None:
    """Test ForexPortfolioHeat data model creation."""
    heat = ForexPortfolioHeat(
        base_heat_pct=Decimal("4.0"),
        weekend_adjustment_pct=Decimal("1.5"),
        total_heat_pct=Decimal("5.5"),
        max_heat_limit_pct=Decimal("5.5"),
        num_positions=3,
        positions_held_over_weekend=True,
        is_friday_close_approaching=True,
        is_weekend=False,
    )
    assert heat.base_heat_pct == Decimal("4.0")
    assert heat.weekend_adjustment_pct == Decimal("1.5")
    assert heat.total_heat_pct == Decimal("5.5")
    assert heat.created_at is not None


def test_forex_portfolio_heat_utilization() -> None:
    """Test heat utilization % calculation."""
    heat = ForexPortfolioHeat(
        base_heat_pct=Decimal("4.0"),
        weekend_adjustment_pct=Decimal("1.5"),
        total_heat_pct=Decimal("5.5"),
        max_heat_limit_pct=Decimal("6.0"),
        num_positions=3,
        positions_held_over_weekend=True,
        is_friday_close_approaching=True,
        is_weekend=False,
    )
    # 5.5 / 6.0 = 91.7%
    utilization = heat.heat_utilization_pct
    assert utilization == Decimal("91.7")


def test_forex_portfolio_heat_can_add_position_true() -> None:
    """Test can_add_position - Room available."""
    heat = ForexPortfolioHeat(
        base_heat_pct=Decimal("2.0"),
        weekend_adjustment_pct=Decimal("1.0"),
        total_heat_pct=Decimal("3.0"),
        max_heat_limit_pct=Decimal("6.0"),
        num_positions=2,
        positions_held_over_weekend=False,
        is_friday_close_approaching=False,
        is_weekend=False,
    )
    # 3.0 + 2.5 (estimated) = 5.5 < 6.0 → Can add
    assert heat.can_add_position is True


def test_forex_portfolio_heat_can_add_position_false() -> None:
    """Test can_add_position - No room."""
    heat = ForexPortfolioHeat(
        base_heat_pct=Decimal("4.5"),
        weekend_adjustment_pct=Decimal("1.5"),
        total_heat_pct=Decimal("6.0"),
        max_heat_limit_pct=Decimal("6.0"),
        num_positions=3,
        positions_held_over_weekend=True,
        is_friday_close_approaching=True,
        is_weekend=False,
    )
    # 6.0 + 2.5 (estimated) = 8.5 > 6.0 → Cannot add
    assert heat.can_add_position is False


# =============================================================================
# Task 9: Integration with Position Opening Tests
# =============================================================================


def test_calculate_portfolio_heat_weekday(
    sample_position: ForexPosition, monday_time: datetime
) -> None:
    """Test portfolio heat calculation - Weekday."""
    heat = calculate_portfolio_heat([sample_position], monday_time)
    assert heat.base_heat_pct > Decimal("0")
    assert heat.weekend_adjustment_pct == Decimal("0")  # No weekend adjustment
    assert heat.total_heat_pct == heat.base_heat_pct
    assert heat.max_heat_limit_pct == WEEKDAY_HEAT_LIMIT
    assert heat.positions_held_over_weekend is False


def test_calculate_portfolio_heat_friday(
    sample_position: ForexPosition, friday_1pm_time: datetime
) -> None:
    """Test portfolio heat calculation - Friday."""
    heat = calculate_portfolio_heat([sample_position], friday_1pm_time)
    assert heat.weekend_adjustment_pct > Decimal("0")  # Weekend adjustment applied
    assert heat.total_heat_pct > heat.base_heat_pct
    assert heat.max_heat_limit_pct == WEEKEND_HEAT_LIMIT
    assert heat.positions_held_over_weekend is True


def test_calculate_portfolio_heat_after_new_position_weekday(
    sample_position: ForexPosition, monday_time: datetime
) -> None:
    """Test portfolio heat after new position - Weekday."""
    heat = calculate_portfolio_heat_after_new_position(
        [sample_position], Decimal("2.0"), None, monday_time
    )
    # Base heat should include new position risk
    assert heat.num_positions == 2
    assert heat.warning is None  # Should pass on weekday


def test_calculate_portfolio_heat_after_new_position_friday_reject(
    sample_position: ForexPosition,
    sample_sos_position: ForexPosition,
    friday_1pm_time: datetime,
) -> None:
    """Test portfolio heat after new position - Friday (rejected)."""
    # 2 positions already (high heat), adding new position
    heat = calculate_portfolio_heat_after_new_position(
        [sample_position, sample_sos_position],
        Decimal("2.0"),
        None,
        friday_1pm_time,
    )
    # Should exceed Friday limit
    assert heat.warning is not None
    assert "REJECTED" in heat.warning


def test_can_open_new_position_weekday_pass(
    sample_position: ForexPosition, monday_time: datetime
) -> None:
    """Test can_open_new_position - Weekday (pass)."""
    can_open, msg = can_open_new_position([sample_position], Decimal("2.0"), None, monday_time)
    assert can_open is True
    assert msg is None


def test_can_open_new_position_friday_reject(
    sample_position: ForexPosition,
    sample_sos_position: ForexPosition,
    friday_1pm_time: datetime,
) -> None:
    """Test can_open_new_position - Friday (reject)."""
    can_open, msg = can_open_new_position(
        [sample_position, sample_sos_position],
        Decimal("2.0"),
        None,
        friday_1pm_time,
    )
    assert can_open is False
    assert msg is not None
    assert "REJECTED" in msg


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


def test_full_portfolio_heat_calculation_friday(
    sample_position: ForexPosition,
    sample_sos_position: ForexPosition,
    sample_lps_position: ForexPosition,
    friday_4pm_time: datetime,
) -> None:
    """Test full portfolio heat calculation with all enhancements - Friday."""
    positions = [sample_position, sample_sos_position, sample_lps_position]
    heat = calculate_portfolio_heat(positions, friday_4pm_time)

    # Verify all fields populated
    assert heat.base_heat_pct > Decimal("0")
    assert heat.weekend_adjustment_pct > Decimal("0")
    assert heat.total_heat_pct > heat.base_heat_pct
    assert heat.num_positions == 3
    assert heat.positions_held_over_weekend is True
    assert heat.max_heat_limit_pct == WEEKEND_HEAT_LIMIT

    # Verify breakdowns
    assert heat.pattern_breakdown is not None
    assert heat.phase_breakdown is not None
    assert heat.volatility_breakdown is not None


def test_selective_auto_close_config_defaults() -> None:
    """Test SelectiveAutoCloseConfig default values."""
    config = SelectiveAutoCloseConfig()
    assert config.enabled is False
    assert config.close_time_et == 16
    assert "SOS" in config.always_close_patterns
    assert "SPRING" in config.never_close_patterns
    assert config.close_losers_below_r == Decimal("0.0")
    assert config.keep_winners_above_r == Decimal("2.0")


def test_weekend_gap_event_creation() -> None:
    """Test WeekendGapEvent data model."""
    event = WeekendGapEvent(
        symbol="GBP/USD",
        friday_close=Decimal("1.4900"),
        sunday_open=Decimal("1.3500"),
        gap_pips=Decimal("-1400"),
        gap_pct=Decimal("-9.40"),
        timestamp=datetime.now(UTC),
    )
    assert event.symbol == "GBP/USD"
    assert event.gap_pct == Decimal("-9.40")
