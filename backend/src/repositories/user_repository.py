"""
User Repository

Handles database operations for users and user settings.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    """Repository for user and user settings database operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: UUID) -> Optional[dict]:
        """
        Get user by ID

        Args:
            user_id: User UUID

        Returns:
            User dict or None if not found
        """
        from src.orm.models import User

        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "last_login_at": user.last_login_at,
            }
        return None

    async def get_settings(self, user_id: UUID) -> Optional[dict]:
        """
        Get user settings by user ID

        Args:
            user_id: User UUID

        Returns:
            Settings dict or None if not found
        """
        from src.orm.models import UserSettingsDB

        stmt = select(UserSettingsDB).where(UserSettingsDB.user_id == user_id)
        result = await self.session.execute(stmt)
        settings = result.scalar_one_or_none()

        if settings:
            return {
                "user_id": settings.user_id,
                "settings": settings.settings,
                "version": settings.version,
                "updated_at": settings.updated_at,
            }
        return None

    async def update_settings(self, user_id: UUID, settings: dict, version: int = 1) -> dict:
        """
        Update user settings (upsert operation)

        Args:
            user_id: User UUID
            settings: Settings dictionary
            version: Schema version

        Returns:
            Updated settings dict
        """
        from src.orm.models import UserSettingsDB

        now = datetime.utcnow()

        # Upsert operation
        stmt = (
            insert(UserSettingsDB)
            .values(user_id=user_id, settings=settings, version=version, updated_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"settings": settings, "version": version, "updated_at": now},
            )
        )

        await self.session.execute(stmt)
        await self.session.commit()

        return {"user_id": user_id, "settings": settings, "version": version, "updated_at": now}

    async def get_api_keys(self, user_id: UUID) -> list[dict]:
        """
        Get all API keys for a user

        Args:
            user_id: User UUID

        Returns:
            List of API key dicts
        """
        from src.orm.models import APIKeyDB

        stmt = (
            select(APIKeyDB).where(APIKeyDB.user_id == user_id).order_by(APIKeyDB.created_at.desc())
        )

        result = await self.session.execute(stmt)
        keys = result.scalars().all()

        return [
            {
                "id": key.id,
                "user_id": key.user_id,
                "name": key.name,
                "key_hash": key.key_hash,
                "scopes": key.scopes,
                "created_at": key.created_at,
                "last_used_at": key.last_used_at,
                "expires_at": key.expires_at,
                "revoked_at": key.revoked_at,
            }
            for key in keys
        ]

    async def create_api_key(
        self,
        user_id: UUID,
        key_id: UUID,
        name: str,
        key_hash: str,
        scopes: list[str],
        expires_at: datetime,
    ) -> dict:
        """
        Create a new API key

        Args:
            user_id: User UUID
            key_id: API key UUID
            name: Key name
            key_hash: SHA256 hash of the key
            scopes: List of scopes
            expires_at: Expiration datetime

        Returns:
            Created API key dict
        """
        from src.orm.models import APIKeyDB

        now = datetime.utcnow()

        api_key = APIKeyDB(
            id=key_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            scopes=scopes,
            created_at=now,
            expires_at=expires_at,
        )

        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)

        return {
            "id": api_key.id,
            "user_id": api_key.user_id,
            "name": api_key.name,
            "key_hash": api_key.key_hash,
            "scopes": api_key.scopes,
            "created_at": api_key.created_at,
            "last_used_at": api_key.last_used_at,
            "expires_at": api_key.expires_at,
            "revoked_at": api_key.revoked_at,
        }

    async def revoke_api_key(self, key_id: UUID) -> bool:
        """
        Revoke an API key (soft delete)

        Args:
            key_id: API key UUID

        Returns:
            True if revoked, False if not found
        """
        from src.orm.models import APIKeyDB

        now = datetime.utcnow()

        stmt = update(APIKeyDB).where(APIKeyDB.id == key_id).values(revoked_at=now)

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0 if hasattr(result, "rowcount") else False  # type: ignore[attr-defined]

    async def get_api_key_by_hash(self, key_hash: str) -> Optional[dict]:
        """
        Get API key by hash (for validation)

        Args:
            key_hash: SHA256 hash of the key

        Returns:
            API key dict or None if not found
        """
        from src.orm.models import APIKeyDB

        stmt = select(APIKeyDB).where(APIKeyDB.key_hash == key_hash)
        result = await self.session.execute(stmt)
        key = result.scalar_one_or_none()

        if key:
            return {
                "id": key.id,
                "user_id": key.user_id,
                "name": key.name,
                "key_hash": key.key_hash,
                "scopes": key.scopes,
                "created_at": key.created_at,
                "last_used_at": key.last_used_at,
                "expires_at": key.expires_at,
                "revoked_at": key.revoked_at,
            }
        return None

    async def update_api_key_last_used(self, key_id: UUID) -> None:
        """
        Update API key last_used_at timestamp

        Args:
            key_id: API key UUID
        """
        from src.orm.models import APIKeyDB

        now = datetime.utcnow()

        stmt = update(APIKeyDB).where(APIKeyDB.id == key_id).values(last_used_at=now)

        await self.session.execute(stmt)
        await self.session.commit()

    async def update_password(self, user_id: UUID, password_hash: str) -> bool:
        """
        Update user password hash

        Args:
            user_id: User UUID
            password_hash: New password hash

        Returns:
            True if updated, False if user not found
        """
        from src.orm.models import User

        now = datetime.utcnow()

        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=password_hash, updated_at=now)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0 if hasattr(result, "rowcount") else False  # type: ignore[attr-defined]
