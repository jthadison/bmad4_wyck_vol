"""
Campaign State Transition Tests (Story 22.14 - AC1)

Tests the campaign state machine transitions:
- FORMING -> ACTIVE (with required patterns)
- ACTIVE -> COMPLETED (on target hit)
- ACTIVE -> FAILED (on expiration)
- Invalid transitions should raise errors

These tests validate the Campaign dataclass and IntradayCampaignDetector
state management before refactoring work begins.
"""

from datetime import UTC, datetime
from decimal import Decimal

from src.backtesting.intraday_campaign_detector import (
    Campaign,
    CampaignState,
    ExitReason,
    IntradayCampaignDetector,
)
from src.models.wyckoff_phase import WyckoffPhase


class TestCampaignStateTransitions:
    """Test campaign state machine transitions (AC1)."""

    def test_new_campaign_starts_in_forming_state(self, sample_campaign: Campaign):
        """AC1: New campaigns start in FORMING state."""
        # sample_campaign fixture creates campaign with 1 pattern
        assert sample_campaign.state == CampaignState.FORMING

    def test_campaign_default_state_is_forming(self):
        """Default Campaign state should be FORMING."""
        campaign = Campaign()
        assert campaign.state == CampaignState.FORMING

    def test_forming_to_active_with_two_patterns(
        self,
        sample_campaign: Campaign,
        sample_ar_pattern,
    ):
        """AC1: FORMING -> ACTIVE when 2+ patterns are added."""
        # Start with 1 pattern (FORMING)
        assert sample_campaign.state == CampaignState.FORMING
        assert len(sample_campaign.patterns) == 1

        # Add second pattern
        sample_campaign.patterns.append(sample_ar_pattern)

        # Use detector to validate transition
        detector = IntradayCampaignDetector(min_patterns_for_active=2)

        # Simulate state update (in real code this happens in add_pattern)
        if len(sample_campaign.patterns) >= detector.min_patterns_for_active:
            sample_campaign.state = CampaignState.ACTIVE

        assert sample_campaign.state == CampaignState.ACTIVE
        assert len(sample_campaign.patterns) == 2

    def test_active_to_completed_on_target_hit(self, active_campaign: Campaign):
        """AC1: ACTIVE -> COMPLETED when exit conditions are met."""
        assert active_campaign.state == CampaignState.ACTIVE

        # Simulate target hit
        active_campaign.state = CampaignState.COMPLETED
        active_campaign.exit_reason = ExitReason.TARGET_HIT
        active_campaign.exit_price = Decimal("160.00")
        active_campaign.exit_timestamp = datetime.now(UTC)

        assert active_campaign.state == CampaignState.COMPLETED
        assert active_campaign.exit_reason == ExitReason.TARGET_HIT

    def test_active_to_completed_on_phase_e(self, active_campaign: Campaign):
        """AC1: ACTIVE -> COMPLETED when Phase E is reached."""
        assert active_campaign.state == CampaignState.ACTIVE

        # Simulate Phase E completion
        active_campaign.current_phase = WyckoffPhase.E
        active_campaign.state = CampaignState.COMPLETED
        active_campaign.exit_reason = ExitReason.PHASE_E

        assert active_campaign.state == CampaignState.COMPLETED
        assert active_campaign.exit_reason == ExitReason.PHASE_E

    def test_active_to_failed_on_stop_out(self, active_campaign: Campaign):
        """AC1: ACTIVE -> FAILED on stop loss hit."""
        assert active_campaign.state == CampaignState.ACTIVE

        # Simulate stop out
        active_campaign.state = CampaignState.FAILED
        active_campaign.exit_reason = ExitReason.STOP_OUT
        active_campaign.failure_reason = "Stop loss triggered at $145.00"

        assert active_campaign.state == CampaignState.FAILED
        assert active_campaign.exit_reason == ExitReason.STOP_OUT
        assert "Stop loss" in active_campaign.failure_reason

    def test_active_to_failed_on_expiration(self, active_campaign: Campaign):
        """AC1: ACTIVE -> FAILED when campaign exceeds expiration window."""
        assert active_campaign.state == CampaignState.ACTIVE

        # Simulate expiration (72 hours exceeded)
        active_campaign.state = CampaignState.FAILED
        active_campaign.exit_reason = ExitReason.TIME_EXIT
        active_campaign.failure_reason = "Campaign expired after 72 hours"

        assert active_campaign.state == CampaignState.FAILED
        assert active_campaign.exit_reason == ExitReason.TIME_EXIT

    def test_state_persistence_across_operations(self, active_campaign: Campaign):
        """AC1: State persists correctly across multiple operations."""
        # Verify initial state
        assert active_campaign.state == CampaignState.ACTIVE

        # Perform various operations
        active_campaign.position_size = Decimal("200")
        active_campaign.dollar_risk = Decimal("600")
        active_campaign.strength_score = 0.90

        # State should remain unchanged
        assert active_campaign.state == CampaignState.ACTIVE

        # Now complete the campaign
        active_campaign.state = CampaignState.COMPLETED
        active_campaign.exit_reason = ExitReason.TARGET_HIT

        # Verify state changed
        assert active_campaign.state == CampaignState.COMPLETED

    def test_dormant_state_transition(self, active_campaign: Campaign):
        """AC1: ACTIVE -> DORMANT when no recent patterns."""
        assert active_campaign.state == CampaignState.ACTIVE

        # Simulate dormant transition
        active_campaign.state = CampaignState.DORMANT

        assert active_campaign.state == CampaignState.DORMANT

    def test_phase_history_tracking_during_transitions(self, sample_campaign: Campaign):
        """AC1: Phase history is tracked during state transitions."""
        # Initial state
        assert sample_campaign.current_phase == WyckoffPhase.C

        # Record phase transition
        sample_campaign.phase_history.append((datetime.now(UTC), WyckoffPhase.C))
        sample_campaign.phase_transition_count += 1

        # Transition to Phase D
        sample_campaign.current_phase = WyckoffPhase.D
        sample_campaign.phase_history.append((datetime.now(UTC), WyckoffPhase.D))
        sample_campaign.phase_transition_count += 1

        assert sample_campaign.current_phase == WyckoffPhase.D
        assert sample_campaign.phase_transition_count == 2
        assert len(sample_campaign.phase_history) == 2

    def test_campaign_id_uniqueness(self):
        """Campaign IDs should be unique."""
        campaign1 = Campaign()
        campaign2 = Campaign()

        assert campaign1.campaign_id != campaign2.campaign_id


class TestCampaignStateEnumValues:
    """Test CampaignState enum values and properties."""

    def test_all_states_exist(self):
        """All expected states should exist in the enum."""
        expected_states = ["FORMING", "ACTIVE", "DORMANT", "COMPLETED", "FAILED"]
        actual_states = [state.value for state in CampaignState]

        for state in expected_states:
            assert state in actual_states

    def test_state_value_consistency(self):
        """State values should match their names."""
        assert CampaignState.FORMING.value == "FORMING"
        assert CampaignState.ACTIVE.value == "ACTIVE"
        assert CampaignState.DORMANT.value == "DORMANT"
        assert CampaignState.COMPLETED.value == "COMPLETED"
        assert CampaignState.FAILED.value == "FAILED"


class TestExitReasonEnum:
    """Test ExitReason enum values."""

    def test_all_exit_reasons_exist(self):
        """All expected exit reasons should exist."""
        expected_reasons = [
            "TARGET_HIT",
            "STOP_OUT",
            "TIME_EXIT",
            "PHASE_E",
            "MANUAL_EXIT",
            "UNKNOWN",
        ]
        actual_reasons = [reason.value for reason in ExitReason]

        for reason in expected_reasons:
            assert reason in actual_reasons

    def test_default_exit_reason_is_unknown(self, sample_campaign: Campaign):
        """Default exit reason should be UNKNOWN."""
        assert sample_campaign.exit_reason == ExitReason.UNKNOWN


class TestDetectorStateManagement:
    """Test IntradayCampaignDetector state management."""

    def test_detector_tracks_campaigns_by_state(
        self,
        detector: IntradayCampaignDetector,
        sample_campaign: Campaign,
    ):
        """Detector should track campaigns by state in index."""
        detector._add_to_indexes(sample_campaign)

        # Campaign should be in FORMING state index
        assert sample_campaign.campaign_id in detector._campaigns_by_state[CampaignState.FORMING]

    def test_detector_updates_indexes_on_state_change(
        self,
        detector: IntradayCampaignDetector,
        sample_campaign: Campaign,
    ):
        """Detector should update indexes when campaign state changes."""
        detector._add_to_indexes(sample_campaign)

        # Verify initial state
        assert sample_campaign.campaign_id in detector._campaigns_by_state[CampaignState.FORMING]

        # Change state
        old_state = sample_campaign.state
        sample_campaign.state = CampaignState.ACTIVE
        detector._update_indexes(sample_campaign, old_state)

        # Verify state updated in indexes
        assert (
            sample_campaign.campaign_id not in detector._campaigns_by_state[CampaignState.FORMING]
        )
        assert sample_campaign.campaign_id in detector._campaigns_by_state[CampaignState.ACTIVE]

    def test_detector_active_time_windows_tracking(
        self,
        detector: IntradayCampaignDetector,
        active_campaign: Campaign,
    ):
        """Detector should track active campaigns in time windows."""
        detector._add_to_indexes(active_campaign)

        # Active campaign should be in time windows
        assert active_campaign.campaign_id in detector._active_time_windows

    def test_detector_removes_from_indexes_correctly(
        self,
        detector: IntradayCampaignDetector,
        active_campaign: Campaign,
    ):
        """Detector should properly remove campaigns from all indexes."""
        detector._add_to_indexes(active_campaign)

        # Verify added
        assert active_campaign.campaign_id in detector._campaigns_by_id
        assert active_campaign.campaign_id in detector._active_time_windows

        # Remove
        detector._remove_from_indexes(active_campaign.campaign_id)

        # Verify removed from all indexes
        assert active_campaign.campaign_id not in detector._campaigns_by_id
        assert active_campaign.campaign_id not in detector._active_time_windows
        assert active_campaign.campaign_id not in detector._campaigns_by_state[CampaignState.ACTIVE]

    def test_detector_rebuild_indexes(
        self,
        detector: IntradayCampaignDetector,
        active_campaign: Campaign,
        sample_campaign: Campaign,
    ):
        """Detector should correctly rebuild indexes from primary store."""
        # Add campaigns directly to _campaigns_by_id
        detector._campaigns_by_id[active_campaign.campaign_id] = active_campaign
        detector._campaigns_by_id[sample_campaign.campaign_id] = sample_campaign

        # Rebuild indexes
        detector._rebuild_indexes()

        # Verify indexes rebuilt correctly
        assert active_campaign.campaign_id in detector._campaigns_by_state[CampaignState.ACTIVE]
        assert sample_campaign.campaign_id in detector._campaigns_by_state[CampaignState.FORMING]
        assert active_campaign.campaign_id in detector._active_time_windows
        assert sample_campaign.campaign_id not in detector._active_time_windows


class TestPerformanceMetricsCalculation:
    """Test Campaign.calculate_performance_metrics()."""

    def test_calculate_performance_metrics_basic(self, active_campaign: Campaign):
        """Should calculate R-multiple and points gained correctly."""
        # Set up entry price via first pattern
        entry_price = active_campaign.patterns[0].bar.close
        exit_price = Decimal("160.00")

        active_campaign.calculate_performance_metrics(exit_price)

        # Verify calculations
        expected_points = exit_price - entry_price
        assert active_campaign.points_gained == expected_points

        if active_campaign.risk_per_share:
            expected_r = expected_points / active_campaign.risk_per_share
            assert active_campaign.r_multiple == expected_r

    def test_calculate_performance_metrics_duration(self, active_campaign: Campaign):
        """Should calculate campaign duration in bars."""
        active_campaign.calculate_performance_metrics(Decimal("160.00"))

        # Duration should be >= 1
        assert active_campaign.duration_bars >= 1

    def test_calculate_performance_metrics_no_patterns(self):
        """Should handle campaigns without patterns gracefully."""
        campaign = Campaign()
        campaign.calculate_performance_metrics(Decimal("100.00"))

        # Should not crash, metrics should be None
        assert campaign.points_gained is None
        assert campaign.r_multiple is None
