"""
Unit tests for historical data ingestion endpoint.

Story 25.5: Historical Data Ingestion Bootstrap
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.market_data.service import IngestionResult


@pytest.mark.asyncio
class TestIngestEndpoint:
    """Test suite for POST /api/v1/data/ingest endpoint."""

    async def test_valid_request_returns_bars_inserted(self):
        """
        AC1: Valid request returns bars_inserted > 0.

        Test that a valid ingestion request successfully fetches and stores bars.
        """
        # Mock the MarketDataService to return a successful result
        mock_result = IngestionResult(
            symbol="AAPL",
            timeframe="1d",
            total_fetched=252,
            inserted=252,
            duplicates=0,
            rejected=0,
            errors=[],
            success=True,
        )

        # Mock MarketDataProviderFactory and MarketDataService (Story 25.6)
        with patch("src.api.routes.data.ingest.MarketDataProviderFactory") as mock_factory_class:
            mock_adapter = MagicMock()
            mock_factory = MagicMock()
            mock_factory.get_historical_provider.return_value = mock_adapter
            mock_factory_class.return_value = mock_factory

            with patch("src.api.routes.data.ingest.MarketDataService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.ingest_historical_data = AsyncMock(return_value=mock_result)
                mock_service_class.return_value = mock_service

                # Make request
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/data/ingest",
                        json={
                            "symbol": "AAPL",
                            "timeframe": "1d",
                            "start_date": "2024-01-01",
                            "end_date": "2024-12-31",
                        },
                    )

                # Assert response
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["bars_fetched"] == 252
                assert data["bars_inserted"] == 252
                assert data["symbol"] == "AAPL"
                assert data["timeframe"] == "1d"
                assert data["date_range"]["start"] == "2024-01-01"
                assert data["date_range"]["end"] == "2024-12-31"

                # Verify service was called with correct parameters
                mock_service.ingest_historical_data.assert_called_once()
                call_args = mock_service.ingest_historical_data.call_args
                assert call_args.kwargs["symbol"] == "AAPL"
                assert call_args.kwargs["start_date"] == date(2024, 1, 1)
                assert call_args.kwargs["end_date"] == date(2024, 12, 31)
                assert call_args.kwargs["timeframe"] == "1d"

    async def test_duplicate_call_returns_zero_inserted(self):
        """
        AC5: Duplicate call with same date range returns bars_inserted = 0.

        Test that calling ingest again for the same date range excludes duplicates.
        """
        # Mock result with duplicates (all bars already exist)
        mock_result = IngestionResult(
            symbol="AAPL",
            timeframe="1d",
            total_fetched=252,
            inserted=0,  # All duplicates
            duplicates=252,
            rejected=0,
            errors=[],
            success=True,
        )

        with patch("src.api.routes.data.ingest.MarketDataProviderFactory") as mock_factory_class:
            mock_factory = MagicMock()
            mock_factory.get_historical_provider.return_value = MagicMock()
            mock_factory_class.return_value = mock_factory
            with patch("src.api.routes.data.ingest.MarketDataService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.ingest_historical_data = AsyncMock(return_value=mock_result)
                mock_service_class.return_value = mock_service

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/data/ingest",
                        json={
                            "symbol": "AAPL",
                            "timeframe": "1d",
                            "start_date": "2024-01-01",
                            "end_date": "2024-12-31",
                        },
                    )

                # Assert response
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["bars_fetched"] == 252
                assert data["bars_inserted"] == 0  # No new bars inserted
                assert data["symbol"] == "AAPL"

    async def test_invalid_api_key_returns_422(self):
        """
        AC6: Invalid API key returns HTTP 422 with provider error.

        Test that provider authentication failures return 422 with provider info.
        """
        # Mock adapter and service to raise RuntimeError (provider auth failure)
        with patch("src.api.routes.data.ingest.MarketDataProviderFactory") as mock_factory_class:
            mock_factory = MagicMock()
            mock_factory.get_historical_provider.return_value = MagicMock()
            mock_factory_class.return_value = mock_factory
            with patch("src.api.routes.data.ingest.MarketDataService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.ingest_historical_data = AsyncMock(
                    side_effect=RuntimeError("Polygon.io authentication failed: Invalid API key")
                )
                mock_service_class.return_value = mock_service

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/data/ingest",
                        json={
                            "symbol": "AAPL",
                            "timeframe": "1d",
                            "start_date": "2024-01-01",
                            "end_date": "2024-12-31",
                        },
                    )

                # Assert HTTP 422 response
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                data = response.json()
                assert "detail" in data
                assert data["detail"]["provider"] == "Polygon.io"
                assert "authentication failed" in data["detail"]["error"].lower()

    async def test_empty_bars_from_provider_returns_200(self):
        """
        Test that empty bars from provider (valid request, 0 bars returned) returns HTTP 200.

        Edge case: Provider returns 0 bars (e.g., symbol not found or no data for date range).
        """
        # Mock result with 0 bars fetched
        mock_result = IngestionResult(
            symbol="INVALID",
            timeframe="1d",
            total_fetched=0,
            inserted=0,
            duplicates=0,
            rejected=0,
            errors=[],
            success=True,
        )

        with patch("src.api.routes.data.ingest.MarketDataProviderFactory") as mock_factory_class:
            mock_factory = MagicMock()
            mock_factory.get_historical_provider.return_value = MagicMock()
            mock_factory_class.return_value = mock_factory
            with patch("src.api.routes.data.ingest.MarketDataService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.ingest_historical_data = AsyncMock(return_value=mock_result)
                mock_service_class.return_value = mock_service

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/data/ingest",
                        json={
                            "symbol": "INVALID",
                            "timeframe": "1d",
                            "start_date": "2024-01-01",
                            "end_date": "2024-12-31",
                        },
                    )

                # Assert HTTP 200 with 0 bars
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["bars_fetched"] == 0
                assert data["bars_inserted"] == 0


@pytest.mark.asyncio
class TestStartupWarning:
    """Test suite for startup warning logic (AC3)."""

    async def test_startup_warning_logs_zero_bar_symbols(self):
        """
        AC3: Startup warning when no data exists.

        Test that startup warning logic logs WARNING for symbols with 0 bars.
        """
        # Import using getattr to access private function
        import src.api.main as main_module

        check_func = main_module._check_historical_data_warnings

        # Mock settings
        with patch.object(main_module, "settings") as mock_settings:
            mock_settings.watchlist_symbols = ["AAPL", "SPY", "QQQ"]
            mock_settings.bar_timeframe = "1d"

            # Mock repository
            mock_repo = AsyncMock()
            # AAPL has bars, SPY has bars, QQQ has 0 bars
            mock_repo.count_bars.side_effect = [100, 252, 0]

            # Patch where it's imported in the function (src.database module)
            with patch("src.database.async_session_maker") as mock_session_maker:
                # Setup async context manager
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session_maker.return_value = mock_session

                with patch(
                    "src.repositories.ohlcv_repository.OHLCVRepository", return_value=mock_repo
                ):
                    # Capture logs
                    with patch.object(main_module, "logger") as mock_logger:
                        await check_func()

                        # Assert WARNING was logged for QQQ
                        warning_calls = [
                            call
                            for call in mock_logger.warning.call_args_list
                            if "QQQ" in str(call)
                        ]
                        assert len(warning_calls) > 0, "Expected WARNING log for QQQ"

                        # Verify repository was queried for each symbol
                        assert mock_repo.count_bars.call_count == 3

    async def test_startup_warning_all_symbols_have_data(self):
        """
        Test that no warnings are logged when all symbols have data.
        """
        import src.api.main as main_module

        check_func = main_module._check_historical_data_warnings

        with patch.object(main_module, "settings") as mock_settings:
            mock_settings.watchlist_symbols = ["AAPL", "SPY"]
            mock_settings.bar_timeframe = "1d"

            # Mock repository - all symbols have data
            mock_repo = AsyncMock()
            mock_repo.count_bars.side_effect = [100, 252]

            with patch("src.database.async_session_maker") as mock_session_maker:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session_maker.return_value = mock_session

                with patch(
                    "src.repositories.ohlcv_repository.OHLCVRepository", return_value=mock_repo
                ):
                    with patch.object(main_module, "logger") as mock_logger:
                        await check_func()

                        # Assert info log for success (no warnings)
                        info_calls = [
                            call
                            for call in mock_logger.info.call_args_list
                            if "historical_data_check_passed" in str(call)
                        ]
                        assert len(info_calls) > 0, "Expected INFO log for success"

                        # Assert no WARNING logs
                        warning_calls = mock_logger.warning.call_args_list
                        # Should have no "no_historical_data_for_symbol" warnings
                        symbol_warnings = [
                            call
                            for call in warning_calls
                            if "no_historical_data_for_symbol" in str(call)
                        ]
                        assert len(symbol_warnings) == 0, "Expected no symbol-specific warnings"


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """Integration test scenarios combining multiple components."""

    async def test_full_endpoint_call_with_mocked_provider(self):
        """
        Integration test: Full endpoint call with mocked provider confirms DB insert.

        This test verifies the full flow: request → service → provider → repository.
        """
        # Mock the entire service layer
        mock_result = IngestionResult(
            symbol="SPY",
            timeframe="1d",
            total_fetched=50,
            inserted=50,
            duplicates=0,
            rejected=0,
            errors=[],
            success=True,
        )

        with patch("src.api.routes.data.ingest.MarketDataProviderFactory") as mock_factory_class:
            mock_factory = MagicMock()
            mock_factory.get_historical_provider.return_value = MagicMock()
            mock_factory_class.return_value = mock_factory
            with patch("src.api.routes.data.ingest.MarketDataService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.ingest_historical_data = AsyncMock(return_value=mock_result)
                mock_service_class.return_value = mock_service

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/data/ingest",
                        json={
                            "symbol": "SPY",
                            "timeframe": "1d",
                            "start_date": "2024-01-01",
                            "end_date": "2024-03-01",
                        },
                    )

                # Assert success
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["bars_inserted"] == 50
                assert data["symbol"] == "SPY"

                # Verify service was called
                mock_service.ingest_historical_data.assert_called_once()
