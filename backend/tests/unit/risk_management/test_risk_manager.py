"""
Unit Tests for RiskManager Module (Story 7.8)

Tests all 8 validation steps and end-to-end validate_and_size pipeline.
"""

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.campaign import MAX_CAMPAIGN_RISK_PCT
from src.models.portfolio import PortfolioContext, Position
from src.models.position_sizing import PositionSizing
from src.models.risk import CorrelationConfig, SectorMapping
from src.models.risk_allocation import PatternType
from src.models.trading_range import TradingRange
from src.risk_management.risk_manager import RiskManager, Signal


@pytest.fixture
def risk_manager():
    """RiskManager instance for testing."""
    return RiskManager()


@pytest.fixture
def portfolio_context():
    """Standard portfolio context for testing."""
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
            ),
            "MSFT": SectorMapping(
                symbol="MSFT",
                sector="Technology",
                asset_class="stock",
                geography="US",
            ),
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
def spring_signal():
    """Spring signal for testing."""
    return Signal(
        symbol="AAPL",
        pattern_type=PatternType.SPRING,
        entry=Decimal("100.00"),
        stop=Decimal("97.00"),  # 3% buffer
        target=Decimal("120.00"),
    )


@pytest.fixture
def sos_signal():
    """SOS signal for testing."""
    return Signal(
        symbol="AAPL",
        pattern_type=PatternType.SOS,
        entry=Decimal("100.00"),
        stop=Decimal("95.00"),  # 5% buffer
        target=Decimal("120.00"),
    )


@pytest.fixture
def trading_range():
    """Trading range with event history."""
    # Placeholder - Story 7.9 will provide full TradingRange with event_history
    from datetime import UTC, datetime

    from src.models.ohlcv import OHLCVBar
    from src.models.price_cluster import PriceCluster, Pivot, PivotType
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


class TestPatternRiskValidation:
    """Tests for Step 1: Pattern risk validation."""

    @pytest.mark.asyncio
    async def test_valid_pattern_risk(self, risk_manager, spring_signal):
        """Test pattern risk validation passes for valid risk."""
        result = await risk_manager._validate_pattern_risk(
            pattern_type=spring_signal.pattern_type, signal=spring_signal
        )
        assert result.is_valid is True
        assert result.validation_step == "pattern_risk"
        assert result.rejection_reason is None

    @pytest.mark.asyncio
    async def test_pattern_risk_at_limit(self, risk_manager, spring_signal):
        """Test pattern risk validation passes at 2.0% limit."""
        # Set risk to maximum allowed (2.0%)
        risk_manager.risk_allocator.set_pattern_risk_override(
            PatternType.SPRING, Decimal("2.0")
        )
        result = await risk_manager._validate_pattern_risk(
            pattern_type=spring_signal.pattern_type, signal=spring_signal
        )
        # At limit should still pass (not exceed)
        assert result.is_valid is True
        assert result.validation_step == "pattern_risk"


class TestRMultipleValidation:
    """Tests for Step 3: R-multiple validation."""

    @pytest.mark.asyncio
    async def test_valid_r_multiple(self, risk_manager, spring_signal):
        """Test R-multiple validation passes for valid R."""
        result, r_multiple = await risk_manager._validate_r_multiple(
            entry=spring_signal.entry,
            stop=spring_signal.stop,
            target=spring_signal.target,
            pattern_type=spring_signal.pattern_type,
        )
        assert result.is_valid is True
        assert result.validation_step == "r_multiple"
        assert r_multiple >= Decimal("3.0")  # Spring minimum 3.0R

    @pytest.mark.asyncio
    async def test_r_multiple_below_minimum(self, risk_manager):
        """Test R-multiple validation fails for R < minimum."""
        # Spring minimum 3.0R, this gives 2.0R
        result, r_multiple = await risk_manager._validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("105.00"),  # Only 5 point gain vs 5 point risk = 1.0R
            pattern_type=PatternType.SPRING,
        )
        assert result.is_valid is False
        assert result.validation_step == "r_multiple"
        assert "minimum" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_r_multiple_warning_below_ideal(self, risk_manager):
        """Test R-multiple validation warns if R < ideal but > minimum."""
        # Spring minimum 3.0R, ideal 4.0R, this gives 3.5R
        result, r_multiple = await risk_manager._validate_r_multiple(
            entry=Decimal("100.00"),
            stop=Decimal("96.00"),  # 4 point risk
            target=Decimal("114.00"),  # 14 point gain = 3.5R
            pattern_type=PatternType.SPRING,
        )
        assert result.is_valid is True  # Acceptable
        assert len(result.warnings) > 0  # But warning issued
        assert "ideal" in result.warnings[0].lower()


class TestStructuralStopValidation:
    """Tests for Step 4: Structural stop calculation."""

    @pytest.mark.asyncio
    async def test_valid_stop_buffer(self, risk_manager, spring_signal):
        """Test structural stop validation passes for valid buffer (1-10%)."""
        result, validated_stop = await risk_manager._calculate_structural_stop(
            pattern_type=spring_signal.pattern_type,
            entry=spring_signal.entry,
            preliminary_stop=spring_signal.stop,
        )
        assert result.is_valid is True
        assert result.validation_step == "structural_stop"
        assert validated_stop == spring_signal.stop  # Not adjusted

    @pytest.mark.asyncio
    async def test_stop_buffer_too_tight_adjusted(self, risk_manager):
        """Test structural stop widens if buffer <1%."""
        result, validated_stop = await risk_manager._calculate_structural_stop(
            pattern_type=PatternType.SPRING,
            entry=Decimal("100.00"),
            preliminary_stop=Decimal("99.50"),  # 0.5% buffer (too tight)
        )
        assert result.is_valid is True  # Adjusted, not rejected
        assert len(result.warnings) > 0
        assert "widened" in result.warnings[0].lower()
        # Stop should be widened to 1% minimum
        expected_stop = Decimal("100.00") * Decimal("0.99")
        assert validated_stop == expected_stop

    @pytest.mark.asyncio
    async def test_stop_buffer_too_wide_rejected(self, risk_manager):
        """Test structural stop rejects if buffer >10%."""
        result, validated_stop = await risk_manager._calculate_structural_stop(
            pattern_type=PatternType.SPRING,
            entry=Decimal("100.00"),
            preliminary_stop=Decimal("88.00"),  # 12% buffer (too wide)
        )
        assert result.is_valid is False
        assert result.validation_step == "structural_stop"
        assert "10%" in result.rejection_reason


class TestPositionSizeCalculation:
    """Tests for Step 5: Position size calculation."""

    @pytest.mark.asyncio
    async def test_valid_position_sizing(
        self, risk_manager, portfolio_context, spring_signal
    ):
        """Test position sizing succeeds for valid signal."""
        result, position_sizing = await risk_manager._calculate_position_size(
            account_equity=portfolio_context.account_equity,
            pattern_type=spring_signal.pattern_type,
            entry=spring_signal.entry,
            stop=spring_signal.stop,
            target=spring_signal.target,
        )
        assert result.is_valid is True
        assert position_sizing is not None
        assert position_sizing.shares >= 1
        assert position_sizing.actual_risk <= position_sizing.risk_amount


class TestPortfolioHeatValidation:
    """Tests for Step 6: Portfolio heat validation."""

    @pytest.mark.asyncio
    async def test_portfolio_heat_within_limit(self, risk_manager):
        """Test portfolio heat validation passes when heat ≤ 10%."""
        # Existing positions: 5% heat
        current_positions = [
            Position(
                symbol="TSLA",
                position_risk_pct=Decimal("5.0"),
                status="OPEN",
            )
        ]
        # New position: 4% risk (total 9% < 10% limit)
        result, projected_heat = await risk_manager._validate_portfolio_heat(
            current_positions=current_positions,
            new_position_risk_pct=Decimal("4.0"),
        )
        assert result.is_valid is True
        assert projected_heat == Decimal("9.0")

    @pytest.mark.asyncio
    async def test_portfolio_heat_exceeds_limit(self, risk_manager):
        """Test portfolio heat validation fails when heat > 10%."""
        # Existing positions: 9.5% heat
        current_positions = [
            Position(
                symbol="TSLA",
                position_risk_pct=Decimal("9.5"),
                status="OPEN",
            )
        ]
        # New position: 1.0% risk (total 10.5% > 10% limit)
        result, projected_heat = await risk_manager._validate_portfolio_heat(
            current_positions=current_positions,
            new_position_risk_pct=Decimal("1.0"),
        )
        assert result.is_valid is False
        assert "10%" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_portfolio_heat_proximity_warning(self, risk_manager):
        """Test portfolio heat generates warning at 80% capacity."""
        # Existing positions: 5% heat
        current_positions = [
            Position(
                symbol="TSLA",
                position_risk_pct=Decimal("5.0"),
                status="OPEN",
            )
        ]
        # New position: 3.5% risk (total 8.5% ≥ 8% warning threshold)
        result, projected_heat = await risk_manager._validate_portfolio_heat(
            current_positions=current_positions,
            new_position_risk_pct=Decimal("3.5"),
        )
        assert result.is_valid is True  # Still passes
        assert len(result.warnings) > 0  # But warning issued
        assert "capacity" in result.warnings[0].lower()


class TestCampaignRiskValidation:
    """Tests for Step 7: Campaign risk validation."""

    @pytest.mark.asyncio
    async def test_campaign_risk_skipped_without_campaign_id(self, risk_manager):
        """Test campaign risk validation skipped when campaign_id is None."""
        result, projected_risk = await risk_manager._validate_campaign_risk(
            campaign_id=None,
            current_positions=[],
            new_position_risk_pct=Decimal("1.0"),
            pattern_type=PatternType.SPRING,
        )
        assert result.is_valid is True
        assert projected_risk is None


class TestValidateAndSizeEndToEnd:
    """Tests for main validate_and_size method end-to-end."""

    @pytest.mark.asyncio
    async def test_all_validations_pass(
        self,
        risk_manager,
        spring_signal,
        portfolio_context,
        trading_range,
    ):
        """Test validate_and_size returns PositionSizing when all pass."""
        result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert result is not None
        assert isinstance(result, PositionSizing)
        assert result.shares >= 1
        assert result.validation_pipeline is not None
        assert result.validation_pipeline.is_valid is True
        assert result.phase_validation is not None
        assert result.r_multiple is not None
        assert result.portfolio_heat_after is not None

    # NOTE: Pattern risk rejection test removed - RiskAllocator enforces 2.0% limit
    # at allocation time, so pattern_risk validation will never see >2% risk.
    # This is by design - the allocator is the single source of truth for risk limits.

    @pytest.mark.asyncio
    async def test_r_multiple_rejection(
        self,
        risk_manager,
        portfolio_context,
        trading_range,
    ):
        """Test validate_and_size returns None when R-multiple below minimum."""
        # Spring minimum 3.0R, this gives ~1.0R
        bad_signal = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            entry=Decimal("100.00"),
            stop=Decimal("95.00"),
            target=Decimal("105.00"),  # Only 1.0R
        )
        result = await risk_manager.validate_and_size(
            signal=bad_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_portfolio_heat_rejection(
        self,
        risk_manager,
        spring_signal,
        portfolio_context,
        trading_range,
    ):
        """Test validate_and_size returns None when portfolio heat exceeds 10%."""
        # Add positions to push heat to 9.6%
        portfolio_context.open_positions = [
            Position(
                symbol="TSLA",
                position_risk_pct=Decimal("9.6"),
                status="OPEN",
            )
        ]
        # Spring signal will add ~0.5% more = 10.1%, exceeds 10% limit
        result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        # Should reject due to portfolio heat
        assert result is None

    @pytest.mark.asyncio
    async def test_warnings_captured_in_pipeline(
        self,
        risk_manager,
        portfolio_context,
        trading_range,
    ):
        """Test warnings are captured in ValidationPipeline.all_warnings."""
        # Signal with R-multiple between minimum and ideal (generates warning)
        signal_with_warning = Signal(
            symbol="AAPL",
            pattern_type=PatternType.SPRING,
            entry=Decimal("100.00"),
            stop=Decimal("96.00"),  # 4 point risk
            target=Decimal("114.00"),  # 14 point gain = 3.5R (< ideal 4.0R)
        )
        result = await risk_manager.validate_and_size(
            signal=signal_with_warning,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert result is not None
        assert result.validation_pipeline is not None
        assert len(result.validation_pipeline.all_warnings) > 0

    @pytest.mark.asyncio
    async def test_validation_pipeline_tracks_all_steps(
        self,
        risk_manager,
        spring_signal,
        portfolio_context,
        trading_range,
    ):
        """Test ValidationPipeline captures all 8 validation steps."""
        result = await risk_manager.validate_and_size(
            signal=spring_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )
        assert result is not None
        assert result.validation_pipeline is not None
        # Should have 8 validation steps
        assert len(result.validation_pipeline.results) == 8
        step_names = [r.validation_step for r in result.validation_pipeline.results]
        assert "pattern_risk" in step_names
        assert "phase_prerequisites" in step_names
        assert "r_multiple" in step_names
        assert "structural_stop" in step_names
        assert "position_size" in step_names
        assert "portfolio_heat" in step_names
        assert "campaign_risk" in step_names
        assert "correlated_risk" in step_names
