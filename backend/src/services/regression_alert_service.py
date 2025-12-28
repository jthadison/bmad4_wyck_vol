#!/usr/bin/env python3
"""
Regression Alert Service (Story 12.7 Task 18 - AC 5).

Provides alert and notification capabilities for regression test failures.
Supports multiple alert channels: Slack, email, and webhook notifications.

Author: Story 12.7 AC 5
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field, field_validator

from src.models.backtest import RegressionTestResult

logger = logging.getLogger(__name__)


class AlertConfig(BaseModel):
    """Configuration for alert channels.

    Attributes:
        slack_webhook_url: Slack incoming webhook URL
        email_recipients: List of email addresses for alerts
        webhook_url: Custom webhook URL for notifications
        alert_on_pass: Whether to send alerts for passing tests (default: False)
        alert_on_fail: Whether to send alerts for failing tests (default: True)
        alert_on_baseline_not_set: Whether to alert when baseline not set (default: False)
    """

    slack_webhook_url: Optional[str] = None
    email_recipients: list[str] = Field(default_factory=list)
    webhook_url: Optional[str] = None
    alert_on_pass: bool = False
    alert_on_fail: bool = True
    alert_on_baseline_not_set: bool = False

    @field_validator("slack_webhook_url", "webhook_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class RegressionAlertService:
    """Service for sending alerts on regression test results.

    Handles multi-channel notification delivery with retry logic and error handling.

    Example:
        >>> config = AlertConfig(
        ...     slack_webhook_url="https://hooks.slack.com/services/...",
        ...     alert_on_fail=True
        ... )
        >>> service = RegressionAlertService(config)
        >>> await service.send_alert(regression_result)
    """

    def __init__(self, config: AlertConfig):
        """Initialize alert service with configuration.

        Args:
            config: AlertConfig with channel settings
        """
        self.config = config
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def send_alert(
        self,
        result: RegressionTestResult,
        include_details: bool = True,
    ) -> dict[str, bool]:
        """Send alerts for regression test result across all configured channels.

        Args:
            result: Regression test result to alert on
            include_details: Include detailed metrics in alert (default: True)

        Returns:
            Dictionary mapping channel names to success status

        Example:
            >>> status = await service.send_alert(result)
            >>> if status["slack"]:
            ...     print("Slack notification sent")
        """
        # Check if we should alert based on status
        if not self._should_alert(result.status):
            logger.info(f"Skipping alert for status: {result.status}")
            return {}

        results = {}

        # Send to all configured channels
        if self.config.slack_webhook_url:
            results["slack"] = await self._send_slack_alert(result, include_details)

        if self.config.email_recipients:
            results["email"] = await self._send_email_alert(result, include_details)

        if self.config.webhook_url:
            results["webhook"] = await self._send_webhook_alert(result, include_details)

        return results

    def _should_alert(self, status: str) -> bool:
        """Determine if alert should be sent based on test status and config.

        Args:
            status: Test status (PASS, FAIL, BASELINE_NOT_SET, ERROR)

        Returns:
            True if alert should be sent
        """
        if status == "PASS":
            return self.config.alert_on_pass
        elif status == "FAIL":
            return self.config.alert_on_fail
        elif status == "BASELINE_NOT_SET":
            return self.config.alert_on_baseline_not_set
        else:  # ERROR or unknown status
            return True  # Always alert on errors

    async def _send_slack_alert(
        self,
        result: RegressionTestResult,
        include_details: bool,
    ) -> bool:
        """Send Slack notification using webhook.

        Args:
            result: Regression test result
            include_details: Include detailed metrics

        Returns:
            True if notification sent successfully
        """
        if not self.config.slack_webhook_url:
            return False

        try:
            payload = self._build_slack_payload(result, include_details)
            response = await self._http_client.post(
                self.config.slack_webhook_url,
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Slack alert sent for test {result.test_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _build_slack_payload(
        self,
        result: RegressionTestResult,
        include_details: bool,
    ) -> dict:
        """Build Slack Block Kit payload.

        Args:
            result: Regression test result
            include_details: Include detailed metrics

        Returns:
            Slack webhook payload
        """
        # Determine emoji and color based on status
        if result.status == "PASS":
            emoji = "✅"
            color = "#36a64f"
        elif result.status == "FAIL":
            emoji = "🚨"
            color = "#d32f2f"
        elif result.status == "BASELINE_NOT_SET":
            emoji = "⚠️"
            color = "#ffa726"
        else:
            emoji = "❌"
            color = "#d32f2f"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Regression Test {result.status}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Test ID:*\n`{result.test_id}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Version:*\n`{result.codebase_version}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{emoji} {result.status}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Timestamp:*\n{result.test_run_time.strftime('%Y-%m-%d %H:%M UTC')}",
                    },
                ],
            },
        ]

        # Add metrics for PASS and FAIL
        if include_details and result.status in ["PASS", "FAIL"]:
            metrics = result.aggregate_metrics
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Aggregate Metrics:*\n"
                            f"• Total Trades: {metrics.total_trades}\n"
                            f"• Win Rate: {float(metrics.win_rate)*100:.2f}%\n"
                            f"• Avg R-Multiple: {float(metrics.average_r_multiple):.2f}\n"
                            f"• Profit Factor: {float(metrics.profit_factor):.2f}\n"
                            f"• Max Drawdown: {float(metrics.max_drawdown)*100:.2f}%\n"
                            f"• Sharpe Ratio: {float(metrics.sharpe_ratio or 0):.2f}"
                        ),
                    },
                }
            )

        # Add degraded metrics for FAIL
        if result.status == "FAIL" and result.degraded_metrics:
            degraded_text = "\n".join([f"• {metric}" for metric in result.degraded_metrics])
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*⚠️ Degraded Metrics:*\n{degraded_text}",
                    },
                }
            )

        blocks.append({"type": "divider"})

        # Add context
        context_msg = {
            "PASS": "Monthly regression test completed successfully with no performance degradation.",
            "FAIL": "Performance regression detected beyond acceptable thresholds. Investigation required.",
            "BASELINE_NOT_SET": "No baseline exists. Establish a baseline to enable regression detection.",
            "ERROR": "Test execution encountered an error.",
        }

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": context_msg.get(result.status, "Regression test completed."),
                    }
                ],
            }
        )

        return {
            "text": f"{emoji} Regression Test {result.status}",
            "blocks": blocks,
            "attachments": [{"color": color}],
        }

    async def _send_email_alert(
        self,
        result: RegressionTestResult,
        include_details: bool,
    ) -> bool:
        """Send email notification.

        Note: Email functionality requires SMTP configuration. This is a placeholder
        implementation that logs the action. Integrate with your email service.

        Args:
            result: Regression test result
            include_details: Include detailed metrics

        Returns:
            True if notification sent successfully
        """
        try:
            # TODO: Integrate with actual email service (e.g., SendGrid, AWS SES)
            # For now, just log
            logger.info(
                f"Email alert triggered for test {result.test_id} "
                f"to {len(self.config.email_recipients)} recipients"
            )
            logger.info(f"Status: {result.status}")

            # In production, you would:
            # 1. Build HTML email body with result details
            # 2. Use SMTP client or email service API
            # 3. Send to all recipients
            # 4. Handle bounces and errors

            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    async def _send_webhook_alert(
        self,
        result: RegressionTestResult,
        include_details: bool,
    ) -> bool:
        """Send webhook notification with JSON payload.

        Args:
            result: Regression test result
            include_details: Include detailed metrics

        Returns:
            True if notification sent successfully
        """
        if not self.config.webhook_url:
            return False

        try:
            payload = self._build_webhook_payload(result, include_details)
            response = await self._http_client.post(
                self.config.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.info(f"Webhook alert sent for test {result.test_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False

    def _build_webhook_payload(
        self,
        result: RegressionTestResult,
        include_details: bool,
    ) -> dict:
        """Build webhook JSON payload.

        Args:
            result: Regression test result
            include_details: Include detailed metrics

        Returns:
            Webhook payload dictionary
        """
        payload = {
            "event": "regression_test_completed",
            "test_id": str(result.test_id),
            "status": result.status,
            "timestamp": result.test_run_time.isoformat(),
            "codebase_version": result.codebase_version,
            "regression_detected": result.regression_detected,
        }

        if include_details:
            payload["aggregate_metrics"] = result.aggregate_metrics.model_dump(mode="json")

            if result.degraded_metrics:
                payload["degraded_metrics"] = result.degraded_metrics

            if result.baseline_comparison:
                payload["baseline_comparison"] = result.baseline_comparison.model_dump(mode="json")

        return payload

    async def close(self):
        """Close HTTP client connection."""
        await self._http_client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
