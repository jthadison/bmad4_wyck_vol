"""
Unit Tests for Campaign State Manager Lifecycle - Story 22.4

Purpose:
--------
Comprehensive test coverage for CampaignStateManager including:
- State transitions (FORMING → ACTIVE → COMPLETED/FAILED)
- Index management operations
- State validation and guards
- Edge cases and error handling

Target Coverage: 95%+

Author: Story 22.4 Implementation
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.campaign_state_manager import (
    VALID_TRANSITIONS,
    CampaignStateManager,
    StateTransitionError,
)
from src.backtesting.intraday_campaign_detector import Campaign, CampaignState
from src.models.ohlcv import OHLCVBar
from src.models.spring import Spring
from src.models.wyckoff_phase import WyckoffPhase

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def state_manager() -> CampaignStateManager:
    """Create a fresh CampaignStateManager instance."""
    return CampaignStateManager()


@pytest.fixture
def sample_ohlcv_bar() -> OHLCVBar:
    """Create a sample OHLCVBar for testing."""
    return OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        volume=1000000,
        spread=Decimal("3.00"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_spring_pattern(sample_ohlcv_bar: OHLCVBar) -> Spring:
    """Create a sample Spring pattern for testing."""
    return Spring(
        bar=sample_ohlcv_bar,
        bar_index=50,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("150.00"),
        spring_low=Decimal("147.00"),
        recovery_price=Decimal("151.00"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
    )


@pytest.fixture
def forming_campaign(sample_spring_pattern: Spring) -> Campaign:
    """Create a Campaign in FORMING state."""
    return Campaign(
        campaign_id=f"test-forming-{uuid4().hex[:8]}",
        start_time=datetime.now(UTC) - timedelta(hours=24),
        patterns=[sample_spring_pattern],
        state=CampaignState.FORMING,
        current_phase=WyckoffPhase.C,
        support_level=Decimal("148.00"),
        resistance_level=Decimal("155.00"),
        strength_score=0.85,
        risk_per_share=Decimal("3.00"),
        range_width_pct=Decimal("4.73"),
        timeframe="1h",
    )


@pytest.fixture
def active_campaign(sample_spring_pattern: Spring) -> Campaign:
    """Create a Campaign in ACTIVE state."""
    return Campaign(
        campaign_id=f"test-active-{uuid4().hex[:8]}",
        start_time=datetime.now(UTC) - timedelta(hours=24),
        patterns=[sample_spring_pattern],
        state=CampaignState.ACTIVE,
        current_phase=WyckoffPhase.D,
        support_level=Decimal("148.00"),
        resistance_level=Decimal("155.00"),
        strength_score=0.80,
        risk_per_share=Decimal("3.00"),
        range_width_pct=Decimal("4.73"),
        position_size=Decimal("100"),
        dollar_risk=Decimal("300"),
        timeframe="1h",
    )


@pytest.fixture
def dormant_campaign(sample_spring_pattern: Spring) -> Campaign:
    """Create a Campaign in DORMANT state."""
    return Campaign(
        campaign_id=f"test-dormant-{uuid4().hex[:8]}",
        start_time=datetime.now(UTC) - timedelta(hours=48),
        patterns=[sample_spring_pattern],
        state=CampaignState.DORMANT,
        current_phase=WyckoffPhase.C,
        support_level=Decimal("148.00"),
        resistance_level=Decimal("155.00"),
        strength_score=0.75,
        risk_per_share=Decimal("3.00"),
        range_width_pct=Decimal("4.73"),
        timeframe="4h",
    )


# ============================================================================
# Test CampaignStateManager Initialization
# ============================================================================


class TestCampaignStateManagerInit:
    """Test CampaignStateManager initialization."""

    def test_init_creates_empty_indexes(self):
        """State manager should initialize with empty indexes."""
        manager = CampaignStateManager()

        assert manager.campaign_count == 0
        assert len(manager._campaigns_by_id) == 0
        assert len(manager._active_time_windows) == 0

    def test_init_multiple_instances_isolated(self):
        """Multiple state manager instances should be isolated."""
        manager1 = CampaignStateManager()
        manager2 = CampaignStateManager()

        # Modifying one should not affect the other
        manager1._campaigns_by_id["test"] = "value"  # type: ignore

        assert "test" not in manager2._campaigns_by_id


# ============================================================================
# Test Campaign Registration
# ============================================================================


class TestCampaignRegistration:
    """Test campaign registration and unregistration."""

    def test_register_campaign_adds_to_indexes(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """Registering a campaign should add it to all indexes."""
        state_manager.register_campaign(forming_campaign)

        assert state_manager.campaign_count == 1
        assert forming_campaign.campaign_id in state_manager._campaigns_by_id
        # State manager uses string keys for state indexes
        assert forming_campaign.campaign_id in state_manager._campaigns_by_state["FORMING"]
        assert forming_campaign.campaign_id in state_manager._campaigns_by_timeframe["1h"]

    def test_register_active_campaign_tracks_time_windows(
        self, state_manager: CampaignStateManager, active_campaign: Campaign
    ):
        """Active campaigns should be tracked in time windows."""
        state_manager.register_campaign(active_campaign)

        assert active_campaign.campaign_id in state_manager._active_time_windows
        assert state_manager._active_time_windows[active_campaign.campaign_id] is True

    def test_register_forming_campaign_not_in_time_windows(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """Forming campaigns should not be in active time windows."""
        state_manager.register_campaign(forming_campaign)

        assert forming_campaign.campaign_id not in state_manager._active_time_windows

    def test_register_duplicate_campaign_raises_error(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """Registering same campaign twice should raise ValueError."""
        state_manager.register_campaign(forming_campaign)

        with pytest.raises(ValueError, match="already registered"):
            state_manager.register_campaign(forming_campaign)

    def test_unregister_campaign_removes_from_all_indexes(
        self, state_manager: CampaignStateManager, active_campaign: Campaign
    ):
        """Unregistering should remove campaign from all indexes."""
        state_manager.register_campaign(active_campaign)

        removed = state_manager.unregister_campaign(active_campaign.campaign_id)

        assert removed is active_campaign
        assert state_manager.campaign_count == 0
        assert active_campaign.campaign_id not in state_manager._campaigns_by_id
        assert (
            active_campaign.campaign_id
            not in state_manager._campaigns_by_state[CampaignState.ACTIVE]
        )
        assert active_campaign.campaign_id not in state_manager._active_time_windows

    def test_unregister_nonexistent_campaign_returns_none(
        self, state_manager: CampaignStateManager
    ):
        """Unregistering nonexistent campaign should return None."""
        result = state_manager.unregister_campaign("nonexistent-id")

        assert result is None


# ============================================================================
# Test State Transitions
# ============================================================================


class TestStateTransitions:
    """Test state transition validation and execution."""

    def test_transition_forming_to_active(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """FORMING → ACTIVE should be valid transition."""
        state_manager.register_campaign(forming_campaign)

        state_manager.transition_to(
            forming_campaign.campaign_id,
            CampaignState.ACTIVE,
            reason="All required patterns detected",
        )

        assert forming_campaign.state == CampaignState.ACTIVE
        # State manager uses string keys for state indexes
        assert forming_campaign.campaign_id in state_manager._campaigns_by_state["ACTIVE"]
        assert forming_campaign.campaign_id not in state_manager._campaigns_by_state["FORMING"]
        assert forming_campaign.campaign_id in state_manager._active_time_windows

    def test_transition_active_to_completed(
        self, state_manager: CampaignStateManager, active_campaign: Campaign
    ):
        """ACTIVE → COMPLETED should be valid transition."""
        state_manager.register_campaign(active_campaign)

        state_manager.transition_to(
            active_campaign.campaign_id,
            CampaignState.COMPLETED,
            reason="Target hit",
        )

        assert active_campaign.state == CampaignState.COMPLETED
        # State manager uses string keys for state indexes
        assert active_campaign.campaign_id in state_manager._campaigns_by_state["COMPLETED"]
        assert active_campaign.campaign_id not in state_manager._active_time_windows

    def test_transition_active_to_failed(
        self, state_manager: CampaignStateManager, active_campaign: Campaign
    ):
        """ACTIVE → FAILED should be valid transition."""
        state_manager.register_campaign(active_campaign)

        state_manager.transition_to(
            active_campaign.campaign_id,
            CampaignState.FAILED,
            reason="Stop loss triggered",
        )

        assert active_campaign.state == CampaignState.FAILED
        # State manager uses string keys for state indexes
        assert active_campaign.campaign_id in state_manager._campaigns_by_state["FAILED"]

    def test_transition_forming_to_failed(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """FORMING → FAILED should be valid transition (e.g., on expiration)."""
        state_manager.register_campaign(forming_campaign)

        state_manager.transition_to(
            forming_campaign.campaign_id,
            CampaignState.FAILED,
            reason="Expired before activation",
        )

        assert forming_campaign.state == CampaignState.FAILED

    def test_transition_from_terminal_state_raises_error(
        self, state_manager: CampaignStateManager, active_campaign: Campaign
    ):
        """Transition from terminal state should raise StateTransitionError."""
        state_manager.register_campaign(active_campaign)
        state_manager.transition_to(active_campaign.campaign_id, CampaignState.COMPLETED)

        with pytest.raises(StateTransitionError) as exc_info:
            state_manager.transition_to(active_campaign.campaign_id, CampaignState.ACTIVE)

        # StateTransitionError stores string values for states
        assert exc_info.value.current_state == "COMPLETED"
        assert exc_info.value.target_state == "ACTIVE"
        assert active_campaign.campaign_id in str(exc_info.value)

    def test_transition_invalid_forming_to_completed(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """FORMING → COMPLETED (direct) should raise StateTransitionError."""
        state_manager.register_campaign(forming_campaign)

        with pytest.raises(StateTransitionError):
            state_manager.transition_to(forming_campaign.campaign_id, CampaignState.COMPLETED)

    def test_transition_nonexistent_campaign_raises_key_error(
        self, state_manager: CampaignStateManager
    ):
        """Transitioning nonexistent campaign should raise KeyError."""
        with pytest.raises(KeyError, match="not found"):
            state_manager.transition_to("nonexistent-id", CampaignState.ACTIVE)

    def test_transition_dormant_to_active(
        self, state_manager: CampaignStateManager, dormant_campaign: Campaign
    ):
        """DORMANT → ACTIVE should be valid (reactivation with new patterns)."""
        state_manager.register_campaign(dormant_campaign)

        state_manager.transition_to(
            dormant_campaign.campaign_id,
            CampaignState.ACTIVE,
            reason="New pattern detected",
        )

        assert dormant_campaign.state == CampaignState.ACTIVE
        assert dormant_campaign.campaign_id in state_manager._active_time_windows


# ============================================================================
# Test can_transition_to
# ============================================================================


class TestCanTransitionTo:
    """Test transition validation queries."""

    def test_can_transition_forming_to_active(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """Should return True for valid FORMING → ACTIVE."""
        state_manager.register_campaign(forming_campaign)

        assert state_manager.can_transition_to(forming_campaign.campaign_id, CampaignState.ACTIVE)

    def test_cannot_transition_completed_to_active(
        self, state_manager: CampaignStateManager, active_campaign: Campaign
    ):
        """Should return False for invalid COMPLETED → ACTIVE."""
        state_manager.register_campaign(active_campaign)
        state_manager.transition_to(active_campaign.campaign_id, CampaignState.COMPLETED)

        assert not state_manager.can_transition_to(
            active_campaign.campaign_id, CampaignState.ACTIVE
        )

    def test_cannot_transition_nonexistent_campaign(self, state_manager: CampaignStateManager):
        """Should return False for nonexistent campaign."""
        assert not state_manager.can_transition_to("nonexistent-id", CampaignState.ACTIVE)


# ============================================================================
# Test is_terminal_state
# ============================================================================


class TestIsTerminalState:
    """Test terminal state detection."""

    def test_completed_is_terminal(self, state_manager: CampaignStateManager):
        """COMPLETED should be terminal."""
        assert state_manager.is_terminal_state(CampaignState.COMPLETED)

    def test_failed_is_terminal(self, state_manager: CampaignStateManager):
        """FAILED should be terminal."""
        assert state_manager.is_terminal_state(CampaignState.FAILED)

    def test_cancelled_string_is_terminal(self, state_manager: CampaignStateManager):
        """CANCELLED (string) should be terminal."""
        # Note: CampaignState enum doesn't have CANCELLED, but the manager supports it via string
        assert state_manager.is_terminal_state("CANCELLED")

    def test_forming_is_not_terminal(self, state_manager: CampaignStateManager):
        """FORMING should not be terminal."""
        assert not state_manager.is_terminal_state(CampaignState.FORMING)

    def test_active_is_not_terminal(self, state_manager: CampaignStateManager):
        """ACTIVE should not be terminal."""
        assert not state_manager.is_terminal_state(CampaignState.ACTIVE)

    def test_dormant_is_not_terminal(self, state_manager: CampaignStateManager):
        """DORMANT should not be terminal."""
        assert not state_manager.is_terminal_state(CampaignState.DORMANT)


# ============================================================================
# Test Query Methods
# ============================================================================


class TestQueryMethods:
    """Test campaign query methods."""

    def test_get_campaign_returns_campaign(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """get_campaign should return registered campaign."""
        state_manager.register_campaign(forming_campaign)

        result = state_manager.get_campaign(forming_campaign.campaign_id)

        assert result is forming_campaign

    def test_get_campaign_returns_none_for_nonexistent(self, state_manager: CampaignStateManager):
        """get_campaign should return None for nonexistent campaign."""
        result = state_manager.get_campaign("nonexistent-id")

        assert result is None

    def test_get_campaigns_by_state(
        self,
        state_manager: CampaignStateManager,
        forming_campaign: Campaign,
        active_campaign: Campaign,
    ):
        """get_campaigns_by_state should return correct campaigns."""
        state_manager.register_campaign(forming_campaign)
        state_manager.register_campaign(active_campaign)

        forming_ids = state_manager.get_campaigns_by_state(CampaignState.FORMING)
        active_ids = state_manager.get_campaigns_by_state(CampaignState.ACTIVE)

        assert forming_campaign.campaign_id in forming_ids
        assert active_campaign.campaign_id in active_ids
        assert forming_campaign.campaign_id not in active_ids

    def test_get_campaigns_by_state_returns_copy(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """get_campaigns_by_state should return a copy (prevent mutation)."""
        state_manager.register_campaign(forming_campaign)

        result = state_manager.get_campaigns_by_state(CampaignState.FORMING)
        result.add("mutated-id")

        # Original should be unaffected
        assert "mutated-id" not in state_manager._campaigns_by_state[CampaignState.FORMING]

    def test_get_campaigns_by_timeframe(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """get_campaigns_by_timeframe should return correct campaigns."""
        state_manager.register_campaign(forming_campaign)

        result = state_manager.get_campaigns_by_timeframe("1h")

        assert forming_campaign.campaign_id in result

    def test_get_active_campaign_ids(
        self,
        state_manager: CampaignStateManager,
        forming_campaign: Campaign,
        active_campaign: Campaign,
    ):
        """get_active_campaign_ids should return only active campaigns."""
        state_manager.register_campaign(forming_campaign)
        state_manager.register_campaign(active_campaign)

        result = state_manager.get_active_campaign_ids()

        assert active_campaign.campaign_id in result
        assert forming_campaign.campaign_id not in result

    def test_get_all_campaigns(
        self,
        state_manager: CampaignStateManager,
        forming_campaign: Campaign,
        active_campaign: Campaign,
    ):
        """get_all_campaigns should return all registered campaigns."""
        state_manager.register_campaign(forming_campaign)
        state_manager.register_campaign(active_campaign)

        result = state_manager.get_all_campaigns()

        assert len(result) == 2
        assert forming_campaign in result
        assert active_campaign in result


# ============================================================================
# Test Index Management
# ============================================================================


class TestIndexManagement:
    """Test internal index management operations."""

    def test_update_indexes_for_state_change(
        self, state_manager: CampaignStateManager, forming_campaign: Campaign
    ):
        """_update_indexes_for_state_change should sync indexes after external state change."""
        state_manager.register_campaign(forming_campaign)

        # Simulate external state change
        old_state = forming_campaign.state
        forming_campaign.state = CampaignState.ACTIVE

        # Update indexes
        state_manager._update_indexes_for_state_change(forming_campaign, old_state)

        # State manager uses string keys for state indexes
        assert forming_campaign.campaign_id in state_manager._campaigns_by_state["ACTIVE"]
        assert forming_campaign.campaign_id not in state_manager._campaigns_by_state["FORMING"]
        assert forming_campaign.campaign_id in state_manager._active_time_windows

    def test_rebuild_indexes_recovers_state(
        self,
        state_manager: CampaignStateManager,
        forming_campaign: Campaign,
        active_campaign: Campaign,
    ):
        """rebuild_indexes should reconstruct all secondary indexes."""
        state_manager.register_campaign(forming_campaign)
        state_manager.register_campaign(active_campaign)

        # Corrupt indexes
        state_manager._campaigns_by_state.clear()
        state_manager._active_time_windows.clear()

        # Rebuild
        state_manager.rebuild_indexes()

        # Verify recovered - state manager uses string keys
        assert forming_campaign.campaign_id in state_manager._campaigns_by_state["FORMING"]
        assert active_campaign.campaign_id in state_manager._campaigns_by_state["ACTIVE"]
        assert active_campaign.campaign_id in state_manager._active_time_windows

    def test_clear_removes_all_data(
        self,
        state_manager: CampaignStateManager,
        forming_campaign: Campaign,
        active_campaign: Campaign,
    ):
        """clear should remove all campaigns and indexes."""
        state_manager.register_campaign(forming_campaign)
        state_manager.register_campaign(active_campaign)

        state_manager.clear()

        assert state_manager.campaign_count == 0
        assert len(state_manager._campaigns_by_state) == 0
        assert len(state_manager._active_time_windows) == 0


# ============================================================================
# Test Bulk Operations
# ============================================================================


class TestBulkOperations:
    """Test bulk operation methods."""

    def test_get_state_summary(
        self,
        state_manager: CampaignStateManager,
        forming_campaign: Campaign,
        active_campaign: Campaign,
        dormant_campaign: Campaign,
    ):
        """get_state_summary should return counts by state."""
        state_manager.register_campaign(forming_campaign)
        state_manager.register_campaign(active_campaign)
        state_manager.register_campaign(dormant_campaign)

        summary = state_manager.get_state_summary()

        assert summary["FORMING"] == 1
        assert summary["ACTIVE"] == 1
        assert summary["DORMANT"] == 1


# ============================================================================
# Test StateTransitionError
# ============================================================================


class TestStateTransitionError:
    """Test StateTransitionError exception."""

    def test_error_contains_states(self):
        """Error should contain current and target states."""
        error = StateTransitionError(CampaignState.COMPLETED, CampaignState.ACTIVE)

        assert error.current_state == CampaignState.COMPLETED
        assert error.target_state == CampaignState.ACTIVE
        assert "COMPLETED" in str(error)
        assert "ACTIVE" in str(error)

    def test_error_contains_campaign_id(self):
        """Error should contain campaign ID when provided."""
        error = StateTransitionError(
            CampaignState.COMPLETED,
            CampaignState.ACTIVE,
            campaign_id="test-123",
        )

        assert error.campaign_id == "test-123"
        assert "test-123" in str(error)


# ============================================================================
# Test VALID_TRANSITIONS Map
# ============================================================================


class TestValidTransitionsMap:
    """Test the VALID_TRANSITIONS configuration."""

    def test_all_campaign_state_values_have_entry(self):
        """All CampaignState enum values should have an entry in VALID_TRANSITIONS."""
        for state in CampaignState:
            assert state.value in VALID_TRANSITIONS

    def test_terminal_states_have_no_transitions(self):
        """Terminal states should have empty transition sets."""
        terminal_states = ["COMPLETED", "FAILED", "CANCELLED"]

        for state in terminal_states:
            assert len(VALID_TRANSITIONS.get(state, set())) == 0

    def test_forming_has_expected_transitions(self):
        """FORMING should allow transitions to ACTIVE, DORMANT, CANCELLED, FAILED."""
        expected = {"ACTIVE", "DORMANT", "CANCELLED", "FAILED"}
        assert VALID_TRANSITIONS["FORMING"] == expected

    def test_active_has_expected_transitions(self):
        """ACTIVE should allow transitions to COMPLETED, FAILED, DORMANT, CANCELLED."""
        expected = {"COMPLETED", "FAILED", "DORMANT", "CANCELLED"}
        assert VALID_TRANSITIONS["ACTIVE"] == expected

    def test_dormant_has_expected_transitions(self):
        """DORMANT should allow transitions to ACTIVE, FAILED, CANCELLED."""
        expected = {"ACTIVE", "FAILED", "CANCELLED"}
        assert VALID_TRANSITIONS["DORMANT"] == expected


# ============================================================================
# Test CampaignState Enum
# ============================================================================


class TestCampaignStateEnum:
    """Test CampaignState enum values."""

    def test_all_expected_states_exist(self):
        """All expected states should be defined (excluding CANCELLED which isn't in detector)."""
        expected = ["FORMING", "ACTIVE", "DORMANT", "COMPLETED", "FAILED"]

        for state_name in expected:
            assert hasattr(CampaignState, state_name)

    def test_state_values_match_names(self):
        """State values should match their names."""
        for state in CampaignState:
            assert state.value == state.name
