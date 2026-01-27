"""
Unit tests for Auto-Execution Engine

Tests rule evaluation chain, signal execution, and daily counter integration.
Story 19.16: Auto-Execution Engine
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.auto_execution import (
    AutoExecutionBypassReason,
)
from src.models.auto_execution_config import AutoExecutionConfig
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import StageValidationResult, ValidationChain, ValidationStatus
from src.services.auto_execution_engine import AutoExecutionEngine
from src.services.daily_counters import DailyCounters


@pytest.fixture
def mock_config_repo():
    """Create a mock auto-execution config repository."""
    return AsyncMock()


@pytest.fixture
def mock_daily_counters():
    """Create a mock daily counters service."""
    counters = AsyncMock(spec=DailyCounters)
    counters.get_trades_today.return_value = 0
    counters.get_risk_today.return_value = Decimal("0.0")
    counters.increment_trades.return_value = 1
    counters.add_risk.return_value = Decimal("1.5")
    return counters


@pytest.fixture
def mock_paper_trading():
    """Create a mock paper trading service."""
    service = AsyncMock()
    position = MagicMock()
    position.id = uuid4()
    position.entry_price = Decimal("150.00")
    position.quantity = Decimal("100")
    service.execute_signal.return_value = position
    return service


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service."""
    return AsyncMock()


@pytest.fixture
def engine(mock_config_repo, mock_daily_counters, mock_paper_trading, mock_notification_service):
    """Create AutoExecutionEngine with mock dependencies."""
    return AutoExecutionEngine(
        config_repository=mock_config_repo,
        daily_counters=mock_daily_counters,
        paper_trading_service=mock_paper_trading,
        notification_service=mock_notification_service,
    )


@pytest.fixture
def enabled_config():
    """Create enabled auto-execution configuration."""
    user_id = uuid4()
    now = datetime.now(UTC)
    return AutoExecutionConfig(
        user_id=user_id,
        enabled=True,
        min_confidence=Decimal("85.00"),
        max_trades_per_day=10,
        max_risk_per_day=Decimal("5.0"),
        circuit_breaker_losses=3,
        enabled_patterns=["SPRING", "SOS", "LPS"],
        symbol_whitelist=None,
        symbol_blacklist=None,
        kill_switch_active=False,
        consent_given_at=now,
        consent_ip_address="192.168.1.1",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_signal():
    """Create a sample trade signal with 87% confidence."""
    confidence_components = ConfidenceComponents(
        pattern_confidence=90,
        phase_confidence=85,
        volume_confidence=80,
        overall_confidence=87,
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
                metadata={"risk_percentage": "1.5"},
            ),
        ],
    )

    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="SPRING",
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
        confidence_score=87,
        confidence_components=confidence_components,
        validation_chain=validation_chain,
        timestamp=datetime.now(UTC),
    )


class TestAutoExecutionEvaluation:
    """Tests for signal evaluation logic."""

    @pytest.mark.asyncio
    async def test_successful_auto_execution_evaluation(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal that passes all eligibility checks."""
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is True
        assert result.route_to_queue is False
        assert result.bypass_reason is None

    @pytest.mark.asyncio
    async def test_disabled_auto_execution_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when auto-execution is disabled."""
        enabled_config.enabled = False
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.DISABLED

    @pytest.mark.asyncio
    async def test_kill_switch_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when kill switch is active."""
        enabled_config.kill_switch_active = True
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.KILL_SWITCH
        assert "kill switch" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_no_consent_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when consent not given."""
        enabled_config.consent_given_at = None
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.NO_CONSENT

    @pytest.mark.asyncio
    async def test_confidence_below_threshold_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when confidence below threshold."""
        # Signal has 87% but threshold is 85%, so this should pass
        # Let's change signal confidence to 80% to fail
        sample_signal.confidence_score = 80
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.CONFIDENCE_TOO_LOW
        assert "80%" in result.reason
        assert "85" in result.reason

    @pytest.mark.asyncio
    async def test_pattern_not_enabled_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when pattern not enabled."""
        sample_signal.pattern_type = "UTAD"  # Not in enabled_patterns
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.PATTERN_NOT_ENABLED
        assert "UTAD" in result.reason

    @pytest.mark.asyncio
    async def test_symbol_not_in_whitelist_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when symbol not in whitelist."""
        enabled_config.symbol_whitelist = ["TSLA", "NVDA"]  # AAPL not in list
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.SYMBOL_NOT_IN_WHITELIST
        assert "AAPL" in result.reason
        assert "whitelist" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_symbol_in_blacklist_bypasses(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test signal is bypassed when symbol in blacklist."""
        enabled_config.symbol_blacklist = ["AAPL", "MEME"]
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.SYMBOL_BLACKLISTED
        assert "AAPL" in result.reason
        assert "blacklist" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_daily_trade_limit_reached_bypasses(
        self, engine, mock_config_repo, mock_daily_counters, enabled_config, sample_signal
    ):
        """Test signal is bypassed when daily trade limit reached."""
        mock_config_repo.get_config.return_value = enabled_config
        mock_daily_counters.get_trades_today.return_value = 10  # At limit

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.DAILY_TRADE_LIMIT
        assert "10/10" in result.reason

    @pytest.mark.asyncio
    async def test_daily_risk_limit_exceeded_bypasses(
        self, engine, mock_config_repo, mock_daily_counters, enabled_config, sample_signal
    ):
        """Test signal is bypassed when daily risk limit would be exceeded."""
        mock_config_repo.get_config.return_value = enabled_config
        mock_daily_counters.get_risk_today.return_value = Decimal("4.5")  # 4.5% + 1.5% > 5%

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is False
        assert result.route_to_queue is True
        assert result.bypass_reason == AutoExecutionBypassReason.DAILY_RISK_LIMIT
        assert "4.5" in result.reason
        assert "5" in result.reason

    @pytest.mark.asyncio
    async def test_no_risk_limit_configured_passes(
        self, engine, mock_config_repo, mock_daily_counters, enabled_config, sample_signal
    ):
        """Test signal passes when no risk limit is configured."""
        enabled_config.max_risk_per_day = None
        mock_config_repo.get_config.return_value = enabled_config
        mock_daily_counters.get_risk_today.return_value = Decimal(
            "100.0"
        )  # Would fail if limit existed

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is True

    @pytest.mark.asyncio
    async def test_no_whitelist_allows_all_symbols(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test all symbols are allowed when whitelist is None."""
        enabled_config.symbol_whitelist = None
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.evaluate_signal(enabled_config.user_id, sample_signal)

        assert result.auto_execute is True


class TestAutoExecutionExecution:
    """Tests for signal execution logic."""

    @pytest.mark.asyncio
    async def test_successful_execution(
        self,
        engine,
        mock_config_repo,
        mock_daily_counters,
        mock_paper_trading,
        enabled_config,
        sample_signal,
    ):
        """Test successful signal execution."""
        mock_config_repo.get_config.return_value = enabled_config

        result = await engine.execute_signal(enabled_config.user_id, sample_signal)

        assert result.success is True
        assert result.position_id is not None
        assert result.entry_price == Decimal("150.00")
        assert result.executed_at is not None
        assert result.error is None

        # Verify counters were updated
        mock_daily_counters.increment_trades.assert_called_once_with(enabled_config.user_id)
        mock_daily_counters.add_risk.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_updates_counters(
        self, engine, mock_config_repo, mock_daily_counters, enabled_config, sample_signal
    ):
        """Test that execution updates daily counters."""
        mock_config_repo.get_config.return_value = enabled_config

        await engine.execute_signal(enabled_config.user_id, sample_signal)

        mock_daily_counters.increment_trades.assert_called_once_with(enabled_config.user_id)
        mock_daily_counters.add_risk.assert_called_once()
        # Check that risk was added with the extracted percentage
        call_args = mock_daily_counters.add_risk.call_args
        assert call_args[0][0] == enabled_config.user_id
        assert call_args[0][1] == Decimal("1.5")  # From validation metadata

    @pytest.mark.asyncio
    async def test_execution_sends_notification(
        self, engine, mock_config_repo, mock_notification_service, enabled_config, sample_signal
    ):
        """Test that execution sends notification."""
        mock_config_repo.get_config.return_value = enabled_config

        await engine.execute_signal(enabled_config.user_id, sample_signal)

        mock_notification_service.notify_signal_approved.assert_called_once_with(sample_signal)

    @pytest.mark.asyncio
    async def test_execution_failure_returns_error(
        self, engine, mock_config_repo, mock_paper_trading, enabled_config, sample_signal
    ):
        """Test execution failure returns error result."""
        mock_config_repo.get_config.return_value = enabled_config
        mock_paper_trading.execute_signal.side_effect = Exception("Execution failed")

        result = await engine.execute_signal(enabled_config.user_id, sample_signal)

        assert result.success is False
        assert "Execution failed" in result.error

    @pytest.mark.asyncio
    async def test_execution_without_paper_trading_service(
        self, mock_config_repo, mock_daily_counters, enabled_config, sample_signal
    ):
        """Test execution fails gracefully without paper trading service."""
        engine = AutoExecutionEngine(
            config_repository=mock_config_repo,
            daily_counters=mock_daily_counters,
            paper_trading_service=None,  # No paper trading service
        )

        result = await engine.execute_signal(enabled_config.user_id, sample_signal)

        assert result.success is False
        assert "not available" in result.error.lower()


class TestEvaluateAndExecute:
    """Tests for combined evaluate and execute flow."""

    @pytest.mark.asyncio
    async def test_evaluate_and_execute_success(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test combined evaluate and execute succeeds."""
        mock_config_repo.get_config.return_value = enabled_config

        eval_result, exec_result = await engine.evaluate_and_execute(
            enabled_config.user_id, sample_signal
        )

        assert eval_result.auto_execute is True
        assert exec_result is not None
        assert exec_result.success is True

    @pytest.mark.asyncio
    async def test_evaluate_and_execute_bypass(
        self, engine, mock_config_repo, enabled_config, sample_signal
    ):
        """Test combined evaluate and execute bypasses when evaluation fails."""
        enabled_config.enabled = False
        mock_config_repo.get_config.return_value = enabled_config

        eval_result, exec_result = await engine.evaluate_and_execute(
            enabled_config.user_id, sample_signal
        )

        assert eval_result.auto_execute is False
        assert exec_result is None  # No execution attempted


class TestRuleCheckMethods:
    """Tests for individual rule check methods."""

    def test_check_enabled_passes(self, engine, enabled_config):
        """Test enabled check passes when enabled."""
        result = engine._check_enabled(enabled_config)
        assert result.passed is True

    def test_check_enabled_fails(self, engine, enabled_config):
        """Test enabled check fails when disabled."""
        enabled_config.enabled = False
        result = engine._check_enabled(enabled_config)
        assert result.passed is False
        assert "disabled" in result.reason.lower()

    def test_check_kill_switch_passes(self, engine, enabled_config):
        """Test kill switch check passes when inactive."""
        result = engine._check_kill_switch(enabled_config)
        assert result.passed is True

    def test_check_kill_switch_fails(self, engine, enabled_config):
        """Test kill switch check fails when active."""
        enabled_config.kill_switch_active = True
        result = engine._check_kill_switch(enabled_config)
        assert result.passed is False
        assert "kill switch" in result.reason.lower()

    def test_check_confidence_passes(self, engine, enabled_config, sample_signal):
        """Test confidence check passes when above threshold."""
        result = engine._check_confidence(enabled_config, sample_signal)
        assert result.passed is True

    def test_check_confidence_fails(self, engine, enabled_config, sample_signal):
        """Test confidence check fails when below threshold."""
        sample_signal.confidence_score = 70  # Below 85% threshold
        result = engine._check_confidence(enabled_config, sample_signal)
        assert result.passed is False
        assert "70" in result.reason
        assert "85" in result.reason

    def test_check_pattern_passes(self, engine, enabled_config, sample_signal):
        """Test pattern check passes when pattern is enabled."""
        result = engine._check_pattern(enabled_config, sample_signal)
        assert result.passed is True

    def test_check_pattern_fails(self, engine, enabled_config, sample_signal):
        """Test pattern check fails when pattern not enabled."""
        sample_signal.pattern_type = "UTAD"
        result = engine._check_pattern(enabled_config, sample_signal)
        assert result.passed is False
        assert "UTAD" in result.reason

    def test_check_whitelist_passes_no_whitelist(self, engine, enabled_config, sample_signal):
        """Test whitelist check passes when no whitelist configured."""
        enabled_config.symbol_whitelist = None
        result = engine._check_symbol_whitelist(enabled_config, sample_signal)
        assert result.passed is True

    def test_check_whitelist_passes_symbol_in_list(self, engine, enabled_config, sample_signal):
        """Test whitelist check passes when symbol in whitelist."""
        enabled_config.symbol_whitelist = ["AAPL", "TSLA"]
        result = engine._check_symbol_whitelist(enabled_config, sample_signal)
        assert result.passed is True

    def test_check_whitelist_fails(self, engine, enabled_config, sample_signal):
        """Test whitelist check fails when symbol not in whitelist."""
        enabled_config.symbol_whitelist = ["TSLA", "NVDA"]
        result = engine._check_symbol_whitelist(enabled_config, sample_signal)
        assert result.passed is False
        assert "AAPL" in result.reason

    def test_check_blacklist_passes_no_blacklist(self, engine, enabled_config, sample_signal):
        """Test blacklist check passes when no blacklist configured."""
        enabled_config.symbol_blacklist = None
        result = engine._check_symbol_blacklist(enabled_config, sample_signal)
        assert result.passed is True

    def test_check_blacklist_passes_symbol_not_in_list(self, engine, enabled_config, sample_signal):
        """Test blacklist check passes when symbol not in blacklist."""
        enabled_config.symbol_blacklist = ["MEME", "GME"]
        result = engine._check_symbol_blacklist(enabled_config, sample_signal)
        assert result.passed is True

    def test_check_blacklist_fails(self, engine, enabled_config, sample_signal):
        """Test blacklist check fails when symbol in blacklist."""
        enabled_config.symbol_blacklist = ["AAPL"]
        result = engine._check_symbol_blacklist(enabled_config, sample_signal)
        assert result.passed is False
        assert "AAPL" in result.reason
        assert "blacklist" in result.reason.lower()


class TestDailyStatusRetrieval:
    """Tests for daily status retrieval."""

    @pytest.mark.asyncio
    async def test_get_daily_status(
        self, engine, mock_config_repo, mock_daily_counters, enabled_config
    ):
        """Test retrieving daily execution status."""
        mock_config_repo.get_config.return_value = enabled_config
        mock_daily_counters.get_snapshot.return_value = MagicMock(
            trades_today=3,
            risk_today=Decimal("2.5"),
            date="2026-01-26",
        )

        status = await engine.get_daily_status(enabled_config.user_id)

        assert status["trades_today"] == 3
        assert status["risk_today"] == 2.5
        assert status["max_trades_per_day"] == 10
        assert status["max_risk_per_day"] == 5.0
        assert status["date"] == "2026-01-26"


class TestRiskExtractionFromSignal:
    """Tests for extracting risk percentage from signals."""

    def test_extract_risk_from_validation_chain(self, engine, sample_signal):
        """Test risk is extracted from validation chain metadata."""
        risk = engine._extract_risk_percentage(sample_signal)
        assert risk == Decimal("1.5")

    def test_extract_risk_default_when_not_found(self, engine, sample_signal):
        """Test default risk is used when not found in validation chain."""
        # Remove risk metadata
        sample_signal.validation_chain.validation_results = [
            StageValidationResult(
                stage="Volume",
                status=ValidationStatus.PASS,
                validator_id="VolumeValidator",
                metadata={},
            )
        ]

        risk = engine._extract_risk_percentage(sample_signal)
        assert risk == Decimal("1.5")  # Default fallback
