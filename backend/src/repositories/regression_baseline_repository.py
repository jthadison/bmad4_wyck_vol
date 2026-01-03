"""
Regression Baseline Repository (Story 12.7 Task 5).

Stores and retrieves regression baselines from database.

Author: Story 12.7 Task 5
"""

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.backtest import RegressionBaseline
from src.orm.models import RegressionBaselineORM


class RegressionBaselineRepository:
    """Repository for regression baselines."""

    def __init__(self, db: AsyncSession):
        """
        Initialize repository.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db

    async def save_baseline(self, baseline: RegressionBaseline) -> UUID:
        """
        Save regression baseline to database.

        Args:
            baseline: RegressionBaseline to save

        Returns:
            UUID of saved baseline
        """
        # Convert Pydantic model to dict for JSONB storage
        baseline_dict = baseline.model_dump(mode="json")

        # Create ORM model
        orm_model = RegressionBaselineORM(
            id=uuid4(),
            baseline_id=baseline.baseline_id,
            test_id=baseline.test_id,
            version=baseline.version,
            metrics=baseline_dict["metrics"],
            per_symbol_metrics=baseline_dict["per_symbol_metrics"],
            established_at=baseline.established_at,
            is_current=baseline.is_current,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )

        # Add to session and commit
        self.db.add(orm_model)
        await self.db.commit()
        await self.db.refresh(orm_model)

        return baseline.baseline_id

    async def get_current_baseline(self) -> Optional[RegressionBaseline]:
        """
        Retrieve current active baseline.

        Returns:
            RegressionBaseline if exists, None otherwise
        """
        # Query for baseline where is_current=True
        # Database enforces unique constraint on is_current=True
        stmt = select(RegressionBaselineORM).where(RegressionBaselineORM.is_current == True)
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()

        if not orm_model:
            return None

        # Deserialize JSONB to Pydantic model
        return RegressionBaseline(
            baseline_id=orm_model.baseline_id,
            test_id=orm_model.test_id,
            version=orm_model.version,
            metrics=orm_model.summary,
            per_symbol_metrics=orm_model.per_symbol_metrics,
            established_at=orm_model.established_at,
            is_current=orm_model.is_current,
        )

    async def update_baseline_status(self, baseline_id: UUID, is_current: bool) -> None:
        """
        Update is_current status of a baseline.

        Args:
            baseline_id: Baseline ID to update
            is_current: New is_current value
        """
        # Update the is_current field
        stmt = (
            update(RegressionBaselineORM)
            .where(RegressionBaselineORM.baseline_id == baseline_id)
            .values(
                is_current=is_current,
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def list_baselines(self, limit: int = 10, offset: int = 0) -> list[RegressionBaseline]:
        """
        List regression baselines with pagination.

        Args:
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of RegressionBaseline ordered by established_at DESC
        """
        # Query with pagination
        stmt = select(RegressionBaselineORM)
        stmt = stmt.order_by(desc(RegressionBaselineORM.established_at))
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        result = await self.db.execute(stmt)
        orm_models = result.scalars().all()

        # Deserialize to Pydantic models
        return [
            RegressionBaseline(
                baseline_id=orm_model.baseline_id,
                test_id=orm_model.test_id,
                version=orm_model.version,
                metrics=orm_model.summary,
                per_symbol_metrics=orm_model.per_symbol_metrics,
                established_at=orm_model.established_at,
                is_current=orm_model.is_current,
            )
            for orm_model in orm_models
        ]


async def get_regression_baseline_repository() -> RegressionBaselineRepository:
    """Dependency injection factory for RegressionBaselineRepository."""
    async for db in get_db():
        return RegressionBaselineRepository(db)
    raise RuntimeError("Failed to get database session")
