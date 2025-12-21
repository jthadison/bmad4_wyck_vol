"""
Walk-Forward Repository (Story 12.4 Task 10).

Provides persistence and retrieval for WalkForwardResult objects.
Stores walk-forward test results in the database with JSONB serialization.

Author: Story 12.4 Task 10
"""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.backtest import (
    ValidationWindow,
    WalkForwardChartData,
    WalkForwardConfig,
    WalkForwardResult,
)
from src.repositories.models import WalkForwardResultModel


class WalkForwardRepository:
    """
    Repository for WalkForwardResult persistence.

    Handles serialization/deserialization of complex Pydantic models to/from
    JSONB database storage.

    AC10: Implement save_result, get_result, list_results with pagination.

    Example:
        repository = WalkForwardRepository(session)
        walk_forward_id = await repository.save_result(result)
        retrieved = await repository.get_result(walk_forward_id)
        all_results = await repository.list_results(limit=10)
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy async session
        """
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)

    async def save_result(self, result: WalkForwardResult) -> UUID:
        """
        Persist a WalkForwardResult to the database.

        AC10 Subtask 10.2-10.6: Store WalkForwardResult with JSONB serialization.

        Args:
            result: WalkForwardResult to save

        Returns:
            walk_forward_id of the saved result

        Example:
            result = WalkForwardResult(...)
            wf_id = await repository.save_result(result)
        """
        self.logger.info(
            "save_walk_forward_result",
            walk_forward_id=str(result.walk_forward_id),
            windows=len(result.windows),
        )

        # Serialize complex nested models to dictionaries
        db_result = WalkForwardResultModel(
            walk_forward_id=result.walk_forward_id,
            config=result.config.model_dump(mode="json"),
            windows=[window.model_dump(mode="json") for window in result.windows],
            summary_statistics=result.summary_statistics,
            stability_score=result.stability_score,
            degradation_windows=result.degradation_windows,
            statistical_significance=result.statistical_significance,
            chart_data=(result.chart_data.model_dump(mode="json") if result.chart_data else None),
            total_execution_time_seconds=result.total_execution_time_seconds,
            avg_window_execution_time_seconds=result.avg_window_execution_time_seconds,
            created_at=result.created_at,
        )

        # Add to session and commit
        self.db_session.add(db_result)
        await self.db_session.commit()
        await self.db_session.refresh(db_result)

        self.logger.info(
            "save_walk_forward_result_completed",
            walk_forward_id=str(result.walk_forward_id),
            id=str(db_result.id),
        )

        return result.walk_forward_id

    async def get_result(self, walk_forward_id: UUID) -> Optional[WalkForwardResult]:
        """
        Retrieve a WalkForwardResult by ID.

        AC10 Subtask 10.7-10.8: Deserialize JSONB back to Pydantic models.

        Args:
            walk_forward_id: UUID of the walk-forward test

        Returns:
            WalkForwardResult if found, None otherwise

        Example:
            result = await repository.get_result(wf_id)
            if result:
                print(f"Found {len(result.windows)} windows")
        """
        self.logger.info("get_walk_forward_result", walk_forward_id=str(walk_forward_id))

        # Query database
        stmt = select(WalkForwardResultModel).where(
            WalkForwardResultModel.walk_forward_id == walk_forward_id
        )
        result_row = await self.db_session.execute(stmt)
        db_result = result_row.scalar_one_or_none()

        if db_result is None:
            self.logger.warning(
                "walk_forward_result_not_found", walk_forward_id=str(walk_forward_id)
            )
            return None

        # Deserialize JSONB to Pydantic models
        config = WalkForwardConfig.model_validate(db_result.config)

        windows = [ValidationWindow.model_validate(w) for w in db_result.windows]

        chart_data = (
            WalkForwardChartData.model_validate(db_result.chart_data)
            if db_result.chart_data
            else None
        )

        result = WalkForwardResult(
            walk_forward_id=db_result.walk_forward_id,
            config=config,
            windows=windows,
            summary_statistics=db_result.summary_statistics,
            stability_score=db_result.stability_score,
            degradation_windows=db_result.degradation_windows,
            statistical_significance=db_result.statistical_significance,
            chart_data=chart_data,
            total_execution_time_seconds=db_result.total_execution_time_seconds,
            avg_window_execution_time_seconds=db_result.avg_window_execution_time_seconds,
            created_at=db_result.created_at,
        )

        self.logger.info(
            "get_walk_forward_result_completed",
            walk_forward_id=str(walk_forward_id),
            windows=len(result.windows),
        )

        return result

    async def list_results(self, limit: int = 10, offset: int = 0) -> list[WalkForwardResult]:
        """
        List walk-forward results with pagination.

        AC10 Subtask 10.9-10.10: List results ordered by created_at DESC.

        Args:
            limit: Maximum number of results to return (default 10)
            offset: Number of results to skip (default 0)

        Returns:
            List of WalkForwardResult objects

        Example:
            # Get first 10 results
            results = await repository.list_results(limit=10, offset=0)

            # Get next 10 results
            results = await repository.list_results(limit=10, offset=10)
        """
        self.logger.info("list_walk_forward_results", limit=limit, offset=offset)

        # Query database with pagination
        stmt = (
            select(WalkForwardResultModel)
            .order_by(WalkForwardResultModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result_rows = await self.db_session.execute(stmt)
        db_results = result_rows.scalars().all()

        # Deserialize to Pydantic models
        results = []
        for db_result in db_results:
            config = WalkForwardConfig.model_validate(db_result.config)
            windows = [ValidationWindow.model_validate(w) for w in db_result.windows]
            chart_data = (
                WalkForwardChartData.model_validate(db_result.chart_data)
                if db_result.chart_data
                else None
            )

            result = WalkForwardResult(
                walk_forward_id=db_result.walk_forward_id,
                config=config,
                windows=windows,
                summary_statistics=db_result.summary_statistics,
                stability_score=db_result.stability_score,
                degradation_windows=db_result.degradation_windows,
                statistical_significance=db_result.statistical_significance,
                chart_data=chart_data,
                total_execution_time_seconds=db_result.total_execution_time_seconds,
                avg_window_execution_time_seconds=db_result.avg_window_execution_time_seconds,
                created_at=db_result.created_at,
            )
            results.append(result)

        self.logger.info(
            "list_walk_forward_results_completed", count=len(results), limit=limit, offset=offset
        )

        return results
