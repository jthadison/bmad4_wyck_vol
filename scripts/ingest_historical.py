#!/usr/bin/env python3
"""
Historical data ingestion CLI script for BMAD Wyckoff system.

Usage:
    python scripts/ingest_historical.py --symbol AAPL --days 365
    python scripts/ingest_historical.py --symbol SPY --timeframe 1h --days 90

Story 25.5: Historical Data Ingestion Bootstrap
"""

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Add backend/src to Python path for imports
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import structlog

from config import settings
from market_data.adapters.polygon_adapter import PolygonAdapter
from market_data.service import MarketDataService

logger = structlog.get_logger(__name__)


async def ingest_historical_data(
    symbol: str,
    timeframe: str,
    days: int,
    asset_class: str | None = None,
) -> int:
    """
    Ingest historical data for a symbol.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        timeframe: Bar timeframe (e.g., "1d", "1h", "5m")
        days: Number of days of historical data to fetch
        asset_class: Optional asset class for symbol formatting

    Returns:
        Exit code (0 = success, 1 = error)
    """
    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    log = logger.bind(
        symbol=symbol,
        timeframe=timeframe,
        start_date=str(start_date),
        end_date=str(end_date),
        days=days,
    )

    log.info("ingest_started")

    try:
        # Create market data provider (Polygon.io)
        provider = PolygonAdapter(api_key=settings.polygon_api_key)

        # Create market data service
        service = MarketDataService(provider=provider)

        # Ingest historical data
        result = await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            asset_class=asset_class,
        )

        # Check result
        if not result.success:
            error_msg = result.error_message or "Unknown error"
            log.error("ingest_failed", error=error_msg)
            print(f"ERROR: {error_msg}", file=sys.stderr)
            return 1

        # Print success summary
        print(
            f"Inserted {result.inserted} bars for {symbol} ({timeframe})",
            flush=True,
        )

        log.info(
            "ingest_complete",
            bars_fetched=result.total_fetched,
            bars_inserted=result.inserted,
            duplicates_skipped=result.duplicates,
            rejected=result.rejected,
        )

        return 0

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        log.error("ingest_error", error=error_msg)
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return 1


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Ingest historical OHLCV data for a symbol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/ingest_historical.py --symbol AAPL --days 365
  python scripts/ingest_historical.py --symbol SPY --timeframe 1h --days 90
  python scripts/ingest_historical.py --symbol EURUSD --asset-class forex --days 180
        """,
    )

    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Stock symbol to ingest (e.g., AAPL, SPY)",
    )

    parser.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        help="Bar timeframe (default: 1d). Supported: 1m, 5m, 15m, 1h, 4h, 1d",
    )

    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="Number of days of historical data to fetch",
    )

    parser.add_argument(
        "--asset-class",
        type=str,
        default=None,
        choices=["stock", "forex", "index", "crypto"],
        help="Asset class for symbol formatting (default: stock)",
    )

    args = parser.parse_args()

    # Validate days
    if args.days <= 0:
        print("ERROR: --days must be positive", file=sys.stderr)
        return 1

    # Run ingestion
    try:
        exit_code = asyncio.run(
            ingest_historical_data(
                symbol=args.symbol,
                timeframe=args.timeframe,
                days=args.days,
                asset_class=args.asset_class,
            )
        )
        return exit_code
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
