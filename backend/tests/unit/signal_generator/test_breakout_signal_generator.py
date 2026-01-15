"""
Unit tests for BreakoutSignalGenerator class.

Story 18.4: Merge Duplicate LPS/SOS Signal Generators

Tests cover:
- LPS signal generation via BreakoutSignalGenerator (AC4.1)
- SOS direct signal generation via BreakoutSignalGenerator (AC4.1)
- Entry type parameterization (AC4.2)
- No duplicated level calculation logic (AC4.3)
- Same output as original functions (AC4.4)
- Test coverage targets (AC4.6)
- Backward-compatible facade behavior (AC4.7)
"""

import warnings
from decimal import Decimal
from uuid import uuid4

import pytest

from src.signal_generator.breakout_signal_generator import (
    LPS_ENTRY_BUFFER_PCT,
    LPS_STOP_DISTANCE_PCT,
    SOS_STOP_DISTANCE_PCT,
    BreakoutSignalGenerator,
)


class TestBreakoutSignalGeneratorLPS:
    """Tests for LPS signal generation via BreakoutSignalGenerator."""

    def test_generate_lps_signal_valid(self, lps_pattern, sos_breakout, trading_range):
        """Test AC4.1: BreakoutSignalGenerator handles LPS signals."""
        generator = BreakoutSignalGenerator()
        confidence = 85

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=confidence,
            lps=lps_pattern,
        )

        assert signal is not None, "LPS signal should be generated"
        assert signal.entry_type == "LPS_ENTRY"

        # AC4.3: Entry above Ice (Ice + 1%)
        expected_entry = Decimal("100.00") * (Decimal("1") + LPS_ENTRY_BUFFER_PCT)
        assert signal.entry_price == expected_entry

        # AC4.3: Stop 3% below Ice
        expected_stop = Decimal("100.00") * (Decimal("1") - LPS_STOP_DISTANCE_PCT)
        assert signal.stop_loss == expected_stop

        # Target = Jump level
        assert signal.target == Decimal("120.00")

    def test_lps_requires_lps_pattern(self, sos_breakout, trading_range):
        """Test that LPS entry type requires LPS pattern."""
        generator = BreakoutSignalGenerator()

        with pytest.raises(ValueError, match="LPS pattern required"):
            generator.generate_signal(
                entry_type="LPS",
                sos=sos_breakout,
                trading_range=trading_range,
                confidence=85,
                lps=None,  # Missing required LPS
            )

    def test_lps_r_multiple_calculation(self, lps_pattern, sos_breakout, trading_range):
        """Test R-multiple calculation for LPS signals."""
        generator = BreakoutSignalGenerator()

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        assert signal is not None
        # Entry: $101, Stop: $97, Target: $120
        # Risk: $4, Reward: $19
        # R-multiple: 19/4 = 4.75R
        expected_r_multiple = Decimal("19.00") / Decimal("4.00")
        assert signal.r_multiple == expected_r_multiple

    def test_lps_pattern_data_structure(self, lps_pattern, sos_breakout, trading_range):
        """Test LPS signal includes correct pattern data structure."""
        generator = BreakoutSignalGenerator()

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        assert signal is not None
        pattern_data = signal.pattern_data

        assert "sos" in pattern_data
        assert "lps" in pattern_data
        assert pattern_data["entry_type"] == "LPS_ENTRY"
        assert "entry_rationale" in pattern_data

        # Verify SOS data
        assert "bar_timestamp" in pattern_data["sos"]
        assert "volume_ratio" in pattern_data["sos"]

        # Verify LPS data
        assert "bar_timestamp" in pattern_data["lps"]
        assert "pullback_low" in pattern_data["lps"]
        assert "held_support" in pattern_data["lps"]


class TestBreakoutSignalGeneratorSOS:
    """Tests for SOS direct signal generation via BreakoutSignalGenerator."""

    def test_generate_sos_signal_valid(self, sos_breakout, trading_range):
        """Test AC4.1: BreakoutSignalGenerator handles SOS signals."""
        generator = BreakoutSignalGenerator()
        confidence = 80

        signal = generator.generate_signal(
            entry_type="SOS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=confidence,
        )

        assert signal is not None, "SOS direct signal should be generated"
        assert signal.entry_type == "SOS_DIRECT_ENTRY"

        # AC4.3: Entry at breakout price
        assert signal.entry_price == Decimal("102.00")

        # AC4.3: Stop 5% below Ice (wider than LPS)
        expected_stop = Decimal("100.00") * (Decimal("1") - SOS_STOP_DISTANCE_PCT)
        assert signal.stop_loss == expected_stop

        # Target = Jump level
        assert signal.target == Decimal("120.00")

    def test_sos_no_lps_pattern_required(self, sos_breakout, trading_range):
        """Test SOS direct entry doesn't require LPS pattern."""
        generator = BreakoutSignalGenerator()

        # Should work without LPS
        signal = generator.generate_signal(
            entry_type="SOS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=80,
        )

        assert signal is not None
        assert signal.lps_bar_timestamp is None
        assert signal.lps_volume_ratio is None

    def test_sos_pattern_data_structure(self, sos_breakout, trading_range):
        """Test SOS signal includes correct pattern data structure."""
        generator = BreakoutSignalGenerator()

        signal = generator.generate_signal(
            entry_type="SOS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=80,
        )

        assert signal is not None
        pattern_data = signal.pattern_data

        assert "sos" in pattern_data
        assert "lps" not in pattern_data  # SOS direct has no LPS
        assert pattern_data["entry_type"] == "SOS_DIRECT_ENTRY"
        assert "entry_rationale" in pattern_data


class TestBreakoutSignalGeneratorCommon:
    """Common tests for both entry types."""

    def test_lps_tighter_stop_than_sos(self, lps_pattern, sos_breakout, trading_range):
        """Test AC4.3: LPS has tighter stop than SOS (no duplicated logic)."""
        generator = BreakoutSignalGenerator()

        lps_signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        sos_signal = generator.generate_signal(
            entry_type="SOS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=80,
        )

        assert lps_signal is not None
        assert sos_signal is not None

        # LPS stop: Ice - 3% = $97.00
        # SOS stop: Ice - 5% = $95.00
        lps_risk = lps_signal.entry_price - lps_signal.stop_loss
        sos_risk = sos_signal.entry_price - sos_signal.stop_loss

        assert lps_risk < sos_risk, "LPS should have tighter stop (lower risk)"
        assert lps_risk == Decimal("4.00")
        assert sos_risk == Decimal("7.00")

    def test_minimum_r_multiple_rejection(self, lps_pattern, sos_breakout, trading_range):
        """Test AC4.3: R-multiple validation with shared logic."""
        generator = BreakoutSignalGenerator()

        # Set Jump level too close (poor R-multiple)
        trading_range.jump.price = Decimal("103.00")

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        assert signal is None, "Should reject for R-multiple < 2.0R"

    def test_boundary_r_multiple_2_0_passes(self, lps_pattern, sos_breakout, trading_range):
        """Test exactly 2.0R passes validation."""
        generator = BreakoutSignalGenerator()

        # Entry: $101, Stop: $97 (risk $4)
        # Target: $109 (reward $8)
        # R-multiple: 8/4 = 2.0R exactly
        trading_range.jump.price = Decimal("109.00")

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        assert signal is not None, "2.0R exactly should pass"
        assert signal.r_multiple == Decimal("2.0")

    def test_missing_ice_level_raises(self, lps_pattern, sos_breakout, trading_range):
        """Test missing Ice level raises ValueError."""
        generator = BreakoutSignalGenerator()
        trading_range.ice = None

        with pytest.raises(ValueError, match="Ice level required"):
            generator.generate_signal(
                entry_type="LPS",
                sos=sos_breakout,
                trading_range=trading_range,
                confidence=85,
                lps=lps_pattern,
            )

    def test_missing_jump_level_raises(self, lps_pattern, sos_breakout, trading_range):
        """Test missing Jump level raises ValueError."""
        generator = BreakoutSignalGenerator()
        trading_range.jump = None

        with pytest.raises(ValueError, match="Jump level required"):
            generator.generate_signal(
                entry_type="LPS",
                sos=sos_breakout,
                trading_range=trading_range,
                confidence=85,
                lps=lps_pattern,
            )

    def test_campaign_linkage(self, lps_pattern, sos_breakout, trading_range):
        """Test campaign ID is properly set."""
        generator = BreakoutSignalGenerator()
        campaign_id = uuid4()

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
            campaign_id=campaign_id,
        )

        assert signal is not None
        assert signal.campaign_id == campaign_id
        assert signal.has_campaign


class TestBackwardCompatibleFacades:
    """Test backward-compatible facade functions (AC4.7)."""

    def test_facade_lps_produces_same_output(self, lps_pattern, sos_breakout, trading_range):
        """Test AC4.4: Facade produces same output as direct generator call."""
        from src.signal_generator.sos_signal_generator import generate_lps_signal

        generator = BreakoutSignalGenerator()

        # Get direct result
        direct_result = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        # Get facade result (with deprecation warning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            facade_result = generate_lps_signal(
                lps_pattern, sos_breakout, trading_range, confidence=85
            )
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "generate_lps_signal() is deprecated" in str(w[0].message)

        # Compare key attributes (excluding generated_at timestamp and ID)
        assert facade_result.entry_type == direct_result.entry_type
        assert facade_result.entry_price == direct_result.entry_price
        assert facade_result.stop_loss == direct_result.stop_loss
        assert facade_result.target == direct_result.target
        assert facade_result.r_multiple == direct_result.r_multiple
        assert facade_result.confidence == direct_result.confidence

    def test_facade_sos_produces_same_output(self, sos_breakout, trading_range):
        """Test AC4.4: SOS facade produces same output as direct generator call."""
        from src.signal_generator.sos_signal_generator import generate_sos_direct_signal

        generator = BreakoutSignalGenerator()

        # Get direct result
        direct_result = generator.generate_signal(
            entry_type="SOS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=80,
        )

        # Get facade result (with deprecation warning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            facade_result = generate_sos_direct_signal(sos_breakout, trading_range, confidence=80)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "generate_sos_direct_signal() is deprecated" in str(w[0].message)

        # Compare key attributes
        assert facade_result.entry_type == direct_result.entry_type
        assert facade_result.entry_price == direct_result.entry_price
        assert facade_result.stop_loss == direct_result.stop_loss
        assert facade_result.target == direct_result.target
        assert facade_result.r_multiple == direct_result.r_multiple

    def test_facade_deprecation_warning_lps(self, lps_pattern, sos_breakout, trading_range):
        """Test AC4.7: LPS facade raises DeprecationWarning."""
        from src.signal_generator.sos_signal_generator import generate_lps_signal

        with pytest.warns(DeprecationWarning, match="generate_lps_signal.*deprecated"):
            generate_lps_signal(lps_pattern, sos_breakout, trading_range, confidence=85)

    def test_facade_deprecation_warning_sos(self, sos_breakout, trading_range):
        """Test AC4.7: SOS facade raises DeprecationWarning."""
        from src.signal_generator.sos_signal_generator import generate_sos_direct_signal

        with pytest.warns(DeprecationWarning, match="generate_sos_direct_signal.*deprecated"):
            generate_sos_direct_signal(sos_breakout, trading_range, confidence=80)


class TestEdgeCases:
    """Edge case tests for BreakoutSignalGenerator."""

    def test_invalid_risk_stop_above_entry(self, sos_breakout, trading_range):
        """Test invalid risk scenario where stop >= entry."""
        from datetime import UTC, datetime

        from src.models.sos_breakout import SOSBreakout

        generator = BreakoutSignalGenerator()

        # Create invalid SOS where breakout is below Ice
        invalid_sos = SOSBreakout(
            bar=sos_breakout.bar,
            breakout_pct=Decimal("0.01"),
            volume_ratio=Decimal("2.0"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("94.00"),  # Below stop level
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            spread_ratio=Decimal("1.3"),
            close_position=Decimal("0.6"),
            spread=Decimal("2.00"),
        )

        signal = generator.generate_signal(
            entry_type="SOS",
            sos=invalid_sos,
            trading_range=trading_range,
            confidence=80,
        )

        assert signal is None, "Should reject when risk <= 0"

    def test_confidence_preserved(self, lps_pattern, sos_breakout, trading_range):
        """Test confidence score is preserved in signal."""
        generator = BreakoutSignalGenerator()

        for confidence in [0, 50, 85, 100]:
            signal = generator.generate_signal(
                entry_type="LPS",
                sos=sos_breakout,
                trading_range=trading_range,
                confidence=confidence,
                lps=lps_pattern,
            )
            assert signal.confidence == confidence

    def test_timestamps_preserved(self, lps_pattern, sos_breakout, trading_range):
        """Test timestamps are correctly preserved."""
        generator = BreakoutSignalGenerator()

        signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        assert signal.sos_bar_timestamp == sos_breakout.bar.timestamp
        assert signal.lps_bar_timestamp == lps_pattern.bar.timestamp

    def test_volume_ratios_preserved(self, lps_pattern, sos_breakout, trading_range):
        """Test volume ratios are correctly preserved."""
        generator = BreakoutSignalGenerator()

        lps_signal = generator.generate_signal(
            entry_type="LPS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=85,
            lps=lps_pattern,
        )

        assert lps_signal.sos_volume_ratio == sos_breakout.volume_ratio
        assert lps_signal.lps_volume_ratio == lps_pattern.volume_ratio

        sos_signal = generator.generate_signal(
            entry_type="SOS",
            sos=sos_breakout,
            trading_range=trading_range,
            confidence=80,
        )

        assert sos_signal.sos_volume_ratio == sos_breakout.volume_ratio
        assert sos_signal.lps_volume_ratio is None
