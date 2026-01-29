"""
Signal Email Notification Service (Story 19.25)

Handles email notifications for trading signals with:
- Confidence-based filtering (all vs high-confidence only)
- Rate limiting (max 10 emails per hour)
- HTML email templates with signal details
- Unsubscribe link support

Dependencies:
- Signal notification flow (Story 19.7)
- Email client (Story 11.6)
- Rate limiter (Story 19.25)

Author: Story 19.25
"""

from __future__ import annotations

__all__ = [
    "SignalEmailService",
    "EmailSendResult",
]

from dataclasses import dataclass
from enum import Enum
from html import escape as html_escape
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import get_settings
from src.models.notification import (
    EmailNotificationSettings,
    SignalEmailData,
    SignalNotification,
)
from src.notifications.rate_limiter import EmailRateLimiter

if TYPE_CHECKING:
    from src.notifications.email_client import EmailClient

logger = structlog.get_logger(__name__)

# High-confidence grades that trigger notifications when filter is enabled
HIGH_CONFIDENCE_GRADES = {"A+", "A"}


class EmailSendStatus(str, Enum):
    """Status of email send attempt."""

    SUCCESS = "success"
    DISABLED = "disabled"
    FILTERED = "filtered"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"


@dataclass
class EmailSendResult:
    """Result of an email send attempt."""

    status: EmailSendStatus
    user_id: UUID
    signal_id: UUID
    message: str


class SignalEmailService:
    """
    Service for sending signal notification emails (Story 19.25).

    Handles the complete email notification flow:
    1. Check if email notifications are enabled
    2. Apply confidence filtering (all signals vs high-confidence only)
    3. Check rate limits
    4. Build and send email with signal details

    Attributes:
        email_client: Email client for SMTP delivery
        rate_limiter: Rate limiter for spam prevention
        settings: Application settings
        jinja_env: Jinja2 template environment

    Example:
        >>> service = SignalEmailService(email_client)
        >>> result = await service.send_signal_notification(user_id, signal, prefs)
        >>> if result.status == EmailSendStatus.SUCCESS:
        ...     print("Email sent successfully")
    """

    def __init__(
        self,
        email_client: EmailClient,
        rate_limiter: Optional[EmailRateLimiter] = None,
    ):
        """
        Initialize SignalEmailService.

        Args:
            email_client: Email client for sending emails
            rate_limiter: Optional rate limiter (creates default if not provided)
        """
        self.email_client = email_client
        self.settings = get_settings()
        self.rate_limiter = rate_limiter or EmailRateLimiter(
            max_per_hour=self.settings.email_rate_limit_per_hour
        )

        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent.parent / "notifications" / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def send_signal_notification(
        self,
        user_id: UUID,
        signal: SignalNotification,
        preferences: EmailNotificationSettings,
    ) -> EmailSendResult:
        """
        Send email notification for an approved signal.

        Applies filtering, rate limiting, and delivers email.

        Args:
            user_id: User to notify
            signal: Approved signal notification
            preferences: User's email notification preferences

        Returns:
            EmailSendResult with status and details
        """
        # Check if email notifications are enabled
        if not preferences.email_enabled:
            logger.debug(
                "signal_email_skipped_disabled",
                user_id=str(user_id),
                signal_id=str(signal.signal_id),
            )
            return EmailSendResult(
                status=EmailSendStatus.DISABLED,
                user_id=user_id,
                signal_id=signal.signal_id,
                message="Email notifications disabled",
            )

        # Check confidence filter
        if not preferences.notify_all_signals:
            if signal.confidence_grade not in HIGH_CONFIDENCE_GRADES:
                logger.debug(
                    "signal_email_skipped_confidence",
                    user_id=str(user_id),
                    signal_id=str(signal.signal_id),
                    confidence_grade=signal.confidence_grade,
                )
                return EmailSendResult(
                    status=EmailSendStatus.FILTERED,
                    user_id=user_id,
                    signal_id=signal.signal_id,
                    message=f"Signal confidence {signal.confidence_grade} below threshold (A+/A only)",
                )

        # Check rate limit
        if not self.rate_limiter.can_send(user_id):
            logger.warning(
                "signal_email_rate_limited",
                user_id=str(user_id),
                signal_id=str(signal.signal_id),
            )
            return EmailSendResult(
                status=EmailSendStatus.RATE_LIMITED,
                user_id=user_id,
                signal_id=signal.signal_id,
                message="Email rate limit exceeded (10/hour)",
            )

        # Get email address
        email_address = preferences.email_address
        if not email_address:
            logger.warning(
                "signal_email_no_address",
                user_id=str(user_id),
                signal_id=str(signal.signal_id),
            )
            return EmailSendResult(
                status=EmailSendStatus.FAILED,
                user_id=user_id,
                signal_id=signal.signal_id,
                message="No email address configured",
            )

        # Build email data
        email_data = self._build_email_data(signal)

        # Render email content
        subject = f"🔔 New {signal.pattern_type} Signal: {signal.symbol}"
        html_body = self._render_html_template(email_data)
        text_body = self._render_text_template(email_data)

        # Send email
        try:
            success = await self.email_client.send_email(
                to_address=email_address,
                subject=subject,
                body_html=html_body,
                body_text=text_body,
            )

            if success:
                # Record send for rate limiting
                self.rate_limiter.record_send(user_id)

                logger.info(
                    "signal_email_sent",
                    user_id=str(user_id),
                    signal_id=str(signal.signal_id),
                    symbol=signal.symbol,
                    pattern_type=signal.pattern_type,
                )

                return EmailSendResult(
                    status=EmailSendStatus.SUCCESS,
                    user_id=user_id,
                    signal_id=signal.signal_id,
                    message="Email sent successfully",
                )
            else:
                return EmailSendResult(
                    status=EmailSendStatus.FAILED,
                    user_id=user_id,
                    signal_id=signal.signal_id,
                    message="Email delivery failed",
                )

        except Exception as e:
            logger.error(
                "signal_email_error",
                user_id=str(user_id),
                signal_id=str(signal.signal_id),
                error=str(e),
                exc_info=True,
            )
            return EmailSendResult(
                status=EmailSendStatus.FAILED,
                user_id=user_id,
                signal_id=signal.signal_id,
                message=f"Email error: {str(e)}",
            )

    def _build_email_data(self, signal: SignalNotification) -> SignalEmailData:
        """
        Build email data structure from signal notification.

        Args:
            signal: Signal notification

        Returns:
            SignalEmailData for template rendering
        """
        base_url = self.settings.app_base_url

        return SignalEmailData(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            pattern_type=signal.pattern_type,
            confidence_score=signal.confidence_score,
            confidence_grade=signal.confidence_grade,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            risk_amount=signal.risk_amount,
            r_multiple=signal.r_multiple,
            approve_url=f"{base_url}/signals/{signal.signal_id}/approve",
            unsubscribe_url=f"{base_url}/settings/notifications",
        )

    def _render_html_template(self, data: SignalEmailData) -> str:
        """
        Render HTML email template.

        Falls back to inline template if file not found.

        Args:
            data: Email data for template context

        Returns:
            Rendered HTML string
        """
        try:
            template = self.jinja_env.get_template("signal_alert.html")
            return template.render(signal=data)
        except Exception:
            # Fallback to inline template
            return self._render_inline_html(data)

    def _render_inline_html(self, data: SignalEmailData) -> str:
        """Render inline HTML email (fallback with XSS protection)."""
        # HTML escape user-facing text for defense-in-depth
        symbol = html_escape(str(data.symbol))
        pattern_type = html_escape(str(data.pattern_type))
        confidence_grade = html_escape(str(data.confidence_grade))
        entry_price = html_escape(str(data.entry_price))
        stop_loss = html_escape(str(data.stop_loss))
        target_price = html_escape(str(data.target_price))
        risk_amount = html_escape(str(data.risk_amount))
        approve_url = html_escape(str(data.approve_url))
        unsubscribe_url = html_escape(str(data.unsubscribe_url))
        confidence_class = (
            "confidence-high" if data.confidence_grade in ["A+", "A"] else "confidence-medium"
        )

        return f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    .container {{ max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }}
    .header {{ background: #1976D2; color: white; padding: 20px; text-align: center; }}
    .content {{ padding: 20px; }}
    .signal-card {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 15px 0; }}
    .metric {{ display: flex; justify-content: space-between; margin: 8px 0; padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
    .metric:last-child {{ border-bottom: none; }}
    .metric-label {{ color: #666; }}
    .metric-value {{ font-weight: bold; color: #333; }}
    .cta-button {{ background: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 15px; }}
    .footer {{ padding: 20px; font-size: 12px; color: #666; text-align: center; border-top: 1px solid #e0e0e0; margin-top: 20px; }}
    .confidence-badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
    .confidence-high {{ background: #4CAF50; color: white; }}
    .confidence-medium {{ background: #FF9800; color: white; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>New {pattern_type} Signal</h1>
      <h2>{symbol}</h2>
    </div>
    <div class="content">
      <div class="signal-card">
        <div class="metric">
          <span class="metric-label">Pattern:</span>
          <span class="metric-value">{pattern_type}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Confidence:</span>
          <span class="metric-value">
            <span class="confidence-badge {confidence_class}">
              {confidence_grade} ({data.confidence_score}%)
            </span>
          </span>
        </div>
        <div class="metric">
          <span class="metric-label">Entry Price:</span>
          <span class="metric-value">${entry_price}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Stop Loss:</span>
          <span class="metric-value">${stop_loss}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Target Price:</span>
          <span class="metric-value">${target_price}</span>
        </div>
        <div class="metric">
          <span class="metric-label">Risk Amount:</span>
          <span class="metric-value">${risk_amount}</span>
        </div>
        <div class="metric">
          <span class="metric-label">R-Multiple:</span>
          <span class="metric-value">{data.r_multiple:.2f}R</span>
        </div>
      </div>
      <p style="text-align: center;">
        <a href="{approve_url}" class="cta-button">View Signal</a>
      </p>
    </div>
    <div class="footer">
      <p>You received this because you enabled email notifications for trading signals.</p>
      <p><a href="{unsubscribe_url}">Manage notification preferences</a></p>
      <p>BMAD Wyckoff Trading System</p>
    </div>
  </div>
</body>
</html>
"""

    def _render_text_template(self, data: SignalEmailData) -> str:
        """Render plain text email version."""
        return f"""
🔔 New {data.pattern_type} Signal: {data.symbol}
{'=' * 50}

SIGNAL DETAILS
--------------
Pattern:      {data.pattern_type}
Confidence:   {data.confidence_grade} ({data.confidence_score}%)
Entry Price:  ${data.entry_price}
Stop Loss:    ${data.stop_loss}
Target Price: ${data.target_price}
Risk Amount:  ${data.risk_amount}
R-Multiple:   {data.r_multiple:.2f}R

View Signal: {data.approve_url}

---
You received this because you enabled email notifications.
Manage preferences: {data.unsubscribe_url}

BMAD Wyckoff Trading System
"""

    def get_rate_limit_remaining(self, user_id: UUID) -> int:
        """
        Get remaining email quota for user.

        Args:
            user_id: User identifier

        Returns:
            Number of emails remaining in current hour
        """
        return self.rate_limiter.get_remaining(user_id)
