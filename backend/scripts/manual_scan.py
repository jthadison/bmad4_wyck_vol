#!/usr/bin/env python3
"""
Manual Signal Scanning Script

This script demonstrates how to manually trigger signal scanning via the API.
It provides two methods:
1. Direct API calls using curl/requests
2. Command-line interface for quick testing

Usage:
    # Scan a single symbol
    poetry run python scripts/manual_scan.py AAPL

    # Scan multiple symbols
    poetry run python scripts/manual_scan.py AAPL TSLA NVDA

    # Scan with different timeframe
    poetry run python scripts/manual_scan.py AAPL --timeframe 1h
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from src.config import settings
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.market_data.service import MarketDataService
from src.orchestrator.service import analyze_symbol

logger = structlog.get_logger(__name__)


async def fetch_and_scan_symbol(
    symbol: str,
    timeframe: str = "1d",
    lookback_days: int = 365,
) -> None:
    """
    Fetch market data and scan for signals.

    Args:
        symbol: Stock symbol to scan
        timeframe: Bar timeframe (default: 1d)
        lookback_days: How many days of historical data to fetch
    """
    print(f"\n{'='*60}")
    print(f"Scanning {symbol} on {timeframe} timeframe")
    print(f"{'='*60}\n")

    # Step 1: Fetch market data
    print(f"Step 1: Fetching {lookback_days} days of market data from Polygon...")
    try:
        adapter = PolygonAdapter(api_key=settings.polygon_api_key)
        service = MarketDataService(provider=adapter)

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        result = await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        if result.success:
            print("[OK] Data fetch successful!")
            print(f"   - Fetched: {result.total_fetched} bars")
            print(f"   - Inserted: {result.inserted} new bars")
            print(f"   - Duplicates: {result.duplicates} (skipped)")
            print(f"   - Rejected: {result.rejected}")
        else:
            print(f"[ERROR] Data fetch failed: {result.error_message}")
            return

    except Exception as e:
        print(f"[ERROR] Error fetching data: {e}")
        logger.exception("data_fetch_failed", symbol=symbol, error=str(e))
        return

    # Step 2: Run pattern analysis
    print("\nStep 2: Running Wyckoff pattern analysis...")
    try:
        signals = await analyze_symbol(symbol, timeframe)

        if signals:
            print(f"[OK] Found {len(signals)} trade signal(s)!\n")

            for i, signal in enumerate(signals, 1):
                print(f"Signal #{i}:")
                print(f"   Pattern: {signal.pattern_type}")
                print(f"   Phase: {signal.phase}")
                print(f"   Entry: ${signal.entry_price}")
                print(f"   Stop: ${signal.stop_price}")
                print(f"   Target: ${signal.target_price}")
                print(f"   R-Multiple: {signal.r_multiple}")
                print(f"   Confidence: {signal.confidence_score}%")
                print(f"   Position Size: {signal.position_size} shares")
                print(f"   Risk: ${signal.risk_amount}")
                print()
        else:
            print("[INFO] No trade signals found")
            print("   This is normal - Wyckoff patterns are relatively rare")
            print("   Try scanning more symbols or different timeframes")

    except Exception as e:
        print(f"[ERROR] Error analyzing symbol: {e}")
        logger.exception("analysis_failed", symbol=symbol, error=str(e))
        return

    print(f"\n{'='*60}\n")


async def scan_multiple_symbols(
    symbols: list[str],
    timeframe: str = "1d",
    lookback_days: int = 365,
) -> None:
    """Scan multiple symbols for signals."""
    print(f"\nScanning {len(symbols)} symbols: {', '.join(symbols)}\n")

    for symbol in symbols:
        await fetch_and_scan_symbol(symbol, timeframe, lookback_days)

    print("\n==> Scan complete!")


def print_api_usage_guide():
    """Print guide for using the API directly."""
    print("\n" + "=" * 60)
    print("API USAGE GUIDE - Manual Signal Scanning")
    print("=" * 60)

    print("\nAPI Endpoints:")
    print("-" * 60)

    print("\n1. Scan Single Symbol:")
    print("   GET /api/v1/orchestrator/analyze/{symbol}?timeframe=1d")
    print()
    print("   Example (curl):")
    print("   curl -X GET 'http://localhost:8000/api/v1/orchestrator/analyze/AAPL?timeframe=1d'")
    print()

    print("2. Scan Multiple Symbols:")
    print("   POST /api/v1/orchestrator/analyze")
    print('   Body: {"symbols": ["AAPL", "TSLA"], "timeframe": "1d"}')
    print()
    print("   Example (curl):")
    print("   curl -X POST 'http://localhost:8000/api/v1/orchestrator/analyze' \\")
    print("        -H 'Content-Type: application/json' \\")
    print('        -d \'{"symbols": ["AAPL", "TSLA", "NVDA"], "timeframe": "1d"}\'')
    print()

    print("3. Check Orchestrator Health:")
    print("   GET /api/v1/orchestrator/health")
    print()
    print("   Example (curl):")
    print("   curl http://localhost:8000/api/v1/orchestrator/health")
    print()

    print("\nVia Frontend:")
    print("-" * 60)
    print("   Open: http://localhost:5174")
    print("   Navigate to the Signals or Patterns page")
    print("   Use the UI to trigger scans")
    print()

    print("\nConfiguration:")
    print("-" * 60)
    print(f"   API Base URL: {settings.database_url}")
    print(f"   Polygon API: {'Configured' if settings.polygon_api_key else 'Missing'}")
    print()

    print("=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manual Signal Scanning Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan AAPL
  poetry run python scripts/manual_scan.py AAPL

  # Scan multiple symbols
  poetry run python scripts/manual_scan.py AAPL TSLA NVDA

  # Scan with custom timeframe
  poetry run python scripts/manual_scan.py AAPL --timeframe 1h

  # Scan with more historical data
  poetry run python scripts/manual_scan.py AAPL --lookback 730

  # Show API usage guide
  poetry run python scripts/manual_scan.py --help-api
        """,
    )

    parser.add_argument(
        "symbols",
        nargs="*",
        help="Stock symbols to scan (e.g., AAPL TSLA NVDA)",
    )
    parser.add_argument(
        "--timeframe",
        "-t",
        default="1d",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        help="Bar timeframe (default: 1d)",
    )
    parser.add_argument(
        "--lookback",
        "-l",
        type=int,
        default=365,
        help="Days of historical data to fetch (default: 365)",
    )
    parser.add_argument(
        "--help-api",
        action="store_true",
        help="Show API usage guide instead of scanning",
    )

    args = parser.parse_args()

    # Show API usage guide
    if args.help_api:
        print_api_usage_guide()
        return

    # Require at least one symbol
    if not args.symbols:
        parser.print_help()
        print("\n[ERROR] Please provide at least one symbol to scan")
        print("   Example: poetry run python scripts/manual_scan.py AAPL")
        sys.exit(1)

    # Validate Polygon API key
    if not settings.polygon_api_key:
        print("\n[ERROR] POLYGON_API_KEY not configured in .env")
        print("   Please add your Polygon.io API key to the .env file")
        sys.exit(1)

    # Run the scan
    asyncio.run(
        scan_multiple_symbols(
            symbols=args.symbols,
            timeframe=args.timeframe,
            lookback_days=args.lookback,
        )
    )


if __name__ == "__main__":
    main()
