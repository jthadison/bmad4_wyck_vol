"""
Unit tests for CampaignCore model - Story 22.10

Tests the core campaign identity and state tracking functionality.
"""

from datetime import UTC, datetime

from src.models.campaign_core import (
    TERMINAL_STATES,
    CampaignCore,
    CampaignState,
)


class TestCampaignState:
    """Test CampaignState enum."""

    def test_all_states_exist(self):
        """Test all expected states are defined."""
        assert CampaignState.FORMING.value == "FORMING"
        assert CampaignState.ACTIVE.value == "ACTIVE"
        assert CampaignState.DORMANT.value == "DORMANT"
        assert CampaignState.COMPLETED.value == "COMPLETED"
        assert CampaignState.FAILED.value == "FAILED"
        assert CampaignState.CANCELLED.value == "CANCELLED"

    def test_terminal_states(self):
        """Test terminal states are correctly defined."""
        assert CampaignState.COMPLETED in TERMINAL_STATES
        assert CampaignState.FAILED in TERMINAL_STATES
        assert CampaignState.CANCELLED in TERMINAL_STATES
        assert CampaignState.FORMING not in TERMINAL_STATES
        assert CampaignState.ACTIVE not in TERMINAL_STATES
        assert CampaignState.DORMANT not in TERMINAL_STATES


class TestCampaignCoreCreation:
    """Test CampaignCore instantiation."""

    def test_default_creation(self):
        """Test creating CampaignCore with defaults."""
        core = CampaignCore()

        assert core.campaign_id is not None
        assert len(core.campaign_id) > 0
        assert core.symbol == ""
        assert core.state == CampaignState.FORMING
        assert core.timeframe == "1d"
        assert core.asset_class == "stock"
        assert core.patterns == []
        assert core.current_phase is None
        assert core.failure_reason is None
        assert core.end_time is None

    def test_custom_creation(self):
        """Test creating CampaignCore with custom values."""
        start = datetime(2025, 1, 15, 9, 30, tzinfo=UTC)
        core = CampaignCore(
            campaign_id="test-123",
            symbol="AAPL",
            start_time=start,
            state=CampaignState.ACTIVE,
            timeframe="4h",
            asset_class="equity",
            current_phase="C",
        )

        assert core.campaign_id == "test-123"
        assert core.symbol == "AAPL"
        assert core.start_time == start
        assert core.state == CampaignState.ACTIVE
        assert core.timeframe == "4h"
        assert core.asset_class == "equity"
        assert core.current_phase == "C"

    def test_patterns_list_default(self):
        """Test patterns list is a new list for each instance."""
        core1 = CampaignCore()
        core2 = CampaignCore()

        core1.patterns.append("pattern1")

        assert len(core1.patterns) == 1
        assert len(core2.patterns) == 0


class TestCampaignCoreTerminalState:
    """Test is_terminal method."""

    def test_forming_not_terminal(self):
        """Test FORMING state is not terminal."""
        core = CampaignCore(state=CampaignState.FORMING)
        assert core.is_terminal() is False

    def test_active_not_terminal(self):
        """Test ACTIVE state is not terminal."""
        core = CampaignCore(state=CampaignState.ACTIVE)
        assert core.is_terminal() is False

    def test_dormant_not_terminal(self):
        """Test DORMANT state is not terminal."""
        core = CampaignCore(state=CampaignState.DORMANT)
        assert core.is_terminal() is False

    def test_completed_is_terminal(self):
        """Test COMPLETED state is terminal."""
        core = CampaignCore(state=CampaignState.COMPLETED)
        assert core.is_terminal() is True

    def test_failed_is_terminal(self):
        """Test FAILED state is terminal."""
        core = CampaignCore(state=CampaignState.FAILED)
        assert core.is_terminal() is True

    def test_cancelled_is_terminal(self):
        """Test CANCELLED state is terminal."""
        core = CampaignCore(state=CampaignState.CANCELLED)
        assert core.is_terminal() is True


class TestCampaignCoreActionable:
    """Test is_actionable method."""

    def test_active_is_actionable(self):
        """Test ACTIVE state is actionable."""
        core = CampaignCore(state=CampaignState.ACTIVE)
        assert core.is_actionable() is True

    def test_forming_not_actionable(self):
        """Test FORMING state is not actionable."""
        core = CampaignCore(state=CampaignState.FORMING)
        assert core.is_actionable() is False

    def test_completed_not_actionable(self):
        """Test COMPLETED state is not actionable."""
        core = CampaignCore(state=CampaignState.COMPLETED)
        assert core.is_actionable() is False


class TestCampaignCoreTransitions:
    """Test can_transition_to method."""

    def test_forming_to_active_allowed(self):
        """Test FORMING -> ACTIVE transition is allowed."""
        core = CampaignCore(state=CampaignState.FORMING)
        assert core.can_transition_to(CampaignState.ACTIVE) is True

    def test_forming_to_cancelled_allowed(self):
        """Test FORMING -> CANCELLED transition is allowed."""
        core = CampaignCore(state=CampaignState.FORMING)
        assert core.can_transition_to(CampaignState.CANCELLED) is True

    def test_forming_to_failed_allowed(self):
        """Test FORMING -> FAILED transition is allowed."""
        core = CampaignCore(state=CampaignState.FORMING)
        assert core.can_transition_to(CampaignState.FAILED) is True

    def test_forming_to_completed_not_allowed(self):
        """Test FORMING -> COMPLETED transition is not allowed."""
        core = CampaignCore(state=CampaignState.FORMING)
        assert core.can_transition_to(CampaignState.COMPLETED) is False

    def test_active_to_completed_allowed(self):
        """Test ACTIVE -> COMPLETED transition is allowed."""
        core = CampaignCore(state=CampaignState.ACTIVE)
        assert core.can_transition_to(CampaignState.COMPLETED) is True

    def test_active_to_failed_allowed(self):
        """Test ACTIVE -> FAILED transition is allowed."""
        core = CampaignCore(state=CampaignState.ACTIVE)
        assert core.can_transition_to(CampaignState.FAILED) is True

    def test_active_to_dormant_allowed(self):
        """Test ACTIVE -> DORMANT transition is allowed."""
        core = CampaignCore(state=CampaignState.ACTIVE)
        assert core.can_transition_to(CampaignState.DORMANT) is True

    def test_dormant_to_active_allowed(self):
        """Test DORMANT -> ACTIVE transition is allowed."""
        core = CampaignCore(state=CampaignState.DORMANT)
        assert core.can_transition_to(CampaignState.ACTIVE) is True

    def test_completed_to_any_not_allowed(self):
        """Test terminal COMPLETED cannot transition."""
        core = CampaignCore(state=CampaignState.COMPLETED)
        assert core.can_transition_to(CampaignState.ACTIVE) is False
        assert core.can_transition_to(CampaignState.FORMING) is False
        assert core.can_transition_to(CampaignState.FAILED) is False

    def test_failed_to_any_not_allowed(self):
        """Test terminal FAILED cannot transition."""
        core = CampaignCore(state=CampaignState.FAILED)
        assert core.can_transition_to(CampaignState.ACTIVE) is False
        assert core.can_transition_to(CampaignState.COMPLETED) is False


class TestCampaignCoreProperties:
    """Test CampaignCore computed properties."""

    def test_pattern_count_empty(self):
        """Test pattern_count with no patterns."""
        core = CampaignCore()
        assert core.pattern_count == 0

    def test_pattern_count_with_patterns(self):
        """Test pattern_count with patterns."""
        core = CampaignCore()
        core.patterns = ["p1", "p2", "p3"]
        assert core.pattern_count == 3

    def test_duration_seconds_no_end_time(self):
        """Test duration_seconds returns None without end_time."""
        core = CampaignCore()
        assert core.duration_seconds is None

    def test_duration_seconds_with_end_time(self):
        """Test duration_seconds calculation."""
        start = datetime(2025, 1, 15, 9, 0, tzinfo=UTC)
        end = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)

        core = CampaignCore(start_time=start, end_time=end)

        assert core.duration_seconds == 3600.0  # 1 hour

    def test_duration_seconds_multi_day(self):
        """Test duration_seconds for multi-day campaign."""
        start = datetime(2025, 1, 15, 9, 0, tzinfo=UTC)
        end = datetime(2025, 1, 17, 9, 0, tzinfo=UTC)

        core = CampaignCore(start_time=start, end_time=end)

        assert core.duration_seconds == 2 * 24 * 3600.0  # 2 days
