"""
Email Notification Client

Handles email delivery via SMTP with:
- Async SMTP using aiosmtplib
- HTML email templates (Jinja2)
- Plain text fallback
- Retry logic and circuit breaker
- Test mode

Story: 11.6 - Notification & Alert System
"""

import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models.notification import Notification, NotificationType

logger = structlog.get_logger(__name__)


class EmailClient:
    """
    Async email client for notification delivery.

    Uses aiosmtplib for async SMTP and Jinja2 for templating.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        test_mode: bool = False,
    ):
        """
        Initialize email client.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (587 for TLS)
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_email: Sender email address
            test_mode: If True, log instead of sending
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.test_mode = test_mode

        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        if not test_mode and not all([smtp_host, smtp_user, smtp_password, from_email]):
            logger.warning(
                "SMTP credentials not configured, running in test mode",
                test_mode=True,
            )
            self.test_mode = True

    async def send_notification_email(
        self,
        to_address: str,
        notification: Notification,
    ) -> bool:
        """
        Send notification email with HTML template.

        Args:
            to_address: Recipient email address
            notification: Notification to send

        Returns:
            True if sent successfully, False otherwise
        """
        # Generate subject
        subject = self._get_subject(notification)

        # Render HTML and text bodies
        html_body = self._render_html_template(notification)
        text_body = self._render_text_template(notification)

        return await self.send_email(
            to_address=to_address,
            subject=subject,
            body_html=html_body,
            body_text=text_body,
        )

    async def send_email(
        self,
        to_address: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> bool:
        """
        Send email with HTML and plain text versions.

        Args:
            to_address: Recipient email address
            subject: Email subject
            body_html: HTML body
            body_text: Plain text body

        Returns:
            True if sent successfully, False otherwise
        """
        if self.test_mode:
            logger.info(
                "TEST MODE: Email would be sent",
                to=self._mask_email(to_address),
                subject=subject,
            )
            return True

        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = to_address

        # Attach plain text and HTML versions
        part_text = MIMEText(body_text, "plain")
        part_html = MIMEText(body_html, "html")

        message.attach(part_text)
        message.attach(part_html)

        # Send with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                import aiosmtplib

                await aiosmtplib.send(
                    message,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    start_tls=True,
                )

                logger.info(
                    "Email sent successfully",
                    to=self._mask_email(to_address),
                    subject=subject,
                    attempt=attempt + 1,
                )

                return True

            except Exception as e:
                logger.error(
                    "Failed to send email",
                    to=self._mask_email(to_address),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )

                # Retry with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    return False

        return False

    async def send_test_email(self, to_address: str) -> bool:
        """
        Send test email for user verification.

        Args:
            to_address: Recipient email address

        Returns:
            True if sent successfully
        """
        subject = "BMAD Wyckoff: Test Notification"

        html_body = """
        <html>
        <body>
            <h2>Email Notifications Configured</h2>
            <p>This is a test notification from the BMAD Wyckoff trading system.</p>
            <p>Your email alerts are configured correctly.</p>
        </body>
        </html>
        """

        text_body = (
            "Email Notifications Configured\n\n"
            "This is a test notification from the BMAD Wyckoff trading system.\n"
            "Your email alerts are configured correctly."
        )

        return await self.send_email(
            to_address=to_address,
            subject=subject,
            body_html=html_body,
            body_text=text_body,
        )

    def _get_subject(self, notification: Notification) -> str:
        """Generate email subject based on notification type."""
        if notification.notification_type == NotificationType.SIGNAL_GENERATED:
            symbol = notification.metadata.get("symbol", "")
            return f"New Signal: {symbol}"
        elif notification.notification_type == NotificationType.RISK_WARNING:
            return "Risk Warning Alert"
        elif notification.notification_type == NotificationType.EMERGENCY_EXIT:
            return "URGENT: Emergency Exit Triggered"
        elif notification.notification_type == NotificationType.SYSTEM_ERROR:
            return "System Error Notification"
        else:
            return "BMAD Wyckoff Notification"

    def _render_html_template(self, notification: Notification) -> str:
        """
        Render HTML email template.

        Args:
            notification: Notification to render

        Returns:
            Rendered HTML string
        """
        # Try to load type-specific template
        template_name = f"{notification.notification_type.value}.html"

        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(notification=notification)
        except Exception:
            # Fallback to generic template
            return self._render_generic_html(notification)

    def _render_generic_html(self, notification: Notification) -> str:
        """Render generic HTML email."""
        priority_color = {
            "info": "#4299e1",
            "warning": "#ed8936",
            "critical": "#f56565",
        }

        color = priority_color.get(notification.priority, "#4299e1")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .header {{ background-color: {color}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .metadata {{ background-color: #f7fafc; padding: 15px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{notification.title}</h2>
            </div>
            <div class="content">
                <p>{notification.message}</p>
                <div class="metadata">
                    <strong>Priority:</strong> {notification.priority.upper()}<br>
                    <strong>Type:</strong> {notification.notification_type.value.replace('_', ' ').title()}<br>
                    <strong>Time:</strong> {notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _render_text_template(self, notification: Notification) -> str:
        """Render plain text email version."""
        text = f"""
{notification.title}
{'=' * len(notification.title)}

{notification.message}

Priority: {notification.priority.upper()}
Type: {notification.notification_type.value.replace('_', ' ').title()}
Time: {notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

---
BMAD Wyckoff Trading System
        """

        return text.strip()

    def _mask_email(self, email: str) -> str:
        """Mask email for logging (PII protection)."""
        if "@" in email:
            user, domain = email.split("@")
            if len(user) > 3:
                masked_user = user[:2] + "***"
            else:
                masked_user = "***"
            return f"{masked_user}@{domain}"
        return "***"
