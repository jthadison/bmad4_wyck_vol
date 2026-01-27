"""
Signal Statistics Models (Story 19.17)

Purpose:
--------
Provides Pydantic models for signal statistics API responses.
Supports performance dashboards with aggregated signal data.

Data Models:
------------
- SignalSummary: High-level signal statistics
- PatternWinRate: Win rate per pattern type
- RejectionCount: Rejection reasons breakdown
- SymbolPerformance: Performance metrics per symbol
- DateRange: Date range filter info
- SignalStatisticsResponse: Complete statistics response

Author: Story 19.17
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class SignalSummary(BaseModel):
    """
    High-level signal statistics summary.

    Provides overall signal counts and performance metrics
    for today, this week, this month, and all-time.

    Fields:
    -------
    - total_signals: Total signals in date range
    - signals_today: Signals generated today
    - signals_this_week: Signals generated this week
    - signals_this_month: Signals generated this month
    - overall_win_rate: Win rate of closed signals (0-100%)
    - avg_confidence: Average confidence score
    - avg_r_multiple: Average R-multiple for closed signals
    - total_pnl: Total P&L from closed signals
    """

    total_signals: int = Field(..., ge=0, description="Total signals in date range")
    signals_today: int = Field(..., ge=0, description="Signals generated today")
    signals_this_week: int = Field(..., ge=0, description="Signals generated this week")
    signals_this_month: int = Field(..., ge=0, description="Signals generated this month")
    overall_win_rate: float = Field(
        ..., ge=0.0, le=100.0, description="Win rate percentage (0-100)"
    )
    avg_confidence: float = Field(..., ge=0.0, le=100.0, description="Average confidence score")
    avg_r_multiple: float = Field(..., ge=0.0, description="Average R-multiple")
    total_pnl: Decimal = Field(..., description="Total P&L from closed signals")

    model_config = {"json_encoders": {Decimal: str}}


class PatternWinRate(BaseModel):
    """
    Win rate statistics per pattern type.

    Provides detailed performance breakdown for each
    Wyckoff pattern type (SPRING, SOS, LPS, UTAD).

    Fields:
    -------
    - pattern_type: Pattern type (SPRING, SOS, LPS, UTAD)
    - total_signals: Total signals for this pattern
    - closed_signals: Number of closed (completed) signals
    - winning_signals: Number of profitable signals
    - win_rate: Win rate percentage (0-100)
    - avg_confidence: Average confidence score
    - avg_r_multiple: Average R-multiple achieved
    """

    pattern_type: str = Field(..., description="Pattern type (SPRING, SOS, LPS, UTAD)")
    total_signals: int = Field(..., ge=0, description="Total signals for pattern")
    closed_signals: int = Field(..., ge=0, description="Number of closed signals")
    winning_signals: int = Field(..., ge=0, description="Number of winning signals")
    win_rate: float = Field(..., ge=0.0, le=100.0, description="Win rate percentage")
    avg_confidence: float = Field(..., ge=0.0, le=100.0, description="Average confidence score")
    avg_r_multiple: float = Field(..., ge=0.0, description="Average R-multiple")


class RejectionCount(BaseModel):
    """
    Rejection reasons breakdown.

    Provides counts and percentages for signal rejections
    grouped by validation stage and reason.

    Fields:
    -------
    - reason: Rejection reason description
    - validation_stage: Stage that rejected (Volume, Phase, Level, Risk, Strategy)
    - count: Number of rejections with this reason
    - percentage: Percentage of total rejections
    """

    reason: str = Field(..., description="Rejection reason description")
    validation_stage: str = Field(..., description="Validation stage that rejected")
    count: int = Field(..., ge=0, description="Number of rejections")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of total rejections")


class SymbolPerformance(BaseModel):
    """
    Performance metrics per trading symbol.

    Provides per-symbol breakdown of signal performance
    including win rate, R-multiples, and P&L.

    Fields:
    -------
    - symbol: Trading symbol (e.g., AAPL, EUR/USD)
    - total_signals: Total signals for symbol
    - win_rate: Win rate percentage (0-100)
    - avg_r_multiple: Average R-multiple achieved
    - total_pnl: Total P&L for symbol
    """

    symbol: str = Field(..., description="Trading symbol")
    total_signals: int = Field(..., ge=0, description="Total signals for symbol")
    win_rate: float = Field(..., ge=0.0, le=100.0, description="Win rate percentage")
    avg_r_multiple: float = Field(..., ge=0.0, description="Average R-multiple")
    total_pnl: Decimal = Field(..., description="Total P&L for symbol")

    model_config = {"json_encoders": {Decimal: str}}


class DateRange(BaseModel):
    """
    Date range for statistics query.

    Fields:
    -------
    - start_date: Start of date range
    - end_date: End of date range
    """

    start_date: date = Field(..., description="Start of date range")
    end_date: date = Field(..., description="End of date range")


class SignalStatisticsResponse(BaseModel):
    """
    Complete signal statistics response.

    Combines all statistics into a single response for the
    performance dashboard.

    Fields:
    -------
    - summary: High-level summary statistics
    - win_rate_by_pattern: Win rates per pattern type
    - rejection_breakdown: Rejection reasons breakdown
    - symbol_performance: Per-symbol performance metrics
    - date_range: Date range for the query
    """

    summary: SignalSummary = Field(..., description="High-level summary statistics")
    win_rate_by_pattern: list[PatternWinRate] = Field(..., description="Win rates per pattern type")
    rejection_breakdown: list[RejectionCount] = Field(
        ..., description="Rejection reasons breakdown"
    )
    symbol_performance: list[SymbolPerformance] = Field(
        ..., description="Per-symbol performance metrics"
    )
    date_range: DateRange = Field(..., description="Date range for query")

    model_config = {"json_encoders": {Decimal: str, date: lambda v: v.isoformat()}}
