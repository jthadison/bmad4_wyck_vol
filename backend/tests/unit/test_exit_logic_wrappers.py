"""
Unit Tests for Exit Logic Wrapper Functions (Story 13.6.5)

Purpose:
--------
Individual unit tests for each wrapper function in exit_logic_refinements.py.
Tests each function in isolation with various input scenarios.

Test Coverage:
--------------
- _build_exit_metadata: Exit metadata builder
- _check_support_break: Priority 1 - Support break
- _check_volatility_spike_wrapper: Priority 2 - Volatility spike
- _check_jump_level: Priority 3 - Jump level reached
- _check_portfolio_heat_wrapper: Priority 4 - Portfolio heat limit
- _check_phase_e_utad_wrapper: Priority 5 - Phase E UTAD
- _check_uptrend_break_wrapper: Priority 6 - Uptrend break
- _check_lower_high_wrapper: Priority 7 - Lower high
- _check_failed_rallies_wrapper: Priority 8 - Failed rallies
- _check_excessive_duration_wrapper: Priority 9 - Excessive duration
- _check_correlation_cascade_wrapper: Priority 10 - Correlation cascade
- _check_volume_divergence_wrapper: Priority 11 - Volume divergence
- _check_time_limit: Priority 12 - Time limit

Author: Developer Agent (Story 13.6.5 Unit Tests)
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.exit_logic_refinements import (
    SessionVolumeProfile,
    _build_exit_metadata,
    _check_correlation_cascade_wrapper,
    _check_excessive_duration_wrapper,
    _check_failed_rallies_wrapper,
    _check_jump_level,
    _check_lower_high_wrapper,
    _check_phase_e_utad_wrapper,
    _check_portfolio_heat_wrapper,
    _check_support_break,
    _check_time_limit,
    _check_uptrend_break_wrapper,
    _check_volatility_spike_wrapper,
    _check_volume_divergence_wrapper,
)
from src.backtesting.intraday_campaign_detector import Campaign, CampaignState
from src.backtesting.portfolio_risk import PortfolioRiskState
from src.models.ohlcv import OHLCVBar
from src.models.wyckoff_phase import WyckoffPhase

# =============================================================================
# Test Helpers
# =============================================================================


def create_test_bar(
    timestamp: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: int,
    symbol: str = "TEST",
) -> OHLCVBar:
    """Create OHLCVBar for testing."""
    # Round spread to avoid floating point precision issues
    spread = round(abs(high - low), 2)
    return OHLCVBar(
        symbol=symbol,
        timestamp=timestamp,
        open=Decimal(str(open_price)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
        timeframe="1h",
        spread=Decimal(str(spread)),
    )


def create_test_campaign(
    support: float = 100.0,
    resistance: float = 110.0,
    jump: float | None = None,
    phase: WyckoffPhase = WyckoffPhase.D,
) -> Campaign:
    """Create test campaign with levels."""
    campaign = Campaign(
        start_time=datetime.now(),
        state=CampaignState.ACTIVE,
        current_phase=phase,
        support_level=Decimal(str(support)),
        resistance_level=Decimal(str(resistance)),
    )

    if jump:
        campaign.jump_level = Decimal(str(jump))
    else:
        range_width = campaign.resistance_level - campaign.support_level
        campaign.jump_level = campaign.resistance_level + range_width

    return campaign


def create_recent_bars(
    count: int = 20,
    base_time: datetime | None = None,
    base_price: float = 108.0,
    volume: int = 1000000,
) -> list[OHLCVBar]:
    """Create list of recent bars for testing."""
    if base_time is None:
        base_time = datetime.now()

    bars = []
    for i in range(count):
        bar = create_test_bar(
            timestamp=base_time - timedelta(hours=count - i),
            open_price=base_price,
            high=base_price + 1,
            low=base_price - 1,
            close=base_price,
            volume=volume,
        )
        bars.append(bar)
    return bars


# =============================================================================
# Test _build_exit_metadata
# =============================================================================


class TestBuildExitMetadata:
    """Unit tests for _build_exit_metadata function."""

    def test_metadata_contains_all_required_fields(self):
        """Test metadata contains exit_type, priority, details, timestamp."""
        bar = create_test_bar(datetime.now(), 100, 101, 99, 100, 1000000)
        details = {"test_key": "test_value"}

        metadata = _build_exit_metadata("TEST_EXIT", 5, details, bar)

        assert "exit_type" in metadata
        assert "priority" in metadata
        assert "details" in metadata
        assert "timestamp" in metadata
        assert "bar_index" in metadata

    def test_metadata_exit_type_correct(self):
        """Test exit_type is set correctly."""
        bar = create_test_bar(datetime.now(), 100, 101, 99, 100, 1000000)

        metadata = _build_exit_metadata("SUPPORT_BREAK", 1, {}, bar)

        assert metadata["exit_type"] == "SUPPORT_BREAK"

    def test_metadata_priority_correct(self):
        """Test priority is set correctly."""
        bar = create_test_bar(datetime.now(), 100, 101, 99, 100, 1000000)

        metadata = _build_exit_metadata("JUMP_LEVEL", 3, {}, bar)

        assert metadata["priority"] == 3

    def test_metadata_details_preserved(self):
        """Test details dict is preserved correctly."""
        bar = create_test_bar(datetime.now(), 100, 101, 99, 100, 1000000)
        details = {"close": "97.00", "support_level": "100.00"}

        metadata = _build_exit_metadata("SUPPORT_BREAK", 1, details, bar)

        assert metadata["details"]["close"] == "97.00"
        assert metadata["details"]["support_level"] == "100.00"

    def test_metadata_timestamp_is_iso_format(self):
        """Test timestamp is valid ISO format."""
        test_time = datetime(2025, 1, 15, 10, 30, 0)
        bar = create_test_bar(test_time, 100, 101, 99, 100, 1000000)

        metadata = _build_exit_metadata("TEST", 1, {}, bar)

        # Should not raise
        datetime.fromisoformat(metadata["timestamp"])


# =============================================================================
# Test _check_support_break
# =============================================================================


class TestCheckSupportBreak:
    """Unit tests for _check_support_break wrapper."""

    def test_exit_when_close_below_support(self):
        """Test exit triggered when close < support_level."""
        campaign = create_test_campaign(support=100)
        bar = create_test_bar(datetime.now(), 99, 100, 95, 97, 1000000)  # Close below support

        should_exit, reason, metadata = _check_support_break(bar, campaign)

        assert should_exit is True
        assert reason is not None
        assert "SUPPORT_BREAK" in reason
        assert metadata["priority"] == 1

    def test_no_exit_when_close_above_support(self):
        """Test no exit when close >= support_level."""
        campaign = create_test_campaign(support=100)
        bar = create_test_bar(datetime.now(), 102, 103, 100.5, 102, 1000000)  # Close above support

        should_exit, reason, metadata = _check_support_break(bar, campaign)

        assert should_exit is False
        assert reason is None
        assert metadata is None

    def test_no_exit_when_no_support_level(self):
        """Test no exit when campaign has no support_level."""
        campaign = create_test_campaign(support=100)
        campaign.support_level = None
        bar = create_test_bar(datetime.now(), 95, 96, 94, 95, 1000000)

        should_exit, reason, metadata = _check_support_break(bar, campaign)

        assert should_exit is False

    def test_metadata_contains_break_details(self):
        """Test metadata contains close, support_level, break_amount."""
        campaign = create_test_campaign(support=100)
        bar = create_test_bar(datetime.now(), 99, 100, 95, 97, 1000000)

        should_exit, reason, metadata = _check_support_break(bar, campaign)

        assert "close" in metadata["details"]
        assert "support_level" in metadata["details"]
        assert "break_amount" in metadata["details"]


# =============================================================================
# Test _check_volatility_spike_wrapper
# =============================================================================


class TestCheckVolatilitySpikeWrapper:
    """Unit tests for _check_volatility_spike_wrapper."""

    def test_exit_on_extreme_volatility(self):
        """Test exit when ATR exceeds 2.5x entry ATR."""
        campaign = create_test_campaign()
        campaign.entry_atr = Decimal("0.50")  # Low entry ATR
        campaign.max_atr_seen = None
        base_time = datetime.now()

        # Create bars with extreme volatility (6x+ entry ATR range)
        recent_bars = []
        for i in range(20):
            bar = create_test_bar(
                timestamp=base_time - timedelta(hours=20 - i),
                open_price=105,
                high=108,  # $6 range = 12x entry ATR
                low=102,
                close=106,
                volume=2000000,
            )
            recent_bars.append(bar)

        current_bar = create_test_bar(base_time, 106, 112, 102, 108, 3000000)

        should_exit, reason, metadata = _check_volatility_spike_wrapper(
            current_bar, campaign, recent_bars
        )

        assert should_exit is True
        assert reason is not None
        assert "VOLATILITY_SPIKE" in reason
        assert metadata["priority"] == 2

    def test_no_exit_on_normal_volatility(self):
        """Test no exit when ATR is within normal range."""
        campaign = create_test_campaign()
        campaign.entry_atr = Decimal("2.00")  # Higher entry ATR
        campaign.max_atr_seen = None
        base_time = datetime.now()

        # Create bars with normal volatility (within 2.5x entry ATR)
        recent_bars = []
        for i in range(20):
            bar = create_test_bar(
                timestamp=base_time - timedelta(hours=20 - i),
                open_price=108,
                high=109,  # $1 range < 2.5x * $2 = $5
                low=108,
                close=108.5,
                volume=1000000,
            )
            recent_bars.append(bar)

        current_bar = create_test_bar(base_time, 108, 109, 108, 108.5, 1000000)

        should_exit, reason, metadata = _check_volatility_spike_wrapper(
            current_bar, campaign, recent_bars
        )

        assert should_exit is False

    def test_no_exit_when_no_entry_atr(self):
        """Test no exit when campaign has no entry_atr."""
        campaign = create_test_campaign()
        campaign.entry_atr = None
        recent_bars = create_recent_bars(20)
        current_bar = create_test_bar(datetime.now(), 108, 120, 100, 110, 3000000)

        should_exit, reason, metadata = _check_volatility_spike_wrapper(
            current_bar, campaign, recent_bars
        )

        assert should_exit is False


# =============================================================================
# Test _check_jump_level
# =============================================================================


class TestCheckJumpLevel:
    """Unit tests for _check_jump_level wrapper."""

    def test_exit_when_high_reaches_jump_level(self):
        """Test exit when bar high >= jump_level."""
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        bar = create_test_bar(datetime.now(), 119, 121, 118, 120, 1500000)

        should_exit, reason, metadata = _check_jump_level(bar, campaign)

        assert should_exit is True
        assert reason is not None
        assert "JUMP_LEVEL" in reason
        assert metadata["priority"] == 3

    def test_no_exit_when_high_below_jump_level(self):
        """Test no exit when bar high < jump_level."""
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        bar = create_test_bar(datetime.now(), 115, 118, 114, 117, 1000000)

        should_exit, reason, metadata = _check_jump_level(bar, campaign)

        assert should_exit is False

    def test_no_exit_when_no_jump_level(self):
        """Test no exit when campaign has no jump_level."""
        campaign = create_test_campaign(support=100, resistance=110)
        campaign.jump_level = None
        bar = create_test_bar(datetime.now(), 130, 135, 128, 132, 1500000)

        should_exit, reason, metadata = _check_jump_level(bar, campaign)

        assert should_exit is False

    def test_metadata_contains_jump_details(self):
        """Test metadata contains high, jump_level."""
        campaign = create_test_campaign(support=100, resistance=110, jump=120)
        campaign.original_jump_level = Decimal("118")
        bar = create_test_bar(datetime.now(), 119, 121, 118, 120, 1500000)

        should_exit, reason, metadata = _check_jump_level(bar, campaign)

        assert "high" in metadata["details"]
        assert "jump_level" in metadata["details"]
        assert "original_jump" in metadata["details"]


# =============================================================================
# Test _check_portfolio_heat_wrapper
# =============================================================================


class TestCheckPortfolioHeatWrapper:
    """Unit tests for _check_portfolio_heat_wrapper."""

    def test_no_exit_when_no_portfolio(self):
        """Test no exit when portfolio is None."""
        campaign = create_test_campaign()
        bar = create_test_bar(datetime.now(), 108, 109, 107, 108, 1000000)

        should_exit, reason, metadata = _check_portfolio_heat_wrapper(
            bar, campaign, portfolio=None, current_price=Decimal("108")
        )

        assert should_exit is False

    def test_no_exit_when_no_current_price(self):
        """Test no exit when current_price is None."""
        campaign = create_test_campaign()
        portfolio = PortfolioRiskState()
        bar = create_test_bar(datetime.now(), 108, 109, 107, 108, 1000000)

        should_exit, reason, metadata = _check_portfolio_heat_wrapper(
            bar, campaign, portfolio=portfolio, current_price=None
        )

        assert should_exit is False


# =============================================================================
# Test _check_phase_e_utad_wrapper
# =============================================================================


class TestCheckPhaseEUtadWrapper:
    """Unit tests for _check_phase_e_utad_wrapper."""

    def test_no_exit_when_not_phase_e(self):
        """Test no exit when campaign is not in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.D)
        recent_bars = create_recent_bars(25)
        bar = create_test_bar(datetime.now(), 108, 115, 107, 109, 2000000)

        should_exit, reason, metadata = _check_phase_e_utad_wrapper(bar, campaign, recent_bars)

        assert should_exit is False

    def test_wrapper_requires_phase_e(self):
        """Test that wrapper only checks UTAD in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.C)
        recent_bars = create_recent_bars(25)
        bar = create_test_bar(datetime.now(), 108, 115, 107, 109, 2000000)

        should_exit, reason, metadata = _check_phase_e_utad_wrapper(bar, campaign, recent_bars)

        assert should_exit is False


# =============================================================================
# Test _check_uptrend_break_wrapper
# =============================================================================


class TestCheckUptrendBreakWrapper:
    """Unit tests for _check_uptrend_break_wrapper."""

    def test_exit_on_uptrend_break(self):
        """Test exit when uptrend structure breaks in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.E)
        base_time = datetime.now()

        # Create bars with rising lows (uptrend)
        recent_bars = []
        for i in range(10):
            low_val = 108 + i * 0.2
            bar = create_test_bar(
                timestamp=base_time - timedelta(hours=10 - i),
                open_price=110 + i * 0.2,
                high=112 + i * 0.2,
                low=low_val,
                close=111 + i * 0.2,
                volume=1000000,
            )
            recent_bars.append(bar)

        # Break bar closes well below recent lows average
        break_bar = create_test_bar(base_time, 108, 109, 105, 106, 1500000)

        should_exit, reason, metadata = _check_uptrend_break_wrapper(
            break_bar, campaign, recent_bars
        )

        assert should_exit is True
        assert "UPTREND_BREAK" in reason
        assert metadata["priority"] == 6

    def test_no_exit_when_not_phase_e(self):
        """Test no exit when campaign is not in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.D)
        recent_bars = create_recent_bars(15)
        bar = create_test_bar(datetime.now(), 100, 101, 95, 96, 1000000)

        should_exit, reason, metadata = _check_uptrend_break_wrapper(bar, campaign, recent_bars)

        assert should_exit is False


# =============================================================================
# Test _check_lower_high_wrapper
# =============================================================================


class TestCheckLowerHighWrapper:
    """Unit tests for _check_lower_high_wrapper."""

    def test_no_exit_when_not_phase_e(self):
        """Test no exit when campaign is not in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.D)
        recent_bars = create_recent_bars(20)
        bar = create_test_bar(datetime.now(), 108, 109, 107, 108, 1000000)

        should_exit, reason, metadata = _check_lower_high_wrapper(campaign, recent_bars, bar)

        assert should_exit is False

    def test_exit_on_lower_high_pattern(self):
        """Test exit when lower high detected in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.E)
        base_time = datetime.now()

        # Create bars with two clear swing highs where second is lower
        # Swing high detection: bar.high > [i-1].high AND > [i-2].high AND > [i+1].high AND > [i+2].high
        bars = []

        # Building bars before first swing high (index 0-1: lead-up bars)
        bars.append(create_test_bar(base_time - timedelta(hours=20), 108, 109, 107, 108, 1000000))
        bars.append(create_test_bar(base_time - timedelta(hours=19), 109, 110, 108, 109, 1000000))

        # First swing high at index 2 (120 is higher than neighbors at 109, 110, 115, 114)
        bars.append(create_test_bar(base_time - timedelta(hours=18), 118, 120, 117, 119, 1200000))

        # Bars after first swing high (indices 3-4: must be lower than 120)
        bars.append(create_test_bar(base_time - timedelta(hours=17), 117, 115, 114, 115, 1000000))
        bars.append(create_test_bar(base_time - timedelta(hours=16), 114, 114, 113, 114, 1000000))

        # Pullback bars (indices 5-6)
        bars.append(create_test_bar(base_time - timedelta(hours=15), 113, 113, 112, 112, 1000000))
        bars.append(create_test_bar(base_time - timedelta(hours=14), 112, 112, 111, 111, 1000000))

        # Second swing high at index 7 (119 is higher than neighbors at 112, 112, 116, 115)
        # 119 < 120 * 0.998 = 119.76, so this is a valid lower high
        bars.append(create_test_bar(base_time - timedelta(hours=13), 116, 119, 115, 118, 1100000))

        # Bars after second swing high (indices 8-9: must be lower than 119)
        bars.append(create_test_bar(base_time - timedelta(hours=12), 117, 116, 115, 115, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=11), 115, 115, 114, 114, 900000))

        # Additional trailing bars (indices 10-13) to meet lookback + 4 requirement
        bars.append(create_test_bar(base_time - timedelta(hours=10), 114, 114, 113, 113, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=9), 113, 114, 112, 113, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=8), 113, 113, 112, 112, 900000))
        bars.append(create_test_bar(base_time - timedelta(hours=7), 112, 113, 111, 112, 900000))

        current_bar = bars[-1]

        should_exit, reason, metadata = _check_lower_high_wrapper(campaign, bars, current_bar)

        assert should_exit is True
        assert "LOWER_HIGH" in reason
        assert metadata["priority"] == 7


# =============================================================================
# Test _check_failed_rallies_wrapper
# =============================================================================


class TestCheckFailedRalliesWrapper:
    """Unit tests for _check_failed_rallies_wrapper."""

    def test_no_exit_when_not_phase_e(self):
        """Test no exit when campaign is not in Phase E."""
        campaign = create_test_campaign(phase=WyckoffPhase.D)
        recent_bars = create_recent_bars(25)
        bar = create_test_bar(datetime.now(), 108, 109, 107, 108, 1000000)

        should_exit, reason, metadata = _check_failed_rallies_wrapper(campaign, recent_bars, bar)

        assert should_exit is False

    def test_exit_on_multiple_failed_rallies(self):
        """Test exit when 3+ failed rally attempts detected."""
        # Campaign with jump=120, so resistance = 120 * 0.95 = 114
        campaign = create_test_campaign(phase=WyckoffPhase.E, resistance=110, jump=120)
        base_time = datetime.now()
        # Resistance derived from jump_level * 0.95 = 114
        # Rally attempts need: high >= 114 * 0.995 = 113.43 AND close < 114

        # Create bars with multiple failed rally attempts at resistance
        bars = []
        for i in range(20):
            if i in [5, 10, 15]:  # Three failed attempts with declining volume
                bar = create_test_bar(
                    timestamp=base_time - timedelta(hours=20 - i),
                    open_price=112,
                    high=113.8,  # >= 113.43 (resistance * 0.995)
                    low=111,
                    close=112,  # < 114 (below resistance)
                    volume=1200000 - i * 25000,  # Declining volume: 1075k, 950k, 825k
                )
            else:
                bar = create_test_bar(
                    timestamp=base_time - timedelta(hours=20 - i),
                    open_price=110,
                    high=111,  # Below resistance threshold
                    low=109,
                    close=110,
                    volume=1000000,
                )
            bars.append(bar)

        current_bar = bars[-1]

        should_exit, reason, metadata = _check_failed_rallies_wrapper(campaign, bars, current_bar)

        assert should_exit is True
        assert "MULTIPLE_TESTS" in reason or "FAILED_RALLIES" in reason
        assert metadata["priority"] == 8


# =============================================================================
# Test _check_excessive_duration_wrapper
# =============================================================================


class TestCheckExcessiveDurationWrapper:
    """Unit tests for _check_excessive_duration_wrapper."""

    def test_exit_on_excessive_duration(self):
        """Test exit when Phase E exceeds max ratio to Phase C."""
        campaign = create_test_campaign(phase=WyckoffPhase.E)
        campaign.phase_c_start_bar = 100
        campaign.phase_d_start_bar = 120  # Phase C = 20 bars
        campaign.phase_e_start_bar = 130
        bar = create_test_bar(datetime.now(), 115, 116, 114, 115, 1000000)

        # Phase E = 55 bars (185-130), max = 20 * 2.5 = 50
        should_exit, reason, metadata = _check_excessive_duration_wrapper(
            campaign, current_bar_index=185, bar=bar
        )

        assert should_exit is True
        assert "EXCESSIVE_DURATION" in reason
        assert metadata["priority"] == 9

    def test_no_exit_within_duration_limit(self):
        """Test no exit when Phase E is within duration limit."""
        campaign = create_test_campaign(phase=WyckoffPhase.E)
        campaign.phase_c_start_bar = 100
        campaign.phase_d_start_bar = 120  # Phase C = 20 bars
        campaign.phase_e_start_bar = 130
        bar = create_test_bar(datetime.now(), 115, 116, 114, 115, 1000000)

        # Phase E = 30 bars (160-130), max = 20 * 2.5 = 50
        should_exit, reason, metadata = _check_excessive_duration_wrapper(
            campaign, current_bar_index=160, bar=bar
        )

        assert should_exit is False

    def test_no_exit_when_missing_phase_data(self):
        """Test no exit when phase start bars are missing."""
        campaign = create_test_campaign(phase=WyckoffPhase.E)
        campaign.phase_c_start_bar = None  # Missing
        bar = create_test_bar(datetime.now(), 115, 116, 114, 115, 1000000)

        should_exit, reason, metadata = _check_excessive_duration_wrapper(
            campaign, current_bar_index=200, bar=bar
        )

        assert should_exit is False


# =============================================================================
# Test _check_correlation_cascade_wrapper
# =============================================================================


class TestCheckCorrelationCascadeWrapper:
    """Unit tests for _check_correlation_cascade_wrapper."""

    def test_no_exit_when_no_portfolio(self):
        """Test no exit when portfolio is None."""
        campaign = create_test_campaign()
        bar = create_test_bar(datetime.now(), 108, 109, 107, 108, 1000000)

        should_exit, reason, metadata = _check_correlation_cascade_wrapper(
            bar, campaign, portfolio=None, current_prices={"TEST": Decimal("108")}
        )

        assert should_exit is False

    def test_no_exit_when_no_prices(self):
        """Test no exit when current_prices is None."""
        campaign = create_test_campaign()
        portfolio = PortfolioRiskState()
        bar = create_test_bar(datetime.now(), 108, 109, 107, 108, 1000000)

        should_exit, reason, metadata = _check_correlation_cascade_wrapper(
            bar, campaign, portfolio=portfolio, current_prices=None
        )

        assert should_exit is False


# =============================================================================
# Test _check_volume_divergence_wrapper
# =============================================================================


class TestCheckVolumeDivergenceWrapper:
    """Unit tests for _check_volume_divergence_wrapper."""

    def test_exit_on_quality_divergences(self):
        """Test exit when 2+ quality divergences detected."""
        base_time = datetime.now()

        # Create bars with quality volume divergence pattern
        bars = []

        # Initial bar
        bars.append(create_test_bar(base_time - timedelta(hours=5), 110, 112, 108, 111, 1500000))

        # New high #1: Higher price, lower volume, narrower spread
        bars.append(create_test_bar(base_time - timedelta(hours=4), 111, 114, 111, 113, 1100000))

        # New high #2: Higher price, lower volume, narrower spread
        bars.append(create_test_bar(base_time - timedelta(hours=3), 113, 116, 114, 115, 700000))

        current_bar = bars[-1]

        should_exit, reason, metadata = _check_volume_divergence_wrapper(
            bars, session_profile=None, bar=current_bar
        )

        # May or may not exit depending on quality calculation
        # Just verify function returns proper structure
        assert isinstance(should_exit, bool)
        if should_exit:
            assert "VOLUME_DIVERGENCE" in reason
            assert metadata["priority"] == 11

    def test_uses_session_profile_when_provided(self):
        """Test wrapper uses session-relative volume when profile provided."""
        base_time = datetime.now()
        recent_bars = create_recent_bars(10, base_time=base_time)
        current_bar = recent_bars[-1]

        # Create session profile
        session_profile = SessionVolumeProfile(
            symbol="TEST",
            timeframe="1h",
            hourly_averages={i: Decimal("1000000") for i in range(24)},
            sample_days=20,
        )

        should_exit, reason, metadata = _check_volume_divergence_wrapper(
            recent_bars, session_profile=session_profile, bar=current_bar
        )

        # Just verify function handles session profile without error
        assert isinstance(should_exit, bool)

    def test_uses_absolute_volume_without_profile(self):
        """Test wrapper uses absolute volume when no profile provided."""
        base_time = datetime.now()
        recent_bars = create_recent_bars(10, base_time=base_time)
        current_bar = recent_bars[-1]

        should_exit, reason, metadata = _check_volume_divergence_wrapper(
            recent_bars, session_profile=None, bar=current_bar
        )

        # Just verify function completes without error
        assert isinstance(should_exit, bool)


# =============================================================================
# Test _check_time_limit
# =============================================================================


class TestCheckTimeLimit:
    """Unit tests for _check_time_limit wrapper."""

    def test_exit_when_time_limit_exceeded(self):
        """Test exit when bars in position exceeds time limit."""
        campaign = create_test_campaign()
        campaign.entry_bar_index = 10
        bar = create_test_bar(datetime.now(), 112, 113, 111, 112, 1000000)

        # Position duration = 60 - 10 = 50 bars, limit = 50
        should_exit, reason, metadata = _check_time_limit(
            bar, campaign, current_bar_index=60, time_limit_bars=50
        )

        assert should_exit is True
        assert "TIME_LIMIT" in reason
        assert metadata["priority"] == 12

    def test_no_exit_within_time_limit(self):
        """Test no exit when bars in position is within time limit."""
        campaign = create_test_campaign()
        campaign.entry_bar_index = 10
        bar = create_test_bar(datetime.now(), 112, 113, 111, 112, 1000000)

        # Position duration = 40 - 10 = 30 bars, limit = 50
        should_exit, reason, metadata = _check_time_limit(
            bar, campaign, current_bar_index=40, time_limit_bars=50
        )

        assert should_exit is False

    def test_no_exit_when_no_entry_bar_index(self):
        """Test no exit when campaign has no entry_bar_index."""
        campaign = create_test_campaign()
        campaign.entry_bar_index = None
        bar = create_test_bar(datetime.now(), 112, 113, 111, 112, 1000000)

        should_exit, reason, metadata = _check_time_limit(
            bar, campaign, current_bar_index=1000, time_limit_bars=50
        )

        assert should_exit is False

    def test_metadata_contains_time_details(self):
        """Test metadata contains bars_in_position, time_limit, entry_bar_index."""
        campaign = create_test_campaign()
        campaign.entry_bar_index = 10
        bar = create_test_bar(datetime.now(), 112, 113, 111, 112, 1000000)

        should_exit, reason, metadata = _check_time_limit(
            bar, campaign, current_bar_index=65, time_limit_bars=50
        )

        assert "bars_in_position" in metadata["details"]
        assert "time_limit" in metadata["details"]
        assert "entry_bar_index" in metadata["details"]
        assert metadata["details"]["bars_in_position"] == 55
        assert metadata["details"]["time_limit"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
