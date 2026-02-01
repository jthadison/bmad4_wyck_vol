"""
Portfolio Heat Tracker Unit Tests - Story 22.5

Tests the PortfolioHeatTracker class:
- Heat calculation formula: (total_risk / account_equity) * 100
- Alert state transitions (NORMAL, WARNING, CRITICAL, EXCEEDED)
- Rate limiting for duplicate alerts
- Position blocking when heat exceeds limit

Coverage target: ≥95%
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.risk_management.portfolio_heat_tracker import (
    HeatAlertState,
    HeatThresholds,
    PortfolioHeatTracker,
)


class TestPortfolioHeatTrackerInit:
    """Test PortfolioHeatTracker initialization."""

    def test_default_initialization(self):
        """Tracker should initialize with default thresholds."""
        tracker = PortfolioHeatTracker()

        assert tracker._thresholds.warning_pct == 7.0
        assert tracker._thresholds.critical_pct == 9.0
        assert tracker._thresholds.exceeded_pct == 10.0
        assert tracker._thresholds.alert_cooldown_seconds == 300
        assert tracker.current_state == HeatAlertState.NORMAL

    def test_custom_thresholds(self):
        """Tracker should accept custom thresholds."""
        thresholds = HeatThresholds(
            warning_pct=5.0,
            critical_pct=8.0,
            exceeded_pct=12.0,
            alert_cooldown_seconds=600,
        )
        tracker = PortfolioHeatTracker(thresholds=thresholds)

        assert tracker._thresholds.warning_pct == 5.0
        assert tracker._thresholds.critical_pct == 8.0
        assert tracker._thresholds.exceeded_pct == 12.0
        assert tracker._thresholds.alert_cooldown_seconds == 600

    def test_state_change_callback(self):
        """Tracker should accept state change callback."""
        callback = MagicMock()
        tracker = PortfolioHeatTracker(on_state_change=callback)

        assert tracker._on_state_change == callback


class TestCampaignRiskManagement:
    """Test campaign risk add/remove operations."""

    def test_add_campaign_risk(self):
        """Should add campaign risk correctly."""
        tracker = PortfolioHeatTracker()

        tracker.add_campaign_risk("c1", 5000.0)

        assert tracker.get_total_risk() == 5000.0
        assert tracker.get_campaign_count() == 1

    def test_add_multiple_campaign_risks(self):
        """Should sum risks from multiple campaigns."""
        tracker = PortfolioHeatTracker()

        tracker.add_campaign_risk("c1", 5000.0)
        tracker.add_campaign_risk("c2", 3000.0)
        tracker.add_campaign_risk("c3", 2000.0)

        assert tracker.get_total_risk() == 10000.0
        assert tracker.get_campaign_count() == 3

    def test_update_existing_campaign_risk(self):
        """Should update risk if campaign ID already exists."""
        tracker = PortfolioHeatTracker()

        tracker.add_campaign_risk("c1", 5000.0)
        tracker.add_campaign_risk("c1", 8000.0)  # Update

        assert tracker.get_total_risk() == 8000.0
        assert tracker.get_campaign_count() == 1

    def test_remove_campaign_risk(self):
        """Should remove campaign risk correctly."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)
        tracker.add_campaign_risk("c2", 3000.0)

        removed = tracker.remove_campaign_risk("c1")

        assert removed == 5000.0
        assert tracker.get_total_risk() == 3000.0
        assert tracker.get_campaign_count() == 1

    def test_remove_nonexistent_campaign(self):
        """Should return 0 when removing nonexistent campaign."""
        tracker = PortfolioHeatTracker()

        removed = tracker.remove_campaign_risk("nonexistent")

        assert removed == 0.0

    def test_clear_tracker(self):
        """Clear should reset all state."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)
        tracker.add_campaign_risk("c2", 3000.0)

        tracker.clear()

        assert tracker.get_total_risk() == 0.0
        assert tracker.get_campaign_count() == 0
        assert tracker.current_state == HeatAlertState.NORMAL


class TestHeatCalculation:
    """Test heat calculation formula (AC2)."""

    def test_heat_calculation_formula(self):
        """AC2: Heat = (total_risk / account_equity) * 100."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)

        heat = tracker.calculate_heat(100_000.0)

        assert heat == 5.0  # $5,000 / $100,000 = 5%

    def test_heat_calculation_multiple_campaigns(self):
        """AC2: Heat should sum risk from all campaigns."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 3000.0)
        tracker.add_campaign_risk("c2", 5000.0)

        heat = tracker.calculate_heat(100_000.0)

        assert heat == 8.0  # $8,000 / $100,000 = 8%

    def test_heat_calculation_zero_equity(self):
        """Should return 100% for zero equity."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)

        heat = tracker.calculate_heat(0.0)

        assert heat == 100.0

    def test_heat_calculation_negative_equity(self):
        """Should return 100% for negative equity."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)

        heat = tracker.calculate_heat(-1000.0)

        assert heat == 100.0

    def test_heat_calculation_no_risk(self):
        """Should return 0% when no risk."""
        tracker = PortfolioHeatTracker()

        heat = tracker.calculate_heat(100_000.0)

        assert heat == 0.0

    def test_heat_calculation_rounding(self):
        """Should round to 2 decimal places."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 3333.0)

        heat = tracker.calculate_heat(100_000.0)

        assert heat == 3.33  # 3.333... rounded to 3.33


class TestAlertStateTransitions:
    """Test heat alert state transitions (AC3)."""

    def test_normal_state_below_7_percent(self):
        """AC3: NORMAL state when heat < 7%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)

        state = tracker.get_alert_state(100_000.0)  # 5%

        assert state == HeatAlertState.NORMAL

    def test_warning_state_at_7_percent(self):
        """AC3: WARNING state when heat >= 7%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 7500.0)

        state = tracker.get_alert_state(100_000.0)  # 7.5%

        assert state == HeatAlertState.WARNING

    def test_warning_state_below_9_percent(self):
        """AC3: WARNING state when 7% <= heat < 9%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 8500.0)

        state = tracker.get_alert_state(100_000.0)  # 8.5%

        assert state == HeatAlertState.WARNING

    def test_critical_state_at_9_percent(self):
        """AC3: CRITICAL state when heat >= 9%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 9500.0)

        state = tracker.get_alert_state(100_000.0)  # 9.5%

        assert state == HeatAlertState.CRITICAL

    def test_critical_state_below_10_percent(self):
        """AC3: CRITICAL state when 9% <= heat < 10%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 9900.0)

        state = tracker.get_alert_state(100_000.0)  # 9.9%

        assert state == HeatAlertState.CRITICAL

    def test_exceeded_state_at_10_percent(self):
        """AC3: EXCEEDED state when heat >= 10%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 10000.0)

        state = tracker.get_alert_state(100_000.0)  # 10%

        assert state == HeatAlertState.EXCEEDED

    def test_exceeded_state_above_10_percent(self):
        """AC3: EXCEEDED state when heat > 10%."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 15000.0)

        state = tracker.get_alert_state(100_000.0)  # 15%

        assert state == HeatAlertState.EXCEEDED

    def test_state_change_callback_fired(self):
        """Callback should be fired on state change."""
        callback = MagicMock()
        tracker = PortfolioHeatTracker(on_state_change=callback)

        # Initial state is NORMAL
        tracker.add_campaign_risk("c1", 8000.0)
        tracker.get_alert_state(100_000.0)  # Triggers WARNING

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == HeatAlertState.NORMAL  # old state
        assert args[1] == HeatAlertState.WARNING  # new state
        assert args[2] == 8.0  # heat pct

    def test_callback_not_fired_if_state_unchanged(self):
        """Callback should not fire if state doesn't change."""
        callback = MagicMock()
        tracker = PortfolioHeatTracker(on_state_change=callback)
        tracker.add_campaign_risk("c1", 5000.0)

        # Both calls result in NORMAL
        tracker.get_alert_state(100_000.0)
        tracker.get_alert_state(100_000.0)

        callback.assert_not_called()

    def test_boundary_at_exactly_7_percent(self):
        """Boundary test: exactly 7% should be WARNING."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 7000.0)

        state = tracker.get_alert_state(100_000.0)

        assert state == HeatAlertState.WARNING

    def test_boundary_at_exactly_9_percent(self):
        """Boundary test: exactly 9% should be CRITICAL."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 9000.0)

        state = tracker.get_alert_state(100_000.0)

        assert state == HeatAlertState.CRITICAL


class TestRateLimiting:
    """Test alert rate limiting (AC4)."""

    def test_first_alert_should_fire(self):
        """First alert for a state should always fire."""
        tracker = PortfolioHeatTracker()

        result = tracker.should_send_alert(HeatAlertState.WARNING)

        assert result is True

    def test_immediate_duplicate_blocked(self):
        """Duplicate alert within cooldown should be blocked."""
        tracker = PortfolioHeatTracker()

        # First alert fires
        tracker.should_send_alert(HeatAlertState.WARNING)

        # Immediate duplicate blocked
        result = tracker.should_send_alert(HeatAlertState.WARNING)

        assert result is False

    def test_alert_allowed_after_cooldown(self):
        """Alert should be allowed after cooldown expires."""
        tracker = PortfolioHeatTracker()

        # Fire alert and backdate it
        tracker.should_send_alert(HeatAlertState.WARNING)
        tracker._last_alert_times[HeatAlertState.WARNING] = datetime.now(UTC) - timedelta(minutes=6)

        # Should be allowed now
        result = tracker.should_send_alert(HeatAlertState.WARNING)

        assert result is True

    def test_different_states_independent_rate_limiting(self):
        """Different alert states have independent rate limits."""
        tracker = PortfolioHeatTracker()

        # Fire WARNING alert
        tracker.should_send_alert(HeatAlertState.WARNING)

        # CRITICAL should still be allowed
        result = tracker.should_send_alert(HeatAlertState.CRITICAL)

        assert result is True

    def test_normal_state_never_fires_alert(self):
        """NORMAL state should never trigger an alert."""
        tracker = PortfolioHeatTracker()

        result = tracker.should_send_alert(HeatAlertState.NORMAL)

        assert result is False

    def test_custom_cooldown_period(self):
        """Should respect custom cooldown period."""
        thresholds = HeatThresholds(alert_cooldown_seconds=60)  # 1 minute
        tracker = PortfolioHeatTracker(thresholds=thresholds)

        # Fire alert and backdate it by 2 minutes
        tracker.should_send_alert(HeatAlertState.WARNING)
        tracker._last_alert_times[HeatAlertState.WARNING] = datetime.now(UTC) - timedelta(minutes=2)

        # Should be allowed (2 min > 1 min cooldown)
        result = tracker.should_send_alert(HeatAlertState.WARNING)

        assert result is True


class TestPositionBlocking:
    """Test position blocking when heat exceeds limit (AC3)."""

    def test_can_add_position_when_under_limit(self):
        """Should allow position when projected heat under limit."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)

        # Adding $2000 would bring to 7% (under 10%)
        result = tracker.can_add_position(2000.0, 100_000.0)

        assert result is True

    def test_cannot_add_position_when_exceeds_limit(self):
        """Should block position when projected heat exceeds limit."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 9000.0)

        # Adding $1500 would bring to 10.5% (over 10%)
        result = tracker.can_add_position(1500.0, 100_000.0)

        assert result is False

    def test_cannot_add_position_at_exactly_limit(self):
        """Should block position when projected heat equals limit."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 9000.0)

        # Adding $1000 would bring to exactly 10%
        result = tracker.can_add_position(1000.0, 100_000.0)

        assert result is False

    def test_cannot_add_position_with_zero_equity(self):
        """Should block position with zero equity."""
        tracker = PortfolioHeatTracker()

        result = tracker.can_add_position(1000.0, 0.0)

        assert result is False

    def test_can_add_position_with_no_existing_risk(self):
        """Should allow position when no existing risk."""
        tracker = PortfolioHeatTracker()

        # Adding $5000 would be 5% (under 10%)
        result = tracker.can_add_position(5000.0, 100_000.0)

        assert result is True


class TestHeatSummary:
    """Test heat summary method."""

    def test_heat_summary_contents(self):
        """Summary should contain all expected fields."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 5000.0)
        tracker.add_campaign_risk("c2", 3000.0)

        summary = tracker.get_heat_summary(100_000.0)

        assert summary["heat_pct"] == 8.0
        assert summary["total_risk"] == 8000.0
        assert summary["campaign_count"] == 2
        assert summary["state"] == "WARNING"
        assert summary["can_add_position"] is True
        assert summary["thresholds"]["warning"] == 7.0
        assert summary["thresholds"]["critical"] == 9.0
        assert summary["thresholds"]["exceeded"] == 10.0

    def test_heat_summary_exceeded_state(self):
        """Summary should show can_add_position=False when exceeded."""
        tracker = PortfolioHeatTracker()
        tracker.add_campaign_risk("c1", 15000.0)

        summary = tracker.get_heat_summary(100_000.0)

        assert summary["state"] == "EXCEEDED"
        assert summary["can_add_position"] is False


class TestHeatThresholds:
    """Test HeatThresholds dataclass."""

    def test_default_thresholds(self):
        """Should have correct default values."""
        thresholds = HeatThresholds()

        assert thresholds.warning_pct == 7.0
        assert thresholds.critical_pct == 9.0
        assert thresholds.exceeded_pct == 10.0
        assert thresholds.alert_cooldown_seconds == 300

    def test_custom_thresholds(self):
        """Should accept custom values."""
        thresholds = HeatThresholds(
            warning_pct=5.0,
            critical_pct=7.0,
            exceeded_pct=8.0,
            alert_cooldown_seconds=120,
        )

        assert thresholds.warning_pct == 5.0
        assert thresholds.critical_pct == 7.0
        assert thresholds.exceeded_pct == 8.0
        assert thresholds.alert_cooldown_seconds == 120


class TestHeatAlertStateEnum:
    """Test HeatAlertState enum."""

    def test_all_states_exist(self):
        """All expected states should exist."""
        expected = ["NORMAL", "WARNING", "CRITICAL", "EXCEEDED"]
        actual = [state.value for state in HeatAlertState]

        for state in expected:
            assert state in actual

    def test_state_values(self):
        """States should have correct string values."""
        assert HeatAlertState.NORMAL.value == "NORMAL"
        assert HeatAlertState.WARNING.value == "WARNING"
        assert HeatAlertState.CRITICAL.value == "CRITICAL"
        assert HeatAlertState.EXCEEDED.value == "EXCEEDED"
