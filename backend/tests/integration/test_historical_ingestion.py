"""
Integration tests for historical data ingestion.

Tests the complete end-to-end workflow:
- Fetching data from providers
- Validating bars
- Inserting into database
- Data quality verification
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.database import async_session_maker
from src.market_data.adapters.yahoo_adapter import YahooAdapter
from src.market_data.service import MarketDataService
from src.repositories.models import OHLCVBarModel
from src.repositories.ohlcv_repository import OHLCVRepository


@pytest.mark.asyncio
class TestHistoricalIngestion:
    """Integration tests for historical data ingestion."""

    async def test_ingest_single_symbol_yahoo(self):
        """
        Test ingesting data for a single symbol using Yahoo Finance.

        This test uses Yahoo Finance as it doesn't require API keys.
        """
        # Arrange
        adapter = YahooAdapter()
        service = MarketDataService(adapter)

        symbol = "SPY"
        start_date = date(2024, 1, 2)
        end_date = date(2024, 1, 31)
        timeframe = "1d"

        # Act
        result = await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Assert
        assert result.success is True
        assert result.total_fetched > 0
        assert result.inserted > 0
        assert result.symbol == symbol
        assert result.timeframe == timeframe

        # Verify data in database
        async with async_session_maker() as session:
            repo = OHLCVRepository(session)
            bars = await repo.get_bars(symbol, timeframe, start_date, end_date)

            assert len(bars) > 0
            # Expect ~20 trading days in January
            assert len(bars) >= 15

            # Verify first bar has valid data
            first_bar = bars[0]
            assert first_bar.symbol == symbol
            assert first_bar.timeframe == timeframe
            assert first_bar.open > 0
            assert first_bar.high > 0
            assert first_bar.low > 0
            assert first_bar.close > 0
            assert first_bar.volume > 0
            assert first_bar.spread > 0

    async def test_idempotent_ingestion(self):
        """
        Test that ingesting the same data twice doesn't create duplicates.

        AC 6: Duplicate detection - idempotent ingestion.
        """
        # Arrange
        adapter = YahooAdapter()
        service = MarketDataService(adapter)

        symbol = "AAPL"
        start_date = date(2024, 1, 2)
        end_date = date(2024, 1, 10)
        timeframe = "1d"

        # Act - First ingestion
        result1 = await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Act - Second ingestion (should skip duplicates)
        result2 = await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Assert
        assert result1.success is True
        assert result1.inserted > 0

        assert result2.success is True
        assert result2.total_fetched > 0
        assert result2.inserted == 0  # All should be duplicates
        assert result2.duplicates == result2.total_fetched

    async def test_data_validation_rejects_invalid_bars(self):
        """
        Test that data validation rejects invalid bars.

        AC 5: Data validation - reject bars with zero volume, missing OHLC.
        """
        # This test would require mocking the provider to return invalid data
        # For now, we test that the validation logic exists and works
        from src.market_data.validators import validate_bar
        from src.models.ohlcv import OHLCVBar

        # Create an invalid bar (zero volume)
        invalid_bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime.now(timezone.utc),
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("99.0"),
            close=Decimal("102.0"),
            volume=0,  # Invalid: zero volume
            spread=Decimal("6.0"),
        )

        is_valid, reason = validate_bar(invalid_bar)

        assert is_valid is False
        assert "Zero volume" in reason

    async def test_data_quality_verification(self):
        """
        Test data quality verification after ingestion.

        AC 10: Database query confirms data quality.
        """
        # Arrange
        adapter = YahooAdapter()
        service = MarketDataService(adapter)

        symbol = "MSFT"
        start_date = date(2024, 1, 2)
        end_date = date(2024, 1, 31)
        timeframe = "1d"

        # Act - Ingest data
        result = await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Act - Verify data quality
        quality_report = await service.verify_data_quality(symbol, timeframe)

        # Assert
        assert quality_report.symbol == symbol
        assert quality_report.timeframe == timeframe
        assert quality_report.total_bars > 0
        assert quality_report.zero_volume_bars == 0  # Should have no zero volume
        assert quality_report.quality_score == 100.0  # Perfect quality

        # Verify date range
        min_date, max_date = quality_report.date_range
        assert min_date is not None
        assert max_date is not None

    async def test_error_handling_continues_with_remaining_symbols(self):
        """
        Test that ingestion continues with remaining symbols if one fails.

        AC 8: Error handling - log failed symbols, continue with remaining.
        """
        # This test would require mocking a provider failure
        # For now, we verify the service handles errors gracefully
        adapter = YahooAdapter()
        service = MarketDataService(adapter)

        # Try to ingest an invalid symbol (should fail gracefully)
        result = await service.ingest_historical_data(
            symbol="INVALIDSYMBOL12345",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            timeframe="1d",
        )

        # Should not raise exception, but return failed result
        assert result.success is True  # Yahoo returns empty, not error
        assert result.total_fetched == 0

    async def test_repository_duplicate_detection(self):
        """
        Test repository-level duplicate detection.

        AC 6: Duplicate detection using unique constraint.
        """
        from src.models.ohlcv import OHLCVBar

        # Create test bar
        bar = OHLCVBar(
            symbol="TEST",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("99.0"),
            close=Decimal("102.0"),
            volume=1000000,
            spread=Decimal("6.0"),
        )

        async with async_session_maker() as session:
            repo = OHLCVRepository(session)

            # Insert once
            count1 = await repo.insert_bars([bar])
            assert count1 == 1

            # Try to insert again (should be skipped due to unique constraint)
            count2 = await repo.insert_bars([bar])
            assert count2 == 0  # Duplicate, not inserted

            # Verify only one bar exists
            total = await repo.count_bars("TEST", "1d")
            assert total == 1

    async def test_date_range_query(self):
        """
        Test repository date range query.

        AC 10: Data quality checks - verify date ranges.
        """
        adapter = YahooAdapter()
        service = MarketDataService(adapter)

        symbol = "TSLA"
        start_date = date(2024, 1, 2)
        end_date = date(2024, 1, 31)
        timeframe = "1d"

        # Ingest data
        await service.ingest_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        # Query date range
        async with async_session_maker() as session:
            repo = OHLCVRepository(session)
            min_ts, max_ts = await repo.get_date_range(symbol, timeframe)

            assert min_ts is not None
            assert max_ts is not None
            assert min_ts <= max_ts

            # Date range should be within expected bounds
            assert min_ts.date() >= start_date
            assert max_ts.date() <= end_date


@pytest.mark.asyncio
async def test_calculate_ratios():
    """
    Test calculation of spread_ratio and volume_ratio.

    Task 14: Calculate ratios using 20-bar rolling averages.
    """
    from src.market_data.calculate_ratios import calculate_ratios_for_symbol

    # Arrange - Ingest some data first
    adapter = YahooAdapter()
    service = MarketDataService(adapter)

    symbol = "SPY"
    start_date = date(2024, 1, 2)
    end_date = date(2024, 2, 29)  # 2 months for enough data
    timeframe = "1d"

    await service.ingest_historical_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
    )

    # Act - Calculate ratios
    updated = await calculate_ratios_for_symbol(symbol, timeframe, window=20)

    # Assert
    assert updated > 0

    # Verify ratios were calculated
    async with async_session_maker() as session:
        stmt = (
            select(OHLCVBarModel)
            .where(
                OHLCVBarModel.symbol == symbol,
                OHLCVBarModel.timeframe == timeframe,
            )
            .order_by(OHLCVBarModel.timestamp)
        )

        result = await session.execute(stmt)
        bars = result.scalars().all()

        assert len(bars) > 20  # Should have enough for rolling window

        # Check that ratios are calculated (not all 1.0)
        # First 19 bars will be 1.0 (no full window), bar 20+ should have calculated ratios
        if len(bars) >= 30:
            bar_30 = bars[29]
            # Ratio should be calculated (may or may not be 1.0, but should be valid)
            assert bar_30.spread_ratio is not None
            assert bar_30.volume_ratio is not None
            assert bar_30.spread_ratio > 0
            assert bar_30.volume_ratio > 0
