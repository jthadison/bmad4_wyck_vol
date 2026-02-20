"""Relative Strength API routes.

Provides RS score comparison of a symbol vs SPY and its sector ETF.
Uses the existing RelativeStrengthCalculator service.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.services.relative_strength_calculator import RelativeStrengthCalculator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/rs", tags=["relative-strength"])


class RSBenchmark(BaseModel):
    """Single benchmark comparison result."""

    benchmark_symbol: str
    benchmark_name: str
    rs_score: float
    stock_return_pct: float
    benchmark_return_pct: float
    interpretation: str  # "outperforming" | "underperforming" | "neutral"


class RSResponse(BaseModel):
    """Response model for relative strength endpoint."""

    symbol: str
    period_days: int
    benchmarks: list[RSBenchmark]
    is_sector_leader: bool
    sector_name: str | None
    calculated_at: str


def _interpret(rs_score: float) -> str:
    """Return interpretation string for an RS score."""
    if rs_score > 1.0:
        return "outperforming"
    elif rs_score < -1.0:
        return "underperforming"
    return "neutral"


# Reverse mapping: ETF symbol -> friendly name
_ETF_NAMES: dict[str, str] = {
    "XLK": "Technology ETF",
    "XLV": "Healthcare ETF",
    "XLF": "Financials ETF",
    "XLY": "Consumer Discretionary ETF",
    "XLP": "Consumer Staples ETF",
    "XLI": "Industrials ETF",
    "XLE": "Energy ETF",
    "XLB": "Materials ETF",
    "XLU": "Utilities ETF",
    "XLRE": "Real Estate ETF",
    "XLC": "Communication Services ETF",
}


@router.get("/{symbol}", response_model=RSResponse)
async def get_relative_strength(
    symbol: str,
    period_days: int = Query(default=30, ge=10, le=252),
    session: AsyncSession = Depends(get_db_session),
) -> RSResponse:
    """Get relative strength metrics for a symbol vs SPY and sector ETF."""
    symbol = symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    # Look up sector for the symbol
    sector_name: str | None = None
    is_sector_leader = False
    try:
        result = await session.execute(
            text(
                "SELECT sector_name, is_sector_leader " "FROM sector_mapping WHERE symbol = :symbol"
            ),
            {"symbol": symbol},
        )
        row = result.fetchone()
        if row:
            sector_name = row.sector_name
            is_sector_leader = (
                bool(row.is_sector_leader) if row.is_sector_leader is not None else False
            )
    except Exception:
        # sector_mapping table might not exist; continue without sector info
        logger.debug("sector_mapping_lookup_skipped", symbol=symbol)

    # Calculate RS
    calc = RelativeStrengthCalculator(session, period_days=period_days)

    end_date = datetime.now(UTC)
    from datetime import timedelta

    start_date = end_date - timedelta(days=period_days)

    # Get stock prices
    stock_prices = await calc._get_price_history(symbol, start_date, end_date)
    if stock_prices is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient price history for {symbol} over {period_days} days",
        )

    stock_return = float(calc.calculate_return(stock_prices[0], stock_prices[1]))

    # Build benchmarks list
    benchmarks: list[RSBenchmark] = []

    # SPY benchmark
    spy_prices = await calc._get_price_history("SPY", start_date, end_date)
    if spy_prices is not None:
        spy_return = float(calc.calculate_return(spy_prices[0], spy_prices[1]))
        rs_vs_spy = float(
            calc.calculate_rs_score(
                calc.calculate_return(stock_prices[0], stock_prices[1]),
                calc.calculate_return(spy_prices[0], spy_prices[1]),
            )
        )
        benchmarks.append(
            RSBenchmark(
                benchmark_symbol="SPY",
                benchmark_name="S&P 500",
                rs_score=rs_vs_spy,
                stock_return_pct=stock_return,
                benchmark_return_pct=spy_return,
                interpretation=_interpret(rs_vs_spy),
            )
        )

    # Sector ETF benchmark
    if sector_name and sector_name in RelativeStrengthCalculator.SECTOR_ETF_MAP:
        etf_symbol = RelativeStrengthCalculator.SECTOR_ETF_MAP[sector_name]
        etf_prices = await calc._get_price_history(etf_symbol, start_date, end_date)
        if etf_prices is not None:
            etf_return = float(calc.calculate_return(etf_prices[0], etf_prices[1]))
            rs_vs_sector = float(
                calc.calculate_rs_score(
                    calc.calculate_return(stock_prices[0], stock_prices[1]),
                    calc.calculate_return(etf_prices[0], etf_prices[1]),
                )
            )
            benchmarks.append(
                RSBenchmark(
                    benchmark_symbol=etf_symbol,
                    benchmark_name=_ETF_NAMES.get(etf_symbol, f"{sector_name} ETF"),
                    rs_score=rs_vs_sector,
                    stock_return_pct=stock_return,
                    benchmark_return_pct=etf_return,
                    interpretation=_interpret(rs_vs_sector),
                )
            )

    if not benchmarks:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No benchmark price history found for RS calculation on {symbol}. "
                "Add SPY to your scanner watchlist to enable RS vs market. "
                "Sector ETF comparisons require the sector ETF to also be in your watchlist."
            ),
        )

    return RSResponse(
        symbol=symbol,
        period_days=period_days,
        benchmarks=benchmarks,
        is_sector_leader=is_sector_leader,
        sector_name=sector_name,
        calculated_at=datetime.now(UTC).isoformat(),
    )
