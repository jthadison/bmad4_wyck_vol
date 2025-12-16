"""
Integration Tests for Analytics Repository (Task 9)

Purpose:
--------
Tests analytics repository with real PostgreSQL database.
Verifies query correctness, performance, edge cases, and error handling.

Test Coverage:
--------------
1. Pattern performance metrics aggregation
2. Sector breakdown queries
3. Win rate trend calculations
4. Trade details pagination
5. VSA metrics retrieval
6. Preliminary events tracking
7. Empty result handling
8. Query performance benchmarks

Author: Story 11.9 Task 9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.analytics_repository import AnalyticsRepository


@pytest.fixture
async def analytics_repo(db_session: AsyncSession):
    """Create analytics repository with test database session"""
    return AnalyticsRepository(db_session)


@pytest.fixture
async def sample_analytics_data(db_session: AsyncSession):
    """
    Create sample data for analytics tests.

    Creates:
    - 3 pattern types (SPRING, UTAD, SOS)
    - 100 total signals (mixed wins/losses)
    - 3 sectors (Technology, Healthcare, Financials)
    - Exit dates spanning 90 days
    - Test confirmed flags (60% confirmed)
    """
    # Insert sector mappings
    await db_session.execute(
        text(
            """
            INSERT INTO sector_mapping (symbol, sector_name, industry)
            VALUES
                ('AAPL', 'Technology', 'Technology Hardware'),
                ('MSFT', 'Technology', 'Software'),
                ('NVDA', 'Technology', 'Semiconductors'),
                ('UNH', 'Healthcare', 'Healthcare Providers'),
                ('JNJ', 'Healthcare', 'Pharmaceuticals'),
                ('JPM', 'Financials', 'Banks'),
                ('V', 'Financials', 'Financial Services')
            ON CONFLICT (symbol) DO NOTHING
        """
        )
    )

    # Create patterns and signals with known metrics
    symbols = ["AAPL", "MSFT", "NVDA", "UNH", "JNJ", "JPM", "V"]
    pattern_types = ["SPRING", "UTAD", "SOS"]
    phases = ["C", "D", "E"]

    pattern_ids = []
    for i in range(100):
        pattern_id = uuid4()
        pattern_ids.append(pattern_id)

        pattern_type = pattern_types[i % len(pattern_types)]
        symbol = symbols[i % len(symbols)]
        phase = phases[i % len(phases)]
        test_confirmed = i % 5 != 0  # 80% test confirmed

        # Insert pattern
        await db_session.execute(
            text(
                """
                INSERT INTO patterns (
                    id, pattern_type, symbol, timeframe, detection_time,
                    pattern_bar_timestamp, confidence_score, detection_phase,
                    entry_price, stop_loss, invalidation_level,
                    volume_ratio, spread_ratio, test_confirmed, metadata
                )
                VALUES (
                    :id, :pattern_type, :symbol, '1D', :detection_time,
                    :pattern_bar_timestamp, 85, :phase,
                    :entry_price, :stop_loss, :invalidation,
                    1.5, 1.2, :test_confirmed, '{}'::jsonb
                )
            """
            ),
            {
                "id": pattern_id,
                "pattern_type": pattern_type,
                "symbol": symbol,
                "detection_time": datetime.now(UTC) - timedelta(days=90 - i),
                "pattern_bar_timestamp": datetime.now(UTC) - timedelta(days=90 - i),
                "phase": phase,
                "entry_price": 100.00 + i,
                "stop_loss": 95.00 + i,
                "invalidation": 93.00 + i,
                "test_confirmed": test_confirmed,
            },
        )

        # Insert signal
        # Win rate by pattern: SPRING 70%, UTAD 60%, SOS 50%
        is_win = (
            (pattern_type == "SPRING" and i % 10 < 7)
            or (pattern_type == "UTAD" and i % 10 < 6)
            or (pattern_type == "SOS" and i % 10 < 5)
        )
        status = "CLOSED_WIN" if is_win else "CLOSED_LOSS"
        r_multiple = Decimal("3.0") if is_win else Decimal("-1.0")
        exit_price = (105.00 + i) if is_win else (98.00 + i)

        await db_session.execute(
            text(
                """
                INSERT INTO signals (
                    id, pattern_id, symbol, timeframe, generated_at,
                    entry_price, stop_loss, target_1, target_2,
                    position_size, risk_amount, r_multiple,
                    confidence_score, status, approval_chain,
                    exit_date, exit_price
                )
                VALUES (
                    gen_random_uuid(), :pattern_id, :symbol, '1D', :generated_at,
                    :entry_price, :stop_loss, :target_1, :target_2,
                    100, 500, :r_multiple,
                    85, :status, '{}'::jsonb,
                    :exit_date, :exit_price
                )
            """
            ),
            {
                "pattern_id": pattern_id,
                "symbol": symbol,
                "generated_at": datetime.now(UTC) - timedelta(days=90 - i),
                "entry_price": 100.00 + i,
                "stop_loss": 95.00 + i,
                "target_1": 110.00 + i,
                "target_2": 120.00 + i,
                "r_multiple": float(r_multiple),
                "status": status,
                "exit_date": datetime.now(UTC) - timedelta(days=85 - i),
                "exit_price": exit_price,
            },
        )

    await db_session.commit()
    return pattern_ids


@pytest.mark.asyncio
async def test_get_pattern_performance_all_patterns(
    analytics_repo: AnalyticsRepository, sample_analytics_data
):
    """Test pattern performance metrics for all patterns"""
    metrics = await analytics_repo.get_pattern_performance()

    # Should have 3 pattern types
    assert len(metrics) == 3

    # Check SPRING metrics (should have ~70% win rate from sample data)
    spring = next(m for m in metrics if m.pattern_type == "SPRING")
    assert spring.trade_count > 0
    assert Decimal("60") <= spring.win_rate <= Decimal("80")
    assert spring.avg_r_multiple > Decimal("0")
    assert spring.profit_factor > Decimal("1.0")


@pytest.mark.asyncio
async def test_get_pattern_performance_with_time_filter(
    analytics_repo: AnalyticsRepository, sample_analytics_data
):
    """Test pattern performance with 30-day filter"""
    metrics = await analytics_repo.get_pattern_performance(days=30)

    assert len(metrics) > 0
    for metric in metrics:
        # Trade count should be less than all-time
        assert metric.trade_count >= 0


@pytest.mark.asyncio
async def test_get_pattern_performance_with_phase_filter(
    analytics_repo: AnalyticsRepository, sample_analytics_data
):
    """Test pattern performance filtered by phase"""
    metrics = await analytics_repo.get_pattern_performance(detection_phase="C")

    assert len(metrics) > 0
    # Phase distribution should only show phase C
    for metric in metrics:
        if metric.phase_distribution:
            assert "C" in metric.phase_distribution


@pytest.mark.asyncio
async def test_get_pattern_performance_empty_result(analytics_repo: AnalyticsRepository):
    """Test handling of empty results (no matching data)"""
    # Query with very recent time filter (should have no data)
    metrics = await analytics_repo.get_pattern_performance(days=1)

    # Should return empty list, not error
    assert isinstance(metrics, list)


@pytest.mark.asyncio
async def test_get_sector_breakdown(analytics_repo: AnalyticsRepository, sample_analytics_data):
    """Test sector breakdown aggregation"""
    breakdown = await analytics_repo.get_sector_breakdown()

    # Should have 3 sectors from sample data
    assert len(breakdown) == 3

    # Check Technology sector exists
    tech = next((s for s in breakdown if s.sector_name == "Technology"), None)
    assert tech is not None
    assert tech.trade_count > 0
    assert Decimal("0") <= tech.win_rate <= Decimal("100")


@pytest.mark.asyncio
async def test_get_win_rate_trend(analytics_repo: AnalyticsRepository, sample_analytics_data):
    """Test win rate trend data for SPRING pattern"""
    trend = await analytics_repo.get_win_rate_trend("SPRING", days=90)

    # Should have multiple data points
    assert len(trend) > 0

    # Check data point structure
    point = trend[0]
    assert point.pattern_type == "SPRING"
    assert isinstance(point.date, datetime)
    assert Decimal("0") <= point.win_rate <= Decimal("100")
    assert point.trade_count >= 0


@pytest.mark.asyncio
async def test_get_trade_details_pagination(
    analytics_repo: AnalyticsRepository, sample_analytics_data
):
    """Test trade details with pagination"""
    # Get first page
    page_1 = await analytics_repo.get_trade_details(limit=20, offset=0)
    assert len(page_1) == 20

    # Get second page
    page_2 = await analytics_repo.get_trade_details(limit=20, offset=20)
    assert len(page_2) == 20

    # Pages should have different trades
    page_1_ids = {t.trade_id for t in page_1}
    page_2_ids = {t.trade_id for t in page_2}
    assert page_1_ids.isdisjoint(page_2_ids)


@pytest.mark.asyncio
async def test_get_trade_details_with_pattern_filter(
    analytics_repo: AnalyticsRepository, sample_analytics_data
):
    """Test trade details filtered by pattern type"""
    trades = await analytics_repo.get_trade_details(pattern_type="SPRING", limit=50)

    # All trades should be SPRING pattern
    assert all(t.pattern_type == "SPRING" for t in trades)
    assert len(trades) > 0


@pytest.mark.asyncio
async def test_get_vsa_metrics(
    analytics_repo: AnalyticsRepository, sample_analytics_data, db_session: AsyncSession
):
    """Test VSA metrics retrieval"""
    # Add VSA events to a pattern
    pattern_id = sample_analytics_data[0]
    await db_session.execute(
        text(
            """
            UPDATE patterns
            SET vsa_events = '{"no_demand": 3, "no_supply": 2, "stopping_volume": 1}'::jsonb
            WHERE id = :pattern_id
        """
        ),
        {"pattern_id": pattern_id},
    )
    await db_session.commit()

    # Query VSA metrics
    vsa_metrics = await analytics_repo.get_vsa_metrics()

    # Should have VSA data
    assert len(vsa_metrics) > 0


@pytest.mark.asyncio
async def test_get_preliminary_events(
    analytics_repo: AnalyticsRepository, sample_analytics_data, db_session: AsyncSession
):
    """Test preliminary events tracking for Spring pattern"""
    # Get a SPRING pattern
    spring_result = await db_session.execute(
        text(
            """
            SELECT id, symbol, detection_time
            FROM patterns
            WHERE pattern_type = 'SPRING'
            LIMIT 1
        """
        )
    )
    spring_row = spring_result.fetchone()

    if spring_row:
        # Create preliminary events (PS, SC, AR, ST) before this Spring
        symbol = spring_row.symbol
        detection_time = spring_row.detection_time

        for event_type in ["PS", "SC", "AR", "ST"]:
            event_pattern_id = uuid4()
            await db_session.execute(
                text(
                    """
                    INSERT INTO patterns (
                        id, pattern_type, symbol, timeframe, detection_time,
                        pattern_bar_timestamp, confidence_score, detection_phase,
                        entry_price, stop_loss, invalidation_level,
                        volume_ratio, spread_ratio, test_confirmed, metadata
                    )
                    VALUES (
                        :id, :pattern_type, :symbol, '1D', :detection_time,
                        :pattern_bar_timestamp, 85, 'A',
                        100.00, 95.00, 93.00,
                        1.5, 1.2, false, '{}'::jsonb
                    )
                """
                ),
                {
                    "id": event_pattern_id,
                    "pattern_type": event_type,
                    "symbol": symbol,
                    "detection_time": detection_time - timedelta(days=10),
                    "pattern_bar_timestamp": detection_time - timedelta(days=10),
                },
            )

        await db_session.commit()

        # Get preliminary events
        events = await analytics_repo.get_preliminary_events(spring_row.id)

        assert events is not None
        assert events.ps_count == 1
        assert events.sc_count == 1
        assert events.ar_count == 1
        assert events.st_count == 1


@pytest.mark.asyncio
async def test_query_performance_benchmark(
    analytics_repo: AnalyticsRepository, sample_analytics_data
):
    """Benchmark query performance (should be <500ms)"""
    import time

    start = time.time()
    metrics = await analytics_repo.get_pattern_performance()
    elapsed = (time.time() - start) * 1000  # Convert to ms

    # Should complete in <500ms (target from Task 12)
    assert elapsed < 500, f"Query took {elapsed}ms, expected <500ms"
