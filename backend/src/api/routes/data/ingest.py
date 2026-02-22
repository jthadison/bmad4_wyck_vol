"""
Historical data ingestion endpoint for BMAD Wyckoff system.

This module provides REST API for loading historical OHLCV data into the database
using configured market data providers (Polygon, Alpaca, Yahoo).

Story 25.5: Historical Data Ingestion Bootstrap
"""

from __future__ import annotations

from datetime import date

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.config import settings
from src.market_data.factory import MarketDataProviderFactory
from src.market_data.service import MarketDataService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/data", tags=["data"])


class IngestRequest(BaseModel):
    """
    Request model for historical data ingestion.

    Attributes:
        symbol: Stock symbol (e.g., "AAPL", "SPY")
        timeframe: Bar timeframe (e.g., "1d", "1h", "5m")
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        asset_class: Optional asset class for symbol formatting
            (e.g., "stock", "forex", "index", "crypto"). Defaults to "stock".
    """

    symbol: str = Field(..., description="Stock symbol (e.g., 'AAPL')")
    timeframe: str = Field(default="1d", description="Bar timeframe (e.g., '1d', '1h', '5m')")
    start_date: date = Field(..., description="Start date (inclusive, YYYY-MM-DD)")
    end_date: date = Field(..., description="End date (inclusive, YYYY-MM-DD)")
    asset_class: str | None = Field(
        default=None,
        description="Asset class: 'stock', 'forex', 'index', 'crypto'. None defaults to stock.",
    )


class IngestResponse(BaseModel):
    """
    Response model for historical data ingestion.

    Attributes:
        bars_fetched: Number of bars fetched from provider
        bars_inserted: Number of bars inserted into database (duplicates excluded)
        symbol: Stock symbol
        timeframe: Bar timeframe
        date_range: Date range ingested (start and end dates)
    """

    bars_fetched: int = Field(..., description="Number of bars fetched from provider")
    bars_inserted: int = Field(..., description="Number of bars inserted (duplicates excluded)")
    symbol: str = Field(..., description="Stock symbol")
    timeframe: str = Field(..., description="Bar timeframe")
    date_range: dict[str, str] = Field(..., description="Date range ingested (start and end dates)")


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest historical OHLCV data",
    description=(
        "Fetch and store historical OHLCV bars from configured market data provider. "
        "Duplicate bars are automatically excluded. Provider errors return HTTP 422."
    ),
)
async def ingest_historical_data(request: IngestRequest) -> IngestResponse:
    """
    Ingest historical OHLCV data for a symbol.

    Fetches bars from the configured market data provider (Polygon.io by default)
    and stores them in the database. Duplicate bars are automatically excluded
    via upsert logic in the repository layer.

    Args:
        request: Ingestion request with symbol, timeframe, and date range

    Returns:
        IngestResponse with summary statistics

    Raises:
        HTTPException 422: Provider authentication failure or API error
        HTTPException 500: Unexpected server error

    Example:
        ```json
        POST /api/v1/data/ingest
        {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
        ```

        Response:
        ```json
        {
            "bars_fetched": 252,
            "bars_inserted": 252,
            "symbol": "AAPL",
            "timeframe": "1d",
            "date_range": {
                "start": "2024-01-01",
                "end": "2024-12-31"
            }
        }
        ```
    """
    log = logger.bind(
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=str(request.start_date),
        end_date=str(request.end_date),
    )

    log.info("ingest_request_received")

    try:
        # Create market data provider via factory (Story 25.6)
        # Uses DEFAULT_PROVIDER from settings (defaults to Polygon)
        factory = MarketDataProviderFactory(settings)
        provider = factory.get_historical_provider()

        # Create market data service
        service = MarketDataService(provider=provider)

        # Ingest historical data
        log.info("ingest_started")
        result = await service.ingest_historical_data(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe,
            asset_class=request.asset_class,
        )

        # Check for provider/service errors
        if not result.success:
            error_msg = result.error_message or "Unknown error"
            log.error("ingest_failed", error=error_msg)

            # If error contains authentication keywords, return 422
            if any(
                keyword in error_msg.lower()
                for keyword in ["auth", "api key", "invalid", "unauthorized"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "provider": "Polygon.io",
                        "error": error_msg,
                        "message": "Provider authentication or API error",
                    },
                )

            # Otherwise generic 500 error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": error_msg, "message": "Data ingestion failed"},
            )

        log.info(
            "ingest_complete",
            bars_fetched=result.total_fetched,
            bars_inserted=result.inserted,
            duplicates_skipped=result.duplicates,
        )

        # Build response
        response = IngestResponse(
            bars_fetched=result.total_fetched,
            bars_inserted=result.inserted,
            symbol=request.symbol,
            timeframe=request.timeframe,
            date_range={
                "start": request.start_date.isoformat(),
                "end": request.end_date.isoformat(),
            },
        )

        return response

    except HTTPException:
        # Re-raise FastAPI HTTPExceptions
        raise

    except RuntimeError as e:
        # Provider errors (Polygon auth failures, rate limits, etc.)
        error_msg = str(e)
        log.error("provider_error", error=error_msg)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "provider": "Polygon.io",
                "error": error_msg,
                "message": "Market data provider error",
            },
        ) from e

    except Exception as e:
        # Unexpected errors
        error_msg = f"{type(e).__name__}: {str(e)}"
        log.error("ingest_unexpected_error", error=error_msg)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": error_msg, "message": "Unexpected server error"},
        ) from e
