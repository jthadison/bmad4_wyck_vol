"""
Unit tests for AlertService - Story 23.13
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.monitoring.alert_service import (
    EVENT_KILL_SWITCH_TRIGGERED,
    EVENT_ORDER_PLACED,
    EVENT_PNL_THRESHOLD_BREACH,
    EVENT_RISK_LIMIT_APPROACH,
    EVENT_SIGNAL_GENERATED,
    AlertService,
)


@pytest.fixture
def service() -> AlertService:
    return AlertService(
        slack_webhook_url="https://hooks.slack.com/test",
        rate_limit_seconds=60,
    )


@pytest.fixture
def service_no_slack() -> AlertService:
    return AlertService(slack_webhook_url=None, rate_limit_seconds=60)


@pytest.mark.asyncio
async def test_send_alert_posts_to_slack(service: AlertService) -> None:
    """Alert sends POST to Slack webhook."""
    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await service.send_alert(
            event_type=EVENT_KILL_SWITCH_TRIGGERED,
            message="Kill switch activated",
            severity="critical",
            metadata={"reason": "pnl_breach"},
        )

    assert result is True
    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://hooks.slack.com/test"
    payload = call_args[1]["json"]
    assert "KILL_SWITCH_TRIGGERED" in payload["text"]
    assert "Kill switch activated" in payload["text"]


@pytest.mark.asyncio
async def test_rate_limiting(service: AlertService) -> None:
    """Second alert within cooldown is rate-limited."""
    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        first = await service.send_alert(
            event_type=EVENT_PNL_THRESHOLD_BREACH,
            message="Threshold breached",
            severity="critical",
        )
        second = await service.send_alert(
            event_type=EVENT_PNL_THRESHOLD_BREACH,
            message="Threshold breached again",
            severity="critical",
        )

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_different_event_types_not_rate_limited(service: AlertService) -> None:
    """Different event types have independent rate limits."""
    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        r1 = await service.send_alert(
            event_type=EVENT_PNL_THRESHOLD_BREACH,
            message="PNL breach",
            severity="critical",
        )
        r2 = await service.send_alert(
            event_type=EVENT_KILL_SWITCH_TRIGGERED,
            message="Kill switch",
            severity="critical",
        )

    assert r1 is True
    assert r2 is True


@pytest.mark.asyncio
async def test_rate_limit_expires(service: AlertService) -> None:
    """Alert allowed after rate limit expires."""
    # Manually set last alert time in the past
    past = datetime.now(UTC) - timedelta(seconds=120)
    service._last_alert_times[EVENT_SIGNAL_GENERATED] = past

    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await service.send_alert(
            event_type=EVENT_SIGNAL_GENERATED,
            message="New signal",
            severity="info",
        )

    assert result is True


@pytest.mark.asyncio
async def test_graceful_without_slack_url(service_no_slack: AlertService) -> None:
    """Without Slack URL, alert is logged but no HTTP call made."""
    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        result = await service_no_slack.send_alert(
            event_type=EVENT_ORDER_PLACED,
            message="Order placed",
            severity="info",
        )

    assert result is True
    # httpx.AsyncClient should never be instantiated
    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_slack_http_error_handled(service: AlertService) -> None:
    """HTTP errors from Slack are caught gracefully."""
    import httpx

    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("connection failed")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Should not raise
        result = await service.send_alert(
            event_type=EVENT_RISK_LIMIT_APPROACH,
            message="Risk approaching limit",
            severity="warning",
        )

    assert result is True


@pytest.mark.asyncio
async def test_slack_non_200_logged(service: AlertService) -> None:
    """Non-200 from Slack is logged as warning."""
    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(status_code=500, text="Server Error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await service.send_alert(
            event_type=EVENT_KILL_SWITCH_TRIGGERED,
            message="Kill switch",
            severity="critical",
        )

    # Alert is still considered "sent" (logged locally)
    assert result is True


@pytest.mark.asyncio
async def test_all_event_types_accepted(service_no_slack: AlertService) -> None:
    """All defined event types can be sent."""
    for event_type in [
        EVENT_SIGNAL_GENERATED,
        EVENT_ORDER_PLACED,
        EVENT_RISK_LIMIT_APPROACH,
        EVENT_KILL_SWITCH_TRIGGERED,
        EVENT_PNL_THRESHOLD_BREACH,
    ]:
        result = await service_no_slack.send_alert(
            event_type=event_type,
            message=f"Test {event_type}",
            severity="info",
        )
        assert result is True, f"Failed for {event_type}"


@pytest.mark.asyncio
async def test_metadata_in_slack_payload(service: AlertService) -> None:
    """Metadata included in Slack message text."""
    with patch("src.monitoring.alert_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(status_code=200)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await service.send_alert(
            event_type=EVENT_PNL_THRESHOLD_BREACH,
            message="Daily loss threshold breached",
            severity="critical",
            metadata={"pnl_pct": "-3.5", "equity": "100000"},
        )

    payload = mock_client.post.call_args[1]["json"]
    assert "pnl_pct" in payload["text"]
    assert "-3.5" in payload["text"]
