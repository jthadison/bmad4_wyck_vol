"""
Pattern Effectiveness Models (Story 19.19)

Purpose:
--------
Provides Pydantic models for pattern effectiveness API responses.
Supports detailed per-pattern performance analysis with statistical
confidence intervals and R-multiple metrics.

Data Models:
------------
- PatternEffectiveness: Detailed effectiveness metrics per pattern type
- PatternEffectivenessResponse: Complete response with all patterns
- ConfidenceInterval: Win rate confidence interval bounds

Author: Story 19.19
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ConfidenceInterval(BaseModel):
    """
    Win rate confidence interval (Wilson score).

    Fields:
    -------
    - lower: 95% CI lower bound (0-100%)
    - upper: 95% CI upper bound (0-100%)
    """

    lower: float = Field(..., ge=0.0, le=100.0, description="95% CI lower bound")
    upper: float = Field(..., ge=0.0, le=100.0, description="95% CI upper bound")


class PatternEffectiveness(BaseModel):
    """
    Detailed effectiveness metrics for a pattern type.

    Provides comprehensive performance analysis including:
    - Funnel metrics (generated → approved → executed → closed → profitable)
    - Win rate with 95% confidence interval (Wilson score)
    - R-multiple analysis (winners, losers, overall)
    - Profitability metrics (profit factor, total P&L)
    - Efficiency rates (approval, execution)

    Fields:
    -------
    - pattern_type: Pattern type (SPRING, SOS, LPS, UTAD, SC, AR)
    - signals_generated: Total signals generated for this pattern
    - signals_approved: Signals that passed validation
    - signals_executed: Signals that were actually traded
    - signals_closed: Completed trades (win or loss)
    - signals_profitable: Winning trades
    - win_rate: Win rate percentage (0-100)
    - win_rate_ci: 95% confidence interval for win rate
    - avg_r_winners: Average R-multiple for winning trades
    - avg_r_losers: Average R-multiple for losing trades (negative)
    - avg_r_overall: Average R-multiple across all closed trades
    - max_r_winner: Best R-multiple achieved
    - max_r_loser: Worst R-multiple (most negative)
    - profit_factor: Gross profit / gross loss ratio
    - total_pnl: Total P&L from closed trades
    - avg_pnl_per_trade: Average P&L per closed trade
    - approval_rate: approved / generated percentage
    - execution_rate: executed / approved percentage
    """

    pattern_type: str = Field(..., description="Pattern type (SPRING, SOS, LPS, UTAD)")

    # Funnel metrics
    signals_generated: int = Field(..., ge=0, description="Total signals generated")
    signals_approved: int = Field(..., ge=0, description="Signals that passed validation")
    signals_executed: int = Field(..., ge=0, description="Signals that were traded")
    signals_closed: int = Field(..., ge=0, description="Completed trades")
    signals_profitable: int = Field(..., ge=0, description="Winning trades")

    # Win rate with confidence
    win_rate: float = Field(..., ge=0.0, le=100.0, description="Win rate percentage")
    win_rate_ci: ConfidenceInterval = Field(..., description="95% confidence interval")

    # R-multiple analysis
    avg_r_winners: float = Field(..., description="Average R-multiple for winners")
    avg_r_losers: float = Field(..., description="Average R-multiple for losers (negative)")
    avg_r_overall: float = Field(..., description="Average R-multiple overall")
    max_r_winner: float = Field(..., description="Best R-multiple achieved")
    max_r_loser: float = Field(..., description="Worst R-multiple (most negative)")

    # Profitability
    profit_factor: float = Field(..., ge=0.0, description="Gross profit / gross loss")
    total_pnl: Decimal = Field(..., description="Total P&L from closed trades")
    avg_pnl_per_trade: Decimal = Field(..., description="Average P&L per trade")

    # Efficiency rates
    approval_rate: float = Field(..., ge=0.0, le=100.0, description="Approval rate %")
    execution_rate: float = Field(..., ge=0.0, le=100.0, description="Execution rate %")

    model_config = {"json_encoders": {Decimal: str}}


class DateRange(BaseModel):
    """
    Date range for effectiveness query.

    Fields:
    -------
    - start_date: Start of date range
    - end_date: End of date range
    """

    start_date: date = Field(..., description="Start of date range")
    end_date: date = Field(..., description="End of date range")


class PatternEffectivenessResponse(BaseModel):
    """
    Complete pattern effectiveness response.

    Combines effectiveness metrics for all pattern types
    into a single response for the report.

    Fields:
    -------
    - patterns: List of effectiveness metrics per pattern type
    - date_range: Date range for the query
    """

    patterns: list[PatternEffectiveness] = Field(
        ..., description="Effectiveness metrics per pattern type"
    )
    date_range: DateRange = Field(..., description="Date range for query")

    model_config = {"json_encoders": {Decimal: str, date: lambda v: v.isoformat()}}
