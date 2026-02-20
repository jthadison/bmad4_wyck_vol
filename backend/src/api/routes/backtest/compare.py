"""
Backtest comparison endpoint.

Feature P2-9: Compare multiple backtest runs side by side.
- POST /compare: Compare 2-4 backtest runs, returning overlaid equity curves,
  side-by-side metrics, and parameter diffs.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.repositories.backtest_repository import BacktestRepository

router = APIRouter()
logger = logging.getLogger(__name__)

# Comparison colors for up to 4 runs (blue, orange, green, purple)
RUN_COLORS = ["#3B82F6", "#F97316", "#22C55E", "#A855F7"]


class CompareRequest(BaseModel):
    """Request body for backtest comparison."""

    run_ids: list[UUID] = Field(
        min_length=2,
        max_length=4,
        description="List of 2-4 backtest run IDs to compare",
    )


def _index_equity_curve(
    equity_curve: list[dict],
    base_value: float = 10000.0,
) -> list[dict]:
    """
    Re-index equity curve to a common base value for fair comparison.

    Quant correctness: all runs start at the same base (10000) so visual
    comparison is not distorted by differing initial capital sizes.

    Args:
        equity_curve: List of equity curve points (dicts with timestamp & portfolio_value)
        base_value: Starting index value (default 10000)

    Returns:
        List of dicts with timestamp and indexed equity value
    """
    if not equity_curve:
        return []

    first_raw = float(equity_curve[0].get("portfolio_value", base_value))
    # Guard against zero initial equity to avoid division by zero
    first_value = first_raw if first_raw != 0 else base_value

    result = []
    for point in equity_curve:
        raw = float(point.get("portfolio_value", first_value))
        # Treat a zero point value as the first_value so the curve starts at base_value
        effective = raw if raw != 0 else first_value
        result.append(
            {
                "date": point.get("timestamp", ""),
                "equity": round(base_value * effective / first_value, 2),
            }
        )
    return result


def _extract_param_diff(
    configs: list[tuple[str, dict]],
) -> list[dict]:
    """
    Find parameters that differ across runs for sensitivity analysis.

    Args:
        configs: List of (run_id_str, config_dict) tuples

    Returns:
        List of dicts with param name and per-run values (only differing params)
    """
    if len(configs) < 2:
        return []

    # Collect all param keys
    all_keys: set[str] = set()
    for _, cfg in configs:
        all_keys.update(cfg.keys())

    diffs = []
    for key in sorted(all_keys):
        values = {run_id: cfg.get(key) for run_id, cfg in configs}
        unique_values = {str(v) for v in values.values()}
        if len(unique_values) > 1:
            diffs.append({"param": key, "values": dict(values.items())})

    return diffs


@router.post("/compare")
async def compare_backtests(
    request: CompareRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Compare 2-4 backtest runs side by side.

    Feature P2-9: Returns overlaid equity curves indexed to a common base value,
    side-by-side metrics, trade counts, and a parameter diff for sensitivity analysis.

    Args:
        request: CompareRequest with list of 2-4 run_ids
        session: Database session

    Returns:
        Comparison payload with runs data and parameter_diffs

    Raises:
        400 Bad Request: Fewer than 2 or more than 4 run_ids
        404 Not Found: Any requested run_id not found in database
    """
    repository = BacktestRepository(session)

    runs_data = []
    configs_for_diff: list[tuple[str, dict]] = []

    for idx, run_id in enumerate(request.run_ids):
        result = await repository.get_result(run_id)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest run {run_id} not found",
            )

        # Serialize equity curve to list of dicts for indexing
        equity_curve_raw = [p.model_dump(mode="json") for p in result.equity_curve]

        # Index to common base of 10000
        indexed_curve = _index_equity_curve(equity_curve_raw)

        # Build config summary (key parameters only, excluding complex nested configs)
        cfg = result.config.model_dump(mode="json")
        config_summary = {
            "symbol": cfg.get("symbol"),
            "timeframe": cfg.get("timeframe"),
            "initial_capital": str(cfg.get("initial_capital", "")),
            "max_position_size": str(cfg.get("max_position_size", "")),
            "slippage_model": cfg.get("slippage_model"),
        }

        # Metrics for comparison table
        s = result.summary
        metrics = {
            "total_return_pct": float(s.total_return_pct),
            "max_drawdown": float(s.max_drawdown) * 100,  # convert 0-1 to %
            "sharpe_ratio": float(s.sharpe_ratio),
            "win_rate": float(s.win_rate) * 100,  # convert 0-1 to %
            "profit_factor": float(s.profit_factor),
            "cagr": float(s.cagr),
        }

        # Human-readable label
        label = f"Run #{idx + 1} - {result.symbol} ({result.start_date} to {result.end_date})"

        runs_data.append(
            {
                "run_id": str(run_id),
                "label": label,
                "color": RUN_COLORS[idx],
                "config_summary": config_summary,
                "metrics": metrics,
                "equity_curve": indexed_curve,
                "trade_count": len(result.trades),
                "trades": [t.model_dump(mode="json") for t in result.trades],
                "created_at": result.created_at.isoformat(),
            }
        )

        # Collect flat config for parameter diff
        configs_for_diff.append((str(run_id), config_summary))

    parameter_diffs = _extract_param_diff(configs_for_diff)

    logger.info(
        "backtest_compare",
        extra={
            "run_ids": [str(r) for r in request.run_ids],
            "runs_found": len(runs_data),
            "param_diffs": len(parameter_diffs),
        },
    )

    return {
        "runs": runs_data,
        "parameter_diffs": parameter_diffs,
    }
