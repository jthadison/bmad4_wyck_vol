"""
Authentication API Routes

Endpoints for login, token refresh, and user registration.
"""

from uuid import uuid4

from backend.src.api.dependencies import get_db_session, token_service
from backend.src.auth.password_service import PasswordService
from backend.src.config import settings
from backend.src.models.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Login with username and password

    Returns access and refresh tokens on successful authentication.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/login \\
          -H "Content-Type: application/json" \\
          -d '{"username": "john_doe", "password": "SecurePassword123!"}'
        ```

    Returns:
        LoginResponse with access_token, refresh_token, and expiration
    """
    from backend.src.db.models import User

    # Find user by username
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    password_service = PasswordService()
    is_valid = password_service.verify_password(request.password, user.password_hash)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    access_token, refresh_token = token_service.create_token_pair(user.id)

    # Update last_login_at
    from datetime import datetime

    user.last_login_at = datetime.utcnow()
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    Validates the refresh token and issues a new access token.
    Refresh tokens have longer expiration (7 days) and can only be used to get new access tokens.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/refresh \\
          -H "Content-Type: application/json" \\
          -d '{"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
        ```

    Returns:
        RefreshTokenResponse with new access_token
    """
    # Verify refresh token
    user_id = token_service.verify_refresh_token(request.refresh_token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate new access token
    access_token = token_service.create_access_token(user_id)

    return RefreshTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db_session)):
    """
    Register a new user

    Creates a new user account with username, email, and password.
    Password must meet strength requirements (min 12 chars, complexity).

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/register \\
          -H "Content-Type: application/json" \\
          -d '{
            "username": "john_doe",
            "email": "john@example.com",
            "password": "SecurePassword123!"
          }'
        ```

    Returns:
        RegisterResponse with user_id, username, and email
    """
    from datetime import datetime

    from backend.src.db.models import User

    # Check if username already exists
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    # Check if email already exists
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    existing_email = result.scalar_one_or_none()

    if existing_email is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Validate password strength
    password_service = PasswordService()
    is_valid, message = password_service.validate_password_strength(request.password)

    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    # Hash password
    password_hash = password_service.hash_password(request.password)

    # Create user
    user_id = uuid4()
    now = datetime.utcnow()

    new_user = User(
        id=user_id,
        username=request.username,
        email=request.email,
        password_hash=password_hash,
        created_at=now,
        updated_at=now,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return RegisterResponse(
        user_id=str(user_id),
        username=new_user.username,
        email=new_user.email,
        message="User registered successfully",
    )


@router.post("/logout")
async def logout():
    """
    Logout user (placeholder)

    In a production system, this would:
    1. Add the token to a blacklist (Redis)
    2. Invalidate all sessions for the user
    3. Clear any cached user data

    For now, client should discard the tokens.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/logout \\
          -H "Authorization: Bearer <access_token>"
        ```

    Returns:
        Success message
    """
    # TODO: Implement token blacklist with Redis
    # For now, client-side logout (discard tokens)
    return {
        "message": "Logout successful. Please discard your tokens.",
        "note": "Server-side token blacklist not yet implemented",
    }
