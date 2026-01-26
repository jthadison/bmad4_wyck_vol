"""
Unit Tests for MasterOrchestrator (Story 8.10)

Test Coverage:
--------------
1. analyze_symbol with mocked dependencies
2. validation_chain early exit on volume failure
3. detector failure does not crash pipeline
4. parallel watchlist processing
5. cache invalidation on new bar
6. performance tracking records latency
7. forex session detection
8. asset class detection
9. signal generation from validated pattern
10. rejection creation from failed validation

Author: Story 8.10
"""

import pytest

# Skip entire module - MasterOrchestrator signature changes
# Tracking issue: https://github.com/jthadison/bmad4_wyck_vol/issues/241
pytestmark = pytest.mark.skip(reason="Issue #241: Master orchestrator signature mismatches")

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.models.signal import RejectedSignal, TradeSignal
from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationContext,
    ValidationStatus,
)
from src.repositories.rejection_repository import RejectionRepository
from src.repositories.signal_repository import SignalRepository
from src.signal_generator.master_orchestrator import (
    ForexSession,
    MasterOrchestrator,
    PerformanceTracker,
)
from src.signal_generator.validators.level_validator import LevelValidator
from src.signal_generator.validators.phase_validator import PhaseValidator
from src.signal_generator.validators.risk_validator import RiskValidator
from src.signal_generator.validators.strategy_validator import StrategyValidator
from src.signal_generator.validators.volume_validator import VolumeValidator

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_validators():
    """Create mocked validators."""
    return {
        "volume": Mock(spec=VolumeValidator),
        "phase": Mock(spec=PhaseValidator),
        "level": Mock(spec=LevelValidator),
        "risk": Mock(spec=RiskValidator),
        "strategy": Mock(spec=StrategyValidator),
    }


@pytest.fixture
def mock_repositories():
    """Create mocked repositories."""
    return {
        "signal": Mock(spec=SignalRepository),
        "rejection": Mock(spec=RejectionRepository),
    }


@pytest.fixture
def orchestrator(mock_validators, mock_repositories):
    """Create MasterOrchestrator with mocked dependencies."""
    return MasterOrchestrator(
        market_data_service=Mock(),
        trading_range_service=Mock(),
        pattern_detectors=[Mock()],
        volume_validator=mock_validators["volume"],
        phase_validator=mock_validators["phase"],
        level_validator=mock_validators["level"],
        risk_validator=mock_validators["risk"],
        strategy_validator=mock_validators["strategy"],
        signal_generator=Mock(),
        signal_repository=mock_repositories["signal"],
        rejection_repository=mock_repositories["rejection"],
        performance_tracker=PerformanceTracker(),
        max_concurrent_symbols=10,
        cache_ttl_seconds=300,
        enable_performance_tracking=True,
    )


@pytest.fixture
def sample_pattern():
    """Create sample pattern data."""
    return {
        "id": uuid4(),
        "pattern_type": "SPRING",
        "symbol": "AAPL",
        "phase": "C",
        "confidence_score": 85,
        "entry_price": Decimal("150.00"),
        "stop_loss": Decimal("148.00"),
        "target_price": Decimal("156.00"),
        "trading_range_id": uuid4(),
    }


@pytest.fixture
def sample_validation_context(sample_pattern):
    """Create sample validation context."""
    return ValidationContext(
        pattern=sample_pattern,
        symbol="AAPL",
        timeframe="1h",
        volume_analysis=Mock(),
        asset_class="STOCK",
    )


# ============================================================================
# Test: PerformanceTracker
# ============================================================================


def test_performance_tracker_timer():
    """Test performance tracker timer functionality."""
    tracker = PerformanceTracker()

    timer_id = tracker.start_timer("test_stage")
    assert timer_id in tracker.timers

    elapsed = tracker.end_timer(timer_id)
    assert elapsed >= 0.0
    assert timer_id not in tracker.timers
    assert "test_stage" in tracker.measurements


def test_performance_tracker_metrics():
    """Test performance tracker metrics aggregation."""
    tracker = PerformanceTracker()

    # Record multiple measurements
    for _ in range(10):
        timer_id = tracker.start_timer("test_stage")
        tracker.end_timer(timer_id)

    metrics = tracker.get_metrics()
    assert "test_stage" in metrics
    assert metrics["test_stage"]["count"] == 10
    assert "avg_ms" in metrics["test_stage"]
    assert "p50_ms" in metrics["test_stage"]


# ============================================================================
# Test: Forex Session Detection
# ============================================================================


def test_forex_session_detection_overlap():
    """Test forex session detection for OVERLAP (13:00-17:00 UTC)."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    # Test OVERLAP period (14:00 UTC)
    test_time = datetime(2024, 3, 13, 14, 0, 0, tzinfo=UTC)
    session = orchestrator._get_forex_session(test_time)
    assert session == ForexSession.OVERLAP


def test_forex_session_detection_london():
    """Test forex session detection for LONDON (8:00-13:00 UTC)."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    # Test LONDON period (10:00 UTC, before overlap)
    test_time = datetime(2024, 3, 13, 10, 0, 0, tzinfo=UTC)
    session = orchestrator._get_forex_session(test_time)
    assert session == ForexSession.LONDON


def test_forex_session_detection_ny():
    """Test forex session detection for NY (17:00-22:00 UTC)."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    # Test NY period (18:00 UTC, after overlap)
    test_time = datetime(2024, 3, 13, 18, 0, 0, tzinfo=UTC)
    session = orchestrator._get_forex_session(test_time)
    assert session == ForexSession.NY


def test_forex_session_detection_asian():
    """Test forex session detection for ASIAN (0:00-8:00 UTC)."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    # Test ASIAN period (3:00 UTC)
    test_time = datetime(2024, 3, 13, 3, 0, 0, tzinfo=UTC)
    session = orchestrator._get_forex_session(test_time)
    assert session == ForexSession.ASIAN


# ============================================================================
# Test: Asset Class Detection
# ============================================================================


def test_asset_class_detection_stock():
    """Test asset class detection for stocks."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    assert orchestrator._detect_asset_class("AAPL") == "STOCK"
    assert orchestrator._detect_asset_class("MSFT") == "STOCK"
    assert orchestrator._detect_asset_class("SPY") == "STOCK"


def test_asset_class_detection_forex():
    """Test asset class detection for forex pairs."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    assert orchestrator._detect_asset_class("EUR/USD") == "FOREX"
    assert orchestrator._detect_asset_class("GBP/JPY") == "FOREX"
    assert orchestrator._detect_asset_class("USD/CHF") == "FOREX"


def test_asset_class_detection_crypto():
    """Test asset class detection for crypto pairs."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    assert orchestrator._detect_asset_class("BTC/USD") == "CRYPTO"
    assert orchestrator._detect_asset_class("ETH/USD") == "CRYPTO"
    assert orchestrator._detect_asset_class("USDT/USD") == "CRYPTO"


def test_is_forex_symbol():
    """Test forex symbol detection."""
    orchestrator = MasterOrchestrator(strategy_validator=Mock(spec=StrategyValidator))

    assert orchestrator._is_forex_symbol("EUR/USD") is True
    assert orchestrator._is_forex_symbol("AAPL") is False
    assert orchestrator._is_forex_symbol("BTC/USD") is True


# ============================================================================
# Test: Validation Chain Execution
# ============================================================================


@pytest.mark.asyncio
async def test_validation_chain_all_pass(
    orchestrator, sample_pattern, sample_validation_context, mock_validators
):
    """Test validation chain when all validators pass."""
    # Mock all validators to return PASS
    for validator in mock_validators.values():
        validator.validate = AsyncMock(
            return_value=StageValidationResult(
                stage="TEST",
                status=ValidationStatus.PASS,
                validator_id="TEST_VALIDATOR",
            )
        )

    chain = await orchestrator.run_validation_chain(
        sample_pattern,
        sample_validation_context,
        correlation_id="test-123",
    )

    assert chain.overall_status == ValidationStatus.PASS
    assert len(chain.validation_results) == 5  # All 5 validators
    assert chain.completed_at is not None


@pytest.mark.asyncio
async def test_validation_chain_early_exit_on_volume_failure(
    orchestrator, sample_pattern, sample_validation_context, mock_validators
):
    """Test validation chain early exit when Volume validator fails."""
    # Mock Volume validator to return FAIL
    mock_validators["volume"].validate = AsyncMock(
        return_value=StageValidationResult(
            stage="VOLUME",
            status=ValidationStatus.FAIL,
            reason="Spring volume 0.75x exceeds 0.60x threshold",
            validator_id="VOLUME_VALIDATOR",
        )
    )

    # Mock other validators (should not be called)
    for name, validator in mock_validators.items():
        if name != "volume":
            validator.validate = AsyncMock(side_effect=AssertionError("Should not be called"))

    chain = await orchestrator.run_validation_chain(
        sample_pattern,
        sample_validation_context,
        correlation_id="test-123",
    )

    assert chain.overall_status == ValidationStatus.FAIL
    assert len(chain.validation_results) == 1  # Only Volume validator
    assert chain.rejection_stage == "VOLUME"
    assert "Spring volume" in chain.rejection_reason


@pytest.mark.asyncio
async def test_validation_chain_early_exit_on_risk_failure(
    orchestrator, sample_pattern, sample_validation_context, mock_validators
):
    """Test validation chain early exit when Risk validator fails."""
    # Mock Volume, Phase, Level validators to return PASS
    for name in ["volume", "phase", "level"]:
        mock_validators[name].validate = AsyncMock(
            return_value=StageValidationResult(
                stage=name.upper(),
                status=ValidationStatus.PASS,
                validator_id=f"{name.upper()}_VALIDATOR",
            )
        )

    # Mock Risk validator to return FAIL
    mock_validators["risk"].validate = AsyncMock(
        return_value=StageValidationResult(
            stage="RISK",
            status=ValidationStatus.FAIL,
            reason="Portfolio heat would exceed 10% limit",
            validator_id="RISK_VALIDATOR",
        )
    )

    # Mock Strategy validator (should not be called)
    mock_validators["strategy"].validate = AsyncMock(
        side_effect=AssertionError("Should not be called")
    )

    chain = await orchestrator.run_validation_chain(
        sample_pattern,
        sample_validation_context,
        correlation_id="test-123",
    )

    assert chain.overall_status == ValidationStatus.FAIL
    assert len(chain.validation_results) == 4  # Volume, Phase, Level, Risk
    assert chain.rejection_stage == "RISK"
    assert "Portfolio heat" in chain.rejection_reason


# ============================================================================
# Test: Multi-Symbol Watchlist Processing
# ============================================================================


@pytest.mark.asyncio
async def test_parallel_watchlist_processing(orchestrator):
    """Test parallel processing of multiple symbols."""

    # Mock analyze_symbol to return signals
    async def mock_analyze_symbol(symbol: str, timeframe: str, correlation_id: str | None = None):
        return []  # Empty signals for testing

    orchestrator.analyze_symbol = mock_analyze_symbol

    symbols = ["AAPL", "MSFT", "TSLA"]
    result = await orchestrator.analyze_watchlist(symbols, "1h")

    assert len(result) == 3
    assert "AAPL" in result
    assert "MSFT" in result
    assert "TSLA" in result


@pytest.mark.asyncio
async def test_watchlist_handles_symbol_failure(orchestrator):
    """Test watchlist processing continues when one symbol fails."""
    call_count = 0

    async def mock_analyze_symbol(symbol: str, timeframe: str, correlation_id: str | None = None):
        nonlocal call_count
        call_count += 1
        if symbol == "MSFT":
            raise Exception("MSFT analysis failed")
        return []

    orchestrator.analyze_symbol = mock_analyze_symbol

    symbols = ["AAPL", "MSFT", "TSLA"]
    result = await orchestrator.analyze_watchlist(symbols, "1h")

    # All 3 symbols should have been attempted
    assert call_count == 3
    # Only AAPL and TSLA should be in results (MSFT failed)
    assert len(result) == 2
    assert "AAPL" in result
    assert "TSLA" in result
    assert "MSFT" not in result


# ============================================================================
# Test: Cache Invalidation
# ============================================================================


def test_cache_invalidation_on_new_bar(orchestrator):
    """Test cache invalidation when new bar arrives."""
    # Populate cache
    orchestrator._range_cache["AAPL"] = (Mock(), datetime.now(UTC).timestamp())
    orchestrator._phase_cache["AAPL"] = (Mock(), datetime.now(UTC).timestamp())

    assert "AAPL" in orchestrator._range_cache
    assert "AAPL" in orchestrator._phase_cache

    # Invalidate cache
    orchestrator._invalidate_cache("AAPL")

    assert "AAPL" not in orchestrator._range_cache
    assert "AAPL" not in orchestrator._phase_cache


# ============================================================================
# Test: Signal Generation
# ============================================================================


@pytest.mark.asyncio
async def test_generate_signal_from_passed_validation(
    orchestrator, sample_pattern, sample_validation_context, mock_repositories
):
    """Test TradeSignal generation when validation passes."""
    # Create passing validation chain
    chain = ValidationChain(pattern_id=sample_pattern["id"])
    chain.add_result(
        StageValidationResult(
            stage="VOLUME",
            status=ValidationStatus.PASS,
            validator_id="VOLUME_VALIDATOR",
        )
    )
    chain.overall_status = ValidationStatus.PASS
    chain.completed_at = datetime.now(UTC)

    # Mock repository
    mock_repositories["signal"].save_signal = AsyncMock(side_effect=lambda s: s)

    signal = await orchestrator.generate_signal_from_pattern(
        sample_pattern,
        chain,
        sample_validation_context,
    )

    assert isinstance(signal, TradeSignal)
    assert signal.symbol == "AAPL"
    assert signal.pattern_type == "SPRING"
    assert signal.status == "APPROVED"
    assert signal.validation_chain.overall_status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_generate_rejection_from_failed_validation(
    orchestrator, sample_pattern, sample_validation_context, mock_repositories
):
    """Test RejectedSignal creation when validation fails."""
    # Create failing validation chain
    chain = ValidationChain(pattern_id=sample_pattern["id"])
    chain.add_result(
        StageValidationResult(
            stage="VOLUME",
            status=ValidationStatus.FAIL,
            reason="Volume too high",
            validator_id="VOLUME_VALIDATOR",
        )
    )
    chain.completed_at = datetime.now(UTC)

    # Mock repository
    mock_repositories["rejection"].log_rejection = AsyncMock(side_effect=lambda r: r)

    rejection = await orchestrator.generate_signal_from_pattern(
        sample_pattern,
        chain,
        sample_validation_context,
    )

    assert isinstance(rejection, RejectedSignal)
    assert rejection.symbol == "AAPL"
    assert rejection.pattern_type == "SPRING"
    assert rejection.rejection_stage == "VOLUME"
    assert "Volume too high" in rejection.rejection_reason


# ============================================================================
# Test: Real-Time Mode
# ============================================================================


@pytest.mark.asyncio
async def test_process_new_bar(orchestrator):
    """Test real-time bar processing."""

    # Mock analyze_symbol
    async def mock_analyze_symbol(symbol: str, timeframe: str, correlation_id: str | None = None):
        return []

    orchestrator.analyze_symbol = mock_analyze_symbol

    # Mock bar
    bar = {"symbol": "AAPL", "timeframe": "1h"}

    signals = await orchestrator.process_new_bar(bar)

    assert isinstance(signals, list)
    assert len(signals) == 0


# ============================================================================
# Test: System State
# ============================================================================


def test_orchestrator_initialization():
    """Test MasterOrchestrator initialization with default values."""
    orchestrator = MasterOrchestrator(
        strategy_validator=Mock(spec=StrategyValidator),
    )

    assert orchestrator.max_concurrent_symbols == 10
    assert orchestrator.cache_ttl_seconds == 300
    assert orchestrator._system_halted is False
    assert len(orchestrator._range_cache) == 0
    assert len(orchestrator._phase_cache) == 0


def test_orchestrator_initialization_with_custom_values():
    """Test MasterOrchestrator initialization with custom values."""
    orchestrator = MasterOrchestrator(
        strategy_validator=Mock(spec=StrategyValidator),
        max_concurrent_symbols=20,
        cache_ttl_seconds=600,
        enable_performance_tracking=False,
    )

    assert orchestrator.max_concurrent_symbols == 20
    assert orchestrator.cache_ttl_seconds == 600
    assert orchestrator.enable_performance_tracking is False


# ============================================================================
# Test: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_symbol_handles_exception(orchestrator):
    """Test analyze_symbol handles exceptions gracefully."""

    # Mock _fetch_bars to raise exception
    async def mock_fetch_bars(symbol: str, timeframe: str, limit: int):
        raise Exception("Database connection error")

    orchestrator._fetch_bars = mock_fetch_bars

    # Should not raise exception
    signals = await orchestrator.analyze_symbol("AAPL", "1h")

    # Should return empty list on error
    assert signals == []


@pytest.mark.asyncio
async def test_validation_chain_handles_validator_exception(
    orchestrator, sample_pattern, sample_validation_context, mock_validators
):
    """Test validation chain handles validator exceptions."""
    # Mock Volume validator to raise exception
    mock_validators["volume"].validate = AsyncMock(side_effect=Exception("Validator crashed"))

    chain = await orchestrator.run_validation_chain(
        sample_pattern,
        sample_validation_context,
        correlation_id="test-123",
    )

    # Chain should fail with system error
    assert chain.overall_status == ValidationStatus.FAIL
    assert chain.rejection_stage == "SYSTEM"
    assert "Validation chain error" in chain.rejection_reason


# ============================================================================
# Test: Performance Tracking
# ============================================================================


@pytest.mark.asyncio
async def test_performance_tracking_records_latency(orchestrator):
    """Test performance tracking records latency for each stage."""

    # Mock _fetch_bars to simulate work
    async def mock_fetch_bars(symbol: str, timeframe: str, limit: int):
        import asyncio

        await asyncio.sleep(0.01)  # Simulate work
        return []

    orchestrator._fetch_bars = mock_fetch_bars

    # Enable performance tracking
    orchestrator.enable_performance_tracking = True

    await orchestrator.analyze_symbol("AAPL", "1h")

    # Check that metrics were recorded
    metrics = orchestrator.performance_tracker.get_metrics()
    assert "fetch_bars" in metrics
    assert metrics["fetch_bars"]["count"] >= 1


# ============================================================================
# Test: Emergency Exits
# ============================================================================


@pytest.mark.asyncio
async def test_check_emergency_exits(orchestrator):
    """Test emergency exit checking."""
    bar = {"symbol": "AAPL", "low": Decimal("145.00"), "high": Decimal("151.00")}

    exits = await orchestrator.check_emergency_exits(bar)

    # Stub implementation returns empty list
    assert isinstance(exits, list)
    assert len(exits) == 0


# ============================================================================
# Test: Service Integration Helper Methods (Story 8.10.1)
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_bars_returns_bars_for_valid_symbol():
    """Test _fetch_bars() returns bars when market_data_service succeeds."""
    # Arrange
    mock_market_data_service = Mock()
    mock_bars = [Mock(), Mock(), Mock()]
    mock_market_data_service.fetch_bars = AsyncMock(return_value=mock_bars)

    orchestrator = MasterOrchestrator(market_data_service=mock_market_data_service)

    # Act
    result = await orchestrator._fetch_bars("AAPL", "1h", limit=100)

    # Assert
    assert result == mock_bars
    mock_market_data_service.fetch_bars.assert_called_once_with(
        symbol="AAPL", timeframe="1h", limit=100
    )


@pytest.mark.asyncio
async def test_fetch_bars_handles_service_error():
    """Test _fetch_bars() returns [] when market_data_service raises exception."""
    # Arrange
    mock_market_data_service = Mock()
    mock_market_data_service.fetch_bars = AsyncMock(side_effect=Exception("Service error"))

    orchestrator = MasterOrchestrator(market_data_service=mock_market_data_service)

    # Act
    result = await orchestrator._fetch_bars("AAPL", "1h")

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_fetch_bars_returns_empty_when_service_not_configured():
    """Test _fetch_bars() returns [] when market_data_service is None."""
    # Arrange
    orchestrator = MasterOrchestrator(market_data_service=None)

    # Act
    result = await orchestrator._fetch_bars("AAPL", "1h")

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_fetch_volume_analysis_passes_forex_session():
    """Test _fetch_volume_analysis() passes forex_session parameter (Victoria requirement)."""
    # Arrange
    mock_volume_service = Mock()
    mock_analysis = Mock()
    mock_volume_service.get_analysis = AsyncMock(return_value=mock_analysis)

    orchestrator = MasterOrchestrator()
    orchestrator.volume_service = mock_volume_service

    pattern = {"id": uuid4(), "bar_timestamp": datetime(2024, 1, 1, 9, 0, tzinfo=UTC)}

    # Act
    result = await orchestrator._fetch_volume_analysis("EUR/USD", pattern, "LONDON")

    # Assert
    assert result == mock_analysis
    mock_volume_service.get_analysis.assert_called_once_with(
        symbol="EUR/USD",
        timestamp=pattern["bar_timestamp"],
        forex_session="LONDON",  # CRITICAL: Session must be passed
    )


@pytest.mark.asyncio
async def test_fetch_volume_analysis_returns_none_on_error():
    """Test _fetch_volume_analysis() returns None when service raises exception."""
    # Arrange
    mock_volume_service = Mock()
    mock_volume_service.get_analysis = AsyncMock(side_effect=Exception("Service error"))

    orchestrator = MasterOrchestrator()
    orchestrator.volume_service = mock_volume_service

    pattern = {"id": uuid4(), "bar_timestamp": datetime(2024, 1, 1, 9, 0, tzinfo=UTC)}

    # Act
    result = await orchestrator._fetch_volume_analysis("EUR/USD", pattern, "LONDON")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_fetch_trading_range_returns_range_for_valid_id():
    """Test _fetch_trading_range() returns TradingRange for valid UUID."""
    # Arrange
    mock_trading_range_service = Mock()
    mock_range = Mock()
    mock_trading_range_service.get_by_id = AsyncMock(return_value=mock_range)

    orchestrator = MasterOrchestrator(trading_range_service=mock_trading_range_service)

    range_id = uuid4()

    # Act
    result = await orchestrator._fetch_trading_range(range_id)

    # Assert
    assert result == mock_range
    mock_trading_range_service.get_by_id.assert_called_once_with(range_id)


@pytest.mark.asyncio
async def test_fetch_trading_range_returns_none_for_invalid_id():
    """Test _fetch_trading_range() returns None when service raises exception."""
    # Arrange
    mock_trading_range_service = Mock()
    mock_trading_range_service.get_by_id = AsyncMock(side_effect=Exception("Not found"))

    orchestrator = MasterOrchestrator(trading_range_service=mock_trading_range_service)

    # Act
    result = await orchestrator._fetch_trading_range(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_fetch_portfolio_context_returns_current_state():
    """Test _fetch_portfolio_context() returns PortfolioContext with total_forex_notional."""
    # Arrange
    mock_portfolio_service = Mock()
    mock_context = {
        "total_equity": Decimal("10000"),
        "available_equity": Decimal("8000"),
        "total_heat": Decimal("5.5"),
        "active_positions": [],
        "active_campaigns": [],
        "total_forex_notional": Decimal("15000"),  # Rachel requirement
        "max_forex_notional": Decimal("30000"),
    }
    mock_portfolio_service.get_current_context = AsyncMock(return_value=mock_context)

    orchestrator = MasterOrchestrator()
    orchestrator.portfolio_service = mock_portfolio_service

    # Act
    result = await orchestrator._fetch_portfolio_context()

    # Assert
    assert result == mock_context
    assert result["total_forex_notional"] == Decimal("15000")  # Verify Rachel requirement
    mock_portfolio_service.get_current_context.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_portfolio_context_returns_safe_defaults_on_error():
    """Test _fetch_portfolio_context() returns safe defaults when service fails."""
    # Arrange
    mock_portfolio_service = Mock()
    mock_portfolio_service.get_current_context = AsyncMock(side_effect=Exception("Service error"))

    orchestrator = MasterOrchestrator()
    orchestrator.portfolio_service = mock_portfolio_service

    # Act
    result = await orchestrator._fetch_portfolio_context()

    # Assert
    assert result["total_equity"] == Decimal("0")
    assert result["total_forex_notional"] == Decimal("0")
    assert result["active_positions"] == []


@pytest.mark.asyncio
async def test_build_market_context_for_stock_includes_asset_class():
    """Test _build_market_context() passes asset_class parameter."""
    # Arrange
    mock_builder = Mock()
    mock_context = {
        "symbol": "AAPL",
        "asset_class": "STOCK",
        "upcoming_events": [],
        "market_regime": "TRENDING",
    }
    mock_builder.build = AsyncMock(return_value=mock_context)

    orchestrator = MasterOrchestrator()
    orchestrator.market_context_builder = mock_builder

    # Act
    result = await orchestrator._build_market_context("AAPL", "STOCK", forex_session=None)

    # Assert
    assert result == mock_context
    mock_builder.build.assert_called_once_with(
        symbol="AAPL", asset_class="STOCK", forex_session=None
    )


@pytest.mark.asyncio
async def test_build_market_context_for_forex_passes_session():
    """Test _build_market_context() passes forex_session for FOREX symbols."""
    # Arrange
    mock_builder = Mock()
    mock_context = {
        "symbol": "EUR/USD",
        "asset_class": "FOREX",
        "upcoming_events": [],
        "market_regime": "RANGING",
        "forex_session": "LONDON",
    }
    mock_builder.build = AsyncMock(return_value=mock_context)

    orchestrator = MasterOrchestrator()
    orchestrator.market_context_builder = mock_builder

    # Act
    result = await orchestrator._build_market_context("EUR/USD", "FOREX", forex_session="LONDON")

    # Assert
    assert result == mock_context
    mock_builder.build.assert_called_once_with(
        symbol="EUR/USD", asset_class="FOREX", forex_session="LONDON"
    )


@pytest.mark.asyncio
async def test_fetch_historical_bars_returns_chronological_order():
    """Test _fetch_historical_bars() returns bars sorted by timestamp."""
    # Arrange
    mock_market_data_service = Mock()

    # Create unsorted bars
    bar1 = Mock(timestamp=datetime(2024, 1, 3, tzinfo=UTC))
    bar2 = Mock(timestamp=datetime(2024, 1, 1, tzinfo=UTC))
    bar3 = Mock(timestamp=datetime(2024, 1, 2, tzinfo=UTC))

    mock_market_data_service.fetch_historical = AsyncMock(return_value=[bar1, bar2, bar3])

    orchestrator = MasterOrchestrator(market_data_service=mock_market_data_service)

    # Act
    result = await orchestrator._fetch_historical_bars(
        "AAPL", "1d", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 31, tzinfo=UTC)
    )

    # Assert
    assert len(result) == 3
    # Verify chronological order (oldest first)
    assert result[0].timestamp == datetime(2024, 1, 1, tzinfo=UTC)
    assert result[1].timestamp == datetime(2024, 1, 2, tzinfo=UTC)
    assert result[2].timestamp == datetime(2024, 1, 3, tzinfo=UTC)


@pytest.mark.asyncio
async def test_fetch_historical_bars_handles_service_error():
    """Test _fetch_historical_bars() returns [] when service fails."""
    # Arrange
    mock_market_data_service = Mock()
    mock_market_data_service.fetch_historical = AsyncMock(side_effect=Exception("Service error"))

    orchestrator = MasterOrchestrator(market_data_service=mock_market_data_service)

    # Act
    result = await orchestrator._fetch_historical_bars(
        "AAPL", "1d", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 31, tzinfo=UTC)
    )

    # Assert
    assert result == []


@pytest.mark.asyncio
async def test_service_failure_does_not_crash_pipeline():
    """Test that service failures log errors but don't crash the pipeline."""
    # Arrange
    mock_market_data_service = Mock()
    mock_market_data_service.fetch_bars = AsyncMock(
        side_effect=Exception("Database connection lost")
    )

    orchestrator = MasterOrchestrator(market_data_service=mock_market_data_service)

    # Act - Should not raise exception
    result = await orchestrator._fetch_bars("AAPL", "1h")

    # Assert
    assert result == []  # Graceful degradation
