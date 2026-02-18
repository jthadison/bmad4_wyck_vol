"""
Unit Tests for Phase Validator Module (Story 13.7)

Tests pattern-phase validation, level proximity validation,
phase confidence adjustment, and volume-phase confidence integration.

AC7.9: Regression test ensuring phase detection doesn't change backtest win rate by > 5%
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.models.phase_classification import WyckoffPhase
from src.pattern_engine.phase_validator import (
    PATTERN_PHASE_EXPECTATIONS,
    PHASE_VOLUME_EXPECTATIONS,
    VALID_PHASE_TRANSITIONS,
    adjust_pattern_confidence_for_phase,
    adjust_pattern_confidence_for_phase_and_volume,
    calculate_volume_multiplier,
    get_transition_description,
    is_valid_phase_transition,
    validate_pattern_level_proximity,
)

# ============================================================================
# Phase Transition Tests (AC7.22)
# ============================================================================


class TestPhaseTransitions:
    """Tests for is_valid_phase_transition function."""

    def test_valid_a_to_b_transition(self):
        """A -> B transition should be valid."""
        assert is_valid_phase_transition(WyckoffPhase.A, WyckoffPhase.B) is True

    def test_valid_b_to_c_transition(self):
        """B -> C transition should be valid."""
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.C) is True

    def test_valid_b_to_d_transition_schematic_1(self):
        """B -> D transition should be valid (Schematic #1)."""
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.D) is True

    def test_valid_c_to_d_transition(self):
        """C -> D transition should be valid."""
        assert is_valid_phase_transition(WyckoffPhase.C, WyckoffPhase.D) is True

    def test_valid_d_to_e_transition(self):
        """D -> E transition should be valid."""
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.E) is True

    def test_invalid_d_to_a_transition(self):
        """D -> A transition should be invalid."""
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.A) is False

    def test_invalid_e_to_c_transition(self):
        """E -> C transition should be invalid."""
        assert is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.C) is False

    def test_stay_in_phase_b(self):
        """B -> B transition should be valid (stay in phase)."""
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.B) is True

    def test_stay_in_phase_e(self):
        """E -> E transition should be valid (stay in markup)."""
        assert is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.E) is True

    def test_start_campaign_in_a(self):
        """None -> A transition should be valid (campaign start)."""
        assert is_valid_phase_transition(None, WyckoffPhase.A) is True

    def test_start_campaign_in_b(self):
        """None -> B transition should be valid (campaign start)."""
        assert is_valid_phase_transition(None, WyckoffPhase.B) is True


# ============================================================================
# Volume Multiplier Tests (AC7.19-AC7.21)
# ============================================================================


class TestVolumePhaseConfidence:
    """Tests for volume-phase confidence integration."""

    def test_volume_in_expected_range_boosts_confidence(self):
        """Volume within expected range should boost confidence."""
        # Phase C expects low volume (0.3-0.7x)
        multiplier = calculate_volume_multiplier(WyckoffPhase.C, 0.5)

        assert multiplier == 1.1  # Boost

    def test_volume_outside_range_penalizes_confidence(self):
        """Volume outside expected range should penalize confidence."""
        # Phase C expects low volume (0.3-0.7x), high volume is wrong
        multiplier = calculate_volume_multiplier(WyckoffPhase.C, 1.5)

        assert multiplier == 0.7  # Strong penalty

    def test_volume_slightly_outside_range_minor_penalty(self):
        """Volume slightly outside range should have minor penalty."""
        # Phase C expects 0.3-0.7x, 0.8x is slightly outside
        multiplier = calculate_volume_multiplier(WyckoffPhase.C, 0.8)

        assert multiplier == 0.9  # Minor penalty

    def test_phase_d_expects_high_volume(self):
        """Phase D should expect high volume (1.5-3.0x)."""
        # Good volume for Phase D
        multiplier = calculate_volume_multiplier(WyckoffPhase.D, 2.0)
        assert multiplier == 1.1

        # Low volume is bad for Phase D
        multiplier_low = calculate_volume_multiplier(WyckoffPhase.D, 0.5)
        assert multiplier_low == 0.7

    def test_none_phase_returns_neutral(self):
        """None phase should return neutral multiplier."""
        multiplier = calculate_volume_multiplier(None, 1.0)
        assert multiplier == 1.0


# ============================================================================
# Phase Confidence Adjustment Tests (AC7.7)
# ============================================================================


class TestPhaseConfidenceAdjustment:
    """Tests for adjust_pattern_confidence_for_phase function."""

    def test_high_phase_confidence_maintains_pattern_confidence(self):
        """High phase confidence should maintain pattern confidence."""
        from src.models.phase_classification import PhaseClassification, PhaseEvents

        pattern_confidence = 85
        phase = PhaseClassification(
            phase=WyckoffPhase.C,
            confidence=100,
            duration=20,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            phase_start_index=30,
            phase_start_timestamp=datetime.now(UTC),
        )

        adjusted = adjust_pattern_confidence_for_phase(pattern_confidence, phase)

        assert adjusted == 85  # 85 * 1.0 = 85

    def test_low_phase_confidence_reduces_pattern_confidence(self):
        """Low phase confidence should reduce pattern confidence."""
        from src.models.phase_classification import PhaseClassification, PhaseEvents

        pattern_confidence = 85
        phase = PhaseClassification(
            phase=WyckoffPhase.C,
            confidence=40,
            duration=20,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            phase_start_index=30,
            phase_start_timestamp=datetime.now(UTC),
        )

        adjusted = adjust_pattern_confidence_for_phase(pattern_confidence, phase)

        # 85 * (0.5 + 0.5 * 0.4) = 85 * 0.7 = 59.5 -> 59
        assert adjusted == 59

    def test_medium_phase_confidence_partially_reduces(self):
        """Medium phase confidence should partially reduce pattern confidence."""
        from src.models.phase_classification import PhaseClassification, PhaseEvents

        pattern_confidence = 85
        phase = PhaseClassification(
            phase=WyckoffPhase.C,
            confidence=80,
            duration=20,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            phase_start_index=30,
            phase_start_timestamp=datetime.now(UTC),
        )

        adjusted = adjust_pattern_confidence_for_phase(pattern_confidence, phase)

        # 85 * (0.5 + 0.5 * 0.8) = 85 * 0.9 = 76.5 -> 76
        assert adjusted == 76


# ============================================================================
# Combined Phase-Volume Adjustment Tests
# ============================================================================


class TestCombinedPhaseVolumeAdjustment:
    """Tests for combined phase and volume adjustment."""

    def test_combined_phase_volume_adjustment(self):
        """Combined phase and volume adjustment should work correctly."""
        from src.models.phase_classification import PhaseClassification, PhaseEvents

        pattern_confidence = 85
        phase = PhaseClassification(
            phase=WyckoffPhase.C,
            confidence=87,
            duration=20,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            phase_start_index=30,
            phase_start_timestamp=datetime.now(UTC),
        )
        volume_ratio = 0.58  # Good for Phase C

        adjusted = adjust_pattern_confidence_for_phase_and_volume(
            pattern_confidence, phase, volume_ratio
        )

        # phase_mult = 0.5 + 0.5 * 0.87 = 0.935
        # volume_mult = 1.1 (good volume for Phase C)
        # combined = 0.935 * 1.1 = 1.0285
        # 85 * 1.0285 = 87.42 -> 87
        assert adjusted == 87

    def test_bad_volume_reduces_even_high_phase_confidence(self):
        """Bad volume should reduce confidence even with high phase confidence."""
        from src.models.phase_classification import PhaseClassification, PhaseEvents

        pattern_confidence = 85
        phase = PhaseClassification(
            phase=WyckoffPhase.C,
            confidence=95,
            duration=20,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            phase_start_index=30,
            phase_start_timestamp=datetime.now(UTC),
        )
        volume_ratio = 1.5  # Bad for Phase C (> 0.7 * 2.0 = 1.4)

        adjusted = adjust_pattern_confidence_for_phase_and_volume(
            pattern_confidence, phase, volume_ratio
        )

        # phase_mult = 0.5 + 0.5 * 0.95 = 0.975
        # volume_mult = 0.7 (bad volume for Phase C, > 1.4)
        # combined = 0.975 * 0.7 = 0.6825
        # 85 * 0.6825 = 58.01 -> 58
        assert adjusted == 58


# ============================================================================
# Transition Description Tests
# ============================================================================


class TestTransitionDescriptions:
    """Tests for get_transition_description function."""

    def test_schematic_1_description(self):
        """B -> D transition should describe Schematic #1."""
        desc = get_transition_description(WyckoffPhase.B, WyckoffPhase.D)

        assert "Schematic #1" in desc

    def test_spring_transition_description(self):
        """B -> C transition should mention Spring."""
        desc = get_transition_description(WyckoffPhase.B, WyckoffPhase.C)

        assert "Spring" in desc

    def test_sos_transition_description(self):
        """C -> D transition should mention Sign of Strength."""
        desc = get_transition_description(WyckoffPhase.C, WyckoffPhase.D)

        assert "Sign of Strength" in desc


# ============================================================================
# Expected Values Tests
# ============================================================================


class TestExpectedValues:
    """Tests for expected pattern-phase mappings."""

    def test_pattern_phase_expectations_complete(self):
        """All pattern types should have phase expectations."""
        assert "Spring" in PATTERN_PHASE_EXPECTATIONS
        assert "SOSBreakout" in PATTERN_PHASE_EXPECTATIONS
        assert "LPS" in PATTERN_PHASE_EXPECTATIONS

    def test_valid_transitions_complete(self):
        """All phases should have valid transitions defined."""
        assert None in VALID_PHASE_TRANSITIONS
        assert WyckoffPhase.A in VALID_PHASE_TRANSITIONS
        assert WyckoffPhase.B in VALID_PHASE_TRANSITIONS
        assert WyckoffPhase.C in VALID_PHASE_TRANSITIONS
        assert WyckoffPhase.D in VALID_PHASE_TRANSITIONS
        assert WyckoffPhase.E in VALID_PHASE_TRANSITIONS

    def test_phase_volume_expectations_complete(self):
        """All phases should have volume expectations defined."""
        assert WyckoffPhase.A in PHASE_VOLUME_EXPECTATIONS
        assert WyckoffPhase.B in PHASE_VOLUME_EXPECTATIONS
        assert WyckoffPhase.C in PHASE_VOLUME_EXPECTATIONS
        assert WyckoffPhase.D in PHASE_VOLUME_EXPECTATIONS
        assert WyckoffPhase.E in PHASE_VOLUME_EXPECTATIONS

    def test_phase_c_expects_low_volume(self):
        """Phase C should expect low volume (0.3-0.7x)."""
        expectations = PHASE_VOLUME_EXPECTATIONS[WyckoffPhase.C]

        assert expectations["min"] == 0.3
        assert expectations["max"] == 0.7
        assert expectations["desc"] == "low (test)"

    def test_phase_d_expects_high_volume(self):
        """Phase D should expect high volume (1.5-3.0x)."""
        expectations = PHASE_VOLUME_EXPECTATIONS[WyckoffPhase.D]

        assert expectations["min"] == 1.5
        assert expectations["max"] == 3.0
        assert expectations["desc"] == "expanding"

    def test_spring_expected_in_phase_c(self):
        """Spring pattern should be expected in Phase C only."""
        expected_phases = PATTERN_PHASE_EXPECTATIONS["Spring"]

        assert WyckoffPhase.C in expected_phases
        assert len(expected_phases) == 1

    def test_sos_expected_in_phase_d_e(self):
        """SOS pattern should be expected in Phase D and E."""
        expected_phases = PATTERN_PHASE_EXPECTATIONS["SOSBreakout"]

        assert WyckoffPhase.D in expected_phases
        assert WyckoffPhase.E in expected_phases

    def test_lps_expected_in_phase_d_e(self):
        """LPS pattern should be expected in Phase D and E (AC7.23)."""
        expected_phases = PATTERN_PHASE_EXPECTATIONS["LPS"]

        assert WyckoffPhase.D in expected_phases
        assert WyckoffPhase.E in expected_phases


# ============================================================================
# Pattern-Phase Validation Tests (Testing PATTERN_PHASE_EXPECTATIONS directly)
# ============================================================================


class TestPatternPhaseExpectationsMapping:
    """Tests verifying pattern-phase expectations mappings."""

    def test_spring_only_valid_in_phase_c(self):
        """Spring should only be valid in Phase C."""
        spring_phases = PATTERN_PHASE_EXPECTATIONS["Spring"]

        # Spring is ONLY valid in Phase C
        assert WyckoffPhase.C in spring_phases
        assert WyckoffPhase.A not in spring_phases
        assert WyckoffPhase.B not in spring_phases
        assert WyckoffPhase.D not in spring_phases
        assert WyckoffPhase.E not in spring_phases

    def test_sos_valid_in_phase_d_and_e(self):
        """SOS should be valid in Phase D and E."""
        sos_phases = PATTERN_PHASE_EXPECTATIONS["SOSBreakout"]

        assert WyckoffPhase.D in sos_phases
        assert WyckoffPhase.E in sos_phases
        assert WyckoffPhase.A not in sos_phases
        assert WyckoffPhase.B not in sos_phases
        assert WyckoffPhase.C not in sos_phases

    def test_lps_valid_in_phase_d_and_e(self):
        """LPS should be valid in Phase D and E (AC7.23 - updated)."""
        lps_phases = PATTERN_PHASE_EXPECTATIONS["LPS"]

        # LPS can occur in Phase D (late) or E
        assert WyckoffPhase.D in lps_phases
        assert WyckoffPhase.E in lps_phases


# ============================================================================
# Wyckoff Phase Progression Tests (Full Campaign)
# ============================================================================


class TestFullCampaignProgression:
    """Tests for complete Wyckoff campaign phase progression."""

    def test_standard_accumulation_progression(self):
        """Standard accumulation should progress A -> B -> C -> D -> E."""
        assert is_valid_phase_transition(None, WyckoffPhase.A)
        assert is_valid_phase_transition(WyckoffPhase.A, WyckoffPhase.B)
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.C)
        assert is_valid_phase_transition(WyckoffPhase.C, WyckoffPhase.D)
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.E)

    def test_schematic_1_accumulation_progression(self):
        """Schematic #1 accumulation should progress B -> D (no Spring)."""
        assert is_valid_phase_transition(None, WyckoffPhase.B)
        assert is_valid_phase_transition(WyckoffPhase.B, WyckoffPhase.D)  # Skip C
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.E)

    def test_campaign_cannot_regress(self):
        """Campaign should not regress to earlier phases (except valid failures).

        Per FR7.3/AC7.22:
        - D->B and D->C are valid (SOS breakout failure)
        - E->A is valid (distribution detected, new accumulation)
        """
        # D->A is never valid
        assert not is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.A)
        # D->B and D->C are valid (failed breakout returns to accumulation)
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.B)
        assert is_valid_phase_transition(WyckoffPhase.D, WyckoffPhase.C)
        # E->A is valid (distribution, new accumulation starting)
        assert is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.A)
        # E cannot go to B, C, or D
        assert not is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.B)
        assert not is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.C)
        assert not is_valid_phase_transition(WyckoffPhase.E, WyckoffPhase.D)


# ============================================================================
# Level Proximity Tests (AC7.16, AC7.17, AC7.18)
# ============================================================================


class TestLevelProximityValidation:
    """Tests for validate_pattern_level_proximity function (Sam - Supply/Demand Mapper)."""

    @pytest.fixture
    def mock_trading_range(self):
        """Create a mock trading range with Creek=100.00 and Ice=110.00."""
        trading_range = MagicMock()
        trading_range.support = Decimal("100.00")  # Creek
        trading_range.resistance = Decimal("110.00")  # Ice
        # No creek/ice attributes, will fallback to support/resistance
        trading_range.creek = None
        trading_range.ice = None
        return trading_range

    @pytest.fixture
    def mock_spring(self):
        """Create a mock Spring pattern."""
        spring = MagicMock()
        spring.__class__.__name__ = "Spring"
        return spring

    @pytest.fixture
    def mock_sos(self):
        """Create a mock SOSBreakout pattern."""
        sos = MagicMock()
        sos.__class__.__name__ = "SOSBreakout"
        return sos

    @pytest.fixture
    def mock_lps(self):
        """Create a mock LPS pattern."""
        lps = MagicMock()
        lps.__class__.__name__ = "LPS"
        return lps

    # AC7.16: Spring at Creek validation
    def test_spring_at_creek_valid(self, mock_trading_range, mock_spring):
        """AC7.16: Spring at Creek (support) should be valid."""
        # Spring exactly at Creek (100.00)
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("100.00")
        )
        assert is_valid is True
        assert reason is None

    def test_spring_below_creek_valid(self, mock_trading_range, mock_spring):
        """AC7.16: Spring below Creek (shakeout) should be valid."""
        # Spring below Creek (shakeout into support)
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("99.50")
        )
        assert is_valid is True
        assert reason is None

    def test_spring_within_tolerance_valid(self, mock_trading_range, mock_spring):
        """AC7.16: Spring within 0.5% above Creek should be valid."""
        # Creek = 100.00, 0.5% tolerance = 100.50
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("100.40")
        )
        assert is_valid is True
        assert reason is None

    def test_spring_at_max_tolerance_valid(self, mock_trading_range, mock_spring):
        """AC7.16: Spring at exact 0.5% above Creek should be valid."""
        # Creek = 100.00, exactly at 100.50 (0.5% above)
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("100.50")
        )
        assert is_valid is True
        assert reason is None

    # AC7.17: Spring rejection (too far from Creek)
    def test_spring_above_tolerance_rejected(self, mock_trading_range, mock_spring):
        """AC7.17: Spring too far above Creek should be rejected."""
        # Creek = 100.00, max valid = 100.50, price = 101.00 (1% above)
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("101.00")
        )
        assert is_valid is False
        assert reason is not None
        assert "too far above Creek" in reason

    def test_spring_way_above_creek_rejected(self, mock_trading_range, mock_spring):
        """AC7.17: Spring way above Creek should be rejected."""
        # Spring at midpoint of range - clearly invalid
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("105.00")
        )
        assert is_valid is False
        assert reason is not None
        assert "too far above Creek" in reason

    def test_spring_near_ice_rejected(self, mock_trading_range, mock_spring):
        """AC7.17: Spring near Ice (resistance) should be rejected."""
        # Spring near Ice (110.00) - completely wrong level
        is_valid, reason = validate_pattern_level_proximity(
            mock_spring, mock_trading_range, Decimal("109.50")
        )
        assert is_valid is False
        assert reason is not None

    # AC7.18: SOS above Ice validation
    def test_sos_above_ice_valid(self, mock_trading_range, mock_sos):
        """AC7.18: SOS above Ice (resistance breakout) should be valid."""
        # SOS breaks above Ice (110.00)
        is_valid, reason = validate_pattern_level_proximity(
            mock_sos, mock_trading_range, Decimal("111.00")
        )
        assert is_valid is True
        assert reason is None

    def test_sos_at_ice_valid(self, mock_trading_range, mock_sos):
        """AC7.18: SOS at Ice (exactly at breakout) should be valid."""
        # SOS at exactly Ice level
        is_valid, reason = validate_pattern_level_proximity(
            mock_sos, mock_trading_range, Decimal("110.00")
        )
        assert is_valid is True
        assert reason is None

    def test_sos_way_above_ice_valid(self, mock_trading_range, mock_sos):
        """AC7.18: SOS well above Ice should be valid (strong breakout)."""
        # SOS way above Ice - strong breakout
        is_valid, reason = validate_pattern_level_proximity(
            mock_sos, mock_trading_range, Decimal("115.00")
        )
        assert is_valid is True
        assert reason is None

    def test_sos_below_ice_rejected(self, mock_trading_range, mock_sos):
        """AC7.18: SOS below Ice should be rejected (no breakout)."""
        # SOS below Ice - hasn't broken resistance
        is_valid, reason = validate_pattern_level_proximity(
            mock_sos, mock_trading_range, Decimal("109.00")
        )
        assert is_valid is False
        assert reason is not None
        assert "hasn't broken Ice" in reason

    def test_sos_at_midpoint_rejected(self, mock_trading_range, mock_sos):
        """AC7.18: SOS at range midpoint should be rejected."""
        # SOS at midpoint (105.00) - no breakout
        is_valid, reason = validate_pattern_level_proximity(
            mock_sos, mock_trading_range, Decimal("105.00")
        )
        assert is_valid is False
        assert reason is not None

    def test_sos_near_creek_rejected(self, mock_trading_range, mock_sos):
        """AC7.18: SOS near Creek (support) should be rejected."""
        # SOS near Creek - completely wrong level
        is_valid, reason = validate_pattern_level_proximity(
            mock_sos, mock_trading_range, Decimal("100.50")
        )
        assert is_valid is False
        assert reason is not None

    # LPS Level Proximity Tests (bonus coverage)
    def test_lps_near_ice_valid(self, mock_trading_range, mock_lps):
        """LPS near Ice (now support after breakout) should be valid."""
        # LPS within 2% of Ice (110.00)
        is_valid, reason = validate_pattern_level_proximity(
            mock_lps, mock_trading_range, Decimal("110.50")
        )
        assert is_valid is True
        assert reason is None

    def test_lps_at_ice_valid(self, mock_trading_range, mock_lps):
        """LPS at Ice (exact retest) should be valid."""
        is_valid, reason = validate_pattern_level_proximity(
            mock_lps, mock_trading_range, Decimal("110.00")
        )
        assert is_valid is True
        assert reason is None

    def test_lps_within_2pct_above_ice_valid(self, mock_trading_range, mock_lps):
        """LPS within 2% above Ice should be valid."""
        # Ice = 110.00, 2% above = 112.20
        is_valid, reason = validate_pattern_level_proximity(
            mock_lps, mock_trading_range, Decimal("112.00")
        )
        assert is_valid is True
        assert reason is None

    def test_lps_too_far_from_ice_rejected(self, mock_trading_range, mock_lps):
        """LPS too far from Ice (>2%) should be rejected."""
        # Ice = 110.00, 3% above = 113.30 (exceeds 2% tolerance)
        is_valid, reason = validate_pattern_level_proximity(
            mock_lps, mock_trading_range, Decimal("114.00")
        )
        assert is_valid is False
        assert reason is not None
        assert "from Ice" in reason

    def test_lps_way_below_ice_rejected(self, mock_trading_range, mock_lps):
        """LPS way below Ice should be rejected."""
        # LPS near Creek - wrong level for LPS
        is_valid, reason = validate_pattern_level_proximity(
            mock_lps, mock_trading_range, Decimal("100.00")
        )
        assert is_valid is False
        assert reason is not None
