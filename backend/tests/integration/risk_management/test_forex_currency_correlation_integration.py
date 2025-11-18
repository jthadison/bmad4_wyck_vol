"""
Integration tests for Forex Currency Correlation Validator (Phase-Weighted).

Tests real-world multi-campaign scenarios validating the Wyckoff team revision.

Key Scenarios:
--------------
1. Multiple Phase E campaigns (Wyckoff benefit test)
2. Mixed Phase E/C/D campaigns (phase weighting in practice)
3. Campaign count limit at 3 concurrent campaigns
4. Currency group concentration (advisory only)
5. Full portfolio validation flow

Wyckoff Validation:
------------------
- Multiple Phase E confirmed campaigns should run concurrently
- Phase weighting allows higher raw exposure for validated campaigns
- Campaign count prevents complexity without blocking valid setups
"""

from datetime import UTC, datetime
from decimal import Decimal

from src.risk_management.forex_campaign_tracker import (
    ForexCurrencyCampaign,
    ForexPosition,
)
from src.risk_management.forex_currency_correlation_validator import (
    calculate_forex_currency_exposure,
    validate_campaign_count_limit,
    validate_currency_limit_phase_weighted,
)

# =============================================================================
# INTEGRATION TEST 1: MULTIPLE PHASE E CAMPAIGNS (WYCKOFF BENEFIT)
# =============================================================================


def test_multiple_phase_e_campaigns_allowed() -> None:
    """
    CRITICAL WYCKOFF TEST: Multiple Phase E confirmed campaigns should be allowed.

    Scenario:
    - EUR/USD Phase E (6% risk)
    - GBP/USD Phase E (4% risk)
    - Total: 10% raw USD short, but 5% weighted USD short (under 6% limit)

    OLD (WRONG): Flat 6% limit would reject (10% > 6%)
    NEW (WYCKOFF): Phase-weighted limit allows (5% weighted < 6% limit)
    """
    eur_usd = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",  # Phase E = 0.5x weight
        pattern_type="SOS",
        position_risk_pct=Decimal("6.0"),
        status="OPEN",
    )

    gbp_usd = ForexPosition(
        symbol="GBP/USD",
        entry=Decimal("1.2650"),
        stop=Decimal("1.2600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("126500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",  # Phase E = 0.5x weight
        pattern_type="SOS",
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )

    # Validate USD exposure (both positions short USD)
    is_valid, error = validate_currency_limit_phase_weighted("USD", [eur_usd], gbp_usd)

    # Raw USD: -6% EUR/USD - 4% GBP/USD = -10% raw USD
    # Weighted USD: (-6% × 0.5) + (-4% × 0.5) = -5% weighted USD
    # Expected: APPROVED (-5% < 6% limit)
    assert is_valid is True
    assert error is None


# =============================================================================
# INTEGRATION TEST 2: MIXED PHASE CAMPAIGNS
# =============================================================================


def test_mixed_phase_e_and_c_campaigns() -> None:
    """
    Mixed Phase E and Phase C campaigns with phase-weighted validation.

    Scenario:
    - EUR/USD Phase E (4% EUR)
    - EUR/GBP Phase C (4% EUR)
    - Total: 8% raw EUR, but 6% weighted EUR (at limit)
    """
    eur_usd_e = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="E",  # 0.5x weight
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )

    eur_gbp_c = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8650"),
        stop=Decimal("0.8600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86500.00"),
        account_balance=Decimal("10000.00"),
        direction="long",
        wyckoff_phase="C",  # 1.0x weight
        position_risk_pct=Decimal("4.0"),
        status="OPEN",
    )

    is_valid, error = validate_currency_limit_phase_weighted("EUR", [eur_usd_e], eur_gbp_c)

    # Raw EUR: 4% + 4% = 8% raw EUR
    # Weighted EUR: (4% × 0.5) + (4% × 1.0) = 6% weighted EUR
    # Expected: APPROVED (6% = exactly at limit)
    assert is_valid is True
    assert error is None


# =============================================================================
# INTEGRATION TEST 3: CAMPAIGN COUNT LIMIT
# =============================================================================


def test_campaign_count_limit_enforcement() -> None:
    """
    Campaign count limit at 3 concurrent campaigns.

    Scenario:
    - 3 active campaigns (EUR_LONG, GBP_LONG, AUD_LONG)
    - Attempting to start 4th campaign (NZD_LONG)
    - Expected: REJECTED (exceeds 3 campaign limit)
    """
    campaign1 = ForexCurrencyCampaign(
        campaign_id="EUR_LONG",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("6.0"),
        position_count=2,
        positions=[
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
            ),
            ForexPosition(
                symbol="EUR/GBP",
                entry=Decimal("0.8650"),
                stop=Decimal("0.8600"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("86500.00"),
                account_balance=Decimal("10000.00"),
                direction="long",
                wyckoff_phase="D",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
            ),
        ],
        started_at=datetime(2024, 3, 15, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )

    campaign2 = ForexCurrencyCampaign(
        campaign_id="GBP_LONG",
        currency="GBP",
        direction="LONG",
        total_risk_pct=Decimal("4.0"),
        position_count=1,
        positions=[
            ForexPosition(
                symbol="GBP/USD",
                entry=Decimal("1.2650"),
                stop=Decimal("1.2600"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("126500.00"),
                account_balance=Decimal("10000.00"),
                direction="long",
                wyckoff_phase="E",
                position_risk_pct=Decimal("4.0"),
                status="OPEN",
            )
        ],
        started_at=datetime(2024, 3, 16, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )

    campaign3 = ForexCurrencyCampaign(
        campaign_id="AUD_LONG",
        currency="AUD",
        direction="LONG",
        total_risk_pct=Decimal("2.0"),
        position_count=1,
        positions=[
            ForexPosition(
                symbol="AUD/USD",
                entry=Decimal("0.6650"),
                stop=Decimal("0.6600"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("66500.00"),
                account_balance=Decimal("10000.00"),
                direction="long",
                wyckoff_phase="D",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
            )
        ],
        started_at=datetime(2024, 3, 17, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )

    campaigns = [campaign1, campaign2, campaign3]

    # Attempt to start 4th campaign (NZD/USD)
    is_valid, error = validate_campaign_count_limit(campaigns, "NZD/USD")

    assert is_valid is False
    assert error is not None
    assert "REJECTED" in error
    assert "3" in error  # Max 3 campaigns


# =============================================================================
# INTEGRATION TEST 4: FULL PORTFOLIO EXPOSURE CALCULATION
# =============================================================================


def test_full_portfolio_exposure_calculation() -> None:
    """
    Full portfolio exposure calculation with phase-weighted data.

    Portfolio:
    - EUR/USD Phase E (4% EUR, -4% USD)
    - GBP/USD Phase D (3% GBP, -3% USD)
    - AUD/USD Phase C (2% AUD, -2% USD)

    Validates:
    - Raw vs weighted exposure calculations
    - Phase breakdown reporting
    - Campaign count tracking
    """
    positions = [
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
        ),
        ForexPosition(
            symbol="GBP/USD",
            entry=Decimal("1.2650"),
            stop=Decimal("1.2600"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("126500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            wyckoff_phase="D",
            position_risk_pct=Decimal("3.0"),
            status="OPEN",
        ),
        ForexPosition(
            symbol="AUD/USD",
            entry=Decimal("0.6650"),
            stop=Decimal("0.6600"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("66500.00"),
            account_balance=Decimal("10000.00"),
            direction="long",
            wyckoff_phase="C",
            position_risk_pct=Decimal("2.0"),
            status="OPEN",
        ),
    ]

    campaign1 = ForexCurrencyCampaign(
        campaign_id="EUR_LONG",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("4.0"),
        position_count=1,
        positions=[positions[0]],
        started_at=datetime(2024, 3, 15, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )

    campaign2 = ForexCurrencyCampaign(
        campaign_id="GBP_LONG",
        currency="GBP",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[positions[1]],
        started_at=datetime(2024, 3, 16, 10, 0, tzinfo=UTC),
        status="ACTIVE",
    )

    campaigns = [campaign1, campaign2]

    exposure = calculate_forex_currency_exposure(positions, campaigns)

    # Raw exposure
    assert exposure.currency_exposure_raw["EUR"] == Decimal("4.0")
    assert exposure.currency_exposure_raw["GBP"] == Decimal("3.0")
    assert exposure.currency_exposure_raw["AUD"] == Decimal("2.0")
    assert exposure.currency_exposure_raw["USD"] == Decimal("-9.0")  # -4 -3 -2

    # Weighted exposure
    assert exposure.currency_exposure_weighted["EUR"] == Decimal("2.0")  # 4 × 0.5
    assert exposure.currency_exposure_weighted["GBP"] == Decimal("2.25")  # 3 × 0.75
    assert exposure.currency_exposure_weighted["AUD"] == Decimal("2.0")  # 2 × 1.0
    assert exposure.currency_exposure_weighted["USD"] == Decimal(
        "-6.25"
    )  # (-4×0.5) + (-3×0.75) + (-2×1.0)

    # Phase breakdown
    assert exposure.phase_breakdown["EUR"]["E"] == Decimal("4.0")
    assert exposure.phase_breakdown["GBP"]["D"] == Decimal("3.0")
    assert exposure.phase_breakdown["AUD"]["C"] == Decimal("2.0")

    # Campaign tracking
    assert exposure.campaign_count == 2
    assert len(exposure.active_campaigns) >= 2  # At least EUR/USD and GBP/USD


# =============================================================================
# SUMMARY
# =============================================================================

"""
Integration Test Summary:
-------------------------
Total Tests: 4 tests

Scenarios:
1. Multiple Phase E campaigns (Wyckoff benefit) - validates phase weighting allows concurrent confirmed campaigns
2. Mixed Phase E/C campaigns - validates phase weighting calculation in practice
3. Campaign count limit at 3 - validates campaign complexity management
4. Full portfolio exposure - validates comprehensive reporting with phase breakdown

Wyckoff Methodology Validation:
- Phase E confirmed campaigns have lower weighted exposure (0.5x)
- Multiple Phase E campaigns can run concurrently (10% raw = 5% weighted)
- Campaign count limit prevents complexity without blocking valid setups
- Phase breakdown provides visibility into campaign validation status

Coverage: Integration scenarios for multi-campaign forex portfolios
"""
