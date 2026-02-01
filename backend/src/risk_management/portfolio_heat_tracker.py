"""
Portfolio Heat Tracker - Story 22.5

Extracts portfolio heat tracking from IntradayCampaignDetector.
Tracks portfolio heat (total risk as percentage of equity) and provides
alert state management with rate limiting.

Heat Alert States:
  NORMAL: Heat below 7%
  WARNING: Heat between 7% and 9%
  CRITICAL: Heat between 9% and 10%
  EXCEEDED: Heat above 10% (blocks new entries)

Trading Rules:
  - Max portfolio heat: 10.0% (EXCEEDED - blocks new entries)
  - Critical threshold: 9.0% (urgent attention required)
  - Warning threshold: 7.0% (caution advised)

Related Modules:
  - forex_portfolio_heat.py: Forex-specific heat tracking with weekend gap risk
    adjustments, Wyckoff pattern-weighted buffers, and dynamic limits (6%/5.5%).
    Use forex_portfolio_heat for forex positions with weekend exposure.
  - PortfolioHeatTracker (this module): General-purpose heat tracking for
    IntradayCampaignDetector integration. Uses simpler fixed thresholds (7/9/10%)
    without asset-specific or time-based adjustments.

Thread Safety:
  This class is NOT thread-safe. All methods that modify state must be called
  from a single thread or with external synchronization.

Integration with IntradayCampaignDetector:
  >>> # Inject via constructor
  >>> heat_tracker = PortfolioHeatTracker(
  ...     on_state_change=lambda old, new, heat: logger.info(f"{old} -> {new}")
  ... )
  >>> detector = IntradayCampaignDetector(heat_tracker=heat_tracker)
  >>>
  >>> # Delegate heat calculations
  >>> heat_tracker.add_campaign_risk(campaign.campaign_id, float(campaign.dollar_risk))
  >>> can_add = heat_tracker.can_add_position(new_risk, account_equity)

Author: Story 22.5 Implementation
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Optional

import structlog
from structlog.stdlib import BoundLogger

logger: BoundLogger = structlog.get_logger(__name__)

__all__ = [
    "PortfolioHeatTracker",
    "HeatAlertState",
    "HeatThresholds",
]


class HeatAlertState(str, Enum):
    """
    Portfolio heat alert state tracking.

    Tracks current heat warning level to prevent duplicate alerts
    and enable state transition tracking.

    Attributes:
        NORMAL: Heat below warning threshold (< 7%)
        WARNING: Heat at warning threshold (7% - 9%)
        CRITICAL: Heat at critical threshold (9% - 10%)
        EXCEEDED: Heat above maximum limit (> 10%)
    """

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EXCEEDED = "EXCEEDED"


@dataclass
class HeatThresholds:
    """
    Configurable heat thresholds.

    Attributes:
        warning_pct: Warning threshold percentage (default 7.0%)
        critical_pct: Critical threshold percentage (default 9.0%)
        exceeded_pct: Hard limit percentage (default 10.0% - non-negotiable)
        alert_cooldown_seconds: Cooldown between duplicate alerts (default 300s = 5 min)
    """

    warning_pct: float = 7.0
    critical_pct: float = 9.0
    exceeded_pct: float = 10.0  # Hard limit - non-negotiable
    alert_cooldown_seconds: int = 300  # 5 minutes


class PortfolioHeatTracker:
    """
    Tracks portfolio heat (total risk as percentage of equity).

    Portfolio heat is a critical risk metric that measures the total
    capital at risk across all open positions. This tracker enforces
    hard limits and provides alerts at configurable thresholds.

    Trading Rules:
        - Max portfolio heat: 10.0% (EXCEEDED - blocks new entries)
        - Critical threshold: 9.0% (urgent attention required)
        - Warning threshold: 7.0% (caution advised)

    Example:
        >>> tracker = PortfolioHeatTracker()
        >>> tracker.add_campaign_risk("c1", 5000.0)
        >>> tracker.add_campaign_risk("c2", 3000.0)
        >>> heat = tracker.calculate_heat(100_000.0)
        >>> print(f"Portfolio heat: {heat}%")  # 8.0%
        >>> state = tracker.get_alert_state(100_000.0)
        >>> print(f"Alert state: {state}")  # WARNING
    """

    def __init__(
        self,
        thresholds: Optional[HeatThresholds] = None,
        on_state_change: Optional[Callable[[HeatAlertState, HeatAlertState, float], None]] = None,
    ) -> None:
        """
        Initialize portfolio heat tracker.

        Args:
            thresholds: Configurable thresholds (default HeatThresholds())
            on_state_change: Callback when state changes (old_state, new_state, heat_pct)
        """
        self._thresholds = thresholds or HeatThresholds()
        self._campaign_risks: dict[str, float] = {}
        self._current_state = HeatAlertState.NORMAL
        self._last_alert_times: dict[HeatAlertState, datetime] = {}
        self._on_state_change = on_state_change
        self._logger: BoundLogger = logger.bind(component="portfolio_heat_tracker")

    def add_campaign_risk(self, campaign_id: str, risk_amount: float) -> None:
        """
        Register risk for a campaign.

        Args:
            campaign_id: Unique campaign identifier
            risk_amount: Dollar amount at risk
        """
        self._campaign_risks[campaign_id] = risk_amount
        self._logger.debug("risk_added", campaign_id=campaign_id, risk_amount=risk_amount)

    def remove_campaign_risk(self, campaign_id: str) -> float:
        """
        Remove risk when campaign closes.

        Args:
            campaign_id: Campaign identifier to remove

        Returns:
            The removed risk amount, or 0.0 if not found
        """
        removed = self._campaign_risks.pop(campaign_id, 0.0)
        if removed:
            self._logger.debug("risk_removed", campaign_id=campaign_id, risk_amount=removed)
        return removed

    def get_total_risk(self) -> float:
        """
        Get total dollar risk across all campaigns.

        Returns:
            Total risk in dollars
        """
        return sum(self._campaign_risks.values())

    def get_campaign_count(self) -> int:
        """
        Get number of campaigns being tracked.

        Returns:
            Number of campaigns with registered risk
        """
        return len(self._campaign_risks)

    def calculate_heat(self, account_equity: float) -> float:
        """
        Calculate portfolio heat as percentage.

        Formula: heat = (total_risk / account_equity) * 100

        Args:
            account_equity: Total account equity

        Returns:
            Heat percentage (0-100+)
        """
        if account_equity <= 0:
            self._logger.warning("invalid_account_equity", account_equity=account_equity)
            return 100.0  # Max heat if no equity

        total_risk = self.get_total_risk()
        heat = (total_risk / account_equity) * 100
        return round(heat, 2)

    def get_alert_state(self, account_equity: float) -> HeatAlertState:
        """
        Get current alert state based on heat level.

        State transitions:
            heat < 7%: NORMAL
            7% <= heat < 9%: WARNING
            9% <= heat < 10%: CRITICAL
            heat >= 10%: EXCEEDED

        Args:
            account_equity: Total account equity

        Returns:
            Current HeatAlertState
        """
        heat = self.calculate_heat(account_equity)
        thresholds = self._thresholds

        if heat >= thresholds.exceeded_pct:
            new_state = HeatAlertState.EXCEEDED
        elif heat >= thresholds.critical_pct:
            new_state = HeatAlertState.CRITICAL
        elif heat >= thresholds.warning_pct:
            new_state = HeatAlertState.WARNING
        else:
            new_state = HeatAlertState.NORMAL

        # Notify on state change
        if new_state != self._current_state:
            old_state = self._current_state
            self._current_state = new_state
            self._logger.info(
                "heat_state_changed",
                from_state=old_state.value,
                to_state=new_state.value,
                heat_pct=heat,
            )
            # Call callback after state update to prevent corruption on exception
            if self._on_state_change:
                try:
                    self._on_state_change(old_state, new_state, heat)
                except Exception:
                    self._logger.exception(
                        "state_change_callback_error",
                        from_state=old_state.value,
                        to_state=new_state.value,
                    )

        return new_state

    @property
    def current_state(self) -> HeatAlertState:
        """Get current alert state without recalculating."""
        return self._current_state

    def can_add_position(self, additional_risk: float, account_equity: float) -> bool:
        """
        Check if a new position can be added without exceeding limits.

        Args:
            additional_risk: Risk amount for proposed position
            account_equity: Total account equity

        Returns:
            True if position can be added, False if it would exceed limit
        """
        if account_equity <= 0:
            return False

        projected_risk = self.get_total_risk() + additional_risk
        projected_heat = (projected_risk / account_equity) * 100

        if projected_heat >= self._thresholds.exceeded_pct:
            self._logger.warning(
                "position_blocked",
                projected_heat=round(projected_heat, 2),
                limit=self._thresholds.exceeded_pct,
                additional_risk=additional_risk,
            )
            return False

        return True

    def should_send_alert(self, state: HeatAlertState) -> bool:
        """
        Check if alert should be sent (respecting rate limiting).

        Prevents duplicate alerts within cooldown period for same state.

        Args:
            state: Alert state to check

        Returns:
            True if alert should be sent, False if rate-limited
        """
        if state == HeatAlertState.NORMAL:
            return False  # No alerts for normal state

        now = datetime.now(UTC)
        last_alert = self._last_alert_times.get(state)
        cooldown = timedelta(seconds=self._thresholds.alert_cooldown_seconds)

        if last_alert and (now - last_alert) < cooldown:
            remaining = (last_alert + cooldown - now).total_seconds()
            self._logger.debug(
                "alert_rate_limited",
                state=state.value,
                remaining_seconds=round(remaining),
            )
            return False

        self._last_alert_times[state] = now
        return True

    def get_heat_summary(self, account_equity: float) -> dict:
        """
        Get summary of current heat status.

        Args:
            account_equity: Total account equity

        Returns:
            Dictionary with heat status details
        """
        heat = self.calculate_heat(account_equity)
        state = self.get_alert_state(account_equity)
        return {
            "heat_pct": heat,
            "total_risk": self.get_total_risk(),
            "campaign_count": len(self._campaign_risks),
            "state": state.value,
            "can_add_position": heat < self._thresholds.exceeded_pct,
            "thresholds": {
                "warning": self._thresholds.warning_pct,
                "critical": self._thresholds.critical_pct,
                "exceeded": self._thresholds.exceeded_pct,
            },
        }

    def clear(self) -> None:
        """Clear all tracked risks and reset state."""
        self._campaign_risks.clear()
        self._current_state = HeatAlertState.NORMAL
        self._last_alert_times.clear()
        self._logger.info("tracker_cleared")
