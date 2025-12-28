"""
Regression Test Repository (Story 12.7 Task 4).

Stores and retrieves regression test results from database.

Author: Story 12.7 Task 4
"""

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.backtest import RegressionTestResult
from src.orm.models import RegressionTestResultORM


class RegressionTestRepository:
    """Repository for regression test results."""

    def __init__(self, db: AsyncSession):
        """
        Initialize repository.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db

    async def save_result(self, result: RegressionTestResult) -> UUID:
        """
        Save regression test result to database.

        Args:
            result: RegressionTestResult to save

        Returns:
            UUID of saved result
        """
        # Convert Pydantic model to dict for JSONB storage
        result_dict = result.model_dump(mode="json")

        # Create ORM model
        orm_model = RegressionTestResultORM(
            id=uuid4(),
            test_id=result.test_id,
            config=result_dict["config"],
            test_run_time=result.test_run_time,
            codebase_version=result.codebase_version,
            aggregate_metrics=result_dict["aggregate_metrics"],
            per_symbol_results=result_dict["per_symbol_results"],
            baseline_comparison=result_dict.get("baseline_comparison"),
            regression_detected=result.regression_detected,
            degraded_metrics=result.degraded_metrics,
            status=result.status,
            execution_time_seconds=result.execution_time_seconds,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )

        # Add to session and commit
        self.db.add(orm_model)
        await self.db.commit()
        await self.db.refresh(orm_model)

        return result.test_id

    async def get_result(self, test_id: UUID) -> Optional[RegressionTestResult]:
        """
        Retrieve regression test result by ID.

        Args:
            test_id: Test ID to retrieve

        Returns:
            RegressionTestResult if found, None otherwise
        """
        # Query by test_id
        stmt = select(RegressionTestResultORM).where(RegressionTestResultORM.test_id == test_id)
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()

        if not orm_model:
            return None

        # Deserialize JSONB to Pydantic model
        return RegressionTestResult(
            test_id=orm_model.test_id,
            config=orm_model.config,
            test_run_time=orm_model.test_run_time,
            codebase_version=orm_model.codebase_version,
            aggregate_metrics=orm_model.aggregate_metrics,
            per_symbol_results=orm_model.per_symbol_results,
            baseline_comparison=orm_model.baseline_comparison,
            regression_detected=orm_model.regression_detected,
            degraded_metrics=orm_model.degraded_metrics,
            status=orm_model.status,
            execution_time_seconds=orm_model.execution_time_seconds,
        )

    async def list_results(
        self, limit: int = 50, offset: int = 0, status_filter: Optional[str] = None
    ) -> list[RegressionTestResult]:
        """
        List regression test results with pagination.

        Args:
            limit: Maximum results to return
            offset: Number of results to skip
            status_filter: Filter by status (PASS/FAIL/BASELINE_NOT_SET)

        Returns:
            List of RegressionTestResult ordered by test_run_time DESC
        """
        # Build query with optional status filter
        stmt = select(RegressionTestResultORM)

        if status_filter:
            stmt = stmt.where(RegressionTestResultORM.status == status_filter)

        # Order by test_run_time DESC, apply pagination
        stmt = stmt.order_by(desc(RegressionTestResultORM.test_run_time))
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()

        # Deserialize to Pydantic models
        return [
            RegressionTestResult(
                test_id=orm_model.test_id,
                config=orm_model.config,
                test_run_time=orm_model.test_run_time,
                codebase_version=orm_model.codebase_version,
                aggregate_metrics=orm_model.aggregate_metrics,
                per_symbol_results=orm_model.per_symbol_results,
                baseline_comparison=orm_model.baseline_comparison,
                regression_detected=orm_model.regression_detected,
                degraded_metrics=orm_model.degraded_metrics,
                status=orm_model.status,
                execution_time_seconds=orm_model.execution_time_seconds,
            )
            for orm_model in orm_models
        ]


async def get_regression_test_repository() -> RegressionTestRepository:
    """Dependency injection factory for RegressionTestRepository."""
    async for db in get_db():
        return RegressionTestRepository(db)
    raise RuntimeError("Failed to get database session")
