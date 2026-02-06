"""
CLI command for ingesting historical market data.

This module provides the `wyckoff ingest` command for fetching and storing
historical OHLCV data from various market data providers.
"""

from __future__ import annotations

import asyncio
import uuid

import click
import structlog

from src.config import settings
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.market_data.adapters.yahoo_adapter import YahooAdapter
from src.market_data.service import MarketDataService

logger = structlog.get_logger(__name__)


@click.group()
def cli():
    """BMAD Wyckoff CLI tool."""
    pass


@cli.command()
@click.option(
    "--symbol",
    "-s",
    multiple=True,
    required=True,
    help="Stock symbol(s) to ingest (can specify multiple)",
)
@click.option(
    "--start",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--timeframe",
    default="1d",
    type=click.Choice(["1m", "5m", "15m", "1h", "1d"]),
    help="Bar timeframe (default: 1d)",
)
@click.option(
    "--provider",
    default=None,
    type=click.Choice(["polygon", "yahoo"]),
    help="Market data provider (default: from settings)",
)
@click.option(
    "--asset-class",
    default=None,
    type=click.Choice(["stock", "forex", "index", "crypto"]),
    help="Asset class for provider-specific symbol formatting (default: stock)",
)
def ingest(symbol, start, end, timeframe, provider, asset_class):
    """
    Ingest historical OHLCV data for backtesting.

    Example:
        wyckoff ingest --symbol AAPL --start 2020-01-01 --end 2024-12-31

    Multiple symbols:
        wyckoff ingest -s AAPL -s MSFT -s TSLA --start 2020-01-01 --end 2024-12-31
    """
    asyncio.run(ingest_async(symbol, start, end, timeframe, provider, asset_class))


async def ingest_async(symbols, start, end, timeframe, provider, asset_class):
    """
    Async implementation of ingest command.

    Args:
        symbols: Tuple of symbol strings
        start: Start datetime
        end: End datetime
        timeframe: Bar timeframe
        provider: Provider name (or None for default)
        asset_class: Asset class for symbol formatting (or None for default)
    """
    # Generate correlation ID for this ingestion run
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)

    # Convert datetime to date
    start_date = start.date()
    end_date = end.date()

    # Select provider
    provider_name = provider or settings.default_provider

    log.info(
        "ingestion_started",
        symbols=list(symbols),
        start_date=str(start_date),
        end_date=str(end_date),
        timeframe=timeframe,
        provider=provider_name,
        message=f"Starting ingestion for {len(symbols)} symbols using {provider_name}",
    )

    click.echo(f"\n{'='*60}")
    click.echo("BMAD Wyckoff Historical Data Ingestion")
    click.echo(f"{'='*60}")
    click.echo(f"Provider: {provider_name}")
    click.echo(f"Symbols: {', '.join(symbols)}")
    click.echo(f"Date Range: {start_date} to {end_date}")
    click.echo(f"Timeframe: {timeframe}")
    click.echo(f"{'='*60}\n")

    # Create provider
    if provider_name == "polygon":
        data_provider = PolygonAdapter()
    elif provider_name == "yahoo":
        data_provider = YahooAdapter()
    else:
        click.echo(f"Error: Unsupported provider '{provider_name}'", err=True)
        return

    # Create service
    service = MarketDataService(data_provider)

    # Track statistics
    total_symbols = len(symbols)
    successful_symbols = []
    failed_symbols = []
    total_bars_fetched = 0
    total_bars_inserted = 0
    total_duplicates = 0
    total_rejected = 0

    # Ingest each symbol
    with click.progressbar(
        symbols,
        label="Ingesting symbols",
        length=total_symbols,
    ) as bar:
        for idx, sym in enumerate(bar, start=1):
            symbol_log = log.bind(symbol=sym)

            try:
                # Calculate progress percentage
                progress_pct = (idx / total_symbols) * 100

                click.echo(f"\n[{idx}/{total_symbols}] Processing {sym}...")

                # Ingest symbol
                result = await service.ingest_historical_data(
                    symbol=sym,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    asset_class=asset_class,
                )

                # Update statistics
                total_bars_fetched += result.total_fetched
                total_bars_inserted += result.inserted
                total_duplicates += result.duplicates
                total_rejected += result.rejected

                if result.success:
                    successful_symbols.append(sym)
                    click.echo(
                        f"  ✓ Fetched {result.total_fetched} bars, "
                        f"inserted {result.inserted}, "
                        f"duplicates {result.duplicates}, "
                        f"rejected {result.rejected}"
                    )
                    click.echo(f"  Progress: {progress_pct:.1f}% complete")

                    symbol_log.info(
                        "symbol_ingestion_success",
                        total_fetched=result.total_fetched,
                        inserted=result.inserted,
                        duplicates=result.duplicates,
                        rejected=result.rejected,
                    )
                else:
                    failed_symbols.append((sym, result.error_message))
                    click.echo(f"  ✗ Failed: {result.error_message}", err=True)

                    symbol_log.error(
                        "symbol_ingestion_failed",
                        error=result.error_message,
                    )

            except Exception as e:
                failed_symbols.append((sym, str(e)))
                click.echo(f"  ✗ Exception: {str(e)}", err=True)

                symbol_log.error(
                    "symbol_ingestion_exception",
                    error=str(e),
                    error_type=type(e).__name__,
                )

    # Print final summary
    click.echo(f"\n{'='*60}")
    click.echo("Ingestion Summary")
    click.echo(f"{'='*60}")
    click.echo(f"Total Symbols: {total_symbols}")
    click.echo(f"Successful: {len(successful_symbols)}")
    click.echo(f"Failed: {len(failed_symbols)}")
    click.echo("\nData Statistics:")
    click.echo(f"  Total Bars Fetched: {total_bars_fetched:,}")
    click.echo(f"  Total Bars Inserted: {total_bars_inserted:,}")
    click.echo(f"  Duplicates Skipped: {total_duplicates:,}")
    click.echo(f"  Bars Rejected: {total_rejected:,}")

    if successful_symbols:
        click.echo(f"\n✓ Successfully ingested: {', '.join(successful_symbols)}")

    if failed_symbols:
        click.echo("\n✗ Failed symbols:")
        for sym, error in failed_symbols:
            click.echo(f"  - {sym}: {error}")

    click.echo(f"{'='*60}\n")

    # Log final summary
    log.info(
        "ingestion_complete",
        total_symbols=total_symbols,
        successful=len(successful_symbols),
        failed=len(failed_symbols),
        total_fetched=total_bars_fetched,
        total_inserted=total_bars_inserted,
        duplicates=total_duplicates,
        rejected=total_rejected,
    )

    # Close provider if needed
    if hasattr(data_provider, "close"):
        await data_provider.close()


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
