"""
JWT Token Service

Handles generation, validation, and refresh of JWT access and refresh tokens.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from jose import JWTError, jwt


class TokenService:
    """Service for JWT token operations"""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7
    ):
        """
        Initialize token service

        Args:
            secret_key: Secret key for JWT signing
            algorithm: JWT algorithm (default: HS256)
            access_token_expire_minutes: Access token expiration in minutes (default: 30)
            refresh_token_expire_days: Refresh token expiration in days (default: 7)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    def create_access_token(self, user_id: UUID, additional_claims: Optional[dict] = None) -> str:
        """
        Create JWT access token

        Args:
            user_id: User UUID
            additional_claims: Optional additional claims to include

        Returns:
            Encoded JWT token string

        Example:
            ```python
            service = TokenService(secret_key="secret")
            token = service.create_access_token(user_id)
            ```
        """
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)

        claims = {
            "sub": str(user_id),
            "type": "access",
            "iat": now,
            "exp": expire,
        }

        # Add additional claims if provided
        if additional_claims:
            claims.update(additional_claims)

        token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
        return token

    def create_refresh_token(self, user_id: UUID) -> str:
        """
        Create JWT refresh token

        Refresh tokens have longer expiration and can only be used to get new access tokens.

        Args:
            user_id: User UUID

        Returns:
            Encoded JWT refresh token string

        Example:
            ```python
            service = TokenService(secret_key="secret")
            refresh_token = service.create_refresh_token(user_id)
            ```
        """
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire_days)

        claims = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": now,
            "exp": expire,
        }

        token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
        return token

    def create_token_pair(self, user_id: UUID) -> Tuple[str, str]:
        """
        Create both access and refresh tokens

        Args:
            user_id: User UUID

        Returns:
            Tuple of (access_token, refresh_token)

        Example:
            ```python
            service = TokenService(secret_key="secret")
            access, refresh = service.create_token_pair(user_id)
            ```
        """
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token(user_id)
        return access_token, refresh_token

    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded token payload or None if invalid

        Example:
            ```python
            service = TokenService(secret_key="secret")
            payload = service.decode_token(token)
            if payload:
                user_id = payload["sub"]
            ```
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    def verify_access_token(self, token: str) -> Optional[UUID]:
        """
        Verify access token and extract user ID

        Args:
            token: JWT access token string

        Returns:
            User UUID if valid access token, None otherwise

        Example:
            ```python
            service = TokenService(secret_key="secret")
            user_id = service.verify_access_token(token)
            if user_id:
                # Token is valid
                pass
            ```
        """
        payload = self.decode_token(token)

        if payload is None:
            return None

        # Verify token type
        if payload.get("type") != "access":
            return None

        # Extract user_id
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None

        try:
            user_id = UUID(user_id_str)
            return user_id
        except ValueError:
            return None

    def verify_refresh_token(self, token: str) -> Optional[UUID]:
        """
        Verify refresh token and extract user ID

        Args:
            token: JWT refresh token string

        Returns:
            User UUID if valid refresh token, None otherwise

        Example:
            ```python
            service = TokenService(secret_key="secret")
            user_id = service.verify_refresh_token(refresh_token)
            if user_id:
                # Generate new access token
                new_access = service.create_access_token(user_id)
            ```
        """
        payload = self.decode_token(token)

        if payload is None:
            return None

        # Verify token type
        if payload.get("type") != "refresh":
            return None

        # Extract user_id
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None

        try:
            user_id = UUID(user_id_str)
            return user_id
        except ValueError:
            return None

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """
        Get token expiration time

        Args:
            token: JWT token string

        Returns:
            Expiration datetime or None if invalid

        Example:
            ```python
            service = TokenService(secret_key="secret")
            exp = service.get_token_expiration(token)
            if exp and exp > datetime.utcnow():
                # Token still valid
                pass
            ```
        """
        payload = self.decode_token(token)

        if payload is None:
            return None

        exp_timestamp = payload.get("exp")
        if exp_timestamp is None:
            return None

        return datetime.fromtimestamp(exp_timestamp)

    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired

        Args:
            token: JWT token string

        Returns:
            True if expired or invalid, False if still valid

        Example:
            ```python
            service = TokenService(secret_key="secret")
            if service.is_token_expired(token):
                # Need to refresh or re-authenticate
                pass
            ```
        """
        expiration = self.get_token_expiration(token)

        if expiration is None:
            return True

        return expiration <= datetime.utcnow()
