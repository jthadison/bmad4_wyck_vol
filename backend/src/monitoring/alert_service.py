"""
Alert Service - Story 23.13

Sends alerts to Slack webhooks with rate limiting.
Gracefully degrades when Slack URL is not configured.

Author: Story 23.13 Implementation
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import httpx
import structlog
from structlog.stdlib import BoundLogger

logger: BoundLogger = structlog.get_logger(__name__)

__all__ = [
    "AlertService",
]

# Supported event types
EVENT_SIGNAL_GENERATED = "SIGNAL_GENERATED"
EVENT_ORDER_PLACED = "ORDER_PLACED"
EVENT_RISK_LIMIT_APPROACH = "RISK_LIMIT_APPROACH"
EVENT_KILL_SWITCH_TRIGGERED = "KILL_SWITCH_TRIGGERED"
EVENT_PNL_THRESHOLD_BREACH = "PNL_THRESHOLD_BREACH"


class AlertService:
    """
    Sends operational alerts via Slack webhook with rate limiting.

    Gracefully handles missing Slack configuration by logging alerts
    locally instead of raising errors.

    Example:
        >>> service = AlertService(slack_webhook_url="https://hooks.slack.com/...")
        >>> await service.send_alert(
        ...     event_type="KILL_SWITCH_TRIGGERED",
        ...     message="Kill switch activated due to daily P&L breach",
        ...     severity="critical",
        ...     metadata={"pnl_pct": "-3.2"},
        ... )
    """

    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        rate_limit_seconds: int = 60,
    ) -> None:
        """
        Initialize alert service.

        Args:
            slack_webhook_url: Slack incoming webhook URL (None to disable Slack).
            rate_limit_seconds: Cooldown per event type in seconds.
        """
        self._slack_webhook_url = slack_webhook_url
        self._rate_limit_seconds = rate_limit_seconds
        self._last_alert_times: dict[str, datetime] = {}
        self._logger: BoundLogger = logger.bind(component="alert_service")

        if not slack_webhook_url:
            self._logger.info("slack_not_configured", detail="Alerts will be logged only")

    async def send_alert(
        self,
        event_type: str,
        message: str,
        severity: str = "info",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Send an alert, respecting rate limits.

        Args:
            event_type: Type of event (e.g. KILL_SWITCH_TRIGGERED).
            message: Human-readable alert message.
            severity: Alert severity (info, warning, critical).
            metadata: Additional context data.

        Returns:
            True if alert was sent (or logged), False if rate-limited.
        """
        if not self._should_send(event_type):
            return False

        self._last_alert_times[event_type] = datetime.now(UTC)

        self._logger.info(
            "alert_triggered",
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )

        if self._slack_webhook_url:
            await self._send_slack(event_type, message, severity, metadata or {})

        return True

    def _should_send(self, event_type: str) -> bool:
        """Check rate limit for event type."""
        now = datetime.now(UTC)
        last = self._last_alert_times.get(event_type)
        if last and (now - last) < timedelta(seconds=self._rate_limit_seconds):
            remaining = (last + timedelta(seconds=self._rate_limit_seconds) - now).total_seconds()
            self._logger.debug(
                "alert_rate_limited",
                event_type=event_type,
                remaining_seconds=round(remaining),
            )
            return False
        return True

    async def _send_slack(
        self,
        event_type: str,
        message: str,
        severity: str,
        metadata: dict[str, Any],
    ) -> None:
        """Post alert to Slack webhook."""
        icon = _severity_icon(severity)
        meta_text = "\n".join(f"  {k}: {v}" for k, v in metadata.items()) if metadata else ""
        payload = {
            "text": (f"{icon} *[{severity.upper()}] {event_type}*\n" f"{message}\n" f"{meta_text}"),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._slack_webhook_url, json=payload)  # type: ignore[arg-type]
                if resp.status_code != 200:
                    self._logger.warning(
                        "slack_webhook_error",
                        status_code=resp.status_code,
                        response=resp.text[:200],
                    )
        except httpx.HTTPError as exc:
            self._logger.warning("slack_webhook_failed", error=str(exc))


def _severity_icon(severity: str) -> str:
    """Map severity to Slack emoji."""
    return {
        "critical": ":rotating_light:",
        "warning": ":warning:",
        "info": ":information_source:",
    }.get(severity.lower(), ":bell:")
