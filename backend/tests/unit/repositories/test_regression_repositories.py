"""
Unit tests for Regression Testing Repositories (Story 12.7 Task 14).

Tests:
- RegressionTestRepository: save_result, get_result, list_results
- RegressionBaselineRepository: save_baseline, get_current_baseline, update_baseline_status, list_baselines
- Edge cases: Not found, empty results, baseline uniqueness

Author: Story 12.7 Task 14
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    BacktestResult,
    MetricComparison,
    RegressionBaseline,
    RegressionComparison,
    RegressionTestConfig,
    RegressionTestResult,
)
from src.orm.models import RegressionBaselineORM, RegressionTestResultORM
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository


@pytest.fixture
def sample_backtest_config():
    """Fixture for BacktestConfig."""
    return BacktestConfig(
        symbol="AAPL",
        entry_type="aggressive",
        position_sizing="fixed",
        initial_capital=Decimal("100000"),
        position_size_usd=Decimal("10000"),
        commission_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.001"),
    )


@pytest.fixture
def sample_backtest_metrics():
    """Fixture for BacktestMetrics."""
    return BacktestMetrics(
        total_signals=10,
        win_rate=Decimal("0.6000"),
        average_r_multiple=Decimal("2.0000"),
        profit_factor=Decimal("2.5000"),
        max_drawdown=Decimal("0.0500"),
        sharpe_ratio=Decimal("1.8000"),
        total_trades=10,
        winning_trades=6,
        losing_trades=4,
    )


@pytest.fixture
def sample_backtest_result(sample_backtest_config, sample_backtest_metrics):
    """Fixture for BacktestResult."""
    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        config=sample_backtest_config,
        trades=[],
        equity_curve=[],
        metrics=sample_backtest_metrics,
        execution_time_seconds=5.0,
    )


@pytest.fixture
def sample_regression_test_config(sample_backtest_config):
    """Fixture for RegressionTestConfig."""
    return RegressionTestConfig(
        symbols=["AAPL", "MSFT"],
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        backtest_config=sample_backtest_config,
        degradation_thresholds={
            "win_rate": Decimal("5.0"),
            "avg_r_multiple": Decimal("10.0"),
        },
    )


@pytest.fixture
def sample_regression_test_result(
    sample_regression_test_config, sample_backtest_result, sample_backtest_metrics
):
    """Fixture for RegressionTestResult."""
    return RegressionTestResult(
        config=sample_regression_test_config,
        codebase_version="abc123f",
        aggregate_metrics=sample_backtest_metrics,
        per_symbol_results={
            "AAPL": sample_backtest_result,
            "MSFT": sample_backtest_result,
        },
        baseline_comparison=None,
        regression_detected=False,
        degraded_metrics=[],
        status="BASELINE_NOT_SET",
        execution_time_seconds=10.0,
    )


@pytest.fixture
def sample_regression_baseline(sample_backtest_metrics):
    """Fixture for RegressionBaseline."""
    return RegressionBaseline(
        test_id=uuid4(),
        version="abc123f",
        metrics=sample_backtest_metrics,
        per_symbol_metrics={
            "AAPL": sample_backtest_metrics,
            "MSFT": sample_backtest_metrics,
        },
        is_current=True,
    )


class TestRegressionTestRepository:
    """Tests for RegressionTestRepository."""

    @pytest.mark.asyncio
    async def test_save_result(self, async_db_session, sample_regression_test_result):
        """Test saving regression test result to database."""
        repo = RegressionTestRepository(async_db_session)

        # Save result
        saved_test_id = await repo.save_result(sample_regression_test_result)

        assert saved_test_id == sample_regression_test_result.test_id

        # Verify in database
        stmt = select(RegressionTestResultORM).where(
            RegressionTestResultORM.test_id == saved_test_id
        )
        result = await async_db_session.execute(stmt)
        orm_model = result.scalar_one_or_none()

        assert orm_model is not None
        assert orm_model.test_id == saved_test_id
        assert orm_model.status == "BASELINE_NOT_SET"
        assert orm_model.codebase_version == "abc123f"
        assert orm_model.regression_detected is False
        assert orm_model.degraded_metrics == []

    @pytest.mark.asyncio
    async def test_get_result(self, async_db_session, sample_regression_test_result):
        """Test retrieving regression test result by test_id."""
        repo = RegressionTestRepository(async_db_session)

        # Save result
        saved_test_id = await repo.save_result(sample_regression_test_result)

        # Retrieve result
        retrieved_result = await repo.get_result(saved_test_id)

        assert retrieved_result is not None
        assert retrieved_result.test_id == saved_test_id
        assert retrieved_result.status == "BASELINE_NOT_SET"
        assert retrieved_result.codebase_version == "abc123f"
        assert retrieved_result.regression_detected is False
        assert len(retrieved_result.per_symbol_results) == 2

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, async_db_session):
        """Test retrieving non-existent regression test result returns None."""
        repo = RegressionTestRepository(async_db_session)

        result = await repo.get_result(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_list_results_empty(self, async_db_session):
        """Test listing results when database is empty."""
        repo = RegressionTestRepository(async_db_session)

        results = await repo.list_results()

        assert results == []

    @pytest.mark.asyncio
    async def test_list_results_pagination(self, async_db_session, sample_regression_test_result):
        """Test listing results with pagination."""
        repo = RegressionTestRepository(async_db_session)

        # Create 5 test results
        test_ids = []
        for i in range(5):
            result = sample_regression_test_result.model_copy()
            result.test_id = uuid4()
            await repo.save_result(result)
            test_ids.append(result.test_id)

        # List with limit
        results = await repo.list_results(limit=3)
        assert len(results) == 3

        # List with offset
        results = await repo.list_results(limit=3, offset=3)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_results_status_filter(
        self, async_db_session, sample_regression_test_result
    ):
        """Test listing results with status filter."""
        repo = RegressionTestRepository(async_db_session)

        # Create results with different statuses
        result_pass = sample_regression_test_result.model_copy()
        result_pass.test_id = uuid4()
        result_pass.status = "PASS"
        await repo.save_result(result_pass)

        result_fail = sample_regression_test_result.model_copy()
        result_fail.test_id = uuid4()
        result_fail.status = "FAIL"
        await repo.save_result(result_fail)

        result_baseline_not_set = sample_regression_test_result.model_copy()
        result_baseline_not_set.test_id = uuid4()
        result_baseline_not_set.status = "BASELINE_NOT_SET"
        await repo.save_result(result_baseline_not_set)

        # Filter by PASS
        results = await repo.list_results(status_filter="PASS")
        assert len(results) == 1
        assert results[0].status == "PASS"

        # Filter by FAIL
        results = await repo.list_results(status_filter="FAIL")
        assert len(results) == 1
        assert results[0].status == "FAIL"

        # Filter by BASELINE_NOT_SET
        results = await repo.list_results(status_filter="BASELINE_NOT_SET")
        assert len(results) == 1
        assert results[0].status == "BASELINE_NOT_SET"


class TestRegressionBaselineRepository:
    """Tests for RegressionBaselineRepository."""

    @pytest.mark.asyncio
    async def test_save_baseline(self, async_db_session, sample_regression_baseline):
        """Test saving regression baseline to database."""
        repo = RegressionBaselineRepository(async_db_session)

        # Save baseline
        saved_baseline_id = await repo.save_baseline(sample_regression_baseline)

        assert saved_baseline_id == sample_regression_baseline.baseline_id

        # Verify in database
        stmt = select(RegressionBaselineORM).where(
            RegressionBaselineORM.baseline_id == saved_baseline_id
        )
        result = await async_db_session.execute(stmt)
        orm_model = result.scalar_one_or_none()

        assert orm_model is not None
        assert orm_model.baseline_id == saved_baseline_id
        assert orm_model.is_current is True
        assert orm_model.version == "abc123f"

    @pytest.mark.asyncio
    async def test_get_current_baseline(self, async_db_session, sample_regression_baseline):
        """Test retrieving current baseline."""
        repo = RegressionBaselineRepository(async_db_session)

        # Save baseline as current
        await repo.save_baseline(sample_regression_baseline)

        # Retrieve current baseline
        current_baseline = await repo.get_current_baseline()

        assert current_baseline is not None
        assert current_baseline.baseline_id == sample_regression_baseline.baseline_id
        assert current_baseline.is_current is True

    @pytest.mark.asyncio
    async def test_get_current_baseline_none(self, async_db_session):
        """Test retrieving current baseline when none exists."""
        repo = RegressionBaselineRepository(async_db_session)

        current_baseline = await repo.get_current_baseline()

        assert current_baseline is None

    @pytest.mark.asyncio
    async def test_update_baseline_status(self, async_db_session, sample_regression_baseline):
        """Test updating baseline is_current status."""
        repo = RegressionBaselineRepository(async_db_session)

        # Save baseline as current
        baseline_id = await repo.save_baseline(sample_regression_baseline)

        # Update to not current
        await repo.update_baseline_status(baseline_id, is_current=False)

        # Verify update
        stmt = select(RegressionBaselineORM).where(RegressionBaselineORM.baseline_id == baseline_id)
        result = await async_db_session.execute(stmt)
        orm_model = result.scalar_one_or_none()

        assert orm_model is not None
        assert orm_model.is_current is False

    @pytest.mark.asyncio
    async def test_baseline_uniqueness_constraint(
        self, async_db_session, sample_regression_baseline
    ):
        """Test that only one baseline can be current at a time."""
        repo = RegressionBaselineRepository(async_db_session)

        # Save first baseline as current
        first_baseline = sample_regression_baseline.model_copy()
        first_baseline.baseline_id = uuid4()
        first_baseline.is_current = True
        await repo.save_baseline(first_baseline)

        # Update first to not current
        await repo.update_baseline_status(first_baseline.baseline_id, is_current=False)

        # Save second baseline as current
        second_baseline = sample_regression_baseline.model_copy()
        second_baseline.baseline_id = uuid4()
        second_baseline.is_current = True
        await repo.save_baseline(second_baseline)

        # Verify only second is current
        current_baseline = await repo.get_current_baseline()
        assert current_baseline.baseline_id == second_baseline.baseline_id

    @pytest.mark.asyncio
    async def test_list_baselines_empty(self, async_db_session):
        """Test listing baselines when database is empty."""
        repo = RegressionBaselineRepository(async_db_session)

        baselines = await repo.list_baselines()

        assert baselines == []

    @pytest.mark.asyncio
    async def test_list_baselines_pagination(self, async_db_session, sample_regression_baseline):
        """Test listing baselines with pagination."""
        repo = RegressionBaselineRepository(async_db_session)

        # Create 5 baselines (only last one is current)
        baseline_ids = []
        for i in range(5):
            baseline = sample_regression_baseline.model_copy()
            baseline.baseline_id = uuid4()
            baseline.is_current = i == 4  # Last one is current
            await repo.save_baseline(baseline)
            baseline_ids.append(baseline.baseline_id)

        # List with limit
        baselines = await repo.list_baselines(limit=3)
        assert len(baselines) == 3

        # List with offset
        baselines = await repo.list_baselines(limit=3, offset=3)
        assert len(baselines) == 2

    @pytest.mark.asyncio
    async def test_list_baselines_ordering(self, async_db_session, sample_regression_baseline):
        """Test that baselines are ordered by established_at DESC."""
        repo = RegressionBaselineRepository(async_db_session)

        # Create baselines with different timestamps
        baseline1 = sample_regression_baseline.model_copy()
        baseline1.baseline_id = uuid4()
        baseline1.established_at = datetime(2024, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        baseline1.is_current = False
        await repo.save_baseline(baseline1)

        baseline2 = sample_regression_baseline.model_copy()
        baseline2.baseline_id = uuid4()
        baseline2.established_at = datetime(2024, 12, 1, tzinfo=UTC).replace(tzinfo=None)
        baseline2.is_current = True
        await repo.save_baseline(baseline2)

        baseline3 = sample_regression_baseline.model_copy()
        baseline3.baseline_id = uuid4()
        baseline3.established_at = datetime(2024, 6, 1, tzinfo=UTC).replace(tzinfo=None)
        baseline3.is_current = False
        await repo.save_baseline(baseline3)

        # List all baselines
        baselines = await repo.list_baselines(limit=10)

        # Should be ordered by established_at DESC
        assert baselines[0].baseline_id == baseline2.baseline_id  # 2024-12-01
        assert baselines[1].baseline_id == baseline3.baseline_id  # 2024-06-01
        assert baselines[2].baseline_id == baseline1.baseline_id  # 2024-01-01


class TestRegressionRepositoriesIntegration:
    """Integration tests for regression repositories working together."""

    @pytest.mark.asyncio
    async def test_full_regression_workflow(
        self,
        async_db_session,
        sample_regression_test_result,
        sample_regression_baseline,
    ):
        """Test complete workflow: run test, establish baseline, run test again."""
        test_repo = RegressionTestRepository(async_db_session)
        baseline_repo = RegressionBaselineRepository(async_db_session)

        # Step 1: Run initial regression test (no baseline)
        test_result1 = sample_regression_test_result.model_copy()
        test_result1.test_id = uuid4()
        test_result1.status = "BASELINE_NOT_SET"
        await test_repo.save_result(test_result1)

        # Step 2: Establish baseline from test result
        baseline = sample_regression_baseline.model_copy()
        baseline.baseline_id = uuid4()
        baseline.test_id = test_result1.test_id
        baseline.is_current = True
        await baseline_repo.save_baseline(baseline)

        # Verify baseline is current
        current_baseline = await baseline_repo.get_current_baseline()
        assert current_baseline is not None
        assert current_baseline.baseline_id == baseline.baseline_id

        # Step 3: Run second regression test (with baseline comparison)
        test_result2 = sample_regression_test_result.model_copy()
        test_result2.test_id = uuid4()
        test_result2.status = "PASS"
        test_result2.baseline_comparison = RegressionComparison(
            baseline_id=baseline.baseline_id,
            baseline_version="abc123f",
            metric_comparisons={
                "win_rate": MetricComparison(
                    metric_name="win_rate",
                    baseline_value=Decimal("0.6000"),
                    current_value=Decimal("0.6100"),
                    absolute_change=Decimal("0.0100"),
                    percent_change=Decimal("1.67"),
                    threshold=Decimal("5.0"),
                    degraded=False,
                )
            },
        )
        await test_repo.save_result(test_result2)

        # Step 4: Verify both results exist
        retrieved_test1 = await test_repo.get_result(test_result1.test_id)
        retrieved_test2 = await test_repo.get_result(test_result2.test_id)

        assert retrieved_test1 is not None
        assert retrieved_test1.status == "BASELINE_NOT_SET"
        assert retrieved_test2 is not None
        assert retrieved_test2.status == "PASS"
        assert retrieved_test2.baseline_comparison is not None

    @pytest.mark.asyncio
    async def test_baseline_management_workflow(self, async_db_session, sample_regression_baseline):
        """Test baseline management: create, update current flag, create new."""
        baseline_repo = RegressionBaselineRepository(async_db_session)

        # Create first baseline
        baseline1 = sample_regression_baseline.model_copy()
        baseline1.baseline_id = uuid4()
        baseline1.is_current = True
        await baseline_repo.save_baseline(baseline1)

        # Verify it's current
        current = await baseline_repo.get_current_baseline()
        assert current.baseline_id == baseline1.baseline_id

        # Mark first as not current
        await baseline_repo.update_baseline_status(baseline1.baseline_id, is_current=False)

        # Create second baseline as current
        baseline2 = sample_regression_baseline.model_copy()
        baseline2.baseline_id = uuid4()
        baseline2.is_current = True
        await baseline_repo.save_baseline(baseline2)

        # Verify second is now current
        current = await baseline_repo.get_current_baseline()
        assert current.baseline_id == baseline2.baseline_id

        # List history - should have both baselines
        history = await baseline_repo.list_baselines(limit=10)
        assert len(history) == 2
