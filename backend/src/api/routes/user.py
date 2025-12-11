"""
User and Settings API Routes

Endpoints for user settings management, password changes, and API key management.
"""

from uuid import UUID

from backend.src.api.dependencies import get_current_user_id, get_db_session
from backend.src.auth.api_key_service import APIKeyService
from backend.src.auth.password_service import PasswordService
from backend.src.models.user_settings import (
    APIKey,
    ChangePasswordRequest,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    UserSettings,
    UserSettingsExport,
)
from backend.src.repositories.user_repository import UserRepository
from backend.src.settings.service import SettingsService
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.get("/settings", response_model=UserSettings)
async def get_user_settings(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db_session)
):
    """
    Get user settings

    Returns complete user settings including appearance, notifications,
    trading preferences, and account settings.
    """
    repository = UserRepository(db)
    service = SettingsService(repository)

    settings = await service.get_user_settings(user_id)

    if settings is None:
        # Return default settings if none exist
        user = await repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        settings = service.get_default_settings(user_id, user["email"])
        # Save defaults
        await service.update_user_settings(user_id, settings)

    return settings


@router.put("/settings", response_model=UserSettings)
async def update_user_settings_full(
    settings: UserSettings,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update user settings (full update)

    Replaces all user settings with the provided values.
    """
    repository = UserRepository(db)
    service = SettingsService(repository)

    # Ensure user_id matches authenticated user
    settings.user_id = user_id

    try:
        updated_settings = await service.update_user_settings(user_id, settings, partial=False)
        return updated_settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}",
        )


@router.patch("/settings", response_model=UserSettings)
async def update_user_settings_partial(
    settings: dict,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update user settings (partial update)

    Updates only the provided fields, preserving other settings.
    """
    repository = UserRepository(db)
    service = SettingsService(repository)

    try:
        # Get existing settings
        existing = await service.get_user_settings(user_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")

        # Merge settings
        existing_dict = existing.dict()
        for key, value in settings.items():
            if isinstance(value, dict) and key in existing_dict:
                existing_dict[key].update(value)
            else:
                existing_dict[key] = value

        updated = UserSettings(**existing_dict)
        updated.user_id = user_id

        result = await service.update_user_settings(user_id, updated, partial=False)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}",
        )


@router.get("/settings/export")
async def export_user_settings(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db_session)
):
    """
    Export user settings as JSON file

    Returns settings with metadata as downloadable JSON file.
    """
    repository = UserRepository(db)
    service = SettingsService(repository)

    try:
        # Get user info for username
        user = await repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Export settings
        export = await service.export_settings(user_id, user["username"])

        # Prepare JSON response with download header
        from datetime import datetime

        filename = f"bmad-settings-{user['username']}-{datetime.utcnow().strftime('%Y%m%d')}.json"

        # Convert to JSON
        json_content = export.json(indent=2)

        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export settings: {str(e)}",
        )


@router.post("/settings/import", response_model=UserSettings)
async def import_user_settings(
    settings_export: UserSettingsExport,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Import user settings from JSON

    Validates and imports settings from exported JSON file.
    """
    repository = UserRepository(db)
    service = SettingsService(repository)

    try:
        updated = await service.import_settings(user_id, settings_export)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import settings: {str(e)}",
        )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Change user password

    Validates current password and updates to new password.
    """
    repository = UserRepository(db)
    password_service = PasswordService()

    try:
        # Get current user
        user = await repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Change password
        success, result, msg_type = password_service.change_password(
            request.current_password, user["password_hash"], request.new_password
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        # Update password in database
        await repository.update_password(user_id, result)

        return {"success": True, "message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}",
        )


@router.get("/api-keys", response_model=list[APIKey])
async def get_api_keys(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db_session)
):
    """
    Get all API keys for the user

    Returns list of API keys with masked key values.
    """
    repository = UserRepository(db)
    api_key_service = APIKeyService()

    try:
        keys_data = await repository.get_api_keys(user_id)

        # Convert to APIKey model with masked keys
        api_keys = []
        for key_data in keys_data:
            # Create full key for masking (we don't have the full key, just hash)
            # So we'll create a masked format from stored data
            masked_key = f"bmad_...{key_data['name'][-4:]}"  # Placeholder

            api_keys.append(
                APIKey(
                    id=key_data["id"],
                    name=key_data["name"],
                    key_masked=masked_key,
                    scopes=key_data["scopes"],
                    created_at=key_data["created_at"],
                    last_used_at=key_data["last_used_at"],
                    expires_at=key_data["expires_at"],
                    revoked_at=key_data["revoked_at"],
                )
            )

        return api_keys

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve API keys: {str(e)}",
        )


@router.post("/api-keys", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateAPIKeyRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Generate a new API key

    Returns the full API key - this is the ONLY time it will be shown.
    """
    repository = UserRepository(db)
    api_key_service = APIKeyService()

    try:
        # Create API key
        key_id, api_key, key_hash, expires_at = api_key_service.create_api_key(
            user_id, request.name, request.scopes, request.expires_days
        )

        # Store in database
        await repository.create_api_key(
            user_id=user_id,
            key_id=key_id,
            name=request.name,
            key_hash=key_hash,
            scopes=request.scopes,
            expires_at=expires_at,
        )

        # Return response with full key
        return CreateAPIKeyResponse(
            id=key_id, name=request.name, api_key=api_key, expires_at=expires_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}",
        )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Revoke an API key

    Soft deletes the key by setting revoked_at timestamp.
    """
    repository = UserRepository(db)

    try:
        # Verify key belongs to user
        keys = await repository.get_api_keys(user_id)
        key_exists = any(k["id"] == key_id for k in keys)

        if not key_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        # Revoke key
        success = await repository.revoke_api_key(key_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        return {"success": True, "message": "API key revoked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}",
        )
