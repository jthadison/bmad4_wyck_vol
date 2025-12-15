"""
User Settings Models

Stub implementation for user settings models.
TODO: Implement full user settings models.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserSettings(BaseModel):
    """User settings model."""

    user_id: UUID
    updated_at: datetime


class UserSettingsExport(BaseModel):
    """User settings export model."""

    user_id: UUID
    settings: dict


class ChangePasswordRequest(BaseModel):
    """Change password request model."""

    current_password: str
    new_password: str


class CreateAPIKeyRequest(BaseModel):
    """Create API key request model."""

    name: str
    description: Optional[str] = None


class CreateAPIKeyResponse(BaseModel):
    """Create API key response model."""

    api_key: str
    created_at: datetime


class APIKey(BaseModel):
    """API key model."""

    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
