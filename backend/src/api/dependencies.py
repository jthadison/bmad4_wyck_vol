"""
FastAPI Dependencies

Provides dependency injection for database sessions, authentication, authorization, and Redis.
"""

from collections.abc import AsyncGenerator
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.token_service import TokenService
from src.config import settings
from src.database import async_session_maker

# Global Redis client instance (lazy initialized)
_redis_client: Redis | None = None


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    """
    FastAPI dependency for Redis client.

    Provides async Redis client with lazy initialization.
    Client is reused across requests for connection pooling.

    Yields:
        Redis: Async Redis client

    Example:
        ```python
        @app.get("/cache")
        async def get_cached_data(
            redis: Redis = Depends(get_redis_client)
        ):
            value = await redis.get("key")
            return {"value": value}
        ```
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,
        )

    yield _redis_client


# Security scheme for Bearer token authentication
security = HTTPBearer()

# Token service instance (uses settings for configuration)
token_service = TokenService(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Provides async database session with automatic cleanup.
    Use with FastAPI's Depends() for automatic session management.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @app.get("/settings")
        async def get_settings(
            db: AsyncSession = Depends(get_db_session),
            user_id: UUID = Depends(get_current_user_id)
        ):
            settings = await db.execute(select(UserSettings).where(user_id=user_id))
            return settings.scalar_one_or_none()
        ```
    """
    async with async_session_maker() as session:
        try:
            yield session
            # Commit is handled by individual operations
        except Exception:
            # Rollback on error
            await session.rollback()
            raise
        finally:
            await session.close()


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    return token_service.decode_token(token)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UUID:
    """
    FastAPI dependency to extract and validate current user ID from JWT token.

    Extracts the user ID from the Authorization header Bearer token.
    Raises 401 Unauthorized if token is invalid or missing.

    Args:
        credentials: HTTP Authorization credentials (Bearer token)

    Returns:
        UUID: Authenticated user's ID

    Raises:
        HTTPException: 401 if authentication fails

    Example:
        ```python
        @app.get("/settings")
        async def get_settings(user_id: UUID = Depends(get_current_user_id)):
            # user_id is automatically extracted from JWT token
            return {"user_id": user_id}
        ```
    """
    token = credentials.credentials

    # Decode the JWT token
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user_id from token payload
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convert to UUID
    try:
        user_id = UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    return user_id


async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[UUID]:
    """
    FastAPI dependency for optional authentication.

    Similar to get_current_user_id but returns None if no token is provided
    instead of raising an exception. Useful for endpoints that have different
    behavior for authenticated vs anonymous users.

    Args:
        credentials: Optional HTTP Authorization credentials

    Returns:
        UUID or None: User ID if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return None


# TODO: Implement these additional auth dependencies for Phase 2


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db_session)
):
    """
    Get the full user object for the authenticated user.

    This is a convenience dependency that combines authentication
    and user lookup. Use when you need more than just the user_id.

    Args:
        user_id: Authenticated user ID
        db: Database session

    Returns:
        User object from database

    Raises:
        HTTPException: 404 if user not found
    """
    from src.repositories.user_repository import UserRepository

    repo = UserRepository(db)
    user = await repo.get_user(user_id)

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


async def require_scope(required_scope: str):
    """
    Dependency factory for API key scope validation.

    Use this to restrict endpoints to users with specific API key scopes.

    Args:
        required_scope: The scope required (e.g., "read", "write", "admin")

    Example:
        ```python
        @app.post("/trading/execute")
        async def execute_trade(
            user_id: UUID = Depends(require_scope("write"))
        ):
            # Only users with "write" scope can access
            pass
        ```
    """
    # TODO: Implement scope checking using API key scopes
    # For now, just return get_current_user_id
    # In Phase 2, decode token and check scopes
    return get_current_user_id
