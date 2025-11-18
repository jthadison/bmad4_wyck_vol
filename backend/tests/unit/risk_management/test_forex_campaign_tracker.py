"""
Unit tests for Forex Campaign Risk Tracking (Story 7.4-FX).

Tests currency trend campaign tracking with Wyckoff team-approved revisions:
- BMAD allocation: 25%/45%/30% (not 40%/35%/25%)
- Volume validation for multi-pair additions
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from backend.src.risk_management.forex_campaign_tracker import (
    ADDON_MIN_VOLUME,
    CONFIRM_MIN_VOLUME,
    FIRST_ENTRY_MAX_VOLUME,
    FOREX_TREND_ADDON_ALLOC,
    FOREX_TREND_CONFIRM_ALLOC,
    # Constants
    FOREX_TREND_FIRST_ENTRY_ALLOC,
    MAX_ADDON_RISK,
    MAX_CONFIRM_RISK,
    MAX_FIRST_ENTRY_RISK,
    ForexCurrencyCampaign,
    # Data models
    ForexPosition,
    add_position_to_campaign,
    calculate_currency_campaign_risk,
    check_campaign_completion,
    create_new_campaign,
    detect_trend_reversal,
    # Functions
    extract_currency_exposure,
    get_campaign_id,
    validate_forex_bmad_allocation,
    validate_position_matches_campaign,
    validate_volume_for_campaign_addition,
)

# =============================================================================
# TEST BMAD ALLOCATION CONSTANTS (WYCKOFF TEAM REVISED)
# =============================================================================


def test_bmad_allocation_constants_revised() -> None:
    """Verify BMAD allocation changed to 25%/45%/30% per Wyckoff team review."""
    assert FOREX_TREND_FIRST_ENTRY_ALLOC == Decimal("0.25")
    assert FOREX_TREND_CONFIRM_ALLOC == Decimal("0.45")
    assert FOREX_TREND_ADDON_ALLOC == Decimal("0.30")

    # Verify sum = 100%
    total = FOREX_TREND_FIRST_ENTRY_ALLOC + FOREX_TREND_CONFIRM_ALLOC + FOREX_TREND_ADDON_ALLOC
    assert total == Decimal("1.0")

    # Verify max risks (as percentage of 5% campaign limit)
    assert MAX_FIRST_ENTRY_RISK == Decimal("1.25")  # 25% of 5%
    assert MAX_CONFIRM_RISK == Decimal("2.25")  # 45% of 5%
    assert MAX_ADDON_RISK == Decimal("1.50")  # 30% of 5%


def test_volume_thresholds() -> None:
    """Verify volume validation thresholds per Wyckoff team review."""
    assert FIRST_ENTRY_MAX_VOLUME == Decimal("0.8")  # Spring: <0.8x avg
    assert CONFIRM_MIN_VOLUME == Decimal("1.5")  # SOS: ≥1.5x avg
    assert ADDON_MIN_VOLUME == Decimal("1.2")  # Continuation: ≥1.2x avg


# =============================================================================
# TEST CURRENCY TREND IDENTIFICATION
# =============================================================================


def test_extract_currency_exposure_eur_usd_long() -> None:
    """EUR/USD long = buy EUR, sell USD."""
    bought, sold = extract_currency_exposure("EUR/USD", "long")
    assert bought == "EUR"
    assert sold == "USD"


def test_extract_currency_exposure_eur_usd_short() -> None:
    """EUR/USD short = buy USD, sell EUR."""
    bought, sold = extract_currency_exposure("EUR/USD", "short")
    assert bought == "USD"
    assert sold == "EUR"


def test_extract_currency_exposure_gbp_jpy_long() -> None:
    """GBP/JPY long = buy GBP, sell JPY."""
    bought, sold = extract_currency_exposure("GBP/JPY", "long")
    assert bought == "GBP"
    assert sold == "JPY"


def test_extract_currency_exposure_invalid_symbol() -> None:
    """Invalid symbol format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid forex symbol format"):
        extract_currency_exposure("EURUSD", "long")


def test_get_campaign_id() -> None:
    """Campaign ID format: CURRENCY_DIRECTION_YYYY_MM_DD."""
    campaign_id = get_campaign_id("EUR", "LONG", datetime(2024, 3, 15, tzinfo=UTC))
    assert campaign_id == "EUR_LONG_2024_03_15"


def test_get_campaign_id_usd_short() -> None:
    """USD short campaign ID."""
    campaign_id = get_campaign_id("USD", "SHORT", datetime(2024, 4, 1, tzinfo=UTC))
    assert campaign_id == "USD_SHORT_2024_04_01"


# =============================================================================
# TEST CAMPAIGN RISK CALCULATION
# =============================================================================


def test_calculate_campaign_risk_single_position() -> None:
    """Single position campaign risk."""
    position = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500"),
        account_balance=Decimal("100000"),
        campaign_id="EUR_LONG_2024_03_15",
        position_risk_pct=Decimal("1.5"),
        status="OPEN",
    )

    risk = calculate_currency_campaign_risk("EUR_LONG_2024_03_15", [position])
    assert risk == Decimal("1.5")


def test_calculate_campaign_risk_multiple_positions() -> None:
    """Multi-pair campaign risk calculation."""
    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0800"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("108500"),
            account_balance=Decimal("100000"),
            campaign_id="EUR_LONG_2024_03_15",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
        ),
        ForexPosition(
            symbol="EUR/GBP",
            entry=Decimal("0.8620"),
            stop=Decimal("0.8580"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("86200"),
            account_balance=Decimal("100000"),
            campaign_id="EUR_LONG_2024_03_15",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
        ),
        ForexPosition(
            symbol="EUR/JPY",
            entry=Decimal("161.50"),
            stop=Decimal("160.50"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("161500"),
            account_balance=Decimal("100000"),
            campaign_id="EUR_LONG_2024_03_15",
            position_risk_pct=Decimal("1.0"),
            status="OPEN",
        ),
    ]

    risk = calculate_currency_campaign_risk("EUR_LONG_2024_03_15", positions)
    assert risk == Decimal("4.0")


def test_calculate_campaign_risk_ignores_closed_positions() -> None:
    """Closed positions not included in campaign risk."""
    positions = [
        ForexPosition(
            symbol="EUR/USD",
            entry=Decimal("1.0850"),
            stop=Decimal("1.0800"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("108500"),
            account_balance=Decimal("100000"),
            campaign_id="EUR_LONG_2024_03_15",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
        ),
        ForexPosition(
            symbol="EUR/GBP",
            entry=Decimal("0.8620"),
            stop=Decimal("0.8580"),
            lot_size=Decimal("1.0"),
            lot_type="standard",
            position_value_usd=Decimal("86200"),
            account_balance=Decimal("100000"),
            campaign_id="EUR_LONG_2024_03_15",
            position_risk_pct=Decimal("1.5"),
            status="CLOSED",
        ),
    ]

    risk = calculate_currency_campaign_risk("EUR_LONG_2024_03_15", positions)
    assert risk == Decimal("1.5")  # Only open position


# =============================================================================
# TEST BMAD ALLOCATION VALIDATION (WYCKOFF REVISED)
# =============================================================================


def test_validate_bmad_first_entry_at_limit() -> None:
    """First entry at 1.25% limit (25% of 5%) passes."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_forex_bmad_allocation(campaign, "FIRST", Decimal("1.25"))
    assert is_valid is True
    assert error_msg is None


def test_validate_bmad_first_entry_exceeds_limit() -> None:
    """First entry exceeding 1.25% limit (25% of 5%) fails."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_forex_bmad_allocation(campaign, "FIRST", Decimal("1.26"))
    assert is_valid is False
    assert "FIRST allocation exceeded" in error_msg
    assert "1.26% > 1.25%" in error_msg


def test_validate_bmad_confirm_at_limit() -> None:
    """Confirm entry at 2.25% limit (45% of 5%) passes."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_forex_bmad_allocation(campaign, "CONFIRM", Decimal("2.25"))
    assert is_valid is True
    assert error_msg is None


def test_validate_bmad_confirm_exceeds_limit() -> None:
    """Confirm entry exceeding 2.25% limit (45% of 5%) fails."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[
            ForexPosition(
                symbol="EUR/USD",
                entry=Decimal("1.0850"),
                stop=Decimal("1.0800"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("108500"),
                account_balance=Decimal("100000"),
                entry_type="CONFIRM",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
            )
        ],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_forex_bmad_allocation(campaign, "CONFIRM", Decimal("0.26"))
    assert is_valid is False
    assert "CONFIRM allocation exceeded" in error_msg
    assert "2.26% > 2.25%" in error_msg


def test_validate_bmad_addon_at_limit() -> None:
    """Addon entry at 1.50% limit (30% of 5%) passes."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_forex_bmad_allocation(campaign, "ADDON", Decimal("1.50"))
    assert is_valid is True
    assert error_msg is None


# =============================================================================
# TEST TREND COMPLETION DETECTION
# =============================================================================


def test_detect_trend_reversal_eur_long_to_short() -> None:
    """EUR long campaign + EUR short signal = reversal."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    reversal = detect_trend_reversal(campaign, "EUR", "SHORT")
    assert reversal is True


def test_detect_trend_reversal_different_currency() -> None:
    """EUR long campaign + USD short signal = no reversal."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    reversal = detect_trend_reversal(campaign, "USD", "SHORT")
    assert reversal is False


def test_detect_trend_reversal_same_direction() -> None:
    """EUR long campaign + EUR long signal = trend continuation."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    reversal = detect_trend_reversal(campaign, "EUR", "LONG")
    assert reversal is False


def test_check_campaign_completion_all_positions_closed() -> None:
    """Campaign completes when all positions closed."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("0.0"),
        position_count=2,
        positions=[
            ForexPosition(
                symbol="EUR/USD",
                entry=Decimal("1.0850"),
                stop=Decimal("1.0800"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("108500"),
                account_balance=Decimal("100000"),
                status="CLOSED",
            ),
            ForexPosition(
                symbol="EUR/GBP",
                entry=Decimal("0.8620"),
                stop=Decimal("0.8580"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("86200"),
                account_balance=Decimal("100000"),
                status="CLOSED",
            ),
        ],
        started_at=datetime.now(UTC),
    )

    is_complete, reason = check_campaign_completion(campaign)
    assert is_complete is True
    assert reason == "ALL_POSITIONS_CLOSED"


def test_check_campaign_completion_duration_exceeded() -> None:
    """Campaign completes when 14-day duration exceeded."""
    start_date = datetime.now(UTC) - timedelta(days=15)
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_01",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[
            ForexPosition(
                symbol="EUR/USD",
                entry=Decimal("1.0850"),
                stop=Decimal("1.0800"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("108500"),
                account_balance=Decimal("100000"),
                status="OPEN",
            )
        ],
        started_at=start_date,
        expected_completion=start_date + timedelta(days=14),
    )

    is_complete, reason = check_campaign_completion(campaign)
    assert is_complete is True
    assert reason == "MAX_DURATION_EXCEEDED"


def test_check_campaign_completion_active() -> None:
    """Campaign active with open positions < 14 days."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[
            ForexPosition(
                symbol="EUR/USD",
                entry=Decimal("1.0850"),
                stop=Decimal("1.0800"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("108500"),
                account_balance=Decimal("100000"),
                status="OPEN",
            )
        ],
        started_at=datetime.now(UTC),
    )

    is_complete, reason = check_campaign_completion(campaign)
    assert is_complete is False
    assert reason == "ACTIVE"


# =============================================================================
# TEST MULTI-PAIR VALIDATION
# =============================================================================


def test_validate_position_matches_eur_long_eur_usd_long() -> None:
    """EUR_LONG campaign can include EUR/USD long (buys EUR)."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_position_matches_campaign(campaign, "EUR/USD", "long")
    assert is_valid is True
    assert error_msg is None


def test_validate_position_matches_eur_long_eur_gbp_long() -> None:
    """EUR_LONG campaign can include EUR/GBP long (buys EUR)."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_position_matches_campaign(campaign, "EUR/GBP", "long")
    assert is_valid is True
    assert error_msg is None


def test_validate_position_rejects_opposite_direction() -> None:
    """EUR_LONG campaign cannot include EUR/USD short (sells EUR)."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_position_matches_campaign(campaign, "EUR/USD", "short")
    assert is_valid is False
    assert "Position mismatch" in error_msg
    assert "long EUR" in error_msg
    assert "buys USD" in error_msg


def test_validate_position_rejects_different_currency() -> None:
    """EUR_LONG campaign cannot include GBP/USD long (buys GBP, not EUR)."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    is_valid, error_msg = validate_position_matches_campaign(campaign, "GBP/USD", "long")
    assert is_valid is False
    assert "Position mismatch" in error_msg
    assert "long EUR" in error_msg
    assert "buys GBP" in error_msg


# =============================================================================
# TEST VOLUME VALIDATION (WYCKOFF TEAM REQUIRED)
# =============================================================================


def test_validate_volume_first_entry_low_volume_passes() -> None:
    """First entry (Spring) with <0.8x volume passes."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("1.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    position = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500"),
        account_balance=Decimal("100000"),
        entry_type="FIRST",
    )

    is_valid, error_msg = validate_volume_for_campaign_addition(campaign, position, Decimal("0.7"))
    assert is_valid is True
    assert error_msg is None


def test_validate_volume_first_entry_high_volume_fails() -> None:
    """First entry (Spring) with >0.8x volume fails (not low volume test)."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("1.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    position = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500"),
        account_balance=Decimal("100000"),
        entry_type="FIRST",
    )

    is_valid, error_msg = validate_volume_for_campaign_addition(campaign, position, Decimal("0.9"))
    assert is_valid is False
    assert "Spring entry volume too high" in error_msg
    assert "0.9x avg" in error_msg


def test_validate_volume_confirm_high_volume_passes() -> None:
    """Confirm entry (SOS) with ≥1.5x volume passes."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("2.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    position = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8620"),
        stop=Decimal("0.8580"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86200"),
        account_balance=Decimal("100000"),
        entry_type="CONFIRM",
    )

    is_valid, error_msg = validate_volume_for_campaign_addition(campaign, position, Decimal("1.8"))
    assert is_valid is True
    assert error_msg is None


def test_validate_volume_confirm_low_volume_fails() -> None:
    """Confirm entry (SOS) with <1.5x volume fails (insufficient confirmation)."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("2.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    position = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8620"),
        stop=Decimal("0.8580"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86200"),
        account_balance=Decimal("100000"),
        entry_type="CONFIRM",
    )

    is_valid, error_msg = validate_volume_for_campaign_addition(campaign, position, Decimal("0.9"))
    assert is_valid is False
    assert "Insufficient volume for SOS entry" in error_msg
    assert "0.9x avg" in error_msg
    assert "minimum 1.5x required" in error_msg


def test_validate_volume_addon_above_average_passes() -> None:
    """Addon entry with ≥1.2x volume passes."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    position = ForexPosition(
        symbol="EUR/JPY",
        entry=Decimal("161.50"),
        stop=Decimal("160.50"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("161500"),
        account_balance=Decimal("100000"),
        entry_type="ADDON",
    )

    is_valid, error_msg = validate_volume_for_campaign_addition(campaign, position, Decimal("1.3"))
    assert is_valid is True
    assert error_msg is None


def test_validate_volume_addon_low_volume_fails() -> None:
    """Addon entry with <1.2x volume fails."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=datetime.now(UTC),
    )

    position = ForexPosition(
        symbol="EUR/JPY",
        entry=Decimal("161.50"),
        stop=Decimal("160.50"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("161500"),
        account_balance=Decimal("100000"),
        entry_type="ADDON",
    )

    is_valid, error_msg = validate_volume_for_campaign_addition(campaign, position, Decimal("0.8"))
    assert is_valid is False
    assert "Insufficient volume for continuation entry" in error_msg


# =============================================================================
# TEST CAMPAIGN LIFECYCLE MANAGEMENT
# =============================================================================


def test_create_new_campaign() -> None:
    """Create new EUR long campaign with first position."""
    position = ForexPosition(
        symbol="EUR/USD",
        entry=Decimal("1.0850"),
        stop=Decimal("1.0800"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("108500"),
        account_balance=Decimal("100000"),
        entry_type="FIRST",
        direction="long",
        position_risk_pct=Decimal("1.0"),
    )

    campaign = create_new_campaign("EUR", "LONG", position)

    assert campaign.currency == "EUR"
    assert campaign.direction == "LONG"
    assert campaign.total_risk_pct == Decimal("1.0")
    assert campaign.position_count == 1
    assert len(campaign.positions) == 1
    assert campaign.status == "ACTIVE"
    assert position.campaign_id == campaign.campaign_id


def test_add_position_to_campaign_success() -> None:
    """Add position to campaign with all validations passing."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("1.0"),
        position_count=1,
        positions=[
            ForexPosition(
                symbol="EUR/USD",
                entry=Decimal("1.0850"),
                stop=Decimal("1.0800"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("108500"),
                account_balance=Decimal("100000"),
                entry_type="FIRST",
                position_risk_pct=Decimal("1.0"),
                status="OPEN",
                direction="long",
            )
        ],
        started_at=datetime.now(UTC),
    )

    new_position = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8620"),
        stop=Decimal("0.8580"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86200"),
        account_balance=Decimal("100000"),
        entry_type="CONFIRM",
        direction="long",
        position_risk_pct=Decimal("1.5"),
    )

    is_valid, error_msg = add_position_to_campaign(campaign, new_position, Decimal("1.8"))

    assert is_valid is True
    assert error_msg is None
    assert campaign.total_risk_pct == Decimal("2.5")
    assert campaign.position_count == 2
    assert new_position.campaign_id == "EUR_LONG_2024_03_15"


def test_add_position_fails_currency_mismatch() -> None:
    """Add position fails when currency doesn't match campaign."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("1.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    new_position = ForexPosition(
        symbol="GBP/USD",  # Buys GBP, not EUR
        entry=Decimal("1.2650"),
        stop=Decimal("1.2600"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("126500"),
        account_balance=Decimal("100000"),
        entry_type="CONFIRM",
        direction="long",
        position_risk_pct=Decimal("1.5"),
    )

    is_valid, error_msg = add_position_to_campaign(campaign, new_position, Decimal("1.8"))

    assert is_valid is False
    assert "Position mismatch" in error_msg


def test_add_position_fails_insufficient_volume() -> None:
    """Add position fails when volume doesn't meet threshold."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("1.0"),
        position_count=1,
        positions=[],
        started_at=datetime.now(UTC),
    )

    new_position = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8620"),
        stop=Decimal("0.8580"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86200"),
        account_balance=Decimal("100000"),
        entry_type="CONFIRM",  # Requires ≥1.5x volume
        direction="long",
        position_risk_pct=Decimal("1.5"),
    )

    is_valid, error_msg = add_position_to_campaign(
        campaign, new_position, Decimal("0.9")
    )  # Too low

    assert is_valid is False
    assert "Insufficient volume" in error_msg


def test_add_position_fails_bmad_allocation_exceeded() -> None:
    """Add position fails when BMAD allocation exceeded."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("2.0"),
        position_count=1,
        positions=[
            ForexPosition(
                symbol="EUR/USD",
                entry=Decimal("1.0850"),
                stop=Decimal("1.0800"),
                lot_size=Decimal("1.0"),
                lot_type="standard",
                position_value_usd=Decimal("108500"),
                account_balance=Decimal("100000"),
                entry_type="CONFIRM",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
                direction="long",
            )
        ],
        started_at=datetime.now(UTC),
    )

    new_position = ForexPosition(
        symbol="EUR/GBP",
        entry=Decimal("0.8620"),
        stop=Decimal("0.8580"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("86200"),
        account_balance=Decimal("100000"),
        entry_type="CONFIRM",  # Already have 2.0%, max is 2.25%
        direction="long",
        position_risk_pct=Decimal("0.30"),  # Would exceed
    )

    is_valid, error_msg = add_position_to_campaign(campaign, new_position, Decimal("1.8"))

    assert is_valid is False
    assert "CONFIRM allocation exceeded" in error_msg


def test_add_position_fails_campaign_risk_limit() -> None:
    """Add position fails when campaign 5% limit exceeded."""
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_15",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("4.5"),
        position_count=3,
        positions=[],
        started_at=datetime.now(UTC),
    )

    new_position = ForexPosition(
        symbol="EUR/JPY",
        entry=Decimal("161.50"),
        stop=Decimal("160.50"),
        lot_size=Decimal("1.0"),
        lot_type="standard",
        position_value_usd=Decimal("161500"),
        account_balance=Decimal("100000"),
        entry_type="ADDON",
        direction="long",
        position_risk_pct=Decimal("0.6"),  # 4.5 + 0.6 = 5.1 > 5.0
    )

    is_valid, error_msg = add_position_to_campaign(campaign, new_position, Decimal("1.3"))

    assert is_valid is False
    assert "Campaign risk limit exceeded" in error_msg


# =============================================================================
# TEST DATA MODEL PROPERTIES
# =============================================================================


def test_forex_currency_campaign_properties() -> None:
    """Test ForexCurrencyCampaign calculated properties."""
    start_date = datetime.now(UTC) - timedelta(days=7)
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_08",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.5"),
        position_count=2,
        positions=[],
        started_at=start_date,
    )

    assert campaign.available_capacity_pct == Decimal("1.50")  # 5.0 - 3.5
    assert campaign.risk_utilization_pct == Decimal("70.0")  # 3.5 / 5.0 * 100
    assert campaign.days_active == 7
    assert campaign.is_expired is False  # < 14 days


def test_forex_currency_campaign_expired() -> None:
    """Campaign expired after 14 days."""
    start_date = datetime.now(UTC) - timedelta(days=15)
    campaign = ForexCurrencyCampaign(
        campaign_id="EUR_LONG_2024_03_01",
        currency="EUR",
        direction="LONG",
        total_risk_pct=Decimal("3.0"),
        position_count=2,
        positions=[],
        started_at=start_date,
        expected_completion=start_date + timedelta(days=14),
    )

    assert campaign.is_expired is True
