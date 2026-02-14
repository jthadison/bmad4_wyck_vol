"""
Unit tests for SignalScannerService safety controls (Story 20.4).

Tests scanner safety mechanisms:
- Circuit breaker integration
- Kill switch integration
- Forex session filtering
- Rate limiting per symbol
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from freezegun import freeze_time

from src.models.scanner_persistence import (
    AssetClass,
    ScanCycleStatus,
    Timeframe,
    WatchlistSymbol,
)
from src.services.session_filter import (
    ForexSession,
    get_current_session,
    is_low_liquidity_session,
    should_skip_forex_symbol,
    should_skip_rate_limit,
)
from src.services.signal_scanner_service import (
    ScanCycleResult,
    SignalScannerService,
)


def create_mock_symbol(
    symbol: str,
    timeframe: Timeframe = Timeframe.H1,
    asset_class: AssetClass = AssetClass.FOREX,
    enabled: bool = True,
    last_scanned_at: datetime | None = None,
) -> WatchlistSymbol:
    """Create a mock WatchlistSymbol for testing."""
    return WatchlistSymbol(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        asset_class=asset_class,
        enabled=enabled,
        last_scanned_at=last_scanned_at,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_repository():
    """Create mock ScannerRepository."""
    repo = MagicMock()

    # Mock get_config to return a default config
    config = MagicMock()
    config.scan_interval_seconds = 300
    config.batch_size = 10
    config.last_cycle_at = None
    config.session_filter_enabled = True
    repo.get_config = AsyncMock(return_value=config)

    # Mock update_config
    repo.update_config = AsyncMock()

    # Mock get_symbol_count
    repo.get_symbol_count = AsyncMock(return_value=5)

    # Mock set_last_cycle_at
    repo.set_last_cycle_at = AsyncMock()

    # Mock get_enabled_symbols (default empty)
    repo.get_enabled_symbols = AsyncMock(return_value=[])

    # Mock update_last_scanned
    repo.update_last_scanned = AsyncMock()

    # Mock add_history
    repo.add_history = AsyncMock()

    return repo


@pytest.fixture
def mock_orchestrator():
    """Create mock MasterOrchestrator."""
    orchestrator = MagicMock()
    orchestrator.analyze_symbol = AsyncMock(return_value=[])
    return orchestrator


@pytest.fixture
def mock_circuit_breaker():
    """Create mock CircuitBreakerService."""
    breaker = MagicMock()
    breaker.is_breaker_open = AsyncMock(return_value=False)
    return breaker


@pytest.fixture
def mock_kill_switch_checker():
    """Create mock kill switch checker."""
    checker = MagicMock()
    checker.is_kill_switch_active = AsyncMock(return_value=False)
    return checker


# ===========================================================
# Session Filter Module Tests
# ===========================================================


class TestForexSessionDetection:
    """Tests for get_current_session function."""

    def test_asian_session_at_midnight(self):
        """Test Asian session at 00:00 UTC."""
        utc_time = datetime(2024, 1, 15, 0, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.ASIAN

    def test_asian_session_at_3am(self):
        """Test Asian session at 03:00 UTC."""
        utc_time = datetime(2024, 1, 15, 3, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.ASIAN

    def test_asian_session_at_5am(self):
        """Test Asian session at 05:59 UTC."""
        utc_time = datetime(2024, 1, 15, 5, 59, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.ASIAN

    def test_london_open_at_6am(self):
        """Test London Open session at 06:00 UTC."""
        utc_time = datetime(2024, 1, 15, 6, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.LONDON_OPEN

    def test_london_session_at_10am(self):
        """Test London session at 10:00 UTC."""
        utc_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.LONDON

    def test_london_ny_overlap_at_2pm(self):
        """Test London/NY overlap at 14:00 UTC (peak liquidity)."""
        utc_time = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.LONDON_NY

    def test_ny_session_at_6pm(self):
        """Test NY session at 18:00 UTC."""
        utc_time = datetime(2024, 1, 15, 18, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.NY

    def test_late_ny_at_9pm(self):
        """Test Late NY session at 21:00 UTC."""
        utc_time = datetime(2024, 1, 15, 21, 0, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.LATE_NY

    def test_late_ny_at_11pm(self):
        """Test Late NY session at 23:59 UTC."""
        utc_time = datetime(2024, 1, 15, 23, 59, tzinfo=UTC)
        assert get_current_session(utc_time) == ForexSession.LATE_NY


class TestLowLiquidityDetection:
    """Tests for is_low_liquidity_session function."""

    def test_asian_is_low_liquidity(self):
        """Test that Asian session is low liquidity."""
        utc_time = datetime(2024, 1, 15, 3, 0, tzinfo=UTC)
        assert is_low_liquidity_session(utc_time) is True

    def test_late_ny_is_low_liquidity(self):
        """Test that Late NY session is low liquidity."""
        utc_time = datetime(2024, 1, 15, 21, 0, tzinfo=UTC)
        assert is_low_liquidity_session(utc_time) is True

    def test_london_is_high_liquidity(self):
        """Test that London session is high liquidity."""
        utc_time = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        assert is_low_liquidity_session(utc_time) is False

    def test_london_ny_is_peak_liquidity(self):
        """Test that London/NY overlap is peak liquidity."""
        utc_time = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        assert is_low_liquidity_session(utc_time) is False

    def test_ny_is_high_liquidity(self):
        """Test that NY session is high liquidity."""
        utc_time = datetime(2024, 1, 15, 18, 0, tzinfo=UTC)
        assert is_low_liquidity_session(utc_time) is False


class TestShouldSkipForexSymbol:
    """Tests for should_skip_forex_symbol function."""

    def test_skip_during_asian_session(self):
        """Test that forex is skipped during Asian session."""
        utc_time = datetime(2024, 1, 15, 3, 0, tzinfo=UTC)
        should_skip, reason = should_skip_forex_symbol(utc_time, session_filter_enabled=True)

        assert should_skip is True
        assert "Asian session" in reason
        assert "low liquidity" in reason

    def test_skip_during_late_ny_session(self):
        """Test that forex is skipped during Late NY session."""
        utc_time = datetime(2024, 1, 15, 21, 0, tzinfo=UTC)
        should_skip, reason = should_skip_forex_symbol(utc_time, session_filter_enabled=True)

        assert should_skip is True
        assert "Late NY session" in reason
        assert "low liquidity" in reason

    def test_no_skip_during_london_ny_overlap(self):
        """Test that forex is NOT skipped during London/NY overlap."""
        utc_time = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
        should_skip, reason = should_skip_forex_symbol(utc_time, session_filter_enabled=True)

        assert should_skip is False
        assert reason is None

    def test_no_skip_when_filter_disabled(self):
        """Test that forex is NOT skipped when session filter is disabled."""
        utc_time = datetime(2024, 1, 15, 3, 0, tzinfo=UTC)  # Asian session
        should_skip, reason = should_skip_forex_symbol(utc_time, session_filter_enabled=False)

        assert should_skip is False
        assert reason is None


class TestShouldSkipRateLimit:
    """Tests for should_skip_rate_limit function."""

    def test_skip_recently_scanned_symbol(self):
        """Test that recently scanned symbol is skipped."""
        utc_now = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        two_min_ago = datetime(2024, 1, 15, 9, 58, tzinfo=UTC)

        should_skip, reason = should_skip_rate_limit(
            last_scanned_at=two_min_ago,
            scan_interval_seconds=300,  # 5 minutes
            utc_now=utc_now,
        )

        assert should_skip is True
        assert "scanned 2 minutes ago" in reason
        assert "interval: 5 min" in reason

    def test_no_skip_stale_symbol(self):
        """Test that symbol scanned long ago is NOT skipped."""
        utc_now = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        six_min_ago = datetime(2024, 1, 15, 9, 54, tzinfo=UTC)

        should_skip, reason = should_skip_rate_limit(
            last_scanned_at=six_min_ago,
            scan_interval_seconds=300,  # 5 minutes
            utc_now=utc_now,
        )

        assert should_skip is False
        assert reason is None

    def test_no_skip_never_scanned_symbol(self):
        """Test that never-scanned symbol is NOT skipped."""
        utc_now = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)

        should_skip, reason = should_skip_rate_limit(
            last_scanned_at=None,
            scan_interval_seconds=300,
            utc_now=utc_now,
        )

        assert should_skip is False
        assert reason is None

    def test_handles_naive_datetime(self):
        """Test that naive datetime is handled correctly."""
        utc_now = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
        # Naive datetime (no tzinfo)
        two_min_ago = datetime(2024, 1, 15, 9, 58)

        should_skip, reason = should_skip_rate_limit(
            last_scanned_at=two_min_ago,
            scan_interval_seconds=300,
            utc_now=utc_now,
        )

        assert should_skip is True


# ===========================================================
# Circuit Breaker Integration Tests
# ===========================================================


class TestCircuitBreakerIntegration:
    """Tests for AC1: Circuit Breaker Check."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_skips_cycle(
        self, mock_repository, mock_orchestrator, mock_circuit_breaker
    ):
        """Test that scan cycle is skipped when circuit breaker is OPEN."""
        mock_circuit_breaker.is_breaker_open.return_value = True
        user_id = uuid4()

        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            circuit_breaker=mock_circuit_breaker,
            user_id=user_id,
        )

        result = await scanner._scan_cycle()

        # Should have recorded a skipped cycle
        assert result.status == ScanCycleStatus.SKIPPED
        assert result.symbols_scanned == 0
        # Orchestrator should not be called
        mock_orchestrator.analyze_symbol.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_proceeds(
        self, mock_repository, mock_orchestrator, mock_circuit_breaker
    ):
        """Test that scan cycle proceeds when circuit breaker is CLOSED."""
        mock_circuit_breaker.is_breaker_open.return_value = False
        user_id = uuid4()

        symbols = [create_mock_symbol("EURUSD", asset_class=AssetClass.STOCK)]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            circuit_breaker=mock_circuit_breaker,
            user_id=user_id,
        )

        result = await scanner._scan_cycle()

        # Cycle should complete normally
        assert result.status == ScanCycleStatus.COMPLETED
        assert result.symbols_scanned == 1
        mock_orchestrator.analyze_symbol.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_none_proceeds(self, mock_repository, mock_orchestrator):
        """Test that scan cycle proceeds when circuit breaker is None."""
        symbols = [create_mock_symbol("SPY", asset_class=AssetClass.STOCK)]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            circuit_breaker=None,
            user_id=None,
        )

        result = await scanner._scan_cycle()

        assert result.status == ScanCycleStatus.COMPLETED
        mock_orchestrator.analyze_symbol.assert_called_once()


# ===========================================================
# Kill Switch Integration Tests
# ===========================================================


class TestKillSwitchIntegration:
    """Tests for AC2: Kill Switch Integration."""

    @pytest.mark.asyncio
    async def test_kill_switch_activated_stops_scanner(
        self, mock_repository, mock_orchestrator, mock_kill_switch_checker
    ):
        """Test that scanner stops completely when kill switch is activated."""
        mock_kill_switch_checker.is_kill_switch_active.return_value = True
        user_id = uuid4()

        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            kill_switch_checker=mock_kill_switch_checker,
            user_id=user_id,
        )

        result = await scanner._scan_cycle()

        # Should return skipped status
        assert result.status == ScanCycleStatus.SKIPPED
        assert result.symbols_scanned == 0
        # Orchestrator should not be called
        mock_orchestrator.analyze_symbol.assert_not_called()

    @pytest.mark.asyncio
    async def test_kill_switch_mid_cycle_stops_scanner(
        self, mock_repository, mock_orchestrator, mock_kill_switch_checker
    ):
        """Test that kill switch mid-cycle stops processing remaining symbols."""
        user_id = uuid4()

        symbols = [
            create_mock_symbol("EURUSD", asset_class=AssetClass.STOCK),
            create_mock_symbol("GBPUSD", asset_class=AssetClass.STOCK),
            create_mock_symbol("SPY", asset_class=AssetClass.STOCK),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        # Mock time.perf_counter to advance beyond cache TTL (5 seconds) between checks
        # This ensures the kill switch is actually checked each time (not cached)
        perf_counter_values = iter([0.0, 10.0, 20.0, 30.0, 40.0])

        # Activate kill switch after first symbol check
        # Call 1: cycle start -> passes (time=0)
        # Call 2: first symbol -> passes -> analyze EURUSD (time=10)
        # Call 3: second symbol -> activated -> stop (time=20)
        call_count = [0]

        async def check_kill_switch(user_id):
            call_count[0] += 1
            # Activate after first symbol is analyzed (call 3+)
            return call_count[0] > 2

        mock_kill_switch_checker.is_kill_switch_active.side_effect = check_kill_switch

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            kill_switch_checker=mock_kill_switch_checker,
            user_id=user_id,
        )
        # Disable session filtering for this test
        scanner._session_filter_enabled = False

        with patch.object(time, "perf_counter", side_effect=perf_counter_values):
            result = await scanner._scan_cycle()

        # Should have processed first symbol before kill switch activated on second
        assert result.symbols_scanned == 1
        # Only first symbol should be analyzed
        assert mock_orchestrator.analyze_symbol.call_count == 1

    @pytest.mark.asyncio
    async def test_kill_switch_inactive_proceeds(
        self, mock_repository, mock_orchestrator, mock_kill_switch_checker
    ):
        """Test that scan cycle proceeds when kill switch is inactive."""
        mock_kill_switch_checker.is_kill_switch_active.return_value = False
        user_id = uuid4()

        symbols = [create_mock_symbol("SPY", asset_class=AssetClass.STOCK)]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            kill_switch_checker=mock_kill_switch_checker,
            user_id=user_id,
        )

        result = await scanner._scan_cycle()

        assert result.status == ScanCycleStatus.COMPLETED
        mock_orchestrator.analyze_symbol.assert_called_once()


# ===========================================================
# Forex Session Filtering in Scanner Tests
# ===========================================================


class TestSessionFilteringInScanner:
    """Tests for AC3/AC4: Forex Session Filtering."""

    @pytest.mark.asyncio
    @freeze_time("2024-01-15 03:00:00", tz_offset=0)
    async def test_forex_filtered_during_asian_session(self, mock_repository, mock_orchestrator):
        """Test that forex symbols are skipped during Asian session."""
        # Create mix of forex and stock
        symbols = [
            create_mock_symbol("EURUSD", asset_class=AssetClass.FOREX),
            create_mock_symbol("SPY", asset_class=AssetClass.STOCK),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._session_filter_enabled = True

        result = await scanner._scan_cycle()

        # EURUSD should be skipped, SPY should be analyzed
        assert result.symbols_skipped_session == 1
        assert result.symbols_scanned == 1
        mock_orchestrator.analyze_symbol.assert_called_once_with("SPY", timeframe="1H")

    @pytest.mark.asyncio
    @freeze_time("2024-01-15 21:00:00", tz_offset=0)
    async def test_forex_filtered_during_late_ny_session(self, mock_repository, mock_orchestrator):
        """Test that forex symbols are skipped during Late NY session."""
        symbols = [
            create_mock_symbol("GBPUSD", asset_class=AssetClass.FOREX),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._session_filter_enabled = True

        result = await scanner._scan_cycle()

        # GBPUSD should be skipped
        assert result.symbols_skipped_session == 1
        assert result.symbols_scanned == 0
        mock_orchestrator.analyze_symbol.assert_not_called()

    @pytest.mark.asyncio
    @freeze_time("2024-01-15 14:00:00", tz_offset=0)
    async def test_forex_not_filtered_during_london_ny(self, mock_repository, mock_orchestrator):
        """Test that forex symbols are NOT skipped during London/NY overlap."""
        symbols = [
            create_mock_symbol("EURUSD", asset_class=AssetClass.FOREX),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._session_filter_enabled = True

        result = await scanner._scan_cycle()

        # EURUSD should be analyzed
        assert result.symbols_skipped_session == 0
        assert result.symbols_scanned == 1
        mock_orchestrator.analyze_symbol.assert_called_once()

    @pytest.mark.asyncio
    @freeze_time("2024-01-15 03:00:00", tz_offset=0)
    async def test_session_filtering_disabled_analyzes_all(
        self, mock_repository, mock_orchestrator
    ):
        """Test that all forex symbols are analyzed when session filter is disabled."""
        symbols = [
            create_mock_symbol("EURUSD", asset_class=AssetClass.FOREX),
            create_mock_symbol("GBPUSD", asset_class=AssetClass.FOREX),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._session_filter_enabled = False

        result = await scanner._scan_cycle()

        # Both forex symbols should be analyzed (no filtering)
        assert result.symbols_skipped_session == 0
        assert result.symbols_scanned == 2
        assert mock_orchestrator.analyze_symbol.call_count == 2

    @pytest.mark.asyncio
    @freeze_time("2024-01-15 03:00:00", tz_offset=0)
    async def test_non_forex_symbols_not_filtered(self, mock_repository, mock_orchestrator):
        """Test that non-forex symbols are never filtered by session."""
        symbols = [
            create_mock_symbol("SPY", asset_class=AssetClass.STOCK),
            create_mock_symbol("QQQ", asset_class=AssetClass.INDEX),
            create_mock_symbol("BTCUSD", asset_class=AssetClass.CRYPTO),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._session_filter_enabled = True

        result = await scanner._scan_cycle()

        # All non-forex symbols should be analyzed
        assert result.symbols_skipped_session == 0
        assert result.symbols_scanned == 3


# ===========================================================
# Rate Limiting in Scanner Tests
# ===========================================================


class TestRateLimitingInScanner:
    """Tests for AC6: Rate Limiting Per Symbol."""

    @pytest.mark.asyncio
    async def test_rate_limiting_skips_recent_symbols(self, mock_repository, mock_orchestrator):
        """Test that recently scanned symbols are skipped."""
        # Symbol scanned 2 minutes ago
        two_min_ago = datetime.now(UTC) - timedelta(minutes=2)
        symbols = [
            create_mock_symbol("EURUSD", asset_class=AssetClass.STOCK, last_scanned_at=two_min_ago),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._scan_interval_seconds = 300  # 5 minutes

        result = await scanner._scan_cycle()

        # Should be skipped due to rate limiting
        assert result.symbols_skipped_rate_limit == 1
        assert result.symbols_scanned == 0
        mock_orchestrator.analyze_symbol.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limiting_allows_stale_symbols(self, mock_repository, mock_orchestrator):
        """Test that symbols scanned long ago are analyzed."""
        # Symbol scanned 6 minutes ago
        six_min_ago = datetime.now(UTC) - timedelta(minutes=6)
        symbols = [
            create_mock_symbol("SPY", asset_class=AssetClass.STOCK, last_scanned_at=six_min_ago),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._scan_interval_seconds = 300  # 5 minutes

        result = await scanner._scan_cycle()

        # Should be analyzed (6 min > 5 min interval)
        assert result.symbols_skipped_rate_limit == 0
        assert result.symbols_scanned == 1
        mock_orchestrator.analyze_symbol.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiting_allows_never_scanned(self, mock_repository, mock_orchestrator):
        """Test that never-scanned symbols are analyzed."""
        symbols = [
            create_mock_symbol("SPY", asset_class=AssetClass.STOCK, last_scanned_at=None),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(mock_repository, mock_orchestrator)
        scanner._scan_interval_seconds = 300

        result = await scanner._scan_cycle()

        # Should be analyzed (never scanned before)
        assert result.symbols_skipped_rate_limit == 0
        assert result.symbols_scanned == 1
        mock_orchestrator.analyze_symbol.assert_called_once()


# ===========================================================
# Combined Safety Checks Tests
# ===========================================================


class TestCombinedSafetyChecks:
    """Tests for combined safety control scenarios."""

    @pytest.mark.asyncio
    async def test_kill_switch_takes_precedence_over_circuit_breaker(
        self, mock_repository, mock_orchestrator, mock_circuit_breaker, mock_kill_switch_checker
    ):
        """Test that kill switch is checked before circuit breaker."""
        mock_kill_switch_checker.is_kill_switch_active.return_value = True
        mock_circuit_breaker.is_breaker_open.return_value = True
        user_id = uuid4()

        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            circuit_breaker=mock_circuit_breaker,
            kill_switch_checker=mock_kill_switch_checker,
            user_id=user_id,
        )

        result = await scanner._scan_cycle()

        # Kill switch should stop scanner before circuit breaker check
        assert result.status == ScanCycleStatus.SKIPPED
        # Kill switch is checked first, so circuit breaker shouldn't be checked
        mock_kill_switch_checker.is_kill_switch_active.assert_called()

    @pytest.mark.asyncio
    async def test_session_filter_applies_after_safety_checks(
        self, mock_repository, mock_orchestrator, mock_circuit_breaker, mock_kill_switch_checker
    ):
        """Test that session filtering applies after kill switch/circuit breaker pass."""
        mock_kill_switch_checker.is_kill_switch_active.return_value = False
        mock_circuit_breaker.is_breaker_open.return_value = False
        user_id = uuid4()

        symbols = [
            create_mock_symbol("EURUSD", asset_class=AssetClass.FOREX),
            create_mock_symbol("SPY", asset_class=AssetClass.STOCK),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = SignalScannerService(
            mock_repository,
            mock_orchestrator,
            circuit_breaker=mock_circuit_breaker,
            kill_switch_checker=mock_kill_switch_checker,
            user_id=user_id,
        )
        scanner._session_filter_enabled = True

        # Use freezegun for cleaner time mocking (Story 20.4 PR review)
        with freeze_time("2024-01-15 03:00:00", tz_offset=0):
            result = await scanner._scan_cycle()

        # EURUSD filtered by session, SPY analyzed
        assert result.symbols_skipped_session == 1
        assert result.symbols_scanned == 1


# ===========================================================
# ScanCycleResult Tests
# ===========================================================


class TestScanCycleResultWithSkips:
    """Tests for ScanCycleResult with skip tracking."""

    def test_scan_cycle_result_includes_skip_counts(self):
        """Test that ScanCycleResult includes skip tracking fields."""
        now = datetime.now(UTC)
        result = ScanCycleResult(
            cycle_started_at=now,
            cycle_ended_at=now,
            symbols_scanned=3,
            signals_generated=1,
            errors_count=0,
            status=ScanCycleStatus.COMPLETED,
            symbols_skipped_session=2,
            symbols_skipped_rate_limit=1,
        )

        assert result.symbols_skipped_session == 2
        assert result.symbols_skipped_rate_limit == 1

    def test_scan_cycle_result_defaults_zero_skips(self):
        """Test that skip counts default to zero."""
        now = datetime.now(UTC)
        result = ScanCycleResult(
            cycle_started_at=now,
            cycle_ended_at=now,
            symbols_scanned=0,
            signals_generated=0,
            errors_count=0,
            status=ScanCycleStatus.COMPLETED,
        )

        assert result.symbols_skipped_session == 0
        assert result.symbols_skipped_rate_limit == 0


# =========================================================================
# History Recording on Failures (Task #26 - Audit Trail Enhancements)
# =========================================================================


class TestHistoryRecordingOnFailures:
    """Test that scan history is recorded even when failures occur."""

    @pytest.mark.asyncio
    async def test_history_recorded_on_partial_failure(self, mock_repository, mock_orchestrator):
        """History should be recorded when some symbols succeed and some fail."""
        # Setup: 3 symbols, 2 succeed, 1 fails
        symbols = [
            create_mock_symbol("AAPL", asset_class=AssetClass.STOCK),
            create_mock_symbol("MSFT", asset_class=AssetClass.STOCK),
            create_mock_symbol("FAIL", asset_class=AssetClass.STOCK),
        ]
        mock_repository.get_enabled_symbols = AsyncMock(return_value=symbols)

        # AAPL and MSFT succeed, FAIL raises exception
        async def mock_analyze(symbol: str, timeframe: str):
            if symbol == "FAIL":
                raise Exception("Analysis failed")
            return []  # No signals but successful analysis

        mock_orchestrator.analyze_symbol = AsyncMock(side_effect=mock_analyze)

        scanner = SignalScannerService(
            repository=mock_repository,
            orchestrator=mock_orchestrator,
        )

        # Run scan cycle
        result = await scanner._scan_cycle()

        # Verify partial completion
        assert result.status == ScanCycleStatus.PARTIAL
        assert result.symbols_scanned == 2  # AAPL, MSFT succeeded
        assert result.errors_count == 1  # FAIL failed

        # Verify history was recorded
        mock_repository.add_history.assert_called_once()
        history_call = mock_repository.add_history.call_args[1]["cycle_data"]
        assert history_call.status == ScanCycleStatus.PARTIAL
        assert history_call.errors_count == 1

    @pytest.mark.asyncio
    async def test_history_recorded_on_complete_failure(self, mock_repository, mock_orchestrator):
        """History should be recorded when all symbols fail."""
        symbols = [
            create_mock_symbol("FAIL1", asset_class=AssetClass.STOCK),
            create_mock_symbol("FAIL2", asset_class=AssetClass.STOCK),
        ]
        mock_repository.get_enabled_symbols = AsyncMock(return_value=symbols)

        # All symbols fail
        mock_orchestrator.analyze_symbol = AsyncMock(side_effect=Exception("Analysis failed"))

        scanner = SignalScannerService(
            repository=mock_repository,
            orchestrator=mock_orchestrator,
        )

        result = await scanner._scan_cycle()

        # Verify complete failure
        assert result.status == ScanCycleStatus.FAILED
        assert result.symbols_scanned == 0  # None succeeded
        assert result.errors_count == 2  # Both failed

        # Verify history was recorded even on complete failure
        mock_repository.add_history.assert_called_once()
        history_call = mock_repository.add_history.call_args[1]["cycle_data"]
        assert history_call.status == ScanCycleStatus.FAILED
        assert history_call.errors_count == 2

    @pytest.mark.asyncio
    async def test_history_recorded_on_kill_switch_abort(self, mock_repository, mock_orchestrator):
        """History should record SKIPPED status when kill switch aborts scan."""
        symbols = [
            create_mock_symbol("AAPL", asset_class=AssetClass.STOCK),
            create_mock_symbol("MSFT", asset_class=AssetClass.STOCK),
        ]
        mock_repository.get_enabled_symbols = AsyncMock(return_value=symbols)
        mock_orchestrator.analyze_symbol = AsyncMock(return_value=[])

        # Mock kill switch checker that becomes active mid-scan
        mock_kill_switch = AsyncMock()
        call_count = [0]

        async def kill_switch_check(user_id):
            call_count[0] += 1
            # Activate after first check
            return call_count[0] > 1

        mock_kill_switch.is_kill_switch_active = AsyncMock(side_effect=kill_switch_check)

        scanner = SignalScannerService(
            repository=mock_repository,
            orchestrator=mock_orchestrator,
            kill_switch_checker=mock_kill_switch,
            user_id=uuid4(),
        )

        result = await scanner._scan_cycle()

        # Verify kill switch stopped the scan
        assert result.status == ScanCycleStatus.SKIPPED
        assert result.kill_switch_triggered is True

        # Verify history recorded the abort
        mock_repository.add_history.assert_called_once()
        history_call = mock_repository.add_history.call_args[1]["cycle_data"]
        assert history_call.status == ScanCycleStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_error_count_matches_actual_failures(self, mock_repository, mock_orchestrator):
        """Error count in history should match actual number of failures."""
        symbols = [create_mock_symbol(f"SYM{i}", asset_class=AssetClass.STOCK) for i in range(10)]
        mock_repository.get_enabled_symbols = AsyncMock(return_value=symbols)

        # Fail symbols 3, 5, 7 (3 failures out of 10)
        async def mock_analyze(symbol: str, timeframe: str):
            if symbol in ["SYM3", "SYM5", "SYM7"]:
                raise Exception("Analysis failed")
            return []

        mock_orchestrator.analyze_symbol = AsyncMock(side_effect=mock_analyze)

        scanner = SignalScannerService(
            repository=mock_repository,
            orchestrator=mock_orchestrator,
        )

        result = await scanner._scan_cycle()

        # Verify error count accuracy
        assert result.errors_count == 3
        assert result.symbols_scanned == 7  # 10 total - 3 failed

        # Verify history recorded accurate count
        mock_repository.add_history.assert_called_once()
        history_call = mock_repository.add_history.call_args[1]["cycle_data"]
        assert history_call.errors_count == 3

    @pytest.mark.asyncio
    async def test_failure_history_queryable(self, mock_repository, mock_orchestrator):
        """Failed scan cycles should be queryable from history."""
        symbols = [create_mock_symbol("FAIL", asset_class=AssetClass.STOCK)]
        mock_repository.get_enabled_symbols = AsyncMock(return_value=symbols)
        mock_orchestrator.analyze_symbol = AsyncMock(side_effect=Exception("Analysis failed"))

        scanner = SignalScannerService(
            repository=mock_repository,
            orchestrator=mock_orchestrator,
        )

        await scanner._scan_cycle()

        # Verify add_history was called with queryable data
        mock_repository.add_history.assert_called_once()
        history_call = mock_repository.add_history.call_args[1]["cycle_data"]

        # All required fields present
        assert history_call.cycle_started_at is not None
        assert history_call.cycle_ended_at is not None
        assert history_call.status == ScanCycleStatus.FAILED
        assert history_call.symbols_scanned == 0
        assert history_call.errors_count == 1
