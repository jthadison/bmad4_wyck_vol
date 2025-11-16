"""
Integration Tests for Forex Position Sizing with Wyckoff Methodology.

Tests cover 6 end-to-end scenarios:
1. EUR/USD Spring with climactic volume and London/NY overlap
2. USD/JPY SOS with weak volume and Asian session
3. GBP/USD LPS with adequate volume and London session
4. Spring pattern stop validation rejection (too tight)
5. SOS pattern stop validation rejection (too wide)
6. Over-leveraged position rejection

Author: Story 7.2-FX
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.src.risk_management.forex_position_sizer import (
    ForexPositionSize,
    adjust_stop_for_spread,
    calculate_forex_lot_size_with_wyckoff_adjustments,
    calculate_pip_value,
    calculate_required_margin,
    calculate_stop_pips_with_spread,
    get_forex_session_multiplier,
    get_forex_volume_multiplier,
    validate_forex_position,
)


class TestEURUSDSpringIntegration:
    """
    Integration Test 1: EUR/USD Spring with climactic volume and London/NY overlap.

    Scenario:
    - Account: $10,000
    - Pattern: Spring (0.5% base risk)
    - Symbol: EUR/USD
    - Entry: 1.0850
    - Structural stop: 1.0820 (30 pips)
    - Tick volume: 2500 (avg 1000) → 2.5x ratio → 1.00x multiplier
    - Session: London/NY overlap (14:00 UTC) → 1.00x multiplier
    - Spread: 1.5 pips → +0.75 pip buffer

    Expected:
    - Effective risk: 0.5% × 1.00 × 1.00 = 0.5% = $50
    - Stop pips: 30 + 0.75 = 30.75 pips
    - Lot size: $50 / (30.75 × $1) ≈ 1.62 mini lots
    - Margin: ~$350 (well under 50% limit)
    """

    def test_eur_usd_spring_full_wyckoff_integration(self) -> None:
        """Test complete EUR/USD Spring with all Wyckoff adjustments."""
        # Setup
        account_balance = Decimal("10000.00")
        pattern_type = "SPRING"
        entry = Decimal("1.0850")
        structural_stop = Decimal("1.0820")
        symbol = "EUR/USD"
        tick_volume = 2500
        avg_tick_volume = 1000
        signal_timestamp = datetime(2025, 11, 16, 14, 0, tzinfo=UTC)  # London/NY overlap
        leverage = Decimal("50")

        # Calculate spread-adjusted stop
        stop_pips = calculate_stop_pips_with_spread(
            entry, structural_stop, symbol, "long"
        )
        assert stop_pips >= Decimal("30.0")
        assert stop_pips <= Decimal("31.0")

        # Calculate pip value
        pip_value = calculate_pip_value(symbol, "mini", "USD")
        assert pip_value == Decimal("1.00")

        # Verify volume multiplier
        volume_mult = get_forex_volume_multiplier(tick_volume, avg_tick_volume)
        assert volume_mult == Decimal("1.00")  # Climactic (2.5x)

        # Verify session multiplier
        session_mult = get_forex_session_multiplier(symbol, signal_timestamp)
        assert session_mult == Decimal("1.00")  # London/NY overlap

        # Calculate lot size with Wyckoff adjustments
        lot_size, details = calculate_forex_lot_size_with_wyckoff_adjustments(
            account_balance=account_balance,
            pattern_type=pattern_type,
            stop_loss_pips=stop_pips,
            pip_value_per_lot=pip_value,
            tick_volume=tick_volume,
            avg_tick_volume=avg_tick_volume,
            signal_timestamp=signal_timestamp,
            symbol=symbol,
            lot_type="mini",
        )

        # Verify lot size
        assert lot_size >= Decimal("1.60")
        assert lot_size <= Decimal("1.70")

        # Verify adjustment details
        assert details["base_risk_percent"] == "0.5"
        assert details["volume_multiplier"] == "1.00"
        assert details["session_multiplier"] == "1.00"
        assert details["effective_risk_percent"] == "0.5"

        # Calculate margin
        exchange_rates = {symbol: entry}
        required_margin = calculate_required_margin(
            lot_size, "mini", symbol, leverage, exchange_rates
        )
        assert required_margin >= Decimal("300.00")
        assert required_margin <= Decimal("400.00")

        # Validate position
        is_valid, error = validate_forex_position(
            stop_pips=stop_pips,
            required_margin=required_margin,
            available_margin=account_balance,
            position_units=int(lot_size * Decimal("10000")),
            pattern_type=pattern_type,
            symbol=symbol,
        )
        assert is_valid is True
        assert error is None


class TestUSDJPYSOSIntegration:
    """
    Integration Test 2: USD/JPY SOS with weak volume and Asian session.

    Scenario:
    - Account: $10,000
    - Pattern: SOS (0.8% base risk)
    - Symbol: USD/JPY
    - Entry: 148.50
    - Structural stop: 147.00 (150 pips)
    - Tick volume: 1200 (avg 1000) → 1.2x ratio → 0.70x multiplier
    - Session: Asian (03:00 UTC) → 0.75x multiplier
    - Spread: 1.0 pip → +0.5 pip buffer

    Expected:
    - Effective risk: 0.8% × 0.70 × 0.75 = 0.42% = $42
    - Stop pips: 150 + 0.5 = 150.5 pips
    - Pip value: ~$0.67/pip (mini lot, varies with rate)
    - Lot size: $42 / (150.5 × $0.67) ≈ 0.41 mini lots
    """

    def test_usd_jpy_sos_reduced_wyckoff_integration(self) -> None:
        """Test USD/JPY SOS with reduced volume and Asian session."""
        # Setup
        account_balance = Decimal("10000.00")
        pattern_type = "SOS"
        entry = Decimal("148.50")
        structural_stop = Decimal("147.00")
        symbol = "USD/JPY"
        tick_volume = 1200
        avg_tick_volume = 1000
        signal_timestamp = datetime(2025, 11, 16, 3, 0, tzinfo=UTC)  # Asian session
        leverage = Decimal("50")

        # Calculate spread-adjusted stop
        stop_pips = calculate_stop_pips_with_spread(
            entry, structural_stop, symbol, "long"
        )
        assert stop_pips >= Decimal("150.0")
        assert stop_pips <= Decimal("151.0")

        # Calculate pip value (USD/JPY varies with rate)
        exchange_rates = {symbol: entry}
        pip_value = calculate_pip_value(symbol, "mini", "USD", exchange_rates)
        assert pip_value >= Decimal("0.60")
        assert pip_value <= Decimal("0.70")

        # Verify volume multiplier
        volume_mult = get_forex_volume_multiplier(tick_volume, avg_tick_volume)
        assert volume_mult == Decimal("0.70")  # Weak (1.2x)

        # Verify session multiplier
        session_mult = get_forex_session_multiplier(symbol, signal_timestamp)
        assert session_mult == Decimal("0.75")  # Asian session

        # Calculate lot size with Wyckoff adjustments
        lot_size, details = calculate_forex_lot_size_with_wyckoff_adjustments(
            account_balance=account_balance,
            pattern_type=pattern_type,
            stop_loss_pips=stop_pips,
            pip_value_per_lot=pip_value,
            tick_volume=tick_volume,
            avg_tick_volume=avg_tick_volume,
            signal_timestamp=signal_timestamp,
            symbol=symbol,
            lot_type="mini",
        )

        # Verify lot size is reduced due to weak volume and Asian session
        assert lot_size >= Decimal("0.35")
        assert lot_size <= Decimal("0.50")

        # Verify adjustment details
        assert details["base_risk_percent"] == "0.8"
        assert details["volume_multiplier"] == "0.70"
        assert details["session_multiplier"] == "0.75"
        # 0.8 × 0.70 × 0.75 = 0.42
        assert Decimal(details["effective_risk_percent"]) == Decimal("0.42")


class TestGBPUSDLPSIntegration:
    """
    Integration Test 3: GBP/USD LPS with adequate volume and London session.

    Scenario:
    - Account: $25,000
    - Pattern: LPS (0.7% base risk)
    - Symbol: GBP/USD
    - Entry: 1.2650
    - Structural stop: 1.2600 (50 pips)
    - Tick volume: 1500 (avg 1000) → 1.5x ratio → 0.75x multiplier
    - Session: London only (10:00 UTC) → 0.90x multiplier
    - Spread: 2.0 pips → +1.0 pip buffer

    Expected:
    - Effective risk: 0.7% × 0.75 × 0.90 = 0.4725% ≈ $118
    - Stop pips: 50 + 1.0 = 51.0 pips
    - Lot size: $118 / (51 × $1) ≈ 2.31 mini lots
    """

    def test_gbp_usd_lps_adequate_wyckoff_integration(self) -> None:
        """Test GBP/USD LPS with adequate volume and London session."""
        # Setup
        account_balance = Decimal("25000.00")
        pattern_type = "LPS"
        entry = Decimal("1.2650")
        structural_stop = Decimal("1.2600")
        symbol = "GBP/USD"
        tick_volume = 1500
        avg_tick_volume = 1000
        signal_timestamp = datetime(2025, 11, 16, 10, 0, tzinfo=UTC)  # London only
        leverage = Decimal("50")

        # Calculate spread-adjusted stop
        stop_pips = calculate_stop_pips_with_spread(
            entry, structural_stop, symbol, "long"
        )
        assert stop_pips == Decimal("51.0")  # 50 + 1.0 spread adjustment

        # Calculate pip value
        pip_value = calculate_pip_value(symbol, "mini", "USD")
        assert pip_value == Decimal("1.00")

        # Verify volume multiplier
        volume_mult = get_forex_volume_multiplier(tick_volume, avg_tick_volume)
        assert volume_mult == Decimal("0.75")  # Adequate (1.5x)

        # Verify session multiplier
        session_mult = get_forex_session_multiplier(symbol, signal_timestamp)
        assert session_mult == Decimal("0.90")  # London only

        # Calculate lot size with Wyckoff adjustments
        lot_size, details = calculate_forex_lot_size_with_wyckoff_adjustments(
            account_balance=account_balance,
            pattern_type=pattern_type,
            stop_loss_pips=stop_pips,
            pip_value_per_lot=pip_value,
            tick_volume=tick_volume,
            avg_tick_volume=avg_tick_volume,
            signal_timestamp=signal_timestamp,
            symbol=symbol,
            lot_type="mini",
        )

        # Verify lot size
        assert lot_size >= Decimal("2.25")
        assert lot_size <= Decimal("2.40")

        # Verify adjustment details
        assert details["base_risk_percent"] == "0.7"
        assert details["volume_multiplier"] == "0.75"
        assert details["session_multiplier"] == "0.90"
        # 0.7 × 0.75 × 0.90 = 0.4725
        effective = Decimal(details["effective_risk_percent"])
        assert effective >= Decimal("0.47")
        assert effective <= Decimal("0.48")


class TestSpringStopValidationRejection:
    """
    Integration Test 4: Spring pattern stop validation rejection (too tight).

    Scenario:
    - Pattern: Spring EUR/USD
    - Stop: 10 pips (below 20 pip minimum)
    - Expected: Validation rejection with structural stop guidance
    """

    def test_spring_stop_too_tight_rejection(self) -> None:
        """Test Spring stop validation rejects stops that are too tight."""
        # Setup
        stop_pips = Decimal("10.0")  # Too tight for Spring EUR/USD (min 20)
        required_margin = Decimal("500.00")
        available_margin = Decimal("10000.00")
        position_units = 10000
        pattern_type = "SPRING"
        symbol = "EUR/USD"

        # Validate position (should fail)
        is_valid, error = validate_forex_position(
            stop_pips=stop_pips,
            required_margin=required_margin,
            available_margin=available_margin,
            position_units=position_units,
            pattern_type=pattern_type,
            symbol=symbol,
        )

        # Verify rejection
        assert is_valid is False
        assert "too tight" in error
        assert "10 pips" in error
        assert "20 pip minimum" in error
        assert "EUR/USD" in error
        assert "structural support" in error


class TestSOSStopValidationRejection:
    """
    Integration Test 5: SOS pattern stop validation rejection (too wide).

    Scenario:
    - Pattern: SOS EUR/USD
    - Stop: 200 pips (above 100 pip maximum)
    - Expected: Validation rejection with range guidance
    """

    def test_sos_stop_too_wide_rejection(self) -> None:
        """Test SOS stop validation rejects stops that are too wide."""
        # Setup
        stop_pips = Decimal("200.0")  # Too wide for SOS EUR/USD (max 100)
        required_margin = Decimal("500.00")
        available_margin = Decimal("10000.00")
        position_units = 10000
        pattern_type = "SOS"
        symbol = "EUR/USD"

        # Validate position (should fail)
        is_valid, error = validate_forex_position(
            stop_pips=stop_pips,
            required_margin=required_margin,
            available_margin=available_margin,
            position_units=position_units,
            pattern_type=pattern_type,
            symbol=symbol,
        )

        # Verify rejection
        assert is_valid is False
        assert "too wide" in error
        assert "200 pips" in error
        assert "100 pip maximum" in error


class TestOverLeveragedPositionRejection:
    """
    Integration Test 6: Over-leveraged position rejection.

    Scenario:
    - Account: $10,000
    - Required margin: $7,500 (75% of account)
    - Max allowed: 50% of account
    - Expected: Position rejection due to over-leverage
    """

    def test_over_leveraged_position_rejection(self) -> None:
        """Test position validation rejects over-leveraged positions."""
        # Setup
        account_balance = Decimal("10000.00")
        required_margin = Decimal("7500.00")  # 75% of account
        stop_pips = Decimal("30.0")
        position_units = 100000  # 1 standard lot
        pattern_type = "SPRING"
        symbol = "EUR/USD"

        # Validate position (should fail due to margin)
        is_valid, error = validate_forex_position(
            stop_pips=stop_pips,
            required_margin=required_margin,
            available_margin=account_balance,
            position_units=position_units,
            pattern_type=pattern_type,
            symbol=symbol,
        )

        # Verify rejection
        assert is_valid is False
        assert "Over-leveraged" in error
        assert "75.0%" in error
        assert "max 50%" in error
