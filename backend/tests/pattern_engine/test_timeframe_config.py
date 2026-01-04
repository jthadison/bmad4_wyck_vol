"""
Unit Tests for Timeframe Configuration Module (Story 13.1)

Test Coverage:
--------------
- TIMEFRAME_MULTIPLIERS dictionary structure and values
- get_scaled_threshold() function
- validate_timeframe() function
- Constants (ICE_DISTANCE_BASE, CREEK_MIN_RALLY_BASE, etc.)

Author: Story 13.1
"""

from decimal import Decimal

import pytest

from src.pattern_engine.timeframe_config import (
    CREEK_MIN_RALLY_BASE,
    ICE_DISTANCE_BASE,
    MAX_PENETRATION_BASE,
    SOS_VOLUME_THRESHOLD,
    SPRING_VOLUME_THRESHOLD,
    TIMEFRAME_MULTIPLIERS,
    get_scaled_threshold,
    validate_timeframe,
)


class TestTimeframeMultipliers:
    """Test Suite for TIMEFRAME_MULTIPLIERS constant."""

    def test_timeframe_multipliers_contains_all_required_timeframes(self):
        """Verify TIMEFRAME_MULTIPLIERS has all 5 required timeframes."""
        required_timeframes = {"1m", "5m", "15m", "1h", "1d"}
        assert set(TIMEFRAME_MULTIPLIERS.keys()) == required_timeframes

    def test_timeframe_multipliers_correct_values(self):
        """Verify multiplier values match specification (AC1.2, AC1.3)."""
        assert TIMEFRAME_MULTIPLIERS["1m"] == Decimal("0.15")
        assert TIMEFRAME_MULTIPLIERS["5m"] == Decimal("0.20")
        assert TIMEFRAME_MULTIPLIERS["15m"] == Decimal("0.30")
        assert TIMEFRAME_MULTIPLIERS["1h"] == Decimal("0.70")
        assert TIMEFRAME_MULTIPLIERS["1d"] == Decimal("1.00")

    def test_timeframe_multipliers_use_decimal_type(self):
        """Verify all multipliers use Decimal for precision."""
        for multiplier in TIMEFRAME_MULTIPLIERS.values():
            assert isinstance(multiplier, Decimal)


class TestBaseConstants:
    """Test Suite for base threshold constants."""

    def test_ice_distance_base_value(self):
        """Verify ICE_DISTANCE_BASE is 2% (0.02)."""
        assert ICE_DISTANCE_BASE == Decimal("0.02")

    def test_creek_min_rally_base_value(self):
        """Verify CREEK_MIN_RALLY_BASE is 5% (0.05)."""
        assert CREEK_MIN_RALLY_BASE == Decimal("0.05")

    def test_max_penetration_base_value(self):
        """Verify MAX_PENETRATION_BASE is 5% (0.05)."""
        assert MAX_PENETRATION_BASE == Decimal("0.05")

    def test_spring_volume_threshold_value(self):
        """Verify SPRING_VOLUME_THRESHOLD is 0.7x."""
        assert SPRING_VOLUME_THRESHOLD == Decimal("0.7")

    def test_sos_volume_threshold_value(self):
        """Verify SOS_VOLUME_THRESHOLD is 2.0x."""
        assert SOS_VOLUME_THRESHOLD == Decimal("2.0")

    def test_all_base_constants_use_decimal(self):
        """Verify all base constants use Decimal type."""
        assert isinstance(ICE_DISTANCE_BASE, Decimal)
        assert isinstance(CREEK_MIN_RALLY_BASE, Decimal)
        assert isinstance(MAX_PENETRATION_BASE, Decimal)
        assert isinstance(SPRING_VOLUME_THRESHOLD, Decimal)
        assert isinstance(SOS_VOLUME_THRESHOLD, Decimal)


class TestGetScaledThreshold:
    """Test Suite for get_scaled_threshold() function."""

    def test_get_scaled_threshold_15m_ice(self):
        """Verify Ice threshold scaling for 15m timeframe."""
        scaled = get_scaled_threshold(ICE_DISTANCE_BASE, "15m")
        # 2% * 0.30 = 0.6% = 0.006
        assert scaled == Decimal("0.006")

    def test_get_scaled_threshold_1h_creek(self):
        """Verify Creek threshold scaling for 1h timeframe."""
        scaled = get_scaled_threshold(CREEK_MIN_RALLY_BASE, "1h")
        # 5% * 0.70 = 3.5% = 0.035
        assert scaled == Decimal("0.035")

    def test_get_scaled_threshold_1d_no_change(self):
        """Verify 1d timeframe returns base threshold unchanged."""
        scaled = get_scaled_threshold(ICE_DISTANCE_BASE, "1d")
        # 2% * 1.00 = 2% = 0.02
        assert scaled == ICE_DISTANCE_BASE

    def test_get_scaled_threshold_invalid_timeframe_raises_error(self):
        """Verify invalid timeframe raises ValueError with helpful message."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            get_scaled_threshold(ICE_DISTANCE_BASE, "3h")

    def test_get_scaled_threshold_returns_decimal(self):
        """Verify function returns Decimal type."""
        scaled = get_scaled_threshold(ICE_DISTANCE_BASE, "15m")
        assert isinstance(scaled, Decimal)

    @pytest.mark.parametrize(
        "timeframe,multiplier",
        [
            ("1m", Decimal("0.15")),
            ("5m", Decimal("0.20")),
            ("15m", Decimal("0.30")),
            ("1h", Decimal("0.70")),
            ("1d", Decimal("1.00")),
        ],
    )
    def test_get_scaled_threshold_all_timeframes(self, timeframe, multiplier):
        """Verify scaling works correctly for all timeframes."""
        base = Decimal("1.0")  # Use 1.0 for easy verification
        scaled = get_scaled_threshold(base, timeframe)
        assert scaled == multiplier


class TestValidateTimeframe:
    """Test Suite for validate_timeframe() function."""

    def test_validate_timeframe_valid_lowercase(self):
        """Verify valid lowercase timeframe passes validation."""
        result = validate_timeframe("15m")
        assert result == "15m"

    def test_validate_timeframe_valid_uppercase(self):
        """Verify uppercase timeframe is normalized to lowercase."""
        result = validate_timeframe("15M")
        assert result == "15m"

    def test_validate_timeframe_valid_mixed_case(self):
        """Verify mixed case timeframe is normalized to lowercase."""
        result = validate_timeframe("1H")
        assert result == "1h"

    def test_validate_timeframe_invalid_raises_error(self):
        """Verify invalid timeframe raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            validate_timeframe("2h")

    def test_validate_timeframe_empty_string_raises_error(self):
        """Verify empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            validate_timeframe("")

    def test_validate_timeframe_returns_string(self):
        """Verify function returns string type."""
        result = validate_timeframe("15m")
        assert isinstance(result, str)

    @pytest.mark.parametrize("timeframe", ["1m", "5m", "15m", "1h", "1d"])
    def test_validate_timeframe_all_valid_timeframes(self, timeframe):
        """Verify all valid timeframes pass validation."""
        result = validate_timeframe(timeframe)
        assert result == timeframe


class TestThresholdScalingAccuracy:
    """Test Suite for exact threshold calculations (AC1.2, AC1.3)."""

    def test_ice_threshold_1m(self):
        """Verify Ice threshold for 1m: 2% * 0.15 = 0.3%."""
        scaled = get_scaled_threshold(ICE_DISTANCE_BASE, "1m")
        assert scaled == Decimal("0.003")  # 0.3%

    def test_ice_threshold_15m(self):
        """Verify Ice threshold for 15m: 2% * 0.30 = 0.6%."""
        scaled = get_scaled_threshold(ICE_DISTANCE_BASE, "15m")
        assert scaled == Decimal("0.006")  # 0.6%

    def test_ice_threshold_1h(self):
        """Verify Ice threshold for 1h: 2% * 0.70 = 1.4%."""
        scaled = get_scaled_threshold(ICE_DISTANCE_BASE, "1h")
        assert scaled == Decimal("0.014")  # 1.4%

    def test_creek_threshold_1m(self):
        """Verify Creek threshold for 1m: 5% * 0.15 = 0.75%."""
        scaled = get_scaled_threshold(CREEK_MIN_RALLY_BASE, "1m")
        assert scaled == Decimal("0.0075")  # 0.75%

    def test_creek_threshold_15m(self):
        """Verify Creek threshold for 15m: 5% * 0.30 = 1.5%."""
        scaled = get_scaled_threshold(CREEK_MIN_RALLY_BASE, "15m")
        assert scaled == Decimal("0.015")  # 1.5%

    def test_creek_threshold_1h(self):
        """Verify Creek threshold for 1h: 5% * 0.70 = 3.5%."""
        scaled = get_scaled_threshold(CREEK_MIN_RALLY_BASE, "1h")
        assert scaled == Decimal("0.035")  # 3.5%


class TestVolumeThresholdConstants:
    """Test Suite for volume threshold constants (AC1.7)."""

    def test_spring_volume_threshold_is_decimal(self):
        """Verify SPRING_VOLUME_THRESHOLD is Decimal type."""
        assert isinstance(SPRING_VOLUME_THRESHOLD, Decimal)

    def test_sos_volume_threshold_is_decimal(self):
        """Verify SOS_VOLUME_THRESHOLD is Decimal type."""
        assert isinstance(SOS_VOLUME_THRESHOLD, Decimal)

    def test_volume_thresholds_do_not_scale(self):
        """Verify volume thresholds are constants and don't scale by timeframe."""
        # This is a design verification test - volume thresholds are
        # separate constants, not subject to get_scaled_threshold()
        assert SPRING_VOLUME_THRESHOLD == Decimal("0.7")
        assert SOS_VOLUME_THRESHOLD == Decimal("2.0")
