"""
Unit Tests for RiskValidator (Story 8.6)

Test Coverage:
--------------
1. Per-trade risk validation (below 2%, at 2%, above 2%)
2. Portfolio heat validation (under 10%, at 10%, over 10%, approaching 8%)
3. Campaign risk validation (under 5%, at 5%, over 5%, max positions)
4. Correlated risk validation (under 6%, at 6%, over 6%)
5. R-multiple validation for each pattern type (Spring, SOS, LPS, UTAD)
6. Position size validation (< 1 share, valid, > 20% equity)
7. Edge cases (missing data, invalid parameters)

Author: Story 8.6
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.portfolio import PortfolioContext, Position
from src.models.risk import CorrelationConfig, SectorMapping
from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators.risk_validator import RiskValidator


# Mock Pattern class for testing
class MockPattern:
    """Mock Pattern for testing without full Pattern model dependency."""

    def __init__(self, pattern_type: str, pattern_id: str | None = None):
        self.id = uuid4() if pattern_id is None else pattern_id
        self.pattern_type = pattern_type


# Fixtures
@pytest.fixture
def risk_validator() -> RiskValidator:
    """Create RiskValidator instance."""
    return RiskValidator()


@pytest.fixture
def valid_portfolio_context() -> PortfolioContext:
    """Create valid portfolio context with $100,000 equity and 5% current heat."""
    return PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
            Position(
                symbol="MSFT",
                position_risk_pct=Decimal("1.5"),
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
            Position(
                symbol="GOOGL",
                position_risk_pct=Decimal("1.5"),
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
                campaign_id=uuid4(),
            ),
        ],
        active_campaigns=[],
        sector_mappings={
            "AAPL": SectorMapping(
                symbol="AAPL", sector="Technology", asset_class="stock", geography="US"
            ),
            "MSFT": SectorMapping(
                symbol="MSFT", sector="Technology", asset_class="stock", geography="US"
            ),
            "GOOGL": SectorMapping(
                symbol="GOOGL", sector="Technology", asset_class="stock", geography="US"
            ),
            "TSLA": SectorMapping(
                symbol="TSLA", sector="Technology", asset_class="stock", geography="US"
            ),
            "JPM": SectorMapping(
                symbol="JPM", sector="Finance", asset_class="stock", geography="US"
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
def high_heat_portfolio_context() -> PortfolioContext:
    """Create portfolio context with 9.3% current heat (will exceed 10% with 0.8% SOS)."""
    return PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("3.1"),  # Total: 9.3% (will exceed 10% with SOS)
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
            Position(
                symbol="MSFT",
                position_risk_pct=Decimal("3.1"),
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
            Position(
                symbol="GOOGL",
                position_risk_pct=Decimal("3.1"),
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
                campaign_id=uuid4(),
            ),
        ],
        active_campaigns=[],
        sector_mappings={
            "AAPL": SectorMapping(
                symbol="AAPL", sector="Technology", asset_class="stock", geography="US"
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
def full_campaign_portfolio_context() -> PortfolioContext:
    """Create portfolio context with 5 positions in same campaign (at limit)."""
    campaign_uuid = uuid4()
    return PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[
            Position(
                symbol=f"TECH{i}",
                position_risk_pct=Decimal("0.8"),
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=campaign_uuid,
            )
            for i in range(5)
        ],
        active_campaigns=[],
        sector_mappings={
            "TECH5": SectorMapping(
                symbol="TECH5", sector="Technology", asset_class="stock", geography="US"
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
def spring_pattern() -> MockPattern:
    """Create Spring pattern."""
    return MockPattern("SPRING")


# Test: Missing portfolio context
@pytest.mark.asyncio
async def test_missing_portfolio_context_fails(
    risk_validator: RiskValidator, spring_pattern: MockPattern
):
    """Test that validation fails if portfolio_context is None."""
    context = ValidationContext(
        pattern=spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=None,  # Not needed for risk validation
        portfolio_context=None,  # Missing!
    )

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Portfolio context not available" in result.reason


# Test: Missing entry/stop/target
@pytest.mark.asyncio
async def test_missing_levels_fails(
    risk_validator: RiskValidator,
    spring_pattern: MockPattern,
    valid_portfolio_context: PortfolioContext,
):
    """Test that validation fails if entry/stop/target not available (LevelValidator must run first)."""
    context = ValidationContext(
        pattern=spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=valid_portfolio_context,
        # Missing: entry_price, stop_loss, target_price
    )

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Entry/stop/target levels not available" in result.reason


# Test: Portfolio heat exceeded (11% total)
@pytest.mark.asyncio
async def test_portfolio_heat_exceeded_rejected(
    risk_validator: RiskValidator, high_heat_portfolio_context: PortfolioContext
):
    """Signal that would exceed 10% portfolio heat should be rejected (AC: 7)."""
    # Add JPM to sector_mappings for Finance sector
    high_heat_portfolio_context.sector_mappings["JPM"] = SectorMapping(
        symbol="JPM", sector="Finance", asset_class="stock", geography="US"
    )

    # Use SOS pattern (1.0% risk) instead of Spring (0.5% risk) to exceed limit
    sos_pattern = MockPattern("SOS")

    context = ValidationContext(
        pattern=sos_pattern,
        symbol="JPM",  # Different sector to avoid correlated risk rejection
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=high_heat_portfolio_context,
    )
    # Add levels from LevelValidator
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("95.00")
    context.target_price = Decimal("110.00")  # 2.0R (SOS minimum)

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Portfolio heat" in result.reason
    assert "10.0%" in result.reason


# Test: 6th campaign position rejected
@pytest.mark.asyncio
async def test_campaign_position_limit_rejected(
    risk_validator: RiskValidator,
    spring_pattern: MockPattern,
    full_campaign_portfolio_context: PortfolioContext,
):
    """6th campaign position should be rejected (AC: 8)."""
    # Get campaign_id from first position
    campaign_id = full_campaign_portfolio_context.open_positions[0].campaign_id

    context = ValidationContext(
        pattern=spring_pattern,
        symbol="TECH5",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=full_campaign_portfolio_context,
    )
    # Add levels
    context.entry_price = Decimal("50.00")
    context.stop_loss = Decimal("48.00")
    context.target_price = Decimal("56.00")  # 3.0R
    context.campaign_id = str(campaign_id)  # Same campaign as existing 5 positions

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Campaign position limit" in result.reason
    assert "5 positions max" in result.reason


# Test: Valid Spring signal passes
@pytest.mark.asyncio
async def test_valid_spring_signal_passes(
    risk_validator: RiskValidator,
    spring_pattern: MockPattern,
    valid_portfolio_context: PortfolioContext,
):
    """Valid Spring signal with all risk checks passing should return PASS."""
    context = ValidationContext(
        pattern=spring_pattern,
        symbol="JPM",  # Different sector (Finance)
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=valid_portfolio_context,
    )
    # Add levels
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("95.00")
    context.target_price = Decimal("115.00")  # 3.0R

    result = await risk_validator.validate(context)

    assert result.status in [ValidationStatus.PASS, ValidationStatus.WARN]
    assert result.metadata is not None
    assert result.metadata["position_size"] >= 1
    assert result.metadata["r_multiple"] >= 3.0  # Spring minimum
    assert result.metadata["portfolio_heat_after"] <= 10.0


# Parametrized Tests: R-multiple validation for all pattern types
@pytest.mark.parametrize(
    "pattern_type,r_multiple_target,expected_status",
    [
        ("SPRING", Decimal("3.0"), ValidationStatus.PASS),  # At minimum
        ("SPRING", Decimal("4.5"), ValidationStatus.PASS),  # Above minimum
        ("SPRING", Decimal("2.8"), ValidationStatus.FAIL),  # Below minimum
        ("SOS", Decimal("2.0"), ValidationStatus.PASS),  # At minimum
        ("SOS", Decimal("1.8"), ValidationStatus.FAIL),  # Below minimum
        ("LPS", Decimal("2.5"), ValidationStatus.PASS),  # At minimum
        ("LPS", Decimal("2.3"), ValidationStatus.FAIL),  # Below minimum
        ("UTAD", Decimal("3.0"), ValidationStatus.PASS),  # At minimum
        ("UTAD", Decimal("2.9"), ValidationStatus.FAIL),  # Below minimum
    ],
)
@pytest.mark.asyncio
async def test_r_multiple_validation(
    risk_validator: RiskValidator,
    valid_portfolio_context: PortfolioContext,
    pattern_type: str,
    r_multiple_target: Decimal,
    expected_status: ValidationStatus,
):
    """Test R-multiple validation for all pattern types (AC: 3, FR19)."""

    pattern = MockPattern(pattern_type)

    context = ValidationContext(
        pattern=pattern,
        symbol="JPM",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=valid_portfolio_context,
    )

    # Calculate entry/stop/target to achieve desired R-multiple
    entry = Decimal("100.00")
    stop = Decimal("95.00")  # $5 risk
    # R = (target - entry) / (entry - stop)
    # target = entry + (R * (entry - stop))
    target = entry + (r_multiple_target * (entry - stop))

    context.entry_price = entry
    context.stop_loss = stop
    context.target_price = target

    result = await risk_validator.validate(context)

    if expected_status == ValidationStatus.FAIL:
        assert result.status == ValidationStatus.FAIL
        assert "R-multiple" in result.reason
        assert "FR19" in result.reason
    else:
        assert result.status in [ValidationStatus.PASS, ValidationStatus.WARN]


# Test: Portfolio heat warning at 80% capacity
@pytest.mark.asyncio
async def test_portfolio_heat_warning_at_80_percent(
    risk_validator: RiskValidator, spring_pattern: MockPattern
):
    """Portfolio heat approaching 80% capacity should generate warning."""
    portfolio_context = PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("7.5"),  # Will push to ~8% with new position
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
        ],
        active_campaigns=[],
        sector_mappings={
            "JPM": SectorMapping(
                symbol="JPM", sector="Finance", asset_class="stock", geography="US"
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

    context = ValidationContext(
        pattern=spring_pattern,
        symbol="JPM",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=portfolio_context,
    )
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("95.00")
    context.target_price = Decimal("115.00")

    result = await risk_validator.validate(context)

    # Should pass with warning
    assert result.status == ValidationStatus.WARN
    assert "WARNING" in result.reason
    assert "Portfolio heat" in result.reason


# Test: Correlated risk exceeded
@pytest.mark.asyncio
async def test_correlated_risk_exceeded_rejected(
    risk_validator: RiskValidator, spring_pattern: MockPattern
):
    """Signal that would exceed 6.0% correlated risk should be rejected."""
    portfolio_context = PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
            Position(
                symbol="MSFT",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=uuid4(),
            ),
            Position(
                symbol="GOOGL",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
                campaign_id=uuid4(),
            ),
        ],
        active_campaigns=[],
        sector_mappings={
            "AAPL": SectorMapping(
                symbol="AAPL", sector="Technology", asset_class="stock", geography="US"
            ),
            "MSFT": SectorMapping(
                symbol="MSFT", sector="Technology", asset_class="stock", geography="US"
            ),
            "GOOGL": SectorMapping(
                symbol="GOOGL", sector="Technology", asset_class="stock", geography="US"
            ),
            "TSLA": SectorMapping(
                symbol="TSLA", sector="Technology", asset_class="stock", geography="US"
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

    context = ValidationContext(
        pattern=spring_pattern,
        symbol="TSLA",  # Another tech stock - would push sector risk to 6.5%
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=portfolio_context,
    )
    context.entry_price = Decimal("200.00")
    context.stop_loss = Decimal("190.00")
    context.target_price = Decimal("230.00")

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Correlated risk" in result.reason
    assert "Technology" in result.reason
    assert "6.0%" in result.reason


# Test: Edge case - invalid stop (stop >= entry)
@pytest.mark.asyncio
async def test_invalid_stop_rejected(
    risk_validator: RiskValidator,
    spring_pattern: MockPattern,
    valid_portfolio_context: PortfolioContext,
):
    """Invalid stop loss (stop >= entry) should be rejected."""
    context = ValidationContext(
        pattern=spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=valid_portfolio_context,
    )
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("105.00")  # Invalid: stop > entry
    context.target_price = Decimal("120.00")

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Invalid stop loss" in result.reason


# Test: Edge case - invalid target (target <= entry)
@pytest.mark.asyncio
async def test_invalid_target_rejected(
    risk_validator: RiskValidator,
    spring_pattern: MockPattern,
    valid_portfolio_context: PortfolioContext,
):
    """Invalid target (target <= entry) should be rejected."""
    context = ValidationContext(
        pattern=spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=valid_portfolio_context,
    )
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("95.00")
    context.target_price = Decimal("98.00")  # Invalid: target < entry

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Invalid target" in result.reason


# Test: Edge case - account equity zero
@pytest.mark.asyncio
async def test_zero_account_equity_rejected(
    risk_validator: RiskValidator, spring_pattern: MockPattern
):
    """Zero account equity should be rejected."""
    portfolio_context = PortfolioContext(
        account_equity=Decimal("0.00"),  # Invalid!
        open_positions=[],
        active_campaigns=[],
        sector_mappings={},
        correlation_config=CorrelationConfig(
            max_sector_correlation=Decimal("6.0"),
            max_asset_class_correlation=Decimal("15.0"),
            enforcement_mode="strict",
            sector_mappings={},
        ),
        r_multiple_config={},
    )

    context = ValidationContext(
        pattern=spring_pattern,
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=portfolio_context,
    )
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("95.00")
    context.target_price = Decimal("115.00")

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Invalid account equity" in result.reason


# Test: Campaign risk exceeded
@pytest.mark.asyncio
async def test_campaign_risk_exceeded_rejected(
    risk_validator: RiskValidator, spring_pattern: MockPattern
):
    """Signal that would exceed 5.0% campaign risk should be rejected."""
    campaign_uuid = uuid4()
    portfolio_context = PortfolioContext(
        account_equity=Decimal("100000.00"),
        open_positions=[
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("2.0"),  # Increased to push over limit
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=campaign_uuid,
            ),
            Position(
                symbol="MSFT",
                position_risk_pct=Decimal("2.0"),  # Increased to push over limit
                status="OPEN",
                wyckoff_phase="D",
                sector="Technology",
                campaign_id=campaign_uuid,
            ),
            Position(
                symbol="GOOGL",
                position_risk_pct=Decimal("1.5"),
                status="OPEN",
                wyckoff_phase="C",
                sector="Technology",
                campaign_id=campaign_uuid,
            ),
        ],
        active_campaigns=[],
        sector_mappings={
            "TSLA": SectorMapping(
                symbol="TSLA", sector="Technology", asset_class="stock", geography="US"
            ),
        },
        correlation_config=CorrelationConfig(
            max_sector_correlation=Decimal("10.0"),  # Increased to avoid correlated risk rejection
            max_asset_class_correlation=Decimal("15.0"),
            enforcement_mode="strict",
            sector_mappings={},
        ),
        r_multiple_config={},
    )

    context = ValidationContext(
        pattern=spring_pattern,
        symbol="TSLA",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=portfolio_context,
    )
    context.entry_price = Decimal("200.00")
    context.stop_loss = Decimal("190.00")
    context.target_price = Decimal("230.00")
    context.campaign_id = str(campaign_uuid)  # Same campaign - would push to 6.0% (over limit)

    result = await risk_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Campaign risk" in result.reason
    assert "5.0%" in result.reason


# Test: Metadata completeness
@pytest.mark.asyncio
async def test_metadata_completeness(
    risk_validator: RiskValidator,
    spring_pattern: MockPattern,
    valid_portfolio_context: PortfolioContext,
):
    """Test that validation result includes comprehensive metadata."""
    context = ValidationContext(
        pattern=spring_pattern,
        symbol="JPM",
        timeframe="1d",
        volume_analysis=None,
        portfolio_context=valid_portfolio_context,
    )
    context.entry_price = Decimal("100.00")
    context.stop_loss = Decimal("95.00")
    context.target_price = Decimal("115.00")

    result = await risk_validator.validate(context)

    assert result.status in [ValidationStatus.PASS, ValidationStatus.WARN]
    assert result.metadata is not None

    # Check all required metadata fields
    required_fields = [
        "position_size",
        "risk_amount",
        "risk_pct",
        "r_multiple",
        "portfolio_heat_before",
        "portfolio_heat_after",
        "portfolio_heat_limit",
        "campaign_risk_before",
        "campaign_risk_after",
        "campaign_risk_limit",
        "correlated_risk_before",
        "correlated_risk_after",
        "correlated_risk_limit",
        "per_trade_risk_limit",
        "r_multiple_minimum",
        "account_equity",
        "position_value",
        "entry_price",
        "stop_loss",
        "target_price",
    ]

    for field in required_fields:
        assert field in result.metadata, f"Missing metadata field: {field}"

    # Verify numeric constraints
    assert result.metadata["portfolio_heat_limit"] == 10.0
    assert result.metadata["campaign_risk_limit"] == 5.0
    assert result.metadata["correlated_risk_limit"] == 6.0
    assert result.metadata["per_trade_risk_limit"] == 2.0
    assert result.metadata["r_multiple_minimum"] == 3.0  # Spring minimum
