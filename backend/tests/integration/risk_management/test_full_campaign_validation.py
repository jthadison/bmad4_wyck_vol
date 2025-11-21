"""
Integration Tests for Full Campaign Validation (Story 7.8 AC 8)

Tests full campaign sequence: Spring → ST → SOS → LPS with proper BMAD
allocations (25%/20%/35%/20%) and campaign risk accumulation.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.campaign import (
    MAX_CAMPAIGN_RISK_PCT,
)
from src.models.portfolio import PortfolioContext, Position
from src.models.position_sizing import PositionSizing
from src.models.risk import CorrelationConfig, SectorMapping
from src.models.risk_allocation import PatternType
from src.models.trading_range import TradingRange
from src.risk_management.risk_manager import RiskManager, Signal


@pytest.fixture
def risk_manager():
    """RiskManager instance for integration testing."""
    return RiskManager()


@pytest.fixture
def campaign_id():
    """Shared campaign ID for all campaign entries."""
    return uuid4()


@pytest.fixture
def portfolio_context():
    """Portfolio context for campaign testing."""
    return PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[],
        active_campaigns=[],
        sector_mappings={
            "AAPL": SectorMapping(
                symbol="AAPL",
                sector="Technology",
                asset_class="stock",
                geography="US",
            )
        },
        correlation_config=CorrelationConfig(
            max_sector_correlation=Decimal("6.0"),
            max_asset_class_correlation=Decimal("15.0"),
            enforcement_mode="strict",
            sector_mappings={},
        ),
        r_multiple_config={},
    )


@pytest.fixture
def trading_range():
    """Trading range with event history for phase validation."""
    # Placeholder - Story 7.9 will provide full TradingRange with event_history
    from datetime import UTC, datetime

    from src.models.ohlcv import OHLCVBar
    from src.models.price_cluster import Pivot, PivotType, PriceCluster
    from src.models.trading_range import RangeStatus

    # Create OHLCV bars for pivots
    support_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 10, 14, 30, tzinfo=UTC),
        open=Decimal("91.00"),
        high=Decimal("92.00"),
        low=Decimal("90.00"),
        close=Decimal("90.50"),
        volume=100000,
        spread=Decimal("2.00"),
        timeframe="1d",
    )

    resistance_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        open=Decimal("109.00"),
        high=Decimal("110.00"),
        low=Decimal("108.50"),
        close=Decimal("109.50"),
        volume=150000,
        spread=Decimal("1.50"),
        timeframe="1d",
    )

    # Create support pivots
    support_pivot1 = Pivot(
        bar=support_bar,
        price=Decimal("90.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=support_bar.timestamp,
        index=10,
    )
    support_pivot2 = Pivot(
        bar=support_bar,
        price=Decimal("90.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=support_bar.timestamp,
        index=20,
    )

    support_cluster = PriceCluster(
        pivots=[support_pivot1, support_pivot2],
        average_price=Decimal("90.00"),
        min_price=Decimal("90.00"),
        max_price=Decimal("90.00"),
        price_range=Decimal("0.00"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.00"),
        timestamp_range=(support_bar.timestamp, support_bar.timestamp),
    )

    # Create resistance pivots
    resistance_pivot1 = Pivot(
        bar=resistance_bar,
        price=Decimal("110.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar.timestamp,
        index=40,
    )
    resistance_pivot2 = Pivot(
        bar=resistance_bar,
        price=Decimal("110.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar.timestamp,
        index=50,
    )

    resistance_cluster = PriceCluster(
        pivots=[resistance_pivot1, resistance_pivot2],
        average_price=Decimal("110.00"),
        min_price=Decimal("110.00"),
        max_price=Decimal("110.00"),
        price_range=Decimal("0.00"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.00"),
        timestamp_range=(resistance_bar.timestamp, resistance_bar.timestamp),
    )

    return TradingRange(
        symbol="AAPL",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("90.00"),
        resistance=Decimal("110.00"),
        midpoint=Decimal("100.00"),
        range_width=Decimal("20.00"),
        range_width_pct=Decimal("0.2222"),  # 20/90 = 22.22% (> 3% minimum)
        start_index=10,
        end_index=50,
        duration=41,  # >= 10 bars minimum
        status=RangeStatus.ACTIVE,
    )


class TestFullCampaignSequence:
    """
    Test complete campaign: Spring → ST → SOS → LPS.

    Campaign Budget: 5% maximum (FR18)
    BMAD Allocations (Wyckoff-aligned):
    - Spring: 25% of 5% = 1.25% max
    - ST: 20% of 5% = 1.0% max
    - SOS: 35% of 5% = 1.75% max
    - LPS: 20% of 5% = 1.0% max
    Total: 100% (allows flexibility, not all entries required)

    Actual Test Scenario:
    - Spring: 0.5% risk (40% of 1.25% max)
    - ST: 0.4% risk (40% of 1.0% max)
    - SOS: 1.0% risk (57% of 1.75% max)
    - LPS: 0.6% risk (60% of 1.0% max)
    Total campaign risk: 2.5% (within 5% limit)
    """

    @pytest.mark.asyncio
    async def test_spring_entry_validation(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """Test Spring entry passes validation and sizing."""
        spring_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            entry=Decimal("95.00"),
            stop=Decimal("92.00"),  # 3.16% buffer
            target=Decimal("115.00"),  # ~6.7R
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        assert result is not None
        assert isinstance(result, PositionSizing)
        assert result.validation_pipeline.is_valid is True
        assert result.phase_validation is not None
        assert result.r_multiple >= Decimal("3.0")  # Spring minimum 3.0R
        # Spring should use ~0.5% risk (pattern risk allocation)
        assert result.risk_pct <= Decimal("1.25")  # Within Spring max allocation

        # Add Spring position to portfolio for next test
        portfolio_context.open_positions.append(
            Position(
                symbol="AAPL",
                position_risk_pct=result.risk_pct,
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            )
        )

        return result

    @pytest.mark.asyncio
    async def test_st_entry_validation(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """Test Secondary Test entry validation (AC 8)."""
        # First add Spring position
        spring_position = Position(
            symbol="AAPL",
            position_risk_pct=Decimal("0.5"),
            status="OPEN",
            wyckoff_phase="C",
            sector="Technology",
        )
        portfolio_context.open_positions = [spring_position]

        st_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.ST,
            entry=Decimal("97.00"),
            stop=Decimal("94.00"),  # 3.09% buffer
            target=Decimal("115.00"),  # ~6.0R
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=st_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        assert result is not None
        assert isinstance(result, PositionSizing)
        assert result.validation_pipeline.is_valid is True
        # ST should use ~0.4% risk (20% of 5% campaign = 1.0% max)
        assert result.risk_pct <= Decimal("1.0")  # Within ST max allocation

        # Campaign risk: 0.5% (Spring) + 0.4% (ST) ≈ 0.9%
        assert result.campaign_risk_after is None or result.campaign_risk_after < MAX_CAMPAIGN_RISK_PCT

    @pytest.mark.asyncio
    async def test_sos_entry_validation(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """Test SOS entry after Spring+ST (AC 8)."""
        # Add Spring and ST positions
        portfolio_context.open_positions = [
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("0.5"),
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            ),
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("0.4"),
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            ),
        ]

        sos_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SOS,
            entry=Decimal("105.00"),
            stop=Decimal("100.00"),  # 4.76% buffer
            target=Decimal("125.00"),  # 4.0R
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=sos_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        assert result is not None
        assert isinstance(result, PositionSizing)
        assert result.validation_pipeline.is_valid is True
        assert result.r_multiple >= Decimal("2.5")  # SOS minimum 2.5R
        # SOS should use ~0.8% risk (35% of 5% campaign = 1.75% max)
        assert result.risk_pct <= Decimal("1.75")  # Within SOS max allocation

        # Add SOS position for LPS test
        portfolio_context.open_positions.append(
            Position(
                symbol="AAPL",
                position_risk_pct=result.risk_pct,
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
            )
        )

    @pytest.mark.asyncio
    async def test_lps_entry_validation(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """Test LPS entry after Spring+ST+SOS (AC 8)."""
        # Add all previous positions
        portfolio_context.open_positions = [
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("0.5"),  # Spring
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            ),
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("0.4"),  # ST
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            ),
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("0.8"),  # SOS
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
            ),
        ]

        lps_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.LPS,
            entry=Decimal("102.00"),
            stop=Decimal("99.00"),  # 2.94% buffer
            target=Decimal("120.00"),  # 6.0R
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=lps_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        assert result is not None
        assert isinstance(result, PositionSizing)
        assert result.validation_pipeline.is_valid is True
        assert result.r_multiple >= Decimal("2.5")  # LPS minimum 2.5R
        # LPS should use ~0.6% risk (20% of 5% campaign = 1.0% max)
        assert result.risk_pct <= Decimal("1.0")  # Within LPS max allocation

        # Total campaign risk: 0.5% + 0.4% + 0.8% + 0.6% = 2.3%
        # Should be well within 5% limit
        assert result.campaign_risk_after is None or result.campaign_risk_after <= Decimal("3.0")

    @pytest.mark.asyncio
    async def test_complete_campaign_risk_accumulation(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """
        Test full campaign sequence validates risk accumulation (AC 8).

        Expected campaign risk progression:
        - After Spring: ~0.5%
        - After ST: ~0.9%
        - After SOS: ~1.7%
        - After LPS: ~2.3%
        All within 5% campaign maximum.
        """
        campaign_positions = []

        # 1. Spring entry
        spring_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            entry=Decimal("95.00"),
            stop=Decimal("92.00"),
            target=Decimal("115.00"),
            campaign_id=campaign_id,
        )
        spring_result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert spring_result is not None
        campaign_positions.append(
            Position(
                symbol="AAPL",
                position_risk_pct=spring_result.risk_pct,
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            )
        )
        portfolio_context.open_positions = campaign_positions.copy()

        # 2. ST entry
        st_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.ST,
            entry=Decimal("97.00"),
            stop=Decimal("94.00"),
            target=Decimal("115.00"),
            campaign_id=campaign_id,
        )
        st_result = await risk_manager.validate_and_size(
            signal=st_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert st_result is not None
        campaign_positions.append(
            Position(
                symbol="AAPL",
                position_risk_pct=st_result.risk_pct,
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
            )
        )
        portfolio_context.open_positions = campaign_positions.copy()

        # 3. SOS entry
        sos_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SOS,
            entry=Decimal("105.00"),
            stop=Decimal("100.00"),
            target=Decimal("125.00"),
            campaign_id=campaign_id,
        )
        sos_result = await risk_manager.validate_and_size(
            signal=sos_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert sos_result is not None
        campaign_positions.append(
            Position(
                symbol="AAPL",
                position_risk_pct=sos_result.risk_pct,
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
            )
        )
        portfolio_context.open_positions = campaign_positions.copy()

        # 4. LPS entry
        lps_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.LPS,
            entry=Decimal("102.00"),
            stop=Decimal("99.00"),
            target=Decimal("120.00"),
            campaign_id=campaign_id,
        )
        lps_result = await risk_manager.validate_and_size(
            signal=lps_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert lps_result is not None

        # Verify all four signals created PositionSizing objects
        assert spring_result is not None
        assert st_result is not None
        assert sos_result is not None
        assert lps_result is not None

        # Verify all ValidationPipelines show 8 steps passed
        for result in [spring_result, st_result, sos_result, lps_result]:
            assert result.validation_pipeline is not None
            assert result.validation_pipeline.is_valid is True
            assert len(result.validation_pipeline.results) == 8

        # Verify each has phase_validation populated
        for result in [spring_result, st_result, sos_result, lps_result]:
            assert result.phase_validation is not None

        # Calculate total campaign risk
        total_campaign_risk = sum(
            [
                spring_result.risk_pct,
                st_result.risk_pct,
                sos_result.risk_pct,
                lps_result.risk_pct,
            ]
        )
        # Should be < 5% campaign maximum
        assert total_campaign_risk < MAX_CAMPAIGN_RISK_PCT


class TestRejectionScenarios:
    """
    Test validation rejection scenarios for Story 7.8.

    Tests that RiskManager properly rejects signals that violate:
    - Campaign risk limits (FR18: 5% max)
    - Structural stop buffer requirements (Story 7.7: 10% minimum)
    - Phase validation short-circuit (Story 7.9 placeholder)
    """

    @pytest.mark.asyncio
    async def test_campaign_risk_rejection_5_3_percent(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """
        Test campaign risk rejection at 5.3% (exceeds 5% FR18 limit).

        Scenario:
        - Existing campaign positions: 4.5% total risk
        - New signal would add: 0.8% risk
        - Projected campaign risk: 5.3% > 5.0% limit
        - Expected: Rejection at Step 7 (campaign risk validation)
        """
        # Add existing campaign positions totaling 4.5% risk
        portfolio_context.open_positions = [
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("1.5"),  # Spring
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
                campaign_id=campaign_id,  # Link to campaign
            ),
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("1.2"),  # ST
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
                campaign_id=campaign_id,  # Link to campaign
            ),
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("1.8"),  # SOS
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=campaign_id,  # Link to campaign
            ),
        ]
        # Total existing: 4.5%

        # New signal that would add 0.8% risk → 5.3% total
        sos_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SOS,
            entry=Decimal("105.00"),
            stop=Decimal("100.00"),  # 4.76% buffer (valid)
            target=Decimal("125.00"),  # 4.0R (valid)
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=sos_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        # Should be rejected due to campaign risk limit
        assert result is None

    @pytest.mark.asyncio
    async def test_structural_stop_buffer_rejection_11_percent(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """
        Test structural stop rejection with 11% buffer (exceeds 10% max).

        Scenario:
        - Signal has entry=$100, stop=$89 (11% buffer)
        - Story 7.7: Maximum stop buffer is 10% of range width
        - Trading range width: $20 (support=$90, resistance=$110)
        - Expected: Rejection at Step 4 (structural stop calculation)
        """
        # Signal with 11% stop buffer (too wide)
        spring_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            entry=Decimal("100.00"),
            stop=Decimal("89.00"),  # 11% buffer → exceeds 10% max
            target=Decimal("120.00"),  # Good R-multiple
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        # Should be rejected due to structural stop buffer exceeding 10%
        assert result is None

    @pytest.mark.asyncio
    async def test_phase_validation_short_circuit(
        self,
        risk_manager,
        campaign_id,
        portfolio_context,
        trading_range,
    ):
        """
        Test phase validation short-circuit behavior (Story 7.9 placeholder).

        Scenario:
        - Valid signal in all respects (risk, R-multiple, stop buffer)
        - Phase validation currently uses placeholder (always passes)
        - Expected: Validation passes (placeholder behavior)
        - Future Story 7.9: Will test actual phase prerequisite rejection

        Note: This test validates that Step 2 (phase validation) executes
        and short-circuits properly when phase prerequisites fail. Since
        Story 7.9 is currently a placeholder that always passes, this test
        documents the expected behavior for future implementation.
        """
        spring_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            entry=Decimal("95.00"),
            stop=Decimal("92.00"),  # 3.16% buffer (valid)
            target=Decimal("115.00"),  # ~6.7R (valid)
            campaign_id=campaign_id,
        )

        result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        # Placeholder behavior: should pass all validations
        assert result is not None
        assert isinstance(result, PositionSizing)
        assert result.validation_pipeline is not None
        assert result.validation_pipeline.is_valid is True

        # Verify Step 2 (phase_prerequisites) was executed
        phase_step = None
        for step_result in result.validation_pipeline.results:
            if step_result.validation_step == "phase_prerequisites":
                phase_step = step_result
                break

        assert phase_step is not None
        assert phase_step.is_valid is True  # Placeholder passes

        # Verify short-circuit logic: if Step 2 failed, Steps 3-8 wouldn't execute
        # Since placeholder passes, we should see all 8 steps
        assert len(result.validation_pipeline.results) == 8

        # TODO (Story 7.9): When phase validation is implemented, create a test
        # that triggers actual prerequisite failures and validates that:
        # 1. Step 2 fails with specific missing prerequisites
        # 2. Steps 3-8 are NOT executed (short-circuit)
        # 3. ValidationPipeline.results contains only Steps 1-2
