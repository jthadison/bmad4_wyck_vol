"""
Configuration repository for database operations.

Handles CRUD operations for system configuration with optimistic locking support.
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.config import SystemConfiguration


class OptimisticLockError(Exception):
    """Raised when optimistic locking conflict occurs."""

    pass


class ConfigurationRepository:
    """Repository for system configuration persistence.

    Implements optimistic locking to prevent concurrent update conflicts.

    Example:
        >>> async with session.begin():
        ...     repo = ConfigurationRepository(session)
        ...     config = await repo.get_current_config()
        ...     config.version += 1
        ...     await repo.update_config(config, old_version=config.version - 1)
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_current_config(self) -> Optional[SystemConfiguration]:
        """Get the current (latest version) system configuration.

        Returns:
            Current SystemConfiguration or None if no configuration exists

        Example:
            >>> config = await repo.get_current_config()
            >>> print(f"Current version: {config.version}")
        """
        # Query for latest version
        query = text(
            """
            SELECT
                id,
                version,
                configuration_json,
                applied_at,
                applied_by,
                created_at
            FROM system_configuration
            ORDER BY version DESC
            LIMIT 1
        """
        )

        result = await self.session.execute(query)
        row = result.first()

        if not row:
            return None

        # Parse configuration_json into SystemConfiguration model
        config_data = row.configuration_json
        config_data["id"] = row.id
        config_data["applied_at"] = row.applied_at

        return SystemConfiguration(**config_data)

    async def get_config_by_version(self, version: int) -> Optional[SystemConfiguration]:
        """Get a specific configuration version.

        Args:
            version: Configuration version number

        Returns:
            SystemConfiguration for the specified version or None
        """
        query = text(
            """
            SELECT
                id,
                version,
                configuration_json,
                applied_at,
                applied_by,
                created_at
            FROM system_configuration
            WHERE version = :version
        """
        )

        result = await self.session.execute(query, {"version": version})
        row = result.first()

        if not row:
            return None

        config_data = row.configuration_json
        config_data["id"] = row.id
        config_data["applied_at"] = row.applied_at

        return SystemConfiguration(**config_data)

    async def update_config(
        self, config: SystemConfiguration, old_version: int
    ) -> SystemConfiguration:
        """Update system configuration with optimistic locking.

        Args:
            config: New configuration to save
            old_version: Expected current version (for optimistic locking)

        Returns:
            Updated SystemConfiguration with new version number

        Raises:
            OptimisticLockError: If version conflict detected (concurrent update)

        Example:
            >>> try:
            ...     updated = await repo.update_config(new_config, old_version=5)
            ... except OptimisticLockError:
            ...     # Refetch and retry
            ...     current = await repo.get_current_config()
        """
        # Verify current version matches expected
        current_config = await self.get_current_config()

        if current_config is None:
            raise ValueError("No current configuration exists")

        if current_config.version != old_version:
            raise OptimisticLockError(
                f"Configuration version mismatch. "
                f"Expected {old_version}, found {current_config.version}. "
                f"Configuration was modified by another process."
            )

        # Increment version for new config
        new_version = old_version + 1
        config.version = new_version
        config.applied_at = datetime.utcnow()

        # Convert to JSON for storage
        config_dict = config.model_dump(mode="json")

        # Insert new configuration record
        insert_query = text(
            """
            INSERT INTO system_configuration (
                id,
                version,
                configuration_json,
                applied_at,
                applied_by
            ) VALUES (
                :id,
                :version,
                :configuration_json,
                :applied_at,
                :applied_by
            )
            RETURNING id, version, applied_at, created_at
        """
        )

        try:
            result = await self.session.execute(
                insert_query,
                {
                    "id": str(config.id),
                    "version": new_version,
                    # Serialize dict to JSON string for psycopg3 compatibility
                    "configuration_json": json.dumps(config_dict),
                    "applied_at": config.applied_at,
                    "applied_by": config.applied_by,
                },
            )
            await self.session.commit()

            row = result.first()
            config.version = row.version
            config.applied_at = row.applied_at

            return config

        except IntegrityError as e:
            await self.session.rollback()
            raise OptimisticLockError(
                f"Failed to update configuration due to concurrent modification: {str(e)}"
            ) from e

    async def get_configuration_history(self, limit: int = 10) -> list[SystemConfiguration]:
        """Get configuration history (most recent first).

        Args:
            limit: Maximum number of historical configurations to return

        Returns:
            List of SystemConfiguration objects ordered by version descending
        """
        query = text(
            """
            SELECT
                id,
                version,
                configuration_json,
                applied_at,
                applied_by,
                created_at
            FROM system_configuration
            ORDER BY version DESC
            LIMIT :limit
        """
        )

        result = await self.session.execute(query, {"limit": limit})
        rows = result.fetchall()

        configs = []
        for row in rows:
            config_data = row.configuration_json
            config_data["id"] = row.id
            config_data["applied_at"] = row.applied_at
            configs.append(SystemConfiguration(**config_data))

        return configs
