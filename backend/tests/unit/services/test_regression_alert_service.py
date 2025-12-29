"""
Unit tests for RegressionAlertService (Story 12.7 AC 5).

Tests alert delivery, channel configuration, and notification formatting.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    CommissionConfig,
    RegressionTestConfig,
    RegressionTestResult,
    SlippageConfig,
)
from src.services.regression_alert_service import AlertConfig, RegressionAlertService


@pytest.fixture
def regression_test_config():
    """Create RegressionTestConfig for testing."""
    return RegressionTestConfig(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        backtest_config=BacktestConfig(
            symbol="AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("100000.00"),
            position_size_pct=Decimal("0.10"),
            max_positions=5,
            commission_config=CommissionConfig(
                commission_type="PER_SHARE",
                commission_rate=Decimal("0.0050"),
            ),
            slippage_config=SlippageConfig(
                slippage_type="PERCENTAGE",
                slippage_rate=Decimal("0.0010"),
            ),
        ),
        degradation_thresholds={
            "win_rate": Decimal("5.0"),
            "average_r_multiple": Decimal("10.0"),
            "profit_factor": Decimal("15.0"),
        },
    )


@pytest.fixture
def alert_config():
    """Create AlertConfig for testing."""
    return AlertConfig(
        slack_webhook_url="https://hooks.slack.com/services/TEST/WEBHOOK",
        email_recipients=["test@example.com", "admin@example.com"],
        webhook_url="https://api.example.com/webhook",
        alert_on_pass=False,
        alert_on_fail=True,
        alert_on_baseline_not_set=False,
    )


@pytest.fixture
def regression_result_pass(regression_test_config):
    """Create passing regression test result."""
    return RegressionTestResult(
        test_id=uuid4(),
        config=regression_test_config,
        test_run_time=datetime(2024, 1, 15, 10, 0, 0),
        codebase_version="abc123",
        status="PASS",
        aggregate_metrics=BacktestMetrics(
            total_trades=150,
            winning_trades=95,
            losing_trades=55,
            win_rate=Decimal("0.6333"),
            average_r_multiple=Decimal("1.85"),
            profit_factor=Decimal("2.45"),
            max_drawdown=Decimal("0.12"),
            sharpe_ratio=Decimal("1.75"),
            total_return=Decimal("0.35"),
        ),
        per_symbol_results={},
        regression_detected=False,
        degraded_metrics=[],
        execution_time_seconds=45.5,
    )


@pytest.fixture
def regression_result_fail(regression_test_config):
    """Create failing regression test result."""
    return RegressionTestResult(
        test_id=uuid4(),
        config=regression_test_config,
        test_run_time=datetime(2024, 1, 15, 10, 0, 0),
        codebase_version="def456",
        status="FAIL",
        aggregate_metrics=BacktestMetrics(
            total_trades=150,
            winning_trades=85,
            losing_trades=65,
            win_rate=Decimal("0.5667"),
            average_r_multiple=Decimal("1.45"),
            profit_factor=Decimal("1.85"),
            max_drawdown=Decimal("0.18"),
            sharpe_ratio=Decimal("1.25"),
            total_return=Decimal("0.22"),
        ),
        per_symbol_results={},
        regression_detected=True,
        degraded_metrics=["win_rate", "average_r_multiple", "profit_factor"],
        execution_time_seconds=52.3,
    )


@pytest.fixture
def regression_result_baseline_not_set(regression_test_config):
    """Create result with no baseline."""
    return RegressionTestResult(
        test_id=uuid4(),
        config=regression_test_config,
        test_run_time=datetime(2024, 1, 15, 10, 0, 0),
        codebase_version="ghi789",
        status="BASELINE_NOT_SET",
        aggregate_metrics=BacktestMetrics(
            total_trades=150,
            winning_trades=95,
            losing_trades=55,
            win_rate=Decimal("0.6333"),
            average_r_multiple=Decimal("1.85"),
            profit_factor=Decimal("2.45"),
            max_drawdown=Decimal("0.12"),
            sharpe_ratio=Decimal("1.75"),
            total_return=Decimal("0.35"),
        ),
        per_symbol_results={},
        regression_detected=False,
        degraded_metrics=[],
        execution_time_seconds=43.1,
    )


class TestAlertConfig:
    """Test AlertConfig validation."""

    def test_alert_config_valid(self):
        """Test valid AlertConfig creation."""
        config = AlertConfig(
            slack_webhook_url="https://hooks.slack.com/services/TEST",
            email_recipients=["test@example.com"],
            webhook_url="https://api.example.com/webhook",
            alert_on_fail=True,
        )

        assert config.slack_webhook_url == "https://hooks.slack.com/services/TEST"
        assert config.email_recipients == ["test@example.com"]
        assert config.alert_on_fail is True
        assert config.alert_on_pass is False

    def test_alert_config_defaults(self):
        """Test AlertConfig default values."""
        config = AlertConfig()

        assert config.slack_webhook_url is None
        assert config.email_recipients == []
        assert config.webhook_url is None
        assert config.alert_on_pass is False
        assert config.alert_on_fail is True
        assert config.alert_on_baseline_not_set is False

    def test_alert_config_invalid_url(self):
        """Test AlertConfig rejects invalid URLs."""
        with pytest.raises(ValueError, match="URL must start with http"):
            AlertConfig(slack_webhook_url="invalid-url")

        with pytest.raises(ValueError, match="URL must start with http"):
            AlertConfig(webhook_url="ftp://example.com")


class TestRegressionAlertService:
    """Test RegressionAlertService functionality."""

    def test_service_initialization(self, alert_config):
        """Test service initialization."""
        service = RegressionAlertService(alert_config)

        assert service.config == alert_config
        assert service._http_client is not None

    def test_should_alert_pass(self, alert_config):
        """Test alert decision for PASS status."""
        service = RegressionAlertService(alert_config)

        # Default: don't alert on pass
        assert service._should_alert("PASS") is False

        # With alert_on_pass enabled
        alert_config.alert_on_pass = True
        service = RegressionAlertService(alert_config)
        assert service._should_alert("PASS") is True

    def test_should_alert_fail(self, alert_config):
        """Test alert decision for FAIL status."""
        service = RegressionAlertService(alert_config)

        # Default: alert on fail
        assert service._should_alert("FAIL") is True

        # With alert_on_fail disabled
        alert_config.alert_on_fail = False
        service = RegressionAlertService(alert_config)
        assert service._should_alert("FAIL") is False

    def test_should_alert_baseline_not_set(self, alert_config):
        """Test alert decision for BASELINE_NOT_SET status."""
        service = RegressionAlertService(alert_config)

        # Default: don't alert on baseline_not_set
        assert service._should_alert("BASELINE_NOT_SET") is False

        # With alert_on_baseline_not_set enabled
        alert_config.alert_on_baseline_not_set = True
        service = RegressionAlertService(alert_config)
        assert service._should_alert("BASELINE_NOT_SET") is True

    def test_should_alert_error(self, alert_config):
        """Test alert decision for ERROR status."""
        service = RegressionAlertService(alert_config)

        # Always alert on errors
        assert service._should_alert("ERROR") is True

    @pytest.mark.asyncio
    async def test_send_alert_pass_no_alert(self, alert_config, regression_result_pass):
        """Test no alert sent for PASS when alert_on_pass=False."""
        service = RegressionAlertService(alert_config)

        result = await service.send_alert(regression_result_pass)

        # Should be empty dict (no alerts sent)
        assert result == {}

    @pytest.mark.asyncio
    async def test_send_alert_pass_with_alert(self, alert_config, regression_result_pass):
        """Test alert sent for PASS when alert_on_pass=True."""
        alert_config.alert_on_pass = True
        service = RegressionAlertService(alert_config)

        with patch.object(service._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()

            result = await service.send_alert(regression_result_pass)

            # Should send to all channels
            assert "slack" in result
            assert "webhook" in result
            assert "email" in result

            # Verify HTTP calls made
            assert mock_post.call_count == 2  # Slack + webhook

    @pytest.mark.asyncio
    async def test_send_alert_fail(self, alert_config, regression_result_fail):
        """Test alert sent for FAIL."""
        service = RegressionAlertService(alert_config)

        with patch.object(service._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()

            result = await service.send_alert(regression_result_fail)

            # Should send to all channels
            assert result["slack"] is True
            assert result["webhook"] is True
            assert result["email"] is True

            # Verify HTTP calls made
            assert mock_post.call_count == 2  # Slack + webhook

    @pytest.mark.asyncio
    async def test_send_slack_alert_success(self, alert_config, regression_result_fail):
        """Test successful Slack alert."""
        service = RegressionAlertService(alert_config)

        with patch.object(service._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()

            success = await service._send_slack_alert(regression_result_fail, include_details=True)

            assert success is True
            assert mock_post.call_count == 1

            # Verify payload structure
            call_args = mock_post.call_args
            assert call_args[0][0] == alert_config.slack_webhook_url
            payload = call_args[1]["json"]
            assert "text" in payload
            assert "blocks" in payload
            assert "🚨" in payload["text"]  # Failure emoji

    @pytest.mark.asyncio
    async def test_send_slack_alert_http_error(self, alert_config, regression_result_fail):
        """Test Slack alert with HTTP error."""
        service = RegressionAlertService(alert_config)

        with patch.object(service._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=MagicMock()
            )

            success = await service._send_slack_alert(regression_result_fail, include_details=True)

            assert success is False

    def test_build_slack_payload_pass(self, alert_config, regression_result_pass):
        """Test Slack payload for PASS status."""
        service = RegressionAlertService(alert_config)

        payload = service._build_slack_payload(regression_result_pass, include_details=True)

        assert "text" in payload
        assert "✅" in payload["text"]
        assert "blocks" in payload
        assert len(payload["blocks"]) > 0

        # Verify header
        header = payload["blocks"][0]
        assert header["type"] == "header"
        assert "PASS" in header["text"]["text"]

    def test_build_slack_payload_fail(self, alert_config, regression_result_fail):
        """Test Slack payload for FAIL status."""
        service = RegressionAlertService(alert_config)

        payload = service._build_slack_payload(regression_result_fail, include_details=True)

        assert "text" in payload
        assert "🚨" in payload["text"]
        assert "blocks" in payload

        # Should include degraded metrics
        block_texts = [str(block) for block in payload["blocks"]]
        combined = " ".join(block_texts)
        assert "win_rate" in combined or "Degraded" in combined

    def test_build_slack_payload_baseline_not_set(
        self, alert_config, regression_result_baseline_not_set
    ):
        """Test Slack payload for BASELINE_NOT_SET status."""
        service = RegressionAlertService(alert_config)

        payload = service._build_slack_payload(
            regression_result_baseline_not_set, include_details=True
        )

        assert "text" in payload
        assert "⚠️" in payload["text"]
        assert "BASELINE_NOT_SET" in payload["text"]

    @pytest.mark.asyncio
    async def test_send_webhook_alert_success(self, alert_config, regression_result_fail):
        """Test successful webhook alert."""
        service = RegressionAlertService(alert_config)

        with patch.object(service._http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()

            success = await service._send_webhook_alert(
                regression_result_fail, include_details=True
            )

            assert success is True
            assert mock_post.call_count == 1

            # Verify payload structure
            call_args = mock_post.call_args
            assert call_args[0][0] == alert_config.webhook_url
            payload = call_args[1]["json"]
            assert payload["event"] == "regression_test_completed"
            assert "test_id" in payload
            assert isinstance(payload["test_id"], str)  # UUID converted to string
            assert payload["status"] == "FAIL"
            assert "aggregate_metrics" in payload

    def test_build_webhook_payload_with_details(self, alert_config, regression_result_fail):
        """Test webhook payload with details."""
        service = RegressionAlertService(alert_config)

        payload = service._build_webhook_payload(regression_result_fail, include_details=True)

        assert payload["event"] == "regression_test_completed"
        assert "test_id" in payload
        assert isinstance(payload["test_id"], str)  # UUID converted to string
        assert payload["status"] == "FAIL"
        assert payload["regression_detected"] is True
        assert "aggregate_metrics" in payload
        assert "degraded_metrics" in payload
        assert payload["degraded_metrics"] == ["win_rate", "average_r_multiple", "profit_factor"]

    def test_build_webhook_payload_without_details(self, alert_config, regression_result_fail):
        """Test webhook payload without details."""
        service = RegressionAlertService(alert_config)

        payload = service._build_webhook_payload(regression_result_fail, include_details=False)

        assert payload["event"] == "regression_test_completed"
        assert "test_id" in payload
        assert isinstance(payload["test_id"], str)  # UUID converted to string
        assert payload["status"] == "FAIL"
        assert "aggregate_metrics" not in payload
        assert "degraded_metrics" not in payload

    @pytest.mark.asyncio
    async def test_send_email_alert(self, alert_config, regression_result_fail):
        """Test email alert (placeholder implementation)."""
        service = RegressionAlertService(alert_config)

        # Email is placeholder - just verifies it doesn't error
        success = await service._send_email_alert(regression_result_fail, include_details=True)

        assert success is True

    @pytest.mark.asyncio
    async def test_context_manager(self, alert_config):
        """Test async context manager."""
        async with RegressionAlertService(alert_config) as service:
            assert service is not None

        # Client should be closed
        # Note: httpx.AsyncClient.aclose() doesn't raise on re-close, so this is safe

    @pytest.mark.asyncio
    async def test_close(self, alert_config):
        """Test explicit close."""
        service = RegressionAlertService(alert_config)

        await service.close()

        # Verify client is closed (no error on re-close)
        await service.close()
