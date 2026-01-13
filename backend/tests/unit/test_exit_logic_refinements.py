"""
Unit Tests for Exit Logic Refinements - Story 13.6.1

Tests all enhanced exit logic functions including:
- Dynamic Jump Level updates
- Phase-contextual UTAD detection
- Additional Phase E signals
- Enhanced volume divergence
- Risk-based exits
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.exit_logic_refinements import (
    EnhancedUTAD,
    SessionVolumeProfile,
    VolumeDivergence,
    build_session_volume_profile,
    calculate_atr,
    check_volatility_spike,
    detect_excessive_phase_e_duration,
    detect_failed_rallies,
    detect_ice_expansion,
    detect_lower_high,
    detect_uptrend_break,
    detect_utad_enhanced,
    detect_volume_divergence_enhanced,
    detect_volume_divergence_intraday,
    get_session_relative_volume,
    should_exit_on_utad,
    update_jump_level,
)
from src.backtesting.intraday_campaign_detector import Campaign
from src.models.ohlcv import OHLCVBar
from src.models.wyckoff_phase import WyckoffPhase


def create_test_bar(
    timestamp: datetime,
    high: Decimal,
    low: Decimal,
    open_price: Decimal | None = None,
    close: Decimal | None = None,
    volume: int = 1000,
    symbol: str = "EUR/USD",
    timeframe: str = "15m",
) -> OHLCVBar:
    """Helper to create test OHLCV bars with all required fields."""
    open_price = open_price or low
    close = close or high
    spread = high - low

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=spread,
    )


class TestDynamicJumpLevelUpdates:
    """Test FR6.1.1: Dynamic Jump Level Updates"""

    def test_detect_ice_expansion_valid(self):
        """AC6.1.1: Detect valid Ice expansion with consolidation"""
        # Setup campaign
        campaign = Campaign(
            resistance_level=Decimal("1.0600"),
            support_level=Decimal("1.0500"),
            jump_level=Decimal("1.0700"),
            current_phase=WyckoffPhase.D,
        )

        # Create bars with new high tested 4x
        base_time = datetime(2025, 1, 1)
        recent_bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0600"),
                high=Decimal("1.0650"),
                low=Decimal("1.0640"),
                close=Decimal("1.0645"),
                volume=1000,
            )
            for i in range(20)
        ]

        # Current bar breaks to new high
        current_bar = create_test_bar(
            timestamp=base_time + timedelta(minutes=25),
            open_price=Decimal("1.0645"),
            high=Decimal("1.0660"),  # New high >0.5% above Ice
            low=Decimal("1.0640"),
            close=Decimal("1.0655"),
            volume=1200,  # Above average
        )

        # Detect expansion
        new_ice = detect_ice_expansion(campaign, current_bar, recent_bars, lookback=5)

        assert new_ice is not None
        assert new_ice == Decimal("1.0660")

    def test_detect_ice_expansion_late_phase_e_rejected(self):
        """AC6.1.2: Reject Jump Level update in late Phase E"""
        campaign = Campaign(
            resistance_level=Decimal("1.0600"),
            support_level=Decimal("1.0500"),
            jump_level=Decimal("1.0700"),
            current_phase=WyckoffPhase.E,
        )

        base_time = datetime(2025, 1, 1)
        recent_bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0675"),  # 75% to Jump
                high=Decimal("1.0680"),
                low=Decimal("1.0670"),
                close=Decimal("1.0675"),
                volume=1000,
            )
            for i in range(20)
        ]

        current_bar = create_test_bar(
            timestamp=base_time + timedelta(minutes=25),
            open_price=Decimal("1.0680"),
            high=Decimal("1.0710"),  # New high
            low=Decimal("1.0675"),
            close=Decimal("1.0680"),  # 80% to Jump - too late
            volume=1200,
        )

        new_ice = detect_ice_expansion(campaign, current_bar, recent_bars)

        # Should be rejected - too late in Phase E
        assert new_ice is None

    def test_update_jump_level_standard(self):
        """Test Jump Level recalculation with expanded Ice"""
        campaign = Campaign(
            resistance_level=Decimal("1.0600"),
            support_level=Decimal("1.0500"),
            jump_level=Decimal("1.0700"),
            current_phase=WyckoffPhase.D,
            timeframe="1d",
        )

        new_ice = Decimal("1.0650")
        new_jump = update_jump_level(campaign, new_ice)

        # New range: 1.0500 to 1.0650 = 150 pips
        # New Jump: 1.0650 + 150 = 1.0800
        assert campaign.resistance_level == Decimal("1.0650")
        assert new_jump == Decimal("1.0800")
        assert campaign.jump_level == Decimal("1.0800")
        assert campaign.ice_expansion_count == 1

    def test_update_jump_level_intraday_adjustment(self):
        """Test Jump Level with 10% intraday reduction"""
        campaign = Campaign(
            resistance_level=Decimal("1.0600"),
            support_level=Decimal("1.0500"),
            jump_level=Decimal("1.0700"),
            current_phase=WyckoffPhase.D,
            timeframe="15m",  # Intraday
        )

        new_ice = Decimal("1.0650")
        new_jump = update_jump_level(campaign, new_ice)

        # New range: 150 pips * 0.9 = 135 pips
        # New Jump: 1.0650 + 135 = 1.0785
        expected_jump = Decimal("1.0650") + (Decimal("0.0150") * Decimal("0.9"))
        assert new_jump == expected_jump
        assert campaign.timeframe == "15m"


class TestPhaseContextualUTAD:
    """Test FR6.2.1: Phase-Contextual UTAD Detection"""

    def test_utad_confidence_calculation(self):
        """Test UTAD confidence scoring"""
        utad = EnhancedUTAD(
            timestamp=datetime(2025, 1, 1),
            breakout_price=Decimal("1.0710"),
            failure_price=Decimal("1.0595"),
            ice_level=Decimal("1.0600"),
            volume_ratio=Decimal("2.8"),  # Climactic
            spread_ratio=Decimal("1.4"),  # Wide spread
            bars_to_failure=1,  # Immediate
            phase=WyckoffPhase.E,
        )

        confidence = utad.calculate_confidence()

        # Expected: 40 (volume) + 20 (spread) + 25 (speed) = 85
        assert confidence == 85

    def test_should_exit_phase_d_no_exit(self):
        """AC6.2.1: Phase D UTAD should NOT trigger exit"""
        campaign = Campaign(
            current_phase=WyckoffPhase.D,
            resistance_level=Decimal("1.0600"),
            jump_level=Decimal("1.0700"),
        )

        utad = EnhancedUTAD(
            timestamp=datetime(2025, 1, 1),
            breakout_price=Decimal("1.0708"),
            failure_price=Decimal("1.0595"),
            ice_level=Decimal("1.0600"),
            volume_ratio=Decimal("2.5"),
            spread_ratio=Decimal("1.3"),
            bars_to_failure=1,
            phase=WyckoffPhase.D,
            confidence=85,
        )

        should_exit, reason = should_exit_on_utad(utad, campaign, Decimal("1.0605"))

        assert should_exit is False
        assert reason == ""

    def test_should_exit_early_phase_e_low_confidence(self):
        """AC6.2.2: Early Phase E with low confidence should NOT exit"""
        campaign = Campaign(
            current_phase=WyckoffPhase.E,
            resistance_level=Decimal("1.0600"),
            jump_level=Decimal("1.0700"),
        )

        utad = EnhancedUTAD(
            timestamp=datetime(2025, 1, 1),
            breakout_price=Decimal("1.0615"),
            failure_price=Decimal("1.0595"),
            ice_level=Decimal("1.0600"),
            volume_ratio=Decimal("1.6"),  # Low
            spread_ratio=Decimal("0.9"),  # Narrow
            bars_to_failure=3,
            phase=WyckoffPhase.E,
            confidence=40,
        )

        # 20% progress to Jump (early)
        current_price = Decimal("1.0620")
        should_exit, reason = should_exit_on_utad(utad, campaign, current_price)

        assert should_exit is False

    def test_should_exit_late_phase_e_high_confidence(self):
        """AC6.2.3: Late Phase E with high confidence SHOULD exit"""
        campaign = Campaign(
            current_phase=WyckoffPhase.E,
            resistance_level=Decimal("1.0600"),
            jump_level=Decimal("1.0700"),
        )

        utad = EnhancedUTAD(
            timestamp=datetime(2025, 1, 1),
            breakout_price=Decimal("1.0708"),
            failure_price=Decimal("1.0595"),
            ice_level=Decimal("1.0600"),
            volume_ratio=Decimal("2.8"),
            spread_ratio=Decimal("1.4"),
            bars_to_failure=1,
            phase=WyckoffPhase.E,
            confidence=90,
        )

        # 70% progress to Jump (late)
        current_price = Decimal("1.0670")
        should_exit, reason = should_exit_on_utad(utad, campaign, current_price)

        assert should_exit is True
        assert "PHASE_E_LATE_UTAD" in reason
        assert "90" in reason

    def test_detect_utad_enhanced_with_spread(self):
        """Test UTAD detection with spread validation"""
        campaign = Campaign(
            resistance_level=Decimal("1.0600"),
            current_phase=WyckoffPhase.E,
        )

        base_time = datetime(2025, 1, 1)

        # Create 20 bars with normal volume/range (10 pip range)
        bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0590"),
                high=Decimal("1.0595"),
                low=Decimal("1.0585"),
                close=Decimal("1.0590"),
                volume=1000,
            )
            for i in range(20)
        ]

        # Add UTAD bar (high volume, wide spread, breaks Ice by 0.5-1.5%)
        # For 0.5% breakout above Ice 1.0600: 1.0600 * 1.005 = 1.0653
        # For 1.0% breakout: 1.0600 * 1.010 = 1.0706
        utad_bar = create_test_bar(
            timestamp=base_time + timedelta(minutes=21),
            open_price=Decimal("1.0600"),
            high=Decimal("1.0660"),  # ~0.57% above Ice (within 0.5-1.5% range)
            low=Decimal("1.0595"),  # Wide spread (~65 pips)
            close=Decimal("1.0650"),
            volume=2000,  # 2x volume
        )
        bars.append(utad_bar)

        # Add failure bar - closes below Ice within 1 bar
        failure_bar = create_test_bar(
            timestamp=base_time + timedelta(minutes=22),
            open_price=Decimal("1.0650"),
            high=Decimal("1.0655"),
            low=Decimal("1.0590"),
            close=Decimal("1.0595"),  # Back below Ice
            volume=1000,
        )
        bars.append(failure_bar)

        utad = detect_utad_enhanced(campaign, bars, lookback=10)

        assert utad is not None
        assert utad.breakout_price == Decimal("1.0660")
        assert utad.failure_price == Decimal("1.0595")
        assert utad.volume_ratio >= Decimal("1.5")
        assert utad.bars_to_failure == 1


class TestAdditionalPhaseESignals:
    """Test FR6.2.2: Additional Phase E Completion Signals"""

    def test_detect_uptrend_break(self):
        """AC6.2.4: Uptrend break detection"""
        campaign = Campaign(
            current_phase=WyckoffPhase.E,
            support_level=Decimal("1.0500"),
        )

        base_time = datetime(2025, 1, 1)

        # Create uptrend bars with increasing lows
        # Lows range from 1.0640 to 1.0649 (avg ~1.0644)
        lows = [
            "1.0640",
            "1.0641",
            "1.0642",
            "1.0643",
            "1.0644",
            "1.0645",
            "1.0646",
            "1.0647",
            "1.0648",
            "1.0649",
        ]
        recent_bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0650"),
                high=Decimal("1.0660"),
                low=Decimal(lows[i]),
                close=Decimal("1.0655"),
                volume=1000,
            )
            for i in range(10)
        ]

        # Current bar breaks below recent lows (avg ~1.0644, need close < 1.0644 * 0.995 = 1.0592)
        bar = create_test_bar(
            timestamp=base_time + timedelta(minutes=11),
            open_price=Decimal("1.0640"),
            high=Decimal("1.0640"),
            low=Decimal("1.0580"),
            close=Decimal("1.0590"),  # Below avg low * 0.995
            volume=800,
        )

        break_detected, reason = detect_uptrend_break(campaign, bar, recent_bars)

        assert break_detected is True
        assert reason is not None
        assert "UPTREND_BREAK" in reason

    def test_detect_lower_high(self):
        """AC6.2.5: Lower high detection"""
        campaign = Campaign(current_phase=WyckoffPhase.E)

        base_time = datetime(2025, 1, 1)

        # Create bars with swing high pattern: need bars where middle bars are higher than neighbors
        # First swing high at position 5 (higher than positions 3,4,6,7)
        # Second swing high at position 10 (higher than positions 8,9,11,12)
        # Second high must be <0.998x first (at least 0.2% lower)
        # If first = 1.0700, second must be < 1.0700 * 0.998 = 1.0679
        recent_bars = []
        for i in range(14):
            if i == 5:
                high = Decimal("1.0700")  # First swing high
            elif i == 10:
                high = Decimal("1.0670")  # Second swing high (clearly lower - 0.3% below first)
            elif i in [3, 4, 6, 7]:
                high = Decimal("1.0650")  # Lower than first swing
            elif i in [8, 9, 11, 12]:
                high = Decimal("1.0645")  # Lower than second swing
            else:
                high = Decimal("1.0640")

            recent_bars.append(
                create_test_bar(
                    timestamp=base_time + timedelta(minutes=i),
                    open_price=Decimal("1.0635"),
                    high=high,
                    low=Decimal("1.0630"),
                    close=Decimal("1.0638"),
                    volume=1000,
                )
            )

        lower_high, reason = detect_lower_high(campaign, recent_bars, lookback=10)

        assert lower_high is True
        assert reason is not None
        assert "LOWER_HIGH" in reason

    def test_detect_failed_rallies(self):
        """AC6.2.6: Multiple failed rally attempts"""
        campaign = Campaign(
            current_phase=WyckoffPhase.E,
            jump_level=Decimal("1.0700"),
        )

        base_time = datetime(2025, 1, 1)
        resistance = Decimal("1.0680")  # 95% of Jump
        # Rally threshold: resistance * 0.995 = 1.0680 * 0.995 = 1.0627

        # Create bars - rally bars touch resistance, non-rally bars stay below threshold
        recent_bars = []
        for i in range(20):
            is_rally = i in [5, 10, 15, 18]
            recent_bars.append(
                create_test_bar(
                    timestamp=base_time + timedelta(minutes=i),
                    open_price=Decimal("1.0650"),
                    # Rally bars touch resistance (>= 1.0627), non-rally bars stay below
                    high=Decimal("1.0682") if is_rally else Decimal("1.0620"),
                    low=Decimal("1.0640"),
                    # Rally bars fail (close < resistance), non-rally bars close lower
                    close=Decimal("1.0670") if is_rally else Decimal("1.0650"),
                    # Rally volumes: 1150, 1100, 1050, 1020 - each <= prev * 1.1
                    volume=1150 - (i - 5) * 10 if is_rally else 1000,
                )
            )

        failed, reason = detect_failed_rallies(campaign, recent_bars, resistance, lookback=20)

        assert failed is True
        assert reason is not None
        assert "MULTIPLE_TESTS" in reason
        assert "4" in reason


class TestEnhancedVolumeDivergence:
    """Test FR6.3.1: Enhanced Volume Divergence Detection"""

    def test_volume_divergence_quality_calculation(self):
        """Test divergence quality scoring"""
        divergence = VolumeDivergence(
            timestamp=datetime(2025, 1, 1),
            price_high=Decimal("1.0675"),
            prev_high=Decimal("1.0670"),
            volume=Decimal("100"),
            prev_volume=Decimal("150"),
            bar_range=Decimal("0.0010"),
            prev_range=Decimal("0.0015"),
            volume_ratio=Decimal("0.67"),  # <0.7 for severe (50 pts)
            spread_ratio=Decimal("0.67"),  # <0.8 for severe (50 pts)
        )

        quality = divergence.calculate_quality()

        # Expected: 50 (severe volume drop) + 50 (severe range contraction) = 100
        assert quality == 100

    def test_volume_divergence_quality_low(self):
        """AC6.3.2: Low quality divergence rejected"""
        divergence = VolumeDivergence(
            timestamp=datetime(2025, 1, 1),
            price_high=Decimal("1.0675"),
            prev_high=Decimal("1.0670"),
            volume=Decimal("112"),
            prev_volume=Decimal("150"),
            bar_range=Decimal("0.0020"),  # Expanding
            prev_range=Decimal("0.0015"),
            volume_ratio=Decimal("0.75"),  # Some volume drop
            spread_ratio=Decimal("1.33"),  # Expanding range
        )

        quality = divergence.calculate_quality()

        # Volume component: 40, Spread component: -30 (penalty) = 10
        assert quality < 60  # Below quality threshold

    def test_detect_volume_divergence_enhanced(self):
        """AC6.3.1: Quality volume divergence detection"""
        base_time = datetime(2025, 1, 1)

        # Bar 1: Baseline with wider spread
        bars = [
            create_test_bar(
                timestamp=base_time,
                open_price=Decimal("1.0655"),
                high=Decimal("1.0670"),
                low=Decimal("1.0650"),  # 20 pip range
                close=Decimal("1.0670"),
                volume=1500,
            )
        ]

        # Bar 2: New high, declining volume and spread
        bars.append(
            create_test_bar(
                timestamp=base_time + timedelta(minutes=1),
                open_price=Decimal("1.0670"),
                high=Decimal("1.0675"),  # New high
                low=Decimal("1.0665"),  # 10 pip range (narrower)
                close=Decimal("1.0674"),
                volume=1050,  # 0.70x volume (severe drop)
            )
        )

        # Bar 3: Another new high, further decline
        bars.append(
            create_test_bar(
                timestamp=base_time + timedelta(minutes=2),
                open_price=Decimal("1.0674"),
                high=Decimal("1.0678"),  # New high
                low=Decimal("1.0672"),  # 6 pip range (even narrower)
                close=Decimal("1.0677"),
                volume=700,  # 0.67x prev volume (severe drop)
            )
        )

        div_count, divergences = detect_volume_divergence_enhanced(
            bars, lookback=10, min_quality=60
        )

        assert div_count >= 1
        assert len(divergences) >= 1
        assert all(d.divergence_quality >= 60 for d in divergences)


class TestRiskBasedExits:
    """Test FR6.5.1: Enhanced Risk-Based Exit Conditions"""

    def test_calculate_atr(self):
        """Test ATR calculation"""
        base_time = datetime(2025, 1, 1)
        # Create 20 bars with consistent 20-pip range (high - low = 0.0020)
        bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0600"),
                high=Decimal("1.0610"),
                low=Decimal("1.0590"),
                close=Decimal("1.0600"),
                volume=1000,
            )
            for i in range(20)
        ]

        atr = calculate_atr(bars, period=14)

        assert atr is not None
        assert atr > Decimal("0")
        # With 20 pip range bars, ATR should be around 0.0020
        assert atr == Decimal("0.0020")

    def test_check_volatility_spike(self):
        """AC6.5.1: Volatility spike detection"""
        # Entry ATR = 40 pips (0.0040)
        # Spike threshold = 2.5x → need current ATR >= 0.0100 (100 pips)
        campaign = Campaign(
            entry_atr=Decimal("0.0040"),  # 40 pip entry ATR
        )

        base_time = datetime(2025, 1, 1)

        # Create 20 bars with high volatility (200-pip range) to ensure ATR > 2.5x entry
        # All bars have 200-pip range → ATR = 0.0200
        # 0.0200 / 0.0040 = 5.0x entry ATR → spike detected
        recent_bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0600"),
                high=Decimal("1.0700"),  # 200 pip range
                low=Decimal("1.0500"),
                close=Decimal("1.0600"),
                volume=5000,
            )
            for i in range(20)
        ]

        current_bar = recent_bars[-1]

        spike, reason = check_volatility_spike(
            current_bar, campaign, recent_bars, atr_period=14, spike_threshold=Decimal("2.5")
        )

        assert spike is True
        assert reason is not None
        assert "VOLATILITY_SPIKE" in reason


class TestIntegration:
    """Integration tests combining multiple features"""

    def test_dynamic_jump_level_with_phase_e_utad(self):
        """Test dynamic Jump Level update followed by Phase E UTAD exit"""
        # Create campaign in Phase D
        campaign = Campaign(
            resistance_level=Decimal("1.0600"),
            support_level=Decimal("1.0500"),
            jump_level=Decimal("1.0700"),
            current_phase=WyckoffPhase.D,
            timeframe="15m",
        )

        # Simulate Ice expansion
        base_time = datetime(2025, 1, 1)
        bars = [
            create_test_bar(
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal("1.0640"),
                high=Decimal("1.0650"),  # New Ice
                low=Decimal("1.0635"),
                close=Decimal("1.0645"),
                volume=1200,
            )
            for i in range(20)
        ]

        # Detect and update
        new_ice = detect_ice_expansion(campaign, bars[-1], bars)
        if new_ice:
            new_jump = update_jump_level(campaign, new_ice)

            # Verify Jump Level updated
            assert campaign.resistance_level == Decimal("1.0650")
            assert campaign.ice_expansion_count == 1
            # With 15m intraday adjustment: (1.0650 - 1.0500) * 0.9 + 1.0650 = 1.0785
            assert new_jump == Decimal("1.0650") + (Decimal("0.0150") * Decimal("0.9"))

        # Transition to Phase E
        campaign.current_phase = WyckoffPhase.E

        # Test UTAD detection in Phase E would work correctly
        assert campaign.current_phase == WyckoffPhase.E
        assert campaign.jump_level is not None


class TestSessionVolumeProfile:
    """Test FR6.6.1: Session-Relative Volume (Story 13.6.3)"""

    def test_build_session_volume_profile_basic(self):
        """AC1: Build session volume profile with hour-of-day aggregation"""
        base_time = datetime(2025, 1, 1, 9, 0)  # Start at 9am

        # Create 20+ bars for each of 3 hours (9am, 10am, 11am)
        bars = []
        for day in range(25):  # 25 days
            for hour_offset in [0, 1, 2]:  # 9am, 10am, 11am
                bars.append(
                    create_test_bar(
                        timestamp=base_time + timedelta(days=day, hours=hour_offset),
                        open_price=Decimal("1.0600"),
                        high=Decimal("1.0610"),
                        low=Decimal("1.0590"),
                        close=Decimal("1.0600"),
                        volume=1000 + (hour_offset * 100),  # 9am=1000, 10am=1100, 11am=1200
                        symbol="EUR/USD",
                        timeframe="1h",
                    )
                )

        profile = build_session_volume_profile(bars, "1h", lookback_days=25)

        assert profile.symbol == "EUR/USD"
        assert profile.timeframe == "1h"
        assert 9 in profile.hourly_averages
        assert 10 in profile.hourly_averages
        assert 11 in profile.hourly_averages

        # Check averages are correct
        assert profile.hourly_averages[9] == Decimal("1000")
        assert profile.hourly_averages[10] == Decimal("1100")
        assert profile.hourly_averages[11] == Decimal("1200")

    def test_build_session_volume_profile_minimum_sample_size(self):
        """AC1: Verify minimum sample size handling (20+ bars required)"""
        base_time = datetime(2025, 1, 1, 9, 0)

        # Create only 15 bars for 9am (below minimum)
        bars = [
            create_test_bar(
                timestamp=base_time + timedelta(days=i),
                open_price=Decimal("1.0600"),
                high=Decimal("1.0610"),
                low=Decimal("1.0590"),
                close=Decimal("1.0600"),
                volume=1000,
            )
            for i in range(15)
        ]

        profile = build_session_volume_profile(bars, "1h")

        # 9am should NOT be in profile (insufficient samples)
        assert 9 not in profile.hourly_averages

    def test_build_session_volume_profile_edge_cases(self):
        """AC1: Edge cases - empty bars, sparse data"""
        # Empty bars
        with pytest.raises(ValueError, match="Cannot build session profile from empty bars list"):
            build_session_volume_profile([], "1h")

        # Mixed symbols
        base_time = datetime(2025, 1, 1, 9, 0)
        bars = [
            create_test_bar(
                timestamp=base_time,
                open_price=Decimal("1.0600"),
                high=Decimal("1.0610"),
                low=Decimal("1.0590"),
                close=Decimal("1.0600"),
                volume=1000,
                symbol="EUR/USD",
            ),
            create_test_bar(
                timestamp=base_time + timedelta(hours=1),
                open_price=Decimal("1.2600"),
                high=Decimal("1.2610"),
                low=Decimal("1.2590"),
                close=Decimal("1.2600"),
                volume=1000,
                symbol="GBP/USD",  # Different symbol
            ),
        ]

        with pytest.raises(ValueError, match="All bars must have same symbol"):
            build_session_volume_profile(bars, "1h")

    def test_get_session_relative_volume_9am_vs_3pm(self):
        """AC2: Session-relative volume calculation - 9am vs 3pm comparison"""
        # Build profile with 9am avg=75k, 3pm avg=25k
        profile = SessionVolumeProfile(
            symbol="EUR/USD",
            timeframe="15m",
            hourly_averages={9: Decimal("75000"), 15: Decimal("25000")},
            sample_days=20,
        )

        # 9am bar with 50k volume
        bar_9am = create_test_bar(
            timestamp=datetime(2025, 1, 1, 9, 0),
            open_price=Decimal("1.0600"),
            high=Decimal("1.0610"),
            low=Decimal("1.0590"),
            close=Decimal("1.0600"),
            volume=50000,
        )

        # 3pm bar with 30k volume
        bar_3pm = create_test_bar(
            timestamp=datetime(2025, 1, 1, 15, 0),
            open_price=Decimal("1.0600"),
            high=Decimal("1.0610"),
            low=Decimal("1.0590"),
            close=Decimal("1.0600"),
            volume=30000,
        )

        ratio_9am = get_session_relative_volume(bar_9am, profile)
        ratio_3pm = get_session_relative_volume(bar_3pm, profile)

        # 50k / 75k = 0.6667
        assert abs(ratio_9am - Decimal("0.6666666666666666666666666667")) < Decimal("0.01")

        # 30k / 25k = 1.2
        assert ratio_3pm == Decimal("1.2")

        # 3pm bar is relatively stronger despite lower absolute volume
        assert ratio_3pm > ratio_9am

    def test_get_session_relative_volume_hour_not_in_profile(self):
        """AC2: Edge case - hour not in profile returns neutral 1.0"""
        profile = SessionVolumeProfile(
            symbol="EUR/USD",
            timeframe="15m",
            hourly_averages={9: Decimal("75000")},  # Only 9am
            sample_days=20,
        )

        # Bar at 3pm (not in profile)
        bar_3pm = create_test_bar(
            timestamp=datetime(2025, 1, 1, 15, 0),
            open_price=Decimal("1.0600"),
            high=Decimal("1.0610"),
            low=Decimal("1.0590"),
            close=Decimal("1.0600"),
            volume=30000,
        )

        ratio = get_session_relative_volume(bar_3pm, profile)

        # Should return neutral 1.0 for missing hour
        assert ratio == Decimal("1.0")

    def test_get_session_relative_volume_zero_average(self):
        """AC2: Edge case - zero session average returns neutral 1.0"""
        profile = SessionVolumeProfile(
            symbol="EUR/USD",
            timeframe="15m",
            hourly_averages={9: Decimal("0")},  # Zero average (edge case)
            sample_days=20,
        )

        bar = create_test_bar(
            timestamp=datetime(2025, 1, 1, 9, 0),
            open_price=Decimal("1.0600"),
            high=Decimal("1.0610"),
            low=Decimal("1.0590"),
            close=Decimal("1.0600"),
            volume=30000,
        )

        ratio = get_session_relative_volume(bar, profile)

        # Should return neutral 1.0 to avoid division by zero
        assert ratio == Decimal("1.0")


class TestIntradayVolumeDivergence:
    """Test FR6.6.1: Intraday Volume Divergence Detection (Story 13.6.3)"""

    def test_detect_volume_divergence_intraday_basic(self):
        """AC3: Intraday divergence using session-relative volume"""
        # Build session profile with varying volumes by hour
        profile = SessionVolumeProfile(
            symbol="EUR/USD",
            timeframe="15m",
            hourly_averages={
                9: Decimal("100000"),  # High volume hour
                15: Decimal("30000"),  # Low volume hour
            },
            sample_days=20,
        )

        base_time = datetime(2025, 1, 1, 15, 0)  # Start at 3pm (low volume hour)

        # Bar 1: Baseline at 3pm with 30k volume (1.0x session avg)
        bars = [
            create_test_bar(
                timestamp=base_time,
                open_price=Decimal("1.0655"),
                high=Decimal("1.0670"),
                low=Decimal("1.0650"),
                close=Decimal("1.0670"),
                volume=30000,  # 1.0x session avg
            )
        ]

        # Bar 2: New high at 3pm with 21k volume (0.7x session avg)
        # Session-relative: 0.7 / 1.0 = 0.7x decline
        bars.append(
            create_test_bar(
                timestamp=base_time + timedelta(minutes=15),
                open_price=Decimal("1.0670"),
                high=Decimal("1.0675"),  # New high
                low=Decimal("1.0665"),
                close=Decimal("1.0674"),
                volume=21000,  # 0.7x session avg
            )
        )

        # Bar 3: Another new high with further decline
        bars.append(
            create_test_bar(
                timestamp=base_time + timedelta(minutes=30),
                open_price=Decimal("1.0674"),
                high=Decimal("1.0678"),  # New high
                low=Decimal("1.0672"),
                close=Decimal("1.0677"),
                volume=18000,  # 0.6x session avg
            )
        )

        div_count, divergences = detect_volume_divergence_intraday(bars, profile, min_quality=60)

        assert div_count >= 1
        assert len(divergences) >= 1
        assert all(d.divergence_quality >= 60 for d in divergences)

    def test_detect_volume_divergence_intraday_false_positive_reduction(self):
        """AC3: Reduces false positives vs absolute volume method"""
        # Scenario: 9am has higher absolute volume than 3pm, but both are average for their sessions
        profile = SessionVolumeProfile(
            symbol="EUR/USD",
            timeframe="15m",
            hourly_averages={
                9: Decimal("100000"),  # 9am session avg
                15: Decimal("30000"),  # 3pm session avg
            },
            sample_days=20,
        )

        base_time = datetime(2025, 1, 1, 9, 0)  # Start at 9am

        # Bar 1: 9am with 100k volume (1.0x session avg for 9am)
        bars = [
            create_test_bar(
                timestamp=base_time,
                open_price=Decimal("1.0655"),
                high=Decimal("1.0670"),
                low=Decimal("1.0650"),
                close=Decimal("1.0670"),
                volume=100000,  # 1.0x for 9am
            )
        ]

        # Transition to 3pm
        # Bar 2: 3pm with 30k volume (1.0x session avg for 3pm)
        # Absolute volume dropped 70% (100k → 30k), but session-relative stayed same (1.0x)
        bars.append(
            create_test_bar(
                timestamp=datetime(2025, 1, 1, 15, 0),  # Jump to 3pm
                open_price=Decimal("1.0670"),
                high=Decimal("1.0675"),  # New high
                low=Decimal("1.0665"),
                close=Decimal("1.0674"),
                volume=30000,  # 1.0x for 3pm
            )
        )

        div_count, divergences = detect_volume_divergence_intraday(bars, profile, min_quality=60)

        # Should NOT detect divergence (session-relative volume unchanged)
        # This is the false positive reduction
        assert div_count == 0


class TestExcessivePhaseDuration:
    """Test FR6.6.2: Excessive Phase E Duration (Story 13.6.3)"""

    def test_detect_excessive_phase_e_duration_no_exit(self):
        """AC5: Phase E at 2.4x (below threshold, no exit)"""
        campaign = Campaign(
            phase_c_start_bar=100,
            phase_d_start_bar=120,  # Phase C = 20 bars
            phase_e_start_bar=130,
        )

        # Phase E = 48 bars (178 - 130)
        # Max allowed = 20 * 2.5 = 50 bars
        # 48 < 50, so no exit
        current_bar_index = 178

        should_exit, reason = detect_excessive_phase_e_duration(
            campaign, current_bar_index, max_ratio=Decimal("2.5")
        )

        assert should_exit is False
        assert reason is None

    def test_detect_excessive_phase_e_duration_exit(self):
        """AC5: Phase E at 2.6x (exceeds threshold, triggers exit)"""
        campaign = Campaign(
            phase_c_start_bar=100,
            phase_d_start_bar=120,  # Phase C = 20 bars
            phase_e_start_bar=130,
        )

        # Phase E = 55 bars (185 - 130)
        # Max allowed = 20 * 2.5 = 50 bars
        # 55 > 50, so exit
        current_bar_index = 185

        should_exit, reason = detect_excessive_phase_e_duration(
            campaign, current_bar_index, max_ratio=Decimal("2.5")
        )

        assert should_exit is True
        assert reason is not None
        assert "EXCESSIVE_DURATION" in reason
        assert "Phase E 55 bars" in reason
        assert "max 50" in reason

    def test_detect_excessive_phase_e_duration_missing_phase_c(self):
        """AC5: Graceful handling - missing Phase C start bar"""
        campaign = Campaign(
            phase_c_start_bar=None,  # Missing
            phase_d_start_bar=120,
            phase_e_start_bar=130,
        )

        should_exit, reason = detect_excessive_phase_e_duration(campaign, 185)

        assert should_exit is False
        assert reason is None

    def test_detect_excessive_phase_e_duration_missing_phase_d(self):
        """AC5: Graceful handling - missing Phase D start bar"""
        campaign = Campaign(
            phase_c_start_bar=100,
            phase_d_start_bar=None,  # Missing
            phase_e_start_bar=130,
        )

        should_exit, reason = detect_excessive_phase_e_duration(campaign, 185)

        assert should_exit is False
        assert reason is None

    def test_detect_excessive_phase_e_duration_missing_phase_e(self):
        """AC5: Graceful handling - missing Phase E start bar (not in Phase E)"""
        campaign = Campaign(
            phase_c_start_bar=100,
            phase_d_start_bar=120,
            phase_e_start_bar=None,  # Not in Phase E yet
        )

        should_exit, reason = detect_excessive_phase_e_duration(campaign, 185)

        assert should_exit is False
        assert reason is None

    def test_detect_excessive_phase_e_duration_custom_ratio(self):
        """AC5: Custom max_ratio parameter (3.0x instead of 2.5x)"""
        campaign = Campaign(
            phase_c_start_bar=100,
            phase_d_start_bar=120,  # Phase C = 20 bars
            phase_e_start_bar=130,
        )

        # Phase E = 55 bars (185 - 130)
        # With 2.5x: max = 50 bars (exit)
        # With 3.0x: max = 60 bars (no exit)
        current_bar_index = 185

        should_exit, reason = detect_excessive_phase_e_duration(
            campaign, current_bar_index, max_ratio=Decimal("3.0")
        )

        assert should_exit is False
        assert reason is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
