"""
User Settings Pydantic Models

Models for user preferences, settings, and API key management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserSettings(BaseModel):
    """User settings model"""

    user_id: UUID
    email: EmailStr
    settings: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    updated_at: datetime


class UserSettingsExport(BaseModel):
    """User settings export model (for backup/restore)"""

    user_id: UUID
    email: EmailStr
    settings: dict[str, Any]
    version: int
    exported_at: datetime


class ChangePasswordRequest(BaseModel):
    """Request model for password change"""

    current_password: str = Field(..., min_length=12, max_length=255)
    new_password: str = Field(..., min_length=12, max_length=255)


class APIKey(BaseModel):
    """API key model (masked for display)"""

    id: UUID
    user_id: UUID
    name: str
    masked_key: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None = None
    is_active: bool


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating API key"""

    name: str = Field(..., min_length=1, max_length=100, description="Key name/description")
    scopes: list[str] = Field(
        default_factory=list, description="Permission scopes (e.g., ['read', 'write'])"
    )
    expires_days: int = Field(default=90, ge=1, le=365, description="Days until expiration (1-365)")


class CreateAPIKeyResponse(BaseModel):
    """Response model for API key creation"""

    key_id: UUID
    api_key: str = Field(..., description="Full API key (only shown once)")
    masked_key: str = Field(..., description="Masked key for display")
    name: str
    scopes: list[str]
    expires_at: datetime
    warning: str = Field(
        default="Save this key now. It will not be shown again.",
        description="Warning message about key storage",
    )
