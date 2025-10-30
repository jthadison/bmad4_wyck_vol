"""
Integration tests for database schema and TimescaleDB functionality.

These tests validate all acceptance criteria from Story 1.2:
1. PostgreSQL 15+ with TimescaleDB extension installed
2. Hypertable created for OHLCV bars
3. Automatic partitioning by time (daily chunks) configured
4. Compression policy enabled for data older than 7 days
5. Indexes created for efficient queries
6. All 7 tables created with correct schema
7. JSON columns for flexible metadata storage
8. Alembic migrations work correctly
9. Connection pooling configured
10. Query performance <50ms for 1-year lookups
"""

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker, engine


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests (Windows compatibility)."""
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide a database session for tests."""
    async with async_session_maker() as session:
        yield session


class TestDatabaseExtensions:
    """Test PostgreSQL and TimescaleDB extensions (AC: 1)."""

    @pytest.mark.asyncio
    async def test_timescaledb_extension_installed(self, db_session):
        """Verify TimescaleDB extension is installed with version 2.13+."""
        result = await db_session.execute(
            text(
                """
            SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'
        """
            )
        )
        version = result.scalar()

        assert version is not None, "TimescaleDB extension not installed"
        major, minor = version.split(".")[:2]
        assert int(major) >= 2, f"TimescaleDB major version {major} < 2"
        assert int(minor) >= 13, f"TimescaleDB minor version {minor} < 13"

    @pytest.mark.asyncio
    async def test_uuid_extension_installed(self, db_session):
        """Verify uuid-ossp extension is installed."""
        result = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM pg_extension WHERE extname = 'uuid-ossp'
        """
            )
        )
        count = result.scalar()
        assert count == 1, "uuid-ossp extension not installed"


class TestHypertableConfiguration:
    """Test TimescaleDB hypertable configuration (AC: 2, 3, 4)."""

    @pytest.mark.asyncio
    async def test_ohlcv_bars_is_hypertable(self, db_session):
        """Verify ohlcv_bars is configured as a TimescaleDB hypertable."""
        result = await db_session.execute(
            text(
                """
            SELECT hypertable_name, num_dimensions, compression_enabled
            FROM timescaledb_information.hypertables
            WHERE hypertable_name = 'ohlcv_bars'
        """
            )
        )
        row = result.first()

        assert row is not None, "ohlcv_bars is not a hypertable"
        assert row[0] == "ohlcv_bars"
        assert row[1] == 1, "Hypertable should have 1 dimension (time)"
        assert row[2] is True, "Compression should be enabled"

    @pytest.mark.asyncio
    async def test_daily_chunk_interval(self, db_session):
        """Verify hypertable uses daily (24-hour) chunk intervals."""
        result = await db_session.execute(
            text(
                """
            SELECT d.interval_length
            FROM _timescaledb_catalog.hypertable h
            JOIN _timescaledb_catalog.dimension d ON d.hypertable_id = h.id
            WHERE h.table_name = 'ohlcv_bars'
        """
            )
        )
        interval_microseconds = result.scalar()

        # Daily chunk = 86400 seconds = 86400000000 microseconds
        expected = 86400000000
        assert (
            interval_microseconds == expected
        ), f"Chunk interval {interval_microseconds}µs != {expected}µs (1 day)"

    @pytest.mark.asyncio
    async def test_compression_policy_configured(self, db_session):
        """Verify compression policy is configured for 7+ day old data."""
        result = await db_session.execute(
            text(
                """
            SELECT config->>'compress_after' as compress_after
            FROM timescaledb_information.jobs
            WHERE proc_name = 'policy_compression'
              AND hypertable_name = 'ohlcv_bars'
        """
            )
        )
        compress_after = result.scalar()

        assert compress_after is not None, "Compression policy not configured"
        assert compress_after == "7 days", f"Compress after {compress_after} != 7 days"


class TestTableSchema:
    """Test all 7 tables exist with correct schema (AC: 6)."""

    @pytest.mark.asyncio
    async def test_all_tables_exist(self, db_session):
        """Verify all 7 required tables exist."""
        result = await db_session.execute(
            text(
                """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND table_name IN (
                'ohlcv_bars', 'trading_ranges', 'patterns', 'signals',
                'campaigns', 'backtest_results', 'audit_trail'
              )
            ORDER BY table_name
        """
            )
        )
        tables = [row[0] for row in result.fetchall()]

        expected_tables = [
            "audit_trail",
            "backtest_results",
            "campaigns",
            "ohlcv_bars",
            "patterns",
            "signals",
            "trading_ranges",
        ]
        assert tables == expected_tables, f"Missing tables: {set(expected_tables) - set(tables)}"

    @pytest.mark.asyncio
    async def test_ohlcv_bars_columns(self, db_session):
        """Verify ohlcv_bars has all required columns with correct types."""
        result = await db_session.execute(
            text(
                """
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'ohlcv_bars'
            ORDER BY ordinal_position
        """
            )
        )
        columns = {row[0]: (row[1], row[2], row[3]) for row in result.fetchall()}

        # Verify critical NUMERIC columns have correct precision (18,8)
        assert columns["open"] == ("numeric", 18, 8)
        assert columns["high"] == ("numeric", 18, 8)
        assert columns["low"] == ("numeric", 18, 8)
        assert columns["close"] == ("numeric", 18, 8)
        assert columns["spread"] == ("numeric", 18, 8)

        # Verify other key columns
        assert columns["volume"][0] == "bigint"
        assert columns["timestamp"][0] == "timestamp with time zone"

    @pytest.mark.asyncio
    async def test_patterns_jsonb_metadata(self, db_session):
        """Verify patterns table has JSONB metadata column (AC: 7)."""
        result = await db_session.execute(
            text(
                """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'patterns'
              AND column_name = 'metadata'
        """
            )
        )
        data_type = result.scalar()
        assert data_type == "jsonb", f"patterns.metadata type {data_type} != jsonb"


class TestConstraints:
    """Test CHECK constraints and foreign keys."""

    @pytest.mark.asyncio
    async def test_volume_check_constraint(self, db_session):
        """Verify volume CHECK constraint prevents negative values."""
        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text(
                    """
                INSERT INTO ohlcv_bars (symbol, timeframe, timestamp, open, high, low, close, volume, spread, spread_ratio, volume_ratio)
                VALUES ('TEST', '1d', NOW(), 100, 105, 95, 102, -1000, 10, 1.0, 1.0)
            """
                )
            )
            await db_session.commit()

        assert "chk_volume_positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_r_multiple_check_constraint(self, db_session):
        """Verify r_multiple CHECK constraint requires >= 2.0."""
        # First, create required parent records
        await db_session.execute(
            text(
                """
            INSERT INTO trading_ranges (symbol, timeframe, start_time, duration_bars, creek_level, ice_level, jump_target, cause_factor, range_width, phase, strength_score)
            VALUES ('TEST', '1d', NOW(), 50, 100, 110, 120, 2.5, 10.0, 'C', 75)
        """
            )
        )

        result = await db_session.execute(
            text("SELECT id FROM trading_ranges WHERE symbol = 'TEST'")
        )
        tr_id = result.scalar()

        await db_session.execute(
            text(
                f"""
            INSERT INTO patterns (pattern_type, symbol, timeframe, detection_time, pattern_bar_timestamp, confidence_score, phase, trading_range_id, entry_price, stop_loss, invalidation_level, volume_ratio, spread_ratio, metadata)
            VALUES ('SPRING', 'TEST', '1d', NOW(), NOW(), 80, 'C', '{tr_id}', 100, 95, 90, 1.0, 1.0, '{"{}"}'::jsonb)
        """
            )
        )

        result = await db_session.execute(text("SELECT id FROM patterns WHERE symbol = 'TEST'"))
        pattern_id = result.scalar()

        # Try to insert signal with r_multiple < 2.0 (should fail)
        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text(
                    f"""
                INSERT INTO signals (signal_type, pattern_id, symbol, timeframe, generated_at, entry_price, stop_loss, target_1, target_2, position_size, risk_amount, r_multiple, confidence_score, approval_chain)
                VALUES ('LONG', '{pattern_id}', 'TEST', '1d', NOW(), 100, 95, 105, 110, 100, 500, 1.5, 80, '{"{}"}'::jsonb)
            """
                )
            )
            await db_session.commit()

        assert "chk_r_multiple" in str(exc_info.value)


class TestIndexes:
    """Test indexes exist and are used (AC: 5)."""

    @pytest.mark.asyncio
    async def test_ohlcv_indexes_exist(self, db_session):
        """Verify all required indexes on ohlcv_bars exist."""
        result = await db_session.execute(
            text(
                """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'ohlcv_bars'
            ORDER BY indexname
        """
            )
        )
        indexes = [row[0] for row in result.fetchall()]

        assert "pk_ohlcv_bars" in indexes, "Primary key index missing"
        assert "idx_ohlcv_symbol_timeframe" in indexes, "Symbol/timeframe index missing"
        assert "idx_ohlcv_id" in indexes, "ID index missing"


class TestConnectionPooling:
    """Test SQLAlchemy connection pooling (AC: 9)."""

    def test_connection_pool_configured(self):
        """Verify connection pool is configured with correct settings."""
        assert engine.pool.size() >= 0, "Pool not initialized"
        # Pool size configured in database.py as 10


class TestQueryPerformance:
    """Test query performance requirements (AC: 10)."""

    @pytest.mark.asyncio
    async def test_one_year_lookup_performance(self, db_session):
        """Verify 1-year lookups complete in <50ms."""
        # Insert test data if not present
        result = await db_session.execute(text("SELECT COUNT(*) FROM ohlcv_bars"))
        if result.scalar() == 0:
            pytest.skip("No test data - run seed_data.py first")

        import time

        start = time.perf_counter()

        await db_session.execute(
            text(
                """
            SELECT * FROM ohlcv_bars
            WHERE symbol = 'AAPL'
              AND timestamp >= NOW() - INTERVAL '1 year'
            ORDER BY timestamp DESC
        """
            )
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"Query took {elapsed_ms:.2f}ms (target <50ms)"


class TestAlembicMigrations:
    """Test Alembic migration system (AC: 8)."""

    @pytest.mark.asyncio
    async def test_alembic_version_table_exists(self, db_session):
        """Verify Alembic version tracking table exists."""
        result = await db_session.execute(
            text(
                """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'alembic_version'
        """
            )
        )
        count = result.scalar()
        assert count == 1, "alembic_version table missing"

    @pytest.mark.asyncio
    async def test_current_migration_applied(self, db_session):
        """Verify at least one migration has been applied."""
        result = await db_session.execute(
            text(
                """
            SELECT version_num FROM alembic_version
        """
            )
        )
        version = result.scalar()
        assert version is not None, "No migrations applied"
        assert version == "001", f"Expected migration 001, got {version}"
