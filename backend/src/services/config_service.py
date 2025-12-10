"""
Configuration service for business logic and validation.

Provides high-level operations for managing system configuration.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.config import SystemConfiguration
from src.repositories.config_repository import ConfigurationRepository


class ConfigurationService:
    """Service for managing system configuration.

    Handles validation, business logic, and orchestration of configuration operations.

    Example:
        >>> service = ConfigurationService(session)
        >>> config = await service.get_current_configuration()
        >>> config.risk_limits.max_risk_per_trade = Decimal("2.5")
        >>> updated = await service.update_configuration(config, current_version=5)
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = ConfigurationRepository(session)

    async def get_current_configuration(self) -> Optional[SystemConfiguration]:
        """Get the current active system configuration.

        Returns:
            Current SystemConfiguration or None if not configured
        """
        return await self.repository.get_current_config()

    async def get_configuration_by_version(self, version: int) -> Optional[SystemConfiguration]:
        """Get a specific configuration version.

        Args:
            version: Configuration version number

        Returns:
            SystemConfiguration for the specified version or None
        """
        return await self.repository.get_config_by_version(version)

    async def update_configuration(
        self, config: SystemConfiguration, current_version: int, applied_by: Optional[str] = None
    ) -> SystemConfiguration:
        """Update system configuration with validation and optimistic locking.

        Args:
            config: New configuration to apply
            current_version: Expected current version (for optimistic locking)
            applied_by: Username or system identifier applying the change

        Returns:
            Updated SystemConfiguration with new version

        Raises:
            OptimisticLockError: If version conflict detected
            ValueError: If configuration validation fails

        Example:
            >>> try:
            ...     updated = await service.update_configuration(
            ...         config=new_config,
            ...         current_version=5,
            ...         applied_by="trader_001"
            ...     )
            ... except OptimisticLockError:
            ...     # Handle conflict - refetch and retry
            ...     pass
        """
        # Validate configuration (Pydantic validation happens automatically)
        self._validate_business_rules(config)

        # Set applied_by if provided
        if applied_by:
            config.applied_by = applied_by

        # Update with optimistic locking
        updated_config = await self.repository.update_config(config, current_version)

        # TODO: Log configuration change to audit trail (Story 10.8 integration)

        return updated_config

    def _validate_business_rules(self, config: SystemConfiguration) -> None:
        """Validate business rules beyond Pydantic field validation.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If business rule validation fails
        """
        # Validate risk limit hierarchy
        if not (
            config.risk_limits.max_risk_per_trade
            < config.risk_limits.max_campaign_risk
            < config.risk_limits.max_portfolio_heat
        ):
            raise ValueError(
                "Risk limits must satisfy: "
                "max_risk_per_trade < max_campaign_risk < max_portfolio_heat"
            )

        # Validate cause factor range
        if config.cause_factors.min_cause_factor >= config.cause_factors.max_cause_factor:
            raise ValueError("min_cause_factor must be less than max_cause_factor")

        # Validate spring volume range
        if config.volume_thresholds.spring_volume_min > config.volume_thresholds.spring_volume_max:
            raise ValueError("spring_volume_min must be less than or equal to spring_volume_max")

    async def get_configuration_history(self, limit: int = 10) -> list[SystemConfiguration]:
        """Get recent configuration change history.

        Args:
            limit: Maximum number of historical configurations to return

        Returns:
            List of SystemConfiguration objects ordered by version descending
        """
        return await self.repository.get_configuration_history(limit)
