"""
Auto-Execution Configuration Repository

Handles database operations for auto-execution configuration.
Story 19.14: Auto-Execution Configuration Backend
"""

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auto_execution_config import AutoExecutionConfig
from src.orm.models import AutoExecutionConfigORM


class AutoExecutionRepository:
    """Repository for auto-execution configuration database operations"""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_config(self, user_id: UUID) -> Optional[AutoExecutionConfig]:
        """
        Get auto-execution configuration for a user.

        Args:
            user_id: User UUID

        Returns:
            AutoExecutionConfig or None if not found
        """
        stmt = select(AutoExecutionConfigORM).where(AutoExecutionConfigORM.user_id == user_id)
        result = await self.session.execute(stmt)
        config_orm = result.scalar_one_or_none()

        if config_orm:
            return AutoExecutionConfig.model_validate(config_orm)
        return None

    async def create_config(
        self, user_id: UUID, config: Optional[AutoExecutionConfig] = None
    ) -> AutoExecutionConfig:
        """
        Create default auto-execution configuration for a user.

        Args:
            user_id: User UUID
            config: Optional configuration (uses defaults if None)

        Returns:
            Created AutoExecutionConfig
        """
        now = datetime.now(UTC)

        if config is None:
            # Create with defaults
            config = AutoExecutionConfig(
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )

        config_orm = AutoExecutionConfigORM(
            user_id=user_id,
            enabled=config.enabled,
            min_confidence=config.min_confidence,
            max_trades_per_day=config.max_trades_per_day,
            max_risk_per_day=config.max_risk_per_day,
            circuit_breaker_losses=config.circuit_breaker_losses,
            enabled_patterns=config.enabled_patterns,
            symbol_whitelist=config.symbol_whitelist,
            symbol_blacklist=config.symbol_blacklist,
            kill_switch_active=config.kill_switch_active,
            consent_given_at=config.consent_given_at,
            consent_ip_address=config.consent_ip_address,
            created_at=now,
            updated_at=now,
        )

        self.session.add(config_orm)
        await self.session.commit()
        await self.session.refresh(config_orm)

        return AutoExecutionConfig.model_validate(config_orm)

    async def update_config(self, user_id: UUID, updates: dict) -> AutoExecutionConfig:
        """
        Update auto-execution configuration.

        Args:
            user_id: User UUID
            updates: Dictionary of fields to update

        Returns:
            Updated AutoExecutionConfig

        Raises:
            ValueError: If config doesn't exist
        """
        now = datetime.now(UTC)
        updates["updated_at"] = now

        stmt = (
            update(AutoExecutionConfigORM)
            .where(AutoExecutionConfigORM.user_id == user_id)
            .values(**updates)
            .returning(AutoExecutionConfigORM)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        config_orm = result.scalar_one_or_none()
        if not config_orm:
            raise ValueError(f"Auto-execution config not found for user {user_id}")

        return AutoExecutionConfig.model_validate(config_orm)

    async def enable(self, user_id: UUID, consent_ip: str) -> AutoExecutionConfig:
        """
        Enable auto-execution with consent tracking.

        Args:
            user_id: User UUID
            consent_ip: IP address of user giving consent

        Returns:
            Updated AutoExecutionConfig

        Raises:
            ValueError: If config doesn't exist
        """
        now = datetime.now(UTC)

        stmt = (
            update(AutoExecutionConfigORM)
            .where(AutoExecutionConfigORM.user_id == user_id)
            .values(
                enabled=True,
                consent_given_at=now,
                consent_ip_address=consent_ip,
                kill_switch_active=False,  # Reset kill switch on enable
                updated_at=now,
            )
            .returning(AutoExecutionConfigORM)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        config_orm = result.scalar_one_or_none()
        if not config_orm:
            raise ValueError(f"Auto-execution config not found for user {user_id}")

        return AutoExecutionConfig.model_validate(config_orm)

    async def disable(self, user_id: UUID) -> AutoExecutionConfig:
        """
        Disable auto-execution.

        Args:
            user_id: User UUID

        Returns:
            Updated AutoExecutionConfig

        Raises:
            ValueError: If config doesn't exist
        """
        now = datetime.now(UTC)

        stmt = (
            update(AutoExecutionConfigORM)
            .where(AutoExecutionConfigORM.user_id == user_id)
            .values(enabled=False, updated_at=now)
            .returning(AutoExecutionConfigORM)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        config_orm = result.scalar_one_or_none()
        if not config_orm:
            raise ValueError(f"Auto-execution config not found for user {user_id}")

        return AutoExecutionConfig.model_validate(config_orm)

    async def activate_kill_switch(self, user_id: UUID) -> AutoExecutionConfig:
        """
        Activate emergency kill switch.

        Args:
            user_id: User UUID

        Returns:
            Updated AutoExecutionConfig

        Raises:
            ValueError: If config doesn't exist
        """
        now = datetime.now(UTC)

        stmt = (
            update(AutoExecutionConfigORM)
            .where(AutoExecutionConfigORM.user_id == user_id)
            .values(kill_switch_active=True, updated_at=now)
            .returning(AutoExecutionConfigORM)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        config_orm = result.scalar_one_or_none()
        if not config_orm:
            raise ValueError(f"Auto-execution config not found for user {user_id}")

        return AutoExecutionConfig.model_validate(config_orm)

    async def get_or_create_config(self, user_id: UUID) -> AutoExecutionConfig:
        """
        Get existing config or create default one if it doesn't exist.

        Args:
            user_id: User UUID

        Returns:
            AutoExecutionConfig (existing or newly created)
        """
        config = await self.get_config(user_id)
        if config is None:
            config = await self.create_config(user_id)
        return config
