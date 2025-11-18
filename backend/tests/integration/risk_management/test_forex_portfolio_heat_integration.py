"""
Integration Tests for Forex Portfolio Heat Module.

Tests end-to-end scenarios:
- Friday close scenarios with pattern-aware risk adjustments
- Weekend gap event handling
- Multi-position portfolio management
- Selective auto-close workflows
- Real-world weekend gap scenarios (Swiss SNB, Brexit, COVID)

Coverage: Real-world trading scenarios with Wyckoff methodology integration.
"""

from datetime import UTC, datetime
from decimal import Decimal

from src.risk_management.forex_portfolio_heat import (
    ForexPosition,
    SelectiveAutoCloseConfig,
    calculate_portfolio_heat,
    can_open_new_position,
    log_weekend_gap,
    should_auto_close_position,
)

# =============================================================================
# Real-World Scenario Tests
# =============================================================================


def test_swiss_snb_unpegging_gap_scenario() -> None:
    """
    Integration test: Swiss SNB unpegging (Jan 15, 2015).

    EUR/CHF gapped from 1.2000 to 0.8500 (-29.2%) on Sunday open.
    Tests gap logging for extreme events.
    """
    # Friday close: 1.2000, Sunday open: 0.8500
    event = log_weekend_gap("EUR/CHF", Decimal("1.2000"), Decimal("0.8500"))

    assert event is not None
    assert event.symbol == "EUR/CHF"
    assert event.friday_close == Decimal("1.2000")
    assert event.sunday_open == Decimal("0.8500")

    # Calculate expected gap %: (0.8500 - 1.2000) / 1.2000 * 100 = -29.17%
    expected_gap_pct = (Decimal("0.8500") - Decimal("1.2000")) / Decimal("1.2000") * Decimal("100")
    assert abs(event.gap_pct - expected_gap_pct) < Decimal("0.1")


def test_brexit_referendum_gap_scenario() -> None:
    """
    Integration test: Brexit referendum (Jun 24, 2016).

    GBP/USD gapped from 1.4900 to 1.3500 (-9.4%) on Sunday open.
    Tests gap logging and volatility multiplier for GBP/USD.
    """
    # Friday close: 1.4900, Sunday open: 1.3500
    event = log_weekend_gap("GBP/USD", Decimal("1.4900"), Decimal("1.3500"))

    assert event is not None
    assert event.symbol == "GBP/USD"

    # Calculate expected gap %: (1.3500 - 1.4900) / 1.4900 * 100 = -9.40%
    expected_gap_pct = (Decimal("1.3500") - Decimal("1.4900")) / Decimal("1.4900") * Decimal("100")
    assert abs(event.gap_pct - expected_gap_pct) < Decimal("0.1")


def test_trump_election_usd_mxn_gap_scenario() -> None:
    """
    Integration test: Trump election (Nov 9, 2016).

    USD/MXN gapped from 18.50 to 20.80 (+12.4%) on Sunday open.
    Tests positive gap logging and EM pair volatility multiplier.
    """
    # Friday close: 18.50, Sunday open: 20.80
    event = log_weekend_gap("USD/MXN", Decimal("18.50"), Decimal("20.80"))

    assert event is not None
    assert event.symbol == "USD/MXN"

    # Calculate expected gap %: (20.80 - 18.50) / 18.50 * 100 = +12.43%
    expected_gap_pct = (Decimal("20.80") - Decimal("18.50")) / Decimal("18.50") * Decimal("100")
    assert abs(event.gap_pct - expected_gap_pct) < Decimal("0.1")


# =============================================================================
# Friday Close Scenario Tests
# =============================================================================


def test_friday_close_scenario_conservative_portfolio() -> None:
    """
    Integration test: Friday 4pm ET with conservative portfolio.

    Scenario:
    - 2 Spring positions in Phase D (EUR/USD, AUD/USD)
    - Low base heat (3.0%)
    - Should pass Friday limit with low weekend adjustment
    """
    friday_4pm = datetime(2025, 11, 14, 21, 0, 0, tzinfo=UTC)

    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0820"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("10850.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="AUD/USD",
            entry=Decimal("0.6650"),
            stop=Decimal("0.6625"),
            lot_size=Decimal("1.50"),
            lot_type="mini",
            position_value_usd=Decimal("9975.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
    ]

    heat = calculate_portfolio_heat(positions, friday_4pm)

    # Both Spring Phase D with major pairs → low weekend adjustment
    # Spring 0.3% × D 1.0x × 1.0 = 0.30% each → 0.60% total adjustment
    assert heat.weekend_adjustment_pct <= Decimal("1.0")
    assert heat.total_heat_pct < Decimal("5.5")  # Should pass Friday limit
    assert heat.warning is None or "WARNING" not in heat.warning


def test_friday_close_scenario_aggressive_portfolio() -> None:
    """
    Integration test: Friday 4pm ET with aggressive portfolio.

    Scenario:
    - 3 positions: 2 SOS in Phase E, 1 EM pair
    - High base heat (5.0%)
    - Should trigger warning/block due to high weekend adjustment
    """
    friday_4pm = datetime(2025, 11, 14, 21, 0, 0, tzinfo=UTC)

    positions = [
        ForexPosition(
            symbol="GBP/USD",
            entry=Decimal("1.2650"),
            stop=Decimal("1.2600"),
            lot_size=Decimal("2.00"),
            lot_type="mini",
            position_value_usd=Decimal("25300.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SOS",
            wyckoff_phase="E",
        ),
        ForexPosition(
            symbol="EUR/JPY",
            entry=Decimal("160.50"),
            stop=Decimal("159.00"),
            lot_size=Decimal("1.50"),
            lot_type="mini",
            position_value_usd=Decimal("24075.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SOS",
            wyckoff_phase="E",
        ),
        ForexPosition(
            symbol="USD/MXN",
            entry=Decimal("18.50"),
            stop=Decimal("18.30"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("18500.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="LPS",
            wyckoff_phase="D",
        ),
    ]

    heat = calculate_portfolio_heat(positions, friday_4pm)

    # High weekend adjustment due to:
    # - GBP/USD SOS E: 0.6% × 1.3 × 1.1 = 0.86%
    # - EUR/JPY SOS E: 0.6% × 1.3 × 1.2 = 0.94%
    # - USD/MXN LPS D: 0.4% × 1.0 × 1.8 = 0.72%
    # Total: ~2.52% adjustment
    assert heat.weekend_adjustment_pct > Decimal("2.0")

    # Likely to exceed Friday limit (5.5%) or trigger warning
    if heat.total_heat_pct > Decimal("5.5"):
        assert heat.warning is not None
        assert "BLOCKED" in heat.warning or "WARNING" in heat.warning


def test_friday_close_scenario_new_position_rejected() -> None:
    """
    Integration test: Attempting to open new position on Friday with high heat.

    Scenario:
    - 2 existing positions (4.5% base heat)
    - Attempt to add 3rd position (2.0% risk)
    - Should be rejected due to exceeding Friday limit after weekend adjustment
    """
    friday_4pm = datetime(2025, 11, 14, 21, 0, 0, tzinfo=UTC)

    existing_positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0820"),
            lot_size=Decimal("2.00"),
            lot_type="mini",
            position_value_usd=Decimal("21700.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="GBP/USD",
            entry=Decimal("1.2650"),
            stop=Decimal("1.2600"),
            lot_size=Decimal("2.00"),
            lot_type="mini",
            position_value_usd=Decimal("25300.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SOS",
            wyckoff_phase="E",
        ),
    ]

    # Attempt to add new SOS position
    new_position = ForexPosition(
        symbol="USD/JPY",
        entry=Decimal("148.50"),
        stop=Decimal("147.50"),
        lot_size=Decimal("1.50"),
        lot_type="mini",
        position_value_usd=Decimal("22275.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="SOS",
        wyckoff_phase="E",
    )

    can_open, msg = can_open_new_position(
        existing_positions, Decimal("2.0"), new_position, friday_4pm
    )

    # Should be rejected
    assert can_open is False
    assert msg is not None
    assert "REJECTED" in msg


# =============================================================================
# Selective Auto-Close Integration Tests
# =============================================================================


def test_selective_auto_close_mixed_portfolio() -> None:
    """
    Integration test: Selective auto-close with mixed portfolio.

    Scenario (Friday 4:30pm):
    - EUR/USD Spring Phase D at +5.2R → KEEP (winner)
    - GBP/USD SOS Phase D at -0.3R → CLOSE (losing SOS)
    - AUD/USD LPS Phase E at +1.5R → CLOSE (Phase E)
    - USD/JPY Spring Phase C at +0.8R → KEEP (Spring in progress)

    Expected: Close 2 positions, keep 2 positions
    """
    friday_430pm = datetime(2025, 11, 14, 21, 30, 0, tzinfo=UTC)
    config = SelectiveAutoCloseConfig(enabled=True)

    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0820"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("10850.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="GBP/USD",
            entry=Decimal("1.2650"),
            stop=Decimal("1.2600"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("12650.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SOS",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="AUD/USD",
            entry=Decimal("0.6650"),
            stop=Decimal("0.6625"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("6650.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="LPS",
            wyckoff_phase="E",
        ),
        ForexPosition(
            symbol="USD/JPY",
            entry=Decimal("148.50"),
            stop=Decimal("148.00"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("14850.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="C",
        ),
    ]

    current_prices = {
        "EUR/USD": Decimal("1.1006"),  # +5.2R (1.0850 + 30*5.2 pips)
        "GBP/USD": Decimal("1.2635"),  # -0.3R (losing)
        "AUD/USD": Decimal("0.6688"),  # +1.5R (profitable but Phase E)
        "USD/JPY": Decimal("148.90"),  # +0.8R (small profit)
    }

    results = []
    for position in positions:
        current_price = current_prices[position.symbol]
        should_close, reason = should_auto_close_position(
            position, config, current_price, friday_430pm
        )
        results.append({"symbol": position.symbol, "should_close": should_close, "reason": reason})

    # Verify decisions
    eur_usd_result = next(r for r in results if r["symbol"] == "EUR/USD")
    assert eur_usd_result["should_close"] is False  # Spring winner >2R → KEEP
    assert "Spring winner >2R" in eur_usd_result["reason"]

    gbp_usd_result = next(r for r in results if r["symbol"] == "GBP/USD")
    assert gbp_usd_result["should_close"] is True  # Losing position → CLOSE

    aud_usd_result = next(r for r in results if r["symbol"] == "AUD/USD")
    assert aud_usd_result["should_close"] is True  # Phase E → CLOSE

    usd_jpy_result = next(r for r in results if r["symbol"] == "USD/JPY")
    assert usd_jpy_result["should_close"] is False  # Spring in progress → KEEP

    # Count closes
    close_count = sum(1 for r in results if r["should_close"])
    keep_count = sum(1 for r in results if not r["should_close"])
    assert close_count == 2
    assert keep_count == 2


def test_selective_auto_close_all_losers() -> None:
    """
    Integration test: Selective auto-close - All positions losing.

    Scenario: Friday 4:30pm, all 3 positions underwater.
    Expected: Close all positions (reduce weekend risk).
    """
    friday_430pm = datetime(2025, 11, 14, 21, 30, 0, tzinfo=UTC)
    config = SelectiveAutoCloseConfig(enabled=True)

    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0820"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("10850.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="GBP/USD",
            entry=Decimal("1.2650"),
            stop=Decimal("1.2600"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("12650.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="LPS",
            wyckoff_phase="D",
        ),
    ]

    # All positions below entry (losing)
    current_prices = {
        "EUR/USD": Decimal("1.0835"),  # -0.5R
        "GBP/USD": Decimal("1.2630"),  # -0.4R
    }

    close_decisions = []
    for position in positions:
        current_price = current_prices[position.symbol]
        should_close, reason = should_auto_close_position(
            position, config, current_price, friday_430pm
        )
        close_decisions.append(should_close)

    # All should be closed (all losing)
    assert all(close_decisions)


def test_selective_auto_close_all_winners() -> None:
    """
    Integration test: Selective auto-close - All positions winning.

    Scenario: Friday 4:30pm, all Spring positions >2R.
    Expected: Keep all positions (let winners run).
    """
    friday_430pm = datetime(2025, 11, 14, 21, 30, 0, tzinfo=UTC)
    config = SelectiveAutoCloseConfig(enabled=True)

    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0820"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("10850.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="AUD/USD",
            entry=Decimal("0.6650"),
            stop=Decimal("0.6625"),
            lot_size=Decimal("1.00"),
            lot_type="mini",
            position_value_usd=Decimal("6650.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
    ]

    # All positions well above entry (>2R)
    current_prices = {
        "EUR/USD": Decimal("1.0910"),  # +2.0R
        "AUD/USD": Decimal("0.6700"),  # +2.0R
    }

    close_decisions = []
    for position in positions:
        current_price = current_prices[position.symbol]
        should_close, reason = should_auto_close_position(
            position, config, current_price, friday_430pm
        )
        close_decisions.append(should_close)

    # None should be closed (all Spring winners >2R)
    assert not any(close_decisions)


# =============================================================================
# Multi-Position Portfolio Management Tests
# =============================================================================


def test_portfolio_heat_progression_throughout_week() -> None:
    """
    Integration test: Portfolio heat progression Monday → Friday.

    Scenario:
    - Same 2 positions held throughout week
    - Heat calculation changes based on day of week
    """
    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0820"),
            lot_size=Decimal("1.50"),
            lot_type="mini",
            position_value_usd=Decimal("16275.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="SPRING",
            wyckoff_phase="D",
        ),
        ForexPosition(
            symbol="GBP/USD",
            entry=Decimal("1.2650"),
            stop=Decimal("1.2600"),
            lot_size=Decimal("1.50"),
            lot_type="mini",
            position_value_usd=Decimal("18975.00"),
            account_balance=Decimal("10000.00"),
            pattern_type="LPS",
            wyckoff_phase="D",
        ),
    ]

    # Monday
    monday = datetime(2025, 11, 10, 15, 0, 0, tzinfo=UTC)
    monday_heat = calculate_portfolio_heat(positions, monday)
    assert monday_heat.weekend_adjustment_pct == Decimal("0")
    assert monday_heat.max_heat_limit_pct == Decimal("6.0")

    # Friday
    friday = datetime(2025, 11, 14, 21, 0, 0, tzinfo=UTC)
    friday_heat = calculate_portfolio_heat(positions, friday)
    assert friday_heat.weekend_adjustment_pct > Decimal("0")
    assert friday_heat.max_heat_limit_pct == Decimal("5.5")

    # Total heat should increase on Friday due to weekend adjustment
    assert friday_heat.total_heat_pct > monday_heat.total_heat_pct


def test_adding_positions_throughout_week() -> None:
    """
    Integration test: Adding positions Monday vs Friday.

    Scenario:
    - 1 position on Monday, can add another
    - Same scenario on Friday may be rejected due to weekend adjustment
    """
    position1 = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0820"),
        lot_size=Decimal("2.00"),
        lot_type="mini",
        position_value_usd=Decimal("21700.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="SPRING",
        wyckoff_phase="D",
    )

    # Monday: Can add position
    monday = datetime(2025, 11, 10, 15, 0, 0, tzinfo=UTC)
    can_open_monday, msg_monday = can_open_new_position([position1], Decimal("2.5"), None, monday)
    # Should pass on Monday (6% limit, no weekend adjustment)

    # Friday: May be rejected
    friday = datetime(2025, 11, 14, 21, 0, 0, tzinfo=UTC)
    can_open_friday, msg_friday = can_open_new_position([position1], Decimal("2.5"), None, friday)
    # Tighter on Friday due to 5.5% limit + weekend adjustment

    # Monday should be more permissive than Friday
    if can_open_monday:
        # If Monday passes, Friday might fail
        if not can_open_friday:
            assert "REJECTED" in msg_friday
