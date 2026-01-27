"""
Integration tests for Auto-Execution Flow

Tests the complete auto-execution pipeline from signal evaluation to execution.
Story 19.16: Auto-Execution Engine
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.auto_execution import AutoExecutionBypassReason
from src.models.auto_execution_config import AutoExecutionConfig
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import StageValidationResult, ValidationChain, ValidationStatus
from src.services.auto_execution_engine import AutoExecutionEngine
from src.services.daily_counters import DailyCounters


def create_mock_redis_with_pipeline(get_side_effect=None):
    """Create a mock Redis client with pipeline support."""
    mock_redis = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.incr = MagicMock()
    mock_pipeline.expire = MagicMock()
    mock_pipeline.incrbyfloat = MagicMock()
    mock_pipeline.decr = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=[1, True, 1.5, True])

    # Create async context manager for pipeline
    class MockPipelineContext:
        async def __aenter__(self):
            return mock_pipeline

        async def __aexit__(self, *args):
            return None

    # Make pipeline a regular MagicMock (not async) that returns our context manager
    mock_redis.pipeline = MagicMock(return_value=MockPipelineContext())

    if get_side_effect is not None:
        mock_redis.get.side_effect = get_side_effect
    else:
        mock_redis.get.return_value = "0"

    return mock_redis, mock_pipeline


def create_test_signal(
    symbol: str = "AAPL",
    pattern_type: str = "SPRING",
    confidence_score: int = 87,
    risk_percentage: str = "1.5",
) -> TradeSignal:
    """Create a test trade signal with configurable parameters."""
    # Calculate component values that produce the desired overall confidence
    # Weights: pattern 50%, phase 30%, volume 20%
    # We set all components equal to get exact overall confidence
    confidence_components = ConfidenceComponents(
        pattern_confidence=confidence_score,
        phase_confidence=confidence_score,
        volume_confidence=confidence_score,
        overall_confidence=confidence_score,
    )

    target_levels = TargetLevels(
        primary_target=Decimal("156.00"),
        secondary_targets=[],
    )

    validation_chain = ValidationChain(
        pattern_id=uuid4(),
        validation_results=[
            StageValidationResult(
                stage="Volume",
                status=ValidationStatus.PASS,
                validator_id="VolumeValidator",
                metadata={},
            ),
            StageValidationResult(
                stage="Risk",
                status=ValidationStatus.PASS,
                validator_id="RiskValidator",
                metadata={"risk_percentage": risk_percentage},
            ),
        ],
    )

    return TradeSignal(
        id=uuid4(),
        symbol=symbol,
        asset_class="STOCK",
        pattern_type=pattern_type,
        phase="C",
        timeframe="1H",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=target_levels,
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        notional_value=Decimal("15000.00"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=confidence_score,
        confidence_components=confidence_components,
        validation_chain=validation_chain,
        timestamp=datetime.now(UTC),
    )


def create_test_config(
    enabled: bool = True,
    kill_switch: bool = False,
    min_confidence: Decimal = Decimal("85.00"),
    max_trades: int = 10,
    max_risk: Decimal | None = Decimal("5.0"),
    enabled_patterns: list[str] | None = None,
    whitelist: list[str] | None = None,
    blacklist: list[str] | None = None,
) -> AutoExecutionConfig:
    """Create a test auto-execution configuration."""
    user_id = uuid4()
    now = datetime.now(UTC)

    return AutoExecutionConfig(
        user_id=user_id,
        enabled=enabled,
        min_confidence=min_confidence,
        max_trades_per_day=max_trades,
        max_risk_per_day=max_risk,
        circuit_breaker_losses=3,
        enabled_patterns=enabled_patterns or ["SPRING", "SOS", "LPS"],
        symbol_whitelist=whitelist,
        symbol_blacklist=blacklist,
        kill_switch_active=kill_switch,
        consent_given_at=now if enabled else None,
        consent_ip_address="192.168.1.1" if enabled else None,
        created_at=now,
        updated_at=now,
    )


class TestFullAutoExecutionFlow:
    """Integration tests for complete auto-execution flow."""

    @pytest.mark.asyncio
    async def test_successful_auto_execution_flow(self):
        """
        Scenario 1: Successful Auto-Execution

        Given auto-execution is enabled with 85% confidence threshold
        When a 92% confidence Spring signal is approved
        Then signal bypasses approval queue
        And position opens automatically via paper trading
        And user receives notification "Position opened: AAPL Spring"
        And daily trade counter increments
        """
        # Setup
        config = create_test_config(min_confidence=Decimal("85.00"))
        signal = create_test_signal(confidence_score=92)

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis, mock_pipeline = create_mock_redis_with_pipeline()
        mock_redis.get.return_value = "0"  # No trades today

        mock_paper_trading = AsyncMock()
        position = MagicMock()
        position.id = uuid4()
        position.entry_price = Decimal("150.00")
        position.quantity = Decimal("100")
        mock_paper_trading.execute_signal.return_value = position

        mock_notification = AsyncMock()

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
            paper_trading_service=mock_paper_trading,
            notification_service=mock_notification,
        )

        # Execute
        eval_result, exec_result = await engine.evaluate_and_execute(config.user_id, signal)

        # Verify
        assert eval_result.auto_execute is True
        assert eval_result.route_to_queue is False

        assert exec_result is not None
        assert exec_result.success is True
        assert exec_result.position_id == position.id

        # Verify trade counter incremented via pipeline
        mock_pipeline.incr.assert_called()

        # Verify notification sent
        mock_notification.notify_signal_approved.assert_called_once_with(signal)

    @pytest.mark.asyncio
    async def test_below_confidence_threshold_flow(self):
        """
        Scenario 2: Below Confidence Threshold

        Given auto-execution threshold is 85%
        When a 78% confidence signal is approved
        Then signal goes to manual approval queue
        And reason logged: "Confidence 78% below threshold 85%"
        """
        # Setup
        config = create_test_config(min_confidence=Decimal("85.00"))
        signal = create_test_signal(confidence_score=78)

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0"

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.CONFIDENCE_TOO_LOW
        assert "78" in result.reason
        assert "85" in result.reason

    @pytest.mark.asyncio
    async def test_daily_trade_limit_flow(self):
        """
        Scenario 3: Daily Trade Limit

        Given daily execution limit is 5 trades
        And 5 trades have already executed today
        When a 6th qualifying signal is approved
        Then signal is NOT auto-executed
        And signal goes to manual approval queue
        And reason: "Daily trade limit reached (5/5)"
        """
        # Setup
        config = create_test_config(max_trades=5)
        signal = create_test_signal(confidence_score=90)

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ["5", b"2.0"]  # 5 trades, 2% risk

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.DAILY_TRADE_LIMIT
        assert "5/5" in result.reason

    @pytest.mark.asyncio
    async def test_daily_risk_limit_flow(self):
        """
        Scenario 4: Daily Risk Limit

        Given daily risk limit is 5%
        And 4.5% risk has been used today
        When a signal with 1% risk is approved
        Then signal is NOT auto-executed
        And reason: "Daily risk limit exceeded (4.5% + 1% > 5%)"
        """
        # Setup
        config = create_test_config(max_risk=Decimal("5.0"))
        signal = create_test_signal(risk_percentage="1.0")

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ["2", b"4.5"]  # 2 trades, 4.5% risk

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.DAILY_RISK_LIMIT
        assert "4.5" in result.reason
        assert "5" in result.reason

    @pytest.mark.asyncio
    async def test_symbol_whitelist_flow(self):
        """
        Scenario 5: Symbol Whitelist

        Given whitelist is ["AAPL", "TSLA"]
        When a qualifying signal arrives for MSFT
        Then signal goes to manual approval queue
        And reason: "Symbol MSFT not in whitelist"
        """
        # Setup
        config = create_test_config(whitelist=["AAPL", "TSLA"])
        signal = create_test_signal(symbol="MSFT")

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0"

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.SYMBOL_NOT_IN_WHITELIST
        assert "MSFT" in result.reason
        assert "whitelist" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_symbol_blacklist_flow(self):
        """
        Scenario 6: Symbol Blacklist

        Given blacklist is ["MEME"]
        When a qualifying signal arrives for MEME
        Then signal goes to manual approval queue
        And reason: "Symbol MEME is blacklisted"
        """
        # Setup
        config = create_test_config(blacklist=["MEME"])
        signal = create_test_signal(symbol="MEME")

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0"

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.SYMBOL_BLACKLISTED
        assert "MEME" in result.reason
        assert "blacklist" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_kill_switch_flow(self):
        """
        Scenario 7: Kill Switch Active

        Given auto-execution is enabled
        And kill switch is active
        When a qualifying signal is approved
        Then signal goes to manual approval queue
        And reason: "Kill switch active"
        """
        # Setup
        config = create_test_config(kill_switch=True)
        signal = create_test_signal(confidence_score=95)

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0"

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.KILL_SWITCH
        assert "kill switch" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_pattern_not_enabled_flow(self):
        """
        Scenario 8: Pattern Not Enabled

        Given enabled_patterns is ["SPRING"]
        When a qualifying SOS signal is approved
        Then signal goes to manual approval queue
        And reason: "Pattern SOS not enabled for auto-execution"
        """
        # Setup
        config = create_test_config(enabled_patterns=["SPRING"])
        signal = create_test_signal(pattern_type="SOS")

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0"

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        # Execute
        result = await engine.evaluate_signal(config.user_id, signal)

        # Verify
        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.PATTERN_NOT_ENABLED
        assert "SOS" in result.reason
        assert "not enabled" in result.reason.lower()


class TestAutoExecutionCounterAccumulation:
    """Tests for counter accumulation across multiple executions."""

    @pytest.mark.asyncio
    async def test_counters_accumulate_across_executions(self):
        """Test that daily counters accumulate correctly across multiple executions."""
        # Setup
        config = create_test_config(max_trades=10, max_risk=Decimal("10.0"))

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = config

        # Track cumulative state
        trade_count = 0
        risk_total = Decimal("0.0")

        async def mock_get(key):
            if "trades" in key:
                return str(trade_count)
            if "risk" in key:
                return str(risk_total).encode()
            return None

        # Create mock Redis with pipeline that tracks state
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = mock_get

        # Create pipeline that tracks increments
        mock_pipeline = AsyncMock()

        async def mock_execute():
            nonlocal trade_count, risk_total
            trade_count += 1
            risk_total += Decimal("1.5")
            return [trade_count, True, float(risk_total), True]

        mock_pipeline.incr = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.incrbyfloat = MagicMock()
        mock_pipeline.execute = mock_execute

        # Create async context manager for pipeline
        class MockPipelineContext:
            async def __aenter__(self):
                return mock_pipeline

            async def __aexit__(self, *args):
                return None

        # Make pipeline a regular MagicMock (not async) that returns our context manager
        mock_redis.pipeline = MagicMock(return_value=MockPipelineContext())

        mock_paper_trading = AsyncMock()
        position = MagicMock()
        position.id = uuid4()
        position.entry_price = Decimal("150.00")
        position.quantity = Decimal("100")
        mock_paper_trading.execute_signal.return_value = position

        counters = DailyCounters(mock_redis)
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
            paper_trading_service=mock_paper_trading,
        )

        # Execute multiple signals
        for i in range(3):
            signal = create_test_signal(confidence_score=90, risk_percentage="1.5")
            await engine.execute_signal(config.user_id, signal)

        # Verify counters accumulated (each execution calls pipeline.execute twice:
        # once for increment_trades and once for add_risk)
        assert trade_count == 6  # 3 signals * 2 execute calls each
        assert risk_total == Decimal("9.0")  # 6 * 1.5%


class TestAutoExecutionWithNoConfig:
    """Tests for handling missing configuration."""

    @pytest.mark.asyncio
    async def test_no_config_bypasses_to_queue(self):
        """Test that missing config routes to manual queue."""
        signal = create_test_signal()

        mock_config_repo = AsyncMock()
        mock_config_repo.get_config.return_value = None

        mock_redis = AsyncMock()
        counters = DailyCounters(mock_redis)

        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=counters,
        )

        result = await engine.evaluate_signal(uuid4(), signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.DISABLED
