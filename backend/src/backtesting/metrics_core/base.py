"""
Base models for metrics calculation (Story 18.7.1).

Provides foundation data models for modular metrics calculation.
These models are used by DrawdownCalculator and other metrics modules.

Author: Story 18.7.1
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass(frozen=True)
class EquityPoint:
    """Single point on an equity curve for drawdown calculation.

    Attributes:
        timestamp: Time of this equity snapshot
        value: Portfolio value at this time
    """

    timestamp: datetime
    value: Decimal


@dataclass
class DrawdownPeriod:
    """A single drawdown period with peak, trough, and recovery info.

    Attributes:
        peak_date: Date of peak portfolio value before drawdown
        trough_date: Date of lowest portfolio value
        recovery_date: Date portfolio recovered to peak (None if ongoing)
        peak_value: Portfolio value at peak
        trough_value: Portfolio value at trough
        drawdown_pct: Drawdown percentage from peak (0-100)
        duration_days: Days from peak to trough
        recovery_days: Days from trough to recovery (None if ongoing)
    """

    peak_date: datetime
    trough_date: datetime
    peak_value: Decimal
    trough_value: Decimal
    drawdown_pct: Decimal
    duration_days: int
    recovery_date: Optional[datetime] = None
    recovery_days: Optional[int] = None


@dataclass
class MetricResult:
    """Generic result container for a calculated metric.

    Attributes:
        name: Name of the metric
        value: Calculated value
        metadata: Optional additional information about the calculation
    """

    name: str
    value: Decimal
    metadata: Optional[dict[str, Any]] = None
