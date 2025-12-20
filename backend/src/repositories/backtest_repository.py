"""
Backtest Repository (Story 12.1 Task 9).

Provides persistence and retrieval for BacktestResult objects.
Stores backtest results in the database with JSONB serialization for
complex nested structures (equity curves, trades, config, metrics).

Author: Story 12.1 Task 9
"""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.backtest import BacktestResult, BacktestTrade, EquityCurvePoint
from src.repositories.models import BacktestResultModel


class BacktestRepository:
    """
    Repository for BacktestResult persistence.

    Handles serialization/deserialization of complex Pydantic models to/from
    JSONB database storage.

    AC10: Implement save_result, get_result, list_results with pagination.

    Example:
        repository = BacktestRepository(session)
        backtest_run_id = await repository.save_result(result)
        retrieved = await repository.get_result(backtest_run_id)
        all_results = await repository.list_results(symbol="AAPL", limit=10)
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy async session
        """
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)

    async def save_result(self, result: BacktestResult) -> UUID:
        """
        Persist a BacktestResult to the database.

        AC10 Subtask 9.2-9.6: Store BacktestResult with JSONB serialization.

        Args:
            result: BacktestResult to save

        Returns:
            backtest_run_id of the saved result

        Example:
            result = BacktestResult(...)
            run_id = await repository.save_result(result)
        """
        self.logger.info(
            "save_result",
            backtest_run_id=str(result.backtest_run_id),
            symbol=result.symbol,
            trades=len(result.trades),
        )

        # Serialize complex nested models to dictionaries
        db_result = BacktestResultModel(
            backtest_run_id=result.backtest_run_id,
            symbol=result.symbol,
            timeframe=result.timeframe,
            start_date=result.start_date,
            end_date=result.end_date,
            config=result.config.model_dump(mode="json"),
            equity_curve=[point.model_dump(mode="json") for point in result.equity_curve],
            trades=[trade.model_dump(mode="json") for trade in result.trades],
            metrics=result.metrics.model_dump(mode="json"),
            look_ahead_bias_check=result.look_ahead_bias_check,
            execution_time_seconds=result.execution_time_seconds,
            created_at=result.created_at,
        )

        # Add to session and commit
        self.db_session.add(db_result)
        await self.db_session.commit()
        await self.db_session.refresh(db_result)

        self.logger.info(
            "save_result_completed",
            backtest_run_id=str(result.backtest_run_id),
            id=str(db_result.id),
        )

        return result.backtest_run_id

    async def get_result(self, backtest_run_id: UUID) -> Optional[BacktestResult]:
        """
        Retrieve a BacktestResult by backtest_run_id.

        AC10 Subtask 9.7-9.8: Deserialize JSONB fields back to Pydantic models.

        Args:
            backtest_run_id: Backtest run identifier

        Returns:
            BacktestResult if found, None otherwise

        Example:
            result = await repository.get_result(run_id)
            if result:
                print(f"Win rate: {result.metrics.win_rate}")
        """
        # Query by backtest_run_id
        stmt = select(BacktestResultModel).where(
            BacktestResultModel.backtest_run_id == backtest_run_id
        )
        db_result = await self.db_session.scalar(stmt)

        if not db_result:
            self.logger.warning("get_result_not_found", backtest_run_id=str(backtest_run_id))
            return None

        # Deserialize JSONB fields back to Pydantic models
        result = self._deserialize_result(db_result)

        self.logger.info(
            "get_result_success",
            backtest_run_id=str(backtest_run_id),
            trades=len(result.trades),
        )

        return result

    async def list_results(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BacktestResult]:
        """
        List BacktestResults with optional filtering and pagination.

        AC10 Subtask 9.9-9.10: Filter by symbol, order by created_at DESC, paginate.

        Args:
            symbol: Optional symbol filter
            limit: Maximum number of results (default 100)
            offset: Number of results to skip (default 0)

        Returns:
            List of BacktestResult objects

        Example:
            # Get first 10 AAPL backtests
            results = await repository.list_results(symbol="AAPL", limit=10)

            # Get next 10 (pagination)
            next_results = await repository.list_results(symbol="AAPL", limit=10, offset=10)
        """
        # Build query
        stmt = select(BacktestResultModel)

        # Apply symbol filter if provided
        if symbol:
            stmt = stmt.where(BacktestResultModel.symbol == symbol)

        # Order by created_at DESC (most recent first)
        stmt = stmt.order_by(BacktestResultModel.created_at.desc())

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        db_results = await self.db_session.scalars(stmt)

        # Deserialize all results
        results = [self._deserialize_result(db_result) for db_result in db_results]

        self.logger.info(
            "list_results",
            symbol=symbol,
            limit=limit,
            offset=offset,
            count=len(results),
        )

        return results

    def _deserialize_result(self, db_result: BacktestResultModel) -> BacktestResult:
        """
        Deserialize database model to Pydantic BacktestResult.

        AC10 Subtask 9.8: Deserialize JSONB fields back to Pydantic models.

        Args:
            db_result: Database model instance

        Returns:
            BacktestResult Pydantic model
        """
        from src.models.backtest import BacktestConfig, BacktestMetrics

        # Deserialize equity curve
        equity_curve = [EquityCurvePoint(**point) for point in db_result.equity_curve]

        # Deserialize trades
        trades = [BacktestTrade(**trade) for trade in db_result.trades]

        # Deserialize config
        config = BacktestConfig(**db_result.config)

        # Deserialize metrics
        metrics = BacktestMetrics(**db_result.metrics)

        return BacktestResult(
            backtest_run_id=db_result.backtest_run_id,
            symbol=db_result.symbol,
            timeframe=db_result.timeframe,
            start_date=db_result.start_date.date(),
            end_date=db_result.end_date.date(),
            config=config,
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
            look_ahead_bias_check=db_result.look_ahead_bias_check,
            execution_time_seconds=float(db_result.execution_time_seconds),
            created_at=db_result.created_at,
        )
