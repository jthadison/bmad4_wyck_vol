"""
Settings Service

Handles user settings management including defaults and validation.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.models.user_settings import UserSettings, UserSettingsExport
from src.repositories.user_repository import UserRepository


class SettingsService:
    """Service for managing user settings"""

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_default_settings(self, user_id: UUID, email: str) -> UserSettings:
        """
        Get default settings for a new user

        Args:
            user_id: User UUID
            email: User email

        Returns:
            UserSettings with default values
        """
        default_settings = {
            "appearance": {
                "theme": "dark",
                "compact_mode": False,
                "chart_colors": "default",
            },
            "notifications": {
                "email_enabled": True,
                "sms_enabled": False,
                "signal_alerts": True,
                "campaign_updates": True,
            },
            "trading": {
                "default_timeframe": "1d",
                "risk_per_trade": 2.0,
                "max_portfolio_risk": 5.0,
                "auto_approve_signals": False,
            },
            "account": {
                "timezone": "UTC",
                "language": "en",
            },
        }

        return UserSettings(
            user_id=user_id,
            email=email,
            settings=default_settings,
            version=1,
            updated_at=datetime.utcnow(),
        )

    async def get_user_settings(self, user_id: UUID) -> UserSettings | None:
        """
        Get user settings from database

        Args:
            user_id: User UUID

        Returns:
            UserSettings or None if not found
        """
        settings_data = await self.repository.get_settings(user_id)

        if settings_data is None:
            return None

        # Get user info for email
        user = await self.repository.get_user(user_id)
        if user is None:
            return None

        return UserSettings(
            user_id=settings_data["user_id"],
            email=user["email"],
            settings=settings_data["settings"],
            version=settings_data["version"],
            updated_at=settings_data["updated_at"],
        )

    async def update_user_settings(
        self, user_id: UUID, settings: UserSettings | dict[str, Any], partial: bool = False
    ) -> UserSettings:
        """
        Update user settings

        Args:
            user_id: User UUID
            settings: UserSettings model or settings dictionary
            partial: Whether this is a partial update (unused, for API compatibility)

        Returns:
            Updated UserSettings
        """
        # Extract settings dict if UserSettings object provided
        if isinstance(settings, UserSettings):
            settings_dict = settings.settings
        else:
            settings_dict = settings

        # Update in database
        updated_data = await self.repository.update_settings(user_id, settings_dict, version=1)

        # Get user info for email
        user = await self.repository.get_user(user_id)
        if user is None:
            raise ValueError("User not found")

        return UserSettings(
            user_id=updated_data["user_id"],
            email=user["email"],
            settings=updated_data["settings"],
            version=updated_data["version"],
            updated_at=updated_data["updated_at"],
        )

    async def export_settings(self, user_id: UUID, username: str) -> UserSettingsExport:
        """
        Export user settings with metadata

        Args:
            user_id: User UUID
            username: Username for export metadata

        Returns:
            UserSettingsExport with settings and metadata

        Raises:
            ValueError: If settings not found
        """
        settings = await self.get_user_settings(user_id)
        if settings is None:
            raise ValueError("Settings not found")

        return UserSettingsExport(
            export_version="1.0",
            exported_at=datetime.utcnow(),
            username=username,
            settings=settings.settings,
        )

    async def import_settings(
        self, user_id: UUID, settings_export: UserSettingsExport
    ) -> UserSettings:
        """
        Import user settings from export

        Args:
            user_id: User UUID
            settings_export: UserSettingsExport object

        Returns:
            Updated UserSettings

        Raises:
            ValueError: If validation fails
        """
        # Validate export version
        if settings_export.export_version != "1.0":
            raise ValueError(f"Unsupported export version: {settings_export.export_version}")

        # Update settings
        return await self.update_user_settings(user_id, settings_export.settings)
