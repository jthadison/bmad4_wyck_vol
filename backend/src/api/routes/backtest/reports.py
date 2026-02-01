"""
Backtest report export endpoints.

Story 12.6B Endpoints:
- GET /results/{backtest_run_id}/report/html: Generate HTML report
- GET /results/{backtest_run_id}/report/pdf: Generate PDF report
- GET /results/{backtest_run_id}/trades/csv: Export trade list as CSV
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.repositories.backtest_repository import BacktestRepository

router = APIRouter()
logger = logging.getLogger(__name__)


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
