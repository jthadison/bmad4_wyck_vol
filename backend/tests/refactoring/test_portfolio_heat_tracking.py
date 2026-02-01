"""
Portfolio Heat Tracking Tests (Story 22.14 - AC2)

Tests the portfolio heat calculation and alert system:
- Heat calculation formula: (total_risk / account_equity) * 100
- WARNING threshold at 80% of max (8% when max is 10%)
- CRITICAL threshold at 95% of max (9.5% when max is 10%)
- EXCEEDED threshold at 100% of max (10%)
- Alert rate limiting (5-minute cooldown)
- Heat normalization after position close

These tests validate the IntradayCampaignDetector heat tracking
before refactoring work begins.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.backtesting.intraday_campaign_detector import (
    Campaign,
    CampaignState,
    HeatAlertState,
    IntradayCampaignDetector,
)


class TestPortfolioHeatCalculation:
    """Test portfolio heat calculation formula (AC2)."""

    def test_heat_calculation_formula(self, detector: IntradayCampaignDetector):
        """AC2: Heat = (total_risk / account_equity) * 100."""
        # Create campaign with known risk
        campaign = Campaign(
            campaign_id="heat-test-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            dollar_risk=Decimal("500"),
            timeframe="1h",
        )
        detector._add_to_indexes(campaign)

        # Calculate heat: $500 risk / $10,000 account = 5%
        heat = detector._calculate_portfolio_heat(Decimal("10000"))

        assert heat == Decimal("5.0")

    def test_heat_calculation_multiple_campaigns(self, detector: IntradayCampaignDetector):
        """AC2: Heat should sum risk from all active campaigns."""
        # Add multiple campaigns
        campaigns = [
            Campaign(
                campaign_id="heat-test-1",
                state=CampaignState.ACTIVE,
                position_size=Decimal("100"),
                risk_per_share=Decimal("3.00"),
                dollar_risk=Decimal("300"),
                timeframe="1h",
            ),
            Campaign(
                campaign_id="heat-test-2",
                state=CampaignState.ACTIVE,
                position_size=Decimal("200"),
                risk_per_share=Decimal("2.50"),
                dollar_risk=Decimal("500"),
                timeframe="1h",
            ),
            Campaign(
                campaign_id="heat-test-3",
                state=CampaignState.ACTIVE,
                position_size=Decimal("150"),
                risk_per_share=Decimal("4.00"),
                dollar_risk=Decimal("600"),
                timeframe="1h",
            ),
        ]

        for camp in campaigns:
            detector._add_to_indexes(camp)

        # Total risk: 300 + 500 + 600 = 1400
        # Heat: 1400 / 100000 * 100 = 1.4%
        heat = detector._calculate_portfolio_heat(Decimal("100000"))

        assert heat == Decimal("1.4")

    def test_heat_calculation_includes_forming_and_active_campaigns(
        self, detector: IntradayCampaignDetector
    ):
        """AC2: FORMING and ACTIVE campaigns with positions should contribute to heat."""
        # Add active, forming, and completed campaigns
        active_campaign = Campaign(
            campaign_id="active-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            dollar_risk=Decimal("500"),
            timeframe="1h",
        )
        forming_campaign = Campaign(
            campaign_id="forming-1",
            state=CampaignState.FORMING,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            dollar_risk=Decimal("500"),
            timeframe="1h",
        )
        completed_campaign = Campaign(
            campaign_id="completed-1",
            state=CampaignState.COMPLETED,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            dollar_risk=Decimal("500"),
            timeframe="1h",
        )

        detector._add_to_indexes(active_campaign)
        detector._add_to_indexes(forming_campaign)
        detector._add_to_indexes(completed_campaign)

        # get_active_campaigns() returns both FORMING and ACTIVE campaigns
        # Heat = ($500 + $500) / $10000 = 10%
        heat = detector._calculate_portfolio_heat(Decimal("10000"))

        # FORMING and ACTIVE contribute, COMPLETED does not
        assert heat == Decimal("10.00")

    def test_heat_calculation_zero_account_size(self, detector: IntradayCampaignDetector):
        """AC2: Should handle zero/negative account size gracefully."""
        campaign = Campaign(
            campaign_id="heat-test-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            timeframe="1h",
        )
        detector._add_to_indexes(campaign)

        # Zero account size should return 0
        heat = detector._calculate_portfolio_heat(Decimal("0"))
        assert heat == Decimal("0")

        # Negative account size should return 0
        heat = detector._calculate_portfolio_heat(Decimal("-1000"))
        assert heat == Decimal("0")

    def test_heat_calculation_no_active_campaigns(self, detector: IntradayCampaignDetector):
        """AC2: Should return 0 when no active campaigns."""
        heat = detector._calculate_portfolio_heat(Decimal("100000"))
        assert heat == Decimal("0")


class TestHeatAlertThresholds:
    """Test heat alert state transitions (AC2)."""

    def test_warning_threshold_at_80_percent(self):
        """AC2: WARNING state at 80% of max heat (8% when max=10%)."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # 8% heat should trigger WARNING (80% of 10%)
        detector._check_heat_alerts(8.0)

        assert detector._heat_alert_state == HeatAlertState.WARNING

    def test_critical_threshold_at_95_percent(self):
        """AC2: CRITICAL state at 95% of max heat (9.5% when max=10%)."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # 9.5% heat should trigger CRITICAL (95% of 10%)
        detector._check_heat_alerts(9.5)

        assert detector._heat_alert_state == HeatAlertState.CRITICAL

    def test_exceeded_threshold_at_100_percent(self):
        """AC2: EXCEEDED triggers when heat > max."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # Mock the _check_portfolio_limits to test exceeded
        campaign = Campaign(
            campaign_id="exceeded-test",
            state=CampaignState.ACTIVE,
            position_size=Decimal("1000"),
            risk_per_share=Decimal("15.00"),
            timeframe="1h",
        )
        detector._add_to_indexes(campaign)

        # Verify limits check fails when heat exceeds max
        result = detector._check_portfolio_limits(
            account_size=Decimal("100000"),
            new_campaign_risk=Decimal("1000"),  # Would push over 10%
        )

        # Should fail because 15% + 1% > 10%
        assert result is False

    def test_normal_state_below_75_percent(self):
        """AC2: NORMAL state when below 75% of max heat."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # 5% heat should be NORMAL (below 75% of 10% = 7.5%)
        detector._check_heat_alerts(5.0)

        assert detector._heat_alert_state == HeatAlertState.NORMAL

    def test_transition_zone_maintains_state(self):
        """AC2: 75-80% zone maintains current state (hysteresis)."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # First, get into WARNING state
        detector._check_heat_alerts(8.5)
        assert detector._heat_alert_state == HeatAlertState.WARNING

        # Heat drops to 7.6% (in transition zone 75-80%)
        # Should maintain WARNING state
        detector._check_heat_alerts(7.6)
        assert detector._heat_alert_state == HeatAlertState.WARNING

    def test_state_transition_warning_to_critical(self):
        """AC2: Transition from WARNING to CRITICAL."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # Start at WARNING
        detector._check_heat_alerts(8.0)
        assert detector._heat_alert_state == HeatAlertState.WARNING

        # Move to CRITICAL
        detector._check_heat_alerts(9.5)
        assert detector._heat_alert_state == HeatAlertState.CRITICAL

    def test_state_transition_critical_to_normal(self):
        """AC2: Transition from CRITICAL back to NORMAL."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # Start at CRITICAL
        detector._check_heat_alerts(9.5)
        assert detector._heat_alert_state == HeatAlertState.CRITICAL

        # Drop to NORMAL (below 75%)
        detector._check_heat_alerts(5.0)
        assert detector._heat_alert_state == HeatAlertState.NORMAL


class TestAlertRateLimiting:
    """Test alert rate limiting (5-minute cooldown)."""

    def test_alert_rate_limiting_prevents_duplicate(self):
        """AC2: Same alert should not fire within 5 minutes."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # First alert should fire
        assert detector._should_fire_alert(HeatAlertState.WARNING) is True

        # Record alert time
        detector._last_alert_time[HeatAlertState.WARNING] = datetime.now(UTC)

        # Immediate second alert should be blocked
        assert detector._should_fire_alert(HeatAlertState.WARNING) is False

    def test_alert_fires_after_cooldown(self):
        """AC2: Alert should fire after 5-minute cooldown."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # Record alert from 6 minutes ago
        detector._last_alert_time[HeatAlertState.WARNING] = datetime.now(UTC) - timedelta(minutes=6)

        # Should be allowed to fire again
        assert detector._should_fire_alert(HeatAlertState.WARNING) is True

    def test_different_alert_types_not_rate_limited(self):
        """AC2: Different alert types have independent rate limits."""
        detector = IntradayCampaignDetector(max_portfolio_heat_pct=Decimal("10.0"))

        # Fire WARNING
        detector._last_alert_time[HeatAlertState.WARNING] = datetime.now(UTC)

        # CRITICAL should still be allowed
        assert detector._should_fire_alert(HeatAlertState.CRITICAL) is True


class TestHeatNormalization:
    """Test heat normalization after position changes."""

    def test_heat_decreases_when_campaign_completes(self, detector: IntradayCampaignDetector):
        """AC2: Heat should decrease when campaigns complete."""
        # Add two active campaigns
        campaign1 = Campaign(
            campaign_id="heat-norm-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            timeframe="1h",
        )
        campaign2 = Campaign(
            campaign_id="heat-norm-2",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("5.00"),
            timeframe="1h",
        )
        detector._add_to_indexes(campaign1)
        detector._add_to_indexes(campaign2)

        # Initial heat: $1000 / $10000 = 10%
        initial_heat = detector._calculate_portfolio_heat(Decimal("10000"))
        assert initial_heat == Decimal("10.0")

        # Complete one campaign
        old_state = campaign1.state
        campaign1.state = CampaignState.COMPLETED
        detector._update_indexes(campaign1, old_state)

        # Heat should now be 5%
        final_heat = detector._calculate_portfolio_heat(Decimal("10000"))
        assert final_heat == Decimal("5.0")

    def test_heat_increases_when_campaign_added(self, detector: IntradayCampaignDetector):
        """AC2: Heat should increase when new campaigns are added."""
        # Initial heat: 0%
        initial_heat = detector._calculate_portfolio_heat(Decimal("100000"))
        assert initial_heat == Decimal("0")

        # Add campaign
        campaign = Campaign(
            campaign_id="heat-add-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("50.00"),  # $5000 risk
            timeframe="1h",
        )
        detector._add_to_indexes(campaign)

        # Heat should now be 5%
        final_heat = detector._calculate_portfolio_heat(Decimal("100000"))
        assert final_heat == Decimal("5.0")


class TestHeatAlertStateEnum:
    """Test HeatAlertState enum values."""

    def test_all_heat_states_exist(self):
        """All expected heat alert states should exist."""
        expected_states = ["NORMAL", "WARNING", "CRITICAL", "EXCEEDED"]
        actual_states = [state.value for state in HeatAlertState]

        for state in expected_states:
            assert state in actual_states

    def test_initial_heat_state_is_normal(self, detector: IntradayCampaignDetector):
        """Detector should start in NORMAL heat state."""
        assert detector._heat_alert_state == HeatAlertState.NORMAL


class TestPortfolioLimitsEnforcement:
    """Test portfolio limits enforcement."""

    def test_max_concurrent_campaigns_enforced(self, detector: IntradayCampaignDetector):
        """Should reject new campaigns when max concurrent reached."""
        # Add max campaigns (3)
        for i in range(3):
            campaign = Campaign(
                campaign_id=f"max-test-{i}",
                state=CampaignState.ACTIVE,
                timeframe="1h",
            )
            detector._add_to_indexes(campaign)

        # Should fail to add another
        result = detector._check_portfolio_limits()
        assert result is False

    def test_heat_limit_enforced(self, detector: IntradayCampaignDetector):
        """Should reject new campaigns when heat limit would be exceeded."""
        # Add campaign with high risk
        campaign = Campaign(
            campaign_id="heat-limit-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("90.00"),  # $9000 risk = 9% of $100k
            timeframe="1h",
        )
        detector._add_to_indexes(campaign)

        # Try to add more risk that would exceed 10%
        result = detector._check_portfolio_limits(
            account_size=Decimal("100000"),
            new_campaign_risk=Decimal("2000"),  # Would push to 11%
        )
        assert result is False

    def test_limits_pass_when_under_threshold(self, detector: IntradayCampaignDetector):
        """Should allow new campaigns when under all limits."""
        # Add one campaign
        campaign = Campaign(
            campaign_id="under-limit-1",
            state=CampaignState.ACTIVE,
            position_size=Decimal("100"),
            risk_per_share=Decimal("20.00"),  # $2000 risk = 2% of $100k
            timeframe="1h",
        )
        detector._add_to_indexes(campaign)

        # Should pass limits check
        result = detector._check_portfolio_limits(
            account_size=Decimal("100000"),
            new_campaign_risk=Decimal("2000"),  # Would be 4% total
        )
        assert result is True
