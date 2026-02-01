"""
Shared fixtures for refactoring test suite (Story 22.14).

Provides common test data and fixtures for validating refactoring work.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from src.backtesting.intraday_campaign_detector import (
    Campaign,
    CampaignState,
    IntradayCampaignDetector,
)
from src.models.automatic_rally import AutomaticRally
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.wyckoff_phase import WyckoffPhase


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """
    Generate sample OHLCV data for 500 bars.

    Creates realistic price data with a trending pattern suitable for
    Wyckoff analysis testing.
    """
    dates = pd.date_range(start="2025-01-01", periods=500, freq="1h", tz=UTC)
    np.random.seed(42)

    # Generate realistic price data with trend
    base_price = 100.0
    returns = np.random.normal(0.0001, 0.01, 500)
    prices = base_price * np.exp(np.cumsum(returns))

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * (1 + np.random.uniform(-0.005, 0.005, 500)),
            "high": prices * (1 + np.random.uniform(0, 0.01, 500)),
            "low": prices * (1 - np.random.uniform(0, 0.01, 500)),
            "close": prices,
            "volume": np.random.randint(1000, 10000, 500),
        }
    )


@pytest.fixture
def accumulation_pattern_data() -> pd.DataFrame:
    """
    Generate OHLCV data with clear accumulation pattern.

    Creates price data simulating:
    - Phase A: Selling climax with high volume
    - Phase B: Trading range
    - Phase C: Spring with low volume
    - Phase D: SOS breakout
    """
    np.random.seed(123)
    dates = pd.date_range(start="2025-01-01", periods=200, freq="1h", tz=UTC)

    # Phase A: Downtrend ending with selling climax (bars 0-30)
    phase_a_prices = np.linspace(110, 95, 31)
    phase_a_volume = np.random.randint(8000, 15000, 31)  # High volume
    phase_a_volume[25:31] = np.random.randint(15000, 25000, 6)  # Climax volume

    # Phase B: Trading range (bars 31-100)
    phase_b_prices = 100 + np.random.normal(0, 2, 70)
    phase_b_volume = np.random.randint(3000, 7000, 70)

    # Phase C: Spring - brief dip below support (bars 101-120)
    phase_c_prices = np.concatenate(
        [
            np.linspace(100, 93, 10),  # Dip below support
            np.linspace(94, 100, 10),  # Recovery
        ]
    )
    phase_c_volume = np.random.randint(1500, 3000, 20)  # Low volume on spring

    # Phase D: SOS breakout (bars 121-160)
    phase_d_prices = np.linspace(100, 115, 40)
    phase_d_volume = np.random.randint(10000, 18000, 40)  # High volume on breakout

    # Phase E: Continuation (bars 161-199)
    phase_e_prices = 115 + np.cumsum(np.random.normal(0.1, 0.5, 39))
    phase_e_volume = np.random.randint(5000, 10000, 39)

    prices = np.concatenate(
        [phase_a_prices, phase_b_prices, phase_c_prices, phase_d_prices, phase_e_prices]
    )
    volumes = np.concatenate(
        [phase_a_volume, phase_b_volume, phase_c_volume, phase_d_volume, phase_e_volume]
    )

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * (1 + np.random.uniform(-0.003, 0.003, 200)),
            "high": prices * (1 + np.random.uniform(0, 0.008, 200)),
            "low": prices * (1 - np.random.uniform(0, 0.008, 200)),
            "close": prices,
            "volume": volumes,
        }
    )


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
        penetration_pct=Decimal("0.02"),  # 2% below Creek
        volume_ratio=Decimal("0.5"),  # Low volume (good for Spring)
        recovery_bars=2,
        creek_reference=Decimal("150.00"),
        spring_low=Decimal("147.00"),
        recovery_price=Decimal("151.00"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
    )


@pytest.fixture
def sample_ar_pattern(sample_ohlcv_bar: OHLCVBar) -> AutomaticRally:
    """Create a sample Automatic Rally pattern for testing."""
    bar_dict = {
        "symbol": "AAPL",
        "timeframe": "1h",
        "timestamp": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "open": "151.00",
        "high": "155.00",
        "low": "150.50",
        "close": "154.00",
        "volume": 1500000,
        "spread": "4.50",
    }
    sc_dict = {
        "symbol": "AAPL",
        "timestamp": datetime.now(UTC).isoformat(),
        "low": "145.00",
    }
    return AutomaticRally(
        bar=bar_dict,
        bar_index=55,
        rally_pct=Decimal("0.035"),  # 3.5% rally
        bars_after_sc=5,
        sc_reference=sc_dict,
        sc_low=Decimal("145.00"),
        ar_high=Decimal("155.00"),
        volume_profile="NORMAL",
        quality_score=0.75,
    )


@pytest.fixture
def sample_sos_pattern(sample_ohlcv_bar: OHLCVBar) -> SOSBreakout:
    """Create a sample SOS breakout pattern for testing."""
    bar = OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1h",
        timestamp=datetime.now(UTC) + timedelta(hours=5),
        open=Decimal("154.00"),
        high=Decimal("158.00"),
        low=Decimal("153.50"),
        close=Decimal("157.00"),
        volume=2000000,
        spread=Decimal("4.50"),
        spread_ratio=Decimal("1.5"),
        volume_ratio=Decimal("1.8"),
        created_at=datetime.now(UTC),
    )
    return SOSBreakout(
        bar=bar,
        breakout_pct=Decimal("0.02"),  # 2% above Ice
        volume_ratio=Decimal("1.8"),
        ice_reference=Decimal("155.00"),
        breakout_price=Decimal("157.00"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.78"),  # (157-153.5)/(158-153.5)
        spread=Decimal("4.50"),
    )


@pytest.fixture
def sample_campaign(
    sample_spring_pattern: Spring,
) -> Campaign:
    """Create a sample Campaign object in FORMING state."""
    return Campaign(
        campaign_id=f"test-campaign-{uuid4().hex[:8]}",
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
def active_campaign(
    sample_spring_pattern: Spring,
    sample_ar_pattern: AutomaticRally,
) -> Campaign:
    """Create a sample Campaign in ACTIVE state with 2 patterns."""
    campaign = Campaign(
        campaign_id=f"test-campaign-{uuid4().hex[:8]}",
        start_time=datetime.now(UTC) - timedelta(hours=24),
        patterns=[sample_spring_pattern, sample_ar_pattern],
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
    return campaign


@pytest.fixture
def detector() -> IntradayCampaignDetector:
    """Create an IntradayCampaignDetector instance for testing."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=72,
        max_concurrent_campaigns=3,
        max_portfolio_heat_pct=Decimal("10.0"),
    )


@pytest.fixture
def detector_with_campaigns(
    detector: IntradayCampaignDetector,
    active_campaign: Campaign,
) -> IntradayCampaignDetector:
    """Create a detector with pre-loaded active campaigns."""
    # Add campaign to detector's internal indexes
    detector._add_to_indexes(active_campaign)
    return detector


@pytest.fixture
def mock_portfolio() -> dict[str, Any]:
    """
    Create a mock portfolio with multiple campaigns.

    Returns a dictionary with portfolio metrics for testing heat calculations.
    """
    return {
        "account_equity": Decimal("100000"),
        "campaigns": [
            {
                "id": "camp-1",
                "position_size": Decimal("100"),
                "risk_per_share": Decimal("3.00"),
                "dollar_risk": Decimal("300"),
            },
            {
                "id": "camp-2",
                "position_size": Decimal("200"),
                "risk_per_share": Decimal("2.50"),
                "dollar_risk": Decimal("500"),
            },
            {
                "id": "camp-3",
                "position_size": Decimal("150"),
                "risk_per_share": Decimal("4.00"),
                "dollar_risk": Decimal("600"),
            },
        ],
    }
