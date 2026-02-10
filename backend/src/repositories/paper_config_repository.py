"""
Paper Config Repository (Story 23.8a)

Repository for accessing and updating paper trading configuration (singleton).
"""

from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.paper_trading import PaperTradingConfig
from src.repositories.paper_trading_orm import PaperTradingConfigDB

logger = structlog.get_logger(__name__)


class PaperConfigRepository:
    """
    Repository for paper trading config operations.

    The config is a singleton - only one config row exists for the system.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get_config(self) -> Optional[PaperTradingConfig]:
        """
        Get the paper trading config (singleton).

        Returns:
            PaperTradingConfig if exists, None otherwise
        """
        stmt = select(PaperTradingConfigDB).limit(1)
        result = await self.session.execute(stmt)
        config_db = result.scalars().first()

        if not config_db:
            logger.debug("paper_config_not_found")
            return None

        return self._to_model(config_db)

    async def save_config(self, config: PaperTradingConfig) -> PaperTradingConfig:
        """
        Create or update the paper trading config (upsert singleton).

        Args:
            config: PaperTradingConfig model to save

        Returns:
            Saved PaperTradingConfig
        """
        stmt = select(PaperTradingConfigDB).limit(1).with_for_update()
        result = await self.session.execute(stmt)
        config_db = result.scalars().first()

        if config_db:
            # Update existing (row is locked via FOR UPDATE)
            config_db.enabled = config.enabled
            config_db.starting_capital = config.starting_capital
            config_db.commission_per_share = config.commission_per_share
            config_db.slippage_percentage = config.slippage_percentage
            config_db.use_realistic_fills = config.use_realistic_fills
        else:
            # Create new
            config_db = self._from_model(config)
            self.session.add(config_db)

        try:
            await self.session.commit()
        except IntegrityError:
            # Another concurrent request inserted first on empty table;
            # rollback and retry as an update.
            await self.session.rollback()
            stmt = select(PaperTradingConfigDB).limit(1).with_for_update()
            result = await self.session.execute(stmt)
            config_db = result.scalars().first()
            if config_db:
                config_db.enabled = config.enabled
                config_db.starting_capital = config.starting_capital
                config_db.commission_per_share = config.commission_per_share
                config_db.slippage_percentage = config.slippage_percentage
                config_db.use_realistic_fills = config.use_realistic_fills
                await self.session.commit()

        await self.session.refresh(config_db)

        logger.info(
            "paper_config_saved",
            config_id=str(config_db.id),
            starting_capital=float(config_db.starting_capital),
        )

        return self._to_model(config_db)

    def _to_model(self, config_db: PaperTradingConfigDB) -> PaperTradingConfig:
        """Convert database model to Pydantic model."""
        return PaperTradingConfig(
            enabled=config_db.enabled,
            starting_capital=Decimal(str(config_db.starting_capital)),
            commission_per_share=Decimal(str(config_db.commission_per_share)),
            slippage_percentage=Decimal(str(config_db.slippage_percentage)),
            use_realistic_fills=config_db.use_realistic_fills,
            created_at=config_db.created_at,
        )

    def _from_model(self, config: PaperTradingConfig) -> PaperTradingConfigDB:
        """Convert Pydantic model to database model."""
        return PaperTradingConfigDB(
            enabled=config.enabled,
            starting_capital=config.starting_capital,
            commission_per_share=config.commission_per_share,
            slippage_percentage=config.slippage_percentage,
            use_realistic_fills=config.use_realistic_fills,
        )
