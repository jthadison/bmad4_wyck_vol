"""
Backtest API Routes (Story 11.2 + Story 12.1 + Story 12.4 + Story 12.7)

Purpose:
--------
Provides REST endpoints for backtesting functionality.

Story 11.2 Endpoints (Preview):
- POST /api/v1/backtest/preview: Initiate backtest preview
- GET /api/v1/backtest/status/{run_id}: Get backtest status

Story 12.1 Endpoints (Full Backtest):
- POST /api/v1/backtest/run: Run full backtest with persistence
- GET /api/v1/backtest/results/{backtest_run_id}: Get specific result
- GET /api/v1/backtest/results: List all results (paginated)

Story 12.4 Endpoints (Walk-Forward Testing):
- POST /api/v1/backtest/walk-forward: Run walk-forward validation test
- GET /api/v1/backtest/walk-forward/{walk_forward_id}: Get walk-forward result
- GET /api/v1/backtest/walk-forward: List walk-forward results (paginated)

Story 12.7 Endpoints (Regression Testing):
- POST /api/v1/backtest/regression: Run regression test
- GET /api/v1/backtest/regression/{test_id}: Get regression test result
- GET /api/v1/backtest/regression: List regression test results (paginated)
- POST /api/v1/backtest/regression/{test_id}/establish-baseline: Establish baseline
- GET /api/v1/backtest/regression/baseline/current: Get current baseline
- GET /api/v1/backtest/regression/baseline/history: List baseline history

Author: Story 11.2, Story 12.1 Task 8, Story 12.4 Task 9, Story 12.7 Task 11
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import manager
from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.engine import BacktestEngine as PreviewEngine
from src.database import async_session_maker, get_db
from src.models.backtest import (
    BacktestCompletedMessage,
    BacktestConfig,
    BacktestPreviewRequest,
    BacktestPreviewResponse,
    BacktestProgressUpdate,
    BacktestResult,
    RegressionTestConfig,
    WalkForwardConfig,
)
from src.models.ohlcv import OHLCVBar
from src.repositories.backtest_repository import BacktestRepository

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)

# In-memory storage for backtest runs (MVP - replace with database in production)
backtest_runs: dict[UUID, dict] = {}


@router.post(
    "/preview", response_model=BacktestPreviewResponse, status_code=status.HTTP_202_ACCEPTED
)
async def start_backtest_preview(
    request: BacktestPreviewRequest,
    session: AsyncSession = Depends(get_db),
) -> BacktestPreviewResponse:
    """
    Initiate backtest preview with proposed configuration.

    This endpoint queues an asynchronous backtest that compares the current
    system configuration against the proposed changes using historical data.

    Args:
        request: Backtest preview request with proposed config and parameters
        session: Database session

    Returns:
        BacktestPreviewResponse with run_id and status

    Raises:
        400 Bad Request: Invalid config payload
        422 Unprocessable Entity: Validation error (days out of range)
        503 Service Unavailable: Too many concurrent backtests

    Example Response:
        {
            "backtest_run_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "queued",
            "estimated_duration_seconds": 120
        }
    """
    print(f"[ROUTE DEBUG] start_backtest_preview called, request={request}", flush=True)

    # Check for concurrent backtest limit (MVP: max 5 concurrent)
    running_backtests = sum(
        1 for run in backtest_runs.values() if run["status"] in ["queued", "running"]
    )
    if running_backtests >= 5:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backtest engine overloaded - too many concurrent backtests. Please try again later.",
        )

    # Generate unique run ID
    run_id = uuid4()

    # Initialize backtest run tracking
    backtest_runs[run_id] = {
        "status": "queued",
        "progress": {"bars_analyzed": 0, "total_bars": 0, "percent_complete": 0},
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Estimate duration (roughly 1 second per day of data for 90 days = ~90-120s)
    estimated_duration = int(request.days * 1.5)  # 1.5 seconds per day estimate

    # Queue background task - Use asyncio.create_task for better Windows compatibility
    print(f"[QUEUE DEBUG] About to queue task for {run_id}", flush=True)
    import asyncio

    async def _run_task_with_error_handling():
        try:
            await run_backtest_preview_task(run_id, request)
        except Exception as e:
            print(f"[ERROR] Background task failed with exception: {e}", flush=True)
            import traceback

            traceback.print_exc()
            raise

    asyncio.create_task(_run_task_with_error_handling())
    print("[QUEUE DEBUG] Task queued successfully", flush=True)

    logger.info(
        "Backtest preview queued",
        extra={
            "backtest_run_id": str(run_id),
            "days": request.days,
            "estimated_duration_seconds": estimated_duration,
        },
    )

    return BacktestPreviewResponse(
        backtest_run_id=run_id, status="queued", estimated_duration_seconds=estimated_duration
    )


@router.get("/status/{run_id}")
async def get_backtest_status(run_id: UUID) -> dict:
    """
    Get current status and progress of a backtest run.

    This endpoint provides REST polling fallback when WebSocket is unavailable.

    Args:
        run_id: Backtest run identifier

    Returns:
        Status object with current progress

    Raises:
        404 Not Found: Backtest run not found

    Example Response:
        {
            "status": "running",
            "progress": {
                "bars_analyzed": 1245,
                "total_bars": 2268,
                "percent_complete": 54
            }
        }
    """
    if run_id not in backtest_runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Backtest run {run_id} not found"
        )

    run = backtest_runs[run_id]
    return {"status": run["status"], "progress": run["progress"], "error": run.get("error")}


async def run_backtest_preview_task(run_id: UUID, request: BacktestPreviewRequest) -> None:
    """
    Background task to execute backtest preview.

    Args:
        run_id: Backtest run identifier
        request: Backtest request parameters
    """
    print(f"[TASK DEBUG] Background task started for {run_id}", flush=True)
    try:
        # Update status to running
        print(f"[TASK DEBUG] About to update status for {run_id}", flush=True)
        backtest_runs[run_id]["status"] = "running"
        print("[TASK DEBUG] Status updated to running", flush=True)

        logger.info("Starting backtest preview execution", extra={"backtest_run_id": str(run_id)})
        print("[TASK DEBUG] Logger info called", flush=True)

        # Fetch historical data from Polygon.io (or fallback to synthetic)
        print("[TASK DEBUG] About to fetch historical data", flush=True)
        historical_bars = await fetch_historical_data(
            request.days, request.symbol, request.timeframe
        )
        print(f"[TASK DEBUG] Fetched {len(historical_bars)} bars", flush=True)
        total_bars = len(historical_bars)
        backtest_runs[run_id]["progress"]["total_bars"] = total_bars

        # Get current configuration (simplified for MVP) - create session manually
        print("[TASK DEBUG] About to get current configuration", flush=True)
        async with async_session_maker() as session:
            print("[TASK DEBUG] Session created, calling get_current_configuration", flush=True)
            current_config = await get_current_configuration(session)
            print(f"[TASK DEBUG] Got current config: {current_config}", flush=True)

        # Create progress callback for WebSocket updates
        sequence_number = 0

        async def progress_callback(bars_analyzed: int, total_bars: int, percent_complete: int):
            nonlocal sequence_number
            sequence_number += 1

            # Update in-memory tracking
            backtest_runs[run_id]["progress"] = {
                "bars_analyzed": bars_analyzed,
                "total_bars": total_bars,
                "percent_complete": percent_complete,
            }

            # Emit WebSocket progress update
            progress_msg = BacktestProgressUpdate(
                sequence_number=sequence_number,
                backtest_run_id=run_id,
                bars_analyzed=bars_analyzed,
                total_bars=total_bars,
                percent_complete=percent_complete,
                timestamp=datetime.now(UTC),
            )

            await manager.broadcast(progress_msg.model_dump(mode="json"))

        # Initialize and run backtest engine (Story 11.2 preview engine)
        print("[TASK DEBUG] Creating PreviewEngine", flush=True)
        engine = PreviewEngine(progress_callback=progress_callback)
        print("[TASK DEBUG] PreviewEngine created", flush=True)

        try:
            print("[TASK DEBUG] About to call engine.run_preview()", flush=True)
            comparison = await engine.run_preview(
                backtest_run_id=run_id,
                current_config=current_config,
                proposed_config=request.proposed_config,
                historical_bars=historical_bars,
                timeout_seconds=300,  # 5 minutes
            )
            print("[TASK DEBUG] engine.run_preview() completed", flush=True)

            # Mark as completed
            print("[TASK DEBUG] Marking backtest as completed", flush=True)
            backtest_runs[run_id]["status"] = "completed"
            backtest_runs[run_id]["comparison"] = comparison
            print("[TASK DEBUG] Backtest marked as completed", flush=True)

            # Save backtest result to database for persistence
            try:
                print("[TASK DEBUG] Saving backtest result to database", flush=True)

                # Calculate start and end dates from historical bars
                start_date = (
                    datetime.fromisoformat(str(historical_bars[0]["timestamp"])).date()
                    if historical_bars
                    else date.today()
                )
                end_date = (
                    datetime.fromisoformat(str(historical_bars[-1]["timestamp"])).date()
                    if historical_bars
                    else date.today()
                )

                # Construct BacktestResult from comparison (using proposed config metrics)
                backtest_result = BacktestResult(
                    backtest_run_id=run_id,
                    symbol=request.symbol or "SYNTHETIC",
                    timeframe=request.timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    config=BacktestConfig(
                        symbol=request.symbol or "SYNTHETIC",
                        start_date=start_date,
                        end_date=end_date,
                        # Use defaults for other config fields
                    ),
                    equity_curve=comparison.equity_curve_proposed,
                    trades=[],  # Preview engine doesn't track individual trades
                    summary=comparison.proposed_metrics,
                    look_ahead_bias_check=False,
                    execution_time_seconds=0.0,
                    created_at=datetime.now(UTC),
                )

                # Save to database using BacktestRepository
                async with async_session_maker() as db_session:
                    repository = BacktestRepository(db_session)
                    await repository.save_result(backtest_result)
                    print("[TASK DEBUG] Backtest result saved to database successfully", flush=True)
                    logger.info(
                        "Backtest result saved to database",
                        extra={"backtest_run_id": str(run_id), "symbol": request.symbol},
                    )
            except Exception as db_error:
                # Log database save error but don't fail the backtest
                logger.error(
                    "Failed to save backtest result to database",
                    extra={"backtest_run_id": str(run_id), "error": str(db_error)},
                    exc_info=True,
                )
                print(f"[TASK DEBUG] Database save failed: {db_error}", flush=True)

            # Emit completion message via WebSocket
            sequence_number += 1
            print("[TASK DEBUG] Creating completion message", flush=True)
            completion_msg = BacktestCompletedMessage(
                sequence_number=sequence_number,
                backtest_run_id=run_id,
                comparison=comparison,
                timestamp=datetime.now(UTC),
            )
            print("[TASK DEBUG] About to broadcast completion message", flush=True)

            await manager.broadcast(completion_msg.model_dump(mode="json"))
            print("[TASK DEBUG] Broadcast completed", flush=True)

            logger.info(
                "Backtest preview completed successfully",
                extra={
                    "backtest_run_id": str(run_id),
                    "recommendation": comparison.recommendation,
                },
            )

        except asyncio.TimeoutError:
            # Handle timeout - mark as timeout with partial results
            backtest_runs[run_id]["status"] = "timeout"
            logger.warning(
                "Backtest preview timed out",
                extra={
                    "backtest_run_id": str(run_id),
                    "bars_analyzed": backtest_runs[run_id]["progress"]["bars_analyzed"],
                },
            )

    except Exception as e:
        # Handle errors
        backtest_runs[run_id]["status"] = "failed"
        backtest_runs[run_id]["error"] = str(e)

        logger.error(
            "Backtest preview failed",
            extra={"backtest_run_id": str(run_id), "error": str(e)},
            exc_info=True,
        )


async def fetch_historical_data(days: int, symbol: str | None, timeframe: str = "1d") -> list[dict]:
    """
    Fetch historical OHLCV data for backtest.

    Fetches real market data from Polygon.io API. Falls back to synthetic data
    if symbol is None or if Polygon API fails.

    Args:
        days: Number of days of historical data
        symbol: Stock symbol (e.g., "SPY", "PLTR")
        timeframe: Bar timeframe (e.g., "1d", "4h", "1h")

    Returns:
        List of OHLCV bar dictionaries
    """
    # If no symbol provided, generate synthetic data
    if not symbol:
        logger.warning("No symbol provided, generating synthetic data")
        return _generate_synthetic_data(days)

    try:
        # Import Polygon adapter
        from src.market_data.adapters.polygon_adapter import PolygonAdapter

        # Initialize adapter
        adapter = PolygonAdapter()

        # Calculate date range
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days)

        logger.info(
            "Fetching real market data from Polygon.io",
            extra={
                "symbol": symbol,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "timeframe": timeframe,
            },
        )

        # Fetch bars from Polygon.io
        ohlcv_bars = await adapter.fetch_historical_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Convert OHLCVBar objects to dictionaries
        bars = []
        for bar in ohlcv_bars:
            bars.append(
                {
                    "timestamp": bar.timestamp,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": bar.volume,
                }
            )

        logger.info(f"Fetched {len(bars)} bars from Polygon.io for {symbol}")
        return bars

    except ValueError as e:
        # Missing API key or configuration error
        logger.error(f"Polygon.io configuration error: {e}, falling back to synthetic data")
        return _generate_synthetic_data(days)

    except Exception as e:
        # Any other error (network, API limit, etc.)
        logger.error(
            f"Failed to fetch data from Polygon.io: {e}, falling back to synthetic data",
            exc_info=True,
        )
        return _generate_synthetic_data(days)


def _generate_synthetic_data(days: int) -> list[dict]:
    """
    Generate synthetic OHLCV data for testing.

    Args:
        days: Number of days of data to generate

    Returns:
        List of OHLCV bar dictionaries
    """
    bars = []
    start_date = datetime.now(UTC) - timedelta(days=days)

    for i in range(days):
        timestamp = start_date + timedelta(days=i)

        # Generate realistic-looking OHLCV data
        base_price = Decimal("150.00") + Decimal(str(i * 0.5))  # Trending upward
        daily_range = Decimal("5.00")

        bars.append(
            {
                "timestamp": timestamp,
                "open": float(base_price),
                "high": float(base_price + daily_range),
                "low": float(base_price - daily_range),
                "close": float(base_price + (daily_range * Decimal("0.3"))),
                "volume": 1000000 + (i * 10000),
            }
        )

    return bars


async def get_current_configuration(session: AsyncSession) -> dict:
    """
    Fetch current system configuration.

    In production, this would query the configuration from the database.
    For MVP, returns a simplified default configuration.

    Args:
        session: Database session

    Returns:
        Current configuration dictionary
    """
    # Simplified default configuration for MVP
    # In production, fetch from ConfigurationService
    return {
        "volume_thresholds": {
            "ultra_high": 2.5,
            "high": 1.8,
            "medium": 1.2,
            "low": 0.8,
        },
        "risk_limits": {"max_portfolio_heat": 0.06, "max_campaign_heat": 0.02},
    }


# =============================
# Story 12.1 Task 8: Full Backtest Endpoints
# =============================


@router.post("/run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def run_backtest(
    config: BacktestConfig,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run a full backtest with the provided configuration.

    AC7 Subtask 8.1-8.5: Run backtest as background task, return immediately.

    Args:
        config: Backtest configuration (symbol, date range, initial capital)
        background_tasks: FastAPI background tasks
        session: Database session

    Returns:
        Response with backtest_run_id and status: RUNNING

    Raises:
        400 Bad Request: Invalid config
        422 Unprocessable Entity: Validation errors

    Example Request:
        POST /api/v1/backtest/run
        {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 100000
        }

    Example Response:
        {
            "backtest_run_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "RUNNING"
        }
    """
    from uuid import uuid4

    # Generate unique run ID
    run_id = uuid4()

    # Validate config
    if config.start_date >= config.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    if config.initial_capital <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="initial_capital must be greater than 0",
        )

    # Initialize tracking (in-memory for now)
    backtest_runs[run_id] = {
        "status": "RUNNING",
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Queue background task
    asyncio.create_task(
        run_backtest_task(
            run_id,
            config,
            session,
        )
    )

    logger.info(
        "Backtest queued",
        extra={
            "backtest_run_id": str(run_id),
            "symbol": config.symbol,
            "start_date": str(config.start_date),
            "end_date": str(config.end_date),
        },
    )

    return {"backtest_run_id": run_id, "status": "RUNNING"}


@router.get("/results/{backtest_run_id}")
async def get_backtest_result(
    backtest_run_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get backtest result by backtest_run_id.

    AC7 Subtask 8.6-8.7: Return result if completed, status if running, 404 if not found.

    Args:
        backtest_run_id: Backtest run identifier
        session: Database session

    Returns:
        BacktestResult if completed, status object if running

    Raises:
        404 Not Found: Backtest not found

    Example Response (Running):
        {
            "status": "RUNNING"
        }

    Example Response (Completed):
        {
            "backtest_run_id": "...",
            "symbol": "AAPL",
            "metrics": {...},
            "trades": [...],
            ...
        }
    """
    from src.repositories.backtest_repository import BacktestRepository

    # Check in-memory tracking first
    if backtest_run_id in backtest_runs:
        run_status = backtest_runs[backtest_run_id]["status"]
        if run_status == "RUNNING":
            return {"status": "RUNNING"}
        elif run_status == "FAILED":
            error = backtest_runs[backtest_run_id].get("error", "Unknown error")
            return {"status": "FAILED", "error": error}

    # Check database for completed result
    repository = BacktestRepository(session)
    result = await repository.get_result(backtest_run_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run {backtest_run_id} not found",
        )

    return result.model_dump(mode="json")


# ==============================================================================
# Story 12.6B: Report Export Endpoints
# ==============================================================================


@router.get("/results/{backtest_run_id}/report/html")
async def get_backtest_html_report(
    backtest_run_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """
    Generate HTML report for backtest result (Story 12.6B Task 6 Subtask 6.4).

    Retrieves backtest result and generates comprehensive HTML report with:
    - Summary metrics table
    - Equity curve chart
    - Monthly returns heatmap
    - Drawdown analysis
    - Pattern performance breakdown
    - Trade list

    Args:
        backtest_run_id: Backtest run identifier
        session: Database session

    Returns:
        HTML report as text/html response

    Raises:
        404 Not Found: Backtest not found
        500 Internal Server Error: Report generation failed

    Example:
        GET /api/v1/backtest/results/550e8400-e29b-41d4-a716-446655440000/report/html
    """
    from fastapi.responses import HTMLResponse

    from src.backtesting.backtest_report_generator import BacktestReportGenerator
    from src.repositories.backtest_repository import BacktestRepository

    logger.info(
        "Generating HTML report",
        extra={"backtest_run_id": str(backtest_run_id)},
    )

    # Retrieve backtest result
    repository = BacktestRepository(session)
    result = await repository.get_result(backtest_run_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run {backtest_run_id} not found",
        )

    # Generate HTML report
    try:
        generator = BacktestReportGenerator()
        html_content = generator.generate_html_report(result)

        logger.info(
            "HTML report generated successfully",
            extra={
                "backtest_run_id": str(backtest_run_id),
                "html_size_kb": len(html_content) / 1024,
            },
        )

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(
            "HTML report generation failed",
            extra={"backtest_run_id": str(backtest_run_id), "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate HTML report: {str(e)}",
        ) from e


@router.get("/results/{backtest_run_id}/report/pdf")
async def get_backtest_pdf_report(
    backtest_run_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """
    Generate PDF report for backtest result (Story 12.6B Task 6 Subtask 6.5).

    Retrieves backtest result and generates PDF report via HTML-to-PDF conversion.

    Args:
        backtest_run_id: Backtest run identifier
        session: Database session

    Returns:
        PDF report with Content-Type: application/pdf and Content-Disposition: attachment

    Raises:
        404 Not Found: Backtest not found
        500 Internal Server Error: Report generation failed

    Example:
        GET /api/v1/backtest/results/550e8400-e29b-41d4-a716-446655440000/report/pdf
    """
    from fastapi.responses import Response as FastAPIResponse

    from src.backtesting.backtest_report_generator import BacktestReportGenerator
    from src.repositories.backtest_repository import BacktestRepository

    logger.info(
        "Generating PDF report",
        extra={"backtest_run_id": str(backtest_run_id)},
    )

    # Retrieve backtest result
    repository = BacktestRepository(session)
    result = await repository.get_result(backtest_run_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run {backtest_run_id} not found",
        )

    # Generate PDF report
    try:
        generator = BacktestReportGenerator()
        pdf_bytes = generator.generate_pdf_report(result)

        logger.info(
            "PDF report generated successfully",
            extra={
                "backtest_run_id": str(backtest_run_id),
                "pdf_size_kb": len(pdf_bytes) / 1024,
            },
        )

        return FastAPIResponse(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=backtest_{result.symbol}_{backtest_run_id}.pdf"
            },
        )

    except Exception as e:
        logger.error(
            "PDF report generation failed",
            extra={"backtest_run_id": str(backtest_run_id), "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {str(e)}",
        ) from e


@router.get("/results/{backtest_run_id}/trades/csv")
async def get_backtest_trades_csv(
    backtest_run_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export trade list as CSV (Story 12.6B Task 6 Subtask 6.6).

    Retrieves backtest result and exports all trades to CSV format.

    CSV Columns:
        - trade_id, position_id, symbol, pattern_type, entry_timestamp
        - entry_price, exit_timestamp, exit_price, quantity, side
        - realized_pnl, commission, slippage, net_pnl, r_multiple
        - gross_pnl, gross_r_multiple

    Args:
        backtest_run_id: Backtest run identifier
        session: Database session

    Returns:
        CSV file with Content-Type: text/csv and Content-Disposition: attachment

    Raises:
        404 Not Found: Backtest not found
        500 Internal Server Error: CSV generation failed

    Example:
        GET /api/v1/backtest/results/550e8400-e29b-41d4-a716-446655440000/trades/csv
    """
    from fastapi.responses import Response as FastAPIResponse

    from src.backtesting.backtest_report_generator import BacktestReportGenerator
    from src.repositories.backtest_repository import BacktestRepository

    logger.info(
        "Generating CSV trade list",
        extra={"backtest_run_id": str(backtest_run_id)},
    )

    # Retrieve backtest result
    repository = BacktestRepository(session)
    result = await repository.get_result(backtest_run_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run {backtest_run_id} not found",
        )

    # Generate CSV trade list
    try:
        generator = BacktestReportGenerator()
        csv_content = generator.generate_csv_trade_list(result.trades)

        logger.info(
            "CSV trade list generated successfully",
            extra={
                "backtest_run_id": str(backtest_run_id),
                "trade_count": len(result.trades),
                "csv_size_kb": len(csv_content) / 1024,
            },
        )

        return FastAPIResponse(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=trades_{result.symbol}_{backtest_run_id}.csv"
            },
        )

    except Exception as e:
        logger.error(
            "CSV generation failed",
            extra={"backtest_run_id": str(backtest_run_id), "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate CSV: {str(e)}",
        ) from e


@router.get("/results")
async def list_backtest_results(
    symbol: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    List backtest results with pagination and optional filtering.

    AC7 Subtask 8.8-8.9: Paginated listing with optional symbol filter.

    Args:
        symbol: Optional symbol filter
        limit: Maximum number of results (default 100, max 1000)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        Paginated list of backtest results

    Example Response:
        {
            "results": [
                {
                    "backtest_run_id": "...",
                    "symbol": "AAPL",
                    "metrics": {...},
                    ...
                },
                ...
            ],
            "total": 42,
            "limit": 100,
            "offset": 0
        }
    """
    from src.repositories.backtest_repository import BacktestRepository

    # Validate pagination parameters
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit cannot exceed 1000",
        )

    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be at least 1",
        )

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset cannot be negative",
        )

    # Query repository
    repository = BacktestRepository(session)
    results = await repository.list_results(symbol=symbol, limit=limit, offset=offset)

    return {
        "results": [r.model_dump(mode="json") for r in results],
        "total": len(results),
        "limit": limit,
        "offset": offset,
    }


async def run_backtest_task(
    run_id: UUID,
    config: BacktestConfig,
    session: AsyncSession,
) -> None:
    """
    Background task to execute full backtest.

    AC7 Subtask 8.4-8.10: Execute engine, save to database via repository.

    Args:
        run_id: Backtest run identifier
        config: Backtest configuration
        session: Database session
    """
    from src.repositories.backtest_repository import BacktestRepository

    try:
        logger.info("Starting backtest execution", extra={"backtest_run_id": str(run_id)})

        # Fetch historical data (simplified - in production, query from OHLCV repository)
        bars = await fetch_historical_bars(config.symbol, config.start_date, config.end_date)

        if not bars:
            raise ValueError(f"No historical data found for {config.symbol}")

        # Initialize backtest engine
        engine = BacktestEngine(config)

        # Define simple buy-and-hold strategy for MVP
        def simple_strategy(bar: OHLCVBar, context: dict) -> str | None:
            """Simple buy-and-hold strategy: buy on first bar, hold until end."""
            bar_count = context.get("bar_count", 0)
            if bar_count == 1:  # First bar
                return "BUY"
            return None

        # Run backtest
        result = engine.run(bars, strategy_func=simple_strategy)

        # Update result with correct run_id
        result.backtest_run_id = run_id

        # Save to database
        repository = BacktestRepository(session)
        await repository.save_result(result)

        # Update in-memory tracking
        backtest_runs[run_id]["status"] = "COMPLETED"

        logger.info(
            "Backtest completed successfully",
            extra={
                "backtest_run_id": str(run_id),
                "total_trades": len(result.trades),
                "win_rate": float(result.summary.win_rate) if result.summary.win_rate else 0,
            },
        )

    except Exception as e:
        # Handle errors
        backtest_runs[run_id]["status"] = "FAILED"
        backtest_runs[run_id]["error"] = str(e)

        logger.error(
            "Backtest failed",
            extra={"backtest_run_id": str(run_id), "error": str(e)},
            exc_info=True,
        )


async def fetch_historical_bars(symbol: str, start_date: date, end_date: date) -> list[OHLCVBar]:
    """
    Fetch historical OHLCV bars for backtest.

    In production, this would query the OHLCV repository.
    For MVP, generates sample data.

    Args:
        symbol: Trading symbol
        start_date: Start date
        end_date: End date

    Returns:
        List of OHLCV bars
    """
    bars = []
    current_date = start_date

    # Generate daily bars
    while current_date <= end_date:
        timestamp = datetime.combine(current_date, datetime.min.time(), tzinfo=UTC)

        # Generate realistic-looking OHLCV data
        day_offset = (current_date - start_date).days
        base_price = Decimal("150.00") + Decimal(str(day_offset * 0.5))
        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe="1d",
                open=base_price,
                high=base_price + daily_range,
                low=base_price - daily_range,
                close=base_price + (daily_range * Decimal("0.3")),
                volume=1000000 + (day_offset * 10000),
                spread=daily_range,
                timestamp=timestamp,
            )
        )

        current_date += timedelta(days=1)

    return bars


# ============================================================================
# Story 12.4: Walk-Forward Testing Endpoints
# ============================================================================

# In-memory storage for walk-forward runs (MVP - replace with database in production)
walk_forward_runs: dict[UUID, dict] = {}


@router.post(
    "/walk-forward",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_walk_forward_test(
    config: WalkForwardConfig,
    session: AsyncSession = Depends(get_db),
):
    """
    Run walk-forward validation test.

    AC9 Subtask 9.1-9.5: Initiate walk-forward test as background task.

    This endpoint queues an asynchronous walk-forward test that validates
    system performance across multiple rolling windows.

    Args:
        config: Walk-forward configuration
        background_tasks: FastAPI background tasks for async execution
        session: Database session

    Returns:
        Response with walk_forward_id and status

    Raises:
        400 Bad Request: Invalid configuration
        503 Service Unavailable: Too many concurrent tests

    Example Response:
        {
            "walk_forward_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "RUNNING",
            "estimated_duration_seconds": 300
        }
    """
    from src.backtesting.walk_forward_engine import WalkForwardEngine
    from src.repositories.walk_forward_repository import WalkForwardRepository

    # Check for concurrent test limit (MVP: max 3 concurrent)
    running_tests = sum(1 for run in walk_forward_runs.values() if run["status"] == "RUNNING")
    if running_tests >= 3:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Walk-forward engine overloaded - too many concurrent tests. Please try again later.",
        )

    # Generate unique walk-forward ID
    walk_forward_id = uuid4()

    # Initialize walk-forward run tracking
    walk_forward_runs[walk_forward_id] = {
        "status": "RUNNING",
        "config": config,
        "created_at": datetime.now(UTC),
    }

    # Queue background task
    async def run_walk_forward():
        """Background task to execute walk-forward test."""
        try:
            engine = WalkForwardEngine()
            result = engine.walk_forward_test(config.symbols, config)

            # Save to database
            repository = WalkForwardRepository(session)
            await repository.save_result(result)

            # Update run tracking
            walk_forward_runs[walk_forward_id]["status"] = "COMPLETED"
            walk_forward_runs[walk_forward_id]["result"] = result

        except Exception as e:
            logger.error(f"Walk-forward test failed: {e}")
            walk_forward_runs[walk_forward_id]["status"] = "FAILED"
            walk_forward_runs[walk_forward_id]["error"] = str(e)

    asyncio.create_task(run_walk_forward())

    # Estimate duration: ~10 seconds per window, assume 10 windows
    estimated_duration = 100

    return {
        "walk_forward_id": str(walk_forward_id),
        "status": "RUNNING",
        "estimated_duration_seconds": estimated_duration,
    }


@router.get(
    "/walk-forward/{walk_forward_id}",
)
async def get_walk_forward_result(
    walk_forward_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get walk-forward test result by ID.

    AC9 Subtask 9.6-9.7: Retrieve walk-forward result.

    Args:
        walk_forward_id: UUID of the walk-forward test
        session: Database session

    Returns:
        WalkForwardResult if completed, status if running, 404 if not found

    Raises:
        404 Not Found: Walk-forward test not found

    Example Response (completed):
        {
            "walk_forward_id": "550e8400...",
            "windows": [...],
            "summary_statistics": {...},
            "stability_score": 0.15,
            "degradation_windows": [3, 7],
            "statistical_significance": {...},
            "chart_data": {...}
        }
    """
    from src.repositories.walk_forward_repository import WalkForwardRepository

    # Check in-memory storage first
    if walk_forward_id in walk_forward_runs:
        run_info = walk_forward_runs[walk_forward_id]

        if run_info["status"] == "RUNNING":
            return {
                "walk_forward_id": str(walk_forward_id),
                "status": "RUNNING",
            }
        elif run_info["status"] == "FAILED":
            return {
                "walk_forward_id": str(walk_forward_id),
                "status": "FAILED",
                "error": run_info.get("error"),
            }

    # Query database
    repository = WalkForwardRepository(session)
    result = await repository.get_result(walk_forward_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Walk-forward test {walk_forward_id} not found",
        )

    return result


@router.get(
    "/walk-forward",
)
async def list_walk_forward_results(
    limit: int = 10,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """
    List walk-forward results with pagination.

    AC9 Subtask 9.8: List results with pagination.

    Args:
        limit: Maximum number of results (default 10, max 100)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        List of WalkForwardResult objects

    Example Response:
        [
            {
                "walk_forward_id": "550e8400...",
                "windows": [...],
                "summary_statistics": {...},
                ...
            },
            ...
        ]
    """
    from src.repositories.walk_forward_repository import WalkForwardRepository

    # Validate pagination parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 10
    if offset < 0:
        offset = 0

    # Query database
    repository = WalkForwardRepository(session)
    results = await repository.list_results(limit=limit, offset=offset)

    return results


# ==============================================================================
# Story 12.7: Regression Testing Endpoints
# ==============================================================================

# In-memory storage for regression test runs
regression_test_runs: dict[UUID, dict] = {}


@router.post("/regression", status_code=status.HTTP_202_ACCEPTED)
async def run_regression_test(
    config: RegressionTestConfig,
    session: AsyncSession = Depends(get_db),
):
    """
    Run regression test across multiple symbols.

    Story 12.7 Task 11 Subtask 11.1-11.5:
    Executes regression test as background task and returns immediately with test_id.

    Args:
        config: RegressionTestConfig with symbols, date range, thresholds
        background_tasks: FastAPI background tasks
        session: Database session

    Returns:
        test_id and status: RUNNING

    Raises:
        400 Bad Request: Invalid config (empty symbols, invalid date range)
        503 Service Unavailable: Too many concurrent regression tests

    Example Request:
        {
            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "degradation_thresholds": {
                "win_rate": 5.0,
                "average_r_multiple": 10.0,
                "profit_factor": 15.0
            }
        }

    Example Response:
        {
            "test_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "RUNNING"
        }
    """

    # Validate config
    if not config.symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Config must include at least one symbol",
        )

    if config.start_date >= config.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    # Check concurrent test limit (max 3)
    running_tests = sum(1 for run in regression_test_runs.values() if run["status"] == "RUNNING")
    if running_tests >= 3:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Too many concurrent regression tests. Please try again later.",
        )

    # Generate test_id
    test_id = uuid4()

    # Initialize tracking
    regression_test_runs[test_id] = {
        "status": "RUNNING",
        "created_at": datetime.now(UTC),
        "error": None,
    }

    # Queue background task
    asyncio.create_task(
        run_regression_test_task(
            test_id,
            config,
            session,
        )
    )

    logger.info(
        "Regression test queued",
        extra={
            "test_id": str(test_id),
            "symbols": config.symbols,
            "start_date": str(config.start_date),
            "end_date": str(config.end_date),
        },
    )

    return {"test_id": test_id, "status": "RUNNING"}


async def run_regression_test_task(
    test_id: UUID,
    config: RegressionTestConfig,
    session: AsyncSession,
) -> None:
    """
    Background task to execute regression test.

    Args:
        test_id: Test identifier
        config: RegressionTestConfig
        session: Database session
    """
    from src.backtesting.regression_test_engine import RegressionTestEngine
    from src.repositories.regression_baseline_repository import (
        RegressionBaselineRepository,
    )
    from src.repositories.regression_test_repository import RegressionTestRepository

    try:
        logger.info("Starting regression test execution", extra={"test_id": str(test_id)})

        # Create repositories
        test_repo = RegressionTestRepository(session)
        baseline_repo = RegressionBaselineRepository(session)

        # Create engine
        engine = RegressionTestEngine(
            test_repository=test_repo,
            baseline_repository=baseline_repo,
        )

        # Run regression test
        result = await engine.run_regression_test(config)

        # Update status
        regression_test_runs[test_id]["status"] = result.status
        regression_test_runs[test_id]["result"] = result

        logger.info(
            "Regression test completed",
            extra={
                "test_id": str(test_id),
                "status": result.status,
                "regression_detected": result.regression_detected,
            },
        )

    except Exception as e:
        logger.error(
            "Regression test failed",
            extra={"test_id": str(test_id), "error": str(e)},
            exc_info=True,
        )
        regression_test_runs[test_id]["status"] = "FAILED"
        regression_test_runs[test_id]["error"] = str(e)


@router.get("/regression/{test_id}")
async def get_regression_test_result(
    test_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get regression test result by test_id.

    Story 12.7 Task 11 Subtask 11.6-11.7:
    Returns result if completed, RUNNING if in progress, 404 if not found.

    Args:
        test_id: Test identifier
        session: Database session

    Returns:
        RegressionTestResult if completed, status if running

    Raises:
        404 Not Found: Test not found

    Example Response (running):
        {
            "test_id": "550e8400...",
            "status": "RUNNING"
        }

    Example Response (completed):
        {
            "test_id": "550e8400...",
            "codebase_version": "abc123",
            "aggregate_metrics": {...},
            "per_symbol_results": {...},
            "baseline_comparison": {...},
            "regression_detected": false,
            "status": "PASS",
            ...
        }
    """
    from src.repositories.regression_test_repository import RegressionTestRepository

    # Check in-memory storage first
    if test_id in regression_test_runs:
        run_info = regression_test_runs[test_id]

        if run_info["status"] == "RUNNING":
            return {"test_id": test_id, "status": "RUNNING"}
        elif run_info["status"] == "FAILED":
            return {
                "test_id": test_id,
                "status": "FAILED",
                "error": run_info.get("error"),
            }

    # Query database
    repository = RegressionTestRepository(session)
    result = await repository.get_result(test_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regression test {test_id} not found",
        )

    return result


@router.get("/regression")
async def list_regression_test_results(
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    """
    List regression test results with pagination and filtering.

    Story 12.7 Task 11 Subtask 11.8-11.9:
    Returns paginated list of regression test results.

    Args:
        limit: Maximum results to return (default 50, max 100)
        offset: Number of results to skip (default 0)
        status_filter: Filter by status (PASS/FAIL/BASELINE_NOT_SET)
        session: Database session

    Returns:
        List of RegressionTestResult objects

    Example Response:
        [
            {
                "test_id": "550e8400...",
                "status": "PASS",
                "regression_detected": false,
                "test_run_time": "2024-01-15T02:00:00Z",
                ...
            },
            ...
        ]
    """
    from src.repositories.regression_test_repository import RegressionTestRepository

    # Validate pagination
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 50
    if offset < 0:
        offset = 0

    # Validate status filter
    if status_filter and status_filter not in ["PASS", "FAIL", "BASELINE_NOT_SET"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status_filter must be one of: PASS, FAIL, BASELINE_NOT_SET",
        )

    # Query database
    repository = RegressionTestRepository(session)
    results = await repository.list_results(limit=limit, offset=offset, status_filter=status_filter)

    return results


@router.post("/regression/{test_id}/establish-baseline")
async def establish_baseline_from_test(
    test_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Establish baseline from regression test result.

    Story 12.7 Task 11 Subtask 11.10-11.12:
    Creates new baseline from specified test result and marks it as current.

    Args:
        test_id: Test identifier to use as baseline
        session: Database session

    Returns:
        RegressionBaseline object

    Raises:
        404 Not Found: Test not found
        400 Bad Request: Test status not PASS

    Example Response:
        {
            "baseline_id": "660e8400...",
            "test_id": "550e8400...",
            "version": "abc123",
            "metrics": {...},
            "per_symbol_metrics": {...},
            "is_current": true,
            "established_at": "2024-01-15T02:00:00Z"
        }
    """
    from src.backtesting.regression_test_engine import RegressionTestEngine
    from src.repositories.regression_baseline_repository import (
        RegressionBaselineRepository,
    )
    from src.repositories.regression_test_repository import RegressionTestRepository

    # Get test result
    test_repo = RegressionTestRepository(session)
    result = await test_repo.get_result(test_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regression test {test_id} not found",
        )

    if result.status != "PASS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot establish baseline from test with status {result.status}. Only PASS tests can be used as baselines.",
        )

    # Create baseline repository
    baseline_repo = RegressionBaselineRepository(session)

    # Create engine
    engine = RegressionTestEngine(
        test_repository=test_repo,
        baseline_repository=baseline_repo,
    )

    # Establish baseline
    baseline = await engine.establish_baseline(result)

    logger.info(
        "Baseline established",
        extra={
            "baseline_id": str(baseline.baseline_id),
            "test_id": str(test_id),
            "version": baseline.version,
        },
    )

    return baseline


@router.get("/regression/baseline/current")
async def get_current_baseline(
    session: AsyncSession = Depends(get_db),
):
    """
    Get current active baseline.

    Story 12.7 Task 11 Subtask 11.13-11.14:
    Returns current baseline or 404 if not set.

    Args:
        session: Database session

    Returns:
        RegressionBaseline if exists

    Raises:
        404 Not Found: No current baseline set

    Example Response:
        {
            "baseline_id": "660e8400...",
            "test_id": "550e8400...",
            "version": "abc123",
            "metrics": {...},
            "per_symbol_metrics": {...},
            "is_current": true,
            "established_at": "2024-01-15T02:00:00Z"
        }
    """
    from src.repositories.regression_baseline_repository import (
        RegressionBaselineRepository,
    )

    repository = RegressionBaselineRepository(session)
    baseline = await repository.get_current_baseline()

    if baseline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current baseline set. Establish a baseline first.",
        )

    return baseline


@router.get("/regression/baseline/history")
async def list_baseline_history(
    limit: int = 10,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """
    List baseline history with pagination.

    Story 12.7 Task 11 Subtask 11.15-11.16:
    Returns paginated list of historical baselines.

    Args:
        limit: Maximum results to return (default 10, max 50)
        offset: Number of results to skip (default 0)
        session: Database session

    Returns:
        List of RegressionBaseline objects ordered by established_at DESC

    Example Response:
        [
            {
                "baseline_id": "660e8400...",
                "version": "abc123",
                "is_current": true,
                "established_at": "2024-01-15T02:00:00Z",
                ...
            },
            ...
        ]
    """
    from src.repositories.regression_baseline_repository import (
        RegressionBaselineRepository,
    )

    # Validate pagination
    if limit > 50:
        limit = 50
    if limit < 1:
        limit = 10
    if offset < 0:
        offset = 0

    # Query database
    repository = RegressionBaselineRepository(session)
    baselines = await repository.list_baselines(limit=limit, offset=offset)

    return baselines
