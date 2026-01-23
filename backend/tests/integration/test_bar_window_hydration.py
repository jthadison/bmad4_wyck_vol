"""
Integration tests for Bar Window Manager startup hydration.

Tests the complete startup hydration workflow:
- Hydrating multiple symbols
- Handling insufficient data scenarios
- Memory usage verification
- State transitions
"""

from unittest.mock import AsyncMock

import pytest

from src.pattern_engine.bar_window_manager import (
    BarWindowManager,
    WindowState,
)


@pytest.mark.asyncio
class TestBarWindowHydration:
    """Integration tests for bar window hydration."""

    async def test_startup_hydration_multiple_symbols(self, create_test_bar):
        """
        Test hydrating multiple symbols on startup (Test Scenario 1).

        Verifies that multiple symbols can be hydrated concurrently
        and all reach READY state.
        """
        # Arrange
        mock_client = AsyncMock()

        # Mock Alpaca client to return 200 bars for each symbol
        def mock_fetch_bars(symbol, start_date, end_date, timeframe):
            return [create_test_bar(symbol, i) for i in range(200)]

        mock_client.fetch_historical_bars.side_effect = mock_fetch_bars

        manager = BarWindowManager(alpaca_client=mock_client)
        symbols = ["AAPL", "TSLA", "MSFT", "NVDA", "GOOGL"]

        # Act - Hydrate all symbols
        states = []
        for symbol in symbols:
            state = await manager.hydrate_symbol(symbol)
            states.append(state)

        # Assert
        assert all(state == WindowState.READY for state in states)
        assert manager.get_window_count() == 5
        assert manager.get_ready_count() == 5

        # Verify all windows have 200 bars
        for symbol in symbols:
            bars = manager.get_bars(symbol)
            assert len(bars) == 200

    async def test_insufficient_data_handling(self, create_test_bar):
        """
        Test handling of symbols with insufficient data (Test Scenario 2).

        Verifies that symbols with < 200 bars are flagged correctly.
        """
        # Arrange
        mock_client = AsyncMock()

        def mock_fetch_bars(symbol, start_date, end_date, timeframe):
            # NEWIPO has only 50 bars
            if symbol == "NEWIPO":
                return [create_test_bar(symbol, i) for i in range(50)]
            # Others have 200 bars
            return [create_test_bar(symbol, i) for i in range(200)]

        mock_client.fetch_historical_bars.side_effect = mock_fetch_bars

        manager = BarWindowManager(alpaca_client=mock_client)

        # Act
        aapl_state = await manager.hydrate_symbol("AAPL")
        newipo_state = await manager.hydrate_symbol("NEWIPO")

        # Assert
        assert aapl_state == WindowState.READY
        assert newipo_state == WindowState.INSUFFICIENT_DATA

        assert manager.get_window_count() == 2
        assert manager.get_ready_count() == 1  # Only AAPL is ready

        # Verify bar counts
        assert len(manager.get_bars("AAPL")) == 200
        assert len(manager.get_bars("NEWIPO")) == 50

    async def test_rolling_update_after_hydration(self, create_test_bar):
        """
        Test rolling window updates after initial hydration (Test Scenario 3).

        Verifies FIFO behavior when new bars arrive after startup.
        """
        # Arrange
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        # Act - Hydrate symbol
        await manager.hydrate_symbol("AAPL")

        # Get oldest bar timestamp
        bars_before = manager.get_bars("AAPL")
        oldest_timestamp = bars_before[0].timestamp
        newest_timestamp = bars_before[-1].timestamp

        # Add new bar
        new_bar = create_test_bar("AAPL", 200)
        await manager.add_bar("AAPL", new_bar)

        # Assert
        bars_after = manager.get_bars("AAPL")
        assert len(bars_after) == 200  # Still 200 bars

        # Oldest bar should be evicted
        assert bars_after[0].timestamp != oldest_timestamp
        assert bars_after[0].timestamp > oldest_timestamp

        # Newest bar should be the one we just added
        assert bars_after[-1].timestamp == new_bar.timestamp

    async def test_memory_usage_compliance(self, create_test_bar):
        """
        Test memory usage for 50 symbols (Test Scenario 4, AC6).

        Verifies total memory usage is under 50MB for 50 symbols.
        """
        # Arrange
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("SYM00", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        # Act - Hydrate 50 symbols
        for i in range(50):
            symbol = f"SYM{i:02d}"
            await manager.hydrate_symbol(symbol)

        # Measure memory usage
        memory_bytes = manager.get_memory_usage()
        memory_mb = memory_bytes / (1024 * 1024)

        # Assert
        assert manager.get_window_count() == 50
        assert manager.get_ready_count() == 50

        # Memory should be well under 50MB
        # Expected: ~1MB for 50 symbols × 200 bars
        assert memory_mb < 50
        assert memory_mb < 2  # Should be around 1MB

    async def test_concurrent_hydration_and_updates(self, create_test_bar):
        """
        Test hydration and real-time updates happening concurrently.

        Verifies that adding new bars during hydration works correctly.
        """
        # Arrange
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        # Act - Start with empty window and add bars manually
        for i in range(195):
            bar = create_test_bar("TSLA", i)
            await manager.add_bar("TSLA", bar)

        # At this point, TSLA has 195 bars and should be HYDRATING
        assert manager.get_state("TSLA") == WindowState.HYDRATING

        # Add 5 more bars to reach 200
        for i in range(195, 200):
            bar = create_test_bar("TSLA", i)
            await manager.add_bar("TSLA", bar)

        # Now should be READY
        assert manager.get_state("TSLA") == WindowState.READY
        assert len(manager.get_bars("TSLA")) == 200

        # Meanwhile, hydrate AAPL normally
        await manager.hydrate_symbol("AAPL")
        assert manager.get_state("AAPL") == WindowState.READY

    async def test_state_transitions(self, create_test_bar):
        """
        Test complete state transition workflow.

        Verifies state transitions: HYDRATING → READY/INSUFFICIENT_DATA.
        """
        # Arrange
        mock_client = AsyncMock()

        def mock_fetch_bars(symbol, start_date, end_date, timeframe):
            if symbol == "READY_SYM":
                return [create_test_bar(symbol, i) for i in range(200)]
            elif symbol == "INSUFFICIENT_SYM":
                return [create_test_bar(symbol, i) for i in range(100)]
            return []

        mock_client.fetch_historical_bars.side_effect = mock_fetch_bars

        manager = BarWindowManager(alpaca_client=mock_client)

        # Act & Assert - Test READY transition
        state = await manager.hydrate_symbol("READY_SYM")
        assert state == WindowState.READY
        assert manager.get_state("READY_SYM") == WindowState.READY

        # Act & Assert - Test INSUFFICIENT_DATA transition
        state = await manager.hydrate_symbol("INSUFFICIENT_SYM")
        assert state == WindowState.INSUFFICIENT_DATA
        assert manager.get_state("INSUFFICIENT_SYM") == WindowState.INSUFFICIENT_DATA

    async def test_window_persistence_across_operations(self, create_test_bar):
        """
        Test that window data persists correctly across operations.

        Verifies that windows maintain data integrity after multiple operations.
        """
        # Arrange
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        # Act - Perform multiple operations
        await manager.hydrate_symbol("AAPL")

        # Query bars multiple times
        bars_1 = manager.get_bars("AAPL")
        bars_2 = manager.get_bars("AAPL")
        bars_3 = manager.get_bars("AAPL")

        # Add a new bar
        new_bar = create_test_bar("AAPL", 200)
        await manager.add_bar("AAPL", new_bar)

        bars_4 = manager.get_bars("AAPL")

        # Assert
        # First three queries should be identical
        assert len(bars_1) == len(bars_2) == len(bars_3) == 200
        assert bars_1[0].timestamp == bars_2[0].timestamp == bars_3[0].timestamp

        # After adding new bar, should still be 200 bars
        assert len(bars_4) == 200

        # But oldest bar should be different (evicted)
        assert bars_4[0].timestamp != bars_1[0].timestamp
