"""
Unit tests for Portfolio Risk Management (Story 13.6.4).

Tests:
- AC1: Portfolio Risk State Model
- AC2: Portfolio Heat Exit - Profitable Position
- AC3: Portfolio Heat Exit - Unprofitable Position
- AC4: Currency Correlation Calculation
- AC5: Correlation Cascade Detection
- AC6: Cascade Threshold Not Met
- AC7: Phase-Weighted Exit Priority
- AC8: Weighted Average Entry for Multi-Pattern Campaigns

Author: Story 13.6.4 Implementation
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import Campaign, CampaignState
from src.backtesting.portfolio_risk import (
    PortfolioRiskState,
    calculate_campaign_profit_pct,
    calculate_weighted_entry_price,
    check_correlation_cascade,
    check_portfolio_heat,
    get_campaigns_by_exit_priority,
    get_currency_correlation,
    get_exit_priority,
    parse_currency_pair,
)
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.wyckoff_phase import WyckoffPhase

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_bar():
    """Create sample OHLCV bar."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="1h",
        timestamp=datetime.utcnow(),
        open=Decimal("1.0600"),
        high=Decimal("1.0650"),
        low=Decimal("1.0580"),
        close=Decimal("1.0630"),
        volume=150000,
        spread=Decimal("0.0070"),
    )


@pytest.fixture
def sample_spring(sample_bar):
    """Create sample Spring pattern."""
    return Spring(
        bar=sample_bar,
        bar_index=100,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("1.0600"),
        spring_low=Decimal("1.0580"),
        recovery_price=Decimal("1.0620"),
        detection_timestamp=datetime.utcnow(),
        trading_range_id=uuid4(),
    )


@pytest.fixture
def sample_sos(sample_bar):
    """Create sample SOS breakout pattern."""
    return SOSBreakout(
        bar=sample_bar,
        breakout_pct=Decimal("0.02"),
        volume_ratio=Decimal("2.0"),
        ice_reference=Decimal("1.0600"),
        breakout_price=Decimal("1.0640"),
        detection_timestamp=datetime.utcnow(),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.4"),
        close_position=Decimal("0.75"),
        spread=Decimal("0.0070"),
    )


@pytest.fixture
def sample_lps(sample_bar):
    """Create sample LPS pattern."""
    return LPS(
        bar=sample_bar,
        distance_from_ice=Decimal("0.015"),
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.6"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.8"),
        volume_ratio_vs_sos=Decimal("0.6"),
        pullback_spread=Decimal("0.0050"),
        range_avg_spread=Decimal("0.0060"),
        spread_ratio=Decimal("0.83"),
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=uuid4(),
        held_support=True,
        pullback_low=Decimal("1.0610"),
        ice_level=Decimal("1.0600"),
        sos_volume=200000,
        pullback_volume=120000,
        bars_after_sos=5,
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime.utcnow(),
        detection_timestamp=datetime.utcnow(),
        trading_range_id=uuid4(),
        atr_14=Decimal("0.0040"),
        stop_distance=Decimal("0.0030"),
        stop_distance_pct=Decimal("3.0"),
        stop_price=Decimal("1.0570"),
        volume_trend="DECLINING",
        volume_trend_quality="EXCELLENT",
        volume_trend_bonus=5,
    )


@pytest.fixture
def sample_campaign_phase_c(sample_spring):
    """Create sample campaign in Phase C."""
    return Campaign(
        campaign_id=str(uuid4()),
        start_time=datetime.utcnow(),
        patterns=[sample_spring],
        state=CampaignState.ACTIVE,
        current_phase=WyckoffPhase.C,
        support_level=Decimal("1.0580"),
        resistance_level=Decimal("1.0650"),
        strength_score=0.85,
        risk_per_share=Decimal("0.0040"),
        range_width_pct=Decimal("0.66"),
        jump_level=Decimal("1.0720"),
    )


@pytest.fixture
def sample_campaign_phase_d(sample_spring, sample_sos):
    """Create sample campaign in Phase D."""
    return Campaign(
        campaign_id=str(uuid4()),
        start_time=datetime.utcnow(),
        patterns=[sample_spring, sample_sos],
        state=CampaignState.ACTIVE,
        current_phase=WyckoffPhase.D,
        support_level=Decimal("1.0580"),
        resistance_level=Decimal("1.0650"),
        strength_score=0.85,
        risk_per_share=Decimal("0.0040"),
        range_width_pct=Decimal("0.66"),
        jump_level=Decimal("1.0720"),
    )


@pytest.fixture
def sample_campaign_phase_e(sample_spring, sample_sos, sample_lps):
    """Create sample campaign in Phase E."""
    return Campaign(
        campaign_id=str(uuid4()),
        start_time=datetime.utcnow(),
        patterns=[sample_spring, sample_sos, sample_lps],
        state=CampaignState.ACTIVE,
        current_phase=WyckoffPhase.E,
        support_level=Decimal("1.0580"),
        resistance_level=Decimal("1.0650"),
        strength_score=0.85,
        risk_per_share=Decimal("0.0040"),
        range_width_pct=Decimal("0.66"),
        jump_level=Decimal("1.0720"),
    )


# ============================================================================
# AC1: Portfolio Risk State Model
# ============================================================================


class TestPortfolioRiskState:
    """Test PortfolioRiskState dataclass."""

    def test_portfolio_state_initialization(self):
        """Test PortfolioRiskState initializes with correct defaults."""
        portfolio = PortfolioRiskState()

        assert len(portfolio.active_campaigns) == 0
        assert portfolio.total_heat_pct == Decimal("0")
        assert portfolio.max_heat_pct == Decimal("10.0")

    def test_add_campaign_success(self, sample_campaign_phase_d):
        """Test adding campaign within heat limits."""
        portfolio = PortfolioRiskState()

        success = portfolio.add_campaign(sample_campaign_phase_d, Decimal("3.0"))

        assert success is True
        assert len(portfolio.active_campaigns) == 1
        assert portfolio.total_heat_pct == Decimal("3.0")

    def test_add_campaign_rejected_heat_limit(self, sample_campaign_phase_d):
        """Test campaign rejected when heat limit exceeded."""
        portfolio = PortfolioRiskState()
        portfolio.total_heat_pct = Decimal("9.0")

        success = portfolio.add_campaign(sample_campaign_phase_d, Decimal("2.0"))

        assert success is False
        assert len(portfolio.active_campaigns) == 0
        assert portfolio.total_heat_pct == Decimal("9.0")

    def test_remove_campaign(self, sample_campaign_phase_d):
        """Test removing campaign from portfolio."""
        portfolio = PortfolioRiskState()
        portfolio.add_campaign(sample_campaign_phase_d, Decimal("3.0"))

        portfolio.remove_campaign(sample_campaign_phase_d.campaign_id)

        assert len(portfolio.active_campaigns) == 0

    def test_get_underwater_campaigns(self, sample_campaign_phase_d, sample_spring, sample_sos):
        """Test getting underwater campaigns."""
        portfolio = PortfolioRiskState()

        # Create campaign with entry at 1.0630 (avg of spring 1.0620 + sos 1.0640)
        campaign = sample_campaign_phase_d
        portfolio.add_campaign(campaign, Decimal("3.0"))

        # Current price significantly below entry = underwater
        current_prices = {"EUR/USD": Decimal("1.0520")}  # Well below entry (-1.03%)

        underwater = portfolio.get_underwater_campaigns(current_prices, Decimal("-1.0"))

        assert len(underwater) == 1
        assert underwater[0].campaign_id == campaign.campaign_id

    def test_recalculate_heat(self, sample_campaign_phase_d):
        """Test recalculating portfolio heat."""
        portfolio = PortfolioRiskState()
        campaign = sample_campaign_phase_d
        campaign.risk_per_share = Decimal("0.0040")
        campaign.support_level = Decimal("1.0580")

        portfolio.add_campaign(campaign, Decimal("3.0"))
        heat = portfolio.recalculate_heat()

        # Risk pct = (0.0040 / 1.0580) * 100 ≈ 0.378%
        assert heat > Decimal("0")
        assert heat < Decimal("1.0")


# ============================================================================
# AC2: Portfolio Heat Exit - Profitable Position
# ============================================================================


class TestPortfolioHeatExit:
    """Test portfolio heat exit logic."""

    def test_heat_exit_profitable_position(self, sample_campaign_phase_e):
        """AC2: Exit profitable position when heat at 81% of max."""
        portfolio = PortfolioRiskState()
        portfolio.total_heat_pct = Decimal("9.2")  # 92% of max 10%
        portfolio.max_heat_pct = Decimal("10.0")

        campaign = sample_campaign_phase_e
        campaign.patterns[0].recovery_price = Decimal("1.0500")  # Entry
        campaign.patterns[1].breakout_price = Decimal("1.0500")  # Same entry
        campaign.patterns[2].bar.close = Decimal("1.0500")  # Same entry

        # Add campaign to portfolio
        portfolio.active_campaigns.append(campaign)

        current_price = Decimal("1.0650")  # +1.43% profit

        should_exit, reason = check_portfolio_heat(
            portfolio, campaign, current_price, heat_threshold_pct=Decimal("80.0")
        )

        assert should_exit is True
        assert "PORTFOLIO_HEAT" in reason
        assert "9.2%" in reason

    def test_heat_no_exit_below_threshold(self, sample_campaign_phase_e):
        """Test no exit when heat below threshold."""
        portfolio = PortfolioRiskState()
        portfolio.total_heat_pct = Decimal("7.5")  # 75% of max
        portfolio.max_heat_pct = Decimal("10.0")

        campaign = sample_campaign_phase_e
        current_price = Decimal("1.0650")

        should_exit, reason = check_portfolio_heat(
            portfolio, campaign, current_price, heat_threshold_pct=Decimal("80.0")
        )

        assert should_exit is False
        assert reason is None


# ============================================================================
# AC3: Portfolio Heat Exit - Unprofitable Position
# ============================================================================


class TestPortfolioHeatUnprofitable:
    """Test portfolio heat exit does not exit unprofitable positions."""

    def test_heat_no_exit_unprofitable(self, sample_campaign_phase_e):
        """AC3: No exit for unprofitable position even with high heat."""
        portfolio = PortfolioRiskState()
        portfolio.total_heat_pct = Decimal("9.5")  # 95% of max
        portfolio.max_heat_pct = Decimal("10.0")

        campaign = sample_campaign_phase_e
        campaign.patterns[0].recovery_price = Decimal("1.0700")  # Entry
        current_price = Decimal("1.0650")  # -0.47% loss

        should_exit, reason = check_portfolio_heat(
            portfolio, campaign, current_price, heat_threshold_pct=Decimal("80.0")
        )

        assert should_exit is False
        assert reason is None


# ============================================================================
# AC4: Currency Correlation Calculation
# ============================================================================


class TestCurrencyCorrelation:
    """Test currency correlation calculation."""

    def test_parse_currency_pair_slash_format(self):
        """Test parsing EUR/USD format."""
        base, quote = parse_currency_pair("EUR/USD")

        assert base == "EUR"
        assert quote == "USD"

    def test_parse_currency_pair_no_slash(self):
        """Test parsing EURUSD format."""
        base, quote = parse_currency_pair("EURUSD")

        assert base == "EUR"
        assert quote == "USD"

    def test_same_quote_currency_high_correlation(self):
        """AC4: EUR/USD vs GBP/USD high correlation (0.8+)."""
        correlation = get_currency_correlation("EUR/USD", "GBP/USD")

        assert correlation >= Decimal("0.8")
        assert correlation == Decimal("0.85")

    def test_same_base_currency_high_correlation(self):
        """AC4: EUR/GBP vs EUR/JPY high correlation (0.8+)."""
        correlation = get_currency_correlation("EUR/GBP", "EUR/JPY")

        assert correlation >= Decimal("0.8")
        assert correlation == Decimal("0.80")

    def test_no_shared_currencies_low_correlation(self):
        """Test no shared currencies = low correlation."""
        correlation = get_currency_correlation("EUR/GBP", "AUD/NZD")

        assert correlation < Decimal("0.5")
        assert correlation == Decimal("0.20")

    def test_same_pair_perfect_correlation(self):
        """Test same pair = 1.0 correlation."""
        correlation = get_currency_correlation("EUR/USD", "EUR/USD")

        assert correlation == Decimal("1.0")


# ============================================================================
# AC5: Correlation Cascade Detection
# ============================================================================


class TestCorrelationCascade:
    """Test correlation cascade detection."""

    def test_cascade_detected_three_correlated(self, sample_bar):
        """AC5: 3 correlated underwater positions trigger exit."""
        portfolio = PortfolioRiskState()

        # Create 3 campaigns: EUR/USD, GBP/USD, AUD/USD (all USD pairs - correlated)
        campaigns = []
        symbols = ["EUR/USD", "GBP/USD", "AUD/USD"]

        for symbol in symbols:
            bar = OHLCVBar(
                symbol=symbol,
                timeframe="1h",
                timestamp=datetime.utcnow(),
                open=Decimal("1.0600"),
                high=Decimal("1.0650"),
                low=Decimal("1.0580"),
                close=Decimal("1.0630"),
                volume=150000,
                spread=Decimal("0.0070"),
            )

            spring = Spring(
                bar=bar,
                bar_index=100,
                penetration_pct=Decimal("0.02"),
                volume_ratio=Decimal("0.4"),
                recovery_bars=1,
                creek_reference=Decimal("1.0600"),
                spring_low=Decimal("1.0580"),
                recovery_price=Decimal("1.0700"),  # Entry at 1.07
                detection_timestamp=datetime.utcnow(),
                trading_range_id=uuid4(),
            )

            campaign = Campaign(
                campaign_id=str(uuid4()),
                start_time=datetime.utcnow(),
                patterns=[spring],
                state=CampaignState.ACTIVE,
                current_phase=WyckoffPhase.D,
                support_level=Decimal("1.0580"),
                resistance_level=Decimal("1.0650"),
            )
            campaigns.append(campaign)
            portfolio.add_campaign(campaign, Decimal("2.0"))

        # All positions underwater (need to be below -1.0%)
        current_prices = {
            "EUR/USD": Decimal("1.0580"),  # -1.12% (entry 1.07)
            "GBP/USD": Decimal("1.0570"),  # -1.21%
            "AUD/USD": Decimal("1.0585"),  # -1.07%
        }

        # Check cascade on EUR/USD campaign
        should_exit, reason = check_correlation_cascade(
            portfolio,
            campaigns[0],
            current_prices,
            cascade_threshold=3,
            underwater_threshold_pct=Decimal("-1.0"),
            correlation_threshold=Decimal("0.7"),
        )

        assert should_exit is True
        assert "CORRELATION_CASCADE" in reason
        assert "3 correlated" in reason


# ============================================================================
# AC6: Cascade Threshold Not Met
# ============================================================================


class TestCascadeThreshold:
    """Test cascade threshold not met."""

    def test_cascade_not_met_two_correlated(self, sample_bar):
        """AC6: Only 2 correlated underwater - no exit."""
        portfolio = PortfolioRiskState()

        # Create 2 campaigns: EUR/USD, GBP/USD (correlated)
        symbols = ["EUR/USD", "GBP/USD"]
        campaigns = []

        for symbol in symbols:
            bar = OHLCVBar(
                symbol=symbol,
                timeframe="1h",
                timestamp=datetime.utcnow(),
                open=Decimal("1.0600"),
                high=Decimal("1.0650"),
                low=Decimal("1.0580"),
                close=Decimal("1.0630"),
                volume=150000,
                spread=Decimal("0.0070"),
            )

            spring = Spring(
                bar=bar,
                bar_index=100,
                penetration_pct=Decimal("0.02"),
                volume_ratio=Decimal("0.4"),
                recovery_bars=1,
                creek_reference=Decimal("1.0600"),
                spring_low=Decimal("1.0580"),
                recovery_price=Decimal("1.0700"),
                detection_timestamp=datetime.utcnow(),
                trading_range_id=uuid4(),
            )

            campaign = Campaign(
                campaign_id=str(uuid4()),
                start_time=datetime.utcnow(),
                patterns=[spring],
                state=CampaignState.ACTIVE,
                current_phase=WyckoffPhase.D,
            )
            campaigns.append(campaign)
            portfolio.add_campaign(campaign, Decimal("2.0"))

        current_prices = {
            "EUR/USD": Decimal("1.0630"),
            "GBP/USD": Decimal("1.0620"),
        }

        should_exit, reason = check_correlation_cascade(
            portfolio, campaigns[0], current_prices, cascade_threshold=3
        )

        assert should_exit is False
        assert reason is None


# ============================================================================
# AC7: Phase-Weighted Exit Priority
# ============================================================================


class TestPhaseWeightedPriority:
    """Test phase-weighted exit priority."""

    def test_exit_priority_phase_e(self, sample_campaign_phase_e):
        """AC7: Phase E campaign has priority 1 (exit first)."""
        priority = get_exit_priority(sample_campaign_phase_e)

        assert priority == 1

    def test_exit_priority_phase_c(self, sample_campaign_phase_c):
        """AC7: Phase C campaign has priority 2."""
        priority = get_exit_priority(sample_campaign_phase_c)

        assert priority == 2

    def test_exit_priority_phase_d(self, sample_campaign_phase_d):
        """AC7: Phase D campaign has priority 3 (exit last)."""
        priority = get_exit_priority(sample_campaign_phase_d)

        assert priority == 3

    def test_campaigns_sorted_by_phase(
        self, sample_campaign_phase_c, sample_campaign_phase_d, sample_campaign_phase_e
    ):
        """AC7: Campaigns sorted Phase E first, Phase D last."""
        campaigns = [
            sample_campaign_phase_d,
            sample_campaign_phase_c,
            sample_campaign_phase_e,
        ]

        current_prices = {"EUR/USD": Decimal("1.0650")}

        sorted_campaigns = get_campaigns_by_exit_priority(campaigns, current_prices)

        # Phase E should be first (priority 1)
        assert sorted_campaigns[0].current_phase == WyckoffPhase.E
        # Phase C should be second (priority 2)
        assert sorted_campaigns[1].current_phase == WyckoffPhase.C
        # Phase D should be last (priority 3)
        assert sorted_campaigns[2].current_phase == WyckoffPhase.D

    def test_same_phase_smallest_profit_first(self, sample_spring, sample_bar):
        """AC7: Within same phase, smallest profit exits first."""
        # Create two Phase E campaigns with different profits
        campaign1 = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[
                Spring(
                    bar=sample_bar,
                    bar_index=100,
                    penetration_pct=Decimal("0.02"),
                    volume_ratio=Decimal("0.4"),
                    recovery_bars=1,
                    creek_reference=Decimal("1.0600"),
                    spring_low=Decimal("1.0580"),
                    recovery_price=Decimal("1.0600"),  # Entry
                    detection_timestamp=datetime.utcnow(),
                    trading_range_id=uuid4(),
                )
            ],
            state=CampaignState.ACTIVE,
            current_phase=WyckoffPhase.E,
        )

        campaign2 = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[
                Spring(
                    bar=sample_bar,
                    bar_index=100,
                    penetration_pct=Decimal("0.02"),
                    volume_ratio=Decimal("0.4"),
                    recovery_bars=1,
                    creek_reference=Decimal("1.0600"),
                    spring_low=Decimal("1.0580"),
                    recovery_price=Decimal("1.0500"),  # Entry (lower)
                    detection_timestamp=datetime.utcnow(),
                    trading_range_id=uuid4(),
                )
            ],
            state=CampaignState.ACTIVE,
            current_phase=WyckoffPhase.E,
        )

        campaigns = [campaign1, campaign2]
        current_prices = {"EUR/USD": Decimal("1.0650")}

        sorted_campaigns = get_campaigns_by_exit_priority(campaigns, current_prices)

        # Campaign1 has smaller profit (entry 1.06), should exit first
        # Campaign2 has larger profit (entry 1.05)
        profit1 = calculate_campaign_profit_pct(campaign1, Decimal("1.0650"))
        profit2 = calculate_campaign_profit_pct(campaign2, Decimal("1.0650"))

        assert profit1 < profit2
        assert sorted_campaigns[0].campaign_id == campaign1.campaign_id


# ============================================================================
# AC8: Weighted Average Entry for Multi-Pattern Campaigns
# ============================================================================


class TestWeightedAverageEntry:
    """Test weighted average entry price calculation."""

    def test_single_pattern_uses_entry(self, sample_campaign_phase_c):
        """Test single pattern returns its entry price."""
        campaign = sample_campaign_phase_c
        campaign.patterns[0].recovery_price = Decimal("1.0620")

        entry = calculate_weighted_entry_price(campaign)

        assert entry == Decimal("1.0620")

    def test_two_patterns_equal_weight_average(self, sample_spring, sample_lps):
        """AC8: Spring at $100 + LPS at $105 = $102.50 average."""
        # Create campaign with Spring + LPS
        spring = sample_spring
        spring.recovery_price = Decimal("100.00")

        lps = sample_lps
        lps.bar.close = Decimal("105.00")

        campaign = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[spring, lps],
            state=CampaignState.ACTIVE,
            current_phase=WyckoffPhase.E,
        )

        entry = calculate_weighted_entry_price(campaign)

        expected = (Decimal("100.00") + Decimal("105.00")) / Decimal("2")
        assert entry == expected
        assert entry == Decimal("102.50")

    def test_three_patterns_average(self, sample_spring, sample_sos, sample_lps):
        """Test three patterns averaged correctly."""
        spring = sample_spring
        spring.recovery_price = Decimal("100.00")

        sos = sample_sos
        sos.breakout_price = Decimal("102.00")

        lps = sample_lps
        lps.bar.close = Decimal("105.00")

        campaign = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[spring, sos, lps],
            state=CampaignState.ACTIVE,
            current_phase=WyckoffPhase.E,
        )

        entry = calculate_weighted_entry_price(campaign)

        expected = (Decimal("100.00") + Decimal("102.00") + Decimal("105.00")) / Decimal("3")
        # Check approximate equality (Decimal precision may vary)
        assert abs(entry - expected) < Decimal("0.0001")

    def test_campaign_profit_uses_weighted_entry(self, sample_spring, sample_lps):
        """AC8: Campaign profit uses weighted average entry."""
        spring = sample_spring
        spring.recovery_price = Decimal("100.00")

        lps = sample_lps
        lps.bar.close = Decimal("105.00")

        campaign = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[spring, lps],
            state=CampaignState.ACTIVE,
            current_phase=WyckoffPhase.E,
        )

        current_price = Decimal("110.00")
        profit_pct = calculate_campaign_profit_pct(campaign, current_price)

        # Entry = 102.50, current = 110
        # Profit = (110 - 102.50) / 102.50 * 100 = 7.317%
        expected_profit = ((current_price - Decimal("102.50")) / Decimal("102.50")) * Decimal("100")
        assert abs(profit_pct - expected_profit) < Decimal("0.01")


# ============================================================================
# Additional Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_campaign_patterns(self):
        """Test campaign with no patterns returns 0."""
        campaign = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[],
            state=CampaignState.ACTIVE,
        )

        entry = calculate_weighted_entry_price(campaign)
        assert entry == Decimal("0")

        profit = calculate_campaign_profit_pct(campaign, Decimal("1.0650"))
        assert profit == Decimal("0")

    def test_invalid_currency_pair_format(self):
        """Test invalid currency pair returns low correlation."""
        correlation = get_currency_correlation("INVALID", "EUR/USD")
        assert correlation == Decimal("0.20")

    def test_portfolio_heat_no_patterns(self):
        """Test portfolio heat check with campaign having no patterns."""
        portfolio = PortfolioRiskState()
        campaign = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[],
            state=CampaignState.ACTIVE,
        )

        should_exit, reason = check_portfolio_heat(portfolio, campaign, Decimal("1.0650"))

        assert should_exit is False
        assert reason is None

    def test_correlation_cascade_no_patterns(self):
        """Test cascade check with campaign having no patterns."""
        portfolio = PortfolioRiskState()
        campaign = Campaign(
            campaign_id=str(uuid4()),
            start_time=datetime.utcnow(),
            patterns=[],
            state=CampaignState.ACTIVE,
        )

        should_exit, reason = check_correlation_cascade(portfolio, campaign, {})

        assert should_exit is False
        assert reason is None
