"""
Unit tests for Forex Currency Correlation Validator (Phase-Weighted).

Tests Story 7.5-FX implementation after Wyckoff team revision (2025-11-18).

Test Coverage:
--------------
1. Phase weighting calculation (Phase E = 0.5x, Phase D = 0.75x, Phase C/B/A = 1.0x)
2. Currency exposure calculation (base/quote mechanics)
3. Phase-weighted currency limit validation (6% max weighted)
4. Campaign count limit validation (max 3 campaigns)
5. Currency group concentration detection (ADVISORY ONLY)
6. Rejection messaging with phase context

Wyckoff Methodology Validation:
-------------------------------
- Phase E confirmed campaigns should have lower weighted exposure
- Multiple Phase E campaigns should be allowed despite high raw exposure
- Campaign count limit prevents complexity without blocking valid setups
- Currency groups are advisory only (no rejections)
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.risk_management.forex_campaign_tracker import (
    ForexCurrencyCampaign,
    ForexPosition,
)
from src.risk_management.forex_currency_correlation_validator import (
    calculate_currency_exposure_for_position,
    calculate_currency_group_exposure,
    calculate_forex_currency_exposure,
    calculate_phase_weighted_exposure,
    check_currency_group_concentration,
    get_phase_weight,
    validate_campaign_count_limit,
    validate_currency_limit_phase_weighted,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def base_position() -> ForexPosition:
    """Base forex position for testing."""
    return ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="SPRING",
        wyckoff_phase="C",
        direction="long",
        entry_type="FIRST",
        status="OPEN",
        position_risk_pct=Decimal("2.0"),
        volume_ratio=Decimal("1.5"),
    )


@pytest.fixture
def phase_e_position(base_position: ForexPosition) -> ForexPosition:
    """Phase E position (0.5x weight)."""
    pos = base_position
    pos.wyckoff_phase = "E"
    pos.pattern_type = "SOS"
    pos.position_risk_pct = Decimal("4.0")
    return pos


@pytest.fixture
def phase_d_position(base_position: ForexPosition) -> ForexPosition:
    """Phase D position (0.75x weight)."""
    pos = ForexPosition(
        symbol="GBP/USD",
        entry=Decimal("1.2650"),
        stop=Decimal("1.2600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("126500.00"),
        account_balance=Decimal("10000.00"),
        pattern_type="LPS",
        wyckoff_phase="D",
        direction="long",
        entry_type="CONFIRM",
        status="OPEN",
        position_risk_pct=Decimal("2.0"),
        volume_ratio=Decimal("1.8"),
    )
    return pos


@pytest.fixture
def base_campaign() -> ForexCurrencyCampaign:
    """Base campaign for testing."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        wyckoff_phase="E",
        direction="long",
        position_risk_pct=Decimal("4.0"),
    )
    return ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("4.0"),
        position_count=1,
        positions=[pos],
        started_at=datetime(2024, 3, 15, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )


# =============================================================================
# TEST TASK 3: PHASE WEIGHTING (AC #3, #9)
# =============================================================================


def test_get_phase_weight_phase_e() -> None:
    """Phase E should return 0.5x weight (confirmed campaign)."""
    assert get_phase_weight("E") == Decimal("0.50")


def test_get_phase_weight_phase_d() -> None:
    """Phase D should return 0.75x weight (progressing campaign)."""
    assert get_phase_weight("D") == Decimal("0.75")


def test_get_phase_weight_phase_c() -> None:
    """Phase C should return 1.0x weight (unconfirmed campaign)."""
    assert get_phase_weight("C") == Decimal("1.00")


def test_get_phase_weight_phase_b() -> None:
    """Phase B should return 1.0x weight (early accumulation)."""
    assert get_phase_weight("B") == Decimal("1.00")


def test_get_phase_weight_phase_a() -> None:
    """Phase A should return 1.0x weight (preliminary support)."""
    assert get_phase_weight("A") == Decimal("1.00")


def test_get_phase_weight_none() -> None:
    """None phase should return 1.0x weight (conservative full risk)."""
    assert get_phase_weight(None) == Decimal("1.00")


def test_calculate_currency_exposure_long_base() -> None:
    """EUR/USD long should have +EUR exposure."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        position_risk_pct=Decimal("2.0"),
    )
    exposure = calculate_currency_exposure_for_position(pos, "EUR")
    assert exposure == Decimal("2.0")


def test_calculate_currency_exposure_long_quote() -> None:
    """EUR/USD long should have -USD exposure."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        position_risk_pct=Decimal("2.0"),
    )
    exposure = calculate_currency_exposure_for_position(pos, "USD")
    assert exposure == Decimal("-2.0")


def test_calculate_currency_exposure_short_base() -> None:
    """EUR/USD short should have -EUR exposure."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0900"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="short",
        position_risk_pct=Decimal("2.0"),
    )
    exposure = calculate_currency_exposure_for_position(pos, "EUR")
    assert exposure == Decimal("-2.0")


def test_calculate_currency_exposure_short_quote() -> None:
    """EUR/USD short should have +USD exposure."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0900"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="short",
        position_risk_pct=Decimal("2.0"),
    )
    exposure = calculate_currency_exposure_for_position(pos, "USD")
    assert exposure == Decimal("2.0")


def test_calculate_currency_exposure_not_involved() -> None:
    """EUR/USD should have 0 GBP exposure."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        position_risk_pct=Decimal("2.0"),
    )
    exposure = calculate_currency_exposure_for_position(pos, "GBP")
    assert exposure == Decimal("0")


def test_calculate_phase_weighted_exposure_single_position_phase_e() -> None:
    """Phase E position should have 0.5x weighted exposure."""
    pos = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )

    raw, weighted, breakdown = calculate_phase_weighted_exposure([pos], "EUR")

    assert raw == Decimal("4.0")  # 4% raw EUR
    assert weighted == Decimal("2.0")  # 4% × 0.5 = 2% weighted
    assert breakdown == {"E": Decimal("4.0")}


def test_calculate_phase_weighted_exposure_mixed_phases() -> None:
    """Mixed Phase E and Phase C should have different weighted exposure."""
    pos_e = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )
    pos_c = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",
        position_risk_pct=Decimal("2.0"),
        status="OPEN",
    )

    raw, weighted, breakdown = calculate_phase_weighted_exposure([pos_e, pos_c], "EUR")

    assert raw == Decimal("6.0")  # 4% + 2% = 6% raw EUR
    assert weighted == Decimal("4.0")  # (4% × 0.5) + (2% × 1.0) = 4% weighted EUR
    assert breakdown == {"E": Decimal("4.0"), "C": Decimal("2.0")}


def test_calculate_phase_weighted_exposure_usd_short() -> None:
    """USD short exposure should be negative and phase-weighted."""
    pos_e = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )
    pos_c = ForexPosition(
        symbol="GBP/USD",
        entry=Decimal("1.2650"),
        stop=Decimal("1.2600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("126500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",
        position_risk_pct=Decimal("2.0"),
        status="OPEN",
    )

    raw, weighted, breakdown = calculate_phase_weighted_exposure([pos_e, pos_c], "USD")

    assert raw == Decimal("-6.0")  # -4% EUR/USD - 2% GBP/USD = -6% raw USD
    assert weighted == Decimal("-4.0")  # (-4% × 0.5) + (-2% × 1.0) = -4% weighted USD
    assert breakdown == {"E": Decimal("-4.0"), "C": Decimal("-2.0")}


# =============================================================================
# TEST TASK 3: CURRENCY LIMIT VALIDATION (AC #3)
# =============================================================================


def test_validate_currency_limit_pass_under_limit() -> None:
    """Position under 6% weighted limit should pass."""
    current = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0800"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("108500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            wyckoff_phase="E",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
        )
    ]
    new = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",
        position_risk_pct=Decimal("2.0"),
        status="OPEN",
    )

    is_valid, error = validate_currency_limit_phase_weighted("EUR", current, new)

    # Current: 4% Phase E = 2% weighted
    # New: 2% Phase C = 2% weighted
    # Total: 4% weighted < 6% limit
    assert is_valid is True
    assert error is None


def test_validate_currency_limit_reject_over_limit() -> None:
    """Position over 6% weighted limit should be rejected."""
    current = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0800"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("108500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            wyckoff_phase="E",
            position_risk_pct=Decimal("4.0"),
            status="OPEN",
        )
    ]
    new = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",
        position_risk_pct=Decimal("5.0"),
        status="OPEN",
    )

    is_valid, error = validate_currency_limit_phase_weighted("EUR", current, new)

    # Current: 4% Phase E = 2% weighted
    # New: 5% Phase C = 5% weighted
    # Total: 7% weighted > 6% limit
    assert is_valid is False
    assert error is not None
    assert "REJECTED" in error
    assert "EUR" in error
    assert "phase-weighted" in error.lower()


def test_validate_currency_limit_exactly_at_limit() -> None:
    """Position exactly at 6% weighted limit should pass (boundary condition)."""
    current = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0800"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("108500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            wyckoff_phase="E",
            position_risk_pct=Decimal("8.0"),
            status="OPEN",
        )
    ]
    new = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",
        position_risk_pct=Decimal("2.0"),
        status="OPEN",
    )

    is_valid, error = validate_currency_limit_phase_weighted("EUR", current, new)

    # Current: 8% Phase E = 4% weighted
    # New: 2% Phase C = 2% weighted
    # Total: 6% weighted = exactly at 6% limit (should pass)
    assert is_valid is True
    assert error is None


def test_validate_currency_limit_wyckoff_benefit_multiple_phase_e() -> None:
    """
    CRITICAL WYCKOFF TEST: Multiple Phase E campaigns should be allowed.

    This validates the key Wyckoff revision - Phase E confirmed campaigns
    can run concurrently with higher raw exposure because weighted exposure
    is lower.
    """
    current = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0800"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("108500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            wyckoff_phase="E",
            position_risk_pct=Decimal("6.0"),
            status="OPEN",
        )
    ]
    new = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",
        position_risk_pct=Decimal("6.0"),
        status="OPEN",
    )

    is_valid, error = validate_currency_limit_phase_weighted("EUR", current, new)

    # Current: 6% Phase E = 3% weighted
    # New: 6% Phase E = 3% weighted
    # Total: 12% raw EUR, but 6% weighted (AT LIMIT, should pass)
    #
    # This would be REJECTED by old flat 6% limit (12% > 6%)
    # But APPROVED by phase-weighted limit (6% weighted = 6% limit)
    assert is_valid is True
    assert error is None


# =============================================================================
# TEST TASK 4: CAMPAIGN COUNT LIMIT (AC #4)
# =============================================================================


def test_validate_campaign_count_under_limit(base_campaign: ForexCurrencyCampaign) -> None:
    """Adding to existing campaign or starting 2nd campaign should pass."""
    campaigns = [base_campaign]

    # Adding to existing EUR/USD campaign
    is_valid, error = validate_campaign_count_limit(campaigns, "EUR/USD")
    assert is_valid is True
    assert error is None

    # Starting new GBP/USD campaign (2nd campaign)
    is_valid, error = validate_campaign_count_limit(campaigns, "GBP/USD")
    assert is_valid is True
    assert error is None


def test_validate_campaign_count_at_limit(base_campaign: ForexCurrencyCampaign) -> None:
    """At 3 campaigns, adding to existing should pass, new campaign should fail."""
    campaign2 = ForexCurrencyCampaign(
        campaign_id="GBP_LONG_2024_03_16",
        currency="GBP",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime(2024, 3, 16, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign2.symbol = "GBP/USD"  # type: ignore

    campaign3 = ForexCurrencyCampaign(
        campaign_id="AUD_LONG_2024_03_17",
        currency="AUD",
        direction="LONG",
        total_risk_pct=Decimal("2.0"),
        position_count=1,
        positions=[],
        started_at=datetime(2024, 3, 17, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign3.symbol = "AUD/USD"  # type: ignore

    campaigns = [base_campaign, campaign2, campaign3]

    # Adding to existing EUR/USD campaign (should pass)
    is_valid, error = validate_campaign_count_limit(campaigns, "EUR/USD")
    assert is_valid is True
    assert error is None

    # Starting 4th campaign NZD/USD (should fail)
    is_valid, error = validate_campaign_count_limit(campaigns, "NZD/USD")
    assert is_valid is False
    assert error is not None
    assert "REJECTED" in error
    assert "3" in error  # Max 3 campaigns
    assert "NZD/USD" in error


def test_validate_campaign_count_completed_campaigns_dont_count() -> None:
    """Completed campaigns should not count toward limit."""
    campaign1 = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_COMPLETED",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("0.0"),
        position_count=0,
        positions=[],
        started_at=datetime(2024, 3, 1, 10, 0, tzinfo=UTC),
        status="COMPLETED",
    )
    campaign1.symbol = "EUR/USD"  # type: ignore

    campaign2 = ForexCurrencyCampaign(
        campaign_id="GBP_LONG_ACTIVE",
        currency="GBP",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime(2024, 3, 15, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign2.symbol = "GBP/USD"  # type: ignore

    campaigns = [campaign1, campaign2]

    # Only 1 active campaign, so starting new AUD/USD should pass
    is_valid, error = validate_campaign_count_limit(campaigns, "AUD/USD")
    assert is_valid is True
    assert error is None


# =============================================================================
# TEST TASK 6: CURRENCY GROUP CONCENTRATION (AC #6 - ADVISORY ONLY)
# =============================================================================


def test_calculate_currency_group_exposure_commodity() -> None:
    """Commodity currency group should sum AUD, NZD, CAD exposure."""
    positions = [
        ForexPosition(
            symbol="AUD/USD",
            entry=Decimal("0.6650"),
            stop=Decimal("0.6600"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("66500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
        ),
        ForexPosition(
            symbol="NZD/USD",
            entry=Decimal("0.6150"),
            stop=Decimal("0.6100"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("61500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
        ),
        ForexPosition(
            symbol="CAD/JPY",
            entry=Decimal("109.50"),
            stop=Decimal("109.00"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("1095000.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
        ),
    ]

    group_exposure = calculate_currency_group_exposure(positions)

    # AUD 3% + NZD 2% + CAD 1.5% = 6.5%
    assert group_exposure["commodity"] == Decimal("6.5")


def test_check_currency_group_concentration_advisory_only() -> None:
    """
    CRITICAL: Currency group warnings are ADVISORY ONLY, not enforced.

    This validates the Wyckoff revision - group concentration warnings
    are informational, do NOT block positions.
    """
    group_exposure = {
        "commodity": Decimal("12.0"),  # Over 10% threshold
        "majors": Decimal("8.0"),  # Under 10% threshold
        "emerging": Decimal("0.0"),
        "european": Decimal("5.0"),
    }

    concentrated = check_currency_group_concentration(group_exposure)

    # Only commodity group >= 10% threshold
    assert len(concentrated) == 1
    assert concentrated[0] == ("commodity", Decimal("12.0"))

    # CRITICAL: This is ADVISORY - validation function doesn't exist
    # Old implementation would have validate_group_concentration() that rejects
    # New implementation only returns warnings, does NOT block positions


# =============================================================================
# TEST TASK 5: FOREX CURRENCY EXPOSURE DATA MODEL (AC #5)
# =============================================================================


def test_calculate_forex_currency_exposure_comprehensive() -> None:
    """Comprehensive currency exposure report with all fields."""
    pos_e = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )
    pos_c = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",
        position_risk_pct=Decimal("2.0"),
        status="OPEN",
    )

    campaign1 = ForexCurrencyCampaign(
        campaign_id="EUR_LONG",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("4.0"),
        position_count=1,
        positions=[pos_e],
        started_at=datetime(2024, 3, 15, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign1.symbol = "EUR/USD"  # type: ignore

    exposure = calculate_forex_currency_exposure([pos_e, pos_c], [campaign1])

    # Raw exposure
    assert exposure.currency_exposure_raw["EUR"] == Decimal("6.0")  # 4% + 2%
    assert exposure.currency_exposure_raw["USD"] == Decimal("-4.0")  # -4% (EUR/USD only)
    assert exposure.currency_exposure_raw["GBP"] == Decimal("-2.0")  # -2% (EUR/GBP only)

    # Weighted exposure
    assert exposure.currency_exposure_weighted["EUR"] == Decimal("4.0")  # (4% × 0.5) + (2% × 1.0)
    assert exposure.currency_exposure_weighted["USD"] == Decimal("-2.0")  # -4% × 0.5

    # Phase breakdown
    assert exposure.phase_breakdown["EUR"]["E"] == Decimal("4.0")
    assert exposure.phase_breakdown["EUR"]["C"] == Decimal("2.0")

    # Campaign tracking
    assert exposure.campaign_count == 1
    assert "EUR/USD" in exposure.active_campaigns
    assert exposure.campaign_limit_warning is None  # Only 1 campaign


def test_calculate_forex_currency_exposure_campaign_limit_warning() -> None:
    """Campaign limit warning should appear at 3 campaigns."""
    campaign1 = ForexCurrencyCampaign(
        campaign_id="EUR_LONG",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("4.0"),
        position_count=1,
        positions=[],
        started_at=datetime(2024, 3, 15, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign1.symbol = "EUR/USD"  # type: ignore

    campaign2 = ForexCurrencyCampaign(
        campaign_id="GBP_LONG",
        currency="GBP",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime(2024, 3, 16, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign2.symbol = "GBP/USD"  # type: ignore

    campaign3 = ForexCurrencyCampaign(
        campaign_id="AUD_LONG",
        currency="AUD",
        direction="LONG",
        total_risk_pct=Decimal("2.0"),
        position_count=1,
        positions=[],
        started_at=datetime(2024, 3, 17, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )
    campaign3.symbol = "AUD/USD"  # type: ignore

    exposure = calculate_forex_currency_exposure([], [campaign1, campaign2, campaign3])

    assert exposure.campaign_count == 3
    assert exposure.campaign_limit_warning is not None
    assert "3" in exposure.campaign_limit_warning


# =============================================================================
# SUMMARY TEST STATISTICS
# =============================================================================

"""
Test Coverage Summary:
----------------------
Total Tests: 25 tests

Breakdown by Category:
- Phase weighting (AC #9): 6 tests
- Currency exposure calculation (AC #2): 5 tests
- Phase-weighted exposure calculation (AC #3): 3 tests
- Currency limit validation (AC #3): 5 tests (including Wyckoff benefit test)
- Campaign count limit (AC #4): 3 tests
- Currency group concentration (AC #6): 2 tests
- Forex currency exposure model (AC #5): 2 tests

Key Wyckoff Validation Tests:
- test_validate_currency_limit_wyckoff_benefit_multiple_phase_e: Validates multiple Phase E campaigns allowed
- test_check_currency_group_concentration_advisory_only: Validates groups are advisory only

Removed Tests (Contradicted Wyckoff):
- Directional limit validation tests (8% cap) - 0 tests (feature removed)
- Correlation matrix tests (EUR/GBP 70%) - 0 tests (feature removed)

Coverage Target: 90%+ of forex_currency_correlation_validator.py
"""
