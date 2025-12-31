"""
Authentication Models

Pydantic models for authentication requests and responses.
"""


from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request with username and password"""

    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "john_doe", "password": "SecurePassword123!"}}
    )

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class LoginResponse(BaseModel):
    """Login response with access and refresh tokens"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }
    )

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token"""

    model_config = ConfigDict(
        json_schema_extra={"example": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}}
    )

    refresh_token: str = Field(..., description="JWT refresh token")


class RefreshTokenResponse(BaseModel):
    """Response with new access token"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }
    )

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RegisterRequest(BaseModel):
    """User registration request"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "SecurePassword123!",
            }
        }
    )

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=12, description="Password (min 12 chars)")


class RegisterResponse(BaseModel):
    """User registration response"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "john_doe",
                "email": "john@example.com",
                "message": "User registered successfully",
            }
        }
    )

    user_id: str = Field(..., description="User UUID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    message: str = Field(default="User registered successfully", description="Success message")
